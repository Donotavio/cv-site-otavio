"""
Observatório Eleições 2026 — Catálogo (fonte única de verdade)
==============================================================
Define a fonte de dados oficial (TSE — Pesquisas Eleitorais 2026), o schema
bronze e os rótulos usados na camada gold. TODOS os scripts (collect_*.py,
gold_*.py) importam daqui — nunca hardcodar URL, colunas ou rótulos fora deste
arquivo.

Fonte: Portal de Dados Abertos do TSE — "Pesquisas Eleitorais 2026".
        https://dadosabertos.tse.jus.br/dataset/pesquisas-eleitorais-2026

IMPORTANTE (transparência): o dataset de REGISTRO de pesquisas traz METADADOS
(instituto, contratante, cargo, UF, nº de entrevistados, custo, datas,
metodologia) — NÃO os percentuais de intenção de voto (que ficam nos PDFs de
questionário). Por isso o observatório é sobre a *máquina de medição* da
eleição, não sobre "quem está ganhando".
"""

from __future__ import annotations

# ─── Fonte oficial (TSE Dados Abertos) ───────────────────────────────────
# ZIP com um CSV nacional (_BRASIL) + um por UF. Latin-1, delimitado por ';'.
TSE_PESQUISAS_ZIP_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/pesquisa_eleitoral/"
    "pesquisa_eleitoral_2026.zip"
)
# Arquivo nacional dentro do zip (contém todas as UFs).
TSE_CSV_NACIONAL = "pesquisa_eleitoral_2026_BRASIL.csv"
CSV_ENCODING = "latin-1"
CSV_DELIMITER = ";"

DATASET_PAGE = "https://dadosabertos.tse.jus.br/dataset/pesquisas-eleitorais-2026"
ANO_ELEICAO = 2026

# ─── Mapa coluna TSE → coluna bronze (canônica) ──────────────────────────
# Só as colunas que interessam à agregação — o texto longo de metodologia/
# plano amostral é descartado (não some no parquet, mantém o bronze enxuto).
COLUNAS = {
    "DT_DIVULGACAO": "dt_divulgacao",
    "DT_INICIO_PESQUISA": "dt_inicio",
    "DT_FIM_PESQUISA": "dt_fim",
    "DT_REGISTRO": "dt_registro",
    "NR_PROTOCOLO_REGISTRO": "protocolo",
    "AA_ELEICAO": "ano_eleicao",
    "SG_UF": "uf",
    "NM_UE": "nm_ue",
    "ST_PESQUISA_PROPRIA": "propria",       # 'S' = própria / 'N' = contratada
    "NR_CNPJ_EMPRESA": "cnpj",
    "NM_EMPRESA": "empresa",
    "DS_CARGO": "cargo",
    "QT_ENTREVISTADO": "qt_entrevistado",
    "VR_PESQUISA": "vr_pesquisa",           # custo declarado (R$)
    "NM_ESTATISTICO_RESP": "estatistico",
}

# ─── Regras de qualidade ─────────────────────────────────────────────────
# QT_ENTREVISTADO aparece com valores inválidos (ex.: -2000). Amostra só é
# considerada válida se > 0. VR_PESQUISA negativo também é descartado.
QT_MIN_VALIDO = 1

# ─── Classificação de cargo (nível da disputa) ───────────────────────────
# DS_CARGO vem como combos ("Governador, Senador, ..."). Para o cockpit,
# classificamos pelo nível: nacional (Presidente / UF=BR) vs estadual.
def nivel_disputa(uf: str, cargo: str) -> str:
    """Presidencial/Nacional quando UF=BR ou cargo cita Presidente; senão Estadual."""
    uf = (uf or "").strip().upper()
    cargo = (cargo or "").lower()
    if uf == "BR" or "presidente" in cargo:
        return "presidencial"
    return "estadual"


# Faixas de tamanho de amostra (rigor metodológico, leitura executiva).
FAIXAS_AMOSTRA = [
    ("até 600", 0, 600),
    ("601–1.000", 601, 1000),
    ("1.001–2.000", 1001, 2000),
    ("2.001–5.000", 2001, 5000),
    ("5.000+", 5001, 10**9),
]
