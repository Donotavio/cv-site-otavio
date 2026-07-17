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

import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion_radar"))
from skills_extractor import extract_skills_row  # noqa: E402
from catalog import (  # noqa: E402
    SALARY_ANCHOR_PATTERN,
    SENIORITY_PATTERNS,
    infer_contract_from_text,
    normalize_contract,
)

GUPY_GLOB = "data/bronze/radar_jobs/*.parquet"
GREENHOUSE_GLOB = "data/bronze/radar_jobs_greenhouse/*.parquet"
# Coletores ATS que compartilham o mesmo schema de bronze (Lever/Ashby/
# InHire/API BR): source → glob. Carregados por `_load_ats()`.
ATS_GLOBS = {
    "lever": "data/bronze/radar_jobs_lever/*.parquet",
    "ashby": "data/bronze/radar_jobs_ashby/*.parquet",
    "inhire": "data/bronze/radar_jobs_inhire/*.parquet",
    "apibr": "data/bronze/radar_jobs_apibr/*.parquet",
}
SILVER_DIR = Path("data/silver")


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


def _load_ats(source: str, glob: str) -> pd.DataFrame:
    """Loader genérico para as fontes ATS (Lever/Ashby/InHire/API BR) que
    compartilham o mesmo schema de bronze — inclui os campos ESTRUTURADOS
    de contrato e salário quando a fonte os fornece (Ashby traz faixa
    salarial; Lever/Ashby/InHire trazem tipo de contrato)."""
    files = sorted(Path(".").glob(glob))
    if not files:
        return pd.DataFrame()

    frames = []
    for f in files:
        df = pd.read_parquet(f)
        df["_iso_week"] = _week_label_from_filename(f)
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    raw = raw.sort_values("_ingest_ts").drop_duplicates(subset=["id", "company_slug"], keep="last")

    out = pd.DataFrame({
        "id": f"{source}_" + raw["company_slug"].astype(str) + "_" + raw["id"].astype(str),
        "title": raw["title"],
        "city": raw["location"],
        "state": "",
        "country": "Brasil",
        "is_remote": raw["is_remote"].fillna(False).astype(bool),
        "publishedDate": raw["updated_at"],
        "_matched_term": f"{source}:" + raw["company"].astype(str),
        "_iso_week": raw["_iso_week"],
        "description": raw["description"],
        "company": raw["company"],
        "url": raw["absolute_url"],
        "source": source,
        # campos estruturados (podem vir vazios conforme a fonte)
        "contract_raw": raw.get("contract_type_raw"),
        "struct_salary_min": raw.get("salary_min"),
        "struct_salary_max": raw.get("salary_max"),
        "struct_salary_currency": raw.get("salary_currency"),
    })
    return out


def _resolve_contract(row: pd.Series) -> str:
    """Contrato ESTRUTURADO (campo do ATS, já normalizado no coletor) tem
    prioridade; senão infere do texto (título+descrição); senão 'não
    especificado'."""
    raw = row.get("contract_raw")
    if isinstance(raw, str) and raw:
        norm = normalize_contract(raw)
        if norm:
            return norm
    return infer_contract_from_text(f"{row.get('title', '')} {row.get('description', '')}")


def _resolve_salary(row: pd.Series) -> tuple[float | None, float | None, str | None, str | None]:
    """Salário ESTRUTURADO (Ashby/InHire) tem prioridade sobre o regex.
    Retorna (min, max, moeda, fonte) — fonte ∈ {estruturado, regex, None}."""
    smin = row.get("struct_salary_min")
    smax = row.get("struct_salary_max")
    if pd.notna(smin) or pd.notna(smax):
        lo = float(smin) if pd.notna(smin) else float(smax)
        hi = float(smax) if pd.notna(smax) else lo
        cur = row.get("struct_salary_currency")
        cur = cur if isinstance(cur, str) and cur else "BRL"
        return min(lo, hi), max(lo, hi), cur, "estruturado"
    rmin, rmax = _extract_salary(row.get("description", ""))
    if rmin is not None:
        return rmin, rmax, "BRL", "regex"
    return None, None, None, None


def build_jobs_clean() -> pd.DataFrame:
    frames = [_load_gupy(), _load_greenhouse()]
    frames += [_load_ats(source, glob) for source, glob in ATS_GLOBS.items()]
    frames = [f for f in frames if not f.empty]

    if not frames:
        raise RuntimeError("Nenhum arquivo bronze de vagas encontrado em nenhuma fonte.")

    raw = pd.concat(frames, ignore_index=True)

    # Colunas estruturadas podem faltar nas fontes antigas (Gupy/Greenhouse)
    # — garante que existam (NaN) para o resolve funcionar após o concat.
    for col in ("contract_raw", "struct_salary_min", "struct_salary_max", "struct_salary_currency"):
        if col not in raw.columns:
            raw[col] = None

    # Vários títulos/nomes de empresa vêm com espaços sobrando na fonte
    # original — cosmético, mas afeta a exibição.
    raw["title"] = raw["title"].str.strip()
    raw["company"] = raw["company"].fillna("").str.strip()

    raw["skills"] = raw.apply(
        lambda r: extract_skills_row(r.get("title", ""), r.get("description", "")), axis=1
    )
    raw["seniority"] = raw["title"].apply(_infer_seniority)
    raw["contract_type"] = raw.apply(_resolve_contract, axis=1)

    salary = raw.apply(_resolve_salary, axis=1)
    raw["salary_min"] = salary.apply(lambda t: t[0])
    raw["salary_max"] = salary.apply(lambda t: t[1])
    raw["salary_currency"] = salary.apply(lambda t: t[2])
    raw["salary_source"] = salary.apply(lambda t: t[3])
    raw["has_salary_info"] = raw["salary_min"].notna()

    clean = raw[[
        "id", "title", "company", "url", "city", "state", "country", "is_remote",
        "seniority", "contract_type", "publishedDate", "_matched_term", "_iso_week",
        "skills", "source", "has_salary_info", "salary_min", "salary_max",
        "salary_currency", "salary_source",
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
