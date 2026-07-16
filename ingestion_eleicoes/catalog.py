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


# ═══════════════════════════════════════════════════════════════════════════
# Perfil do Eleitorado (TSE — Estatísticas de Eleitorado, snapshot ATUAL)
# ═══════════════════════════════════════════════════════════════════════════
# Contraparte demográfica das pesquisas: quem é o eleitorado que os institutos
# tentam medir. Fonte oficial, apartidária (só contagem de eleitores por
# atributo — sexo, faixa etária, escolaridade, cor/raça, biometria, UF).
#
# ATENÇÃO: o CSV descompactado tem ~2,3 GB (uma linha por seção × combinação de
# atributos). O collector faz stream direto do ZIP em chunks e agrega para um
# bronze compacto (nunca grava o CSV cru em disco). Job pesado → roda mensal,
# separado do cron diário das pesquisas (o eleitorado muda pouco).
TSE_ELEITORADO_ZIP_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/"
    "perfil_eleitorado_ATUAL.zip"
)
TSE_ELEITORADO_CSV = "perfil_eleitorado_ATUAL.csv"
DATASET_PAGE_ELEITORADO = "https://dadosabertos.tse.jus.br/dataset/eleitorado-atual"

# Colunas do CSV de perfil que interessam à agregação (as demais são
# descartadas na leitura — usecols — para caber em memória em stream).
COLUNAS_ELEITORADO = {
    "SG_UF": "uf",
    "DS_GENERO": "genero",
    "DS_FAIXA_ETARIA": "faixa_etaria",
    "DS_GRAU_INSTRUCAO": "grau_instrucao",
    "DS_COR_RACA": "cor_raca",
    "TP_OBRIGATORIEDADE_VOTO": "obrigatoriedade",
    "QT_ELEITORES": "qt_eleitores",
    "QT_ELEITORES_BIOMETRIA": "qt_biometria",
    "QT_ELEITORES_DEFICIENCIA": "qt_deficiencia",
}
# Chaves de agrupamento do bronze agregado (colapsa 2,3 GB → milhares de linhas).
ELEITORADO_GROUP_KEYS = [
    "uf", "genero", "faixa_etaria", "grau_instrucao", "cor_raca", "obrigatoriedade",
]
ELEITORADO_MEASURES = ["qt_eleitores", "qt_biometria", "qt_deficiencia"]

# UFs válidas (exclui "ZZ" = exterior e "VT" = voto em trânsito, tratadas à parte).
UF_EXTERIOR = "ZZ"
UF_TRANSITO = "VT"


# ═══════════════════════════════════════════════════════════════════════════
# Pré-candidatos + Intenção de voto PRESIDENCIAL (agregador da Wikipedia PT)
# ═══════════════════════════════════════════════════════════════════════════
# O dataset de REGISTRO do TSE não traz percentuais de intenção de voto (ficam
# nos PDFs de questionário). Para a v1 do módulo de pré-candidatos usamos a
# Wikipedia PT como AGREGADORA das pesquisas presidenciais registradas — fonte
# estruturada (wikitables de 1º/2º turno), citável e apartidária. Cada pesquisa
# permanece atribuída ao seu instituto e data; nunca há previsão nem cor
# partidária no runtime.
#
# ATENÇÃO (apartidarismo): exibimos instituto + data + margem sempre; o "líder"
# é só um destaque visual (--wc-gold), não um prognóstico.
WIKIPEDIA_API = "https://pt.wikipedia.org/w/api.php"
WIKIPEDIA_PRESIDENCIAL_TITLE = (
    "Pesquisas de opinião para a eleição presidencial no Brasil em 2026"
)
WIKIPEDIA_PRESIDENCIAL_URL = (
    "https://pt.wikipedia.org/wiki/"
    "Pesquisas_de_opinião_para_a_eleição_presidencial_no_Brasil_em_2026"
)
ANO_ELEICAO_PRESIDENCIAL = 2026

# Só consideram-se relevantes candidatos que atingem este piso de intenção em
# alguma medição recente (a própria Wikipedia lista quem passou de ~3%).
PCT_MIN_RELEVANTE = 3.0
# Para entrar no painel de 1º turno, o candidato precisa aparecer em pelo menos
# este nº de pesquisas na janela recente (descarta ruído de 1 pesquisa isolada,
# ex.: cenários hipotéticos com nomes inelegíveis).
MIN_PESQUISAS_RECENTES = 3
# Janela "recente" para o snapshot/médias do 1º turno (dias).
JANELA_RECENTE_DIAS = 90

# Rótulos internos dos cenários.
CENARIO_1T = "primeiro_turno"
CENARIO_2T = "segundo_turno"

# Cabeçalhos de coluna (nível meta) das wikitables — casados por substring, em
# minúsculas. Tudo que não é meta nem coluna a ignorar é tratado como candidato.
META_COL_KEYS = {
    "inst": "contratante",
    "data": "data",
    "amostra": "amostra",
    "margem": "margem",
}
# Colunas que NÃO são candidato (somatórios/residuais das wikitables).
COL_IGNORAR = (
    "outros", "indecisos", "absten", "branco", "nulo", "vantagem",
    "ninguém", "nenhum", "não sab", "diferença", "líquido", "total",
)

# Meses PT abreviados → número (parsing das datas "10 jul - 13 jul").
MESES_PT = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}

# Normalização de nome do candidato (variações da Wikipedia → nome canônico).
# A sigla do partido vem junto na wikitable ("Lula PT"); usamos o primeiro token
# como nome curto e mapeamos aqui só os casos ambíguos/compostos.
CANDIDATO_NORMALIZE = {
    "Lula": "Lula",
    "Flávio": "Flávio Bolsonaro",
    "Bolsonaro": "Jair Bolsonaro",
    "Michelle": "Michelle Bolsonaro",
    "Eduardo": "Eduardo Bolsonaro",
    "Tarcísio": "Tarcísio de Freitas",
    "Haddad": "Fernando Haddad",
    "Caiado": "Ronaldo Caiado",
    "Zema": "Romeu Zema",
    "Ratinho": "Ratinho Jr.",
    "Leite": "Eduardo Leite",
    "Ciro": "Ciro Gomes",
    "Marçal": "Pablo Marçal",
    "Moro": "Sergio Moro",
    "Renan": "Renan (Missão)",
}


# ═══════════════════════════════════════════════════════════════════════════
# Intenção de voto ESTADUAL — governador + senador (Fase 2)
# ═══════════════════════════════════════════════════════════════════════════
# Um artigo por UF na Wikipedia PT ("Pesquisas eleitorais para a eleição
# estadual de 2026 {sufixo}"). Mesma natureza da Fase 1: agrega pesquisas
# registradas no TSE, é citável e apartidária. Confirmado: 24 das 27 UFs têm
# artigo (faltam DF, MS, MT) → coletor fail-soft por estado.
#
# ATENÇÃO (rate limit): baixar 24 artigos em série rápida provoca HTTP 429.
# O coletor faz throttle entre estados (ver ESTADUAL_THROTTLE_S) e usa
# User-Agent descritivo.
WIKIPEDIA_ESTADUAL_TITLE_FMT = "Pesquisas eleitorais para a eleição estadual de 2026 {suf}"
ESTADUAL_THROTTLE_S = 2.0

# UF → sufixo do título (com a preposição correta). DF/MS/MT omitidos: sem
# artigo hoje. Se forem publicados, basta acrescentar aqui.
UF_ARTIGO_SUFIXO = {
    "SP": "em São Paulo",
    "RJ": "no Rio de Janeiro",
    "MG": "em Minas Gerais",
    "PR": "no Paraná",
    "RS": "no Rio Grande do Sul",
    "BA": "na Bahia",
    "CE": "no Ceará",
    "PE": "em Pernambuco",
    "SC": "em Santa Catarina",
    "GO": "em Goiás",
    "PA": "no Pará",
    "MA": "no Maranhão",
    "AM": "no Amazonas",
    "ES": "no Espírito Santo",
    "PB": "na Paraíba",
    "RN": "no Rio Grande do Norte",
    "PI": "no Piauí",
    "AL": "em Alagoas",
    "SE": "em Sergipe",
    "RO": "em Rondônia",
    "TO": "no Tocantins",
    "AC": "no Acre",
    "AP": "no Amapá",
    "RR": "em Roraima",
}

# Cenários estaduais.
CENARIO_GOV_1T = "governador_1t"
CENARIO_GOV_2T = "governador_2t"
CENARIO_SEN = "senador"


def cargo_do_heading(texto: str) -> str | None:
    """Classifica a tabela pelo H2/H3 mais próximo (texto).

    'Segundo Turno' (sob a seção Governador) → governador_2t;
    'Governador' → governador_1t; 'Senador' → senador.
    """
    t = (texto or "").lower()
    if "senador" in t or "senado" in t:
        return CENARIO_SEN
    if "segundo turno" in t or "2º turno" in t or "2° turno" in t:
        return CENARIO_GOV_2T
    if "governador" in t or "primeiro turno" in t or "1º turno" in t:
        return CENARIO_GOV_1T
    return None


def split_nome_partido(coluna: str) -> tuple[str, str] | None:
    """Separa 'Nome (PARTIDO)' OU 'Nome PARTIDO' → (nome_curto, partido).

    Governador 1º turno usa parênteses ('Tarcísio (REP)'); 2º turno e senador
    usam sufixo ('Tarcísio REP', 'Simone Tebet PSB'). Devolve None se não casar.
    """
    import re as _re

    s = (coluna or "").strip()
    m = _re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", s)  # Nome (PARTIDO)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    parts = s.rsplit(" ", 1)  # Nome PARTIDO
    if len(parts) == 2 and parts[1]:
        return parts[0].strip(), parts[1].strip()
    return None


# ══════════════════════════ INTEGRIDADE (situação jurídica) ══════════════════════════
# Seção [13] do painel. Enquadramento neutro: estágio processual, presunção de
# inocência, fontes oficiais. Dados POR CANDIDATO passam a existir após o
# registro das candidaturas (TSE DivulgaCand publica certidões/elegibilidade a
# partir de 15/08/2026). Até lá, o coletor roda fail-soft e o envelope sai com
# itens_por_candidato vazio. Nunca inferir/alegar sem fonte oficial citável.

INTEGRIDADE_METODOLOGIA = (
    "Reúne a situação jurídica pública dos pré-candidatos a partir de fontes "
    "oficiais (TSE, STF/STJ). Cada item traz o órgão, o estágio processual e a "
    "fonte. Passa a exibir dados por candidato conforme o registro das "
    "candidaturas (a partir de 15/08/2026), quando o TSE publica certidões e "
    "condições de elegibilidade."
)
INTEGRIDADE_DISCLAIMER = (
    "Estágio processual não é condenação. Todos são presumidos inocentes até "
    "decisão final (trânsito em julgado). Sem juízo de valor nem cor partidária "
    "— apenas o que o registro público permite."
)
# Estágios (ordem crescente de gravidade). Os ids batem com o data-stage do CSS
# e com estagios[].id lidos pelo frontend.
INTEGRIDADE_ESTAGIOS = [
    {"id": "investigacao", "label": "investigação"},
    {"id": "denuncia", "label": "denúncia recebida"},
    {"id": "reu", "label": "réu (ação penal)"},
    {"id": "condenacao_1a", "label": "condenação em 1ª instância"},
    {"id": "transito", "label": "trânsito em julgado"},
    {"id": "ficha_limpa", "label": "Ficha Limpa · elegível"},
]
INTEGRIDADE_FONTES = [
    {"label": "TSE · DivulgaCand", "url": "https://divulgacandcontas.tse.jus.br/divulga/"},
    {"label": "STF · consulta processual", "url": "https://portal.stf.jus.br/processos/"},
    {"label": "STJ · consulta processual", "url": "https://processo.stj.jus.br/processo/pesquisa/"},
]

# TSE DivulgaCand — API pública oficial. O código da eleição ordinária 2026 é
# atribuído no sistema durante o registro; enquanto vazio aqui, o coletor NÃO
# consulta (produz itens vazios). Preencher após 15/08/2026.
TSE_DIVULGACAND_API = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1"
TSE_DIVULGACAND_COD_ELEICAO = ""  # ex.: "2040602026" (definir no registro)

# Rosters canônicos já produzidos por outros coletores (join por nome do painel).
INTEGRIDADE_ROSTER_PRESIDENCIAL = "assets/data/eleicoes_precandidatos.json"
INTEGRIDADE_ROSTER_ESTADUAL = "assets/data/eleicoes_estaduais.json"
