"""
Observatório Eleições 2026 — coleta do perfil das candidaturas
================================================================
Baixa o dataset "Candidatos" (consulta_cand) do Portal de Dados Abertos do
TSE para 2026 e grava TODAS as candidaturas do arquivo nacional consolidado
(todos os cargos, ~20,7 mil linhas) com as colunas demográficas que o painel
agrega — sem filtro de cargo (diferente de integridade/patrimônio, que
recortam para o roster presidente/governador).

Uso:
    python ingestion_eleicoes/collect_candidaturas.py

Saída:
    data/bronze/eleicoes_candidaturas/candidaturas_{YYYY}_{MM}_{DD}.parquet
    (schema: sq_candidato, cargo, uf, partido, genero, cor_raca,
     grau_instrucao, ocupacao, dt_nascimento, situacao, ano_eleicao)

ATENÇÃO (situação): em ago/2026 DS_SITUACAO_CANDIDATURA vem '#NE' (campo não
preenchido) para TODAS as 20.708 candidaturas — o prazo de registro fechou em
15/08 e o julgamento leva semanas (mesma realidade documentada na §13 do
painel). NUNCA filtrar por situação aqui: zeraria o universo inteiro. A
coluna vai crua para o bronze e o gold registra a nota no payload.

Fail-soft: mesmo bloqueio de rede do consulta_cand descrito em
tse_dados_abertos.py. Se o download falhar, o bronze do dia simplesmente NÃO
é gravado (exit 0) — o gold reusa o último bronze bom em vez de publicar um
JSON zerado. Gravar bronze vazio aqui apagaria um universo de 20 mil
candidaturas do painel por causa de um 403 intermitente.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    ANO_ELEICAO_PRESIDENCIAL,
    TSE_CONSULTA_CAND_SUFIXO_BRASIL,
    TSE_CONSULTA_CAND_ZIP_URL_FMT,
)
from ingestion_eleicoes.tse_dados_abertos import (  # noqa: E402
    baixar_zip_csv_brasil,
    col,
)

BRONZE_DIR = Path("data/bronze/eleicoes_candidaturas")

# Colunas do consulta_cand usadas pelo perfil das candidaturas — nomes
# oficiais do padrão TSE, CONFIRMADOS contra o CSV real de 2026 (ago/2026).
# CAND_COLUNAS do helper compartilhado não expõe as demográficas; o dict vive
# aqui (e não no catálogo) porque catalog.py está em edição paralela por outra
# frente — constante nova de uso exclusivo deste coletor fica no coletor.
PERFIL_COLUNAS = {
    "sq_candidato": "SQ_CANDIDATO",
    "cargo": "DS_CARGO",
    "uf": "SG_UF",
    "partido": "SG_PARTIDO",
    "genero": "DS_GENERO",
    "cor_raca": "DS_COR_RACA",
    "grau_instrucao": "DS_GRAU_INSTRUCAO",
    "ocupacao": "DS_OCUPACAO",
    "dt_nascimento": "DT_NASCIMENTO",  # dd/mm/aaaa
    "situacao": "DS_SITUACAO_CANDIDATURA",
    "ano_eleicao": "ANO_ELEICAO",
}


def _coletar() -> list[dict] | None:
    """Baixa consulta_cand_2026 e projeta as colunas de perfil. None se a rede falhar."""
    url = TSE_CONSULTA_CAND_ZIP_URL_FMT.format(ano=ANO_ELEICAO_PRESIDENCIAL)
    linhas = baixar_zip_csv_brasil(
        url, TSE_CONSULTA_CAND_SUFIXO_BRASIL, "consulta_cand (perfil candidaturas)", colunas=PERFIL_COLUNAS
    )
    if linhas is None:
        return None

    # Defensivo: o zip do ano é mono-ano por construção, mas se o TSE algum
    # dia misturar ciclos (como faz nos zips de pesquisa), avisar alto — o
    # perfil de 2026 não pode diluir candidatura de outro ano.
    anos = {col(row, PERFIL_COLUNAS, "ano_eleicao") for row in linhas}
    if anos - {str(ANO_ELEICAO_PRESIDENCIAL)}:
        print(f"  ! ANO_ELEICAO inesperado no CSV: {sorted(anos)} (esperado só {ANO_ELEICAO_PRESIDENCIAL})")

    return [{campo: col(row, PERFIL_COLUNAS, campo) for campo in PERFIL_COLUNAS} for row in linhas]


def _save_bronze(rows: list[dict]) -> Path:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    now = datetime.now(timezone.utc)
    df = pd.DataFrame(rows)
    df["_ingest_ts"] = now.isoformat()
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRONZE_DIR / f"candidaturas_{now.year}_{now.month:02d}_{now.day:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    return out_path


def main() -> int:
    print("🗳  Observatório Eleições 2026 — coleta do perfil das candidaturas")
    rows = _coletar()
    if rows is None:
        print("  ✗ download indisponível — bronze de hoje não gravado (gold reusa o último bom).")
        return 0  # fail-soft: 403 intermitente do CDN não derruba o pipeline

    out_path = _save_bronze(rows)
    n_situacoes = {}
    for r in rows:
        n_situacoes[r["situacao"] or "(vazio)"] = n_situacoes.get(r["situacao"] or "(vazio)", 0) + 1
    print(f"  ✓ {out_path} ({len(rows):,} candidaturas · situações: {n_situacoes})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
