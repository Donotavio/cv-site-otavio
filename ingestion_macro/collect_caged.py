"""
Brasil Cockpit — Coleta Novo CAGED (admitidos / desligados / saldo)
====================================================================
O Novo CAGED (séries 28763, 28764, 28765) só existe a partir de janeiro de
2020 — start fixo em catalog.CAGED_START. Nunca recuar antes disso.

Uso:
    python ingestion_macro/collect_caged.py
Saída:
    data/bronze/macro_caged/caged.parquet  (kpi_id, data_referencia, valor, _ingest_ts)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timezone

from ingestion_macro.catalog import CAGED_KEYS, CAGED_START, SGS_SERIES

BRONZE_DIR = Path("data/bronze/macro_caged")


def main() -> int:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    from bcb import sgs

    print("👷 Brasil Cockpit — coleta Novo CAGED (start fixo 2020-01)")
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    frames: list[pd.DataFrame] = []

    for kpi_id in CAGED_KEYS:
        code = SGS_SERIES[kpi_id]
        try:
            df = sgs.get({kpi_id: code}, start=CAGED_START)
            if df is None or df.empty:
                print(f"  ✗ {kpi_id} ({code}): sem dados")
                continue
            df = df.reset_index()
            date_col = "Date" if "Date" in df.columns else df.columns[0]
            df = df.rename(columns={date_col: "data_referencia", kpi_id: "valor"})
            df = df[["data_referencia", "valor"]].copy()
            df.insert(0, "kpi_id", kpi_id)
            df["data_referencia"] = pd.to_datetime(df["data_referencia"]).dt.tz_localize(None)
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
            df = df.dropna(subset=["valor"])
            print(f"  ✓ {kpi_id:<20} ({code}) → {len(df):>4} meses")
            frames.append(df)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {kpi_id} ({code}): {e}")

    if not frames:
        print("✗ CAGED sem dados — saindo (exit 0).")
        return 0

    out = pd.concat(frames, ignore_index=True)
    out["_ingest_ts"] = now_iso
    out_path = BRONZE_DIR / "caged.parquet"
    pq.write_table(pa.Table.from_pandas(out, preserve_index=False), out_path, compression="snappy")
    print(f"\n  ✓ {out_path} ({len(out)} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
