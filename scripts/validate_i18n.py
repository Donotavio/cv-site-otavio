#!/usr/bin/env python3
"""
Valida a paridade de chaves entre os dicionários de i18n (pt-BR / en-US / es-ES).
pt-BR.json é a fonte da verdade. Documentado em .opencode/skills/content-i18n.md.

Uso:
    python3 scripts/validate_i18n.py
Saída:
    lista chaves FALTANDO/EXTRA por idioma; exit != 0 se houver divergência.
"""

import json
import sys
from pathlib import Path


def flatten(obj, prefix=""):
    keys = set()
    for k, v in obj.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= flatten(v, full)
        else:
            keys.add(full)
    return keys


base = Path(__file__).resolve().parent.parent / "assets" / "i18n"
langs = ["pt-BR", "en-US", "es-ES"]
data = {l: flatten(json.loads((base / f"{l}.json").read_text(encoding="utf-8"))) for l in langs}
reference = data["pt-BR"]
errors = 0

for lang in langs[1:]:
    missing = reference - data[lang]
    extra = data[lang] - reference
    if missing:
        print(f"FALTANDO em {lang}:")
        for k in sorted(missing):
            print(f"  - {k}")
        errors += 1
    if extra:
        print(f"EXTRA em {lang} (não existe em pt-BR):")
        for k in sorted(extra):
            print(f"  + {k}")
        errors += 1

if not errors:
    print(f"✓ Paridade de i18n validada ({len(reference)} chaves em cada idioma).")
sys.exit(errors)
