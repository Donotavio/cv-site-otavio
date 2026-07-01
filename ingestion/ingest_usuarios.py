"""
PIX Observatory — Usuários cadastrados no PIX (série histórica real)
======================================================================
Fonte: BACEN Olinda API, entidade `PixUsuariosCadastradosDICT`.

Diferente dos outros endpoints do Pix_DadosAbertos, esta entidade NÃO é
uma function-import parametrizada — é um entity set direto, e uma única
chamada retorna o HISTÓRICO COMPLETO desde o lançamento do PIX (nov/2020)
até o mês mais recente disponível. Não precisa de paginação nem de
lógica de "mês mais recente" — o próprio dataset é pequeno (~67 linhas).

Uso:
    python ingestion/ingest_usuarios.py

Saída:
    data/bronze/usuarios_dict/usuarios_dict.parquet
    data/gold/pix_usuarios.json
    assets/data/pix_usuarios.json   (consumido pelo frontend em runtime)
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).parent.parent))

URL = (
    "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/"
    "PixUsuariosCadastradosDICT?$format=json&$orderby=DataGraficosPix%20asc&$top=1000"
)

BRONZE = Path("data/bronze/usuarios_dict")
GOLD = Path("data/gold")
FRONTEND_OUT = Path("assets/data/pix_usuarios.json")
TIMEOUT = 60


def fetch_series() -> list[dict]:
    """Busca a série histórica completa de usuários cadastrados no DICT."""
    req = Request(URL, headers={"User-Agent": "pix-observatory/1.0"})
    with urlopen(req, timeout=TIMEOUT) as resp:
        data = json.load(resp)
    return data.get("value", [])


def build_payload(rows: list[dict]) -> dict:
    """
    Monta o payload com a série completa + KPIs derivados (crescimento
    total, fator multiplicador desde o lançamento).
    """
    if not rows:
        raise RuntimeError("PixUsuariosCadastradosDICT não retornou dados.")

    rows_sorted = sorted(rows, key=lambda r: r["DataGraficosPix"])
    primeiro = rows_sorted[0]
    ultimo = rows_sorted[-1]

    total_inicial = primeiro["qtdUsuariosCadastradosDICTTotal"]
    total_atual = ultimo["qtdUsuariosCadastradosDICTTotal"]
    fator = round(total_atual / total_inicial, 2) if total_inicial else None

    serie = [
        {
            "data": r["DataGraficosPix"],
            "pf": r["qtdUsuariosPessoaFisica"],
            "pj": r["qtdUsuariosPessoaJuridica"],
            "total": r["qtdUsuariosCadastradosDICTTotal"],
        }
        for r in rows_sorted
    ]

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "BACEN Olinda API — Pix_DadosAbertos / PixUsuariosCadastradosDICT",
        "primeiro_mes": primeiro["DataGraficosPix"],
        "ultimo_mes": ultimo["DataGraficosPix"],
        "usuarios_pf_atual": ultimo["qtdUsuariosPessoaFisica"],
        "usuarios_pj_atual": ultimo["qtdUsuariosPessoaJuridica"],
        "usuarios_total_atual": total_atual,
        "usuarios_total_inicial": total_inicial,
        "fator_crescimento": fator,
        "serie_mensal": serie,
    }


def main() -> int:
    print("→ Buscando série histórica de usuários cadastrados (DICT)...")
    try:
        rows = fetch_series()
    except (URLError, HTTPError, TimeoutError) as e:
        print(f"  ✗ Falha: {e}")
        return 1

    print(f"  ✓ {len(rows)} meses recebidos")
    payload = build_payload(rows)

    # Bronze
    try:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq

        df = pd.DataFrame(rows)
        df["_ingest_ts"] = datetime.now(timezone.utc).isoformat()
        BRONZE.mkdir(parents=True, exist_ok=True)
        out_path = BRONZE / "usuarios_dict.parquet"
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
        print(f"  ✓ {out_path}")
    except ImportError:
        print("  ⚠ pandas/pyarrow indisponíveis — pulando bronze.")

    # Gold + frontend
    GOLD.mkdir(parents=True, exist_ok=True)
    gold_path = GOLD / "pix_usuarios.json"
    gold_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {gold_path}")

    FRONTEND_OUT.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {FRONTEND_OUT}")

    print()
    print(f"Usuários hoje: {payload['usuarios_total_atual']:,} "
          f"(PF: {payload['usuarios_pf_atual']:,} · PJ: {payload['usuarios_pj_atual']:,})")
    print(f"Crescimento desde {payload['primeiro_mes']}: {payload['fator_crescimento']}×")

    return 0


if __name__ == "__main__":
    print("👥 Coletando usuários cadastrados no PIX (DICT)")
    print()
    sys.exit(main())
