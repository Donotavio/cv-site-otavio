"""
Observatório Eleições 2026 — Gold ESTADUAL (governador + senador → JSON)
========================================================================
Lê o bronze estadual mais recente (pesquisas por UF, formato long) e agrega,
por UF × cargo: snapshot recente de governador (1º turno), confrontos de 2º
turno e senador. Mesma lógica de janela/limiares da Fase 1. Zero LLM em runtime.

Uso:
    python transform_eleicoes/gold_estaduais.py
Saída:
    data/gold/eleicoes_estaduais.parquet
    assets/data/eleicoes_estaduais.json

Enquadramento apartidário idêntico à Fase 1: instituto/data/margem à vista,
líder é só destaque visual, medição — não previsão.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    ANO_ELEICAO_PRESIDENCIAL,
    CENARIO_GOV_1T,
    CENARIO_GOV_2T,
    CENARIO_SEN,
    JANELA_RECENTE_DIAS,
    MIN_PESQUISAS_RECENTES,
    PCT_MIN_RELEVANTE,
    UF_ARTIGO_SUFIXO,
    UF_SEM_ARTIGO,
    WIKIPEDIA_ESTADUAL_TITLE_FMT,
)

BRONZE_DIR = Path("data/bronze/eleicoes_estaduais")
GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")


def _latest_bronze() -> Path:
    files = sorted(BRONZE_DIR.glob("estaduais_*.parquet"))
    if not files:
        raise RuntimeError("Sem bronze — rode ingestion_eleicoes/collect_estaduais.py antes.")
    return files[-1]


def _limpar(df):
    import pandas as pd

    df["dt_fim"] = pd.to_datetime(df["dt_fim"], errors="coerce")
    df["pct"] = pd.to_numeric(df["pct"], errors="coerce")
    df = df.dropna(subset=["dt_fim", "pct", "candidato"])
    df = df[(df["pct"] >= 0) & (df["pct"] <= 100)]
    return df


def _snapshot(df) -> dict | None:
    """Média na janela recente + delta vs. período anterior (governador/senador).

    Só considera medições do ANO_ELEICAO_PRESIDENCIAL (2026) — sem esse filtro,
    uma UF cuja Wikipedia só publicou pesquisas de um ciclo anterior (ex.: 2024)
    aparecia com dado antigo disfarçado de atual (achado real: BA/senador só
    tinha pesquisas de 2024 e ainda assim preenchia o card).
    """
    df = df[df["ano"] == ANO_ELEICAO_PRESIDENCIAL]
    if df.empty:
        return None
    ref = df["dt_fim"].max()
    janela = ref - timedelta(days=JANELA_RECENTE_DIAS)
    prev_ini = janela - timedelta(days=JANELA_RECENTE_DIAS)
    recente = df[df["dt_fim"] > janela]
    anterior = df[(df["dt_fim"] > prev_ini) & (df["dt_fim"] <= janela)]
    if recente.empty:
        return None
    med_prev = anterior.groupby("candidato")["pct"].mean().to_dict()

    candidatos = []
    for nome, grp in recente.groupby("candidato"):
        if len(grp) < MIN_PESQUISAS_RECENTES:
            continue
        media = round(float(grp["pct"].mean()), 1)
        if media < PCT_MIN_RELEVANTE:
            continue
        ult = grp.sort_values("dt_fim").iloc[-1]
        delta = round(media - float(med_prev[nome]), 1) if nome in med_prev else None
        candidatos.append(
            {
                "nome": nome,
                "partido": grp["partido"].mode().iloc[0],
                "media_recente": media,
                "pct_ultima": round(float(ult["pct"]), 1),
                "instituto_ultima": ult["instituto"],
                "data_ultima": ult["dt_fim"].strftime("%Y-%m-%d"),
                "n_pesquisas": int(len(grp)),
                "delta": delta,
            }
        )
    if not candidatos:
        return None
    candidatos.sort(key=lambda d: d["media_recente"], reverse=True)
    for i, c in enumerate(candidatos):
        c["lider"] = i == 0
    return {
        "data_ref": ref.strftime("%Y-%m-%d"),
        "janela_dias": JANELA_RECENTE_DIAS,
        "n_pesquisas": int(len(recente)),
        "candidatos": candidatos,
    }


def _confrontos_2t(df) -> list[dict]:
    """Confronto mais recente por par (governador 2º turno, ano da eleição)."""
    d2 = df[df["ano"] == ANO_ELEICAO_PRESIDENCIAL]
    if d2.empty:
        return []
    confrontos: dict[tuple, dict] = {}
    for _, grp in d2.groupby("medicao_id"):
        if len(grp) != 2:
            continue
        g = grp.sort_values("pct", ascending=False)
        a, b = g.iloc[0], g.iloc[1]
        par = tuple(sorted([a["candidato"], b["candidato"]]))
        data = a["dt_fim"]
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


def _agg(df) -> dict:
    estados: dict[str, dict] = {}
    for uf, grp in df.groupby("uf"):
        gov1 = _snapshot(grp[grp["cargo"] == CENARIO_GOV_1T])
        gov2 = _confrontos_2t(grp[grp["cargo"] == CENARIO_GOV_2T])
        sen = _snapshot(grp[grp["cargo"] == CENARIO_SEN])
        if not (gov1 or gov2 or sen):
            continue
        estados[str(uf)] = {
            "governador_1t": gov1,
            "governador_2t": gov2,
            "senador": sen,
        }
    ufs = sorted(estados.keys())
    # UFs com artigo na Wikipedia mas que não renderam nenhum card (ex.: só
    # pesquisa velha, fora da janela de 90 dias, ou nenhuma com o mínimo de
    # medições recentes) — diferente de "sem artigo", que nunca foi coletado.
    ufs_com_artigo = set(UF_ARTIGO_SUFIXO.keys())
    ufs_sem_dado_recente = sorted(ufs_com_artigo - set(ufs))
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "Wikipedia — agregação de pesquisas estaduais registradas no TSE",
        "fonte_url_fmt": (
            "https://pt.wikipedia.org/wiki/"
            + WIKIPEDIA_ESTADUAL_TITLE_FMT.replace(" ", "_")
        ),
        "ano_eleicao": ANO_ELEICAO_PRESIDENCIAL,
        "ufs_disponiveis": ufs,
        "estados": estados,
        "notas": {
            "disclaimer": (
                "Medição da intenção de voto por estado (governador e senador) — "
                "não é previsão de resultado. Instituto, data e margem sempre à "
                "vista; destaque do líder apenas visual, sem cor partidária."
            ),
            "senado": (
                "Em 2026 cada estado renova 2 das 3 cadeiras do Senado; o painel "
                "mostra os principais nomes medidos, não um vencedor único."
            ),
            "cobertura": _texto_cobertura(len(ufs), UF_SEM_ARTIGO, ufs_sem_dado_recente),
            "ufs_sem_artigo": UF_SEM_ARTIGO,
            "ufs_sem_dado_recente": ufs_sem_dado_recente,
        },
    }


def _texto_cobertura(n_ufs: int, sem_artigo: list[str], sem_dado_recente: list[str]) -> str:
    partes = [f"{n_ufs} UFs com pesquisas recentes publicadas."]
    if sem_artigo:
        partes.append(f"Sem artigo na fonte: {', '.join(sem_artigo)}.")
    if sem_dado_recente:
        partes.append(
            f"Com artigo mas sem pesquisa dentro da janela de {JANELA_RECENTE_DIAS} dias: "
            f"{', '.join(sem_dado_recente)}."
        )
    return " ".join(partes)


def main() -> int:
    import pandas as pd

    print("🗳  Observatório Eleições 2026 — gold ESTADUAL (governador + senador)")
    src = _latest_bronze()
    df = pd.read_parquet(src)
    print(f"  • bronze: {src.name} ({len(df):,} linhas)")

    df = _limpar(df)
    payload = _agg(df)

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
    df.drop(columns=[c for c in ("_ingest_ts",) if c in df.columns]).to_parquet(
        GOLD_DIR / "eleicoes_estaduais.parquet", index=False
    )
    out_json = FRONTEND_DIR / "eleicoes_estaduais.json"
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"  ✓ {out_json}")
    print(f"    {len(payload['ufs_disponiveis'])} UFs: {' '.join(payload['ufs_disponiveis'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
