"""
Observatório Eleições 2026 — Gold: prestação de contas (campanha)
=====================================================================
Lê o bronze de prestação de contas (receitas + despesas por candidato) e
produz o envelope da seção: ranking de arrecadação/gasto, saldo, e
divergências doador×Receita Federal quando o TSE publica os dois nomes.

Uso:
    python transform_eleicoes/gold_prestacao_contas.py
Saída:
    data/gold/eleicoes_prestacao_contas.parquet
    assets/data/eleicoes_prestacao_contas.json

SEM DADO REAL até o prazo da prestação de contas parcial (ver
PRESTACAO_PRAZO_PARCIAL em catalog.py) — até lá o bronze vem vazio e o JSON
sai com candidatos=[]; o frontend mostra o arcabouço + contagem regressiva
para o prazo, igual ao padrão já usado em patrimônio/integridade. Idempotente.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    PRESTACAO_ANO,
    PRESTACAO_DISCLAIMER,
    PRESTACAO_FONTES,
    PRESTACAO_METODOLOGIA,
    PRESTACAO_PRAZO_FINAL,
    PRESTACAO_PRAZO_PARCIAL,
)

BRONZE_DIR = Path("data/bronze/eleicoes_prestacao_contas")
GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")
TOP_N = 5

# ── Agregados do roster (aditivo) ───────────────────────────────────────────
TOP_CATEGORIAS = 8  # top categorias de gasto; o resto vira "Outras"
TOP_FORNECEDORES = 8  # top fornecedores PJ por valor (agregado por CNPJ)
TOP_CNAE = 6  # top setores CNAE por valor
# `gastos_por_cnae` só entra no payload se o CNAE do fornecedor estiver
# preenchido para pelo menos esta fração do VALOR das despesas do roster —
# abaixo disso o recorte setorial distorce mais do que informa.
CNAE_COBERTURA_MINIMA_PCT = 50.0
NOTA_FORNECEDORES = (
    "O ranking de fornecedores agrega por CNPJ e considera apenas pessoa "
    "jurídica. Fornecedor pessoa física não é destacado nominalmente pelo "
    "painel — não é figura pública —, mas seu valor segue contado nos totais "
    "por candidato e por categoria."
)


def _json_col(row, coluna: str) -> list:
    """Lê uma coluna JSON do bronze; [] se ausente/corrompida (bronze anterior
    a esta feature continua funcionando)."""
    raw = row.get(coluna) if hasattr(row, "get") else None
    if not isinstance(raw, str) or not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _latest_bronze() -> Path | None:
    files = sorted(BRONZE_DIR.glob("prestacao_contas_*.parquet"))
    return files[-1] if files else None


def _envelope(extra: dict) -> dict:
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "metodologia": PRESTACAO_METODOLOGIA,
        "disclaimer": PRESTACAO_DISCLAIMER,
        "fontes": PRESTACAO_FONTES,
        "ano": PRESTACAO_ANO,
        "prazo_parcial": PRESTACAO_PRAZO_PARCIAL,
        "prazo_final": PRESTACAO_PRAZO_FINAL,
        **extra,
    }


def _agg(df) -> dict:
    candidatos = []
    total_divergencias = 0
    total_despesas_roster = 0.0
    cat_valor: dict[str, float] = defaultdict(float)
    cat_n: dict[str, int] = defaultdict(int)
    forn: dict[str, dict] = {}
    cnae_valor: dict[str, float] = defaultdict(float)
    cnae_n: dict[str, int] = defaultdict(int)
    for _, row in df.iterrows():
        receitas = float(row.get("receitas_total_rs") or 0.0)
        despesas = float(row.get("despesas_total_rs") or 0.0)
        try:
            origem_breakdown = json.loads(row.get("origem_breakdown") or "[]")
        except (ValueError, TypeError):
            origem_breakdown = []
        try:
            divergencias = json.loads(row.get("doador_rfb_divergencias") or "[]")
        except (ValueError, TypeError):
            divergencias = []
        total_divergencias += len(divergencias)

        # Agregados do roster a partir dos breakdowns por candidato do bronze.
        total_despesas_roster += despesas
        for item in _json_col(row, "despesa_categorias"):
            cat_valor[item.get("categoria") or "não informada"] += float(item.get("valor_rs") or 0.0)
            cat_n[item.get("categoria") or "não informada"] += int(item.get("n") or 0)
        for item in _json_col(row, "fornecedores_pj"):
            cnpj = item.get("cnpj") or ""
            if not cnpj:
                continue
            f = forn.setdefault(
                cnpj,
                {"nome": "", "nome_rfb": "", "uf": "", "valor": 0.0, "n": 0, "n_candidatos": 0},
            )
            f["valor"] += float(item.get("valor_rs") or 0.0)
            f["n"] += int(item.get("n") or 0)
            f["n_candidatos"] += 1  # 1 entrada por candidato no bronze
            if not f["nome"]:
                f["nome"] = item.get("nome") or ""
            if not f["nome_rfb"]:
                f["nome_rfb"] = item.get("nome_rfb") or ""
            if not f["uf"]:
                f["uf"] = item.get("uf") or ""
        for item in _json_col(row, "cnae_breakdown"):
            cnae_valor[item.get("cnae") or ""] += float(item.get("valor_rs") or 0.0)
            cnae_n[item.get("cnae") or ""] += int(item.get("n") or 0)

        candidatos.append(
            {
                "nome_urna": row.get("nome_urna"),
                "cargo": row.get("cargo"),
                "uf": row.get("uf"),
                "partido": row.get("partido"),
                "receitas_total_rs": round(receitas, 2),
                "despesas_total_rs": round(despesas, 2),
                "saldo_rs": round(receitas - despesas, 2),
                "n_doacoes": int(row.get("n_doacoes") or 0),
                "n_despesas": int(row.get("n_despesas") or 0),
                "origem_breakdown": origem_breakdown,
                "doador_rfb_divergencias": divergencias,
            }
        )

    candidatos.sort(key=lambda c: c["receitas_total_rs"], reverse=True)
    com_receita = [c for c in candidatos if c["receitas_total_rs"] > 0]
    top_arrecadadores = com_receita[:TOP_N]
    top_gastadores = sorted(candidatos, key=lambda c: c["despesas_total_rs"], reverse=True)[:TOP_N]

    # Categorias de gasto (DS_ORIGEM_DESPESA): top N + resíduo "Outras".
    # Denominador do pct = soma das categorias (== total de despesas do
    # roster, já que todo lançamento real cai em exatamente uma categoria).
    total_categorias = sum(cat_valor.values())
    cats = sorted(cat_valor, key=lambda c: cat_valor[c], reverse=True)

    def _pct(valor: float) -> float:
        return round(valor / total_categorias * 100, 1) if total_categorias else 0.0

    despesas_categorias = [
        {"categoria": c, "valor_rs": round(cat_valor[c], 2), "n": cat_n[c], "pct": _pct(cat_valor[c])}
        for c in cats[:TOP_CATEGORIAS]
    ]
    resto = cats[TOP_CATEGORIAS:]
    if resto:
        v = sum(cat_valor[c] for c in resto)
        despesas_categorias.append(
            {"categoria": "Outras", "valor_rs": round(v, 2), "n": sum(cat_n[c] for c in resto), "pct": _pct(v)}
        )

    # Top fornecedores — só pessoa jurídica (ver NOTA_FORNECEDORES); o CNPJ é
    # a chave de agregação, mas o payload expõe o nome (preferindo o da RFB).
    top_fornecedores = [
        {
            "nome": f["nome_rfb"] or f["nome"] or "não identificado",
            "uf": f["uf"],
            "valor_rs": round(f["valor"], 2),
            "n_despesas": f["n"],
            "n_candidatos": f["n_candidatos"],
        }
        for f in sorted(forn.values(), key=lambda f: f["valor"], reverse=True)[:TOP_FORNECEDORES]
    ]

    extra = {
        "n_candidatos": len(candidatos),
        "n_com_receita": len(com_receita),
        "total_divergencias": total_divergencias,
        "candidatos": candidatos,
        "top_arrecadadores": top_arrecadadores,
        "top_gastadores": top_gastadores,
        "despesas_categorias": despesas_categorias,
        "top_fornecedores": top_fornecedores,
        "nota_fornecedores": NOTA_FORNECEDORES,
    }

    # Recorte setorial (CNAE do fornecedor) só quando a cobertura sustenta a
    # leitura; senão o bloco fica FORA do payload e a seção nem o mostra.
    cnae_total = sum(cnae_valor.values())
    cobertura_pct = round(cnae_total / total_categorias * 100, 1) if total_categorias else 0.0
    if cobertura_pct >= CNAE_COBERTURA_MINIMA_PCT:
        setores = sorted(cnae_valor, key=lambda s: cnae_valor[s], reverse=True)
        extra["cnae_cobertura_pct"] = cobertura_pct
        extra["gastos_por_cnae"] = [
            {"setor": s, "valor_rs": round(cnae_valor[s], 2), "pct": _pct(cnae_valor[s])}
            for s in setores[:TOP_CNAE]
        ]
    else:
        print(
            f"  · gastos_por_cnae omitido: CNAE preenchido em só {cobertura_pct}% "
            f"do valor das despesas (mínimo {CNAE_COBERTURA_MINIMA_PCT}%)"
        )

    return _envelope(extra)


def _vazio() -> dict:
    return _envelope(
        {
            "n_candidatos": 0,
            "n_com_receita": 0,
            "total_divergencias": 0,
            "candidatos": [],
            "top_arrecadadores": [],
            "top_gastadores": [],
            "despesas_categorias": [],
            "top_fornecedores": [],
            "nota_fornecedores": NOTA_FORNECEDORES,
        }
    )


def main() -> int:
    print("🗳  Observatório Eleições 2026 — gold de prestação de contas (campanha)")
    bronze = _latest_bronze()
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    if bronze is None:
        print("  ✗ nenhum bronze de prestação de contas — rode collect_prestacao_contas.py antes.")
        return 1

    import pandas as pd

    df = pd.read_parquet(bronze)
    payload = _agg(df) if not df.empty else _vazio()

    if not df.empty:
        df.drop(columns=[c for c in ("_ingest_ts",) if c in df.columns]).to_parquet(
            GOLD_DIR / "eleicoes_prestacao_contas.parquet", index=False
        )
    out_json = FRONTEND_DIR / "eleicoes_prestacao_contas.json"
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(
        f"  ✓ {out_json} ({payload['n_candidatos']} candidatos · "
        f"{payload['n_com_receita']} com receita declarada · {payload['total_divergencias']} divergências doador×RFB)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
