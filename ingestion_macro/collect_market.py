"""
Brasil Cockpit — Coleta mercado (Ibovespa via yfinance)
========================================================
Ticker ^BVSP (Ibovespa). Recua 2 anos de fechamento diário.

Uso:
    python ingestion_macro/collect_market.py
Saída:
    data/bronze/macro_market/ibovespa.parquet  (kpi_id, data_referencia, valor, _ingest_ts)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, datetime, timedelta, timezone

from ingestion_macro.catalog import MARKET_SERIES

BRONZE_DIR = Path("data/bronze/macro_market")
MARKET_LOOKBACK_DAYS = 730


def main() -> int:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    import yfinance as yf

    print("📊 Brasil Cockpit — coleta mercado (yfinance)")
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    start = date.today() - timedelta(days=MARKET_LOOKBACK_DAYS)
    frames: list[pd.DataFrame] = []

    for kpi_id, ticker in MARKET_SERIES.items():
        try:
            df = yf.download(ticker, start=start.isoformat(), progress=False, auto_adjust=True)
            if df is None or df.empty:
                print(f"  ✗ {kpi_id} ({ticker}): sem dados")
                continue
            # yf devolve MultiIndex nas colunas em versões recentes
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close_col = "Close" if "Close" in df.columns else df.columns[0]
            df = df.reset_index().rename(columns={"Date": "data_referencia", close_col: "valor"})
            sub = pd.DataFrame({
                "kpi_id": kpi_id,
                "data_referencia": pd.to_datetime(df["data_referencia"]).dt.tz_localize(None),
                "valor": pd.to_numeric(df["valor"], errors="coerce"),
            }).dropna(subset=["valor"])
            # 1 fechamento por dia
            sub = sub.sort_values("data_referencia").drop_duplicates("data_referencia", keep="last")
            print(f"  ✓ {kpi_id:<10} ({ticker}) → {len(sub):>5} pregões")
            frames.append(sub)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {kpi_id} ({ticker}): {e}")

    if not frames:
        print("✗ Mercado sem dados — saindo (exit 0).")
        return 0

    out = pd.concat(frames, ignore_index=True)
    out["_ingest_ts"] = now_iso
    out_path = BRONZE_DIR / "ibovespa.parquet"
    pq.write_table(pa.Table.from_pandas(out, preserve_index=False), out_path, compression="snappy")
    print(f"\n  ✓ {out_path} ({len(out)} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
