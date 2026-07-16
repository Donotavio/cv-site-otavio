"""
Observatório Eleições 2026 — Gold (bronze → agregações → JSON de frontend)
==========================================================================
Lê o snapshot bronze mais recente das pesquisas registradas no TSE, limpa
(regras do catálogo) e agrega para o dashboard. Zero LLM em runtime.

Uso:
    python transform_eleicoes/gold_eleicoes.py
Saída:
    data/gold/eleicoes_pesquisas.parquet      (bronze limpo, 1 linha por pesquisa)
    assets/data/eleicoes_pesquisas.json        (agregações consumidas pela página Astro)

Ângulo (transparente): o dataset do TSE é de REGISTRO — traz metadados das
pesquisas (quem mede, onde, com que amostra, a que custo), não os percentuais
de intenção de voto. O observatório é sobre a *máquina de medição* da eleição.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    ANO_ELEICAO,
    DATASET_PAGE,
    FAIXAS_AMOSTRA,
    QT_MIN_VALIDO,
    nivel_disputa,
)

BRONZE_DIR = Path("data/bronze/eleicoes_pesquisas")
GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")


def _latest_bronze() -> Path:
    files = sorted(BRONZE_DIR.glob("pesquisas_*.parquet"))
    if not files:
        raise RuntimeError(
            "Sem bronze — rode ingestion_eleicoes/collect_pesquisas.py antes."
        )
    return files[-1]


def _limpar(df):
    import pandas as pd

    # números (decimal com vírgula no padrão TSE)
    df["qt_entrevistado"] = pd.to_numeric(
        df["qt_entrevistado"].str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )
    df["vr_pesquisa"] = pd.to_numeric(
        df["vr_pesquisa"].str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )
    # datas (formato 'AAAA-MM-DD HH:MM:SS')
    df["dt_divulgacao"] = pd.to_datetime(df["dt_divulgacao"], errors="coerce")
    # qualidade: amostra válida (> 0)
    df.loc[df["qt_entrevistado"] < QT_MIN_VALIDO, "qt_entrevistado"] = pd.NA
    df.loc[df["vr_pesquisa"] < 0, "vr_pesquisa"] = pd.NA
    # nível da disputa
    df["nivel"] = [nivel_disputa(uf, cargo) for uf, cargo in zip(df["uf"], df["cargo"])]
    return df


def _agg(df) -> dict:
    import pandas as pd

    total = int(len(df))
    validos = df.dropna(subset=["dt_divulgacao"])

    # timeline mensal (intensidade de pesquisas rumo à eleição)
    por_mes = (
        validos.assign(mes=validos["dt_divulgacao"].dt.strftime("%Y-%m"))
        .groupby("mes")
        .size()
        .reset_index(name="n")
        .sort_values("mes")
    )

    # top institutos (nº de pesquisas + investimento declarado)
    inst = (
        df.groupby("empresa")
        .agg(n=("empresa", "size"), investimento_rs=("vr_pesquisa", "sum"))
        .reset_index()
        .sort_values("n", ascending=False)
        .head(12)
    )

    # cobertura por UF
    por_uf = (
        df.groupby("uf").size().reset_index(name="n").sort_values("n", ascending=False)
    )

    # detalhe por UF (alimenta o combobox interativo) — exclui BR (nacional)
    uf_detalhe = {}
    for uf_code, grp in df[df["uf"] != "BR"].groupby("uf"):
        top = (
            grp.groupby("empresa").size().reset_index(name="n")
            .sort_values("n", ascending=False).head(5)
        )
        q_uf = grp["qt_entrevistado"].dropna()
        uf_detalhe[str(uf_code)] = {
            "n": int(len(grp)),
            "mediana_amostra": int(q_uf.median()) if len(q_uf) else None,
            "top_institutos": [
                {
                    "empresa": r["empresa"].title() if isinstance(r["empresa"], str) else r["empresa"],
                    "n": int(r["n"]),
                }
                for _, r in top.iterrows()
            ],
        }

    # própria vs contratada
    propria = int((df["propria"].str.upper() == "S").sum())
    contratada = int((df["propria"].str.upper() == "N").sum())

    # faixas de amostra
    amostragem = []
    q = df["qt_entrevistado"].dropna()
    for rotulo, lo, hi in FAIXAS_AMOSTRA:
        amostragem.append({"faixa": rotulo, "n": int(((q >= lo) & (q <= hi)).sum())})

    # nível da disputa
    por_nivel = df.groupby("nivel").size().to_dict()

    invest_total = float(df["vr_pesquisa"].fillna(0).sum())
    mediana_amostra = q.median()

    # ── Recordes (card estrela do bento + linha de mini-stats) ──
    inst_top = None
    if len(inst):
        r0 = inst.iloc[0]
        inst_top = {
            "empresa": r0["empresa"].title() if isinstance(r0["empresa"], str) else r0["empresa"],
            "n": int(r0["n"]),
            "investimento_rs": round(float(r0["investimento_rs"] or 0), 2),
        }
    mes_pico = None
    if len(por_mes):
        rm = por_mes.loc[por_mes["n"].idxmax()]
        mes_pico = {"mes": str(rm["mes"]), "n": int(rm["n"])}
    maior_amostra = int(q.max()) if len(q) else None
    pesquisa_mais_cara = (
        round(float(df["vr_pesquisa"].max()), 2) if df["vr_pesquisa"].notna().any() else None
    )

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "TSE — Portal de Dados Abertos (Pesquisas Eleitorais 2026)",
        "dataset_url": DATASET_PAGE,
        "ano_eleicao": ANO_ELEICAO,
        "janela": {
            "primeira_divulgacao": (
                validos["dt_divulgacao"].min().strftime("%Y-%m-%d") if len(validos) else None
            ),
            "ultima_divulgacao": (
                validos["dt_divulgacao"].max().strftime("%Y-%m-%d") if len(validos) else None
            ),
        },
        "kpis": {
            "total_pesquisas": total,
            "n_institutos": int(df["empresa"].nunique()),
            "investimento_total_rs": round(invest_total, 2),
            "mediana_entrevistados": int(mediana_amostra) if pd.notna(mediana_amostra) else None,
            "pct_presidencial": round(100 * por_nivel.get("presidencial", 0) / total, 1) if total else 0,
        },
        "por_mes": por_mes.to_dict(orient="records"),
        "por_nivel": {
            "presidencial": int(por_nivel.get("presidencial", 0)),
            "estadual": int(por_nivel.get("estadual", 0)),
        },
        "top_institutos": [
            {
                "empresa": r["empresa"].title() if isinstance(r["empresa"], str) else r["empresa"],
                "n": int(r["n"]),
                "investimento_rs": round(float(r["investimento_rs"] or 0), 2),
            }
            for _, r in inst.iterrows()
        ],
        "por_uf": [{"uf": r["uf"], "n": int(r["n"])} for _, r in por_uf.iterrows()],
        "por_uf_detalhe": uf_detalhe,
        "propria_vs_contratada": {"propria": propria, "contratada": contratada},
        "amostragem": amostragem,
        "records": {
            "maior_amostra": maior_amostra,
            "pesquisa_mais_cara_rs": pesquisa_mais_cara,
            "instituto_mais_ativo": inst_top,
            "mes_pico": mes_pico,
        },
        "notas": {
            "escopo": (
                "Dataset de REGISTRO do TSE: metadados das pesquisas (instituto, "
                "cargo, UF, amostra, custo, datas) — não os percentuais de intenção "
                "de voto, que constam nos questionários (PDF)."
            ),
            "qualidade": (
                f"Amostras com QT_ENTREVISTADO < {QT_MIN_VALIDO} e custos negativos "
                "são descartados (erros de preenchimento no registro)."
            ),
            "atualizacao": "Diária — o TSE republica o dataset conforme novas pesquisas são registradas.",
        },
    }


def main() -> int:
    import pandas as pd

    print("🗳  Observatório Eleições 2026 — gold (agregações de pesquisas)")
    src = _latest_bronze()
    df = pd.read_parquet(src)
    print(f"  • bronze: {src.name} ({len(df):,} registros)")

    df = _limpar(df)
    payload = _agg(df)

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    # gold parquet (bronze limpo, para reuso analítico)
    keep = [
        "dt_divulgacao", "uf", "nm_ue", "empresa", "cargo", "nivel",
        "qt_entrevistado", "vr_pesquisa", "propria", "protocolo",
    ]
    df[keep].to_parquet(GOLD_DIR / "eleicoes_pesquisas.parquet", index=False)

    out_json = FRONTEND_DIR / "eleicoes_pesquisas.json"
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"  ✓ {out_json}")
    print(
        f"    {payload['kpis']['total_pesquisas']:,} pesquisas · "
        f"{payload['kpis']['n_institutos']} institutos · "
        f"R$ {payload['kpis']['investimento_total_rs']:,.0f} declarados"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
