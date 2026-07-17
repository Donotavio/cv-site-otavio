"""
Data Stack Radar BR — Coleta de vagas via Ashby Posting API (sub-fonte)
============================================================================
A Ashby expõe um board público oficial por organização (sem auth):

    GET https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true

Retorna `{ jobs: [...] }`. Campos usados: `title`, `location`,
`employmentType` (**contrato** — ex.: "FullTime", "Intern"), `isRemote`,
`descriptionPlain`, `jobUrl`, `compensation` (faixa salarial estruturada,
quando a empresa opta por exibir — muitas não exibem, então é opcional).

Curadoria no catálogo (`ATS_COMPANIES["ashby"]`). Dupla filtragem
client-side: título casa `DATA_TITLE_PATTERN` + localização BR.

Uso:
    python ingestion_radar/collect_jobs_ashby.py

Saída:
    data/bronze/radar_jobs_ashby/ashby_{YYYY}_W{WW}.parquet
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

API_BASE = "https://api.ashbyhq.com/posting-api/job-board/{org}"
BRONZE_DIR = Path("data/bronze/radar_jobs_ashby")
COMPANIES: dict[str, str] = ATS_COMPANIES["ashby"]
TIMEOUT = 30
TIMEOUT_SLEEP = 1.0


def _parse_compensation(comp: dict | None) -> tuple[float | None, float | None, str | None]:
    """Extrai (min, max, moeda) da faixa salarial estruturada da Ashby, se
    presente. Só aceita componente do tipo salário/anual/mensal com valores
    numéricos — retorna (None, None, None) quando a empresa não publica."""
    if not comp:
        return None, None, None
    # summaryComponents é o formato mais estável; cai p/ compensationTiers.
    components: list[dict] = list(comp.get("summaryComponents") or [])
    for tier in comp.get("compensationTiers") or []:
        components.extend(tier.get("components") or [])
    for c in components:
        ctype = (c.get("compensationType") or "").lower()
        if ctype and ctype != "salary":
            continue
        mn, mx = c.get("minValue"), c.get("maxValue")
        cur = c.get("currencyCode")
        if isinstance(mn, (int, float)) or isinstance(mx, (int, float)):
            lo = float(mn) if isinstance(mn, (int, float)) else None
            hi = float(mx) if isinstance(mx, (int, float)) else lo
            if lo is None:
                lo = hi
            if lo is not None:
                return min(lo, hi), max(lo, hi), cur
    return None, None, None


def collect_all() -> list[dict]:
    rows: list[dict] = []

    for slug, canonical_name in COMPANIES.items():
        url = API_BASE.format(org=slug)
        try:
            resp = requests.get(
                url,
                params={"includeCompensation": "true"},
                headers={"User-Agent": "data-stack-radar-br/1.0"},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            jobs = resp.json().get("jobs", [])
        except (requests.RequestException, ValueError) as e:
            print(f"  ✗ {canonical_name} ({slug}): falha na busca ({e})")
            continue

        kept = 0
        for job in jobs:
            title = job.get("title", "")
            if not is_data_title(title):
                continue
            location = job.get("location", "") or ""
            is_remote = bool(job.get("isRemote"))
            if not (is_br_location(location) or (is_remote and is_br_location("remoto"))):
                continue
            smin, smax, scur = _parse_compensation(job.get("compensation"))
            rows.append({
                "id": str(job.get("id", "")),
                "company": canonical_name,
                "company_slug": slug,
                "title": title,
                "description": job.get("descriptionPlain", "") or "",
                "location": location,
                "absolute_url": job.get("jobUrl", "") or "",
                "updated_at": str(job.get("publishedAt", "") or ""),
                "is_remote": is_remote,
                "contract_type_raw": normalize_contract(job.get("employmentType")),
                "salary_min": smin,
                "salary_max": smax,
                "salary_currency": scur,
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
    out_path = BRONZE_DIR / f"ashby_{iso_year}_W{iso_week:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    return out_path


def main() -> int:
    print("📋 Data Stack Radar BR — coleta de vagas (Ashby, sub-fonte BR)")
    print()

    if not COMPANIES:
        print("  ⚠ Nenhuma empresa Ashby no catálogo — nada a coletar.")
        return 0

    rows = collect_all()
    if not rows:
        print("✗ Nenhuma vaga BR coletada — abortando gravação.")
        return 1

    print()
    print(f"→ Total de vagas de dados BR coletadas (Ashby, {len(COMPANIES)} empresas): {len(rows)}")

    out_path = _save_bronze(rows)
    print(f"  ✓ {out_path} ({len(rows):,} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
