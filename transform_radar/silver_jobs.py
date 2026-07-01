"""
Data Stack Radar BR — Silver: vagas → skills por semana
===========================================================
Lê todos os snapshots semanais em `data/bronze/radar_jobs/*.parquet`,
aplica a taxonomia regex (`skills_extractor.py`) sobre título+descrição
de cada vaga e produz uma tabela long-format (uma linha por
vaga × skill mencionada), agregada por semana ISO.

A extração de skills é feita em Python (regex — não é uma agregação),
mas todo o GROUP BY/aggregation final roda em DuckDB, conforme constraint
do projeto.

Saída:
    data/silver/skills_by_week.parquet   — (iso_week, skill, n_jobs)
    data/silver/jobs_clean.parquet       — vagas deduplicadas e tipadas,
                                            com seniority/city/remote
                                            (usado na análise de vagas)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion_radar"))
from skills_extractor import extract_skills_row  # noqa: E402

BRONZE_GLOB = "data/bronze/radar_jobs/*.parquet"
SILVER_DIR = Path("data/silver")

SENIORITY_PATTERNS = [
    ("estágio", re.compile(r"est[aá]gi", re.IGNORECASE)),
    ("júnior", re.compile(r"j[uú]nior|\bjr\b", re.IGNORECASE)),
    ("pleno", re.compile(r"pleno|\bpl\b", re.IGNORECASE)),
    ("sênior", re.compile(r"s[eê]nior|\bsr\b|senior", re.IGNORECASE)),
    ("especialista", re.compile(r"especialista|specialist|staff|principal", re.IGNORECASE)),
    ("liderança", re.compile(r"lead|coordenador|gerente|head|manager", re.IGNORECASE)),
]


def _infer_seniority(title: str) -> str:
    for label, pattern in SENIORITY_PATTERNS:
        if pattern.search(title or ""):
            return label
    return "não especificado"


def _week_label_from_filename(path: Path) -> str:
    # ex.: gupy_2026_W27.parquet -> "2026-W27"
    stem = path.stem
    parts = stem.split("_")
    year, week = parts[1], parts[2]
    return f"{year}-{week}"


def build_jobs_clean() -> pd.DataFrame:
    files = sorted(Path(".").glob(BRONZE_GLOB))
    if not files:
        raise RuntimeError(f"Nenhum arquivo bronze encontrado em {BRONZE_GLOB}")

    frames = []
    for f in files:
        df = pd.read_parquet(f)
        df["_iso_week"] = _week_label_from_filename(f)
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)

    # Dedup: mesma vaga pode aparecer em múltiplos snapshots semanais —
    # mantemos a ocorrência mais recente por id.
    raw = raw.sort_values("_ingest_ts").drop_duplicates(subset=["id"], keep="last")

    raw["skills"] = raw.apply(
        lambda r: extract_skills_row(r.get("name", ""), r.get("description", "")), axis=1
    )
    raw["seniority"] = raw["name"].apply(_infer_seniority)
    raw["is_remote"] = raw["isRemoteWork"].fillna(False) | (raw["workplaceType"] == "remote")

    clean = raw[[
        "id", "name", "city", "state", "country", "workplaceType", "is_remote",
        "seniority", "publishedDate", "_matched_term", "_iso_week", "skills",
    ]].rename(columns={"name": "title"})

    return clean


def main() -> int:
    print("🔍 Silver — extraindo skills das vagas coletadas")
    clean = build_jobs_clean()
    print(f"  ✓ {len(clean)} vagas únicas processadas")

    SILVER_DIR.mkdir(parents=True, exist_ok=True)

    # jobs_clean.parquet — grava via DuckDB (lista de skills como VARCHAR[] nativo)
    con = duckdb.connect()
    con.register("clean_df", clean)
    con.execute(f"""
        COPY (SELECT * FROM clean_df)
        TO '{SILVER_DIR / "jobs_clean.parquet"}' (FORMAT PARQUET)
    """)
    print(f"  ✓ {SILVER_DIR / 'jobs_clean.parquet'}")

    # skills_by_week.parquet — explode a lista de skills e agrega por semana
    con.execute(f"""
        COPY (
            SELECT iso_week, skill, COUNT(*) AS n_jobs
            FROM (
                SELECT _iso_week AS iso_week, unnest(skills) AS skill
                FROM clean_df
            )
            GROUP BY iso_week, skill
            ORDER BY iso_week, n_jobs DESC
        )
        TO '{SILVER_DIR / "skills_by_week.parquet"}' (FORMAT PARQUET)
    """)
    print(f"  ✓ {SILVER_DIR / 'skills_by_week.parquet'}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
