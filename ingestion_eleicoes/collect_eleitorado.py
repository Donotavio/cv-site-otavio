"""
Observatório Eleições 2026 — Ingestão do Perfil do Eleitorado (TSE)
==================================================================
Baixa o snapshot ATUAL de perfil do eleitorado do TSE e agrega em stream para
um bronze compacto. O CSV descompactado tem ~2,3 GB (1 linha por seção ×
combinação de atributos), então NUNCA gravamos o CSV cru: lemos direto de
dentro do ZIP em chunks, somando por combinação de atributos.

Uso:
    python ingestion_eleicoes/collect_eleitorado.py
Saída:
    data/bronze/eleitorado/eleitorado_AAAA_MM_DD.parquet
      (agregado por uf × genero × faixa × instrução × cor/raça × obrigatoriedade,
       com somas de QT_ELEITORES / BIOMETRIA / DEFICIENCIA)

Fail-soft: erro de rede/parse não derruba o pipeline (sai com código 0 e sem
snapshot novo) — o gold usa o último bronze disponível.
"""

from __future__ import annotations

import io
import sys
import time
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    COLUNAS_ELEITORADO,
    CSV_DELIMITER,
    CSV_ENCODING,
    ELEITORADO_GROUP_KEYS,
    ELEITORADO_MEASURES,
    TSE_ELEITORADO_CSV,
    TSE_ELEITORADO_ZIP_URL,
)

BRONZE_DIR = Path("data/bronze/eleitorado")
CHUNK = 500_000  # linhas por chunk (leitura em stream)
MAX_RETRIES = 4


def _download_zip() -> bytes:
    import requests

    print(f"  • baixando {TSE_ELEITORADO_ZIP_URL} …")
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(TSE_ELEITORADO_ZIP_URL, timeout=180)
            if resp.status_code in (429, 503):
                wait = int(resp.headers.get("Retry-After", 0) or 0) or attempt * 10
                print(f"    TSE {resp.status_code} — aguardando {wait}s ({attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            print(f"    {len(resp.content) / 1e6:.1f} MB (zip)")
            return resp.content
        except requests.RequestException as e:  # noqa: BLE001
            last_exc = e
            if attempt < MAX_RETRIES:
                wait = attempt * 10
                print(f"    falha de rede ({attempt}/{MAX_RETRIES}): {e.__class__.__name__} — retry em {wait}s")
                time.sleep(wait)
    raise last_exc if last_exc else RuntimeError("download do eleitorado falhou após retries")


def _aggregate(zip_bytes: bytes):
    import pandas as pd

    inv = {tse: canon for tse, canon in COLUNAS_ELEITORADO.items()}
    usecols = list(COLUNAS_ELEITORADO.keys())

    acc = None
    n_rows = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        with zf.open(TSE_ELEITORADO_CSV) as fh:
            reader = pd.read_csv(
                io.TextIOWrapper(fh, encoding=CSV_ENCODING),
                sep=CSV_DELIMITER,
                usecols=usecols,
                dtype=str,
                chunksize=CHUNK,
            )
            for i, chunk in enumerate(reader):
                chunk = chunk.rename(columns=inv)
                for m in ELEITORADO_MEASURES:
                    chunk[m] = pd.to_numeric(chunk[m], errors="coerce").fillna(0).astype("int64")
                for k in ELEITORADO_GROUP_KEYS:
                    chunk[k] = chunk[k].fillna("—").str.strip()
                g = chunk.groupby(ELEITORADO_GROUP_KEYS, as_index=False)[ELEITORADO_MEASURES].sum()
                acc = g if acc is None else (
                    pd.concat([acc, g], ignore_index=True)
                    .groupby(ELEITORADO_GROUP_KEYS, as_index=False)[ELEITORADO_MEASURES].sum()
                )
                n_rows += len(chunk)
                if (i + 1) % 5 == 0:
                    print(f"    … {n_rows:,} linhas lidas ({len(acc):,} grupos)")
    print(f"  • total: {n_rows:,} linhas → {len(acc):,} grupos agregados")
    return acc


def main() -> int:
    print("🗳  Eleições 2026 — ingestão do perfil do eleitorado (TSE)")
    try:
        zip_bytes = _download_zip()
        agg = _aggregate(zip_bytes)
    except Exception as exc:  # fail-soft
        print(f"  ⚠  ingestão falhou ({exc}); mantém bronze anterior.")
        return 0

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out = BRONZE_DIR / f"eleitorado_{date.today():%Y_%m_%d}.parquet"
    agg.to_parquet(out, index=False)
    total = int(agg["qt_eleitores"].sum())
    print(f"  ✓ {out} · {total:,} eleitores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
