"""
PIX Observatory — Ingestão Bronze: DICT (Diretório de Identificadores)
=======================================================================
Coleta endpoints do DICT do BACEN — chaves PIX por tipo de usuário,
participantes e transações fora do SPI.

Uso:
    python ingestion/ingest_dict.py

Saída:
    data/bronze/dict_chaves/dict_chaves_YYYY_MM.parquet
    data/bronze/dict_participantes/dict_participantes_YYYY_MM.parquet
"""

import sys
from pathlib import Path
from datetime import date, datetime
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

BRONZE_PATH = Path("data/bronze")
DICT_BASE = "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/"


def _odata_collect(endpoint: str, filter_str: str = "") -> pd.DataFrame:
    """
    Coleta um endpoint OData do BACEN com paginação automática.

    Args:
        endpoint: Nome do endpoint (ex: 'EstoqueChavesPorTipoUsuario')
        filter_str: Filtro OData opcional (ex: "$filter=...")

    Returns:
        DataFrame com todos os registros.
    """
    url = f"{DICT_BASE}{endpoint}?$format=json&$orderby=DataBase%20asc&$top=1000"
    if filter_str:
        url += f"&{filter_str}"

    all_records = []
    page_url: str | None = url

    while page_url:
        resp = requests.get(page_url, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        records = data.get("value", [])
        all_records.extend(records)
        page_url = data.get("@odata.nextLink")

    return pd.DataFrame(all_records)


def _save_parquet(df: pd.DataFrame, out_path: Path) -> None:
    """Salva DataFrame como Parquet com compressão snappy."""
    if df.empty:
        print(f"  ⚠ Sem dados para {out_path.name} — pulando")
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, out_path, compression="snappy")
    print(f"  ✓ {out_path} ({len(df):,} linhas)")


def ingest_dict_chaves_tipo() -> pd.DataFrame:
    """
    Estoque de chaves PIX por tipo de usuário (CPF, CNPJ, email, celular, EVP).
    Dados mensais — mostra composição do DICT ao longo do tempo.

    Insight esperado: CPF domina, EVP cresce, CNPJ acelera.
    """
    print("  → EstoqueChavesPorTipoUsuario...")
    df = _odata_collect("EstoqueChavesPorTipoUsuario")
    df["_ingest_ts"] = datetime.utcnow().isoformat()

    today = date.today().strftime("%Y_%m")
    out_path = BRONZE_PATH / "dict_chaves" / f"dict_chaves_{today}.parquet"
    _save_parquet(df, out_path)
    return df


def ingest_dict_participantes() -> pd.DataFrame:
    """
    Quantidade de participantes do PIX por mês.
    Mostra crescimento do ecossistema de IFs participantes.
    """
    print("  → QuantidadeParticipantesMes...")
    df = _odata_collect("QuantidadeParticipantesMes")
    df["_ingest_ts"] = datetime.utcnow().isoformat()

    today = date.today().strftime("%Y_%m")
    out_path = BRONZE_PATH / "dict_participantes" / f"dict_participantes_{today}.parquet"
    _save_parquet(df, out_path)
    return df


def ingest_dict_chaves_participante() -> pd.DataFrame:
    """
    Estoque de chaves PIX por participante (market share de chaves por banco).
    Útil para análise de concentração de mercado.
    """
    print("  → EstoqueChavesPorParticipante...")
    try:
        df = _odata_collect("EstoqueChavesPorParticipante")
    except Exception as e:
        print(f"  ✗ Falhou: {e} — pulando")
        return pd.DataFrame()

    df["_ingest_ts"] = datetime.utcnow().isoformat()

    today = date.today().strftime("%Y_%m")
    out_path = BRONZE_PATH / "dict_chaves_participante" / f"dict_chaves_part_{today}.parquet"
    _save_parquet(df, out_path)
    return df


if __name__ == "__main__":
    print("🔄 Iniciando ingestão Bronze — DICT")
    print()

    ingest_dict_chaves_tipo()
    ingest_dict_participantes()
    ingest_dict_chaves_participante()

    print()
    print("✅ Ingestão Bronze DICT concluída.")
