"""
Observatório Eleições 2026 — coleta de situação de registro (integridade)
===========================================================================
Baixa o dataset "Candidatos" (consulta_cand) do Portal de Dados Abertos do
TSE, filtra para presidente + governador (roster do painel) e grava a
situação de registro (DEFERIDO / INDEFERIDO / SUB JUDICE / ...) declarada
pelo TSE — join por nome com os rosters já produzidos pelos outros coletores.

Uso:
    python ingestion_eleicoes/collect_integridade.py

Saída:
    data/bronze/eleicoes_integridade/integridade_{YYYY}_{MM}_{DD}.parquet

Fail-soft: o CDN do TSE (cdn.tse.jus.br) é conhecido por recusar conexões de
datacenter (confirmado bloqueado neste ambiente em ago/2026, ver
tse_dados_abertos.py). Se o download falhar, o bronze sai com itens vazios —
nunca falha o pipeline por ausência de dado, nunca infere situação sem fonte.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion_eleicoes.catalog import (  # noqa: E402
    ANO_ELEICAO_PRESIDENCIAL,
    CARGOS_ROSTER_PAINEL,
    INTEGRIDADE_ROSTER_ESTADUAL,
    INTEGRIDADE_ROSTER_PRESIDENCIAL,
    INTEGRIDADE_SITUACOES,
    TSE_CONSULTA_CAND_SUFIXO_BRASIL,
    TSE_CONSULTA_CAND_ZIP_URL_FMT,
)
from ingestion_eleicoes.tse_dados_abertos import (  # noqa: E402
    CAND_COLUNAS,
    baixar_zip_csv_brasil,
    col,
)

BRONZE_DIR = Path("data/bronze/eleicoes_integridade")


def _carregar_roster() -> list[dict]:
    """Lê os pré-candidatos do painel (presidenciais + governadores por UF).

    Usa os nomes canônicos já normalizados pelos coletores anteriores, para que
    o join por nome funicone com os cards do painel. Fail-soft: arquivo
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


def _situacao_id(valor_tse: str) -> str:
    """Mapeia DS_SITUACAO_CANDIDATURA (texto bruto do TSE) → id de INTEGRIDADE_SITUACOES.

    Usa startswith, não substring livre: "DEFERIDO" é substring de
    "INDEFERIDO", então um teste `m in v` classificaria erroneamente um
    candidato indeferido como deferido (bug real, pego em teste local antes
    de subir).
    """
    v = (valor_tse or "").strip().upper()
    for s in INTEGRIDADE_SITUACOES:
        if any(v.startswith(m) for m in s["match"]):
            return s["id"]
    return "outro"


def _nome_bate(nome_urna_tse: str, nome_completo_tse: str, roster_nome: str) -> bool:
    """Compara por substring (nome de urna costuma ser 1 token: 'LULA', 'TARCÍSIO')."""
    alvo = roster_nome.casefold()
    urna = (nome_urna_tse or "").casefold()
    completo = (nome_completo_tse or "").casefold()
    if not urna and not completo:
        return False
    return urna in alvo or alvo in urna or any(tok in completo for tok in alvo.split() if len(tok) > 3)


def _consultar_situacoes(roster: list[dict]) -> dict[str, dict]:
    """Baixa consulta_cand_2026, filtra presidente/governador e casa com o roster."""
    url = TSE_CONSULTA_CAND_ZIP_URL_FMT.format(ano=ANO_ELEICAO_PRESIDENCIAL)
    linhas = baixar_zip_csv_brasil(
        url, TSE_CONSULTA_CAND_SUFIXO_BRASIL, "consulta_cand (integridade)", colunas=CAND_COLUNAS
    )
    if linhas is None:
        return {}

    candidatos_tse = [
        row for row in linhas if col(row, CAND_COLUNAS, "cargo").upper() in CARGOS_ROSTER_PAINEL
    ]
    print(f"  · {len(candidatos_tse)} candidaturas de presidente/governador no CSV do TSE")

    resultado: dict[str, dict] = {}
    for r in roster:
        for row in candidatos_tse:
            nome_urna = col(row, CAND_COLUNAS, "nome_urna")
            nome_completo = col(row, CAND_COLUNAS, "nome")
            if not _nome_bate(nome_urna, nome_completo, r["nome"]):
                continue
            situacao_raw = col(row, CAND_COLUNAS, "situacao")
            resultado[r["nome"]] = {
                "situacao_id": _situacao_id(situacao_raw),
                "situacao_raw": situacao_raw,
                "partido_tse": col(row, CAND_COLUNAS, "partido"),
                "uf_tse": col(row, CAND_COLUNAS, "uf"),
            }
            break  # 1ª candidatura do TSE que bate com este nome do roster
    return resultado


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
    print("🗳  Observatório Eleições 2026 — coleta de situação de registro (integridade)")
    roster = _carregar_roster()
    if not roster:
        print("  ✗ roster vazio — rode collect_precandidatos / collect_estaduais antes.")
        return 1
    print(f"  · {len(roster)} pré-candidatos no roster do painel")

    situacoes = _consultar_situacoes(roster)

    rows: list[dict] = []
    for c in roster:
        info = situacoes.get(c["nome"])
        rows.append({**c, "info": json.dumps(info, ensure_ascii=False) if info else None})

    out_path = _save_bronze(rows)
    n_com_dado = sum(1 for r in rows if r["info"])
    print(f"  ✓ {out_path} ({len(rows)} candidatos no roster · {n_com_dado} com situação encontrada)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
