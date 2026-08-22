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

    return _envelope(
        {
            "n_candidatos": len(candidatos),
            "n_com_receita": len(com_receita),
            "total_divergencias": total_divergencias,
            "candidatos": candidatos,
            "top_arrecadadores": top_arrecadadores,
            "top_gastadores": top_gastadores,
        }
    )


def _vazio() -> dict:
    return _envelope(
        {
            "n_candidatos": 0,
            "n_com_receita": 0,
            "total_divergencias": 0,
            "candidatos": [],
            "top_arrecadadores": [],
            "top_gastadores": [],
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
