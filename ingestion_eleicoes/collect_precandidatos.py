"""
Observatório Eleições 2026 — Coleta de pré-candidatos + intenção (presidencial)
===============================================================================
Baixa o HTML renderizado do artigo da Wikipedia PT que agrega as pesquisas
presidenciais registradas no TSE, extrai as wikitables (1º e 2º turno) e grava
um snapshot bronze em formato LONG (uma linha por instituto × candidato).

Fonte (agregadora, apartidária): Wikipedia PT — "Pesquisas de opinião para a
eleição presidencial no Brasil em 2026". Cada pesquisa permanece atribuída ao
instituto/data de origem. Lê tudo do catálogo — nunca hardcodar aqui.

Uso:
    python ingestion_eleicoes/collect_precandidatos.py
Saída:
    data/bronze/eleicoes_precandidatos/precandidatos_AAAA_MM_DD.parquet
    (schema: instituto, dt_fim, ano, cenario, candidato, partido, pct, +_ingest_ts)

Fail-soft: tabela/linha/coluna fora do padrão é ignorada (não derruba o pipeline).
"""

from __future__ import annotations

import io
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from ingestion_eleicoes.catalog import (  # noqa: E402
    CANDIDATO_NORMALIZE,
    CENARIO_1T,
    CENARIO_2T,
    COL_IGNORAR,
    MESES_PT,
    META_COL_KEYS,
    WIKIPEDIA_API,
    WIKIPEDIA_PRESIDENCIAL_TITLE,
)

BRONZE_DIR = Path("data/bronze/eleicoes_precandidatos")
TIMEOUT = 60


def _baixar_html() -> str:
    """Baixa o HTML renderizado do artigo via API MediaWiki (action=parse)."""
    url = WIKIPEDIA_API + "?" + urllib.parse.urlencode(
        {
            "action": "parse",
            "page": WIKIPEDIA_PRESIDENCIAL_TITLE,
            "prop": "text",
            "format": "json",
            "formatversion": "2",
        }
    )
    resp = requests.get(
        url, headers={"User-Agent": "observatorio-eleicoes-2026/1.0"}, timeout=TIMEOUT
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"API MediaWiki: {data['error']}")
    return data["parse"]["text"]


def _ano_do_heading(tbl) -> int | None:
    """Ano da seção (heading mais próximo, subindo, que contenha 20XX)."""
    prevs = tbl.xpath("preceding::*[self::h2 or self::h3 or self::h4]")
    for h in reversed(prevs):
        m = re.search(r"\b(202[0-9])\b", h.text_content())
        if m:
            return int(m.group(1))
    return None


def _parse_dt_fim(cell: str, year: int | None) -> str | None:
    """Última data 'dd mmm' da célula ('10 Jul - 13 Jul' → AAAA-07-13)."""
    if not year:
        return None
    s = str(cell).lower()
    matches = re.findall(r"(\d{1,2})\s*[º°]?\s*(?:de\s+)?([a-zç]{3})", s)
    if not matches:
        return None
    d, mon = matches[-1]
    mm = MESES_PT.get(mon[:3])
    if not mm:
        return None
    try:
        return f"{year:04d}-{mm:02d}-{int(d):02d}"
    except ValueError:
        return None


def _col_names(df) -> list[str]:
    """Nomes de coluna no nível que carrega 'Nome PARTIDO' (nível 1 se MultiIndex)."""
    import pandas as pd

    if isinstance(df.columns, pd.MultiIndex):
        return [str(c) for c in df.columns.get_level_values(1)]
    return [str(c) for c in df.columns]


def _classificar_colunas(names: list[str]) -> tuple[dict, list[tuple[int, str]]]:
    """Devolve (meta_idx, cand_cols) — índices meta e (idx, 'Nome PARTIDO')."""
    meta_idx: dict[str, int] = {}
    cand_cols: list[tuple[int, str]] = []
    for ci, nm in enumerate(names):
        low = nm.lower()
        matched_meta = False
        for key, needle in META_COL_KEYS.items():
            if needle in low and key not in meta_idx:
                meta_idx[key] = ci
                matched_meta = True
                break
        if matched_meta:
            continue
        if any(k in low for k in COL_IGNORAR):
            continue
        if nm.startswith("Unnamed") or nm == "nan" or not nm.strip():
            continue
        # candidato: "Nome PARTIDO" (dois tokens ou mais)
        if len(nm.rsplit(" ", 1)) == 2:
            cand_cols.append((ci, nm))
    return meta_idx, cand_cols


def _linhas_da_tabela(df, meta_idx, cand_cols, cenario, year, pos) -> list[dict]:
    import pandas as pd

    rows: list[dict] = []
    for ri, (_, r) in enumerate(df.iterrows()):
        inst_raw = str(r.iloc[meta_idx["inst"]])
        if inst_raw == "nan" or "contratante" in inst_raw.lower():
            continue
        inst = re.sub(r"\[.*?\]", "", inst_raw).strip()  # remove refs [1]
        dt_fim = (
            _parse_dt_fim(r.iloc[meta_idx["data"]], year) if "data" in meta_idx else None
        )
        # id único da medição de origem (tabela × linha) — mantém juntos os dois
        # candidatos de um mesmo confronto de 2º turno.
        medicao_id = f"{pos}:{ri}"
        for ci, nm in cand_cols:
            val = str(r.iloc[ci]).replace("%", "").replace(",", ".").strip()
            if not re.match(r"^\d+(\.\d+)?$", val):
                continue
            nome_wiki, partido = nm.rsplit(" ", 1)
            nome = CANDIDATO_NORMALIZE.get(nome_wiki, nome_wiki)
            rows.append(
                {
                    "medicao_id": medicao_id,
                    "instituto": inst,
                    "dt_fim": dt_fim,
                    "ano": year,
                    "cenario": cenario,
                    "candidato": nome,
                    "partido": partido,
                    "pct": float(val),
                }
            )
    return rows


def _parse_html(html: str) -> list[dict]:
    import pandas as pd
    from lxml import html as lh

    doc = lh.fromstring(html)
    dfs = pd.read_html(io.StringIO(html))
    tables = doc.xpath("//table")  # mesma ordem/contagem que read_html

    rows: list[dict] = []
    for pos, tbl in enumerate(tables):
        if "wikitable" not in (tbl.get("class") or ""):
            continue
        if pos >= len(dfs):
            continue
        df = dfs[pos]
        if df.shape[1] < 6:
            continue
        meta_idx, cand_cols = _classificar_colunas(_col_names(df))
        if "inst" not in meta_idx or "data" not in meta_idx or not cand_cols:
            continue
        cenario = CENARIO_2T if len(cand_cols) == 2 else CENARIO_1T
        year = _ano_do_heading(tbl)
        rows.extend(_linhas_da_tabela(df, meta_idx, cand_cols, cenario, year, pos))
    return rows


def _save_bronze(rows: list[dict]) -> Path:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    now = datetime.now(timezone.utc)
    df = pd.DataFrame(rows)
    df["_ingest_ts"] = now.isoformat()

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = (
        BRONZE_DIR / f"precandidatos_{now.year}_{now.month:02d}_{now.day:02d}.parquet"
    )
    pq.write_table(
        pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy"
    )
    return out_path


def main() -> int:
    print("🗳  Observatório Eleições 2026 — coleta de pré-candidatos (Wikipedia)")
    try:
        html = _baixar_html()
    except (requests.RequestException, RuntimeError) as e:  # noqa: BLE001
        print(f"  ✗ falha ao baixar o artigo da Wikipedia: {e}")
        return 1

    rows = _parse_html(html)
    if not rows:
        print("  ✗ nenhuma linha extraída das wikitables — layout pode ter mudado.")
        return 1

    out_path = _save_bronze(rows)
    n_1t = sum(1 for r in rows if r["cenario"] == CENARIO_1T)
    n_2t = sum(1 for r in rows if r["cenario"] == CENARIO_2T)
    print(f"  ✓ {out_path} ({len(rows):,} linhas · 1º turno {n_1t:,} · 2º turno {n_2t:,})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
