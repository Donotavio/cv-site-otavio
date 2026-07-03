"""
Brasil Cockpit — Gold: cockpit + histórico
============================================
Lê data/silver/macro.parquet, deriva séries (balança comercial, saldo CAGED
12m), calcula status/delta/trend via ingestion_macro/catalog e grava:

    data/gold/cockpit.parquet   + assets/data/cockpit.json
    data/gold/historico.parquet + assets/data/historico.json

Full rebuild — sem argumentos. Status e trend vêm SEMPRE das funções do
catalog (compute_status / compute_trend) — nunca hardcodar bandas aqui.
Conversões de unidade (US$ mi→bi, pessoas→mil) aplicadas só na saída, depois
de status/trend (que usam valores brutos + targets brutos do catalog).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from ingestion_macro.catalog import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    KPI_META,
    TARGETS,
    UNIT_DIV_1000,
    UNIT_DIV_1000_K,
    compute_status,
    compute_trend,
)

GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")
SILVER_PATH = Path("data/silver/macro.parquet")

HISTORY_YEARS = 5


def _scale_for_display(kpi_id: str, value):
    """Converte valor bruto → unidade de exibição do KPI_META (mi→bi, pessoas→mil)."""
    if value is None or pd.isna(value):
        return None
    if kpi_id in UNIT_DIV_1000 or kpi_id in UNIT_DIV_1000_K:
        return float(value) / 1000.0
    return float(value)


def _build_derived(silver: pd.DataFrame) -> pd.DataFrame:
    """Séries derivadas: balança comercial e saldo CAGED 12m."""
    parts = []

    # balanca_comercial = exportações − importações (por mês)
    exp = (silver[silver.kpi_id == "exportacoes_fob"]
           [["data_referencia", "valor"]].rename(columns={"valor": "exp"}))
    imp = (silver[silver.kpi_id == "importacoes_fob"]
           [["data_referencia", "valor"]].rename(columns={"valor": "imp"}))
    if not exp.empty and not imp.empty:
        bal = exp.merge(imp, on="data_referencia", how="inner")
        bal["valor"] = bal["exp"] - bal["imp"]
        parts.append(bal[["data_referencia", "valor"]].assign(kpi_id="balanca_comercial"))

    # caged_saldo_12m = soma móvel 12 meses do saldo mensal do CAGED
    caged = (silver[silver.kpi_id == "caged_saldo"]
             .sort_values("data_referencia").reset_index(drop=True))
    if not caged.empty:
        caged = caged.copy()
        caged["valor"] = caged["valor"].rolling(window=12, min_periods=12).sum()
        caged12 = caged.dropna(subset=["valor"])[["data_referencia", "valor"]]
        caged12 = caged12.assign(kpi_id="caged_saldo_12m")
        parts.append(caged12)

    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["kpi_id", "data_referencia", "valor"]
    )


def main() -> int:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    if not SILVER_PATH.exists():
        raise RuntimeError("Silver macro.parquet ausente — rode silver_macro.py primeiro.")

    silver = pd.read_parquet(SILVER_PATH)
    silver["data_referencia"] = pd.to_datetime(silver["data_referencia"]).dt.normalize()

    derived = _build_derived(silver)
    all_series = pd.concat([silver[["kpi_id", "data_referencia", "valor"]], derived],
                           ignore_index=True)

    now_iso = datetime.now(timezone.utc).isoformat()

    # ── Cockpit: 1 linha/KPI ──────────────────────────────────────────────
    cockpit_rows = []
    for kpi_id, grp in all_series.groupby("kpi_id"):
        grp = grp.sort_values("data_referencia")
        if grp.empty:
            continue
        latest = grp.iloc[-1]
        prior = grp.iloc[-2] if len(grp) >= 2 else None

        valor_atual_raw = float(latest["valor"])
        valor_anterior_raw = float(prior["valor"]) if prior is not None else None

        delta_abs_raw = (valor_atual_raw - valor_anterior_raw
                         if valor_anterior_raw is not None else None)
        delta_pct = ((delta_abs_raw / valor_anterior_raw * 100.0)
                     if valor_anterior_raw not in (None, 0) else None)

        tgt = TARGETS.get(kpi_id, {})
        status = compute_status(kpi_id, valor_atual_raw)
        trend = compute_trend(kpi_id, delta_abs_raw)

        meta_raw = tgt.get("meta")
        banda_raw = tgt.get("banda")

        cockpit_rows.append({
            "kpi_id": kpi_id,
            "label": KPI_META.get(kpi_id, {}).get("label", kpi_id),
            "unit": KPI_META.get(kpi_id, {}).get("unit", ""),
            "category": KPI_META.get(kpi_id, {}).get("category", "outros"),
            "frequency": KPI_META.get(kpi_id, {}).get("frequency", ""),
            "description": KPI_META.get(kpi_id, {}).get("description", ""),
            "data_referencia": pd.Timestamp(latest["data_referencia"]).date().isoformat(),
            "valor_atual": _scale_for_display(kpi_id, valor_atual_raw),
            "valor_anterior": _scale_for_display(kpi_id, valor_anterior_raw),
            "delta_abs": _scale_for_display(kpi_id, delta_abs_raw),
            "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
            "status": status,
            "trend": trend,
            "meta": _scale_for_display(kpi_id, meta_raw),
            "banda": _scale_for_display(kpi_id, banda_raw),
            "direction": tgt.get("direction"),
            "threshold_trend": tgt.get("threshold_trend"),
        })

    cockpit_df = pd.DataFrame(cockpit_rows)
    # ordenar por categoria (CATEGORY_ORDER) e depois por kpi_id
    cat_rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    cockpit_df["_rank"] = cockpit_df["category"].map(lambda c: cat_rank.get(c, 99))
    cockpit_df = cockpit_df.sort_values(["_rank", "kpi_id"]).drop(columns="_rank").reset_index(drop=True)

    cockpit_path = GOLD_DIR / "cockpit.parquet"
    cockpit_df.to_parquet(cockpit_path, index=False)
    print(f"  ✓ {cockpit_path} ({len(cockpit_df)} KPIs)")

    # ── Histórico: série completa, últimos 5 anos no JSON ─────────────────
    cutoff = pd.Timestamp.now().normalize() - pd.DateOffset(years=HISTORY_YEARS)
    hist = all_series.copy()
    hist = hist[hist["data_referencia"] >= cutoff]
    hist["valor"] = hist.apply(lambda r: _scale_for_display(r["kpi_id"], r["valor"]), axis=1)
    hist = hist.dropna(subset=["valor"]).sort_values(["kpi_id", "data_referencia"])

    hist_path = GOLD_DIR / "historico.parquet"
    hist.to_parquet(hist_path, index=False)
    print(f"  ✓ {hist_path} ({len(hist)} pontos)")

    # ── JSON para o frontend (assets/data/) ───────────────────────────────
    kpis_json = json.loads(cockpit_df.to_json(orient="records"))

    cockpit_payload = {
        "gerado_em": now_iso,
        "categorias": CATEGORY_LABELS,
        "category_order": CATEGORY_ORDER,
        "kpis": kpis_json,
    }
    (FRONTEND_DIR / "cockpit.json").write_text(
        json.dumps(cockpit_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"  ✓ {FRONTEND_DIR / 'cockpit.json'}")

    hist_payload = {
        "gerado_em": now_iso,
        "janela_anos": HISTORY_YEARS,
        "series": {
            kpi_id: [
                {"data_referencia": pd.Timestamp(r["data_referencia"]).date().isoformat(),
                 "valor": r["valor"]}
                for _, r in g.iterrows()
            ]
            for kpi_id, g in hist.groupby("kpi_id")
        },
    }
    (FRONTEND_DIR / "historico.json").write_text(
        json.dumps(hist_payload, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"  ✓ {FRONTEND_DIR / 'historico.json'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
