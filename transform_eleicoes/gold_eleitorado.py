"""
Observatório Eleições 2026 — Gold do Perfil do Eleitorado (bronze → JSON)
========================================================================
Lê o bronze agregado (collect_eleitorado.py) e monta os recortes demográficos
do eleitorado brasileiro apto a votar em 2026: total, sexo, faixa etária,
escolaridade, cor/raça, biometria, obrigatoriedade e distribuição por UF.

É a contraparte apartidária das pesquisas — quem é o eleitorado que os
institutos tentam medir. Alimenta a seção "O eleitorado" e o "Índice de
intensidade por UF" (pesquisas ÷ eleitores) da página Astro.

Uso:
    python transform_eleicoes/gold_eleitorado.py
Saída:
    assets/data/eleicoes_eleitorado.json
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    DATASET_PAGE_ELEITORADO,
    UF_EXTERIOR,
    UF_TRANSITO,
)

BRONZE_DIR = Path("data/bronze/eleitorado")
FRONTEND_DIR = Path("assets/data")

# Ordem canônica de escolaridade (do menor ao maior grau).
ESCOLARIDADE_ORDEM = [
    "ANALFABETO", "LÊ E ESCREVE", "ENSINO FUNDAMENTAL INCOMPLETO",
    "ENSINO FUNDAMENTAL COMPLETO", "ENSINO MÉDIO INCOMPLETO", "ENSINO MÉDIO COMPLETO",
    "SUPERIOR INCOMPLETO", "SUPERIOR COMPLETO", "NÃO INFORMADO",
]

# Buckets de faixa etária (agrupam as ~22 faixas granulares do TSE).
FAIXA_BUCKETS = [
    ("16–17", 16, 17), ("18–24", 18, 24), ("25–34", 25, 34), ("35–44", 35, 44),
    ("45–59", 45, 59), ("60–69", 60, 69), ("70+", 70, 999),
]


def _latest_bronze() -> Path:
    files = sorted(BRONZE_DIR.glob("eleitorado_*.parquet"))
    if not files:
        raise RuntimeError(
            "Sem bronze de eleitorado — rode ingestion_eleicoes/collect_eleitorado.py."
        )
    return files[-1]


def _titlecase(s: str) -> str:
    return s.title() if isinstance(s, str) else s


def _bucket_faixa(ds: str):
    """Extrai a idade inicial de 'DS_FAIXA_ETARIA' e mapeia para um bucket."""
    m = re.search(r"\d+", ds or "")
    if not m:
        return None
    age = int(m.group())
    for label, lo, hi in FAIXA_BUCKETS:
        if lo <= age <= hi:
            return label
    return None


def _dist(df, col, measure="qt_eleitores", total=None, titlecase=True):
    import pandas as pd  # noqa: F401

    g = df.groupby(col, as_index=False)[measure].sum().sort_values(measure, ascending=False)
    tot = total if total is not None else int(g[measure].sum())
    return [
        {
            "label": _titlecase(r[col]) if titlecase else r[col],
            "n": int(r[measure]),
            "pct": round(100 * int(r[measure]) / tot, 1) if tot else 0,
        }
        for _, r in g.iterrows()
    ]


def build(df) -> dict:
    total = int(df["qt_eleitores"].sum())

    # Exterior (ZZ) e trânsito (VT) fora do ranking de estados.
    domestic = df[~df["uf"].isin([UF_EXTERIOR, UF_TRANSITO])]
    exterior_n = int(df.loc[df["uf"] == UF_EXTERIOR, "qt_eleitores"].sum())

    # ── Distribuições ──
    genero = _dist(df, "genero", total=total)
    escol = _dist(df, "grau_instrucao", total=total)
    escol.sort(key=lambda d: ESCOLARIDADE_ORDEM.index(d["label"].upper())
               if d["label"].upper() in ESCOLARIDADE_ORDEM else 99)
    cor = _dist(df, "cor_raca", total=total)
    obrig = _dist(df, "obrigatoriedade", total=total)

    # Faixa etária (bucketizada)
    fa = df.copy()
    fa["bucket"] = fa["faixa_etaria"].map(_bucket_faixa)
    fa = fa.dropna(subset=["bucket"])
    faixa = []
    order = [b[0] for b in FAIXA_BUCKETS]
    fg = fa.groupby("bucket", as_index=False)["qt_eleitores"].sum()
    for label in order:
        n = int(fg.loc[fg["bucket"] == label, "qt_eleitores"].sum())
        faixa.append({"label": label, "n": n, "pct": round(100 * n / total, 1) if total else 0})

    # ── Por UF (27 estados) ──
    uf_g = (
        domestic.groupby("uf", as_index=False)["qt_eleitores"].sum()
        .sort_values("qt_eleitores", ascending=False)
    )
    total_dom = int(uf_g["qt_eleitores"].sum())
    por_uf = [
        {"uf": r["uf"], "eleitores": int(r["qt_eleitores"]),
         "pct": round(100 * int(r["qt_eleitores"]) / total_dom, 1) if total_dom else 0}
        for _, r in uf_g.iterrows()
    ]

    # ── Biometria ──
    bio_n = int(df["qt_biometria"].sum())

    # ── Destaques (números-âncora) ──
    def _get(dist, label_upper):
        for d in dist:
            if d["label"].upper() == label_upper:
                return d
        return {"n": 0, "pct": 0}

    fem = next((d for d in genero if d["label"].upper().startswith("FEMIN")), {"pct": 0, "n": 0})
    jovens = next((d for d in faixa if d["label"] == "16–17"), {"n": 0})
    idosos = next((d for d in faixa if d["label"] == "70+"), {"n": 0})
    analf = _get(escol, "ANALFABETO")
    facultativo = next((d for d in obrig if d["label"].upper().startswith("FACULT")), {"pct": 0, "n": 0})

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "TSE — Estatísticas de Eleitorado (perfil do eleitorado, snapshot ATUAL)",
        "dataset_url": DATASET_PAGE_ELEITORADO,
        "total_eleitores": total,
        "biometria": {"n": bio_n, "pct": round(100 * bio_n / total, 1) if total else 0},
        "genero": genero,
        "faixa_etaria": faixa,
        "escolaridade": escol,
        "cor_raca": cor,
        "obrigatoriedade": obrig,
        "por_uf": por_uf,
        "exterior": {"eleitores": exterior_n},
        "destaques": {
            "feminino_pct": fem["pct"],
            "feminino_n": fem["n"],
            "jovens_16_17": jovens["n"],
            "idosos_70mais": idosos["n"],
            "analfabetos": {"n": analf["n"], "pct": analf["pct"]},
            "facultativo_pct": facultativo["pct"],
            "maior_uf": por_uf[0] if por_uf else None,
            "menor_uf": por_uf[-1] if por_uf else None,
        },
    }


def main() -> int:
    import pandas as pd

    print("🗳  Eleições 2026 — gold do perfil do eleitorado")
    src = _latest_bronze()
    df = pd.read_parquet(src)
    print(f"  • bronze: {src.name} ({len(df):,} grupos)")

    payload = build(df)

    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
    out = FRONTEND_DIR / "eleicoes_eleitorado.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {out}")
    print(
        f"    {payload['total_eleitores']:,} eleitores · "
        f"{payload['destaques']['feminino_pct']}% mulheres · "
        f"biometria {payload['biometria']['pct']}%"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
