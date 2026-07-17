"""
Data Stack Radar BR — Coleta de vagas via API BR / GitHub issues (sub-fonte)
==============================================================================
A comunidade dev BR publica vagas como *issues* em repositórios abertos
(datascience-br/vagas, backend-br/vagas, …) — o mesmo acervo que o
agregador API BR (apibr.com/ui/vagas) indexa. Listamos as issues abertas
de cada repo via GitHub Issues API e filtramos por título de vaga de dados
(`is_data_title`) — mais robusto que a Search API (que limita operadores
OR e casa também no corpo, trazendo falsos positivos):

    GET https://api.github.com/repos/{repo}/issues?state=open&per_page=100

Usa o mesmo `GITHUB_TOKEN` do Actions (como `collect_github.py`). Título +
corpo alimentam a taxonomia de skills; labels e texto dão contrato/vínculo.

Fonte 100% aberta/comunidade — adiciona diversidade de fonte ao radar.
Fail-soft por repositório.

Uso:
    GITHUB_TOKEN=... python ingestion_radar/collect_jobs_apibr.py

Saída:
    data/bronze/radar_jobs_apibr/apibr_{YYYY}_W{WW}.parquet
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from catalog import (
    APIBR_REMOTE_LABELS,
    APIBR_REPOS,
    infer_contract_from_text,
    is_data_title,
    normalize_contract,
)

ISSUES_URL = "https://api.github.com/repos/{repo}/issues"
BRONZE_DIR = Path("data/bronze/radar_jobs_apibr")
TIMEOUT = 30
# labels de contrato explícitas que o normalize_contract entende
_CONTRACT_LABELS = ["clt", "pj", "estágio", "estagio", "temporário", "temporario"]


def _token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "data-stack-radar-br/1.0"}
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _contract_from_labels(labels: list[str]) -> str | None:
    low = [l.lower() for l in labels]
    for c in _CONTRACT_LABELS:
        if c in low:
            return normalize_contract(c)
    return None


def collect_all() -> list[dict]:
    rows: list[dict] = []
    headers = _headers()

    for repo in APIBR_REPOS:
        try:
            resp = requests.get(
                ISSUES_URL.format(repo=repo),
                params={"state": "open", "per_page": 100},
                headers=headers,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            items = resp.json()
        except (requests.RequestException, ValueError) as e:
            print(f"  ✗ {repo}: falha na listagem ({e})")
            continue

        # descarta pull requests (a Issues API mistura PRs) e não-dados
        issues = [i for i in items if "pull_request" not in i and is_data_title(i.get("title", ""))]

        kept = 0
        for issue in issues:
            title = issue.get("title", "")
            body = issue.get("body", "") or ""
            labels = [l.get("name", "") for l in issue.get("labels", [])]
            low = {l.lower() for l in labels}
            text = f"{title} {' '.join(labels)} {body}"
            is_remote = bool(low & APIBR_REMOTE_LABELS) or "remot" in title.lower()
            contract = _contract_from_labels(labels) or infer_contract_from_text(text)
            rows.append({
                "id": str(issue.get("id", "")),
                "company": "",  # issue não tem empresa estruturada confiável
                "company_slug": repo,
                "title": title,
                "description": text,
                "location": "Brasil",  # repos da comunidade dev BR são nacionais
                "absolute_url": issue.get("html_url", "") or "",
                "updated_at": str(issue.get("created_at", "") or ""),
                "is_remote": is_remote,
                "contract_type_raw": contract if contract != "não especificado" else None,
                "salary_min": None,
                "salary_max": None,
                "salary_currency": None,
            })
            kept += 1

        print(f"  ✓ {repo:<28} → {kept}/{len(items)} vagas de dados")
        time.sleep(1.0)

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
    out_path = BRONZE_DIR / f"apibr_{iso_year}_W{iso_week:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    return out_path


def main() -> int:
    print("📋 Data Stack Radar BR — coleta de vagas (API BR / GitHub issues)")
    print()

    if not _token():
        print("  ⚠ GITHUB_TOKEN não definido — search sem auth (limite baixo).")

    rows = collect_all()
    if not rows:
        print("✗ Nenhuma vaga de dados coletada — abortando gravação.")
        return 1

    print()
    print(f"→ Total de vagas de dados coletadas (API BR, {len(APIBR_REPOS)} repos): {len(rows)}")

    out_path = _save_bronze(rows)
    print(f"  ✓ {out_path} ({len(rows):,} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
