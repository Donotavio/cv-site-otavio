"""
Data Stack Radar BR — Gold: insights extras (vagas recentes, empresas,
combinações de skills, transparência salarial)
=============================================================================
Camada Gold adicional, sobre `data/silver/jobs_clean.parquet`, com
agregações "criativas" pensadas para quem está procurando vaga ou
decidindo o que estudar — não é o score do radar, é contexto extra.
Tudo em DuckDB, tudo a partir de dado real já coletado (sem inferência).

1. Vagas mais recentes — lista com link direto para a vaga (Gupy ou
   Greenhouse), ordenada por data de publicação desc. É basicamente um
   "feed" das últimas aberturas de vaga de dados no Brasil.
2. Quem mais contrata — ranking de empresas por nº de vagas de dados
   abertas agora (só Greenhouse tem `company` populado de forma
   confiável hoje; Gupy usa o nome da careerPage, que também vira
   "empresa" quando disponível).
3. Combinações de skills — quais pares de skill aparecem juntos com
   mais frequência na MESMA vaga (ex.: "Python + SQL", "Databricks +
   dbt") — insight de "o que estudar junto", não é o mesmo dado do
   radar (que é por ferramenta isolada).
4. Transparência salarial — % de vagas que mencionam alguma faixa/valor
   de remuneração no texto (não extraímos/agregamos valores — a
   heterogeneidade de formato tornaria qualquer média não confiável).

Saída:
    data/gold/insights.parquet        — skill_combos (formato long)
    assets/data/radar_insights.json   — payload completo p/ frontend
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")

RECENT_LIMIT = 25
COMPANY_LIMIT = 15
COMBO_LIMIT = 15


def main() -> int:
    con = duckdb.connect()
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Vagas mais recentes (com link) ───────────────────────────────
    recentes = con.execute(f"""
        SELECT
            title, company, city, is_remote, seniority, skills, url, source,
            publishedDate,
            TRY_CAST(publishedDate AS TIMESTAMP) AS published_ts
        FROM 'data/silver/jobs_clean.parquet'
        WHERE url IS NOT NULL AND url != ''
        ORDER BY published_ts DESC
        LIMIT {RECENT_LIMIT}
    """).df()
    recentes["published_ts"] = recentes["published_ts"].astype(str)
    recentes["skills"] = recentes["skills"].apply(lambda arr: list(arr) if arr is not None else [])

    # ── 2. Quem mais contrata (ranking de empresas) ─────────────────────
    por_empresa = con.execute(f"""
        SELECT company, COUNT(*) AS n_vagas,
               CAST(SUM(CASE WHEN is_remote THEN 1 ELSE 0 END) AS INTEGER) AS n_remoto,
               source
        FROM 'data/silver/jobs_clean.parquet'
        WHERE company IS NOT NULL AND company != ''
        GROUP BY company, source
        ORDER BY n_vagas DESC
        LIMIT {COMPANY_LIMIT}
    """).df().to_dict(orient="records")

    # ── 3. Combinações de skills (co-ocorrência na mesma vaga) ──────────
    con.execute("""
        CREATE TEMP TABLE job_skill_pairs AS
        SELECT a.id, a.skill AS skill_a, b.skill AS skill_b
        FROM (SELECT id, unnest(skills) AS skill FROM 'data/silver/jobs_clean.parquet') a
        JOIN (SELECT id, unnest(skills) AS skill FROM 'data/silver/jobs_clean.parquet') b
            ON a.id = b.id AND a.skill < b.skill
    """)
    total_jobs = con.execute("SELECT COUNT(*) FROM 'data/silver/jobs_clean.parquet'").fetchone()[0]
    combos = con.execute(f"""
        SELECT skill_a, skill_b, COUNT(*) AS n_vagas,
               ROUND(100.0 * COUNT(*) / {total_jobs}, 1) AS pct_of_jobs
        FROM job_skill_pairs
        GROUP BY skill_a, skill_b
        ORDER BY n_vagas DESC
        LIMIT {COMBO_LIMIT}
    """).df()

    # ── 4. Transparência salarial ───────────────────────────────────────
    salario_pct = con.execute("""
        SELECT ROUND(100.0 * SUM(CASE WHEN has_salary_info THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM 'data/silver/jobs_clean.parquet'
    """).fetchone()[0]

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "vagas_recentes": recentes.drop(columns=["published_ts"]).to_dict(orient="records"),
        "por_empresa": por_empresa,
        "skill_combos": combos.to_dict(orient="records"),
        "salario_transparencia_pct": float(salario_pct) if salario_pct is not None else 0.0,
        "notas": {
            "vagas_recentes": "ordenado por data de publicação — inclui link direto para a vaga original (Gupy ou Greenhouse).",
            "por_empresa": "só empresas com nome de careerPage/company disponível nos dados coletados.",
            "skill_combos": "pares de skill que aparecem juntos na mesma vaga — não é o score do radar, é 'o que estudar junto'.",
            "salario_transparencia_pct": "% de vagas que mencionam alguma faixa/valor de remuneração no texto — não agregamos valores (formato muito heterogêneo entre vagas para uma média ser confiável).",
        },
    }

    (FRONTEND_DIR / "radar_insights.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"  ✓ {FRONTEND_DIR / 'radar_insights.json'}")

    con.register("combos_df", combos)
    con.execute(f"""
        COPY (SELECT skill_a, skill_b, n_vagas, pct_of_jobs FROM combos_df)
        TO '{GOLD_DIR / "insights.parquet"}' (FORMAT PARQUET)
    """)
    print(f"  ✓ {GOLD_DIR / 'insights.parquet'}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
