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
    "Gomes": "Ciro Gomes",
    "Marçal": "Pablo Marçal",
    "Moro": "Sergio Moro",
    "Renan": "Renan (Missão)",
}

# Normalização de NOME DE INSTITUTO (variações de grafia/capitalização da
# Wikipedia → nome canônico). Escopo deliberadamente conservador: só funde
# strings que são inequivocamente o MESMO instituto com erro de digitação ou
# capitalização diferente. NÃO funde parcerias regionais distintas (ex.: "Doxa
# (Belém)" vs "Doxa (Santarém)" são o mesmo instituto em praças diferentes,
# mas contam como medições separadas no ranking "quem mede" — fundir mudaria
# a métrica sem uma fonte que confirme que deveriam ser 1 linha só).
INSTITUTO_NORMALIZE = {
    "Atlasinstel": "AtlasIntel",
    "AltasIntel": "AtlasIntel",
    "DataFolha": "Datafolha",
    "Vox": "Vox Brasil",
    "Futura/Inteligência": "Futura Inteligência",
    "Nexus/BTG": "Nexus/BTG Pactual",
    "100%Cidades/Futura": "100% Cidades/Futura",
}


def normalizar_instituto(nome: str) -> str:
    """Aplica INSTITUTO_NORMALIZE; devolve o nome original se não houver mapa."""
    nome = (nome or "").strip()
    return INSTITUTO_NORMALIZE.get(nome, nome)


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

# As 27 unidades federativas — usada só para derivar UF_SEM_ARTIGO abaixo
# (nunca hardcodar essa lista em outro lugar do pipeline).
TODAS_UFS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
    "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
    "SE", "SP", "TO",
}
# UFs sem artigo próprio na Wikipedia hoje (derivado, não mantido à mão — se
# UF_ARTIGO_SUFIXO ganhar uma entrada nova, esta lista encolhe sozinha).
UF_SEM_ARTIGO = sorted(TODAS_UFS - set(UF_ARTIGO_SUFIXO.keys()))

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


# ══════════════════════════ INTEGRIDADE (situação de registro) ═══════════════════════
# Seção [13] do painel. O registro de candidaturas fechou em 15/08/2026; desde
# então o TSE publica, por candidato, a SITUAÇÃO DE REGISTRO no dataset aberto
# "Candidatos" (consulta_cand — ver tse_dados_abertos.py). Isso é diferente de
# "situação jurídica" no sentido de processo criminal: o dataset não tem
# estágio de investigação/denúncia/condenação — só o resultado administrativo
# da análise de elegibilidade (deferido, indeferido, sub judice, cancelado,
# renúncia). A Lei da Ficha Limpa (LC 64/90) É aplicada nessa análise: uma
# candidatura indeferida por inelegibilidade aparece aqui. Por isso a seção
# mostra "situação de registro", não os 6 estágios processuais originalmente
# desenhados (que exigiriam a API DivulgaCand REST — sem documentação pública
# do código de eleição e bloqueada neste ambiente; ver tse_dados_abertos.py).
# Nunca inferir/alegar situação sem fonte oficial citável.

INTEGRIDADE_METODOLOGIA = (
    "Reúne a situação de registro de cada candidatura junto à Justiça Eleitoral "
    "(fonte: TSE — Portal de Dados Abertos, dataset Candidatos). O prazo de "
    "registro fechou em 15/08/2026 e o julgamento dos pedidos leva semanas: "
    "enquanto a Justiça Eleitoral não decide, o TSE publica a situação como "
    "não preenchida e este painel mostra 'aguardando julgamento'. Conforme as "
    "decisões saem, cada candidatura passa a deferida, indeferida ou sub "
    "judice — o painel reflete o snapshot da última coleta."
)
INTEGRIDADE_DISCLAIMER = (
    "Situação de registro não é o mesmo que processo criminal — é o resultado "
    "da análise de elegibilidade feita pela Justiça Eleitoral. 'Aguardando "
    "julgamento' significa que o pedido ainda não foi decidido, não que haja "
    "qualquer problema com a candidatura. 'Sub judice' significa recurso "
    "pendente: a candidatura concorre normalmente até decisão final. Sem juízo "
    "de valor nem cor partidária — apenas o que o registro público informa."
)
# Situações de registro (rótulo em pt-BR do valor DS_SITUACAO_CANDIDATURA do
# TSE). O id "outro" cobre qualquer valor que apareça no CSV real e não bata
# com os rótulos abaixo — nunca descartar um candidato por situação
# desconhecida, só rotular como "outro" e mostrar o texto bruto do TSE.
INTEGRIDADE_SITUACOES = [
    {"id": "deferido", "label": "Deferido", "match": ["DEFERIDO"]},
    {"id": "sub_judice", "label": "Sub judice (recurso pendente)", "match": ["SUB JUDICE", "SUB JÚDICE"]},
    {"id": "indeferido", "label": "Indeferido", "match": ["INDEFERIDO"]},
    {"id": "cancelado", "label": "Cancelado", "match": ["CANCELADO"]},
    {"id": "renuncia", "label": "Renúncia", "match": ["RENUNCIA", "RENÚNCIA"]},
    # '#NE' e '#NULO' são os marcadores do TSE para "campo não preenchido na
    # base". Em 22/08/2026 TODAS as 20.708 candidaturas vinham assim: o prazo
    # de registro fechou em 15/08 e a Justiça Eleitoral ainda não julgou os
    # pedidos. Mapear isso para "outra situação" seria enganoso — sugere algo
    # anômalo onde só falta o julgamento acontecer.
    {"id": "aguardando", "label": "Aguardando julgamento", "match": ["#NE", "#NULO", "#NULO#"]},
    {"id": "outro", "label": "Outra situação", "match": []},
]
INTEGRIDADE_FONTES = [
    {
        "label": "TSE · Portal de Dados Abertos — Candidatos",
        "url": "https://dadosabertos.tse.jus.br/dataset/candidatos-2026",
    },
    {"label": "TSE · DivulgaCandContas", "url": "https://divulgacandcontas.tse.jus.br/divulga/"},
]

# TSE Portal de Dados Abertos — mesmo CDN usado por TSE_PESQUISAS_ZIP_URL.
# {ano} é preenchido pelo coletor (2026 = atual; 2022 = comparação, só p/
# patrimônio). ATENÇÃO: confirmado bloqueado (HTTP 403) em teste manual de
# ago/2026 mesmo simulando navegador — fail-soft, ver tse_dados_abertos.py.
TSE_CONSULTA_CAND_ZIP_URL_FMT = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip"
)
TSE_BEM_CANDIDATO_ZIP_URL_FMT = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_{ano}.zip"
)
TSE_CONSULTA_CAND_SUFIXO_BRASIL = "_BRASIL.csv"
TSE_BEM_CANDIDATO_SUFIXO_BRASIL = "_BRASIL.csv"

# Cargos do roster do painel (presidente + governador) como aparecem em
# DS_CARGO no consulta_cand — usados para filtrar as ~20 mil candidaturas do
# CSV nacional só para quem interessa ao painel antes de qualquer join.
CARGOS_ROSTER_PAINEL = {"PRESIDENTE", "GOVERNADOR"}

# Rosters canônicos já produzidos por outros coletores (join por nome do painel).
INTEGRIDADE_ROSTER_PRESIDENCIAL = "assets/data/eleicoes_precandidatos.json"
INTEGRIDADE_ROSTER_ESTADUAL = "assets/data/eleicoes_estaduais.json"


# ══════════════════════════ PATRIMÔNIO (bens declarados) ══════════════════════════
# Seção nova do painel: evolução patrimonial 2022→2026 dos candidatos do
# roster (presidente + governador), a partir da declaração de bens que cada
# candidato presta ao TSE no registro (dataset "bem_candidato", mesmo Portal
# de Dados Abertos). É dado público por desenho — não confundir com sigilo
# fiscal: NÃO cruza com Receita Federal (dado de pessoa física é sigiloso, sem
# API pública) nem infere patrimônio não declarado. Mostra só o que o próprio
# candidato declarou em cada ano, lado a lado.
PATRIMONIO_ANO_ATUAL = 2026
PATRIMONIO_ANO_COMPARACAO = 2022
PATRIMONIO_METODOLOGIA = (
    "Soma o valor declarado de todos os bens de cada candidato (imóveis, "
    "veículos, aplicações financeiras, participação societária etc.) no "
    "registro de candidatura — fonte: TSE, Portal de Dados Abertos, dataset "
    "Candidatos. Compara a declaração de 2026 com a de 2022 do mesmo "
    "candidato (join por CPF). Não é patrimônio real nem auditado — é o valor "
    "autodeclarado; a Justiça Eleitoral não confere com a Receita Federal "
    "publicamente (dado de pessoa física é sigilo fiscal, sem API pública)."
)
PATRIMONIO_DISCLAIMER = (
    "Valor autodeclarado pelo próprio candidato, sem auditoria pública. "
    "Ausência de bem declarado não significa ausência de patrimônio. "
    "Comparação só é possível para quem também foi candidato em 2022."
)
PATRIMONIO_FONTES = [
    {
        "label": "TSE · Portal de Dados Abertos — Candidatos (bens)",
        "url": "https://dadosabertos.tse.jus.br/dataset/candidatos-2026",
    },
]


# ═══════════════════════ PRESTAÇÃO DE CONTAS (campanha) ═══════════════════════
# Seção nova do painel: dinheiro arrecadado (receitas) e gasto (despesas pagas)
# por candidato do roster, dataset "Prestação de Contas Eleitorais" do mesmo
# Portal de Dados Abertos do TSE. SEM DADO REAL até o prazo de entrega da
# prestação parcial (PRESTACAO_PRAZO_PARCIAL) — antes disso o coletor roda
# fail-soft e a seção do painel mostra só o arcabouço + contagem regressiva.
#
# Único ponto do painel onde um cruzamento com Receita Federal é PUBLICAMENTE
# possível: para doador pessoa jurídica (CNPJ), o TSE publica ao lado do nome
# autodeclarado pela campanha (NM_DOADOR) o nome da própria Receita Federal
# para aquele CNPJ (NM_DOADOR_RFB) — os dois deveriam bater. Para pessoa física
# (CPF) não existe equivalente público: dado de pessoa física é sigilo fiscal,
# sem API da Receita Federal. Não fabricar comparação para CPF.
PRESTACAO_ANO = 2026
PRESTACAO_PRAZO_PARCIAL = "2026-09-13"  # prestação de contas parcial (curado em eleicoes_contexto.json)
PRESTACAO_PRAZO_FINAL = "2026-11-03"  # prestação de contas final (só 1º turno)

# URL e nomes de arquivo CONFIRMADOS contra o zip real de 2026 (112 arquivos:
# CSVs por UF + um "_BRASIL" consolidado por dataset).
TSE_PRESTACAO_CONTAS_ZIP_URL_FMT = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/"
    "prestacao_de_contas_eleitorais_candidatos_{ano}.zip"
)
TSE_RECEITAS_SUFIXO_BRASIL = "receitas_candidatos_{ano}_BRASIL.csv"
# "contratadas", não "pagas": só este traz identificação do candidato —
# ver comentário em DESPESAS_COLUNAS (tse_dados_abertos.py).
TSE_DESPESAS_SUFIXO_BRASIL = "despesas_contratadas_candidatos_{ano}_BRASIL.csv"

PRESTACAO_METODOLOGIA = (
    "Soma as receitas declaradas (doações, recursos próprios, Fundo "
    "Eleitoral/partidário) e as despesas contratadas de cada candidato a "
    "presidente ou governador — fonte: TSE, Portal de Dados Abertos, dataset "
    "Prestação de Contas Eleitorais. Usa 'despesas contratadas' porque o "
    "arquivo de despesas pagas do TSE não identifica o candidato. Os valores "
    "são cumulativos e crescem a cada relatório financeiro enviado durante a "
    "campanha."
)
PRESTACAO_DISCLAIMER = (
    f"Valores autodeclarados pela própria campanha, ainda sem julgamento das "
    f"contas pela Justiça Eleitoral. O TSE republica os relatórios financeiros "
    f"ao longo da campanha, então o total sobe com o tempo — o retrato é da "
    f"última coleta, não o gasto final (prestação parcial até "
    f"{PRESTACAO_PRAZO_PARCIAL}, final até {PRESTACAO_PRAZO_FINAL}). "
    f"O confronto doador × Receita Federal usa o nome que o próprio TSE "
    f"publica para o CPF/CNPJ ao lado do declarado pela campanha; divergência "
    f"aqui indica cadastro desatualizado ou grafia diferente, não irregularidade."
)
PRESTACAO_FONTES = [
    {
        "label": "TSE · Portal de Dados Abertos — Prestação de Contas Eleitorais",
        "url": "https://dadosabertos.tse.jus.br/group/prestacao-de-contas-eleitorais",
    },
]
