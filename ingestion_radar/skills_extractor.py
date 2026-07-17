"""
Data Stack Radar BR — Extração de skills via regex (taxonomia fixa)
=====================================================================
Aplica uma taxonomia de padrões regex pré-compilados (case-insensitive)
sobre o texto (título + descrição) de cada vaga, para identificar quais
ferramentas/tecnologias de dados são mencionadas.

Não usa NLP probabilístico nem LLM — apenas correspondência de padrões,
conforme constraint do projeto ("Sem componente de IA").

Uso (como módulo):
    from skills_extractor import extract_skills
    skills = extract_skills(job_title + " " + job_description)
"""

from __future__ import annotations

import re

# Taxonomia e universo de tools vêm do catálogo (fonte única). Re-exportados
# aqui por compatibilidade com quem já importava de `skills_extractor`.
from catalog import RAW_TAXONOMY, TOOL_TOPICS  # noqa: F401

# Compila tudo uma única vez no import — evita recompilar regex por vaga.
_COMPILED: dict[str, list[re.Pattern]] = {
    skill: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for skill, patterns in RAW_TAXONOMY.items()
}


def extract_skills(text: str) -> list[str]:
    """Retorna a lista de skills (chaves da taxonomia) encontradas em `text`."""
    if not text:
        return []
    found = []
    for skill, patterns in _COMPILED.items():
        if any(p.search(text) for p in patterns):
            found.append(skill)
    return found


def extract_skills_row(title: str, description: str) -> list[str]:
    return extract_skills(f"{title or ''} {description or ''}")
