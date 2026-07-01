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

# Extrai valor(es) REAL de remuneração — não é "menciona R$ em algum
# lugar" (isso captura quase só benefício: vale-refeição, auxílio home
# office, plano de saúde, bônus de indicação — nada disso é salário).
# Só conta como remuneração real quando o valor vem a poucos caracteres
# de "remuneração"/"salário"/"faixa salarial" — descartamos deliberada-
# mente qualquer R$ solto no meio do texto de benefícios.
# Achado real ao validar manualmente: de 301 vagas, o padrão antigo
# (r"r\$\s?\d") batia em 26 (8,6%) — quase todas eram benefício, não
# salário. Com este padrão mais estrito, restam só 2 (0,7%) — é o dado
# real, e o próprio "quase nada divulga salário" é o insight.
SALARY_ANCHOR_PATTERN = re.compile(
    r"(?:remunera[çc][ãa]o|sal[áa]rio|faixa\s+salarial)[^R$\n]{0,25}"
    r"r\$\s?([\d.,]+)"
    r"(?:[^R$\n]{0,15}(?:a|até|[-–—]|e)[^R$\n]{0,10}r\$\s?([\d.,]+))?",
    re.IGNORECASE,
)


def _infer_seniority(title: str) -> str:
    for label, pattern in SENIORITY_PATTERNS:
        if pattern.search(title or ""):
            return label
    return "não especificado"


def _parse_brl(raw: str) -> float | None:
    """Converte string BR ('20.000', '4037,00', '8.000,00') pra float.
    Assume '.' como separador de milhar e ',' como decimal (padrão BR)."""
    if not raw:
        return None
    cleaned = raw.replace(".", "").replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def _extract_salary(description: str) -> tuple[float | None, float | None]:
    """Retorna (valor_min, valor_max) só quando encontra um valor de
    remuneração real e inequívoco na descrição — (None, None) caso
    contrário (não força extração de menções ambíguas/benefícios)."""
    m = SALARY_ANCHOR_PATTERN.search(description or "")
    if not m:
        return None, None
    v1 = _parse_brl(m.group(1))
    v2 = _parse_brl(m.group(2)) if m.group(2) else None
    if v1 is None:
        return None, None
    if v2 is not None:
        return min(v1, v2), max(v1, v2)
    return v1, v1


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
        "careerPageName", "jobUrl",
    ]].rename(columns={
        "name": "title", "careerPageName": "company", "jobUrl": "url",
    })
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
        "company": raw["company"],
        "url": raw["absolute_url"],
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

    # Vários títulos/nomes de empresa vêm com espaços sobrando na fonte
    # original (Gupy e Greenhouse) — cosmético, mas afeta a exibição
    # (ex.: "Analista de Dados " em vez de "Analista de Dados").
    raw["title"] = raw["title"].str.strip()
    raw["company"] = raw["company"].str.strip()

    raw["skills"] = raw.apply(
        lambda r: extract_skills_row(r.get("title", ""), r.get("description", "")), axis=1
    )
    raw["seniority"] = raw["title"].apply(_infer_seniority)
    salary = raw["description"].apply(_extract_salary)
    raw["salary_min"] = salary.apply(lambda t: t[0])
    raw["salary_max"] = salary.apply(lambda t: t[1])
    raw["has_salary_info"] = raw["salary_min"].notna()

    clean = raw[[
        "id", "title", "company", "url", "city", "state", "country", "is_remote",
        "seniority", "publishedDate", "_matched_term", "_iso_week", "skills", "source",
        "has_salary_info", "salary_min", "salary_max",
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
