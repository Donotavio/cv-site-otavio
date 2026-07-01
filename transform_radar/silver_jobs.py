"""
Data Stack Radar BR — Silver: vagas → skills por semana
===========================================================
Lê todos os snapshots semanais de vagas de **duas fontes** —
`data/bronze/radar_jobs/*.parquet` (Gupy, portal agregador) e
`data/bronze/radar_jobs_greenhouse/*.parquet` (Greenhouse Jobs API,
carreiras diretas de empresas BR/LatAm curadas) — normaliza ambas para
um schema comum e aplica a taxonomia regex (`skills_extractor.py`) sobre
título+descrição de cada vaga, produzindo uma tabela long-format (uma
linha por vaga × skill mencionada), agregada por semana ISO.

`job_mentions` no Gold passa a ser a SOMA das menções nas duas fontes —
é a mesma métrica (menções de skill em vaga aberta), só que agora vinda
de mais de um lugar. Não altera pesos nem metodologia do score.

A extração de skills é feita em Python (regex — não é uma agregação),
mas todo o GROUP BY/aggregation final roda em DuckDB, conforme constraint
do projeto.

Saída:
    data/silver/skills_by_week.parquet   — (iso_week, skill, n_jobs)
    data/silver/jobs_clean.parquet       — vagas deduplicadas e tipadas,
                                            com seniority/city/remote/source
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

GUPY_GLOB = "data/bronze/radar_jobs/*.parquet"
GREENHOUSE_GLOB = "data/bronze/radar_jobs_greenhouse/*.parquet"
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
    # ex.: gupy_2026_W27.parquet / greenhouse_2026_W27.parquet -> "2026-W27"
    parts = path.stem.split("_")
    year, week = parts[-2], parts[-1]
    return f"{year}-{week}"


def _load_gupy() -> pd.DataFrame:
    files = sorted(Path(".").glob(GUPY_GLOB))
    if not files:
        return pd.DataFrame()

    frames = []
    for f in files:
        df = pd.read_parquet(f)
        df["_iso_week"] = _week_label_from_filename(f)
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    raw = raw.sort_values("_ingest_ts").drop_duplicates(subset=["id"], keep="last")

    raw["is_remote"] = raw["isRemoteWork"].fillna(False) | (raw["workplaceType"] == "remote")

    out = raw[[
        "id", "name", "city", "state", "country", "is_remote",
        "publishedDate", "_matched_term", "_iso_week", "description",
    ]].rename(columns={"name": "title"})
    out["id"] = "gupy_" + out["id"].astype(str)
    out["source"] = "gupy"
    return out


def _load_greenhouse() -> pd.DataFrame:
    files = sorted(Path(".").glob(GREENHOUSE_GLOB))
    if not files:
        return pd.DataFrame()

    frames = []
    for f in files:
        df = pd.read_parquet(f)
        df["_iso_week"] = _week_label_from_filename(f)
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    raw = raw.sort_values("_ingest_ts").drop_duplicates(subset=["id", "company_slug"], keep="last")

    # Location vem como string livre ("Curitiba", "Belo Horizonte, MG"...) —
    # não tenta separar city/state com precisão (heterogêneo entre empresas),
    # mantém como veio no campo `city` para exibição, sem inferir `state`.
    out = pd.DataFrame({
        "id": "gh_" + raw["company_slug"].astype(str) + "_" + raw["id"].astype(str),
        "title": raw["title"],
        "city": raw["location"],
        "state": "",
        "country": "Brasil",
        "is_remote": raw["location"].str.lower().str.contains("remot", na=False),
        "publishedDate": raw["updated_at"],
        "_matched_term": "greenhouse:" + raw["company"].astype(str),
        "_iso_week": raw["_iso_week"],
        "description": raw["description"],
        "source": "greenhouse",
    })
    return out


def build_jobs_clean() -> pd.DataFrame:
    gupy = _load_gupy()
    greenhouse = _load_greenhouse()

    if gupy.empty and greenhouse.empty:
        raise RuntimeError(
            f"Nenhum arquivo bronze de vagas encontrado em {GUPY_GLOB} nem {GREENHOUSE_GLOB}"
        )

    raw = pd.concat([gupy, greenhouse], ignore_index=True)

    raw["skills"] = raw.apply(
        lambda r: extract_skills_row(r.get("title", ""), r.get("description", "")), axis=1
    )
    raw["seniority"] = raw["title"].apply(_infer_seniority)

    clean = raw[[
        "id", "title", "city", "state", "country", "is_remote",
        "seniority", "publishedDate", "_matched_term", "_iso_week", "skills", "source",
    ]]

    return clean


def main() -> int:
    print("🔍 Silver — extraindo skills das vagas coletadas (Gupy + Greenhouse)")
    clean = build_jobs_clean()
    by_source = clean["source"].value_counts().to_dict()
    print(f"  ✓ {len(clean)} vagas únicas processadas ({by_source})")

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
    # (soma as duas fontes — é a mesma métrica vinda de mais de um lugar)
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
