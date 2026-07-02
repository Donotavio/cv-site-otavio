"""
Brasil Cockpit — Coleta IBGE SIDRA (PIB, desocupação, PIM, PMC, PMS)
=====================================================================
Lê tabelas de ingestion_macro/catalog.SIDRA_SERIES. Sempre nacional:
territorial_level='1' + ibge_territorial_code='1' (nunca 'all').

sidrapy.get_table() tem o quirk da 1ª linha virar cabeçalho real — corrigimos
com df.columns = df.iloc[0]; df = df.iloc[1:]. O período vem por nome humano
("janeiro 2023", "2º trimestre 2023") — parser via regex (mais robusto que
códigos, que variam por tabela).

Uso:
    python ingestion_macro/collect_ibge.py
Saída:
    data/bronze/macro_ibge/ibge.parquet  (kpi_id, data_referencia, valor, _ingest_ts)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timezone

from ingestion_macro.catalog import SIDRA_SERIES

BRONZE_DIR = Path("data/bronze/macro_ibge")

_MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def _parse_period(name: str):
    """'janeiro 2023' → date(2023,1,1); '2º trimestre 2023' → date(2023,4,1)."""
    if not name:
        return None
    s = name.lower().strip()
    m = re.search(r"(\d{4})", s)
    if not m:
        return None
    year = int(m.group(1))
    for mes, n in _MESES.items():
        if mes in s:
            from datetime import date
            return date(year, n, 1)
    q = re.search(r"(\d)\s*[ºo°]?\s*(trim|trimestre|móvel)", s)
    if q:
        from datetime import date
        month = int(q.group(1)) * 3 - 2  # Q1→1, Q2→4, Q3→7, Q4→10
        return date(year, month, 1)
    from datetime import date
    return date(year, 1, 1)


def _fetch_one(kpi_id: str, cfg: dict):
    """Busca uma tabela SIDRA e devolve DataFrame (kpi_id, data_referencia, valor).

    sidrapy com header='y' devolve colunas em D-codes (NC, NN, V, D1C, D2C,
    D2N, ...) com a 1ª linha sendo o cabeçalho humano — descartamos essa
    linha. Valor em 'V'; período por nome humano em 'D2N' (parser via regex).
    """
    import pandas as pd
    import sidrapy

    df = sidrapy.get_table(
        table_code=cfg["table"],
        territorial_level="1",
        ibge_territorial_code="1",
        variable=cfg.get("variable"),
        classifications=cfg.get("classifications"),
        period=cfg.get("period", "last 24"),
        header="y",
        format="pandas",
    )
    if df is None or df.empty:
        return None

    # 1ª linha = cabeçalho humano (descartar); colunas já são D-codes.
    df = df.iloc[1:].reset_index(drop=True)

    val_col = "V" if "V" in df.columns else df.columns[-1]
    period_col = "D2N" if "D2N" in df.columns else None

    sub = pd.DataFrame({
        "kpi_id": kpi_id,
        "data_referencia": df[period_col].map(_parse_period) if period_col else None,
        "valor": pd.to_numeric(df[val_col], errors="coerce"),
    })
    sub = sub.dropna(subset=["data_referencia", "valor"])
    sub["data_referencia"] = pd.to_datetime(sub["data_referencia"])
    return sub


def main() -> int:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    print("🏛  Brasil Cockpit — coleta IBGE SIDRA")
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    frames: list[pd.DataFrame] = []

    for kpi_id, cfg in SIDRA_SERIES.items():
        try:
            sub = _fetch_one(kpi_id, cfg)
            if sub is None or sub.empty:
                print(f"  ✗ {kpi_id} (tabela {cfg['table']}): sem dados")
                continue
            print(f"  ✓ {kpi_id:<14} (tab {cfg['table']}) → {len(sub):>3} períodos")
            frames.append(sub)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {kpi_id} (tabela {cfg['table']}): {e}")

    if not frames:
        print("✗ IBGE sem dados — saindo (exit 0).")
        return 0

    out = pd.concat(frames, ignore_index=True)
    out["_ingest_ts"] = now_iso
    out_path = BRONZE_DIR / "ibge.parquet"
    pq.write_table(pa.Table.from_pandas(out, preserve_index=False), out_path, compression="snappy")
    print(f"\n  ✓ {out_path} ({len(out)} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
