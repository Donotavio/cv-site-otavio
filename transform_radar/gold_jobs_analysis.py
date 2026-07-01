"""
Data Stack Radar BR — Gold: análise de vagas
================================================
Agrega `data/silver/jobs_clean.parquet` (sempre via DuckDB) para produzir
os números usados na seção "Análise de vagas" do frontend: % remoto,
distribuição por cidade/estado, por senioridade e as skills mais
mencionadas (todas as 24 da taxonomia — não só as 16 do radar de score).

Saída:
    data/gold/jobs_analysis.parquet (resumo por dimensão, formato long)
    assets/data/radar_jobs_analysis.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")


def main() -> int:
    con = duckdb.connect()
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    total_jobs = con.execute("SELECT COUNT(*) FROM 'data/silver/jobs_clean.parquet'").fetchone()[0]

    remote_pct = con.execute("""
        SELECT ROUND(100.0 * SUM(CASE WHEN is_remote THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM 'data/silver/jobs_clean.parquet'
    """).fetchone()[0]

    by_seniority = con.execute("""
        SELECT seniority, COUNT(*) AS n, ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM 'data/silver/jobs_clean.parquet'
        GROUP BY seniority ORDER BY n DESC
    """).df().to_dict(orient="records")

    by_city = con.execute("""
        SELECT city, state, COUNT(*) AS n
        FROM 'data/silver/jobs_clean.parquet'
        WHERE city IS NOT NULL AND city != ''
        GROUP BY city, state ORDER BY n DESC LIMIT 12
    """).df().to_dict(orient="records")

    top_skills = con.execute("""
        SELECT skill, n_jobs, ROUND(100.0 * n_jobs / (SELECT COUNT(*) FROM 'data/silver/jobs_clean.parquet'), 1) AS pct_of_jobs
        FROM 'data/silver/skills_by_week.parquet'
        WHERE iso_week = (SELECT MAX(iso_week) FROM 'data/silver/skills_by_week.parquet')
        ORDER BY n_jobs DESC LIMIT 24
    """).df().to_dict(orient="records")

    by_term = con.execute("""
        SELECT _matched_term AS termo_busca, COUNT(*) AS n
        FROM 'data/silver/jobs_clean.parquet'
        GROUP BY _matched_term ORDER BY n DESC
    """).df().to_dict(orient="records")

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "total_vagas": int(total_jobs),
        "remoto_pct": float(remote_pct) if remote_pct is not None else None,
        "por_senioridade": by_seniority,
        "por_cidade": by_city,
        "por_termo_busca": by_term,
        "skills_mais_mencionadas": top_skills,
    }

    (FRONTEND_DIR / "radar_jobs_analysis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"  ✓ {FRONTEND_DIR / 'radar_jobs_analysis.json'}")

    con.execute(f"""
        COPY (
            SELECT 'senioridade' AS dim, seniority AS chave, n AS valor FROM (
                SELECT seniority, COUNT(*) AS n FROM 'data/silver/jobs_clean.parquet' GROUP BY seniority
            )
            UNION ALL
            SELECT 'cidade', city, COUNT(*) FROM 'data/silver/jobs_clean.parquet'
                WHERE city IS NOT NULL AND city != '' GROUP BY city
        )
        TO '{GOLD_DIR / "jobs_analysis.parquet"}' (FORMAT PARQUET)
    """)
    print(f"  ✓ {GOLD_DIR / 'jobs_analysis.parquet'}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
