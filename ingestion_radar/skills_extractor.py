"""
Data Stack Radar BR — Extração de skills via regex (taxonomia fixa)
=====================================================================
Aplica uma taxonomia de padrões regex pré-compilados (case-insensitive)
sobre o texto (título + descrição) de cada vaga, para identificar quais
ferramentas/tecnologias de dados são mencionadas.

Não usa NLP probabilístico nem LLM — apenas correspondência de padrões,
conforme constraint do projeto ("Sem componente de IA").

Uso (como módulo):
    from skills_extractor import extract_skills
    skills = extract_skills(job_title + " " + job_description)
"""

from __future__ import annotations

import re

RAW_TAXONOMY: dict[str, list[str]] = {
    "airflow": ["airflow", "apache airflow"],
    "dagster": ["dagster"],
    "prefect": ["prefect"],
    "databricks": ["databricks"],
    "spark": [r"\bspark\b", "pyspark"],
    "dbt": [r"\bdbt\b", r"dbt[\s\-]core"],
    "duckdb": ["duckdb"],
    "polars": ["polars"],
    "kafka": [r"\bkafka\b"],
    "bigquery": ["bigquery"],
    "snowflake": ["snowflake"],
    "delta lake": [r"delta[\s\-]lake"],
    "iceberg": [r"\biceberg\b"],
    "airbyte": ["airbyte"],
    "fivetran": ["fivetran"],
    "power bi": ["power bi", "powerbi"],
    "python": [r"\bpython\b"],
    "sql": [r"\bsql\b"],
    "aws": [r"\baws\b"],
    "azure": [r"\bazure\b"],
    "gcp": [r"\bgcp\b", "google cloud"],
    "mlflow": ["mlflow"],
    "kubernetes": [r"\bk8s\b", "kubernetes"],
    "docker": [r"\bdocker\b"],
}

# Compila tudo uma única vez no import — evita recompilar regex por vaga.
_COMPILED: dict[str, list[re.Pattern]] = {
    skill: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for skill, patterns in RAW_TAXONOMY.items()
}

# Ferramentas monitoradas pelo radar (sinal GitHub/PyPI) — usadas para
# cruzar taxonomia de skills de vaga com o universo de "tools" do radar.
TOOL_TOPICS: dict[str, str] = {
    "airflow": "apache-airflow",
    "dagster": "dagster",
    "prefect": "prefect",
    "databricks": "databricks",
    "dbt": "dbt",
    "spark": "apache-spark",
    "polars": "polars",
    "duckdb": "duckdb",
    "kafka": "apache-kafka",
    "airbyte": "airbyte",
    "mlflow": "mlflow",
    "delta-lake": "delta-lake",
    "iceberg": "apache-iceberg",
    "kestra": "kestra",
}


def extract_skills(text: str) -> list[str]:
    """Retorna a lista de skills (chaves da taxonomia) encontradas em `text`."""
    if not text:
        return []
    found = []
    for skill, patterns in _COMPILED.items():
        if any(p.search(text) for p in patterns):
            found.append(skill)
    return found


def extract_skills_row(title: str, description: str) -> list[str]:
    return extract_skills(f"{title or ''} {description or ''}")
