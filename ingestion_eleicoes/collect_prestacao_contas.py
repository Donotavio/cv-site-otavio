"""
Observatório Eleições 2026 — coleta de prestação de contas (campanha)
=========================================================================
Baixa os datasets "Candidatos" (consulta_cand) e "Prestação de Contas
Eleitorais" (receitas + despesas pagas) do Portal de Dados Abertos do TSE
para 2026, filtra para presidente + governador (roster do painel) e soma
receitas/despesas por candidato — join por SQ_CANDIDATO.

Uso:
    python ingestion_eleicoes/collect_prestacao_contas.py

Saída:
    data/bronze/eleicoes_prestacao_contas/prestacao_contas_{YYYY}_{MM}_{DD}.parquet
    (schema: sq_candidato, cpf, nome_urna, cargo, uf, partido,
     receitas_total_rs, despesas_total_rs, n_doacoes,
     origem_breakdown [json], doador_rfb_divergencias [json],
     despesa_categorias [json: DS_ORIGEM_DESPESA por candidato],
     fornecedores_pj [json: só pessoa jurídica, agregado por CNPJ],
     cnae_breakdown [json: DS_CNAE_FORNECEDOR por candidato] —
     os três guardam a lista COMPLETA por candidato; top-N e agregado do
     roster são papel do gold)

SEM DADO REAL até o prazo da prestação de contas parcial
(PRESTACAO_PRAZO_PARCIAL, ver catalog.py) — antes disso o candidato nem
enviou a prestação, então "não encontrado" é o resultado correto, não uma
falha de coleta. Fail-soft do mesmo jeito que collect_patrimonio.py: falha de
download em qualquer arquivo não derruba o pipeline.
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
    CARGOS_ROSTER_PAINEL,
    PRESTACAO_ANO,
    TSE_CONSULTA_CAND_SUFIXO_BRASIL,
    TSE_CONSULTA_CAND_ZIP_URL_FMT,
    TSE_DESPESAS_SUFIXO_BRASIL,
    TSE_PRESTACAO_CONTAS_ZIP_URL_FMT,
    TSE_RECEITAS_SUFIXO_BRASIL,
)
from ingestion_eleicoes.tse_dados_abertos import (  # noqa: E402
    CAND_COLUNAS,
    DESPESAS_COLUNAS,
    RECEITAS_COLUNAS,
    TSE_MARCADORES_NULOS,
    baixar_zip_csv_brasil,
    col,
    lancamento_vazio,
    valor_num,
)

BRONZE_DIR = Path("data/bronze/eleicoes_prestacao_contas")
TOP_ORIGENS = 6
TOP_DIVERGENCIAS = 5


def _normalizar_nome(nome: str) -> str:
    """Caixa alta sem acento, pontuação nem espaço duplicado.

    Serve só para COMPARAR nomes (declarado × RFB) — o payload sempre guarda
    o texto original. Sem isso, acento e caixa viram "divergência" falsa.
    """
    base = unicodedata.normalize("NFKD", nome or "")
    base = "".join(c for c in base if not unicodedata.combining(c))
    base = re.sub(r"[^A-Za-z0-9 ]+", " ", base)
    return re.sub(r"\s+", " ", base).strip().upper()


def _origem_partidaria(origem: str) -> bool:
    """Doação vinda de partido/fundo: nome do órgão ≠ razão social na RFB por
    construção, então comparar os dois só gera ruído."""
    o = _normalizar_nome(origem)
    return "PARTIDO" in o or "FUNDO" in o


PARTICULAS = {"DE", "DA", "DO", "DAS", "DOS", "E"}


def _tokens_nome(nome: str) -> list[str]:
    return [t for t in _normalizar_nome(nome).split() if t not in PARTICULAS]


def _nome_diverge(declarado: str, rfb: str) -> bool:
    """True só quando os nomes são realmente incompatíveis.

    Absorve as três formas de "diferença" que o dado real do TSE produz sem
    que haja qualquer divergência de fato (verificado no CSV de 2026):
      1. acento/caixa/pontuação  → _normalizar_nome
      2. truncamento do NM_DOADOR (~32 chars) → prefixo
      3. abreviação do nome do meio ("JOSE M BORTOLI" = "JOSE MARIA BORTOLI")
         e partículas omitidas ("GONDIM" vs "DE GONDIM") → alinhamento de
         tokens em ordem, aceitando token abreviado como prefixo.
    Só o que não casa por nenhuma dessas regras é sinalizado — o objetivo é
    não insinuar irregularidade onde há apenas forma de cadastro diferente.
    """
    a, b = _normalizar_nome(declarado), _normalizar_nome(rfb)
    if not a or not b or a == b or a.startswith(b) or b.startswith(a):
        return False

    ta, tb = _tokens_nome(declarado), _tokens_nome(rfb)
    if not ta or not tb:
        return False
    # O nome mais curto costuma ser o declarado (abreviado/truncado); tenta
    # alinhá-lo, em ordem, contra o mais completo.
    curto, longo = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    i = 0
    for tok in curto:
        while i < len(longo) and not (longo[i].startswith(tok) or tok.startswith(longo[i])):
            i += 1
        if i == len(longo):
            return True  # sobrou token do nome curto sem correspondente
        i += 1
    return False


def _candidatos_roster() -> list[dict]:
    """Candidaturas de presidente/governador do ano corrente, com SQ_CANDIDATO."""
    url = TSE_CONSULTA_CAND_ZIP_URL_FMT.format(ano=PRESTACAO_ANO)
    linhas = baixar_zip_csv_brasil(
        url, TSE_CONSULTA_CAND_SUFIXO_BRASIL, "consulta_cand (prestação de contas)", colunas=CAND_COLUNAS
    )
    if linhas is None:
        return []
    return [row for row in linhas if col(row, CAND_COLUNAS, "cargo").upper() in CARGOS_ROSTER_PAINEL]


def _receitas_por_sq(sqs_interesse: set[str]) -> dict[str, dict]:
    """{SQ_CANDIDATO: {total, n, origens: {origem: (valor, n)}, divergencias: [...]}}"""
    url = TSE_PRESTACAO_CONTAS_ZIP_URL_FMT.format(ano=PRESTACAO_ANO)
    sufixo = TSE_RECEITAS_SUFIXO_BRASIL.format(ano=PRESTACAO_ANO)
    linhas = baixar_zip_csv_brasil(url, sufixo, "receitas_candidatos (prestação de contas)", colunas=RECEITAS_COLUNAS)
    if linhas is None:
        return {}

    out: dict[str, dict] = defaultdict(
        lambda: {"total": 0.0, "n": 0, "origens": defaultdict(lambda: [0.0, 0]), "divergencias": []}
    )
    for row in linhas:
        sq = col(row, RECEITAS_COLUNAS, "sq_candidato")
        if sq not in sqs_interesse:
            continue
        valor = valor_num(row.get(RECEITAS_COLUNAS["valor"]))
        origem_raw = col(row, RECEITAS_COLUNAS, "origem")
        # Relatório entregue sem receita a declarar não é uma doação de R$ 0.
        if lancamento_vazio(valor, origem_raw):
            continue
        origem = origem_raw or "não informado"
        d = out[sq]
        d["total"] += valor
        d["n"] += 1
        d["origens"][origem][0] += valor
        d["origens"][origem][1] += 1

        # Cruzamento doador × Receita Federal. Comparar os dois nomes crus
        # produz quase só falso positivo — verificado no dado real de 2026:
        # "Maria Angela de Magalhães Junque" vs "MARIA ANGELA DE MAGALHAES
        # JUNQUE" é a MESMA pessoa (acento + caixa + truncamento do TSE), e
        # doação de partido registra o órgão ("Direção Estadual - NOVO")
        # contra a razão social na RFB ("PARTIDO NOVO - MINAS GERAIS").
        # Num painel eleitoral, marcar isso como "divergência" insinua
        # irregularidade onde não há — então normalizamos agressivamente e
        # só sinalizamos o que sobra de fato diferente.
        if _origem_partidaria(origem):
            continue
        nome_declarado = col(row, RECEITAS_COLUNAS, "nome_doador")
        nome_rfb = col(row, RECEITAS_COLUNAS, "nome_doador_rfb")
        if nome_declarado and nome_rfb and _nome_diverge(nome_declarado, nome_rfb):
            d["divergencias"].append(
                {"doador": nome_declarado, "doador_rfb": nome_rfb, "valor_rs": round(valor, 2)}
            )
    return out


def _texto_limpo(raw: str) -> str:
    """Texto do TSE sem os marcadores de campo vazio ('#NULO' → '')."""
    texto = (raw or "").strip()
    return "" if texto.upper() in TSE_MARCADORES_NULOS else texto


def _apenas_digitos(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def _fornecedor_pj(cnpj_digits: str, tipo_fornecedor: str) -> bool:
    """Pessoa jurídica: CNPJ tem 14 dígitos (CPF tem 11); DS_TIPO_FORNECEDOR
    confirma como fallback quando o número vier truncado/mascarado."""
    if len(cnpj_digits) == 14:
        return True
    return "JURIDICA" in _normalizar_nome(tipo_fornecedor)


def _despesas_por_sq(sqs_interesse: set[str]) -> dict[str, dict]:
    """{SQ_CANDIDATO: {"total", "n", "categorias", "fornecedores_pj", "cnae"}}.

    `total`/`n` mantêm a semântica original. Os três breakdowns são aditivos e
    passam pelo MESMO filtro `lancamento_vazio` do total (linha-placeholder de
    relatório sem movimento não é despesa em nenhum agregado):
      categorias      {DS_ORIGEM_DESPESA: [valor, n]}
      fornecedores_pj {cnpj: {nome, nome_rfb, uf, valor, n}} — SÓ pessoa
                      jurídica; fornecedor pessoa física não é destacado
                      nominalmente pelo painel (recorte editorial), embora o
                      valor siga contado em total/categorias/cnae.
      cnae            {DS_CNAE_FORNECEDOR: [valor, n]} — só linhas com CNAE
                      preenchido; a cobertura é medida no gold.
    """
    url = TSE_PRESTACAO_CONTAS_ZIP_URL_FMT.format(ano=PRESTACAO_ANO)
    sufixo = TSE_DESPESAS_SUFIXO_BRASIL.format(ano=PRESTACAO_ANO)
    linhas = baixar_zip_csv_brasil(url, sufixo, "despesas_contratadas (prestação de contas)", colunas=DESPESAS_COLUNAS)
    if linhas is None:
        return {}

    out: dict[str, dict] = defaultdict(
        lambda: {
            "total": 0.0,
            "n": 0,
            "categorias": defaultdict(lambda: [0.0, 0]),
            "fornecedores_pj": {},
            "cnae": defaultdict(lambda: [0.0, 0]),
        }
    )
    for row in linhas:
        sq = col(row, DESPESAS_COLUNAS, "sq_candidato")
        if sq not in sqs_interesse:
            continue
        valor = valor_num(row.get(DESPESAS_COLUNAS["valor"]))
        # Relatório entregue sem despesa a declarar não é um gasto de R$ 0.
        if lancamento_vazio(valor, col(row, DESPESAS_COLUNAS, "tipo")):
            continue
        d = out[sq]
        d["total"] += valor
        d["n"] += 1

        origem = _texto_limpo(col(row, DESPESAS_COLUNAS, "origem")) or "não informada"
        c = d["categorias"][origem]
        c[0] += valor
        c[1] += 1

        cnpj = _apenas_digitos(col(row, DESPESAS_COLUNAS, "cpf_cnpj_fornecedor"))
        if cnpj and _fornecedor_pj(cnpj, col(row, DESPESAS_COLUNAS, "tipo_fornecedor")):
            f = d["fornecedores_pj"].setdefault(
                cnpj, {"nome": "", "nome_rfb": "", "uf": "", "valor": 0.0, "n": 0}
            )
            f["valor"] += valor
            f["n"] += 1
            if not f["nome"]:
                f["nome"] = _texto_limpo(col(row, DESPESAS_COLUNAS, "nome_fornecedor"))
            if not f["nome_rfb"]:
                f["nome_rfb"] = _texto_limpo(col(row, DESPESAS_COLUNAS, "nome_fornecedor_rfb"))
            if not f["uf"]:
                f["uf"] = _texto_limpo(col(row, DESPESAS_COLUNAS, "uf_fornecedor"))

        cnae = _texto_limpo(col(row, DESPESAS_COLUNAS, "cnae_fornecedor"))
        if cnae:
            k = d["cnae"][cnae]
            k[0] += valor
            k[1] += 1
    return dict(out)


def _coletar() -> list[dict]:
    candidatos = _candidatos_roster()
    if not candidatos:
        return []
    print(f"  · {PRESTACAO_ANO}: {len(candidatos)} candidaturas de presidente/governador")
    sqs = {col(c, CAND_COLUNAS, "sq_candidato") for c in candidatos}

    receitas = _receitas_por_sq(sqs)
    despesas = _despesas_por_sq(sqs)

    rows: list[dict] = []
    for c in candidatos:
        sq = col(c, CAND_COLUNAS, "sq_candidato")
        r = receitas.get(sq)
        d = despesas.get(sq)

        origem_breakdown: list[dict] = []
        divergencias: list[dict] = []
        receitas_total = 0.0
        n_doacoes = 0
        if r is not None:
            receitas_total = r["total"]
            n_doacoes = r["n"]
            top = sorted(r["origens"].items(), key=lambda kv: kv[1][0], reverse=True)[:TOP_ORIGENS]
            origem_breakdown = [{"origem": o, "valor_rs": round(v, 2), "n": n} for o, (v, n) in top]
            divergencias = sorted(r["divergencias"], key=lambda x: x["valor_rs"], reverse=True)[:TOP_DIVERGENCIAS]

        desp_total = 0.0
        n_desp = 0
        despesa_categorias: list[dict] = []
        fornecedores_pj: list[dict] = []
        cnae_breakdown: list[dict] = []
        if d is not None:
            desp_total = d["total"]
            n_desp = d["n"]
            despesa_categorias = [
                {"categoria": cat, "valor_rs": round(v, 2), "n": n}
                for cat, (v, n) in sorted(d["categorias"].items(), key=lambda kv: kv[1][0], reverse=True)
            ]
            fornecedores_pj = [
                {
                    "cnpj": cnpj,
                    "nome": f["nome"],
                    "nome_rfb": f["nome_rfb"],
                    "uf": f["uf"],
                    "valor_rs": round(f["valor"], 2),
                    "n": f["n"],
                }
                for cnpj, f in sorted(
                    d["fornecedores_pj"].items(), key=lambda kv: kv[1]["valor"], reverse=True
                )
            ]
            cnae_breakdown = [
                {"cnae": cnae, "valor_rs": round(v, 2), "n": n}
                for cnae, (v, n) in sorted(d["cnae"].items(), key=lambda kv: kv[1][0], reverse=True)
            ]

        rows.append(
            {
                "sq_candidato": sq,
                "cpf": col(c, CAND_COLUNAS, "nr_cpf"),
                "nome_urna": col(c, CAND_COLUNAS, "nome_urna"),
                "cargo": col(c, CAND_COLUNAS, "cargo"),
                "uf": col(c, CAND_COLUNAS, "uf"),
                "partido": col(c, CAND_COLUNAS, "partido"),
                "receitas_total_rs": receitas_total,
                "despesas_total_rs": desp_total,
                "n_doacoes": n_doacoes,
                "n_despesas": n_desp,
                "origem_breakdown": json.dumps(origem_breakdown, ensure_ascii=False),
                "doador_rfb_divergencias": json.dumps(divergencias, ensure_ascii=False),
                "despesa_categorias": json.dumps(despesa_categorias, ensure_ascii=False),
                "fornecedores_pj": json.dumps(fornecedores_pj, ensure_ascii=False),
                "cnae_breakdown": json.dumps(cnae_breakdown, ensure_ascii=False),
            }
        )
    return rows


def _save_bronze(rows: list[dict]) -> Path:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    now = datetime.now(timezone.utc)
    df = pd.DataFrame(rows)
    df["_ingest_ts"] = now.isoformat()
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRONZE_DIR / f"prestacao_contas_{now.year}_{now.month:02d}_{now.day:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    return out_path


def main() -> int:
    print("🗳  Observatório Eleições 2026 — coleta de prestação de contas (campanha)")
    rows = _coletar()

    if not rows:
        print("  ✗ nenhum dado coletado — provável bloqueio de rede ou prazo da prestação ainda não chegou.")
        # Fail-soft: grava bronze vazio (schema válido) em vez de abortar.
        rows = []

    out_path = _save_bronze(rows)
    com_receita = sum(1 for r in rows if r["receitas_total_rs"] > 0)
    print(f"  ✓ {out_path} ({len(rows)} candidatos no roster · {com_receita} com receita declarada)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
