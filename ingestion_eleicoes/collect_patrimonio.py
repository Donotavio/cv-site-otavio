"""
Observatório Eleições 2026 — coleta de patrimônio declarado (bens)
======================================================================
Baixa os datasets "Candidatos" (consulta_cand) e "Bens de candidato"
(bem_candidato) do Portal de Dados Abertos do TSE para 2026 e 2022, filtra
para presidente + governador (roster do painel) e soma o valor total
declarado por candidato em cada ano — join entre os dois anos por CPF.

Uso:
    python ingestion_eleicoes/collect_patrimonio.py

Saída:
    data/bronze/eleicoes_patrimonio/patrimonio_{YYYY}_{MM}_{DD}.parquet
    (schema: cpf, nome_urna, cargo, uf, partido, ano, patrimonio_total_rs, n_bens)

Fail-soft: mesmo bloqueio de rede do consulta_cand/bem_candidato descrito em
tse_dados_abertos.py — falha de download em qualquer um dos 4 arquivos (2
datasets × 2 anos) não derruba o pipeline; o ano/dataset que faltar
simplesmente não aparece no bronze.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    CARGOS_ROSTER_PAINEL,
    PATRIMONIO_ANO_ATUAL,
    PATRIMONIO_ANO_COMPARACAO,
    TSE_BEM_CANDIDATO_SUFIXO_BRASIL,
    TSE_BEM_CANDIDATO_ZIP_URL_FMT,
    TSE_CONSULTA_CAND_SUFIXO_BRASIL,
    TSE_CONSULTA_CAND_ZIP_URL_FMT,
)
from ingestion_eleicoes.tse_dados_abertos import (  # noqa: E402
    BEM_COLUNAS,
    CAND_COLUNAS,
    baixar_zip_csv_brasil,
    col,
    valor_num,
)

BRONZE_DIR = Path("data/bronze/eleicoes_patrimonio")


def _candidatos_do_ano(ano: int) -> list[dict]:
    """Candidaturas de presidente/governador do ano, com SQ_CANDIDATO próprio daquele ano."""
    url = TSE_CONSULTA_CAND_ZIP_URL_FMT.format(ano=ano)
    linhas = baixar_zip_csv_brasil(
        url, TSE_CONSULTA_CAND_SUFIXO_BRASIL, f"consulta_cand {ano} (patrimônio)", colunas=CAND_COLUNAS
    )
    if linhas is None:
        return []
    return [row for row in linhas if col(row, CAND_COLUNAS, "cargo").upper() in CARGOS_ROSTER_PAINEL]


def _patrimonio_por_sq(ano: int, sqs_interesse: set[str]) -> dict[str, tuple[float, int]]:
    """{SQ_CANDIDATO: (valor_total, n_bens)} só para os sequenciais de interesse."""
    url = TSE_BEM_CANDIDATO_ZIP_URL_FMT.format(ano=ano)
    linhas = baixar_zip_csv_brasil(
        url, TSE_BEM_CANDIDATO_SUFIXO_BRASIL, f"bem_candidato {ano} (patrimônio)", colunas=BEM_COLUNAS
    )
    if linhas is None:
        return {}
    totais: dict[str, float] = defaultdict(float)
    contagem: dict[str, int] = defaultdict(int)
    for row in linhas:
        sq = col(row, BEM_COLUNAS, "sq_candidato")
        if sq not in sqs_interesse:
            continue
        totais[sq] += valor_num(row.get(BEM_COLUNAS["valor"]))
        contagem[sq] += 1
    return {sq: (totais[sq], contagem[sq]) for sq in totais}


def _coletar_ano(ano: int) -> list[dict]:
    candidatos = _candidatos_do_ano(ano)
    if not candidatos:
        return []
    print(f"  · {ano}: {len(candidatos)} candidaturas de presidente/governador")
    sqs = {col(c, CAND_COLUNAS, "sq_candidato") for c in candidatos}
    patrimonio = _patrimonio_por_sq(ano, sqs)

    rows: list[dict] = []
    for c in candidatos:
        sq = col(c, CAND_COLUNAS, "sq_candidato")
        valor, n_bens = patrimonio.get(sq, (0.0, 0))
        rows.append(
            {
                "ano": ano,
                "sq_candidato": sq,
                "cpf": col(c, CAND_COLUNAS, "nr_cpf"),
                "nome_urna": col(c, CAND_COLUNAS, "nome_urna"),
                "nome": col(c, CAND_COLUNAS, "nome"),
                "cargo": col(c, CAND_COLUNAS, "cargo"),
                "uf": col(c, CAND_COLUNAS, "uf"),
                "partido": col(c, CAND_COLUNAS, "partido"),
                "patrimonio_total_rs": valor,
                "n_bens": n_bens,
            }
        )
    return rows


def _save_bronze(rows: list[dict]) -> Path:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    now = datetime.now(timezone.utc)
    df = pd.DataFrame(rows)
    df["_ingest_ts"] = now.isoformat()
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRONZE_DIR / f"patrimonio_{now.year}_{now.month:02d}_{now.day:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    return out_path


def main() -> int:
    print("🗳  Observatório Eleições 2026 — coleta de patrimônio declarado (bens)")
    rows: list[dict] = []
    for ano in (PATRIMONIO_ANO_ATUAL, PATRIMONIO_ANO_COMPARACAO):
        rows.extend(_coletar_ano(ano))

    if not rows:
        print("  ✗ nenhum dado coletado em nenhum dos anos — provável bloqueio de rede.")
        # Fail-soft: grava bronze vazio (schema válido) em vez de abortar o
        # pipeline. O gold trata "sem linhas" como "sem comparação disponível".
        rows = []

    out_path = _save_bronze(rows)
    n_2026 = sum(1 for r in rows if r["ano"] == PATRIMONIO_ANO_ATUAL)
    n_2022 = sum(1 for r in rows if r["ano"] == PATRIMONIO_ANO_COMPARACAO)
    print(f"  ✓ {out_path} ({len(rows)} linhas · {n_2026} em {PATRIMONIO_ANO_ATUAL} · {n_2022} em {PATRIMONIO_ANO_COMPARACAO})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
