"""
Brasil Cockpit — Coleta BACEN PTAX (câmbio diário USD e EUR)
==============================================================
Usa bcb.currency.get (wrapper do OData PTAX) para USD e EUR — cotação de
fechamento diária. KPIs: cambio_usd, cambio_eur (catalog.PTAX_SYMBOLS).

Uso:
    python ingestion_macro/collect_ptax.py
Saída:
    data/bronze/macro_ptax/ptax.parquet  (kpi_id, data_referencia, valor, _ingest_ts)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, datetime, timedelta, timezone

BRONZE_DIR = Path("data/bronze/macro_ptax")

# PTAX: recua 2 anos de câmbio diário (mais que suficiente p/ histórico/spark)
PTAX_LOOKBACK_DAYS = 730


def main() -> int:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    from bcb import currency

    print("💱 Brasil Cockpit — coleta PTAX (USD, EUR)")
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    start = date.today() - timedelta(days=PTAX_LOOKBACK_DAYS)
    end = date.today()

    frames: list[pd.DataFrame] = []

    for kpi_id, symbol in (("cambio_usd", "USD"), ("cambio_eur", "EUR")):
        try:
            df = currency.get([symbol], start=start, end=end)
            if df is None or df.empty:
                print(f"  ✗ {kpi_id} ({symbol}): sem dados")
                continue
            # currency.get retorna coluna nomeada pelo símbolo + índice de data
            df = df.reset_index()
            date_col = "Date" if "Date" in df.columns else df.columns[0]
            val_col = symbol if symbol in df.columns else df.columns[-1]
            df = df.rename(columns={date_col: "data_referencia", val_col: "valor"})
            df = df[["data_referencia", "valor"]].copy()
            df.insert(0, "kpi_id", kpi_id)
            df["data_referencia"] = pd.to_datetime(df["data_referencia"]).dt.tz_localize(None)
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
            df = df.dropna(subset=["valor"])
            # Manter apenas a última cotação por dia (PTAX pode ter >1)
            df = df.sort_values("data_referencia").drop_duplicates(
                "data_referencia", keep="last"
            )
            print(f"  ✓ {kpi_id:<12} ({symbol}) → {len(df):>5} dias")
            frames.append(df)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {kpi_id} ({symbol}): {e}")

    if not frames:
        print("✗ PTAX sem dados — saindo (exit 0).")
        return 0

    out = pd.concat(frames, ignore_index=True)
    out["_ingest_ts"] = now_iso
    out_path = BRONZE_DIR / "ptax.parquet"
    pq.write_table(pa.Table.from_pandas(out, preserve_index=False), out_path, compression="snappy")
    print(f"\n  ✓ {out_path} ({len(out)} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
