"""
PIX Observatory — Ranking de cidades + mapa de calor por estado (PIX)
=====================================================================
Fonte: BACEN Olinda API, function import `TransacoesPixPorMunicipio`.

Notas de integração (mesmo padrão descoberto em ingest_ranking.py):
    1. O parâmetro da function (`DataBase='YYYYMM'`) por si só não filtra
       — é preciso `$filter=AnoMes eq YYYYMM` (campo real é AnoMes, inteiro
       no formato YYYYMM, não Data como em ChavesPix).
    2. `$skip` retorna 500 (sem paginação via skip). Existem ~5.570
       municípios brasileiros — muito mais que o limite de 1000 linhas
       por chamada. Não é possível obter o dataset completo.
    3. Mitigação: ordenar por `$orderby=VL_PagadorPF desc` garante que as
       maiores cidades (que dominam TODAS as colunas de valor simultaneamente,
       dado a concentração econômica do Brasil) apareçam no topo — seguro
       para "top 10/15 cidades", não seguro para ranking completo/cauda longa.

Mapa de calor por estado (UF):
    Agregamos as mesmas ~1000 linhas (já ordenadas pelas maiores cidades)
    por estado. Isso é uma APROXIMAÇÃO — não é o total real de cada estado,
    é a soma das cidades desse estado que apareceram na amostra das maiores
    do país. Estados pequenos podem não ter nenhuma cidade na amostra — são
    marcados explicitamente com `amostra_insuficiente: true`, nunca tratados
    como zero real. Os níveis de calor (0-4) usam escala logarítmica, pois a
    distribuição é extremamente concentrada (São Paulo >> qualquer outro).

Uso:
    python ingestion/ingest_municipios.py

Saída:
    data/bronze/transacoes_municipio/transacoes_municipio_{YYYYMM}.parquet
    data/gold/pix_municipios.json
    assets/data/pix_municipios.json   (consumido pelo frontend em runtime)
"""

import json
import math
import sys
from pathlib import Path
from datetime import date, datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/TransacoesPixPorMunicipio"
BRONZE = Path("data/bronze/transacoes_municipio")
GOLD = Path("data/gold")
FRONTEND_OUT = Path("assets/data/pix_municipios.json")

TOP_N = 10          # tamanho do ranking de cidades exibido
CITIES_PER_UF = 8   # cidades por estado guardadas para o painel de drill-down
TIMEOUT = 60

# Nome do estado (como vem do BACEN, ex: "SÃO PAULO") → sigla UF.
# Fixo — são sempre as 27 unidades federativas do Brasil.
ESTADO_PARA_UF = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPÁ": "AP", "AMAZONAS": "AM",
    "BAHIA": "BA", "CEARÁ": "CE", "DISTRITO FEDERAL": "DF",
    "ESPÍRITO SANTO": "ES", "GOIÁS": "GO", "MARANHÃO": "MA",
    "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS", "MINAS GERAIS": "MG",
    "PARÁ": "PA", "PARAÍBA": "PB", "PARANÁ": "PR", "PERNAMBUCO": "PE",
    "PIAUÍ": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS", "RONDÔNIA": "RO", "RORAIMA": "RR",
    "SANTA CATARINA": "SC", "SÃO PAULO": "SP", "SERGIPE": "SE",
    "TOCANTINS": "TO",
}
def _titlecase_pt(nome: str) -> str:
    """Title case respeitando partículas minúsculas do português (de/do/da...)."""
    minusculas = {"de", "do", "da", "dos", "das"}
    palavras = nome.lower().split(" ")
    return " ".join(p if p in minusculas else p.capitalize() for p in palavras)


UF_PARA_NOME = {v: _titlecase_pt(k) for k, v in ESTADO_PARA_UF.items()}
# Correções de acentuação que _titlecase_pt não resolve (capitalize() tira acento? não,
# preserva — mas alguns nomes do BACEN vêm sem o acento correto; força a grafia oficial).
UF_PARA_NOME.update({
    "AP": "Amapá", "CE": "Ceará", "ES": "Espírito Santo", "GO": "Goiás",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PI": "Piauí",
    "RN": "Rio Grande do Norte", "RO": "Rondônia", "SP": "São Paulo",
    "MA": "Maranhão",
})


def _anomes(d: date) -> str:
    """Formata uma data como AnoMes (YYYYMM), formato usado por este endpoint."""
    return f"{d.year}{d.month:02d}"


def _shift_months(d: date, months: int) -> date:
    total = d.year * 12 + (d.month - 1) - months
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


def _fetch_month(anomes: str) -> list[dict]:
    """Busca o ranking de municípios para um AnoMes (YYYYMM) específico."""
    url = (
        f"{BASE_URL}(DataBase=%27{anomes}%27)?$format=json&$top=1000"
        f"&$filter=AnoMes%20eq%20{anomes}&$orderby=VL_PagadorPF%20desc"
    )
    req = Request(url, headers={"User-Agent": "pix-observatory/1.0"})
    with urlopen(req, timeout=TIMEOUT) as resp:
        data = json.load(resp)
    rows = data.get("value", [])
    anomes_found = {str(r.get("AnoMes")) for r in rows}
    if anomes_found and anomes_found != {anomes}:
        print(f"  ⚠ Aviso: filtro pode ter falhado para {anomes} (encontrado: {anomes_found})")
    return rows


def _find_latest_available(max_attempts: int = 4) -> tuple[str, list[dict]] | None:
    candidate = date.today()
    for _ in range(max_attempts):
        anomes = _anomes(candidate)
        try:
            rows = _fetch_month(anomes)
        except (URLError, HTTPError, TimeoutError) as e:
            print(f"  ✗ {anomes} falhou: {e}")
            rows = []
        if rows:
            return anomes, rows
        candidate = _shift_months(candidate, 1)
    return None


def _save_bronze(rows: list[dict], anomes: str) -> None:
    try:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        print("  ⚠ pandas/pyarrow indisponíveis — pulando bronze.")
        return

    df = pd.DataFrame(rows)
    df["_ingest_ts"] = datetime.now(timezone.utc).isoformat()
    BRONZE.mkdir(parents=True, exist_ok=True)
    out_path = BRONZE / f"transacoes_municipio_{anomes}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    print(f"  ✓ {out_path} ({len(df):,} linhas)")


def _compute_heat_levels(valores: dict[str, float]) -> dict[str, int]:
    """
    Bucketiza valores em níveis 0-4 usando escala logarítmica — a
    distribuição de valor por estado é extremamente concentrada (São Paulo
    pode ser 100x+ maior que estados pequenos), então quantis lineares
    deixariam quase tudo no nível mínimo. log10 espalha melhor os buckets.
    Estados com valor 0 (amostra insuficiente) ficam no nível -1 (sem dado).
    """
    positivos = {uf: v for uf, v in valores.items() if v > 0}
    if not positivos:
        return {uf: -1 for uf in valores}

    logs = {uf: math.log10(v) for uf, v in positivos.items()}
    lo, hi = min(logs.values()), max(logs.values())
    span = hi - lo if hi > lo else 1.0

    niveis: dict[str, int] = {}
    for uf, v in valores.items():
        if v <= 0:
            niveis[uf] = -1
            continue
        frac = (logs[uf] - lo) / span  # 0..1
        nivel = min(4, max(0, int(frac * 4 + 0.5)))
        niveis[uf] = nivel
    return niveis


def build_ranking() -> dict:
    print("→ Buscando snapshot mais recente disponível...")
    latest = _find_latest_available()
    if not latest:
        raise RuntimeError("Nenhum snapshot de TransacoesPixPorMunicipio disponível.")
    anomes, rows = latest
    print(f"  ✓ Snapshot mais recente: {anomes} ({len(rows)} linhas)")
    _save_bronze(rows, anomes)

    # Processa TODAS as linhas da amostra (não só o top N) — usadas tanto
    # para o ranking de cidades quanto para a agregação por estado.
    processadas = []
    for r in rows:
        pago = float(r.get("VL_PagadorPF", 0) or 0) + float(r.get("VL_PagadorPJ", 0) or 0)
        recebido = float(r.get("VL_RecebedorPF", 0) or 0) + float(r.get("VL_RecebedorPJ", 0) or 0)
        estado_nome = r.get("Estado", "").strip()
        processadas.append({
            "municipio": r.get("Municipio", "").strip(),
            "estado": estado_nome,
            "uf": ESTADO_PARA_UF.get(estado_nome.upper(), ""),
            "regiao": r.get("Regiao", "").strip(),
            "valor_pago": round(pago, 2),
            "valor_recebido": round(recebido, 2),
        })

    # ── Ranking nacional de cidades (reordenado pelo valor combinado) ──
    candidatas = sorted(processadas, key=lambda c: -c["valor_pago"])
    ranking = [{"rank": i + 1, **c} for i, c in enumerate(candidatas[:TOP_N])]

    # ── Agregação por estado (soma das cidades da amostra em cada UF) ──
    valor_por_uf: dict[str, float] = {uf: 0.0 for uf in UF_PARA_NOME}
    cidades_por_uf: dict[str, list[dict]] = {uf: [] for uf in UF_PARA_NOME}
    for c in processadas:
        uf = c["uf"]
        if not uf:
            continue
        valor_por_uf[uf] += c["valor_pago"]
        cidades_por_uf[uf].append(c)

    niveis = _compute_heat_levels(valor_por_uf)

    estados = []
    for uf, nome in sorted(UF_PARA_NOME.items()):
        cidades_uf = sorted(cidades_por_uf[uf], key=lambda c: -c["valor_pago"])[:CITIES_PER_UF]
        estados.append({
            "uf": uf,
            "nome": nome,
            "valor_pago": round(valor_por_uf[uf], 2),
            "nivel": niveis[uf],
            "amostra_insuficiente": valor_por_uf[uf] <= 0,
            "cidades": [
                {"municipio": c["municipio"], "valor_pago": c["valor_pago"]}
                for c in cidades_uf
            ],
        })

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "BACEN Olinda API — Pix_DadosAbertos / TransacoesPixPorMunicipio",
        "metodologia": "Ordenado por valor pago por pessoas físicas (VL_PagadorPF desc). "
                        "Não é o dataset completo (~5.570 municípios) — a API não pagina "
                        "além de 1000 linhas — mas é seguro para o top 10/15 cidades, dado "
                        "que as maiores dominam todas as colunas de valor simultaneamente. "
                        "A agregação por estado é a soma das cidades desse estado presentes "
                        "na amostra — estados pequenos podem aparecer com amostra_insuficiente.",
        "anomes": anomes,
        "ranking": ranking,
        "estados": estados,
    }


def main() -> int:
    payload = build_ranking()

    GOLD.mkdir(parents=True, exist_ok=True)
    gold_path = GOLD / "pix_municipios.json"
    gold_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {gold_path}")

    FRONTEND_OUT.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {FRONTEND_OUT}")

    print()
    top3 = [f"{r['municipio']}/{r['estado']}" for r in payload["ranking"][:3]]
    print(f"Top 3 cidades: {top3}")

    return 0


if __name__ == "__main__":
    print("🏙️  Construindo ranking de cidades PIX")
    print()
    sys.exit(main())
