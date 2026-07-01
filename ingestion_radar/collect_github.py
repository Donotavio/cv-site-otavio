"""
Data Stack Radar BR — Sinal GitHub (repositórios novos por ferramenta)
========================================================================
Fonte real: GitHub Search API (REST), sem PyGithub externo — usa apenas
`requests` para manter a dependência mínima e o mesmo padrão de
autenticação via `GITHUB_TOKEN` do Actions (30 req/min é suficiente para
14 ferramentas × 1 request cada).

Para cada ferramenta monitorada, contamos quantos repositórios com aquele
`topic` foram criados desde 1º de janeiro do ano vigente — um proxy de
"quanto a comunidade brasileira/global está adotando essa tool agora"
(GitHub Search não permite filtrar por país, então é sinal global, não
BR-específico — documentado no README do frontend).

Uso:
    GITHUB_TOKEN=... python ingestion_radar/collect_github.py

Saída:
    data/bronze/radar_github/github_{YYYY}_{MM}.parquet
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from skills_extractor import TOOL_TOPICS

API_URL = "https://api.github.com/search/repositories"
BRONZE_DIR = Path("data/bronze/radar_github")
TIMEOUT = 30


def _token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")


def _headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "data-stack-radar-br/1.0",
    }
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _created_since() -> str:
    """1º de janeiro do ano vigente, formato exigido pela Search API."""
    return date(date.today().year, 1, 1).isoformat()


def collect_all() -> list[dict]:
    since = _created_since()
    rows: list[dict] = []
    headers = _headers()

    for topic, canonical_name in TOOL_TOPICS.items():
        query = f"topic:{topic} created:>{since}"
        try:
            resp = requests.get(
                API_URL,
                params={"q": query, "per_page": 1},
                headers=headers,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            total = data.get("total_count", 0)
            rows.append({
                "topic": topic,
                "tool": canonical_name,
                "new_repos_ytd": total,
                "since": since,
            })
            print(f"  ✓ {canonical_name:<16} topic:{topic:<16} → {total:,} repos novos desde {since}")
        except requests.RequestException as e:
            print(f"  ✗ {canonical_name}: falha na busca ({e})")
            rows.append({
                "topic": topic,
                "tool": canonical_name,
                "new_repos_ytd": None,
                "since": since,
            })

        remaining = resp.headers.get("X-RateLimit-Remaining") if 'resp' in dir() else None
        time.sleep(2.1)  # 30 req/min do token do Actions → ~1 req cada 2s é seguro

    return rows


def _save_bronze(rows: list[dict]) -> Path:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    now = datetime.now(timezone.utc)
    df = pd.DataFrame(rows)
    df["_ingest_ts"] = now.isoformat()

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRONZE_DIR / f"github_{now.year}_{now.month:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    return out_path


def main() -> int:
    print("🐙 Data Stack Radar BR — coleta de sinais GitHub")
    print()

    if not _token():
        print("  ⚠ GITHUB_TOKEN não definido — requests sem autenticação (limite de 10/min).")

    rows = collect_all()
    if not rows:
        print("✗ Nenhum dado coletado.")
        return 1

    out_path = _save_bronze(rows)
    print()
    print(f"  ✓ {out_path} ({len(rows)} ferramentas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
