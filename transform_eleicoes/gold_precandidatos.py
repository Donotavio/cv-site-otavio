"""
Observatório Eleições 2026 — Gold (pré-candidatos → JSON de frontend)
=====================================================================
Lê o snapshot bronze mais recente (pesquisas presidenciais agregadas da
Wikipedia, formato long) e agrega para o painel: panorama de pré-candidatos,
snapshot + médias de 1º turno, confrontos de 2º turno e série temporal mensal.
Zero LLM em runtime.

Uso:
    python transform_eleicoes/gold_precandidatos.py
Saída:
    data/gold/eleicoes_precandidatos.parquet   (bronze limpo, 1 linha/medição)
    assets/data/eleicoes_precandidatos.json     (consumido pela página Astro)

Enquadramento (apartidário): cada pesquisa carrega instituto + data + margem; o
"líder" é só destaque visual, nunca previsão. Candidatos com pouca presença na
janela recente são descartados (ruído/cenários hipotéticos).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    ANO_ELEICAO_PRESIDENCIAL,
    CENARIO_1T,
    CENARIO_2T,
    JANELA_RECENTE_DIAS,
    MIN_PESQUISAS_RECENTES,
    PCT_MIN_RELEVANTE,
    WIKIPEDIA_PRESIDENCIAL_URL,
)

BRONZE_DIR = Path("data/bronze/eleicoes_precandidatos")
GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")


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


def _panorama(df) -> list[dict]:
    """Pré-candidatos que atingiram o piso de relevância em alguma medição."""
    rel = df[df["pct"] >= PCT_MIN_RELEVANTE]
    # nome canônico → partido mais frequente
    out = []
    for nome, grp in rel.groupby("candidato"):
        partido = grp["partido"].mode().iloc[0] if len(grp) else ""
        out.append(
            {
                "nome": nome,
                "partido": partido,
                "n_pesquisas": int(len(grp)),
                "ultima": grp["dt_fim"].max().strftime("%Y-%m-%d"),
            }
        )
    out.sort(key=lambda d: d["n_pesquisas"], reverse=True)
    return out


def _primeiro_turno(df):
    """Snapshot recente do 1º turno: média na janela + delta vs. período anterior."""
    import pandas as pd

    t1 = df[df["cenario"] == CENARIO_1T]
    if t1.empty:
        return None
    ref = t1["dt_fim"].max()
    janela = ref - timedelta(days=JANELA_RECENTE_DIAS)
    prev_ini = janela - timedelta(days=JANELA_RECENTE_DIAS)

    recente = t1[t1["dt_fim"] > janela]
    anterior = t1[(t1["dt_fim"] > prev_ini) & (t1["dt_fim"] <= janela)]

    med_prev = anterior.groupby("candidato")["pct"].mean().to_dict()
    candidatos = []
    for nome, grp in recente.groupby("candidato"):
        if len(grp) < MIN_PESQUISAS_RECENTES:
            continue
        media = round(float(grp["pct"].mean()), 1)
        if media < PCT_MIN_RELEVANTE:
            continue
        partido = grp["partido"].mode().iloc[0]
        ult = grp.sort_values("dt_fim").iloc[-1]
        delta = None
        if nome in med_prev:
            delta = round(media - float(med_prev[nome]), 1)
        candidatos.append(
            {
                "nome": nome,
                "partido": partido,
                "media_recente": media,
                "pct_ultima": round(float(ult["pct"]), 1),
                "instituto_ultima": ult["instituto"],
                "data_ultima": ult["dt_fim"].strftime("%Y-%m-%d"),
                "n_pesquisas": int(len(grp)),
                "delta": delta,
            }
        )
    candidatos.sort(key=lambda d: d["media_recente"], reverse=True)
    for i, c in enumerate(candidatos):
        c["lider"] = i == 0
    return {
        "data_ref": ref.strftime("%Y-%m-%d"),
        "janela_dias": JANELA_RECENTE_DIAS,
        "n_pesquisas": int(len(recente)),
        "candidatos": candidatos,
    }


def _segundo_turno(df) -> list[dict]:
    """Confronto mais recente por par de candidatos (só medições do ano da eleição)."""
    t2 = df[
        (df["cenario"] == CENARIO_2T) & (df["ano"] == ANO_ELEICAO_PRESIDENCIAL)
    ].copy()
    if t2.empty:
        return []
    # agrupa pelas 2 linhas da MESMA medição de origem (tabela × linha)
    confrontos: dict[tuple, dict] = {}
    for _, grp in t2.groupby("medicao_id"):
        if len(grp) != 2:
            continue
        g = grp.sort_values("pct", ascending=False)
        a, b = g.iloc[0], g.iloc[1]
        par = tuple(sorted([a["candidato"], b["candidato"]]))
        data = a["dt_fim"]
        # mantém o confronto mais recente por par
        if par in confrontos and confrontos[par]["_dt"] >= data:
            continue
        confrontos[par] = {
            "_dt": data,
            "instituto": a["instituto"],
            "data": data.strftime("%Y-%m-%d"),
            "a": {"nome": a["candidato"], "partido": a["partido"], "pct": round(float(a["pct"]), 1)},
            "b": {"nome": b["candidato"], "partido": b["partido"], "pct": round(float(b["pct"]), 1)},
        }
    saida = sorted(confrontos.values(), key=lambda d: d["_dt"], reverse=True)
    for c in saida:
        c.pop("_dt", None)
    return saida


def _serie_temporal(df, nomes: list[str]) -> dict:
    """Média mensal de 1º turno por candidato do painel (alimenta a tendência)."""
    t1 = df[(df["cenario"] == CENARIO_1T) & (df["candidato"].isin(nomes))].copy()
    if t1.empty:
        return {"meses": [], "candidatos": {}}
    t1["mes"] = t1["dt_fim"].dt.strftime("%Y-%m")
    pivot = t1.groupby(["mes", "candidato"])["pct"].mean().round(1).unstack("candidato")
    pivot = pivot.sort_index()
    meses = list(pivot.index)
    candidatos = {
        nome: [None if v != v else float(v) for v in pivot[nome].tolist()]
        for nome in pivot.columns
    }
    return {"meses": meses, "candidatos": candidatos}


def _agg(df) -> dict:
    pt = _primeiro_turno(df)
    nomes_painel = [c["nome"] for c in pt["candidatos"]] if pt else []
    st = _segundo_turno(df)
    janela = {
        "primeira": df["dt_fim"].min().strftime("%Y-%m-%d"),
        "ultima": df["dt_fim"].max().strftime("%Y-%m-%d"),
    }
    institutos = sorted(df["instituto"].dropna().unique().tolist())
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "Wikipedia — agregação de pesquisas de institutos registrados no TSE",
        "fonte_url": WIKIPEDIA_PRESIDENCIAL_URL,
        "ano_eleicao": ANO_ELEICAO_PRESIDENCIAL,
        "janela": janela,
        "n_medicoes": int(len(df)),
        "n_institutos": int(df["instituto"].nunique()),
        "institutos": institutos,
        "panorama": _panorama(df),
        "primeiro_turno": pt,
        "segundo_turno": st,
        "serie_temporal": _serie_temporal(df, nomes_painel),
        "notas": {
            "disclaimer": (
                "Cada pesquisa mantém instituto, data e margem à vista. O painel "
                "mostra a MEDIÇÃO da intenção de voto — não uma previsão de "
                "resultado. O destaque do líder é apenas visual, sem cor partidária."
            ),
            "metodo": (
                "Agregação da Wikipedia (que compila pesquisas registradas no TSE). "
                "1º turno: média das pesquisas dos últimos "
                f"{JANELA_RECENTE_DIAS} dias; candidatos com menos de "
                f"{MIN_PESQUISAS_RECENTES} pesquisas na janela ou abaixo de "
                f"{PCT_MIN_RELEVANTE:.0f}% são omitidos. 2º turno: confronto mais "
                "recente por par."
            ),
            "atualizacao": "Diária — republicada conforme novas pesquisas entram no artigo.",
        },
    }


def main() -> int:
    import pandas as pd

    print("🗳  Observatório Eleições 2026 — gold (pré-candidatos + intenção)")
    src = _latest_bronze()
    df = pd.read_parquet(src)
    print(f"  • bronze: {src.name} ({len(df):,} linhas)")

    df = _limpar(df)
    payload = _agg(df)

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    df.drop(columns=[c for c in ("_ingest_ts",) if c in df.columns]).to_parquet(
        GOLD_DIR / "eleicoes_precandidatos.parquet", index=False
    )

    out_json = FRONTEND_DIR / "eleicoes_precandidatos.json"
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    pt = payload["primeiro_turno"]
    lider = pt["candidatos"][0] if pt and pt["candidatos"] else None
    print(f"  ✓ {out_json}")
    print(
        f"    {len(payload['panorama'])} pré-candidatos · "
        f"{len(pt['candidatos']) if pt else 0} no 1º turno · "
        f"{len(payload['segundo_turno'])} confrontos de 2º turno"
    )
    if lider:
        print(f"    líder (medição): {lider['nome']} {lider['media_recente']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
