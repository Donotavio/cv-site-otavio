"""
Data Stack Radar BR — Coleta de vagas (Gupy)
=============================================
Fonte real: Portal Gupy (https://portal.gupy.io), um agregador de vagas
Next.js usado por milhares de empresas brasileiras. A UI do portal busca
vagas via XHR client-side; o endpoint real (descoberto via engenharia
reversa do bundle JS, documentado abaixo) é público e não exige
autenticação:

    GET https://employability-portal.gupy.io/api/v1/jobs
        ?term=<termo de busca>&limit=<N>&offset=<N>

Nota de integração: `portal.gupy.io/api/job-search/jobs` (mencionado em
specs antigas) não existe mais como rota real — o app Next.js atual monta
uma instância axios com baseURL `https://employability-portal.gupy.io` e
chama `/api/v1/jobs`. Validado manualmente em 2026-07-01 com curl.

Compliance:
    - Verificamos `robots.txt` de `portal.gupy.io` (o site/app que expõe
      esta busca) via `urllib.robotparser` antes de rodar — ver
      `_check_robots()`. O host da API (`employability-portal.gupy.io`)
      é um backend interno sem robots.txt próprio (404), então a política
      do portal principal é a que vale.
    - Rate limit: 1 req/s + jitter (0.3–0.9s) entre chamadas.
    - Sem login, sem cookies de sessão, sem headers de autenticação.

Uso:
    python ingestion_radar/collect_jobs.py

Saída:
    data/bronze/radar_jobs/gupy_{YYYY}_W{WW}.parquet   (bronze, snapshot semanal)
"""

from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from catalog import SEARCH_TERMS

API_BASE = "https://employability-portal.gupy.io/api/v1/jobs"
ROBOTS_URL = "https://portal.gupy.io/robots.txt"
USER_AGENT = "data-stack-radar-br/1.0 (+https://donotavio.github.io)"

PAGE_LIMIT = 100          # itens por página aceitos pela API
MAX_PAGES_PER_TERM = 5    # cap de segurança (até 500 vagas/termo)
TIMEOUT = 30
BRONZE_DIR = Path("data/bronze/radar_jobs")


def _check_robots() -> bool:
    """Confere se `portal.gupy.io` permite crawling do que nos interessa."""
    rp = RobotFileParser()
    rp.set_url(ROBOTS_URL)
    try:
        rp.read()
    except (URLError, HTTPError, TimeoutError) as e:
        print(f"  ⚠ Não foi possível ler robots.txt ({e}) — seguindo com cautela.")
        return True
    allowed = rp.can_fetch(USER_AGENT, "https://portal.gupy.io/job-search/")
    print(f"  {'✓' if allowed else '✗'} robots.txt de portal.gupy.io: "
          f"{'permite' if allowed else 'BLOQUEIA'} /job-search/")
    return allowed


def _fetch_page(term: str, offset: int) -> dict:
    params = {"term": term, "limit": PAGE_LIMIT, "offset": offset}
    url = f"{API_BASE}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)


def _sleep_polite() -> None:
    time.sleep(1.0 + random.uniform(0.3, 0.9))


def collect_all() -> list[dict]:
    all_jobs: dict[int, dict] = {}  # dedup por job id (mesma vaga pode bater em vários termos)

    for term in SEARCH_TERMS:
        print(f"→ Buscando: '{term}'")
        offset = 0
        for page in range(MAX_PAGES_PER_TERM):
            try:
                payload = _fetch_page(term, offset)
            except (URLError, HTTPError, TimeoutError) as e:
                print(f"  ✗ falha em offset={offset}: {e}")
                break

            jobs = payload.get("data", [])
            total = payload.get("pagination", {}).get("total", 0)
            if not jobs:
                break

            for job in jobs:
                jid = job.get("id")
                if jid is not None:
                    job["_matched_term"] = term
                    all_jobs.setdefault(jid, job)

            print(f"  ✓ offset={offset}: +{len(jobs)} vagas (total disponível: {total})")

            offset += PAGE_LIMIT
            if offset >= total:
                break
            _sleep_polite()

        _sleep_polite()

    return list(all_jobs.values())


def _save_bronze(jobs: list[dict]) -> Path:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    now = datetime.now(timezone.utc)
    iso_year, iso_week, _ = now.isocalendar()

    df = pd.DataFrame(jobs)
    df["_ingest_ts"] = now.isoformat()

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRONZE_DIR / f"gupy_{iso_year}_W{iso_week:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    return out_path


def main() -> int:
    print("📋 Data Stack Radar BR — coleta de vagas (Gupy)")
    print()

    if not _check_robots():
        print("✗ robots.txt bloqueia a coleta — abortando.")
        return 1

    jobs = collect_all()
    if not jobs:
        print("✗ Nenhuma vaga coletada — abortando gravação.")
        return 1

    print()
    print(f"→ Total de vagas únicas coletadas: {len(jobs)}")

    out_path = _save_bronze(jobs)
    print(f"  ✓ {out_path} ({len(jobs):,} linhas)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
