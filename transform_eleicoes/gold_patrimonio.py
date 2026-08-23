"""
Observatório Eleições 2026 — Gold: patrimônio declarado (bens)
==================================================================
Lê o bronze de patrimônio (2026 + 2022, presidente/governador) e produz o
envelope da seção de patrimônio: total declarado por candidato em 2026,
comparação com 2022 quando o mesmo CPF concorreu nos dois anos (join por
CPF — o nome muda de grafia entre fontes, o CPF mascarado do TSE não).

Uso:
    python transform_eleicoes/gold_patrimonio.py
Saída:
    data/gold/eleicoes_patrimonio.parquet
    assets/data/eleicoes_patrimonio.json

Se o bronze vier vazio (download bloqueado nos dois anos), o JSON sai com
candidatos=[] — o frontend mostra o arcabouço + fontes, igual ao padrão já
usado em integridade. Idempotente.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    PATRIMONIO_ANO_ATUAL,
    PATRIMONIO_ANO_COMPARACAO,
    PATRIMONIO_DISCLAIMER,
    PATRIMONIO_FONTES,
    PATRIMONIO_METODOLOGIA,
)

BRONZE_DIR = Path("data/bronze/eleicoes_patrimonio")
GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")

# ── Composição por tipo de bem (aditivo) ────────────────────────────────────
# Complemento de 1 frase em cada texto curado do catálogo (o catálogo em si
# não muda — outro fluxo é dono dele). O frontend continua recebendo uma
# string única em `metodologia`/`disclaimer`.
METODOLOGIA_COMPOSICAO = (
    " A composição por tipo de bem agrupa a categoria declarada ao TSE "
    "(DS_TIPO_BEM_CANDIDATO) em famílias legíveis — imóveis, veículos, "
    "aplicações financeiras etc."
)
DISCLAIMER_COMPOSICAO = (
    " A composição usa o valor de aquisição autodeclarado de cada bem — o TSE "
    "não corrige pela inflação nem reavalia a preço de mercado."
)

# Mapeamento DS_TIPO_BEM_CANDIDATO (41 rótulos distintos no dado real de
# 2026, taxonomia herdada da declaração IRPF) → 6 categorias legíveis +
# "Outros". Casamento por palavra-chave sobre o rótulo normalizado (caixa
# alta, sem acento), com fronteira de palavra onde há risco de colisão.
# Verificado rótulo a rótulo contra o CSV real de bem_candidato_2026
# (roster presidente+governador):
#   Imóveis                   ← Apartamento · Casa · Terreno · Terra nua ·
#                               Sala ou conjunto · Loja · Galpão · Prédio
#                               residencial/comercial · Construção ·
#                               benfeitorias · "Outros bens imóveis"
#   Veículos                  ← "Veículo automotor terrestre: caminhão,
#                               automóvel, moto etc." · Aeronave · Embarcação
#   Aplicações financeiras    ← Aplicação de renda fixa (CDB, RDB…) ·
#                               Caderneta de poupança · Fundos (ações, curto/
#                               longo prazo, FII, FIDC…) · Ações · Ouro ·
#                               VGBL/PGBL · plano PAIT/pecúlio · "Outras
#                               aplicações e investimentos"
#   Participações societárias ← Quotas ou quinhões de capital · "Outras
#                               participações societárias"
#   Dinheiro e contas         ← Depósito bancário em conta corrente (País ou
#                               exterior) · Dinheiro em espécie (moeda
#                               nacional ou estrangeira) · "Outros depósitos
#                               à vista e numerário"
#   Créditos e consórcios     ← Consórcio não contemplado · Crédito
#                               decorrente de empréstimo/alienação · "Outros
#                               créditos e poupança vinculados"
#   Outros bens e direitos    ← resíduo (inclui o rótulo literal "OUTROS BENS
#                               E DIREITOS" do TSE, bem de atividade
#                               autônoma, outros bens móveis, joia/obra de
#                               arte, linha telefônica etc.)
CATEGORIA_OUTROS = "Outros bens e direitos"
# Ordem importa (regra mais específica primeiro). Armadilhas do dado real:
# "PARTICIPACOES" contém "ACOES"; "DIREITOS CREDITORIOS" (FIDC, que é fundo)
# contém "CREDITO" — por isso créditos casa só rótulos explícitos; e o plural
# "aplicações"/"participações" exige APLICAC/PARTICIPAC\w*.
_CATEGORIA_REGRAS: list[tuple[str, str]] = [
    (r"VEICULO|AERONAVE|EMBARCACA", "Veículos"),
    (
        r"APARTAMENTO|\bCASA\b|TERRENO|TERRA NUA|\bSALA\b|\bLOJA\b|GALPAO|PREDIO|IMOVE|BENFEITORIA|CONSTRUCAO",
        "Imóveis",
    ),
    (r"QUOTA|QUINH|PARTICIPAC\w* SOCIET", "Participações societárias"),
    (r"DEPOSITO|CONTA CORRENTE|DINHEIRO EM ESPECIE|NUMERARIO", "Dinheiro e contas"),
    (r"OUTROS CREDITOS|CREDITO DECORRENTE|CONSORCIO|EMPRESTIMO", "Créditos e consórcios"),
    (
        r"RENDA FIXA|POUPANCA|FUNDO|\bACOES\b|\bOURO\b|DEBENTURE|VGBL|PGBL|PREVIDENCIA|CRIPTO|APLICAC|TESOURO|PAIT|PECULIO",
        "Aplicações financeiras",
    ),
]


def _normalizar_rotulo(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto or "")
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", base).strip().upper()


def _categoria_bem(tipo_raw: str) -> str:
    rotulo = _normalizar_rotulo(tipo_raw)
    if not rotulo or rotulo.startswith("#N"):  # '#NULO'/'#NE' → sem tipo declarado
        return CATEGORIA_OUTROS
    for padrao, categoria in _CATEGORIA_REGRAS:
        if re.search(padrao, rotulo):
            return categoria
    return CATEGORIA_OUTROS


def _parse_tipos(row) -> list[dict]:
    """Lê `tipos_breakdown` (json) do bronze; [] se coluna ausente/corrompida
    (bronze anterior a esta feature continua funcionando)."""
    raw = row.get("tipos_breakdown") if hasattr(row, "get") else None
    if not isinstance(raw, str) or not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _latest_bronze() -> Path | None:
    files = sorted(BRONZE_DIR.glob("patrimonio_*.parquet"))
    return files[-1] if files else None


def _agg(df) -> dict:
    atual = {row["cpf"]: row for _, row in df[df["ano"] == PATRIMONIO_ANO_ATUAL].iterrows() if row.get("cpf")}
    comparacao = {
        row["cpf"]: row for _, row in df[df["ano"] == PATRIMONIO_ANO_COMPARACAO].iterrows() if row.get("cpf")
    }

    candidatos = []
    comp_valor: dict[str, float] = defaultdict(float)
    comp_n: dict[str, int] = defaultdict(int)
    rotulos_sem_regra: set[str] = set()
    for cpf, row in atual.items():
        prev = comparacao.get(cpf)

        # Composição por categoria (candidato + agregado do roster).
        cat_valor: dict[str, float] = defaultdict(float)
        for tb in _parse_tipos(row):
            valor = float(tb.get("valor_rs") or 0.0)
            categoria = _categoria_bem(tb.get("tipo") or "")
            if categoria == CATEGORIA_OUTROS and _normalizar_rotulo(tb.get("tipo") or ""):
                rotulos_sem_regra.add(tb.get("tipo") or "")
            cat_valor[categoria] += valor
            comp_valor[categoria] += valor
            comp_n[categoria] += int(tb.get("n") or 0)
        tipos_top = [
            {"tipo": c, "valor_rs": round(v, 2)}
            for c, v in sorted(cat_valor.items(), key=lambda kv: kv[1], reverse=True)[:3]
            if v > 0
        ]

        item = {
            "nome_urna": row["nome_urna"],
            "cargo": row["cargo"],
            "uf": row["uf"],
            "partido": row["partido"],
            "patrimonio_2026_rs": round(float(row["patrimonio_total_rs"]), 2),
            "n_bens_2026": int(row["n_bens"]),
            "tipos_top": tipos_top,
            "tem_comparacao": prev is not None,
        }
        if prev is not None and float(prev["patrimonio_total_rs"]) > 0:
            p2022 = float(prev["patrimonio_total_rs"])
            p2026 = float(row["patrimonio_total_rs"])
            item["patrimonio_2022_rs"] = round(p2022, 2)
            item["variacao_pct"] = round((p2026 - p2022) / p2022 * 100, 1)
        else:
            item["tem_comparacao"] = False
        candidatos.append(item)

    candidatos.sort(key=lambda c: c["patrimonio_2026_rs"], reverse=True)
    com_comparacao = [c for c in candidatos if c["tem_comparacao"]]
    maior_alta = sorted(com_comparacao, key=lambda c: c["variacao_pct"], reverse=True)[:5]
    maior_queda = sorted(com_comparacao, key=lambda c: c["variacao_pct"])[:5]

    # Agregado do roster: categorias em ordem de valor, "Outros" sempre por
    # último (é o resíduo, não uma categoria que disputa o topo).
    total_composicao = sum(comp_valor.values())
    ordem = sorted(
        (c for c in comp_valor if c != CATEGORIA_OUTROS), key=lambda c: comp_valor[c], reverse=True
    )
    if CATEGORIA_OUTROS in comp_valor:
        ordem.append(CATEGORIA_OUTROS)
    composicao_tipos = [
        {
            "tipo": c,
            "valor_rs": round(comp_valor[c], 2),
            "n": comp_n[c],
            "pct": round(comp_valor[c] / total_composicao * 100, 1) if total_composicao else 0.0,
        }
        for c in ordem
        if comp_n[c] > 0 or comp_valor[c] > 0
    ]
    if rotulos_sem_regra:
        # Diagnóstico p/ log de CI: rótulo novo do TSE caindo no resíduo.
        print(f"  · tipos de bem sem regra própria (foram p/ 'Outros'): {sorted(rotulos_sem_regra)}")

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "metodologia": PATRIMONIO_METODOLOGIA + METODOLOGIA_COMPOSICAO,
        "disclaimer": PATRIMONIO_DISCLAIMER + DISCLAIMER_COMPOSICAO,
        "fontes": PATRIMONIO_FONTES,
        "ano_atual": PATRIMONIO_ANO_ATUAL,
        "ano_comparacao": PATRIMONIO_ANO_COMPARACAO,
        "n_candidatos": len(candidatos),
        "n_com_comparacao": len(com_comparacao),
        "candidatos": candidatos,
        "maior_alta": maior_alta,
        "maior_queda": maior_queda,
        "composicao_tipos": composicao_tipos,
    }


def _vazio() -> dict:
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "metodologia": PATRIMONIO_METODOLOGIA + METODOLOGIA_COMPOSICAO,
        "disclaimer": PATRIMONIO_DISCLAIMER + DISCLAIMER_COMPOSICAO,
        "fontes": PATRIMONIO_FONTES,
        "ano_atual": PATRIMONIO_ANO_ATUAL,
        "ano_comparacao": PATRIMONIO_ANO_COMPARACAO,
        "n_candidatos": 0,
        "n_com_comparacao": 0,
        "candidatos": [],
        "maior_alta": [],
        "maior_queda": [],
        "composicao_tipos": [],
    }


def main() -> int:
    print("🗳  Observatório Eleições 2026 — gold de patrimônio declarado (bens)")
    bronze = _latest_bronze()
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    if bronze is None:
        print("  ✗ nenhum bronze de patrimônio — rode collect_patrimonio.py antes.")
        return 1

    import pandas as pd

    df = pd.read_parquet(bronze)
    payload = _agg(df) if not df.empty else _vazio()

    if not df.empty:
        df.drop(columns=[c for c in ("_ingest_ts",) if c in df.columns]).to_parquet(
            GOLD_DIR / "eleicoes_patrimonio.parquet", index=False
        )
    out_json = FRONTEND_DIR / "eleicoes_patrimonio.json"
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(
        f"  ✓ {out_json} ({payload['n_candidatos']} candidatos · "
        f"{payload['n_com_comparacao']} com comparação {PATRIMONIO_ANO_COMPARACAO}→{PATRIMONIO_ANO_ATUAL})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
