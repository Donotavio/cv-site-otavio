"""
Data Stack Radar BR — Catálogo (fonte única de verdade)
========================================================
Define TODAS as constantes compartilhadas do radar: termos de busca de
vaga, empresas por ATS (Greenhouse/Lever/Ashby/InHire), filtros de
título/localização BR, pacotes PyPI e topics GitHub monitorados,
taxonomia de skills, mapa skill→ferramenta, categorias e os padrões
(regex) de senioridade / contrato / salário.

TODOS os scripts (`collect_*.py`, `skills_extractor.py`, `silver_*.py`,
`gold_*.py`) importam daqui. Nunca hardcodar termo de busca, empresa,
pacote, topic, skill, target ou padrão fora deste arquivo — adicionar
uma ferramenta ou fonte nova deve ser 1 edição aqui.

Espelha o padrão de `ingestion_macro/catalog.py` e
`ingestion_eleicoes/catalog.py`.
"""

from __future__ import annotations

import re

# ─── Termos de busca de vaga (Gupy) ──────────────────────────────────────
SEARCH_TERMS = [
    "engenheiro de dados",
    "data engineer",
    "analytics engineer",
    "data analyst",
    "analista de dados",
    "cientista de dados",
    "data platform",
    "MLOps",
]

# ─── Empresas por ATS (boards públicos, sem auth token) ──────────────────
# Cada ATS expõe uma API/board público por empresa. Chave = slug/tenant na
# URL do ATS; valor = nome canônico exibido. Curadoria editorial: empresas
# BR/LatAm com página de carreira pública ativa e vagas de dados abertas.
#
#   greenhouse: GET boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
#   lever:      GET api.lever.co/v0/postings/{slug}?mode=json
#   ashby:      GET api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
#   inhire:     GET api.inhire.app/job-posts/public/pages   (header X-Tenant: {slug})
ATS_COMPANIES: dict[str, dict[str, str]] = {
    "greenhouse": {
        "stone": "Stone",
        "nubank": "Nubank",
        "inter": "Banco Inter",
        "quintoandar": "QuintoAndar",
        "gympass": "Gympass/Wellhub",
        "ebanx": "Ebanx",
        "vtex": "VTEX",
        "wildlifestudios": "Wildlife Studios",
        "arco": "Arco Educação",
        "vitta": "Vitta",
        "zenvia": "Zenvia",
        "c6bank": "C6 Bank",
    },
    # Curadoria validada board-a-board em 2026-07 (só entram slugs que
    # respondem 200 e trazem vaga de dados BR na curadoria — dead slugs não
    # são incluídos, mantendo a lista auditável). Empresas BR usam pouco
    # Lever/Ashby públicos; a InHire (ATS tech nacional) é a fonte mais rica.
    "lever": {
        "neon": "Neon",
        "cloudwalk": "CloudWalk",
    },
    "ashby": {
        "belvo": "Belvo",
        "swap": "Swap",
    },
    # InHire: `slug` = tenant (header X-Tenant). Consultorias de dados
    # concentram muitas vagas de dados (BIX, Radix, Indicium, Semantix).
    "inhire": {
        "bixtecnologia": "BIX Tecnologia",
        "radix": "Radix",
        "indicium": "Indicium",
        "semantix": "Semantix",
        "intera": "Intera",
        "ctctech": "CTC",
        "dotgroup": "DOT Group",
    },
}

# ─── API BR: repositórios de vaga da comunidade (GitHub issues) ──────────
# O agregador API BR (apibr.com/ui/vagas) coleta vagas publicadas como
# issues nesses repositórios da comunidade dev BR. Consultamos direto a
# GitHub Search API (issues abertas) filtrando por vaga de dados — labels
# trazem contrato (PJ/CLT), senioridade e stack.
APIBR_REPOS = [
    "datascience-br/vagas",   # repo dedicado a vagas de dados (mais rico)
    "backend-br/vagas",
    "frontendbr/vagas",
    "react-brasil/vagas",
    "androiddevbr/vagas",
]

# Labels do API BR que indicam contrato/senioridade/localização (para
# enriquecer a partir dos labels das issues).
APIBR_REMOTE_LABELS = {"remoto", "remote-jobs", "trabalho-remoto", "remote"}
APIBR_BR_LABELS = {"brasil", "nacional"}

# ─── Filtros de vaga (compartilhados por todos os coletores ATS) ─────────
# A Greenhouse/Lever/Ashby/InHire não têm busca por termo/país como o Gupy —
# o board devolve TODAS as vagas da empresa. Filtramos client-side por
# título (é vaga de dados?) e localização (é BR?).
DATA_TITLE_PATTERN = re.compile(
    r"engenheir[ao]\s+de\s+dados|data\s+engineer|analytics\s+engineer|"
    r"data\s+analyst|analista\s+de\s+dados|analista\s+de\s+bi\b|"
    r"cientista\s+de\s+dados|data\s+scientist|data\s+platform|"
    r"\bmlops\b|machine\s+learning\s+engineer|data\s+science|"
    r"business\s+intelligence|\betl\b|data\s+architect|arquitet[ao]\s+de\s+dados",
    re.IGNORECASE,
)

BR_LOCATION_KEYWORDS = [
    "brazil", "brasil", "são paulo", "sao paulo", "rio de janeiro",
    "belo horizonte", "curitiba", "recife", "campinas", "porto alegre",
    "salvador", "fortaleza", "brasília", "brasilia", "florianópolis",
    "florianopolis", "minas gerais", "paraná", "parana", "pernambuco",
    "rio grande do sul", "santa catarina", "goiânia", "goiania",
    "espírito santo", "espirito santo", "distrito federal",
]
# Deliberadamente SEM abreviações de estado de 2 letras (", sp", ", pa"…) —
# ", pa" (Pará) casava com "Palo Alto" e vazava vagas dos EUA pro dataset BR.

# Outros países comuns nas boards multi-país (para desambiguar "Remoto"/
# "Remote" sem país explícito — só tratamos como BR se nenhum aparecer).
OTHER_COUNTRY_KEYWORDS = [
    "argentina", "méxico", "mexico", "colombia", "colômbia", "usa",
    "united states", "canada", "canadá", "france", "frança", "spain",
    "españa", "espanha", "chile", "peru", "uruguay", "uruguai",
]

# ─── Sinal PyPI: pacote → ferramenta canônica ────────────────────────────
PYPI_PACKAGES: dict[str, str] = {
    "apache-airflow": "apache-airflow",
    "prefect": "prefect",
    "dagster": "dagster",
    "dbt-core": "dbt",
    "pyspark": "apache-spark",
    "polars": "polars",
    "duckdb": "duckdb",
    "airbyte-cdk": "airbyte",
    "dlt": "dlt",
    "great-expectations": "great-expectations",
    "mlflow": "mlflow",
}

# ─── Taxonomia de skills (regex) ─────────────────────────────────────────
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

# ─── Ferramentas monitoradas via GitHub topic (sinal GitHub) ─────────────
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

# ─── Skill (taxonomia) → ferramenta canônica do radar ────────────────────
# Só as skills com equivalente direto de tool monitorada via GitHub/PyPI.
# Skills genéricas (python/sql/aws/azure/gcp/docker/kubernetes/power bi/
# bigquery/snowflake/fivetran) ficam fora do radar de *ferramentas de dados*
# mas seguem disponíveis em skills_by_week.parquet.
SKILL_TO_TOOL: dict[str, str] = {
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

# ─── Universo do radar (16 ferramentas): nome canônico → categoria ───────
TOOL_CATEGORY: dict[str, str] = {
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

# ─── Senioridade (inferida do título da vaga) ────────────────────────────
SENIORITY_PATTERNS = [
    ("estágio", re.compile(r"est[aá]gi", re.IGNORECASE)),
    ("júnior", re.compile(r"j[uú]nior|\bjr\b", re.IGNORECASE)),
    ("pleno", re.compile(r"pleno|\bpl\b", re.IGNORECASE)),
    ("sênior", re.compile(r"s[eê]nior|\bsr\b|senior", re.IGNORECASE)),
    ("especialista", re.compile(r"especialista|specialist|staff|principal", re.IGNORECASE)),
    ("liderança", re.compile(r"lead|coordenador|gerente|head|manager", re.IGNORECASE)),
]

# ─── Contrato/vínculo (normalização + fallback por texto) ────────────────
# Normaliza o campo estruturado das fontes ATS (Lever `commitment`, Ashby
# `employmentType`, InHire `contractType`) para um rótulo canônico. Quando
# não há campo estruturado (Gupy/Greenhouse), tenta inferir por regex no
# título+descrição — e cai em "não especificado" se nada bater.
CONTRACT_CANONICAL = ["CLT", "PJ", "Estágio", "Temporário", "não especificado"]

# valor bruto (lowercase) das fontes → rótulo canônico
CONTRACT_RAW_MAP: dict[str, str] = {
    "clt": "CLT",
    "efetivo": "CLT",
    "full-time": "CLT",
    "fulltime": "CLT",
    "full time": "CLT",
    "permanent": "CLT",
    "pj": "PJ",
    "cnpj": "PJ",
    "cooperado": "PJ",
    "contractor": "PJ",
    "contract": "PJ",
    "freelance": "PJ",
    "estágio": "Estágio",
    "estagio": "Estágio",
    "intern": "Estágio",
    "internship": "Estágio",
    "menor aprendiz": "Estágio",
    "apprentice": "Estágio",
    "temporário": "Temporário",
    "temporary": "Temporário",
    "temp": "Temporário",
    "part-time": "Temporário",
    "parttime": "Temporário",
}

# fallback: procura o rótulo no texto livre (título+descrição) quando não há
# campo estruturado. Ordem importa (estágio antes de CLT/PJ).
CONTRACT_PATTERNS = [
    ("Estágio", re.compile(r"est[aá]gi|\bintern\b|menor\s+aprendiz", re.IGNORECASE)),
    ("PJ", re.compile(r"\bpj\b|pessoa\s+jur[íi]dica|\bcnpj\b|cooperad", re.IGNORECASE)),
    ("CLT", re.compile(r"\bclt\b|regime\s+clt|carteira\s+assinada", re.IGNORECASE)),
    ("Temporário", re.compile(r"tempor[áa]ri|\bfreelance\b", re.IGNORECASE)),
]

# ─── Salário: valor REAL e inequívoco na descrição (não benefício) ───────
# Só conta como remuneração real quando o valor vem a poucos caracteres de
# "remuneração"/"salário"/"faixa salarial" — descarta R$ solto de benefício
# (vale-refeição, auxílio home office, plano de saúde etc.).
SALARY_ANCHOR_PATTERN = re.compile(
    r"(?:remunera[çc][ãa]o|sal[áa]rio|faixa\s+salarial)[^R$\n]{0,25}"
    r"r\$\s?([\d.,]+)"
    r"(?:[^R$\n]{0,15}(?:a|até|[-–—]|e)[^R$\n]{0,10}r\$\s?([\d.,]+))?",
    re.IGNORECASE,
)


def is_data_title(title: str) -> bool:
    """True se o título indica vaga de dados/analytics (mesmo filtro do Gupy
    `SEARCH_TERMS`, aplicado client-side nas boards ATS que devolvem todas
    as vagas da empresa)."""
    return bool(DATA_TITLE_PATTERN.search(title or ""))


def is_br_location(location_name: str) -> bool:
    """True se a localização é no Brasil. Trata 'Remoto/Remote' sem país
    explícito como BR (as boards BR/LatAm usam remoto multi-país)."""
    loc = (location_name or "").lower()
    if any(kw in loc for kw in BR_LOCATION_KEYWORDS):
        return True
    if "remot" in loc and not any(kw in loc for kw in OTHER_COUNTRY_KEYWORDS):
        return True
    return False


def normalize_contract(raw: str | None) -> str | None:
    """Mapeia um valor bruto de contrato (campo estruturado do ATS) para o
    rótulo canônico. Retorna None se `raw` for vazio/desconhecido (o caller
    decide se cai no fallback por texto)."""
    if not raw:
        return None
    key = str(raw).strip().lower()
    if key in CONTRACT_RAW_MAP:
        return CONTRACT_RAW_MAP[key]
    for token, label in CONTRACT_RAW_MAP.items():
        if token in key:
            return label
    return None


def infer_contract_from_text(text: str) -> str:
    """Fallback: infere contrato do texto livre (título+descrição).
    Retorna 'não especificado' se nada bater."""
    for label, pattern in CONTRACT_PATTERNS:
        if pattern.search(text or ""):
            return label
    return "não especificado"
