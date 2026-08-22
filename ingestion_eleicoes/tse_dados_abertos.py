"""
Observatório Eleições 2026 — acesso ao Portal de Dados Abertos do TSE
=======================================================================
Helper compartilhado por collect_integridade.py e collect_patrimonio.py para
baixar e ler os ZIPs de "Candidatos" (consulta_cand, bem_candidato) do Portal
de Dados Abertos do TSE (https://dadosabertos.tse.jus.br).

ATENÇÃO (rede): cdn.tse.jus.br é conhecido por recusar conexões de datacenter
(o coletor de pesquisas já convive com isso — ver comentário no workflow CI).
Confirmado manualmente em 22/08/2026: tanto os ZIPs de Dados Abertos quanto a
API DivulgaCand REST devolveram HTTP 403 mesmo simulando um navegador. Por
isso TODO download aqui é fail-soft — retorna None em qualquer falha (rede,
403, zip corrompido, arquivo ausente) e NUNCA lança. O cron diário tenta de
novo no dia seguinte; não há por que derrubar o pipeline inteiro por causa de
um bloqueio que pode ser intermitente ou específico deste ambiente.

ATENÇÃO (colunas): o layout de colunas do TSE é estável desde ~2014, mas não
há documentação pública verificável neste ambiente (mesmo bloqueio de rede
acima impede inspecionar o CSV real antes da primeira execução em CI). Os
nomes em CAND_COLUNAS/BEM_COLUNAS são os nomes oficiais conhecidos do padrão
TSE. `linha_valor()` resolve pelo header REAL do CSV baixado (não assume
posição) e `checar_colunas()` loga um aviso claro — nunca falha silenciosamente
— se alguma coluna esperada não existir, facilitando o diagnóstico na primeira
execução real em produção.
"""

from __future__ import annotations

import csv
import io
import zipfile

import requests

# ── Cliente HTTP para os domínios do TSE ────────────────────────────────────
# O TSE está atrás do Akamai Bot Manager, que classifica o cliente pelo
# fingerprint TLS/JA3 — não por IP nem User-Agent. `requests` (via urllib3)
# tem fingerprint de biblioteca e leva 403 em TUDO, inclusive no site
# institucional e em arquivos históricos; browser real passa. Diagnosticado em
# 22/08/2026 comparando os dois clientes lado a lado no mesmo IP:
#     requests → 403 | curl_cffi(impersonate=chrome) → 200 (3 MB)
# `curl_cffi` replica o fingerprint do Chrome, então o pipeline volta a ler o
# dado público que o TSE publica justamente para consumo (Dados Abertos/LAI).
# Fallback para `requests` se a lib não estiver instalada — aí o download
# falha fail-soft como antes, sem quebrar o pipeline.
try:
    from curl_cffi import requests as _cffi

    _IMPERSONATE = "chrome"
except ImportError:  # pragma: no cover - só em ambiente sem a dependência
    _cffi = None
    _IMPERSONATE = None


def http_get(url: str, timeout: int, stream: bool = False):
    """GET nos domínios do TSE com fingerprint de browser (ver nota acima)."""
    if _cffi is not None:
        return _cffi.get(url, impersonate=_IMPERSONATE, timeout=timeout, stream=stream)
    return requests.get(url, headers=HEADERS, timeout=timeout, stream=stream)

HEADERS = {
    "User-Agent": (
        "observatorio-eleicoes-2026/1.0 "
        "(https://github.com/Donotavio/cv-site-otavio; dados-abertos) requests"
    )
}
TIMEOUT = 180
CSV_ENCODING = "latin-1"
CSV_DELIMITER = ";"

# Nomes oficiais de coluna do padrão TSE (consulta_cand). Uma entrada por
# campo lógico — se o TSE trocar o nome de uma coluna, ajustar só aqui.
CAND_COLUNAS = {
    "sq_candidato": "SQ_CANDIDATO",
    "nr_cpf": "NR_CPF_CANDIDATO",
    "nome_urna": "NM_URNA_CANDIDATO",
    "nome": "NM_CANDIDATO",
    "cargo": "DS_CARGO",
    "uf": "SG_UF",
    "partido": "SG_PARTIDO",
    "situacao": "DS_SITUACAO_CANDIDATURA",
    # Não existe coluna de "detalhe da situação" no consulta_cand (confirmado
    # contra o CSV real de 2026 em 22/08/2026 — checar_colunas() acusou a
    # ausência). DS_SIT_TOT_TURNO existe mas é resultado da totalização do
    # turno, semântica diferente: não usar como substituto.
    "ano_eleicao": "ANO_ELEICAO",
}

# Nomes oficiais de coluna do padrão TSE (bem_candidato).
BEM_COLUNAS = {
    "sq_candidato": "SQ_CANDIDATO",
    "tipo_bem": "DS_TIPO_BEM_CANDIDATO",
    "descricao": "DS_BEM_CANDIDATO",
    "valor": "VR_BEM_CANDIDATO",
    "ano_eleicao": "ANO_ELEICAO",
}

# Colunas de receitas_candidatos_{ano}_BRASIL.csv — CONFIRMADAS contra o CSV
# real de 2026 (inspecionado em 22/08/2026). Atenção a dois nomes que fogem do
# padrão dos outros datasets: o ano é AA_ELEICAO (não ANO_ELEICAO) e o nome do
# candidato é NM_CANDIDATO (não há NM_URNA_CANDIDATO aqui).
RECEITAS_COLUNAS = {
    "sq_candidato": "SQ_CANDIDATO",
    "nr_cpf": "NR_CPF_CANDIDATO",
    "nome": "NM_CANDIDATO",
    "cargo": "DS_CARGO",
    "uf": "SG_UF",
    "partido": "SG_PARTIDO",
    "dt_receita": "DT_RECEITA",
    "valor": "VR_RECEITA",
    "origem": "DS_ORIGEM_RECEITA",
    "especie": "DS_ESPECIE_RECEITA",
    "cpf_cnpj_doador": "NR_CPF_CNPJ_DOADOR",
    "nome_doador": "NM_DOADOR",
    # Nome que a Receita Federal tem para aquele CPF/CNPJ, publicado pelo
    # próprio TSE ao lado do nome declarado pela campanha. É o que viabiliza
    # o cruzamento doador × RFB (confirmado presente no CSV real).
    "nome_doador_rfb": "NM_DOADOR_RFB",
    "ano_eleicao": "AA_ELEICAO",
}

# Colunas de despesas_contratadas_candidatos_{ano}_BRASIL.csv — CONFIRMADAS
# contra o CSV real de 2026. Usamos "contratadas" e não "pagas" de propósito:
# despesas_pagas_*_BRASIL.csv não traz identificação do candidato (só
# SQ_PRESTADOR_CONTAS/VR_PAGTO_DESPESA), enquanto contratadas traz candidato,
# cargo, partido e ainda o fornecedor com nome RFB.
DESPESAS_COLUNAS = {
    "sq_candidato": "SQ_CANDIDATO",
    "nr_cpf": "NR_CPF_CANDIDATO",
    "nome": "NM_CANDIDATO",
    "cargo": "DS_CARGO",
    "uf": "SG_UF",
    "partido": "SG_PARTIDO",
    "dt_despesa": "DT_DESPESA",
    "valor": "VR_DESPESA_CONTRATADA",
    "tipo": "DS_DESPESA",
    "origem": "DS_ORIGEM_DESPESA",
    "cpf_cnpj_fornecedor": "NR_CPF_CNPJ_FORNECEDOR",
    "nome_fornecedor": "NM_FORNECEDOR",
    "nome_fornecedor_rfb": "NM_FORNECEDOR_RFB",
    "ano_eleicao": "AA_ELEICAO",
}


def checar_colunas(header: list[str], colunas: dict[str, str], rotulo: str) -> bool:
    """Loga quais colunas esperadas faltam no header real. True se todas presentes."""
    header_set = set(header)
    faltantes = [nome for nome in colunas.values() if nome not in header_set]
    if faltantes:
        print(f"  ! {rotulo}: colunas esperadas ausentes no CSV real: {faltantes}")
        print(f"    colunas disponíveis: {sorted(header_set)}")
        return False
    return True


def valor_num(raw: str | None) -> float:
    """'1234,56' (padrão TSE, vírgula decimal) → 1234.56. '' / None → 0.0."""
    if not raw:
        return 0.0
    try:
        return float(str(raw).strip().replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def baixar_zip_csv_brasil(
    url: str, sufixo_arquivo: str, rotulo: str, colunas: dict[str, str] | None = None
) -> list[dict] | None:
    """Baixa um ZIP do TSE Dados Abertos e devolve as linhas do CSV nacional
    consolidado (arquivo cujo nome termina em `sufixo_arquivo`, ex.:
    '_BRASIL.csv') como list[dict]. None em qualquer falha — fail-soft.

    `colunas`: dict de colunas esperadas (CAND_COLUNAS/BEM_COLUNAS/...) para
    `checar_colunas()`. Passar explicitamente — todo nome de arquivo do TSE
    contém "candidato" (consulta_cand, bem_candidato, receitas_candidatos...),
    então inferir o schema a partir de `rotulo` sempre bate com o schema
    errado (bug real: "bem_candidato" também contém a substring "cand").
    """
    try:
        resp = http_get(url, timeout=TIMEOUT)
    except Exception as e:  # noqa: BLE001 - curl_cffi tem hierarquia própria de erro
        print(f"  ! {rotulo}: falha de rede ao baixar {url}: {e}")
        return None
    if resp.status_code != 200:
        print(f"  ! {rotulo}: HTTP {resp.status_code} ao baixar {url}")
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            nomes = zf.namelist()
            alvo = next(
                (n for n in nomes if n.upper().endswith(sufixo_arquivo.upper())), None
            )
            if not alvo:
                print(f"  ! {rotulo}: nenhum arquivo terminado em {sufixo_arquivo!r} no zip.")
                print(f"    conteúdo do zip ({len(nomes)} arquivos): {nomes[:10]}")
                return None
            with zf.open(alvo) as f:
                text = io.TextIOWrapper(f, encoding=CSV_ENCODING, newline="")
                reader = csv.DictReader(text, delimiter=CSV_DELIMITER)
                linhas = list(reader)
    except (zipfile.BadZipFile, OSError, csv.Error) as e:  # noqa: BLE001
        print(f"  ! {rotulo}: falha ao ler o zip/csv: {e}")
        return None
    if not linhas:
        print(f"  ! {rotulo}: CSV vazio.")
        return None
    if colunas is not None:
        checar_colunas(list(linhas[0].keys()), colunas, rotulo)
    print(f"  ✓ {rotulo}: {len(linhas):,} linhas")
    return linhas


def col(row: dict, colunas: dict[str, str], campo: str) -> str:
    """Lê row[colunas[campo]] com fallback seguro para string vazia."""
    return (row.get(colunas[campo]) or "").strip()
