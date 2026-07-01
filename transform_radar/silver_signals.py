"""
Data Stack Radar BR — Silver: sinais GitHub + PyPI
=====================================================
Une todos os snapshots mensais em `data/bronze/radar_github/*.parquet` e
`data/bronze/radar_pypi/*.parquet` em duas tabelas silver tipadas
(histórico acumulado mês a mês — cada cron mensal adiciona um arquivo
bronze novo, e este script sempre reconstrói o silver a partir de todo
o histórico disponível).

Saída:
    data/silver/github_monthly.parquet
    data/silver/pypi_monthly.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

SILVER_DIR = Path("data/silver")


def main() -> int:
    con = duckdb.connect()
    SILVER_DIR.mkdir(parents=True, exist_ok=True)

    github_files = sorted(Path(".").glob("data/bronze/radar_github/*.parquet"))
    if not github_files:
        raise RuntimeError("Nenhum bronze de GitHub encontrado.")
    con.execute(f"""
        COPY (
            SELECT tool, topic, new_repos_ytd, since, _ingest_ts,
                   strftime(CAST(_ingest_ts AS TIMESTAMP), '%Y-%m') AS ingest_month
            FROM read_parquet('data/bronze/radar_github/*.parquet')
        )
        TO '{SILVER_DIR / "github_monthly.parquet"}' (FORMAT PARQUET)
    """)
    print(f"  ✓ {SILVER_DIR / 'github_monthly.parquet'}")

    pypi_files = sorted(Path(".").glob("data/bronze/radar_pypi/*.parquet"))
    if not pypi_files:
        raise RuntimeError("Nenhum bronze de PyPI encontrado.")
    con.execute(f"""
        COPY (
            SELECT package, tool, last_day, last_week, last_month, _ingest_ts,
                   strftime(CAST(_ingest_ts AS TIMESTAMP), '%Y-%m') AS ingest_month
            FROM read_parquet('data/bronze/radar_pypi/*.parquet')
        )
        TO '{SILVER_DIR / "pypi_monthly.parquet"}' (FORMAT PARQUET)
    """)
    print(f"  ✓ {SILVER_DIR / 'pypi_monthly.parquet'}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
