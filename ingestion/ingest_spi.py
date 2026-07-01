"""
PIX Observatory — Ingestão Bronze: SPI (Sistema de Pagamentos Instantâneos)
===========================================================================
Coleta os endpoints do SPI do BACEN via python-bcb e salva em Parquet na
camada bronze. Zero autenticação necessária — APIs abertas do BACEN.

Uso:
    python ingestion/ingest_spi.py

Saída:
    data/bronze/spi_liquidados/spi_liquidados_YYYY_MM.parquet
    data/bronze/spi_disponibilidade/spi_disponibilidade_YYYY_MM.parquet
    data/bronze/spi_interrupcoes/spi_interrupcoes_YYYY_MM.parquet
"""

import sys
from pathlib import Path
from datetime import date, datetime
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Adiciona o root ao path para imports relativos
sys.path.insert(0, str(Path(__file__).parent.parent))

BRONZE_PATH = Path("data/bronze")


def _save_parquet(df: pd.DataFrame, out_path: Path) -> None:
    """Salva DataFrame como Parquet com compressão snappy."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, out_path, compression="snappy")
    print(f"  ✓ {out_path} ({len(df):,} linhas)")


def ingest_spi_liquidados(from_date: date | None = None) -> pd.DataFrame:
    """
    Puxa PixLiquidadosAtual desde from_date (ou novembro/2020 se None).
    Endpoint: série diária de volume e valor de transações PIX.

    Returns:
        DataFrame bruto salvo em bronze/spi_liquidados/.
    """
    try:
        from bcb import SPI
        pix = SPI()
        ep = pix.get_endpoint("PixLiquidadosAtual")

        query = ep.query().orderby(ep.Data.asc())
        if from_date:
            query = query.filter(ep.Data >= from_date)

        df = query.collect()
    except Exception as e:
        print(f"  ✗ python-bcb falhou: {e}")
        print("  → Tentando fallback via requests direto à API BACEN...")
        df = _ingest_spi_liquidados_fallback(from_date)

    df["_ingest_ts"] = datetime.utcnow().isoformat()

    today = date.today().strftime("%Y_%m")
    out_path = BRONZE_PATH / "spi_liquidados" / f"spi_liquidados_{today}.parquet"
    _save_parquet(df, out_path)
    return df


def _ingest_spi_liquidados_fallback(from_date: date | None = None) -> pd.DataFrame:
    """
    Fallback: coleta PixLiquidadosAtual diretamente via requests OData.
    Usado quando python-bcb não está disponível ou falha.
    """
    import requests

    base_url = (
        "https://olinda.bcb.gov.br/olinda/servico/SPI/versao/v1/odata/"
        "PixLiquidadosAtual?$format=json&$orderby=Data%20asc"
    )

    if from_date:
        date_str = from_date.strftime("%Y-%m-%d")
        base_url += f"&$filter=Data%20ge%20'{date_str}'"

    all_records = []
    url = base_url + "&$top=1000&$skip=0"

    while url:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        records = data.get("value", [])
        all_records.extend(records)

        # OData paginação
        next_link = data.get("@odata.nextLink")
        url = next_link if next_link else None

    return pd.DataFrame(all_records)


def ingest_spi_disponibilidade() -> pd.DataFrame:
    """
    Puxa PixDisponibilidadeSPI — disponibilidade mensal do sistema (SLA).
    Mostra o índice de disponibilidade vs. o mínimo normativo do BACEN.
    """
    try:
        from bcb import SPI
        pix = SPI()
        ep = pix.get_endpoint("PixDisponibilidadeSPI")
        df = ep.query().orderby(ep.DataBase.asc()).collect()
    except Exception as e:
        print(f"  ✗ PixDisponibilidadeSPI via bcb falhou: {e} — pulando")
        return pd.DataFrame()

    df["_ingest_ts"] = datetime.utcnow().isoformat()

    today = date.today().strftime("%Y_%m")
    out_path = BRONZE_PATH / "spi_disponibilidade" / f"spi_disponibilidade_{today}.parquet"
    _save_parquet(df, out_path)
    return df


def ingest_spi_interrupcoes() -> pd.DataFrame:
    """
    Puxa PixInterrupcaoSPI — log de incidentes/interrupções do sistema.
    Fonte para análise de resiliência e SLA histórico.
    """
    try:
        from bcb import SPI
        pix = SPI()
        ep = pix.get_endpoint("PixInterrupcaoSPI")
        df = ep.query().collect()
    except Exception as e:
        print(f"  ✗ PixInterrupcaoSPI via bcb falhou: {e} — pulando")
        return pd.DataFrame()

    df["_ingest_ts"] = datetime.utcnow().isoformat()

    today = date.today().strftime("%Y_%m")
    out_path = BRONZE_PATH / "spi_interrupcoes" / f"spi_interrupcoes_{today}.parquet"
    _save_parquet(df, out_path)
    return df


if __name__ == "__main__":
    print("🔄 Iniciando ingestão Bronze — SPI")
    print()

    print("→ PixLiquidadosAtual (série histórica completa)...")
    df_liquidados = ingest_spi_liquidados()
    print(f"  Período: {df_liquidados['Data'].min() if not df_liquidados.empty else 'N/A'} "
          f"→ {df_liquidados['Data'].max() if not df_liquidados.empty else 'N/A'}")
    print()

    print("→ PixDisponibilidadeSPI...")
    ingest_spi_disponibilidade()
    print()

    print("→ PixInterrupcaoSPI...")
    ingest_spi_interrupcoes()
    print()

    print("✅ Ingestão Bronze SPI concluída.")
