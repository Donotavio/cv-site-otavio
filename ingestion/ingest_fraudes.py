"""
PIX Observatory — Estatísticas de fraude e o MED (Mecanismo Especial de
Devolução)
=====================================================================
Fonte: BACEN Olinda API, function import `EstatisticasFraudesPix`.

Diferente dos outros endpoints deste projeto, esta entidade retorna UMA
ÚNICA LINHA por mês — é um agregado nacional já pronto, publicado
diretamente pelo BACEN. Não há risco de amostragem/truncamento (ao
contrário de ChavesPix ou TransacoesPixPorMunicipio): o número aqui é
exato, não um proxy nem uma estimativa.

Publicado com defasagem maior que outros datasets do PIX — por isso a
busca tenta vários meses até achar o mais recente disponível.

Uso:
    python ingestion/ingest_fraudes.py

Saída:
    data/bronze/fraudes_pix/fraudes_pix_{YYYYMM}.parquet
    data/gold/pix_fraudes.json
    assets/data/pix_fraudes.json   (consumido pelo frontend em runtime)
"""

import json
import sys
from pathlib import Path
from datetime import date, datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/EstatisticasFraudesPix"
BRONZE = Path("data/bronze/fraudes_pix")
GOLD = Path("data/gold")
FRONTEND_OUT = Path("assets/data/pix_fraudes.json")
TIMEOUT = 60


def _anomes(d: date) -> str:
    return f"{d.year}{d.month:02d}"


def _shift_months(d: date, months: int) -> date:
    total = d.year * 12 + (d.month - 1) - months
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


def _fetch_month(anomes: str) -> dict | None:
    url = (
        f"{BASE_URL}(Database=%27{anomes}%27)?$format=json"
        f"&$filter=AnoMes%20eq%20{anomes}&$top=5"
    )
    req = Request(url, headers={"User-Agent": "pix-observatory/1.0"})
    with urlopen(req, timeout=TIMEOUT) as resp:
        data = json.load(resp)
    rows = data.get("value", [])
    return rows[0] if rows else None


def _find_latest_available(max_attempts: int = 6) -> tuple[str, dict] | None:
    """Publicação de fraudes tem mais defasagem — tenta até 6 meses atrás."""
    candidate = date.today()
    for _ in range(max_attempts):
        anomes = _anomes(candidate)
        try:
            row = _fetch_month(anomes)
        except (URLError, HTTPError, TimeoutError) as e:
            print(f"  ✗ {anomes} falhou: {e}")
            row = None
        if row:
            return anomes, row
        candidate = _shift_months(candidate, 1)
    return None


def build_payload(anomes: str, row: dict) -> dict:
    """
    Reorganiza os campos brutos do BACEN em uma estrutura semântica,
    separando: contestações, devoluções via MED, e bloqueios cautelares.
    """
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "BACEN Olinda API — Pix_DadosAbertos / EstatisticasFraudesPix",
        "anomes": anomes,
        "contestacoes": {
            "total": int(row.get("QtdePixcontestados", 0) or 0),
            "aceitas": int(row.get("Qtdecontestacoesaceitas", 0) or 0),
            "rejeitadas": int(row.get("Qtdecontestacoesrejeitadas", 0) or 0),
            "aceitas_por_100mil": float(row.get("Qtdecontestacoesaceitasacada100mil", 0) or 0),
            "valor_aceitas": float(row.get("ValorPixcontestadosaceitos", 0) or 0),
        },
        "usuarios_marcados_fraude": int(row.get("QtdeUsuarioscommarcacoesdefraude", 0) or 0),
        "chaves_marcadas_fraude": int(row.get("QtdeChavesPixcommarcacoesdefraude", 0) or 0),
        "med": {
            "devolvido_integral_qtd": int(row.get("QuantidadedevolvidaintegralmentepormeiodoMED", 0) or 0),
            "devolvido_integral_valor": float(row.get("ValorPixdevolvidosintegralmente", 0) or 0),
            "devolvido_parcial_qtd": int(row.get("QuantidadedevolvidaparcialmentepormeiodoMED", 0) or 0),
            "devolvido_parcial_valor": float(row.get("ValorPixdevolvidosparcialmente", 0) or 0),
            "valor_residual_nao_devolvido": float(row.get("ValorPixresidualnaodevolvido", 0) or 0),
            "percentual_devolucao": float(row.get("PercentualdeDevolucao", 0) or 0),
        },
        "bloqueios_cautelares": {
            "liberados_qtd": int(row.get("QtdePixbloqueadoscautelarmenteeliberados", 0) or 0),
            "liberados_valor": float(row.get("ValorPixbloqueadoscautelarmenteeliberados", 0) or 0),
            "devolvidos_qtd": int(row.get("QtdePixbloqueadoscautelarmenteedevolvidos", 0) or 0),
            "devolvidos_valor": float(row.get("ValorPixbloqueadoscautelarmenteedevolvidos", 0) or 0),
        },
    }


def main() -> int:
    print("→ Buscando estatísticas de fraude mais recentes disponíveis...")
    latest = _find_latest_available()
    if not latest:
        print("  ✗ Nenhum snapshot de EstatisticasFraudesPix disponível.")
        return 1

    anomes, row = latest
    print(f"  ✓ Snapshot mais recente: {anomes}")

    # Bronze
    try:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq

        df = pd.DataFrame([row])
        df["_ingest_ts"] = datetime.now(timezone.utc).isoformat()
        BRONZE.mkdir(parents=True, exist_ok=True)
        out_path = BRONZE / f"fraudes_pix_{anomes}.parquet"
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
        print(f"  ✓ {out_path}")
    except ImportError:
        print("  ⚠ pandas/pyarrow indisponíveis — pulando bronze.")

    payload = build_payload(anomes, row)

    GOLD.mkdir(parents=True, exist_ok=True)
    gold_path = GOLD / "pix_fraudes.json"
    gold_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {gold_path}")

    FRONTEND_OUT.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {FRONTEND_OUT}")

    print()
    print(f"Contestações: {payload['contestacoes']['total']:,} · "
          f"Bloqueado cautelarmente: R$ {payload['bloqueios_cautelares']['liberados_valor']:,.2f} · "
          f"% devolução: {payload['med']['percentual_devolucao']}%")

    return 0


if __name__ == "__main__":
    print("🛡️  Coletando estatísticas de fraude e MED")
    print()
    sys.exit(main())
