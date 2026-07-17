"""
Data Stack Radar BR — Coleta de vagas via InHire Public API (sub-fonte)
============================================================================
A InHire é o ATS de recrutamento tech nacional (BR). Expõe a página de
carreira pública por tenant, sem auth (apenas o header `X-Tenant`):

    GET https://api.inhire.app/job-posts/public/pages          (X-Tenant: {tenant})
        → { tenantName, ..., jobsPage: [ {jobId, displayName, location,
             workplaceType, status}, ... ] }                    (lista "lean")

    GET https://api.inhire.app/job-posts/public/pages/{jobId}   (X-Tenant: {tenant})
        → { displayName, contractType: ["PJ"|"CLT"|...], description (HTML),
             workplaceType, location, ... }                     (detalhe)

Vantagem sobre Gupy/Greenhouse: `contractType` vem **estruturado** (não
inferido por regex) — alimenta a análise de vínculo (CLT/PJ/estágio).

Estratégia: baixa a lista lean, filtra por título de dados (`displayName`),
e só então busca o detalhe de cada vaga que passou (1 request/vaga) — evita
N requests desnecessários. Fail-soft por tenant e por vaga.

Uso:
    python ingestion_radar/collect_jobs_inhire.py

Saída:
    data/bronze/radar_jobs_inhire/inhire_{YYYY}_W{WW}.parquet
"""

from __future__ import annotations

import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from catalog import ATS_COMPANIES, is_br_location, is_data_title, normalize_contract

PAGES_URL = "https://api.inhire.app/job-posts/public/pages"
DETAIL_URL = "https://api.inhire.app/job-posts/public/pages/{job_id}"
CAREER_URL = "https://carreiras.inhire.app/{tenant}/vaga/{job_id}"
BRONZE_DIR = Path("data/bronze/radar_jobs_inhire")
TENANTS: dict[str, str] = ATS_COMPANIES["inhire"]
TIMEOUT = 30
TIMEOUT_SLEEP = 0.6


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&ccedil;|&atilde;|&otilde;|&ecirc;|&aacute;|&eacute;|&iacute;|&oacute;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _inhire_is_br(location: str) -> bool:
    """A InHire usa código ISO de país no campo location (ex.: 'BR')."""
    loc = (location or "").strip().upper()
    return loc in {"BR", "BRA", "BRASIL", "BRAZIL"} or is_br_location(location)


def _first(value) -> str | None:
    """contractType vem como lista (ex.: ['PJ']); pega o primeiro valor."""
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else None
    return str(value) if value else None


def collect_all() -> list[dict]:
    rows: list[dict] = []

    for tenant, canonical_name in TENANTS.items():
        headers = {"User-Agent": "data-stack-radar-br/1.0", "X-Tenant": tenant}
        try:
            resp = requests.get(PAGES_URL, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            lean = resp.json().get("jobsPage", [])
        except (requests.RequestException, ValueError) as e:
            print(f"  ✗ {canonical_name} ({tenant}): falha na página ({e})")
            continue

        candidates = [
            j for j in lean
            if j.get("status") == "published"
            and is_data_title(j.get("displayName", ""))
            and _inhire_is_br(j.get("location", ""))
        ]

        kept = 0
        for lean_job in candidates:
            job_id = lean_job.get("jobId")
            if not job_id:
                continue
            try:
                d = requests.get(
                    DETAIL_URL.format(job_id=job_id), headers=headers, timeout=TIMEOUT
                )
                d.raise_for_status()
                detail = d.json()
            except (requests.RequestException, ValueError) as e:
                print(f"    ⚠ vaga {job_id} sem detalhe ({e})")
                detail = {}
            time.sleep(TIMEOUT_SLEEP)

            title = detail.get("displayName") or lean_job.get("displayName", "")
            workplace = (detail.get("workplaceType") or lean_job.get("workplaceType") or "")
            rows.append({
                "id": str(job_id),
                "company": canonical_name,
                "company_slug": tenant,
                "title": title,
                "description": _strip_html(detail.get("description", "")),
                "location": detail.get("location") or lean_job.get("location", "") or "BR",
                "absolute_url": CAREER_URL.format(tenant=tenant, job_id=job_id),
                "updated_at": str(detail.get("publishedAt") or detail.get("createdAt") or ""),
                "is_remote": "remot" in workplace.lower(),
                "contract_type_raw": normalize_contract(_first(detail.get("contractType"))),
                "salary_min": None,
                "salary_max": None,
                "salary_currency": None,
            })
            kept += 1

        print(f"  ✓ {canonical_name:<18} ({tenant:<16}) → {kept}/{len(lean)} vagas de dados BR")
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
    out_path = BRONZE_DIR / f"inhire_{iso_year}_W{iso_week:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    return out_path


def main() -> int:
    print("📋 Data Stack Radar BR — coleta de vagas (InHire, sub-fonte BR)")
    print()

    if not TENANTS:
        print("  ⚠ Nenhum tenant InHire no catálogo — nada a coletar.")
        return 0

    rows = collect_all()
    if not rows:
        print("✗ Nenhuma vaga BR coletada — abortando gravação.")
        return 1

    print()
    print(f"→ Total de vagas de dados BR coletadas (InHire, {len(TENANTS)} tenants): {len(rows)}")

    out_path = _save_bronze(rows)
    print(f"  ✓ {out_path} ({len(rows):,} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
