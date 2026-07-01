"""
PIX Observatory — Ranking de instituições por chaves PIX (DICT)
=================================================================
Fonte real: BACEN Olinda API, serviço Pix_DadosAbertos, function import
`ChavesPix(Data='YYYY-MM-DD')`. Retorna o estoque de chaves PIX cadastradas
por instituição (ISPB/Nome), tipo de chave e natureza do usuário, para um
snapshot de fechamento de mês.

IMPORTANTE — o que este ranking representa (e o que NÃO representa):
    O BACEN não publica volume ou valor financeiro transacionado por
    instituição na API aberta — esse dado é agregado (só o total do
    sistema, ver ingest_spi.py). O que existe publicamente é o estoque de
    CHAVES PIX cadastradas por instituição, que usamos aqui como proxy de
    base de usuários/adoção — não de volume transacionado.

Descobertas de integração (documentadas para futura manutenção):
    1. A function `ChavesPix` exige o parâmetro `Data` na própria URL
       (sintaxe de function-call OData: `ChavesPix(Data='YYYY-MM-DD')`),
       mas esse parâmetro por si só NÃO filtra o resultado — a API ignora
       silenciosamente e devolve linhas de múltiplos meses misturadas.
    2. É necessário adicionar TAMBÉM um `$filter=Data eq YYYY-MM-DD`
       (sem aspas, espaço como %20) para filtrar corretamente ao mês.
    3. `$skip` retorna 500 nesta function-composable — não há paginação
       via skip. `$top=1000` + `$orderby=qtdChaves desc` é a estratégia
       usada: como o objetivo é rankear os MAIORES participantes, ordenar
       por qtdChaves desc garante que os líderes apareçam sempre dentro do
       top 1000 linhas (mesmo que a cauda longa de cooperativas pequenas
       fique de fora — irrelevante para este ranking).

Uso:
    python ingestion/ingest_ranking.py

Saída:
    data/bronze/chaves_pix_participante/chaves_pix_{YYYY_MM}.parquet  (×2 meses)
    data/gold/pix_ranking_participantes.parquet
    assets/data/pix_ranking.json   (consumido pelo frontend em runtime)
"""

import json
import sys
import calendar
from pathlib import Path
from collections import defaultdict
from datetime import date, datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/ChavesPix"
BRONZE = Path("data/bronze/chaves_pix_participante")
GOLD = Path("data/gold")
FRONTEND_OUT = Path("assets/data/pix_ranking.json")

TOP_N = 10               # tamanho de cada ranking exibido
MONTHS_BACK_COMPARE = 3  # janela de comparação para "últimos meses"
TIMEOUT = 60


def _month_end(d: date) -> date:
    """Retorna a data do último dia do mês de `d`."""
    last_day = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last_day)


def _shift_months(d: date, months: int) -> date:
    """Desloca `d` em `months` meses (pode ser negativo) e normaliza p/ fim do mês."""
    total = d.year * 12 + (d.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    return _month_end(date(year, month, 1))


def _fetch_month(date_str: str) -> list[dict]:
    """
    Busca o snapshot de um mês específico (ver notas de integração no
    docstring do módulo — Data no path + $filter são ambos necessários).
    """
    url = (
        f"{BASE_URL}(Data=%27{date_str}%27)?$format=json&$top=1000"
        f"&$filter=Data%20eq%20{date_str}&$orderby=qtdChaves%20desc"
    )
    req = Request(url, headers={"User-Agent": "pix-observatory/1.0"})
    with urlopen(req, timeout=TIMEOUT) as resp:
        data = json.load(resp)
    rows = data.get("value", [])
    # Validação defensiva: confirma que o filtro realmente funcionou
    # (proteção contra regressão silenciosa da API — ver nota 2 do docstring).
    dates_found = {r.get("Data") for r in rows}
    if dates_found and dates_found != {date_str}:
        print(f"  ⚠ Aviso: filtro de data pode ter falhado para {date_str} "
              f"(datas encontradas: {dates_found})")
    return rows


def _aggregate(rows: list[dict]) -> dict[tuple[str, str], int]:
    """Agrega qtdChaves por (ISPB, Nome), somando natureza/tipo de chave."""
    agg: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows:
        key = (r.get("ISPB", ""), r.get("Nome", "").strip())
        agg[key] += int(r.get("qtdChaves", 0) or 0)
    return agg


def _find_latest_available(max_attempts: int = 4) -> tuple[str, list[dict]] | None:
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


def _save_bronze(rows: list[dict], date_str: str) -> None:
    """Salva o snapshot bruto em Parquet (bronze)."""
    try:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        print("  ⚠ pandas/pyarrow indisponíveis — pulando gravação bronze.")
        return

    df = pd.DataFrame(rows)
    df["_ingest_ts"] = datetime.now(timezone.utc).isoformat()
    BRONZE.mkdir(parents=True, exist_ok=True)
    label = date_str.replace("-", "_")
    out_path = BRONZE / f"chaves_pix_{label}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    print(f"  ✓ {out_path} ({len(df):,} linhas)")


def build_ranking() -> dict:
    """
    Monta os dois rankings (histórico + últimos meses) e retorna o payload
    completo, já pronto para serialização.
    """
    print("→ Buscando snapshot mais recente disponível...")
    latest = _find_latest_available()
    if not latest:
        raise RuntimeError("Nenhum snapshot de ChavesPix disponível nas últimas tentativas.")
    latest_date_str, latest_rows = latest
    print(f"  ✓ Snapshot mais recente: {latest_date_str} ({len(latest_rows)} linhas)")
    _save_bronze(latest_rows, latest_date_str)

    latest_date = date.fromisoformat(latest_date_str)
    past_date = _shift_months(latest_date, MONTHS_BACK_COMPARE)
    past_date_str = past_date.isoformat()

    print(f"→ Buscando snapshot de comparação ({MONTHS_BACK_COMPARE} meses antes: {past_date_str})...")
    try:
        past_rows = _fetch_month(past_date_str)
    except (URLError, HTTPError, TimeoutError) as e:
        print(f"  ✗ {past_date_str} falhou: {e} — ranking de crescimento ficará vazio.")
        past_rows = []
    if past_rows:
        _save_bronze(past_rows, past_date_str)
        print(f"  ✓ Snapshot de comparação: {past_date_str} ({len(past_rows)} linhas)")

    recent_agg = _aggregate(latest_rows)
    past_agg = _aggregate(past_rows) if past_rows else {}

    # ── Ranking histórico: estoque atual de chaves (medida acumulada) ──
    historico_sorted = sorted(recent_agg.items(), key=lambda kv: -kv[1])[:TOP_N]
    historico = [
        {"rank": i + 1, "ispb": ispb, "nome": nome, "chaves": qtd}
        for i, ((ispb, nome), qtd) in enumerate(historico_sorted)
    ]

    # ── Ranking recente: maior crescimento absoluto no período ─────────
    growth = []
    for key, qtd_now in recent_agg.items():
        qtd_before = past_agg.get(key)
        if qtd_before and qtd_before > 0:
            delta = qtd_now - qtd_before
            pct = round((delta / qtd_before) * 100, 1)
            growth.append((key, qtd_now, qtd_before, delta, pct))

    growth_sorted = sorted(growth, key=lambda x: -x[3])[:TOP_N]
    recentes = [
        {
            "rank": i + 1,
            "ispb": ispb,
            "nome": nome,
            "chaves_atual": now,
            "chaves_anterior": before,
            "crescimento_absoluto": delta,
            "crescimento_pct": pct,
        }
        for i, ((ispb, nome), now, before, delta, pct) in enumerate(growth_sorted)
    ]

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "BACEN Olinda API — Pix_DadosAbertos / ChavesPix (DICT)",
        "metrica": "Estoque de chaves PIX cadastradas por instituição "
                   "(proxy de adoção — BACEN não publica volume/valor "
                   "transacionado por instituição na API aberta)",
        "snapshot_recente": latest_date_str,
        "snapshot_comparacao": past_date_str if past_rows else None,
        "historico": historico,
        "recente": recentes,
    }


def main() -> int:
    payload = build_ranking()

    GOLD.mkdir(parents=True, exist_ok=True)
    gold_json = GOLD / "pix_ranking_participantes.json"
    gold_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {gold_json}")

    # Tenta também salvar em Parquet (gold) para consistência com o resto do pipeline
    try:
        import pandas as pd
        pd.DataFrame(payload["historico"]).to_parquet(
            GOLD / "pix_ranking_historico.parquet", index=False
        )
        if payload["recente"]:
            pd.DataFrame(payload["recente"]).to_parquet(
                GOLD / "pix_ranking_recente.parquet", index=False
            )
        print(f"  ✓ {GOLD}/pix_ranking_*.parquet")
    except ImportError:
        print("  ⚠ pandas indisponível — pulando gravação Parquet gold.")

    # Copia para assets/data/ — é isso que o frontend consome em runtime
    # (mesmo padrão de fetch_news.py → pix_news.json).
    FRONTEND_OUT.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {FRONTEND_OUT}")

    print()
    print(f"Top 3 histórico: {[h['nome'] for h in payload['historico'][:3]]}")
    if payload["recente"]:
        print(f"Top 3 crescimento: {[r['nome'] for r in payload['recente'][:3]]}")

    return 0


if __name__ == "__main__":
    print("🏆 Construindo ranking de instituições PIX (chaves DICT)")
    print()
    sys.exit(main())
