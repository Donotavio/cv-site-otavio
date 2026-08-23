"""
Observatório Eleições 2026 — Gold (house effect dos institutos → JSON de frontend)
==================================================================================
Lê o snapshot bronze mais recente das pesquisas presidenciais (Wikipedia, formato
long — o MESMO bronze do gold_precandidatos) e calcula o "house effect" de cada
instituto: o desvio sistemático das medições dele em relação à média dos demais
institutos no mesmo período, por candidato. Zero coleta nova, zero LLM em runtime.

Uso:
    python transform_eleicoes/gold_house_effect.py
Saída:
    data/gold/eleicoes_house_effect.parquet    (1 linha por instituto × candidato)
    assets/data/eleicoes_house_effect.json     (consumido pela página Astro)

Método (leave-one-out):
    Universo = cenários de 1º turno (estimulado) do ano da eleição — o mesmo
    filtro que gold_precandidatos usa para a média — restrito aos candidatos
    mais medidos. Ponto de medição = (instituto, candidato, data), com cenários
    múltiplos da mesma pesquisa colapsados pela média. Para cada ponto, a
    referência é a média dos pontos de TODOS os outros institutos para o mesmo
    candidato numa janela de ±JANELA_HOUSE_DIAS dias; o próprio instituto fica
    de fora da referência (sem isso ele se ancoraria em si mesmo). Pontos com
    menos de MIN_PONTOS_REFERENCIA medições alheias na janela são descartados.
    Resíduo = pct − referência; house effect(i, c) = média dos resíduos.

Enquadramento (apartidário): house effect NÃO é erro nem manipulação — é a
assinatura metodológica de cada instituto. Nenhum adjetivo sobre institutos.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    ANO_ELEICAO_PRESIDENCIAL,
    CENARIO_1T,
    WIKIPEDIA_PRESIDENCIAL_URL,
)

BRONZE_DIR = Path("data/bronze/eleicoes_precandidatos")
GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")

# --- Parâmetros do método (documentados no payload) -------------------------
JANELA_HOUSE_DIAS = 14      # ±dias em torno de cada medição para a referência
MIN_PONTOS_REFERENCIA = 3   # mínimo de medições de OUTROS institutos na janela
MIN_PONTOS_PUBLICAR = 5     # efeito só é publicado com pelo menos N pontos
SIG_EFEITO_PP = 1.0         # |efeito| mínimo (pp) para marcar significativo…
SIG_MIN_PONTOS = 8          # …e mínimo de pontos para a marca de significância
N_CANDIDATOS = 3            # candidatos avaliados (os N mais medidos no universo)
SANITY_TOL_PP = 0.3         # tolerância do sanity check leave-one-out


def _latest_bronze() -> Path:
    files = sorted(BRONZE_DIR.glob("precandidatos_*.parquet"))
    if not files:
        raise RuntimeError(
            "Sem bronze — rode ingestion_eleicoes/collect_precandidatos.py antes."
        )
    return files[-1]


def _limpar(df):
    import pandas as pd

    df["dt_fim"] = pd.to_datetime(df["dt_fim"], errors="coerce")
    df["pct"] = pd.to_numeric(df["pct"], errors="coerce")
    df = df.dropna(subset=["dt_fim", "pct", "candidato"])
    df = df[(df["pct"] >= 0) & (df["pct"] <= 100)]
    return df


def _pontos(df):
    """Universo do método + colapso em pontos de medição.

    Mesmo filtro da média do gold_precandidatos (_primeiro_turno): cenário de
    1º turno E ano da eleição. Uma pesquisa pode publicar vários cenários de 1º
    turno (com/sem certos nomes); colapsar por (instituto, candidato, data) com
    a média evita que uma única pesquisa com 5 variantes conte como 5 pontos.
    """
    t1 = df[(df["cenario"] == CENARIO_1T) & (df["ano"] == ANO_ELEICAO_PRESIDENCIAL)]
    if t1.empty:
        return t1
    return t1.groupby(["instituto", "candidato", "dt_fim"], as_index=False)["pct"].mean()


def _top_candidatos(pts) -> list[str]:
    """Os N candidatos mais medidos (por pontos colapsados), com empate no corte."""
    vol = pts.groupby("candidato").size().sort_values(ascending=False)
    if len(vol) <= N_CANDIDATOS:
        return list(vol.index)
    corte = vol.iloc[N_CANDIDATOS - 1]
    return list(vol[vol >= corte].index)


def _residuos(pts, candidatos: list[str]):
    """Resíduo leave-one-out por ponto; retorna (DataFrame, n_descartados)."""
    import pandas as pd

    janela = pd.Timedelta(days=JANELA_HOUSE_DIAS)
    linhas: list[dict] = []
    descartados = 0
    for cand in candidatos:
        sub = pts[pts["candidato"] == cand]
        for _, r in sub.iterrows():
            outros = sub[
                (sub["instituto"] != r["instituto"])
                & ((sub["dt_fim"] - r["dt_fim"]).abs() <= janela)
            ]
            if len(outros) < MIN_PONTOS_REFERENCIA:
                descartados += 1
                continue
            linhas.append(
                {
                    "instituto": r["instituto"],
                    "candidato": cand,
                    "dt_fim": r["dt_fim"],
                    "pct": float(r["pct"]),
                    "referencia": float(outros["pct"].mean()),
                    "residuo": float(r["pct"] - outros["pct"].mean()),
                }
            )
    return pd.DataFrame(linhas), descartados


def _efeitos(res):
    """Tabela gold: 1 linha por instituto × candidato, com flags editoriais."""
    eff = (
        res.groupby(["instituto", "candidato"])["residuo"]
        .agg(efeito_pp="mean", desvio_pp="std", n_pontos="count")
        .reset_index()
    )
    eff["publicado"] = eff["n_pontos"] >= MIN_PONTOS_PUBLICAR
    # significância avaliada sobre o valor ARREDONDADO (1 casa) — o mesmo que o
    # leitor vê no painel; flag e número impresso nunca podem discordar
    eff["significativo"] = (eff["efeito_pp"].round(1).abs() >= SIG_EFEITO_PP) & (
        eff["n_pontos"] >= SIG_MIN_PONTOS
    )
    return eff


def _sanity(eff) -> dict:
    """Média dos efeitos ponderada por n_pontos ≈ 0 por candidato (leave-one-out).

    Calculada sobre TODOS os efeitos (antes do filtro editorial de publicação),
    que é onde a propriedade vale. Não é exatamente zero porque cada ponto usa
    uma referência própria (janela ± dias, institutos distintos excluídos).
    """
    por_candidato = {}
    ok = True
    for cand, grp in eff.groupby("candidato"):
        w = float((grp["efeito_pp"] * grp["n_pontos"]).sum() / grp["n_pontos"].sum())
        por_candidato[cand] = round(w, 2)
        ok = ok and abs(w) <= SANITY_TOL_PP
    return {
        "descricao": (
            "Propriedade do leave-one-out: a média dos efeitos ponderada pelo "
            "número de pontos deve ficar próxima de 0 pp para cada candidato "
            f"(tolerância ±{SANITY_TOL_PP} pp)."
        ),
        "media_ponderada_pp": por_candidato,
        "ok": ok,
    }


def _payload(pts, eff, sanity: dict, descartados: int, candidatos: list[str]) -> dict:
    pub = eff[eff["publicado"]]

    lista_candidatos = [
        {
            "nome": cand,
            "n_institutos_avaliados": int((pub["candidato"] == cand).sum()),
        }
        for cand in candidatos
    ]

    # nº de pesquisas por instituto no universo: datas distintas de campo
    # (uma pesquisa pode publicar vários cenários; a data identifica o campo)
    n_pesquisas = pts.groupby("instituto")["dt_fim"].nunique().to_dict()

    institutos = []
    for inst, grp in pub.groupby("instituto"):
        efeitos = [
            {
                "candidato": r["candidato"],
                "efeito_pp": round(float(r["efeito_pp"]), 1),
                "n_pontos": int(r["n_pontos"]),
                "significativo": bool(r["significativo"]),
            }
            for _, r in grp.sort_values("candidato").iterrows()
        ]
        institutos.append(
            {
                "nome": inst,
                "n_pesquisas_total": int(n_pesquisas.get(inst, 0)),
                "efeitos": efeitos,
            }
        )
    institutos.sort(key=lambda d: (-d["n_pesquisas_total"], d["nome"]))

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "Wikipedia — agregação de pesquisas de institutos registrados no TSE",
        "fonte_url": WIKIPEDIA_PRESIDENCIAL_URL,
        "ano_eleicao": ANO_ELEICAO_PRESIDENCIAL,
        "metodologia": (
            "Para cada medição de um instituto (candidato, data), calculamos a "
            "média do que todos os OUTROS institutos mediram para o mesmo "
            f"candidato em uma janela de ±{JANELA_HOUSE_DIAS} dias — a medição "
            "do próprio instituto fica de fora da referência (leave-one-out). O "
            "house effect é a média dessas diferenças: quanto o instituto tende "
            "a medir acima (+) ou abaixo (−) da média dos demais para aquele "
            "candidato, em pontos percentuais. Universo: cenários de 1º turno "
            "(estimulado) do ano da eleição, candidatos mais medidos; cenários "
            "múltiplos da mesma pesquisa são colapsados pela média e só entram "
            f"pontos com pelo menos {MIN_PONTOS_REFERENCIA} medições de outros "
            "institutos na janela."
        ),
        "disclaimer": (
            "House effect é o desvio sistemático de um instituto em relação à "
            "média dos demais — NÃO é erro, viés intencional nem manipulação. "
            "Ele reflete escolhas metodológicas legítimas, como o modo de "
            "coleta (presencial, telefônico ou online), a ponderação da "
            "amostra e o tratamento de indecisos. Serve para ler uma pesquisa "
            "nova sabendo a 'assinatura' de quem a produziu."
        ),
        "janela_dias": JANELA_HOUSE_DIAS,
        "criterio_significancia": (
            f"Efeito publicado apenas com n_pontos ≥ {MIN_PONTOS_PUBLICAR}. "
            f"Marcado como significativo somente quando |efeito| ≥ "
            f"{SIG_EFEITO_PP:.1f} ponto percentual E n_pontos ≥ {SIG_MIN_PONTOS} "
            "— abaixo disso, a diferença é indistinguível de ruído amostral."
        ),
        "universo": {
            "cenario": CENARIO_1T,
            "ano": ANO_ELEICAO_PRESIDENCIAL,
            "n_pontos_medicao": int(len(pts)),
            "n_institutos": int(pts["instituto"].nunique()),
            "n_pontos_descartados_janela": int(descartados),
            "periodo": {
                "primeira": pts["dt_fim"].min().strftime("%Y-%m-%d"),
                "ultima": pts["dt_fim"].max().strftime("%Y-%m-%d"),
            },
        },
        "sanity_check": sanity,
        "candidatos": lista_candidatos,
        "institutos": institutos,
    }


def main() -> int:
    import pandas as pd

    print("🗳  Observatório Eleições 2026 — gold (house effect dos institutos)")
    src = _latest_bronze()
    df = pd.read_parquet(src)
    print(f"  • bronze: {src.name} ({len(df):,} linhas)")

    df = _limpar(df)
    pts_all = _pontos(df)
    if pts_all.empty:
        print("  ✗ universo vazio (1º turno / ano da eleição) — nada a fazer.")
        return 1
    candidatos = _top_candidatos(pts_all)
    pts = pts_all[pts_all["candidato"].isin(candidatos)]
    vol = pts.groupby("candidato").size().sort_values(ascending=False)
    print(
        f"  • universo 1T/{ANO_ELEICAO_PRESIDENCIAL}: {len(pts_all):,} pontos · "
        f"{pts_all['instituto'].nunique()} institutos"
    )
    print(
        "  • candidatos avaliados: "
        + " · ".join(f"{c} ({vol[c]} pts)" for c in candidatos)
    )

    res, descartados = _residuos(pts, candidatos)
    if res.empty:
        print("  ✗ nenhum ponto com referência suficiente — nada a publicar.")
        return 1
    print(f"  • resíduos: {len(res):,} pontos usados · {descartados} descartados (janela rala)")

    eff = _efeitos(res)
    sanity = _sanity(eff)
    for cand, valor in sanity["media_ponderada_pp"].items():
        print(f"  • sanity {cand}: média ponderada {valor:+.2f} pp")
    if not sanity["ok"]:
        print("  ⚠ sanity check fora da tolerância — revisar método/janela.")

    payload = _payload(pts, eff, sanity, descartados, candidatos)

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    eff.to_parquet(GOLD_DIR / "eleicoes_house_effect.parquet", index=False)

    out_json = FRONTEND_DIR / "eleicoes_house_effect.json"
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    n_pub = int(eff["publicado"].sum())
    n_sig = int((eff["publicado"] & eff["significativo"]).sum())
    print(f"  ✓ {out_json}")
    print(
        f"    {len(payload['institutos'])} institutos publicados · "
        f"{n_pub} efeitos (n≥{MIN_PONTOS_PUBLICAR}) · {n_sig} significativos"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
