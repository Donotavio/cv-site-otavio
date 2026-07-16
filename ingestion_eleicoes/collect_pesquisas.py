"""
Observatório Eleições 2026 — Coleta de pesquisas registradas (TSE)
==================================================================
Baixa o ZIP oficial do TSE (Pesquisas Eleitorais 2026), extrai o CSV nacional
e grava um snapshot bronze. Lê tudo do catálogo — nunca hardcodar aqui.

Uso:
    python ingestion_eleicoes/collect_pesquisas.py
Saída:
    data/bronze/eleicoes_pesquisas/pesquisas_AAAA_MM_DD.parquet
    (schema: colunas do catálogo COLUNAS + _ingest_ts)

Fail-soft: linha com data/valor inválido é limpa (não derruba o pipeline).
"""

from __future__ import annotations

import csv
import io
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from ingestion_eleicoes.catalog import (  # noqa: E402
    COLUNAS,
    CSV_DELIMITER,
    CSV_ENCODING,
    TSE_CSV_NACIONAL,
    TSE_PESQUISAS_ZIP_URL,
)

BRONZE_DIR = Path("data/bronze/eleicoes_pesquisas")
TIMEOUT = 60
MAX_RETRIES = 4


def _baixar_csv_nacional() -> str:
    """Baixa o zip do TSE (com retry/backoff) e devolve o CSV nacional (texto).

    O CDN do TSE (cdn.tse.jus.br) às vezes atrasa/recusa conexões de IPs de
    nuvem — timeout transitório no runner. Repete com backoff e respeita
    Retry-After em 429/503. Se esgotar as tentativas, propaga a última exceção
    (o main() trata como fail-soft).
    """
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                TSE_PESQUISAS_ZIP_URL,
                headers={"User-Agent": "observatorio-eleicoes-2026/1.0"},
                timeout=TIMEOUT,
            )
            if resp.status_code in (429, 503):
                wait = int(resp.headers.get("Retry-After", 0) or 0) or attempt * 5
                print(f"  · TSE {resp.status_code} — aguardando {wait}s ({attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                with zf.open(TSE_CSV_NACIONAL) as fh:
                    return fh.read().decode(CSV_ENCODING)
        except requests.RequestException as e:  # noqa: BLE001
            last_exc = e
            if attempt < MAX_RETRIES:
                wait = attempt * 5
                print(f"  · falha de rede ({attempt}/{MAX_RETRIES}): {e.__class__.__name__} — retry em {wait}s")
                time.sleep(wait)
    raise last_exc if last_exc else RuntimeError("download do TSE falhou após retries")


def _parse_rows(csv_text: str) -> list[dict]:
    """Converte o CSV bruto do TSE em linhas bronze (só colunas do catálogo)."""
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=CSV_DELIMITER)
    rows: list[dict] = []
    for raw in reader:
        row: dict = {}
        for tse_col, bronze_col in COLUNAS.items():
            row[bronze_col] = (raw.get(tse_col) or "").strip()
        rows.append(row)
    return rows


def _save_bronze(rows: list[dict]) -> Path:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    now = datetime.now(timezone.utc)
    df = pd.DataFrame(rows)
    df["_ingest_ts"] = now.isoformat()

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRONZE_DIR / f"pesquisas_{now.year}_{now.month:02d}_{now.day:02d}.parquet"
    pq.write_table(
        pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy"
    )
    return out_path


def main() -> int:
    print("🗳  Observatório Eleições 2026 — coleta de pesquisas registradas (TSE)")
    try:
        csv_text = _baixar_csv_nacional()
    except (requests.RequestException, RuntimeError) as e:  # noqa: BLE001
        print(f"  ✗ falha ao baixar o dataset do TSE (após {MAX_RETRIES} tentativas): {e}")
        return 1

    rows = _parse_rows(csv_text)
    if not rows:
        print("  ✗ CSV do TSE sem linhas — nada a gravar.")
        return 1

    out_path = _save_bronze(rows)
    print(f"  ✓ {out_path} ({len(rows):,} pesquisas registradas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
