"""
Brasil Cockpit — Coleta BACEN SGS (preços, juros, externo, fiscal)
====================================================================
Cobre todas as séries SGS EXCETO CAGED (que tem start fixo 2020-01 e roda em
collect_caged.py). Lê códigos de ingestion_macro/catalog.py — nunca hardcodar.

SGS impõe janela de ~10 anos desde mar/2025 — start = today - 3650 dias.

Uso:
    python ingestion_macro/collect_sgs.py
Saída:
    data/bronze/macro_sgs/sgs.parquet  (schema: kpi_id, data_referencia, valor, _ingest_ts)

Fail-soft: uma série com erro é pulada (logado); o pipeline segue.
"""

from __future__ import annotations

import sys
from pathlib import Path

# repo root no sys.path para importar o catálogo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, datetime, timedelta, timezone

from ingestion_macro.catalog import SGS_LOOKBACK_DAYS, SGS_SERIES

BRONZE_DIR = Path("data/bronze/macro_sgs")

# CAGED é coletado em collect_caged.py (start fixo 2020-01)
from ingestion_macro.catalog import CAGED_KEYS  # noqa: E402


def main() -> int:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    from bcb import sgs

    print("📈 Brasil Cockpit — coleta BACEN SGS")
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    start = date.today() - timedelta(days=SGS_LOOKBACK_DAYS)

    series = {k: v for k, v in SGS_SERIES.items() if k not in CAGED_KEYS}
    frames: list[pd.DataFrame] = []

    for kpi_id, code in series.items():
        try:
            df = sgs.get({kpi_id: code}, start=start)
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
            print(f"  ✓ {kpi_id:<22} ({code:>6}) → {len(df):>5} pontos")
            frames.append(df)
        except Exception as e:  # noqa: BLE001 — fail-soft por série
            print(f"  ✗ {kpi_id} ({code}): {e}")

    if not frames:
        print("✗ Nenhuma série SGS coletada.")
        return 0  # exit(0) — não quebra o pipeline

    out = pd.concat(frames, ignore_index=True)
    out["_ingest_ts"] = now_iso
    out_path = BRONZE_DIR / "sgs.parquet"
    pq.write_table(pa.Table.from_pandas(out, preserve_index=False), out_path, compression="snappy")
    print(f"\n  ✓ {out_path} ({len(out)} linhas, {out['kpi_id'].nunique()} KPIs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
