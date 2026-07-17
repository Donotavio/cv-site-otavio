"""
Observatório Eleições 2026 — Deflator IPCA do Fundo Eleitoral
=============================================================
Responde, com fonte oficial e de forma reprodutível, à pergunta:
o salto do Fundo Especial de Financiamento de Campanha (FEFC) de 2018 → 2026
apenas acompanhou a inflação, ou cresceu acima dela?

- Lê os valores curados do fundo em `assets/data/eleicoes_contexto.json`
  (`fundo_eleitoral.valor_rs` = 2026, `ref_2018_rs` = 2018). NÃO hardcoda
  valores de fundo aqui — o contexto continua sendo a fonte única curada.
- Puxa o IPCA (variação % mensal, série 433 do BACEN SGS) via API REST pública
  (só `requests` — sem adicionar deps ao sub-projeto de eleições).
- Deflaciona o fundo de 2018 para reais do último mês publicado e calcula o
  múltiplo REAL (vs. o múltiplo nominal de ~2,9×).
- Escreve o companion `assets/data/eleicoes_fundo_ipca.json`, consumido por
  fetch em runtime pela seção [09] do painel. O contexto curado fica intacto.

Uso:
    python transform_eleicoes/gold_fundo_ipca.py

Fail-soft: se a API do BACEN falhar ou o contexto não tiver o fundo, sai com
código 0 SEM sobrescrever o JSON existente (a seção degrada para só o nominal).
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

FRONTEND_DIR = Path("assets/data")
CONTEXTO = FRONTEND_DIR / "eleicoes_contexto.json"
OUT_JSON = FRONTEND_DIR / "eleicoes_fundo_ipca.json"

# BACEN SGS — IPCA, variação % no mês. Mesmo código do catálogo do Brasil
# Cockpit (ingestion_macro/catalog.py: SGS_SERIES["ipca_mensal"] = 433).
SGS_IPCA_MENSAL = 433
SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
# Base da correção: o FEFC de 2018 é tratado como reais de jan/2018 (início do
# ciclo eleitoral). Documentado no envelope; ~4% de folga vs. escolher out/2018.
BASE_INICIAL = "01/01/2018"
FONTE = "Banco Central do Brasil — SGS série 433 (IPCA, variação % mensal)"
FONTE_URL = "https://www3.bcb.gov.br/sgspub/consultarvalores/telaCvsSelecionarSeries.paint?method=consultarSeries&codigoSerie=433"


def _fetch_ipca_mensal() -> list[dict]:
    """Série 433 de jan/2018 até hoje: [{'data': 'DD/MM/YYYY', 'valor': '0.29'}, ...]."""
    hoje = date.today().strftime("%d/%m/%Y")
    resp = requests.get(
        SGS_URL.format(code=SGS_IPCA_MENSAL),
        params={"formato": "json", "dataInicial": BASE_INICIAL, "dataFinal": hoje},
        timeout=30,
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    print("🗳  Observatório Eleições 2026 — deflator IPCA do Fundo Eleitoral")

    if not CONTEXTO.exists():
        print(f"  ✗ {CONTEXTO} não encontrado — nada a fazer.")
        return 0
    fundo = json.loads(CONTEXTO.read_text(encoding="utf-8")).get("fundo_eleitoral", {})
    v2026 = fundo.get("valor_rs")
    v2018 = fundo.get("ref_2018_rs")
    if not v2026 or not v2018:
        print("  ✗ fundo_eleitoral.valor_rs / ref_2018_rs ausentes no contexto — pulando.")
        return 0

    try:
        serie = _fetch_ipca_mensal()
    except Exception as e:  # noqa: BLE001 — fail-soft: preserva o JSON existente
        print(f"  ✗ BACEN SGS indisponível ({e}) — mantendo {OUT_JSON.name} atual.")
        return 0
    if not serie:
        print("  ✗ série 433 vazia — mantendo JSON atual.")
        return 0

    fator = 1.0
    for pt in serie:
        try:
            fator *= 1 + float(pt["valor"]) / 100.0
        except (KeyError, ValueError, TypeError):
            continue

    ref_mes_br = serie[-1]["data"]            # 'DD/MM/YYYY' do último ponto
    ref_ano = int(ref_mes_br.split("/")[-1])
    ref_ym = f"{ref_ano}-{ref_mes_br.split('/')[1]}"

    corrigido = round(v2018 * fator)
    mult_nominal = round(v2026 / v2018, 1)
    mult_real = round(v2026 / corrigido, 1)
    acumulado_pct = round((fator - 1) * 100, 1)
    acima_pct = round((v2026 / corrigido - 1) * 100)   # % acima da inflação

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "indice": "IPCA",
        "base": "2018",
        "ref_ano": ref_ano,
        "ref_mes": ref_ym,
        "ipca_acumulado_pct": acumulado_pct,
        "ref_2018_rs": v2018,
        "ref_2018_corrigido_rs": corrigido,
        "valor_2026_rs": v2026,
        "multiplo_nominal": mult_nominal,
        "multiplo_real": mult_real,
        "acima_inflacao_pct": acima_pct,
        "fonte": FONTE,
        "fonte_url": FONTE_URL,
    }

    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"  ✓ IPCA acum. jan/2018→{ref_ym}: +{acumulado_pct}% · "
        f"R$ {v2018/1e9:.2f} bi → R$ {corrigido/1e9:.2f} bi (R$ de {ref_ano})"
    )
    print(f"  ✓ múltiplo nominal {mult_nominal}× · real {mult_real}× (+{acima_pct}% acima da inflação)")
    print(f"  ✓ {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
