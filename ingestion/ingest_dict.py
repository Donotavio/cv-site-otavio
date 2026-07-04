"""
PIX Observatory — Ingestão Bronze: DICT (Diretório de Identificadores)
======================================================================
Reconstrói os snapshots de chaves PIX a partir da function import
`ChavesPix(Data='YYYY-MM-DD')` do BACEN — que retorna o estoque de chaves
por instituição (ISPB/Nome), tipo de chave, natureza do usuário e segmento.

Migração de API (jul/2026):
    O BACEN removeu 3 entity sets que este módulo usava originalmente:
      - EstoqueChavesPorTipoUsuario  (chaves por tipo de usuário)
      - QuantidadeParticipantesMes   (participantes por mês)
      - EstoqueChavesPorParticipante (chaves por instituição)

    Esses datasets agora são DERIVADOS da function import `ChavesPix`, que
    permanece ativa e é mais granular — cada linha traz ISPB + TipoChave +
    NaturezaUsuario, então podemos agregar nas três dimensões necessárias
    a partir de uma única chamada mensal.

    Observação: `ChavesPix` retorna no máximo 1000 linhas por chamada
    (ordenadas por qtdChaves desc) — os agregados nacionais são
    aproximações do top de mercado, não totais exatos do sistema. Isso é
    consistente com a metodologia já documentada em ingest_ranking.py.

Uso:
    python ingestion/ingest_dict.py

Saída:
    data/bronze/dict_chaves/dict_chaves_YYYY_MM.parquet
    data/bronze/dict_participantes/dict_participantes_YYYY_MM.parquet
    data/bronze/dict_chaves_participante/dict_chaves_part_YYYY_MM.parquet
"""

import calendar
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent.parent))

BRONZE_PATH = Path("data/bronze")
BASE_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/"
    "ChavesPix"
)
TIMEOUT = 60


# ─── Helpers de data ──────────────────────────────────────────────────────────

def _month_end(d: date) -> date:
    """Retorna o último dia do mês de `d`."""
    last_day = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last_day)


def _shift_months(d: date, months: int) -> date:
    """Desloca `d` em `months` meses e normaliza para o fim do mês."""
    total = d.year * 12 + (d.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    return _month_end(date(year, month, 1))


# ─── Coleta ───────────────────────────────────────────────────────────────────

def _fetch_month(date_str: str) -> list[dict]:
    """
    Busca o snapshot de ChavesPix para um mês (fim do mês, formato ISO).

    Usa a sintaxe de function-call OData com `$filter=Data eq YYYY-MM-DD`
    (ambos são necessários — ver notas de integração em ingest_ranking.py).
    Ordena por qtdChaves desc para garantir que os maiores participantes
    apareçam dentro do limite de 1000 linhas.
    """
    url = (
        f"{BASE_URL}(Data=%27{date_str}%27)?$format=json&$top=1000"
        f"&$filter=Data%20eq%20{date_str}&$orderby=qtdChaves%20desc"
    )
    req = Request(url, headers={"User-Agent": "pix-observatory/1.0"})
    with urlopen(req, timeout=TIMEOUT) as resp:
        data = json.load(resp)
    rows = data.get("value", [])
    dates_found = {r.get("Data") for r in rows}
    if dates_found and dates_found != {date_str}:
        print(f"  ⚠ Aviso: filtro de data pode ter falhado para {date_str} "
              f"(datas encontradas: {dates_found})")
    return rows


def find_latest_available(max_attempts: int = 4) -> tuple[str, list[dict]] | None:
    """
    Tenta o mês corrente e recua até `max_attempts` meses procurando o
    snapshot mais recente disponível (o BACEN publica com defasagem).
    """
    candidate = _month_end(date.today())
    for _ in range(max_attempts):
        date_str = candidate.isoformat()
        try:
            rows = _fetch_month(date_str)
        except (URLError, HTTPError, TimeoutError) as e:
            print(f"  ✗ {date_str} falhou: {e}")
            rows = []
        if rows:
            return date_str, rows
        candidate = _shift_months(candidate, 1)
    return None


# ─── Bronze ───────────────────────────────────────────────────────────────────

def _save_parquet(df: pd.DataFrame, out_path: Path) -> None:
    """Salva DataFrame como Parquet com compressão snappy."""
    if df.empty:
        print(f"  ⚠ Sem dados para {out_path.name} — pulando")
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, out_path, compression="snappy")
    print(f"  ✓ {out_path} ({len(df):,} linhas)")


def ingest_dict_chaves_tipo(rows: list[dict], date_str: str) -> pd.DataFrame:
    """
    Estoque de chaves PIX por tipo de chave (cpf, cnpj, e-mail, celular,
    aleatória/EVP) para o snapshot mensal.

    Derivado de ChavesPix agregando qtdChaves por TipoChave.
    Consumido por transform.build_gold_chaves() — coluna DataBase é exigida.
    """
    print("  → Agregando chaves por tipo de chave...")
    agg: dict[str, int] = defaultdict(int)
    for r in rows:
        agg[r.get("TipoChave", "desconhecido")] += int(r.get("qtdChaves", 0) or 0)

    df = pd.DataFrame(
        [
            {
                "DataBase": date_str,
                "TipoChave": tipo,
                "QtdChaves": qtd,
            }
            for tipo, qtd in sorted(agg.items(), key=lambda kv: -kv[1])
        ]
    )
    df["_ingest_ts"] = datetime.now(timezone.utc).isoformat()

    label = date_str.replace("-", "_")[:7]
    out_path = BRONZE_PATH / "dict_chaves" / f"dict_chaves_{label}.parquet"
    _save_parquet(df, out_path)
    return df


def ingest_dict_participantes(rows: list[dict], date_str: str) -> pd.DataFrame:
    """
    Quantidade de participantes do PIX (ISPBs distintos) no snapshot.

    Derivado de ChavesPix contando ISPBs únicos.
    """
    print("  → Contando participantes (ISPBs distintos)...")
    ispbs = {r.get("ISPB") for r in rows if r.get("ISPB")}
    segmentos = defaultdict(int)
    for r in rows:
        seg = r.get("Segmento", "Não classificado")
        segmentos[seg] += 1

    df = pd.DataFrame(
        [
            {
                "DataBase": date_str,
                "qtd_participantes": len(ispbs),
                "segmento": seg,
                "qtd_ispbs_segmento": n,
            }
            for seg, n in sorted(segmentos.items(), key=lambda kv: -kv[1])
        ]
    )
    df["_ingest_ts"] = datetime.now(timezone.utc).isoformat()

    label = date_str.replace("-", "_")[:7]
    out_path = BRONZE_PATH / "dict_participantes" / f"dict_participantes_{label}.parquet"
    _save_parquet(df, out_path)
    return df


def ingest_dict_chaves_participante(rows: list[dict], date_str: str) -> pd.DataFrame:
    """
    Estoque de chaves PIX por participante (market share de chaves por banco).

    Derivado de ChavesPix agregando qtdChaves por (ISPB, Nome).
    Dataset parcialmente redundante com ingest_ranking.py, mantido para a
    camada Bronze seguir isolada e autocontida.
    """
    print("  → Agregando chaves por participante (ISPB)...")
    agg: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows:
        key = (r.get("ISPB", ""), r.get("Nome", "").strip())
        agg[key] += int(r.get("qtdChaves", 0) or 0)

    df = pd.DataFrame(
        [
            {
                "Data": date_str,
                "ISPB": ispb,
                "Nome": nome,
                "qtdChaves": qtd,
            }
            for (ispb, nome), qtd in sorted(agg.items(), key=lambda kv: -kv[1])
        ]
    )
    df["_ingest_ts"] = datetime.now(timezone.utc).isoformat()

    label = date_str.replace("-", "_")[:7]
    out_path = BRONZE_PATH / "dict_chaves_participante" / f"dict_chaves_part_{label}.parquet"
    _save_parquet(df, out_path)
    return df


if __name__ == "__main__":
    print("🔄 Iniciando ingestão Bronze — DICT (via ChavesPix)")
    print()

    latest = find_latest_available()
    if not latest:
        print("✗ Nenhum snapshot de ChavesPix disponível nas últimas tentativas.")
        print("  A ingestão DICT será pulada — o pipeline continua com as")
        print("  demais fontes (SPI, usuários, fraudes, municípios, ranking).")
        sys.exit(0)

    date_str, rows = latest
    print(f"  ✓ Snapshot mais recente: {date_str} ({len(rows):,} linhas)")
    print()

    ingest_dict_chaves_tipo(rows, date_str)
    print()
    ingest_dict_participantes(rows, date_str)
    print()
    ingest_dict_chaves_participante(rows, date_str)

    print()
    print("✅ Ingestão Bronze DICT concluída.")
