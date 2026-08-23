"""
Observatório Eleições 2026 — Gold: perfil das candidaturas
=============================================================
Lê o bronze de candidaturas (consulta_cand 2026, todos os cargos) e produz o
envelope demográfico do painel: gênero, cor/raça, grau de instrução, faixa
etária (idade no 1º turno), ocupações, cargo e UF — no MESMO formato
{label, n, pct} do eleicoes_eleitorado.json, para o frontend cruzar os dois
perfis lado a lado (candidaturas × eleitorado).

Uso:
    python transform_eleicoes/gold_candidaturas.py
Saída:
    data/gold/eleicoes_candidaturas.parquet   (nível candidatura, com idade/faixa)
    assets/data/eleicoes_candidaturas.json    (agregados + envelope)

Sem bronze → exit 1 (rodar collect_candidaturas.py antes). Bronze existente
nunca é sobrescrito por vazio: o coletor só grava bronze quando o download
funciona, então o gold sempre agrega o último snapshot bom. Idempotente.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import ANO_ELEICAO_PRESIDENCIAL  # noqa: E402

BRONZE_DIR = Path("data/bronze/eleicoes_candidaturas")
GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")

# Referência do eleitorado para a nota de comparação (leitura fail-soft — o
# número entra na frase pronta; se o arquivo faltar, usa o fallback).
ELEITORADO_JSON = FRONTEND_DIR / "eleicoes_eleitorado.json"

# ── Constantes editoriais do bloco (ficam aqui, não no catálogo: catalog.py
# está em edição paralela por outra frente e estas são de uso exclusivo deste
# gold) ──────────────────────────────────────────────────────────────────────
CANDIDATURAS_FONTE = "TSE — Portal de Dados Abertos, consulta_cand 2026"
CANDIDATURAS_FONTE_URL = "https://dadosabertos.tse.jus.br/dataset/candidatos-2026"
CANDIDATURAS_METODOLOGIA = (
    "Contagem simples de todas as candidaturas do arquivo nacional consolidado "
    "consulta_cand 2026 do TSE (todos os cargos, incluindo vices e suplentes), "
    "agregada por gênero, cor/raça, grau de instrução, faixa etária (idade em "
    "04/10/2026, data do 1º turno), ocupação declarada, cargo e UF. Candidaturas "
    "a presidente e vice-presidente têm âmbito nacional e aparecem com UF 'BR'."
)
CANDIDATURAS_DISCLAIMER = (
    "Dados autodeclarados pelas próprias candidaturas no pedido de registro ao "
    "TSE. Em agosto de 2026 o TSE publica a situação de registro como campo não "
    "preenchido (#NE) para todas as candidaturas — o universo inclui, portanto, "
    "candidaturas que ainda aguardam julgamento, e os totais podem mudar conforme "
    "os registros forem deferidos ou indeferidos."
)

# Data do 1º turno de 2026 — referência para o cálculo de idade.
DATA_PRIMEIRO_TURNO = date(2026, 10, 4)

# Faixas etárias do perfil do eleitorado (eleicoes_eleitorado.json), menos a
# 16–17: idade mínima de elegibilidade impede candidatura antes dos 18. O
# rótulo usa en dash (–), igual ao eleitorado, para o cruzamento por label.
FAIXAS_ETARIAS = [
    ("18–24", 18, 24),
    ("25–34", 25, 34),
    ("35–44", 35, 44),
    ("45–59", 45, 59),
    ("60–69", 60, 69),
    ("70+", 70, 999),
]

# Ordem canônica de escolaridade — a MESMA do bloco `escolaridade` do
# eleitorado. Os rótulos do consulta_cand, após .title(), coincidem 1:1 com os
# do eleitorado (confirmado contra o CSV real de 2026); "Analfabeto" não
# ocorre entre candidaturas (alfabetização é condição de elegibilidade).
# Rótulo fora desta lista é anexado ao final, com aviso no log.
GRAU_INSTRUCAO_ORDEM = [
    "Analfabeto",
    "Lê E Escreve",
    "Ensino Fundamental Incompleto",
    "Ensino Fundamental Completo",
    "Ensino Médio Incompleto",
    "Ensino Médio Completo",
    "Superior Incompleto",
    "Superior Completo",
    "Não Informado",
]

TOP_OCUPACOES_N = 10
# O TSE tem a ocupação própria "OUTROS" (a mais frequente do arquivo); o
# rótulo do resíduo do top-10 precisa ser distinto dela para não fundir as
# duas coisas no gráfico.
OCUPACOES_RESIDUO_LABEL = "Demais ocupações"


def _latest_bronze() -> Path | None:
    files = sorted(BRONZE_DIR.glob("candidaturas_*.parquet"))
    return files[-1] if files else None


def _pct(n: int, total: int) -> float:
    return round(n / total * 100, 1) if total else 0.0


def _bloco_contagem(serie, total: int) -> list[dict]:
    """value_counts → [{label, n, pct}] em ordem decrescente de n (formato do eleitorado)."""
    return [
        {"label": str(label).title(), "n": int(n), "pct": _pct(int(n), total)}
        for label, n in serie.value_counts().items()
    ]


def _bloco_grau_instrucao(serie, total: int) -> list[dict]:
    """Como _bloco_contagem, mas na ordem canônica de escolaridade do eleitorado."""
    contagem = {str(label).title(): int(n) for label, n in serie.value_counts().items()}
    fora_da_ordem = [lb for lb in contagem if lb not in GRAU_INSTRUCAO_ORDEM]
    if fora_da_ordem:
        print(f"  ! grau de instrução fora da ordem canônica (anexado ao final): {fora_da_ordem}")
    ordem = [lb for lb in GRAU_INSTRUCAO_ORDEM if lb in contagem] + fora_da_ordem
    return [{"label": lb, "n": contagem[lb], "pct": _pct(contagem[lb], total)} for lb in ordem]


def _idade_em(nascimento: date | None, referencia: date) -> int | None:
    if nascimento is None:
        return None
    idade = referencia.year - nascimento.year
    if (referencia.month, referencia.day) < (nascimento.month, nascimento.day):
        idade -= 1
    return idade


def _faixa_etaria(idade: int | None) -> str:
    if idade is None:
        return "Não Informado"
    for label, lo, hi in FAIXAS_ETARIAS:
        if lo <= idade <= hi:
            return label
    # Idade < 18 seria dado sujo (elegibilidade mínima é 18) — não inventar
    # faixa: agrupa como não informado e o log de faixas acusa o volume.
    return "Não Informado"


def _bloco_faixa_etaria(df, total: int) -> list[dict]:
    contagem = df["faixa_etaria"].value_counts().to_dict()
    ordem = [label for label, _, _ in FAIXAS_ETARIAS] + ["Não Informado"]
    return [
        {"label": lb, "n": int(contagem[lb]), "pct": _pct(int(contagem[lb]), total)}
        for lb in ordem
        if lb in contagem
    ]


def _bloco_ocupacoes(serie, total: int) -> list[dict]:
    contagem = serie.value_counts()
    top = contagem.head(TOP_OCUPACOES_N)
    bloco = [
        {"label": str(label).title(), "n": int(n), "pct": _pct(int(n), total)}
        for label, n in top.items()
    ]
    resto = int(contagem.iloc[TOP_OCUPACOES_N:].sum())
    if resto:
        bloco.append({"label": OCUPACOES_RESIDUO_LABEL, "n": resto, "pct": _pct(resto, total)})
    return bloco


def _bloco_por_cargo(df, total: int) -> list[dict]:
    bloco = []
    for cargo, grupo in df.groupby("cargo"):
        n = len(grupo)
        bloco.append(
            {
                "label": str(cargo).title(),
                "n": n,
                "pct": _pct(n, total),
                "pct_feminino": _pct(int((grupo["genero"] == "FEMININO").sum()), n),
                "pct_negros": _pct(int(grupo["cor_raca"].isin(["PRETA", "PARDA"]).sum()), n),
            }
        )
    bloco.sort(key=lambda item: item["n"], reverse=True)
    return bloco


def _bloco_por_uf(df, total: int) -> list[dict]:
    return [
        {"uf": str(uf), "n": int(n), "pct": _pct(int(n), total)}
        for uf, n in df["uf"].value_counts().items()
    ]


def _pct_feminino_eleitorado() -> float | None:
    """% Feminino do perfil do eleitorado, para a nota de comparação. Fail-soft."""
    try:
        data = json.loads(ELEITORADO_JSON.read_text(encoding="utf-8"))
        for item in data.get("genero", []) or []:
            if str(item.get("label", "")).strip().casefold() == "feminino":
                return float(item["pct"])
    except (OSError, ValueError, KeyError, TypeError) as e:  # noqa: BLE001
        print(f"  · eleitorado indisponível p/ nota de comparação: {e}")
    return None


def _nota_comparacao(pct_fem_cand: float) -> str:
    pct_fem_ele = _pct_feminino_eleitorado()
    ele_txt = f"{pct_fem_ele}%" if pct_fem_ele is not None else "cerca de 53%"
    return (
        f"Comparação-chave com o perfil do eleitorado: mulheres são {pct_fem_cand}% "
        f"das candidaturas registradas para 2026, ante {ele_txt} do eleitorado apto "
        "a votar. Os demais recortes (cor/raça, grau de instrução, faixa etária) "
        "usam o mesmo formato do perfil do eleitorado para leitura lado a lado."
    )


def _agg(df) -> dict:
    total = len(df)
    genero = _bloco_contagem(df["genero"], total)
    pct_fem = next((g["pct"] for g in genero if g["label"] == "Feminino"), 0.0)

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": CANDIDATURAS_FONTE,
        "fonte_url": CANDIDATURAS_FONTE_URL,
        "metodologia": CANDIDATURAS_METODOLOGIA,
        "disclaimer": CANDIDATURAS_DISCLAIMER,
        "nota_comparacao": _nota_comparacao(pct_fem),
        "ano_eleicao": ANO_ELEICAO_PRESIDENCIAL,
        "total_candidaturas": total,
        "genero": genero,
        "cor_raca": _bloco_contagem(df["cor_raca"], total),
        "grau_instrucao": _bloco_grau_instrucao(df["grau_instrucao"], total),
        "faixa_etaria": _bloco_faixa_etaria(df, total),
        "top_ocupacoes": _bloco_ocupacoes(df["ocupacao"], total),
        "por_cargo": _bloco_por_cargo(df, total),
        "por_uf": _bloco_por_uf(df, total),
    }


def main() -> int:
    print("🗳  Observatório Eleições 2026 — gold do perfil das candidaturas")
    bronze = _latest_bronze()
    if bronze is None:
        print("  ✗ nenhum bronze de candidaturas — rode collect_candidaturas.py antes.")
        return 1

    import pandas as pd

    df = pd.read_parquet(bronze)
    if df.empty:
        # Não deveria ocorrer (o coletor não grava bronze vazio) — proteger o
        # JSON publicado de ser sobrescrito por um universo zerado.
        print(f"  ✗ bronze vazio ({bronze}) — mantendo o JSON existente.")
        return 1
    print(f"  · bronze: {bronze} ({len(df):,} candidaturas)")

    # Idade na data do 1º turno + faixa etária (derivadas, viram coluna do gold).
    nascimento = pd.to_datetime(df["dt_nascimento"], format="%d/%m/%Y", errors="coerce")
    n_invalidas = int(nascimento.isna().sum())
    if n_invalidas:
        print(f"  ! {n_invalidas} datas de nascimento não parseáveis → faixa 'Não Informado'")
    df["idade"] = [
        _idade_em(dt.date() if pd.notna(dt) else None, DATA_PRIMEIRO_TURNO) for dt in nascimento
    ]
    df["faixa_etaria"] = df["idade"].map(_faixa_etaria)

    payload = _agg(df)

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
    df.drop(columns=[c for c in ("_ingest_ts",) if c in df.columns]).to_parquet(
        GOLD_DIR / "eleicoes_candidaturas.parquet", index=False
    )
    out_json = FRONTEND_DIR / "eleicoes_candidaturas.json"
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    pct_fem = next((g["pct"] for g in payload["genero"] if g["label"] == "Feminino"), 0.0)
    pct_negros = round(
        sum(c["n"] for c in payload["cor_raca"] if c["label"] in ("Preta", "Parda"))
        / payload["total_candidaturas"]
        * 100,
        1,
    )
    print(
        f"  ✓ {out_json} ({payload['total_candidaturas']:,} candidaturas · "
        f"{pct_fem}% feminino · {pct_negros}% pretos+pardos · "
        f"{len(payload['por_cargo'])} cargos · {len(payload['por_uf'])} UFs)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
