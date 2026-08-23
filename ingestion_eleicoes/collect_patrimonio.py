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
    (schema: cpf, nome_urna, cargo, uf, partido, ano, patrimonio_total_rs, n_bens,
     tipos_breakdown [json: composição por DS_TIPO_BEM_CANDIDATO, rótulo cru do
     TSE — o agrupamento em categorias legíveis é papel do gold])

Fail-soft: mesmo bloqueio de rede do consulta_cand/bem_candidato descrito em
tse_dados_abertos.py — falha de download em qualquer um dos 4 arquivos (2
datasets × 2 anos) não derruba o pipeline; o ano/dataset que faltar
simplesmente não aparece no bronze.
"""

from __future__ import annotations

import json
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
    lancamento_vazio,
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


def _patrimonio_por_sq(ano: int, sqs_interesse: set[str]) -> dict[str, dict]:
    """{SQ_CANDIDATO: {"total": R$, "n": n_bens, "tipos": {tipo: [R$, n]}}}.

    `total`/`n` mantêm a semântica original (toda linha do CSV conta). O
    breakdown `tipos` é aditivo e guarda o rótulo CRU de DS_TIPO_BEM_CANDIDATO
    — o agrupamento em categorias legíveis fica no gold. Nele aplicamos o
    mesmo filtro de linha-placeholder da prestação de contas
    (`lancamento_vazio`): registro de R$ 0,00 com tipo '#NULO' não é um bem.
    """
    url = TSE_BEM_CANDIDATO_ZIP_URL_FMT.format(ano=ano)
    linhas = baixar_zip_csv_brasil(
        url, TSE_BEM_CANDIDATO_SUFIXO_BRASIL, f"bem_candidato {ano} (patrimônio)", colunas=BEM_COLUNAS
    )
    if linhas is None:
        return {}
    out: dict[str, dict] = defaultdict(
        lambda: {"total": 0.0, "n": 0, "tipos": defaultdict(lambda: [0.0, 0])}
    )
    for row in linhas:
        sq = col(row, BEM_COLUNAS, "sq_candidato")
        if sq not in sqs_interesse:
            continue
        valor = valor_num(row.get(BEM_COLUNAS["valor"]))
        d = out[sq]
        d["total"] += valor
        d["n"] += 1
        tipo = col(row, BEM_COLUNAS, "tipo_bem")
        if lancamento_vazio(valor, tipo):
            continue
        t = d["tipos"][tipo or "não informado"]
        t[0] += valor
        t[1] += 1
    return dict(out)


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
        info = patrimonio.get(sq) or {"total": 0.0, "n": 0, "tipos": {}}
        tipos_breakdown = sorted(
            (
                {"tipo": tipo, "valor_rs": round(v, 2), "n": n}
                for tipo, (v, n) in info["tipos"].items()
            ),
            key=lambda x: x["valor_rs"],
            reverse=True,
        )
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
                "patrimonio_total_rs": info["total"],
                "n_bens": info["n"],
                "tipos_breakdown": json.dumps(tipos_breakdown, ensure_ascii=False),
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
