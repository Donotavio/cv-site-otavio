"""
PIX Observatory — Transformações Bronze → Silver → Gold
========================================================
Camadas de transformação seguindo o padrão Medallion Architecture:

  Bronze → Silver: limpeza, tipagem, deduplicação, normalização de nomes
  Silver → Gold:   agregações analíticas, crescimento MoM/YoY, KPIs

Uso:
    python ingestion/transform.py

Dependências:
    duckdb, pandas, pyarrow
"""

import json
import sys
from pathlib import Path
from datetime import date

import pandas as pd
import duckdb
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent.parent))

BRONZE = Path("data/bronze")
SILVER = Path("data/silver")
GOLD = Path("data/gold")

for p in [SILVER, GOLD]:
    p.mkdir(parents=True, exist_ok=True)


# ─── Bronze → Silver ──────────────────────────────────────────────────────────

def build_silver_daily() -> pd.DataFrame:
    """
    Consolida todos os Parquet de bronze/spi_liquidados/ em uma série
    temporal diária limpa, deduplicada e tipada.

    Colunas de saída:
        data, qtd_transacoes, canal_primario, canal_secundario,
        valor_total_reais, ticket_medio, ano, mes, dia_semana, fds
    """
    files = sorted(BRONZE.glob("spi_liquidados/*.parquet"))

    if not files:
        print("  ⚠ Nenhum arquivo bronze/spi_liquidados/ encontrado.")
        print("  → Execute ingestion/ingest_spi.py primeiro.")
        return pd.DataFrame()

    print(f"  → Consolidando {len(files)} arquivo(s) bronze...")

    df = (
        pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        .drop_duplicates(subset=["Data"])
        .sort_values("Data")
        .reset_index(drop=True)
    )

    # Rename para nomes semânticos
    rename_map = {
        "Data":              "data",
        "Quantidade":        "qtd_transacoes",
        "CanalPrimario":     "canal_primario",
        "CanalSecundario":   "canal_secundario",
        "Total":             "valor_total_reais",
        "Media":             "ticket_medio",
    }
    # Aplica apenas as colunas que existem (resiliência a mudanças de schema)
    rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=rename_map)

    # Tipagem
    df["data"] = pd.to_datetime(df["data"])
    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.month
    df["dia_semana"] = df["data"].dt.dayofweek   # 0=segunda, 6=domingo
    df["fds"] = df["dia_semana"].isin([5, 6])

    # Remove linhas com qtd_transacoes nula ou zero (dias sem dados)
    if "qtd_transacoes" in df.columns:
        df = df[df["qtd_transacoes"] > 0]

    out = SILVER / "pix_daily.parquet"
    df.to_parquet(out, index=False, compression="snappy")
    print(f"  ✓ {out} ({len(df):,} linhas)")
    print(f"  Período: {df['data'].min().date()} → {df['data'].max().date()}")

    return df


# ─── Silver → Gold ────────────────────────────────────────────────────────────

def build_gold_monthly() -> pd.DataFrame:
    """
    Agrega pix_daily.parquet por mês, calculando:
        - Soma de transações e valor
        - Ticket médio do período
        - Crescimento MoM (mom) e YoY (yoy) em percentual
        - Dias com dados no mês

    Essa é a tabela principal do dashboard.
    """
    silver_path = SILVER / "pix_daily.parquet"
    if not silver_path.exists():
        print("  ⚠ pix_daily.parquet não encontrado — execute build_silver_daily() primeiro.")
        return pd.DataFrame()

    con = duckdb.connect()
    df = con.execute("""
        WITH base AS (
            SELECT
                DATE_TRUNC('month', data)           AS mes,
                SUM(qtd_transacoes)                 AS qtd_transacoes,
                SUM(COALESCE(valor_total_reais, 0)) AS valor_total_reais,
                AVG(COALESCE(ticket_medio, 0))      AS ticket_medio_avg,
                COUNT(*)                             AS dias_com_dados
            FROM read_parquet('data/silver/pix_daily.parquet')
            GROUP BY 1
        ),
        com_growth AS (
            SELECT
                *,
                LAG(qtd_transacoes, 1)  OVER (ORDER BY mes) AS qtd_mes_anterior,
                LAG(qtd_transacoes, 12) OVER (ORDER BY mes) AS qtd_ano_anterior,
                ROUND(
                    (qtd_transacoes - LAG(qtd_transacoes, 1) OVER (ORDER BY mes))
                    / NULLIF(LAG(qtd_transacoes, 1) OVER (ORDER BY mes), 0) * 100,
                    2
                ) AS crescimento_mom_pct,
                ROUND(
                    (qtd_transacoes - LAG(qtd_transacoes, 12) OVER (ORDER BY mes))
                    / NULLIF(LAG(qtd_transacoes, 12) OVER (ORDER BY mes), 0) * 100,
                    2
                ) AS crescimento_yoy_pct
            FROM base
        )
        SELECT * FROM com_growth ORDER BY mes
    """).df()

    out = GOLD / "pix_monthly.parquet"
    df.to_parquet(out, index=False, compression="snappy")
    print(f"  ✓ {out} ({len(df):,} meses)")
    return df


def build_gold_kpis() -> dict:
    """
    KPIs consolidados para o contexto do chat AI e os cards do dashboard.
    Exporta Parquet + JSON (para leitura direta no frontend estático).

    KPIs calculados:
        - Primeiro e último dia com dados
        - Total histórico de transações e valor
        - Recorde de transações em um dia
        - Ticket médio histórico e extremos
        - Fator de crescimento (max/min qtd)
        - Métricas do último mês disponível
    """
    silver_path = SILVER / "pix_daily.parquet"
    if not silver_path.exists():
        print("  ⚠ pix_daily.parquet não encontrado — execute build_silver_daily() primeiro.")
        return {}

    con = duckdb.connect()

    kpis_df = con.execute("""
        SELECT
            MIN(data)                                           AS primeiro_dia,
            MAX(data)                                          AS ultimo_dia,
            SUM(qtd_transacoes)                                AS total_transacoes,
            SUM(COALESCE(valor_total_reais, 0))                AS total_valor_reais,
            MAX(qtd_transacoes)                                AS record_dia_transacoes,
            argmax(data, qtd_transacoes)                       AS data_record,
            AVG(COALESCE(ticket_medio, 0))                     AS ticket_medio_historico,
            MAX(COALESCE(ticket_medio, 0))                     AS maior_ticket_dia,
            MIN(CASE WHEN ticket_medio > 0 THEN ticket_medio END) AS menor_ticket_dia,
            ROUND(
                MAX(qtd_transacoes)::DOUBLE
                / NULLIF(MIN(CASE WHEN qtd_transacoes > 0 THEN qtd_transacoes END), 0),
                0
            )                                                  AS fator_crescimento
        FROM read_parquet('data/silver/pix_daily.parquet')
        WHERE qtd_transacoes > 0
    """).df()

    # Última semana
    last_week_df = con.execute("""
        SELECT
            AVG(qtd_transacoes) AS media_ultimos_7d,
            MAX(qtd_transacoes) AS max_ultimos_7d
        FROM (
            SELECT * FROM read_parquet('data/silver/pix_daily.parquet')
            ORDER BY data DESC LIMIT 7
        )
    """).df()

    # Salva Parquet
    out_parquet = GOLD / "pix_kpis.parquet"
    kpis_df.to_parquet(out_parquet, index=False)
    print(f"  ✓ {out_parquet}")

    # Converte para dict serializável e salva JSON (lido pelo frontend)
    row = kpis_df.iloc[0].to_dict()
    lw = last_week_df.iloc[0].to_dict()

    for k, v in row.items():
        if hasattr(v, "isoformat"):
            row[k] = str(v)
        elif hasattr(v, "item"):
            row[k] = v.item()

    row["media_ultimos_7d"] = float(lw.get("media_ultimos_7d", 0) or 0)
    row["max_ultimos_7d"] = float(lw.get("max_ultimos_7d", 0) or 0)
    row["gerado_em"] = date.today().isoformat()

    out_json = GOLD / "pix_kpis.json"
    out_json.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {out_json}")

    return row


def build_gold_chaves() -> pd.DataFrame:
    """
    Agrega as chaves PIX por tipo (CPF, CNPJ, email, celular, EVP) por mês.
    Permite análise de composição e crescimento relativo por categoria.
    """
    files = sorted(BRONZE.glob("dict_chaves/*.parquet"))
    if not files:
        print("  ⚠ Nenhum dado de chaves PIX — execute ingest_dict.py primeiro.")
        return pd.DataFrame()

    df = (
        pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        .drop_duplicates()
        .sort_values(["DataBase", "TipoUsuario"] if "TipoUsuario" in
                     pd.read_parquet(files[0]).columns else ["DataBase"])
        .reset_index(drop=True)
    )

    out = GOLD / "pix_chaves_tipo.parquet"
    df.to_parquet(out, index=False, compression="snappy")
    print(f"  ✓ {out} ({len(df):,} linhas)")
    return df


if __name__ == "__main__":
    print("🔄 Iniciando transformações Bronze → Silver → Gold")
    print()

    print("[ Silver ] pix_daily.parquet")
    build_silver_daily()
    print()

    print("[ Gold ] pix_monthly.parquet")
    build_gold_monthly()
    print()

    print("[ Gold ] pix_kpis.parquet + pix_kpis.json")
    kpis = build_gold_kpis()
    if kpis:
        print(f"  Total transações: {kpis.get('total_transacoes', 'N/A'):,.0f}")
        print(f"  Fator crescimento: {kpis.get('fator_crescimento', 'N/A'):,.0f}×")
    print()

    print("[ Gold ] pix_chaves_tipo.parquet")
    build_gold_chaves()
    print()

    print("✅ Transformações concluídas.")
