"""
Observatório Eleições 2026 — Gold: situação de registro (integridade)
========================================================================
Lê o bronze do coletor de integridade e escreve o envelope consumido pela
seção [13] do painel: metodologia, disclaimer, situações possíveis, fontes e
itens_por_candidato (agrupado por nome canônico).

Uso:
    python transform_eleicoes/gold_integridade.py

Saída:
    data/gold/eleicoes_integridade.parquet
    assets/data/eleicoes_integridade.json

Enquanto o download do TSE falhar (bloqueio de rede — ver
tse_dados_abertos.py), itens_por_candidato sai vazio e o frontend mostra o
arcabouço + links oficiais, igual antes. Idempotente.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    INTEGRIDADE_DISCLAIMER,
    INTEGRIDADE_FONTES,
    INTEGRIDADE_METODOLOGIA,
    INTEGRIDADE_SITUACOES,
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


def _itens_por_candidato(df) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for _, row in df.iterrows():
        nome = str(row.get("nome", "")).strip()
        info_raw = row.get("info")
        if not nome or not info_raw or (isinstance(info_raw, float)):  # NaN do parquet
            continue
        try:
            info = json.loads(info_raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(info, dict) or not info.get("situacao_id"):
            continue
        out[nome] = info
    return out


def main() -> int:
    print("🗳  Observatório Eleições 2026 — gold de situação de registro (integridade)")
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
        "situacoes": [{"id": s["id"], "label": s["label"]} for s in INTEGRIDADE_SITUACOES],
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
    print(f"  ✓ {out_json} ({n_cand} candidato(s) com situação · {len(df)} no roster)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
