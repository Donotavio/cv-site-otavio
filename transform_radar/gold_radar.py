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

sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion_radar"))
from catalog import SKILL_TO_TOOL, TOOL_CATEGORY  # noqa: E402

GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")


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
            "job_score": "PERCENT_RANK() sobre menções de skill na semana mais recente de vagas coletadas (Gupy, Greenhouse, Lever, Ashby, InHire e API BR)",
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

    # ── Trending: variação da SHARE de demanda por ferramenta ────────────
    # Mede a fatia (%) que cada ferramenta representa das menções de skill do
    # universo do radar, e compara a janela recente vs. anterior. Usar SHARE
    # (não contagem absoluta) torna o sinal robusto à entrada de novas fontes
    # de vaga — mais fontes elevam o volume de todas as ferramentas, mas não
    # a fatia relativa de uma. Janela adaptativa (medalhão real, sem inventar):
    #   >= 8 semanas → média das 4 semanas recentes vs. 4 anteriores (suave)
    #   >= 2 semanas → semana mais recente vs. semana anterior (janela curta)
    #    < 2 semanas → insuficiente (sem número)
    weeks = [r[0] for r in con.execute("""
        SELECT DISTINCT iso_week FROM read_parquet('data/silver/skills_by_week.parquet')
        ORDER BY iso_week DESC
    """).fetchall()]
    weeks_available = len(weeks)

    def _weeks_sql(ws: list[str]) -> str:
        return ", ".join("'" + w.replace("'", "''") + "'" for w in ws)

    if weeks_available >= 8:
        recent_weeks, prior_weeks = weeks[0:4], weeks[4:8]
        mode, window_label = "media_4s", "4 semanas recentes vs. 4 anteriores"
    elif weeks_available >= 2:
        recent_weeks, prior_weeks = weeks[0:1], weeks[1:2]
        mode, window_label = "semana", "semana mais recente vs. semana anterior"
    else:
        recent_weeks, prior_weeks = [], []
        mode, window_label = "insuficiente", "acumulando histórico"

    insufficient_history = mode == "insuficiente"

    if not insufficient_history:
        trending_df = con.execute(f"""
            WITH recent_m AS (
                SELECT sm.tool, COALESCE(SUM(sw.n_jobs), 0) AS m
                FROM skill_map sm
                LEFT JOIN read_parquet('data/silver/skills_by_week.parquet') sw
                    ON sw.skill = sm.skill AND sw.iso_week IN ({_weeks_sql(recent_weeks)})
                GROUP BY sm.tool
            ),
            prior_m AS (
                SELECT sm.tool, COALESCE(SUM(sw.n_jobs), 0) AS m
                FROM skill_map sm
                LEFT JOIN read_parquet('data/silver/skills_by_week.parquet') sw
                    ON sw.skill = sm.skill AND sw.iso_week IN ({_weeks_sql(prior_weeks)})
                GROUP BY sm.tool
            ),
            tot AS (
                SELECT (SELECT SUM(m) FROM recent_m) AS r, (SELECT SUM(m) FROM prior_m) AS p
            )
            SELECT
                t.tool,
                COALESCE(rm.m, 0) AS mentions_recent,
                COALESCE(pm.m, 0) AS mentions_prior,
                ROUND(100.0 * COALESCE(rm.m, 0) / NULLIF((SELECT r FROM tot), 0), 1) AS share_recent_pct,
                ROUND(100.0 * COALESCE(pm.m, 0) / NULLIF((SELECT p FROM tot), 0), 1) AS share_prior_pct
            FROM tools t
            LEFT JOIN recent_m rm ON rm.tool = t.tool
            LEFT JOIN prior_m pm ON pm.tool = t.tool
        """).df()
        trending_df["share_recent_pct"] = trending_df["share_recent_pct"].fillna(0.0)
        trending_df["share_prior_pct"] = trending_df["share_prior_pct"].fillna(0.0)
        trending_df["delta_pp"] = (trending_df["share_recent_pct"] - trending_df["share_prior_pct"]).round(1)
        trending_df["direction"] = trending_df["delta_pp"].apply(
            lambda d: "up" if d > 0.1 else ("down" if d < -0.1 else "flat")
        )
        # ordena por maior movimento (risers no topo, fallers no fim), com
        # tiebreaker estável por tool para não gerar diff de ruído no CI
        trending_df = trending_df.sort_values(
            ["delta_pp", "tool"], ascending=[False, True]
        ).reset_index(drop=True)
    else:
        trending_df = con.execute("SELECT tool FROM tools ORDER BY tool").df()
        for col in ("mentions_recent", "mentions_prior", "share_recent_pct",
                    "share_prior_pct", "delta_pp"):
            trending_df[col] = None
        trending_df["direction"] = "flat"

    con.execute(f"""
        COPY (SELECT * FROM trending_df)
        TO '{GOLD_DIR / "trending.parquet"}' (FORMAT PARQUET)
    """)
    print(f"  ✓ {GOLD_DIR / 'trending.parquet'}")

    payload_trending = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "insufficient_history": insufficient_history,
        "mode": mode,
        "window_label": window_label,
        "nota": (
            "Histórico ainda insuficiente — necessário pelo menos 2 semanas de "
            "coleta para comparar janelas (o pipeline roda diariamente e agrega "
            "por semana ISO)."
            if insufficient_history else
            f"Variação da fatia (share, em pontos percentuais) de cada ferramenta "
            f"nas menções de vaga do universo do radar: {window_label}. Share "
            f"(não contagem) para ser robusto à entrada de novas fontes. A partir "
            f"de 8 semanas, a janela passa a usar a média de 4 semanas (mais suave)."
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
