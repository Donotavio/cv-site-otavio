"""
Data Stack Radar BR — Coleta de vagas via Greenhouse Jobs API (sub-fonte)
============================================================================
Complementa o Sinal 1 (vagas) além do Gupy. A Greenhouse expõe uma API
pública oficial por empresa, feita justamente para terceiros embutirem
vagas em outros sites — sem ambiguidade de compliance (diferente de
scraping de portal agregador):

    GET https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true

`content=true` retorna a descrição completa (HTML) de cada vaga numa
única chamada por empresa — não precisa de 1 request por vaga.

Curadoria de empresas (decisão editorial, não técnica — ver `COMPANIES`):
empresas brasileiras/LatAm confirmadas com página de carreiras pública na
Greenhouse e vagas abertas no momento da curadoria (2026-07). A lista é
mantida deliberadamente pequena e auditável — adicionar uma empresa nova
é 1 linha nesta constante.

Filtro geográfico: a Greenhouse não tem parâmetro de busca por país, então
filtramos client-side por palavras-chave de localização (cidades/estados
BR, "Brasil/Brazil", ou "Remoto" em português — que no contexto de uma
vaga sem outro país listado indica público brasileiro). Empresas como
Nubank/QuintoAndar/Gympass contratam para vários países da LatAm na mesma
board — sem esse filtro, o sinal ficaria poluído com vagas México/
Argentina/Colômbia/EUA.

O `job_mentions` resultante é somado ao do Gupy em `silver_jobs.py` (mesma
métrica: menções de skill em vaga aberta — não é um sinal novo, é a mesma
métrica vinda de mais uma fonte, conforme decisão de produto documentada).

Uso:
    python ingestion_radar/collect_jobs_greenhouse.py

Saída:
    data/bronze/radar_jobs_greenhouse/greenhouse_{YYYY}_W{WW}.parquet
"""

from __future__ import annotations

import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API_BASE = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
BRONZE_DIR = Path("data/bronze/radar_jobs_greenhouse")
TIMEOUT = 30

# Curadoria — todas confirmadas com vagas reais abertas em 2026-07.
# name: nome canônico exibido; slug: identificador na URL da Greenhouse.
COMPANIES: dict[str, str] = {
    "stone": "Stone",
    "nubank": "Nubank",
    "inter": "Banco Inter",
    "quintoandar": "QuintoAndar",
    "gympass": "Gympass/Wellhub",
    "ebanx": "Ebanx",
    "vtex": "VTEX",
    "wildlifestudios": "Wildlife Studios",
    "arco": "Arco Educação",
    "vitta": "Vitta",
    "zenvia": "Zenvia",
}

BR_LOCATION_KEYWORDS = [
    "brazil", "brasil", "são paulo", "sao paulo", "rio de janeiro",
    "belo horizonte", "curitiba", "recife", "campinas", "porto alegre",
    "salvador", "fortaleza", "brasília", "brasilia", "florianópolis",
    "florianopolis", ", sp", ", rj", ", mg", ", pr", ", pe", ", rs",
    ", ba", ", ce", ", df", ", sc", ", go", ", pa", ", es",
]

# Outros países comuns nas mesmas boards multi-país (para desambiguar
# "Remoto"/"Remote" sem país explícito — só tratamos como BR se nenhum
# desses aparecer junto).
OTHER_COUNTRY_KEYWORDS = [
    "argentina", "méxico", "mexico", "colombia", "colômbia", "usa",
    "united states", "canada", "canadá", "france", "frança", "spain",
    "españa", "espanha", "chile", "peru", "peru", "uruguay", "uruguai",
]

TIMEOUT_SLEEP = 1.0


def _is_br_location(location_name: str) -> bool:
    loc = (location_name or "").lower()
    if any(kw in loc for kw in BR_LOCATION_KEYWORDS):
        return True
    if "remoto" in loc and not any(kw in loc for kw in OTHER_COUNTRY_KEYWORDS):
        return True
    return False


def _strip_html(html: str) -> str:
    """Remove tags HTML da descrição (regex simples — não precisamos de
    parsing perfeito, só texto corrido suficiente para a taxonomia regex
    de skills funcionar)."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def collect_all() -> list[dict]:
    rows: list[dict] = []

    for slug, canonical_name in COMPANIES.items():
        url = API_BASE.format(company=slug)
        try:
            resp = requests.get(
                url,
                params={"content": "true"},
                headers={"User-Agent": "data-stack-radar-br/1.0"},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            jobs = resp.json().get("jobs", [])
        except requests.RequestException as e:
            print(f"  ✗ {canonical_name} ({slug}): falha na busca ({e})")
            continue

        kept = 0
        for job in jobs:
            location_name = (job.get("location") or {}).get("name", "")
            if not _is_br_location(location_name):
                continue
            rows.append({
                "id": job.get("id"),
                "company": canonical_name,
                "company_slug": slug,
                "title": job.get("title", ""),
                "description": _strip_html(job.get("content", "")),
                "location": location_name,
                "absolute_url": job.get("absolute_url", ""),
                "updated_at": job.get("updated_at", ""),
            })
            kept += 1

        print(f"  ✓ {canonical_name:<20} ({slug:<18}) → {kept}/{len(jobs)} vagas BR")
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
    out_path = BRONZE_DIR / f"greenhouse_{iso_year}_W{iso_week:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    return out_path


def main() -> int:
    print("📋 Data Stack Radar BR — coleta de vagas (Greenhouse, sub-fonte BR)")
    print()

    rows = collect_all()
    if not rows:
        print("✗ Nenhuma vaga BR coletada — abortando gravação.")
        return 1

    print()
    print(f"→ Total de vagas BR coletadas (Greenhouse, {len(COMPANIES)} empresas): {len(rows)}")

    out_path = _save_bronze(rows)
    print(f"  ✓ {out_path} ({len(rows):,} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
