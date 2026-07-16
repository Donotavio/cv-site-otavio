"""
Observatório Eleições 2026 — Gold: situação jurídica (integridade)
==================================================================
Lê o bronze do coletor de integridade e escreve o envelope consumido pela
seção [13] do painel: metodologia, disclaimer, estágios, fontes e
itens_por_candidato (agrupado por nome canônico).

Uso:
    python transform_eleicoes/gold_integridade.py

Saída:
    data/gold/eleicoes_integridade.parquet
    assets/data/eleicoes_integridade.json

Enquanto não há dado oficial por candidato (pré-registro), itens_por_candidato
sai vazio — o frontend mostra o arcabouço + links oficiais. Idempotente.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    INTEGRIDADE_DISCLAIMER,
    INTEGRIDADE_ESTAGIOS,
    INTEGRIDADE_FONTES,
    INTEGRIDADE_METODOLOGIA,
)

BRONZE_DIR = Path("data/bronze/eleicoes_integridade")
GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")


def _latest_bronze() -> Path:
    files = sorted(BRONZE_DIR.glob("integridade_*.parquet"))
    if not files:
        raise RuntimeError(
            "Nenhum bronze de integridade. Rode: python ingestion_eleicoes/collect_integridade.py"
        )
    return files[-1]


def _itens_por_candidato(df) -> dict[str, list[dict]]:
    ids_validos = {e["id"] for e in INTEGRIDADE_ESTAGIOS}
    out: dict[str, list[dict]] = {}
    for _, row in df.iterrows():
        nome = str(row.get("nome", "")).strip()
        if not nome:
            continue
        try:
            itens = json.loads(row.get("itens") or "[]")
        except (ValueError, TypeError):
            itens = []
        # Só emite candidatos com pelo menos 1 item válido e com fonte citável.
        limpos = [
            it for it in itens
            if isinstance(it, dict) and it.get("estagio") in ids_validos and it.get("descricao")
        ]
        if limpos:
            out[nome] = limpos
    return out


def main() -> int:
    print("🗳  Observatório Eleições 2026 — gold de situação jurídica (integridade)")
    try:
        bronze = _latest_bronze()
    except RuntimeError as e:
        print(f"  ✗ {e}")
        return 1

    import pandas as pd

    df = pd.read_parquet(bronze)
    itens_por_candidato = _itens_por_candidato(df)

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "metodologia": INTEGRIDADE_METODOLOGIA,
        "disclaimer": INTEGRIDADE_DISCLAIMER,
        "estagios": INTEGRIDADE_ESTAGIOS,
        "fontes": INTEGRIDADE_FONTES,
        "itens_por_candidato": itens_por_candidato,
    }

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
    df.drop(columns=[c for c in ("_ingest_ts",) if c in df.columns]).to_parquet(
        GOLD_DIR / "eleicoes_integridade.parquet", index=False
    )
    out_json = FRONTEND_DIR / "eleicoes_integridade.json"
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    n_cand = len(itens_por_candidato)
    print(f"  ✓ {out_json} ({n_cand} candidato(s) com itens · {len(df)} no roster)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
