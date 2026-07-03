"""
Brasil Cockpit — Catálogo (fonte única de verdade)
====================================================
Define as séries do BACEN SGS, tabelas IBGE SIDRA, tickers de mercado (yfinance),
metadados de cada KPI e as metas/bandas usadas para computar status
(verde/amarelo/vermelho/neutro) e tendência.

TODOS os scripts (collect_*.py, silver, gold) importam daqui. Nunca hardcodar
códigos de série, unidades ou targets fora deste arquivo.

Convenções:
- SGS:      kpi_id -> codigo (int)
- SIDRA:    kpi_id -> dict com params do sidrapy (territorial_level='1',
             ibge_territorial_code='1' — sempre nacional)
- MARKET:   kpi_id -> ticker yfinance
- TARGETS:  kpi_id -> {meta, banda, direction, threshold_trend, derived}
"""

from __future__ import annotations

# ─── Direção do KPI (para status) ────────────────────────────────────────
# "baixo_melhor": valor menor é melhor (inflação, desemprego, dívida)
# "alto_melhor":  valor maior é melhor (emprego, crescimento, reservas, câmbio p/ exportadores não)
BAIXO_MELHOR = "baixo_melhor"
ALTO_MELHOR = "alto_melhor"

# ─── BACEN SGS ───────────────────────────────────────────────────────────
# códigos do Sistema Gerenciador de Séries Temporais (SGS) do Banco Central.
SGS_SERIES: dict[str, int] = {
    # Preços
    "ipca_12m": 13522,      # IPCA — variação % acumulada em 12 meses
    "ipca_mensal": 433,     # IPCA — variação % no mês
    # Juros
    "selic": 432,           # Taxa Selic (% a.a.) — meta Copom
    # Externo
    "reservas": 13635,      # Reservas internacionais (US$ milhões)
    "exportacoes_fob": 22705,  # Balança comercial — exportações (US$ mi, FOB)
    "importacoes_fob": 22706,  # Balança comercial — importações (US$ mi, FOB)
    # Fiscal (% PIB)
    "divida_bruta": 4513,   # Dívida bruta do governo geral (% PIB)
    "resultado_primario": 5790,  # Resultado primário consolidado (% PIB, 12m)
    # Emprego — Novo CAGED: REATIVAR quando confirmados os códigos de FLUXO
    # MENSAL (admitidos/desligados/saldo do mês). Os códigos 28763/28764/28765
    # são séries CUMULATIVAS (estoque/YTD), não fluxo mensal — o rolling 12m
    # sobre elas seria inválido. Emprego no cockpit vem da PNAD (desocupacao).
}

# CAGED: o Novo CAGED não existe antes de 2020 — start fixo.
CAGED_START = "2020-01-01"
# Chaves CAGED em SGS_SERIES (coletadas à parte por causa do start fixo).
# Atualmente vazio — códigos de fluxo mensal pendentes de confirmação.
CAGED_KEYS: set[str] = set()

# SGS: limite de 10 anos introduzido em mar/2025 — sempre recuar ~10 anos.
SGS_LOOKBACK_DAYS = 3650

# ─── IBGE SIDRA (via sidrapy) ────────────────────────────────────────────
# territorial_level='1' (Brasil) + ibge_territorial_code='1' — sempre nacional.
# Cada entrada traz os params prontos para sidrapy.get_table().
#
# NOTA: as tabelas de índice (PIB 1620/5932, PIM 8159, PMC 3416, PMS 8161)
# estão encerradas/vazias no SIDRA — excluídas por agora. Reativar aqui
# quando as tabelas-base atuais forem identificadas (únicas tabelas
# estáveis hoje: PNAD Contínua). O catálogo é o único ponto de re-adição.
SIDRA_SERIES: dict[str, dict] = {
    "desocupacao": {
        "table": "4099",        # PNAD Contínua trimestral — taxas de desocupação
        "variable": "4099",     # Taxa de desocupação (pessoas 14+)
        "period": "last 24",
    },
}

# ─── Mercado (yfinance) ──────────────────────────────────────────────────
MARKET_SERIES: dict[str, str] = {
    "ibovespa": "^BVSP",   # Ibovespa — fechamento diário
}

# ─── PTAX (câmbio diário, via OData BACEN) ───────────────────────────────
# Símbolos suportados pelo endpoint CotacaoMoedaDia.
PTAX_SYMBOLS: dict[str, str] = {
    "cambio_usd": "USD",
    "cambio_eur": "EUR",
}

# ─── Metadados de KPI ────────────────────────────────────────────────────
# Categorias agrupam o briefing executivo (espelham as páginas de detalhe).
KPI_META: dict[str, dict] = {
    # ── Preços
    "ipca_12m": {
        "label": "IPCA (12 meses)",
        "unit": "%",
        "category": "precos",
        "source": "sgs",
        "frequency": "mensal",
        "description": "Inflação oficial — acumulado em 12 meses",
    },
    "ipca_mensal": {
        "label": "IPCA (mensal)",
        "unit": "%",
        "category": "precos",
        "source": "sgs",
        "frequency": "mensal",
        "description": "Inflação oficial — variação no mês",
    },
    # ── Juros
    "selic": {
        "label": "Taxa Selic",
        "unit": "% a.a.",
        "category": "juros",
        "source": "sgs",
        "frequency": "diária",
        "description": "Taxa básica de juros (meta Copom)",
    },
    # ── Externo
    "cambio_usd": {
        "label": "Dólar (USD/BRL)",
        "unit": "R$",
        "category": "externo",
        "source": "ptax",
        "frequency": "diária",
        "description": "Cotação PTAX de fechamento",
    },
    "cambio_eur": {
        "label": "Euro (EUR/BRL)",
        "unit": "R$",
        "category": "externo",
        "source": "ptax",
        "frequency": "diária",
        "description": "Cotação PTAX de fechamento",
    },
    "reservas": {
        "label": "Reservas internacionais",
        "unit": "US$ bi",
        "category": "externo",
        "source": "sgs",
        "frequency": "diária",
        "description": "Reservas internacionais do Banco Central",
    },
    "balanca_comercial": {
        "label": "Balança comercial (saldo)",
        "unit": "US$ bi",
        "category": "externo",
        "source": "derived",
        "frequency": "mensal",
        "description": "Exportações − Importações (FOB)",
    },
    "exportacoes_fob": {
        "label": "Exportações (FOB)",
        "unit": "US$ bi",
        "category": "externo",
        "source": "sgs",
        "frequency": "mensal",
        "description": "Exportações mensais — Free On Board",
    },
    "importacoes_fob": {
        "label": "Importações (FOB)",
        "unit": "US$ bi",
        "category": "externo",
        "source": "sgs",
        "frequency": "mensal",
        "description": "Importações mensais — Free On Board",
    },
    # ── Fiscal
    "divida_bruta": {
        "label": "Dívida bruta (GG)",
        "unit": "% PIB",
        "category": "fiscal",
        "source": "sgs",
        "frequency": "mensal",
        "description": "Dívida bruta do governo geral",
    },
    "resultado_primario": {
        "label": "Resultado primário",
        "unit": "% PIB",
        "category": "fiscal",
        "source": "sgs",
        "frequency": "mensal",
        "description": "Resultado primário consolidado (12m)",
    },
    # ── Atividade (KPIs de índice IBGE — PIB/PIM/PMC/PMS — reativar quando
    #    as tabelas-base atuais do SIDRA forem identificadas)
    # ── Emprego
    "desocupacao": {
        "label": "Taxa de desocupação",
        "unit": "%",
        "category": "emprego",
        "source": "ibge",
        "frequency": "trimestral",
        "description": "PNAD Contínua — taxa de desocupação",
    },
    # ── Financeiro / Mercado
    "ibovespa": {
        "label": "Ibovespa",
        "unit": "pts",
        "category": "financeiro",
        "source": "market",
        "frequency": "diária",
        "description": "Índice Bovespa — fechamento",
    },
}

# ─── Metas, bandas e tendência ───────────────────────────────────────────
# meta:        valor-alvo (ou None para KPI sem meta → status "neutro").
# banda:       tolerância absoluta em torno da meta.
# direction:   "baixo_melhor" | "alto_melhor".
# threshold_trend: variação mínima (|delta_abs|) para considerar tendência
#                  "alta"/"baixa"; abaixo disso → "estavel".
# derived:     True para KPIs calculados no gold (não coletados diretamente).
TARGETS: dict[str, dict] = {
    "ipca_12m":          {"meta": 3.0, "banda": 1.5, "direction": BAIXO_MELHOR, "threshold_trend": 0.3},
    "ipca_mensal":       {"meta": None},
    "selic":             {"meta": None},
    "cambio_usd":        {"meta": None},
    "cambio_eur":        {"meta": None},
    "reservas":          {"meta": 300_000, "banda": 50_000, "direction": ALTO_MELHOR, "threshold_trend": 5_000},
    "exportacoes_fob":   {"meta": None},
    "importacoes_fob":   {"meta": None},
    "balanca_comercial": {"meta": 0, "banda": 4_000, "direction": ALTO_MELHOR, "threshold_trend": 2_000, "derived": True},
    "divida_bruta":      {"meta": 60.0, "banda": 15.0, "direction": BAIXO_MELHOR, "threshold_trend": 1.0},
    "resultado_primario": {"meta": None},
    "desocupacao":       {"meta": 8.0, "banda": 2.0, "direction": BAIXO_MELHOR, "threshold_trend": 0.3},
    "ibovespa":          {"meta": None},
}

# ─── Conversões de unidade (Bronze → Gold) ───────────────────────────────
# Valores em milhões (US$ mi) que o cockpit mostra em bilhões (÷ 1000).
UNIT_DIV_1000 = {"reservas", "exportacoes_fob", "importacoes_fob", "balanca_comercial"}
# CAGED saldo 12m: pessoas → milhares (÷ 1000) para leitura executiva.
UNIT_DIV_1000_K = {"caged_saldo_12m"}


def compute_status(kpi_id: str, valor) -> str:
    """
    Status semafórico a partir de catalog.TARGETS.

    Regras:
    - meta None              -> "neutro"
    - direction baixo_melhor: valor <= meta              -> "verde"
                               valor <= meta + banda      -> "amarelo"
                               senão                      -> "vermelho"
    - direction alto_melhor:  valor >= meta              -> "verde"
                               valor >= meta - banda      -> "amarelo"
                               senão                      -> "vermelho"
    """
    if valor is None:
        return "neutro"
    t = TARGETS.get(kpi_id, {})
    meta = t.get("meta")
    if meta is None:
        return "neutro"
    banda = t.get("banda", 0)
    direction = t.get("direction", BAIXO_MELHOR)
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "neutro"
    if direction == BAIXO_MELHOR:
        if v <= meta:
            return "verde"
        if v <= meta + banda:
            return "amarelo"
        return "vermelho"
    else:  # alto_melhor
        if v >= meta:
            return "verde"
        if v >= meta - banda:
            return "amarelo"
        return "vermelho"


def compute_trend(kpi_id: str, delta_abs) -> str:
    """
    Tendência a partir do delta e do threshold_trend do KPI.
    "alta" / "baixa" / "estavel". (Direção do MOVIMENTO, não julgamento —
    o julgamento de bom/ruim fica em compute_status via direction.)
    """
    if delta_abs is None:
        return "estavel"
    t = TARGETS.get(kpi_id, {})
    threshold = t.get("threshold_trend", 0)
    try:
        d = float(delta_abs)
    except (TypeError, ValueError):
        return "estavel"
    if abs(d) < threshold:
        return "estavel"
    return "alta" if d > 0 else "baixa"


# Ordem de exibição no briefing executivo (por categoria).
CATEGORY_ORDER = [
    "precos",
    "juros",
    "emprego",
    "externo",
    "fiscal",
    "financeiro",
]

CATEGORY_LABELS = {
    "precos": "Preços",
    "juros": "Juros",
    "emprego": "Emprego",
    "externo": "Setor externo",
    "fiscal": "Fiscal",
    "financeiro": "Financeiro",
}


def briefing_kpis() -> list[str]:
    """KPIs que aparecem no briefing de 30s (1ª página) — ordenados por categoria."""
    return [
        "ipca_12m",
        "selic",
        "desocupacao",
        "cambio_usd",
        "reservas",
        "balanca_comercial",
        "divida_bruta",
        "ibovespa",
    ]
