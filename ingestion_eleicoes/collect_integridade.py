"""
Observatório Eleições 2026 — coleta de situação jurídica (integridade)
=====================================================================
Monta o roster de pré-candidatos (presidenciais + governadores) a partir dos
JSONs já produzidos pelo painel e consulta o TSE DivulgaCand, fonte oficial, a
situação de elegibilidade / processos por candidato.

Uso:
    python ingestion_eleicoes/collect_integridade.py

Saída:
    data/bronze/eleicoes_integridade/integridade_{YYYY}_{MM}_{DD}.parquet

Transparência / fail-soft: os dados oficiais POR CANDIDATO só passam a existir
após o registro das candidaturas (TSE publica certidões/elegibilidade a partir
de 15/08/2026). Enquanto TSE_DIVULGACAND_COD_ELEICAO estiver vazio no catálogo,
a consulta não roda e o roster é gravado com itens vazios — sem inferir nem
alegar nada sem fonte oficial. Nunca falha o pipeline por ausência de dado.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from ingestion_eleicoes.catalog import (  # noqa: E402
    INTEGRIDADE_ROSTER_ESTADUAL,
    INTEGRIDADE_ROSTER_PRESIDENCIAL,
    TSE_DIVULGACAND_API,
    TSE_DIVULGACAND_COD_ELEICAO,
)

BRONZE_DIR = Path("data/bronze/eleicoes_integridade")
TIMEOUT = 45
HEADERS = {
    "User-Agent": "observatorio-eleicoes-2026/1.0 (https://github.com/Donotavio/cv-site-otavio; integridade) requests",
}


def _carregar_roster() -> list[dict]:
    """Lê os pré-candidatos do painel (presidenciais + governadores por UF).

    Usa os nomes canônicos já normalizados pelos coletores anteriores, para que
    itens_por_candidato faça join com os cards do painel. Fail-soft: arquivo
    ausente ou malformado → apenas ignora aquela fonte.
    """
    roster: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def _add(nome: str, partido: str, cargo: str, uf: str) -> None:
        nome = (nome or "").strip()
        if not nome:
            return
        key = (nome.casefold(), cargo)
        if key in seen:
            return
        seen.add(key)
        roster.append({"nome": nome, "partido": (partido or "").strip(), "cargo": cargo, "uf": uf})

    pres = Path(INTEGRIDADE_ROSTER_PRESIDENCIAL)
    if pres.exists():
        try:
            data = json.loads(pres.read_text(encoding="utf-8"))
            for c in (data.get("primeiro_turno") or {}).get("candidatos", []) or []:
                _add(c.get("nome", ""), c.get("partido", ""), "presidente", "BR")
        except (ValueError, OSError) as e:  # noqa: BLE001
            print(f"  · roster presidencial indisponível: {e}")

    est = Path(INTEGRIDADE_ROSTER_ESTADUAL)
    if est.exists():
        try:
            data = json.loads(est.read_text(encoding="utf-8"))
            for uf, bloco in (data.get("estados") or {}).items():
                for c in ((bloco or {}).get("governador_1t") or {}).get("candidatos", []) or []:
                    _add(c.get("nome", ""), c.get("partido", ""), "governador", uf)
        except (ValueError, OSError) as e:  # noqa: BLE001
            print(f"  · roster estadual indisponível: {e}")

    return roster


def _mapear_itens(_data: dict) -> list[dict]:
    """Mapeia a resposta do DivulgaCand → lista de itens {estagio, descricao, ...}.

    O schema exato dos campos de elegibilidade/processos do DivulgaCand só é
    observável após o registro. Enquanto isso, mantém-se conservador: não emite
    item sem campo oficial correspondente. Finalizar o mapeamento quando a API
    responder com dados reais (pós-15/08/2026).
    """
    return []


def _consultar_tse(nome: str) -> list[dict]:
    """Consulta a situação de elegibilidade no TSE DivulgaCand (fonte oficial).

    Ativa somente quando TSE_DIVULGACAND_COD_ELEICAO está preenchido no catálogo
    (após o registro). Fail-soft: 404 / rede / JSON inválido → [].
    """
    if not TSE_DIVULGACAND_COD_ELEICAO:
        return []
    try:
        url = (
            f"{TSE_DIVULGACAND_API}/candidatura/buscar/{TSE_DIVULGACAND_COD_ELEICAO}"
            f"/2/BR/candidato/{quote(nome)}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return _mapear_itens(resp.json())
    except (requests.RequestException, ValueError):  # noqa: BLE001
        return []


def _save_bronze(rows: list[dict]) -> Path:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    now = datetime.now(timezone.utc)
    df = pd.DataFrame(rows)
    df["_ingest_ts"] = now.isoformat()
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRONZE_DIR / f"integridade_{now.year}_{now.month:02d}_{now.day:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy")
    return out_path


def main() -> int:
    print("🗳  Observatório Eleições 2026 — coleta de situação jurídica (integridade)")
    roster = _carregar_roster()
    if not roster:
        print("  ✗ roster vazio — rode collect_precandidatos / collect_estaduais antes.")
        return 1
    ativo = bool(TSE_DIVULGACAND_COD_ELEICAO)
    print(f"  · {len(roster)} pré-candidatos | consulta TSE DivulgaCand: {'ativa' if ativo else 'aguardando registro (15/08)'}")

    rows: list[dict] = []
    total_itens = 0
    for c in roster:
        itens = _consultar_tse(c["nome"])
        total_itens += len(itens)
        rows.append({**c, "itens": json.dumps(itens, ensure_ascii=False)})

    out_path = _save_bronze(rows)
    print(f"  ✓ {out_path} ({len(rows)} candidatos · {total_itens} itens)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
