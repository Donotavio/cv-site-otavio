"""
Observatório Eleições 2026 — Gold: patrimônio declarado (bens)
==================================================================
Lê o bronze de patrimônio (2026 + 2022, presidente/governador) e produz o
envelope da seção de patrimônio: total declarado por candidato em 2026,
comparação com 2022 quando o mesmo CPF concorreu nos dois anos (join por
CPF — o nome muda de grafia entre fontes, o CPF mascarado do TSE não).

Uso:
    python transform_eleicoes/gold_patrimonio.py
Saída:
    data/gold/eleicoes_patrimonio.parquet
    assets/data/eleicoes_patrimonio.json

Se o bronze vier vazio (download bloqueado nos dois anos), o JSON sai com
candidatos=[] — o frontend mostra o arcabouço + fontes, igual ao padrão já
usado em integridade. Idempotente.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    PATRIMONIO_ANO_ATUAL,
    PATRIMONIO_ANO_COMPARACAO,
    PATRIMONIO_DISCLAIMER,
    PATRIMONIO_FONTES,
    PATRIMONIO_METODOLOGIA,
)

BRONZE_DIR = Path("data/bronze/eleicoes_patrimonio")
GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")


def _latest_bronze() -> Path | None:
    files = sorted(BRONZE_DIR.glob("patrimonio_*.parquet"))
    return files[-1] if files else None


def _agg(df) -> dict:
    atual = {row["cpf"]: row for _, row in df[df["ano"] == PATRIMONIO_ANO_ATUAL].iterrows() if row.get("cpf")}
    comparacao = {
        row["cpf"]: row for _, row in df[df["ano"] == PATRIMONIO_ANO_COMPARACAO].iterrows() if row.get("cpf")
    }

    candidatos = []
    for cpf, row in atual.items():
        prev = comparacao.get(cpf)
        item = {
            "nome_urna": row["nome_urna"],
            "cargo": row["cargo"],
            "uf": row["uf"],
            "partido": row["partido"],
            "patrimonio_2026_rs": round(float(row["patrimonio_total_rs"]), 2),
            "n_bens_2026": int(row["n_bens"]),
            "tem_comparacao": prev is not None,
        }
        if prev is not None and float(prev["patrimonio_total_rs"]) > 0:
            p2022 = float(prev["patrimonio_total_rs"])
            p2026 = float(row["patrimonio_total_rs"])
            item["patrimonio_2022_rs"] = round(p2022, 2)
            item["variacao_pct"] = round((p2026 - p2022) / p2022 * 100, 1)
        else:
            item["tem_comparacao"] = False
        candidatos.append(item)

    candidatos.sort(key=lambda c: c["patrimonio_2026_rs"], reverse=True)
    com_comparacao = [c for c in candidatos if c["tem_comparacao"]]
    maior_alta = sorted(com_comparacao, key=lambda c: c["variacao_pct"], reverse=True)[:5]
    maior_queda = sorted(com_comparacao, key=lambda c: c["variacao_pct"])[:5]

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "metodologia": PATRIMONIO_METODOLOGIA,
        "disclaimer": PATRIMONIO_DISCLAIMER,
        "fontes": PATRIMONIO_FONTES,
        "ano_atual": PATRIMONIO_ANO_ATUAL,
        "ano_comparacao": PATRIMONIO_ANO_COMPARACAO,
        "n_candidatos": len(candidatos),
        "n_com_comparacao": len(com_comparacao),
        "candidatos": candidatos,
        "maior_alta": maior_alta,
        "maior_queda": maior_queda,
    }


def _vazio() -> dict:
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "metodologia": PATRIMONIO_METODOLOGIA,
        "disclaimer": PATRIMONIO_DISCLAIMER,
        "fontes": PATRIMONIO_FONTES,
        "ano_atual": PATRIMONIO_ANO_ATUAL,
        "ano_comparacao": PATRIMONIO_ANO_COMPARACAO,
        "n_candidatos": 0,
        "n_com_comparacao": 0,
        "candidatos": [],
        "maior_alta": [],
        "maior_queda": [],
    }


def main() -> int:
    print("🗳  Observatório Eleições 2026 — gold de patrimônio declarado (bens)")
    bronze = _latest_bronze()
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    if bronze is None:
        print("  ✗ nenhum bronze de patrimônio — rode collect_patrimonio.py antes.")
        return 1

    import pandas as pd

    df = pd.read_parquet(bronze)
    payload = _agg(df) if not df.empty else _vazio()

    if not df.empty:
        df.drop(columns=[c for c in ("_ingest_ts",) if c in df.columns]).to_parquet(
            GOLD_DIR / "eleicoes_patrimonio.parquet", index=False
        )
    out_json = FRONTEND_DIR / "eleicoes_patrimonio.json"
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(
        f"  ✓ {out_json} ({payload['n_candidatos']} candidatos · "
        f"{payload['n_com_comparacao']} com comparação {PATRIMONIO_ANO_COMPARACAO}→{PATRIMONIO_ANO_ATUAL})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
