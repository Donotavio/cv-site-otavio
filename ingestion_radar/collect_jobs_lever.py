"""
Data Stack Radar BR — Coleta de vagas via Lever Postings API (sub-fonte)
============================================================================
A Lever expõe um board público oficial por empresa (feito para embutir
vagas em sites próprios) — sem auth, sem ambiguidade de compliance:

    GET https://api.lever.co/v0/postings/{company}?mode=json

Retorna um array JSON de vagas. Campos usados: `text` (título),
`categories.commitment` (**tipo de contrato** — ex.: "CLT", "PJ"),
`categories.location`, `descriptionPlain`, `hostedUrl`, `workplaceType`.

Curadoria de empresas no catálogo (`ATS_COMPANIES["lever"]`) — só entram
slugs validados board-a-board. Adicionar uma empresa é 1 linha lá.

Dupla filtragem client-side (a Lever não filtra por termo/país):
    1. título casa com `DATA_TITLE_PATTERN` (é vaga de dados?)
    2. localização casa com BR (`is_br_location`)

Uso:
    python ingestion_radar/collect_jobs_lever.py

Saída:
    data/bronze/radar_jobs_lever/lever_{YYYY}_W{WW}.parquet
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from catalog import (
    ATS_COMPANIES,
    is_br_location,
    is_data_title,
    normalize_contract,
)

API_BASE = "https://api.lever.co/v0/postings/{company}"
BRONZE_DIR = Path("data/bronze/radar_jobs_lever")
COMPANIES: dict[str, str] = ATS_COMPANIES["lever"]
TIMEOUT = 30
TIMEOUT_SLEEP = 1.0


def collect_all() -> list[dict]:
    rows: list[dict] = []

    for slug, canonical_name in COMPANIES.items():
        url = API_BASE.format(company=slug)
        try:
            resp = requests.get(
                url,
                params={"mode": "json"},
                headers={"User-Agent": "data-stack-radar-br/1.0"},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            jobs = resp.json()
        except (requests.RequestException, ValueError) as e:
            # fail-soft: um board fora do ar não derruba a coleta.
            print(f"  ✗ {canonical_name} ({slug}): falha na busca ({e})")
            continue

        kept = 0
        for job in jobs:
            title = job.get("text", "")
            if not is_data_title(title):
                continue
            categories = job.get("categories") or {}
            location = categories.get("location", "") or ""
            if not is_br_location(location):
                continue
            workplace = (job.get("workplaceType") or "").lower()
            is_remote = "remot" in location.lower() or workplace == "remote"
            rows.append({
                "id": str(job.get("id", "")),
                "company": canonical_name,
                "company_slug": slug,
                "title": title,
                "description": job.get("descriptionPlain", "") or "",
                "location": location,
                "absolute_url": job.get("hostedUrl", "") or "",
                "updated_at": str(job.get("createdAt", "") or ""),
                "is_remote": bool(is_remote),
                "contract_type_raw": normalize_contract(categories.get("commitment")),
                "salary_min": None,
                "salary_max": None,
                "salary_currency": None,
            })
            kept += 1

        print(f"  ✓ {canonical_name:<20} ({slug:<16}) → {kept}/{len(jobs)} vagas de dados BR")
        time.sleep(TIMEOUT_SLEEP)

    return rows


def _save_bronze(rows: list[dict]) -> Path:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    now = datetime.now(timezone.utc)
    iso_year, iso_week, _ = now.isocalendar()

    df = pd.DataFrame(rows)
    df["_ingest_ts"] = now.isoformat()

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRONZE_DIR / f"lever_{iso_year}_W{iso_week:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    return out_path


def main() -> int:
    print("📋 Data Stack Radar BR — coleta de vagas (Lever, sub-fonte BR)")
    print()

    if not COMPANIES:
        print("  ⚠ Nenhuma empresa Lever no catálogo — nada a coletar.")
        return 0

    rows = collect_all()
    if not rows:
        print("✗ Nenhuma vaga BR coletada — abortando gravação.")
        return 1

    print()
    print(f"→ Total de vagas de dados BR coletadas (Lever, {len(COMPANIES)} empresas): {len(rows)}")

    out_path = _save_bronze(rows)
    print(f"  ✓ {out_path} ({len(rows):,} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
