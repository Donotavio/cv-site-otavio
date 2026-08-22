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
from typing import Iterable

import requests

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
    "situacao_detalhe": "DS_DETALHE_SITUACAO_CAND",
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

# Nomes oficiais de coluna do padrão TSE (receitas_candidatos). Diferente de
# CAND_COLUNAS/BEM_COLUNAS (confirmados em execuções anteriores desta sessão
# contra o schema estável do TSE), estes nomes NÃO foram confirmados contra
# um CSV real — o bloqueio de rede (ver docstring do módulo) impediu inspecionar
# o header do prestação de contas 2026 antes do prazo de registro (13/09/2026).
# São o melhor palpite a partir do padrão TSE conhecido de ciclos anteriores;
# `checar_colunas()` loga o header real na primeira execução em CI para ajuste.
RECEITAS_COLUNAS = {
    "sq_candidato": "SQ_CANDIDATO",
    "nr_cpf": "NR_CPF_CANDIDATO",
    "nome_urna": "NM_URNA_CANDIDATO",
    "cargo": "DS_CARGO",
    "uf": "SG_UF",
    "partido": "SG_PARTIDO",
    "dt_receita": "DT_RECEITA",
    "valor": "VR_RECEITA",
    "origem": "DS_ORIGEM_RECEITA",
    "cpf_cnpj_doador": "NR_CPF_CNPJ_DOADOR",
    "nome_doador": "NM_DOADOR",
    "nome_doador_rfb": "NM_DOADOR_RFB",
    "ano_eleicao": "ANO_ELEICAO",
}

# Nomes oficiais de coluna do padrão TSE (despesas_pagas_candidatos). Mesma
# ressalva de RECEITAS_COLUNAS acima — não confirmado contra CSV real.
DESPESAS_COLUNAS = {
    "sq_candidato": "SQ_CANDIDATO",
    "nr_cpf": "NR_CPF_CANDIDATO",
    "nome_urna": "NM_URNA_CANDIDATO",
    "cargo": "DS_CARGO",
    "uf": "SG_UF",
    "partido": "SG_PARTIDO",
    "dt_pagamento": "DT_PAGAMENTO",
    "valor": "VR_PAGAMENTO",
    "tipo": "DS_DESPESA",
    "cpf_cnpj_fornecedor": "NR_CPF_CNPJ_FORNECEDOR",
    "nome_fornecedor": "NM_FORNECEDOR",
    "ano_eleicao": "ANO_ELEICAO",
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
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as e:  # noqa: BLE001
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
