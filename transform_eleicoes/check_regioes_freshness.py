"""
Observatório Eleições 2026 — Monitor de frescor + validador do bloco regional
=============================================================================
O mapa presidencial por região (§2) é CURADO À MÃO a partir de UMA pesquisa
citável (os números regionais só existem em imagem/PDF, então não há pipeline
que os colete com rigor). Este script NÃO coleta nem altera dados — ele só:

1. VALIDA o schema de `assets/data/eleicoes_presidencial_regioes.json`
   (regiões ↔ UFs completas, candidatos com %, metadados e fontes presentes).
2. Avisa se o dado está VELHO (`data_ref` além de STALE_DAYS) — a Quaest publica
   ~mensalmente, então um recorte antigo sinaliza que é hora de atualizar à mão.

Uso:
    python transform_eleicoes/check_regioes_freshness.py

Saída/return:
- Erros de schema  → exit 1 (algo quebrado no JSON curado; aparece vermelho no CI).
- Dado velho       → ⚠ no log, exit 0 (nag não-bloqueante).
- Tudo ok e fresco → exit 0.

Roda no CI com continue-on-error: nunca derruba o pipeline de dados.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

JSON_PATH = Path("assets/data/eleicoes_presidencial_regioes.json")

# Quaest publica ~mensalmente; além disto o recorte está defasado.
STALE_DAYS = 45

# 27 UFs — o mapa (brazil-states.svg) tem exatamente estas.
UFS_BRASIL = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
    "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
    "SE", "SP", "TO",
}

REQUIRED_KEYS = ["instituto", "data_ref", "cenario", "fonte", "fonte_url",
                 "disclaimer", "registro_tse", "ufs_por_regiao", "regioes"]


def _validate(d: dict) -> list[str]:
    """Retorna a lista de erros de schema (vazia = ok)."""
    errs: list[str] = []

    for k in REQUIRED_KEYS:
        if not d.get(k):
            errs.append(f"campo obrigatório ausente/vazio: '{k}'")

    regioes = d.get("regioes") or {}
    ufmap = d.get("ufs_por_regiao") or {}

    if set(regioes) != set(ufmap):
        errs.append(
            f"chaves de 'regioes' {sorted(regioes)} ≠ 'ufs_por_regiao' {sorted(ufmap)}"
        )

    # Cobertura das 27 UFs: sem faltar, sem duplicar, sem UF desconhecida.
    vistos: list[str] = []
    for rk, ufs in ufmap.items():
        if not isinstance(ufs, list) or not ufs:
            errs.append(f"região '{rk}': ufs_por_regiao deve ser lista não-vazia")
            continue
        vistos.extend(ufs)
    dup = sorted({u for u in vistos if vistos.count(u) > 1})
    if dup:
        errs.append(f"UF(s) em mais de uma região: {dup}")
    faltando = sorted(UFS_BRASIL - set(vistos))
    if faltando:
        errs.append(f"UF(s) sem região (mapa ficaria com buraco): {faltando}")
    desconhecidas = sorted(set(vistos) - UFS_BRASIL)
    if desconhecidas:
        errs.append(f"UF(s) desconhecida(s): {desconhecidas}")

    # Cada região precisa de candidatos com nome/partido/pct numérico plausível.
    for rk, r in regioes.items():
        if not r.get("nome"):
            errs.append(f"região '{rk}': falta 'nome'")
        cands = r.get("candidatos") or []
        if not cands:
            errs.append(f"região '{rk}': sem candidatos")
        for i, c in enumerate(cands):
            if not c.get("nome"):
                errs.append(f"região '{rk}' cand #{i}: falta 'nome'")
            if "partido" not in c:
                errs.append(f"região '{rk}' cand #{i}: falta 'partido'")
            pct = c.get("pct")
            if not isinstance(pct, (int, float)) or not (0 <= pct <= 100):
                errs.append(f"região '{rk}' cand '{c.get('nome')}': pct inválido ({pct!r})")

    return errs


def main() -> int:
    print("🗳  Observatório Eleições 2026 — validador + frescor do bloco regional")

    if not JSON_PATH.exists():
        print(f"  ✗ {JSON_PATH} não existe — bloco regional ausente.")
        return 1
    try:
        d = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"  ✗ JSON inválido: {e}")
        return 1

    errs = _validate(d)
    if errs:
        print(f"  ✗ {len(errs)} erro(s) de schema:")
        for e in errs:
            print(f"     · {e}")
        return 1
    n_reg = len(d.get("regioes") or {})
    print(f"  ✓ schema ok — {n_reg} regiões, 27 UFs cobertas, candidatos com % válidos")

    # ── Frescor ──────────────────────────────────────────────────────────
    try:
        ref = datetime.strptime(d["data_ref"], "%Y-%m-%d").date()
    except (ValueError, KeyError):
        print(f"  ✗ data_ref inválida: {d.get('data_ref')!r}")
        return 1
    idade = (date.today() - ref).days
    fonte = d.get("fonte_url", "(sem URL)")
    if idade > STALE_DAYS:
        print(f"  ⚠ DADO VELHO: recorte de {d['data_ref']} tem {idade} dias (> {STALE_DAYS}).")
        print(f"    Atualize à mão com a rodada mais recente. Fonte/checar: {fonte}")
        print(f"    (nag não-bloqueante — instituto={d.get('instituto')}, TSE {d.get('registro_tse')})")
    else:
        print(f"  ✓ fresco — {d['data_ref']} ({idade} dias; limite {STALE_DAYS}). Instituto: {d.get('instituto')}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
