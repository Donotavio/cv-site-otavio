"""
Data Stack Radar BR — Gold: scores do radar + trending
==========================================================
Combina os 3 sinais (jobs, GitHub, PyPI) em um score único por
ferramenta, normalizado via PERCENT_RANK() (0–100, maior = mais forte),
com peso jobs 50% / github 25% / pypi 25%, e classifica em quadrante
(Adopt/Trial/Assess/Hold) — 100% em SQL/DuckDB, sem pandas para
agregações.

Universo de ferramentas = união das 14 monitoradas via GitHub topic
(TOOL_TOPICS) + 2 adicionais só com sinal PyPI (dlt, great-expectations)
= 16 ferramentas. Ferramentas sem menção nas vagas coletadas recebem
job_score mínimo (0 menções é um dado real, não um erro).

Saída:
    data/gold/radar_scores.parquet   + assets/data/radar_scores.json
    data/gold/trending.parquet       + assets/data/radar_trending.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")

# Skill (regex taxonomy) → ferramenta canônica (só as que têm equivalente
# direto de tool monitorada via GitHub/PyPI — skills genéricas como
# python/sql/aws/azure/gcp/docker/kubernetes/power bi/bigquery/snowflake/
# fivetran ficam de fora do radar de *ferramentas de dados* propriamente,
# mas continuam disponíveis em skills_by_week.parquet para outras análises).
SKILL_TO_TOOL = {
    "airflow": "apache-airflow",
    "dagster": "dagster",
    "prefect": "prefect",
    "databricks": "databricks",
    "spark": "apache-spark",
    "dbt": "dbt",
    "duckdb": "duckdb",
    "polars": "polars",
    "kafka": "apache-kafka",
    "delta lake": "delta-lake",
    "iceberg": "apache-iceberg",
    "airbyte": "airbyte",
    "mlflow": "mlflow",
}

# Universo completo do radar (16 ferramentas) — nome canônico → categoria
# (usado só para agrupar visualmente no frontend).
TOOL_CATEGORY = {
    "apache-airflow": "orquestração",
    "dagster": "orquestração",
    "prefect": "orquestração",
    "kestra": "orquestração",
    "databricks": "plataforma",
    "dbt": "transformação",
    "apache-spark": "processamento",
    "polars": "processamento",
    "duckdb": "processamento",
    "apache-kafka": "streaming",
    "delta-lake": "storage",
    "apache-iceberg": "storage",
    "airbyte": "ingestão",
    "dlt": "ingestão",
    "mlflow": "mlops",
    "great-expectations": "qualidade",
}


def main() -> int:
    con = duckdb.connect()
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    tools_sql = ", ".join(f"('{t}', '{cat}')" for t, cat in TOOL_CATEGORY.items())
    skill_map_sql = ", ".join(f"('{s}', '{t}')" for s, t in SKILL_TO_TOOL.items())

    con.execute(f"""
        CREATE TEMP TABLE tools AS
            SELECT * FROM (VALUES {tools_sql}) AS t(tool, category);

        CREATE TEMP TABLE skill_map AS
            SELECT * FROM (VALUES {skill_map_sql}) AS m(skill, tool);
    """)

    # ── Sinal 1: jobs (semana mais recente disponível) ──────────────────
    con.execute("""
        CREATE TEMP TABLE latest_week AS
            SELECT MAX(iso_week) AS w FROM read_parquet('data/silver/skills_by_week.parquet');

        CREATE TEMP TABLE job_signal AS
            SELECT sm.tool, COALESCE(SUM(sw.n_jobs), 0) AS job_mentions
            FROM skill_map sm
            LEFT JOIN read_parquet('data/silver/skills_by_week.parquet') sw
                ON sw.skill = sm.skill AND sw.iso_week = (SELECT w FROM latest_week)
            GROUP BY sm.tool;
    """)

    # ── Sinal 2: GitHub (mês mais recente disponível) ───────────────────
    con.execute("""
        CREATE TEMP TABLE latest_gh_month AS
            SELECT MAX(ingest_month) AS m FROM read_parquet('data/silver/github_monthly.parquet');

        CREATE TEMP TABLE github_signal AS
            SELECT tool, COALESCE(MAX(new_repos_ytd), 0) AS new_repos_ytd
            FROM read_parquet('data/silver/github_monthly.parquet')
            WHERE ingest_month = (SELECT m FROM latest_gh_month)
            GROUP BY tool;
    """)

    # ── Sinal 3: PyPI (mês mais recente disponível) ─────────────────────
    con.execute("""
        CREATE TEMP TABLE latest_pypi_month AS
            SELECT MAX(ingest_month) AS m FROM read_parquet('data/silver/pypi_monthly.parquet');

        CREATE TEMP TABLE pypi_signal AS
            SELECT tool, COALESCE(MAX(last_month), 0) AS downloads_last_month
            FROM read_parquet('data/silver/pypi_monthly.parquet')
            WHERE ingest_month = (SELECT m FROM latest_pypi_month)
            GROUP BY tool;
    """)

    # ── Combina + PERCENT_RANK + score ponderado + quadrante ────────────
    con.execute("""
        CREATE TEMP TABLE combined AS
            SELECT
                t.tool,
                t.category,
                COALESCE(j.job_mentions, 0) AS job_mentions,
                COALESCE(g.new_repos_ytd, 0) AS new_repos_ytd,
                COALESCE(p.downloads_last_month, 0) AS downloads_last_month
            FROM tools t
            LEFT JOIN job_signal j ON j.tool = t.tool
            LEFT JOIN github_signal g ON g.tool = t.tool
            LEFT JOIN pypi_signal p ON p.tool = t.tool;

        CREATE TEMP TABLE ranked AS
            SELECT
                tool, category, job_mentions, new_repos_ytd, downloads_last_month,
                ROUND(PERCENT_RANK() OVER (ORDER BY job_mentions) * 100, 1) AS job_score,
                ROUND(PERCENT_RANK() OVER (ORDER BY new_repos_ytd) * 100, 1) AS github_score,
                ROUND(PERCENT_RANK() OVER (ORDER BY downloads_last_month) * 100, 1) AS pypi_score
            FROM combined;

        CREATE TEMP TABLE scored AS
            SELECT
                *,
                ROUND(job_score * 0.5 + github_score * 0.25 + pypi_score * 0.25, 1) AS total_score,
                CASE
                    WHEN (job_score * 0.5 + github_score * 0.25 + pypi_score * 0.25) >= 75 THEN 'Adopt'
                    WHEN (job_score * 0.5 + github_score * 0.25 + pypi_score * 0.25) >= 50 THEN 'Trial'
                    WHEN (job_score * 0.5 + github_score * 0.25 + pypi_score * 0.25) >= 25 THEN 'Assess'
                    ELSE 'Hold'
                END AS quadrant
            FROM ranked;
    """)

    n_tools = con.execute("SELECT COUNT(*) FROM scored").fetchone()[0]

    con.execute(f"""
        COPY (SELECT * FROM scored ORDER BY total_score DESC)
        TO '{GOLD_DIR / "radar_scores.parquet"}' (FORMAT PARQUET)
    """)
    print(f"  ✓ {GOLD_DIR / 'radar_scores.parquet'} ({n_tools} ferramentas)")

    scores_df = con.execute("SELECT * FROM scored ORDER BY total_score DESC").df()
    latest_week = con.execute("SELECT w FROM latest_week").fetchone()[0]
    latest_gh_month = con.execute("SELECT m FROM latest_gh_month").fetchone()[0]
    latest_pypi_month = con.execute("SELECT m FROM latest_pypi_month").fetchone()[0]

    payload_scores = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "metodologia": {
            "job_score": "PERCENT_RANK() sobre menções de skill na semana mais recente de vagas coletadas (Gupy + Greenhouse Jobs API)",
            "github_score": "PERCENT_RANK() sobre repositórios novos (topic search) desde 1º de janeiro do ano vigente",
            "pypi_score": "PERCENT_RANK() sobre downloads/mês (PyPI Stats)",
            "total_score": "job_score*0.5 + github_score*0.25 + pypi_score*0.25",
            "quadrantes": {"Adopt": ">=75", "Trial": ">=50", "Assess": ">=25", "Hold": "<25"},
        },
        "janelas": {
            "jobs_semana": latest_week,
            "github_mes": latest_gh_month,
            "pypi_mes": latest_pypi_month,
        },
        "tools": scores_df.to_dict(orient="records"),
    }
    (FRONTEND_DIR / "radar_scores.json").write_text(
        json.dumps(payload_scores, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"  ✓ {FRONTEND_DIR / 'radar_scores.json'}")

    # ── Trending: growth_pct últimas 4 semanas vs. 4 semanas anteriores ──
    # (real — se não houver histórico suficiente ainda, fica marcado
    # explicitamente como tal, sem inventar número).
    weeks_available = con.execute("""
        SELECT COUNT(DISTINCT iso_week) FROM read_parquet('data/silver/skills_by_week.parquet')
    """).fetchone()[0]

    if weeks_available >= 8:
        trending_df = con.execute("""
            WITH weeks AS (
                SELECT DISTINCT iso_week FROM read_parquet('data/silver/skills_by_week.parquet')
                ORDER BY iso_week DESC
            ),
            recent_weeks AS (SELECT iso_week FROM weeks LIMIT 4),
            prior_weeks AS (SELECT iso_week FROM weeks LIMIT 8 OFFSET 4),
            recent AS (
                SELECT sm.tool, SUM(sw.n_jobs) AS mentions
                FROM skill_map sm
                LEFT JOIN read_parquet('data/silver/skills_by_week.parquet') sw
                    ON sw.skill = sm.skill AND sw.iso_week IN (SELECT iso_week FROM recent_weeks)
                GROUP BY sm.tool
            ),
            prior AS (
                SELECT sm.tool, SUM(sw.n_jobs) AS mentions
                FROM skill_map sm
                LEFT JOIN read_parquet('data/silver/skills_by_week.parquet') sw
                    ON sw.skill = sm.skill AND sw.iso_week IN (SELECT iso_week FROM prior_weeks)
                GROUP BY sm.tool
            )
            SELECT
                r.tool,
                COALESCE(p.mentions, 0) AS mentions_prior_4w,
                COALESCE(r.mentions, 0) AS mentions_recent_4w,
                CASE WHEN COALESCE(p.mentions, 0) > 0
                     THEN ROUND((r.mentions - p.mentions) * 100.0 / p.mentions, 1)
                     ELSE NULL
                END AS growth_pct
            FROM recent r
            LEFT JOIN prior p ON p.tool = r.tool
            ORDER BY growth_pct DESC NULLS LAST
        """).df()
        insufficient_history = False
    else:
        trending_df = con.execute("SELECT tool FROM tools").df()
        trending_df["mentions_prior_4w"] = None
        trending_df["mentions_recent_4w"] = None
        trending_df["growth_pct"] = None
        insufficient_history = True

    con.execute(f"""
        COPY (SELECT * FROM trending_df)
        TO '{GOLD_DIR / "trending.parquet"}' (FORMAT PARQUET)
    """)
    print(f"  ✓ {GOLD_DIR / 'trending.parquet'}")

    payload_trending = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "insufficient_history": insufficient_history,
        "nota": (
            "Histórico ainda insuficiente para calcular crescimento 4 semanas "
            "vs. 4 semanas anteriores — necessário acumular pelo menos 8 semanas "
            "de coleta (o pipeline roda semanalmente às segundas-feiras)."
            if insufficient_history else
            "growth_pct compara menções de skill nas 4 semanas mais recentes "
            "vs. as 4 semanas imediatamente anteriores."
        ),
        "weeks_available": int(weeks_available),
        "tools": trending_df.to_dict(orient="records"),
    }
    (FRONTEND_DIR / "radar_trending.json").write_text(
        json.dumps(payload_trending, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"  ✓ {FRONTEND_DIR / 'radar_trending.json'}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
