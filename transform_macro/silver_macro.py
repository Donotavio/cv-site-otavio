"""
Brasil Cockpit — Silver: normalização Bronze → Silver
=======================================================
Lê todos os Parquets de data/bronze/macro_*/ e consolida num único Silver
unificado (kpi_id, data_referencia, valor), ordenado. Full rebuild — sem
argumentos.

A derivação (balança comercial, saldo CAGED 12m, status/delta/trend, conversões
de unidade) fica toda no gold (gold_cockpit.py) — fonte única de lógica.

Saída:
    data/silver/macro.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb

SILVER_DIR = Path("data/silver")
BRONZE_GLOBS = [
    "data/bronze/macro_sgs/sgs.parquet",
    "data/bronze/macro_caged/caged.parquet",
    "data/bronze/macro_ptax/ptax.parquet",
    "data/bronze/macro_ibge/ibge.parquet",
    "data/bronze/macro_market/ibovespa.parquet",
]


def main() -> int:
    SILVER_DIR.mkdir(parents=True, exist_ok=True)

    existing = [g for g in BRONZE_GLOBS if Path(g).exists()]
    if not existing:
        raise RuntimeError("Nenhum bronze macro encontrado — rode os collect_*.py primeiro.")

    unions = " UNION ALL ".join(
        f"SELECT kpi_id, CAST(data_referencia AS DATE) AS data_referencia, "
        f"CAST(valor AS DOUBLE) AS valor FROM read_parquet('{g}')"
        for g in existing
    )

    con = duckdb.connect()
    out_path = SILVER_DIR / "macro.parquet"
    con.execute(f"""
        COPY (
            SELECT kpi_id, data_referencia, valor
            FROM ({unions})
            WHERE valor IS NOT NULL
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY kpi_id, data_referencia ORDER BY valor
            ) = 1
            ORDER BY kpi_id, data_referencia
        )
        TO '{out_path}' (FORMAT PARQUET)
    """)

    n = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_path}')").fetchone()[0]
    kpis = con.execute(f"SELECT COUNT(DISTINCT kpi_id) FROM read_parquet('{out_path}')").fetchone()[0]
    con.close()

    print(f"✓ Silver — Brasil Cockpit")
    print(f"  {out_path} ({n} linhas, {kpis} KPIs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
