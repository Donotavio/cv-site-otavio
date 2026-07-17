"""
Data Stack Radar BR — Sinal PyPI (downloads recentes por pacote)
====================================================================
Fonte real: PyPI Stats API (https://pypistats.org), 100% público, sem
autenticação. Retorna downloads recentes (dia/semana/mês) por pacote —
usamos `last_month` como proxy de adoção corrente.

Uso:
    python ingestion_radar/collect_pypi.py

Saída:
    data/bronze/radar_pypi/pypi_{YYYY}_{MM}.parquet
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from catalog import PYPI_PACKAGES as PACKAGES

API_BASE = "https://pypistats.org/api/packages/{package}/recent"
BRONZE_DIR = Path("data/bronze/radar_pypi")
TIMEOUT = 30


def collect_all() -> list[dict]:
    rows: list[dict] = []
    for package, canonical_name in PACKAGES.items():
        url = API_BASE.format(package=package)
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "data-stack-radar-br/1.0"},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            rows.append({
                "package": package,
                "tool": canonical_name,
                "last_day": data.get("last_day"),
                "last_week": data.get("last_week"),
                "last_month": data.get("last_month"),
            })
            print(f"  ✓ {canonical_name:<18} ({package:<20}) → "
                  f"{data.get('last_month', 0):,} downloads/mês")
        except requests.RequestException as e:
            print(f"  ✗ {canonical_name} ({package}): falha ({e})")
            rows.append({
                "package": package,
                "tool": canonical_name,
                "last_day": None,
                "last_week": None,
                "last_month": None,
            })
        time.sleep(1.2)  # gentil com a API pública

    return rows


def _save_bronze(rows: list[dict]) -> Path:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    now = datetime.now(timezone.utc)
    df = pd.DataFrame(rows)
    df["_ingest_ts"] = now.isoformat()

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRONZE_DIR / f"pypi_{now.year}_{now.month:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    return out_path


def main() -> int:
    print("📦 Data Stack Radar BR — coleta de sinais PyPI")
    print()

    rows = collect_all()
    if not rows:
        print("✗ Nenhum dado coletado.")
        return 1

    out_path = _save_bronze(rows)
    print()
    print(f"  ✓ {out_path} ({len(rows)} pacotes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
