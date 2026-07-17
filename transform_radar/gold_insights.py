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
4. Transparência salarial — % de vagas com um valor de remuneração REAL
   e inequívoco extraído da descrição (ver `SALARY_ANCHOR_PATTERN` em
   `silver_jobs.py`). Achado real ao validar manualmente: um regex
   solto tipo `R$\d` captura quase só benefício (vale-refeição, auxílio
   home office, plano de saúde) — só 2 de 301 vagas (0,7%) têm de fato
   um número de salário/remuneração declarado. Não calculamos "média
   salarial por cargo" nem "evolução no tempo" com esse volume — seria
   estatisticamente enganoso com N=2. Em vez disso, mostramos os poucos
   pontos reais como amostra anedótica (não como estatística), e citamos
   como contexto externo a pesquisa "State of Data Brazil" (Data
   Hackers + Bain & Company, ~5.200 respondentes) para quem quer uma
   referência de mercado com N estatisticamente relevante.

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
# Amostra mínima por senioridade para reportar mediana/faixa salarial — com
# N menor, seria estatisticamente enganoso (mostramos amostra anedótica).
SALARY_MIN_SAMPLE = 5


def main() -> int:
    con = duckdb.connect()
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Vagas mais recentes (com link) ───────────────────────────────
    recentes = con.execute(f"""
        SELECT
            title, company, city, is_remote, seniority, contract_type, skills, url, source,
            publishedDate,
            TRY_CAST(publishedDate AS TIMESTAMP) AS published_ts
        FROM 'data/silver/jobs_clean.parquet'
        WHERE url IS NOT NULL AND url != ''
        ORDER BY published_ts DESC NULLS LAST, title ASC
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
        ORDER BY n_vagas DESC, company ASC
        LIMIT {COMPANY_LIMIT}
    """).df().to_dict(orient="records")

    # ── 2b. Cobertura por fonte (transparência metodológica) ────────────
    # Quantas vagas cada fonte contribui + quantas empresas distintas —
    # deixa explícito o viés de amostra (nenhuma fonte cobre o mercado todo).
    cobertura_por_fonte = con.execute("""
        SELECT source AS fonte,
               COUNT(*) AS n_vagas,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct,
               COUNT(DISTINCT NULLIF(company, '')) AS n_empresas
        FROM 'data/silver/jobs_clean.parquet'
        GROUP BY source
        ORDER BY n_vagas DESC, fonte ASC
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
        ORDER BY n_vagas DESC, skill_a ASC, skill_b ASC
        LIMIT {COMBO_LIMIT}
    """).df()

    # ── 4. Transparência salarial (valor REAL, não menção de benefício) ──
    total_jobs_all = con.execute("SELECT COUNT(*) FROM 'data/silver/jobs_clean.parquet'").fetchone()[0]
    n_com_salario = con.execute("""
        SELECT COUNT(*) FROM 'data/silver/jobs_clean.parquet' WHERE has_salary_info = true
    """).fetchone()[0]
    salario_pct = round(100.0 * n_com_salario / total_jobs_all, 1) if total_jobs_all else 0.0

    # Fonte do salário: estruturado (faixa nativa do ATS) vs regex (extraído
    # da descrição) — transparência sobre a origem de cada número.
    salario_por_fonte = con.execute("""
        SELECT COALESCE(salary_source, 'sem_salario') AS origem, COUNT(*) AS n
        FROM 'data/silver/jobs_clean.parquet'
        WHERE has_salary_info = true
        GROUP BY salary_source ORDER BY n DESC, origem ASC
    """).df().to_dict(orient="records")

    # Salário por senioridade — só reportado para buckets com amostra
    # suficiente (>= SALARY_MIN_SAMPLE); com N baixo seria enganoso. Hoje o
    # volume é insuficiente, então tende a vir vazio (o frontend cai na
    # amostra anedótica) — a query já está pronta para quando crescer.
    salario_por_senioridade = con.execute(f"""
        SELECT seniority,
               COUNT(*) AS n,
               ROUND(MEDIAN(salary_min), 0) AS mediana_min,
               ROUND(MEDIAN(salary_max), 0) AS mediana_max,
               ROUND(QUANTILE_CONT(salary_max, 0.25), 0) AS p25,
               ROUND(QUANTILE_CONT(salary_max, 0.75), 0) AS p75
        FROM 'data/silver/jobs_clean.parquet'
        WHERE has_salary_info = true
        GROUP BY seniority
        HAVING COUNT(*) >= {SALARY_MIN_SAMPLE}
        ORDER BY mediana_max DESC, seniority ASC
    """).df().to_dict(orient="records")

    vagas_com_salario_real = con.execute("""
        SELECT title, company, seniority, contract_type,
               salary_min, salary_max, salary_currency, salary_source, url, source
        FROM 'data/silver/jobs_clean.parquet'
        WHERE has_salary_info = true
        ORDER BY salary_max DESC, title ASC
    """).df().to_dict(orient="records")

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "vagas_recentes": recentes.drop(columns=["published_ts"]).to_dict(orient="records"),
        "por_empresa": por_empresa,
        "cobertura_por_fonte": cobertura_por_fonte,
        "skill_combos": combos.to_dict(orient="records"),
        "salario_transparencia_pct": salario_pct,
        "n_vagas_com_salario_real": int(n_com_salario),
        "n_vagas_total": int(total_jobs_all),
        "salario_por_fonte": salario_por_fonte,
        "salario_por_senioridade": salario_por_senioridade,
        "vagas_com_salario_real": vagas_com_salario_real,
        "benchmark_externo": {
            "fonte": "State of Data Brazil 2024-2025 (Data Hackers + Bain & Company)",
            "amostra": "5.217 respondentes, pesquisa realizada entre 14/10/2024 e 18/12/2024",
            "salario_crescimento_2023_2024_pct": 11.8,
            "inflacao_2024_pct": 4.83,
            "pct_preferem_100_remoto": 46.0,
            "pct_preferem_hibrido_flexivel": 43.3,
            "url": "https://www.bain.com/pt-br/insights/state-of-data-2024/",
            "nota": (
                "Fonte externa, independente deste pipeline — não coletamos "
                "esses dados via API, é uma citação de contexto para quem "
                "quer uma referência de mercado com amostra estatisticamente "
                "relevante (nosso dado direto de vagas tem N=2, insuficiente "
                "para qualquer média ou série temporal confiável)."
            ),
        },
        "notas": {
            "vagas_recentes": "ordenado por data de publicação — inclui link direto para a vaga original (Gupy, Greenhouse, Lever, InHire ou API BR).",
            "por_empresa": "só empresas com nome de careerPage/company disponível nos dados coletados.",
            "cobertura_por_fonte": (
                "quantas vagas cada fonte contribui (e quantas empresas distintas). "
                "Nenhuma fonte cobre o mercado inteiro — o número é medição da nossa "
                "amostra agregada, não do universo de vagas do Brasil."
            ),
            "salario_por_fonte": (
                "origem do número salarial: 'estruturado' = faixa nativa do ATS "
                "(Ashby/InHire); 'regex' = extraído da descrição com padrão estrito."
            ),
            "salario_por_senioridade": (
                f"só reportado para senioridades com amostra >= {SALARY_MIN_SAMPLE} vagas "
                "com salário real — abaixo disso seria estatisticamente enganoso, então "
                "fica vazio e a UI mostra os pontos individuais (amostra anedótica)."
            ),
            "skill_combos": "pares de skill que aparecem juntos na mesma vaga — não é o score do radar, é 'o que estudar junto'.",
            "salario_transparencia_pct": (
                "% de vagas com um valor de remuneração REAL e inequívoco na "
                "descrição (não conta menção de benefício — vale-refeição, "
                "auxílio home office, plano de saúde etc., que não é salário). "
                "Com N tão baixo, não calculamos média por cargo nem evolução "
                "no tempo — os valores abaixo são mostrados individualmente, "
                "como amostra, não como estatística de mercado."
            ),
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
