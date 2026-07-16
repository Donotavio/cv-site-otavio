"""
Observatório Eleições 2026 — Coleta ESTADUAL (governador + senador)
===================================================================
Baixa os artigos por UF da Wikipedia PT ("Pesquisas eleitorais para a eleição
estadual de 2026 {sufixo}"), extrai as wikitables de governador (1º/2º turno) e
senador e grava um bronze em formato LONG (uma linha por UF × instituto ×
candidato). Reaproveita helpers do coletor presidencial.

Fonte (agregadora, apartidária): Wikipedia PT (agrega pesquisas registradas no
TSE). Lê tudo do catálogo — nunca hardcodar aqui.

Uso:
    python ingestion_eleicoes/collect_estaduais.py
Saída:
    data/bronze/eleicoes_estaduais/estaduais_AAAA_MM_DD.parquet
    (schema: uf, medicao_id, instituto, dt_fim, ano, cargo, candidato, partido, pct)

Fail-soft: UF sem artigo (DF/MS/MT) ou tabela fora do padrão é pulada. Throttle
entre estados evita HTTP 429.
"""

from __future__ import annotations

import io
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from ingestion_eleicoes.catalog import (  # noqa: E402
    CANDIDATO_NORMALIZE,
    COL_IGNORAR,
    ESTADUAL_THROTTLE_S,
    META_COL_KEYS,
    UF_ARTIGO_SUFIXO,
    WIKIPEDIA_API,
    WIKIPEDIA_ESTADUAL_TITLE_FMT,
    cargo_do_heading,
    split_nome_partido,
)
from ingestion_eleicoes.collect_precandidatos import (  # noqa: E402
    _ano_do_heading,
    _col_names,
    _parse_dt_fim,
)

BRONZE_DIR = Path("data/bronze/eleicoes_estaduais")
TIMEOUT = 60


HEADERS = {
    "User-Agent": (
        "observatorio-eleicoes-2026/1.0 "
        "(https://github.com/Donotavio/cv-site-otavio; estaduais) requests"
    )
}
MAX_RETRIES = 4


def _baixar_html(title: str) -> str | None:
    """HTML renderizado do artigo (None se ausente/404). Retenta em 429/5xx."""
    url = WIKIPEDIA_API + "?" + urllib.parse.urlencode(
        {"action": "parse", "page": title, "prop": "text", "format": "json", "formatversion": "2"}
    )
    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 404:
            return None
        if resp.status_code in (429, 503) and attempt < MAX_RETRIES:
            wait = int(resp.headers.get("Retry-After", 0) or 0) or attempt * 5
            print(f"    ↻ {resp.status_code} — aguardando {wait}s (tentativa {attempt}/{MAX_RETRIES})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:  # página inexistente
            return None
        return data["parse"]["text"]
    return None


def _cargo_da_tabela(tbl) -> str | None:
    """Cargo pelo heading classificável mais próximo (subindo h2/h3/h4)."""
    prevs = tbl.xpath("preceding::*[self::h2 or self::h3 or self::h4]")
    for h in reversed(prevs):
        cargo = cargo_do_heading(h.text_content())
        if cargo:
            return cargo
    return None


def _classificar_colunas(names: list[str]):
    """(meta_idx, cand_cols) — candidatos aceitam 'Nome (PARTIDO)' e 'Nome PARTIDO'."""
    meta_idx: dict[str, int] = {}
    cand_cols: list[tuple[int, str, str]] = []
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
        sp = split_nome_partido(nm)
        if sp:
            cand_cols.append((ci, sp[0], sp[1]))
    return meta_idx, cand_cols


def _linhas_uf(uf: str, html: str) -> list[dict]:
    import pandas as pd
    from lxml import html as lh

    doc = lh.fromstring(html)
    dfs = pd.read_html(io.StringIO(html))
    tables = doc.xpath("//table")

    rows: list[dict] = []
    for pos, tbl in enumerate(tables):
        if "wikitable" not in (tbl.get("class") or ""):
            continue
        if pos >= len(dfs):
            continue
        df = dfs[pos]
        if df.shape[1] < 6:
            continue
        cargo = _cargo_da_tabela(tbl)
        if not cargo:
            continue
        meta_idx, cand_cols = _classificar_colunas(_col_names(df))
        if "inst" not in meta_idx or "data" not in meta_idx or not cand_cols:
            continue
        year = _ano_do_heading(tbl)
        for ri, (_, r) in enumerate(df.iterrows()):
            inst_raw = str(r.iloc[meta_idx["inst"]])
            if inst_raw == "nan" or "contratante" in inst_raw.lower():
                continue
            inst = re.sub(r"\[.*?\]", "", inst_raw).strip()
            dt_fim = _parse_dt_fim(r.iloc[meta_idx["data"]], year)
            medicao_id = f"{uf}:{pos}:{ri}"
            for ci, nome_wiki, partido in cand_cols:
                val = str(r.iloc[ci]).replace("%", "").replace(",", ".").strip()
                if not re.match(r"^\d+(\.\d+)?$", val):
                    continue
                nome = CANDIDATO_NORMALIZE.get(nome_wiki, nome_wiki)
                rows.append(
                    {
                        "uf": uf,
                        "medicao_id": medicao_id,
                        "instituto": inst,
                        "dt_fim": dt_fim,
                        "ano": year,
                        "cargo": cargo,
                        "candidato": nome,
                        "partido": partido,
                        "pct": float(val),
                    }
                )
    return rows


def _save_bronze(rows: list[dict]) -> Path:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    now = datetime.now(timezone.utc)
    df = pd.DataFrame(rows)
    df["_ingest_ts"] = now.isoformat()

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRONZE_DIR / f"estaduais_{now.year}_{now.month:02d}_{now.day:02d}.parquet"
    pq.write_table(
        pa.Table.from_pandas(df, preserve_index=False), out_path, compression="snappy"
    )
    return out_path


def main() -> int:
    print("🗳  Observatório Eleições 2026 — coleta ESTADUAL (governador + senador)")
    todas: list[dict] = []
    ok, ausentes, falhas = [], [], []
    for i, (uf, suf) in enumerate(UF_ARTIGO_SUFIXO.items()):
        title = WIKIPEDIA_ESTADUAL_TITLE_FMT.format(suf=suf)
        try:
            html = _baixar_html(title)
        except requests.RequestException as e:  # noqa: BLE001
            print(f"  ! {uf}: falha de rede ({e}) — pulando")
            falhas.append(uf)
            html = None
        if html is None:
            ausentes.append(uf)
        else:
            try:
                rows = _linhas_uf(uf, html)
            except Exception as e:  # noqa: BLE001
                print(f"  ! {uf}: falha de parse ({e}) — pulando")
                falhas.append(uf)
                rows = []
            if rows:
                todas.extend(rows)
                ok.append(uf)
            else:
                ausentes.append(uf)
        if i < len(UF_ARTIGO_SUFIXO) - 1:
            time.sleep(ESTADUAL_THROTTLE_S)  # throttle anti-429

    if not todas:
        print("  ✗ nenhuma linha extraída de nenhuma UF — layout pode ter mudado.")
        return 1

    out_path = _save_bronze(todas)
    print(f"  ✓ {out_path} ({len(todas):,} linhas · {len(ok)} UFs)")
    print(f"    UFs com dados: {' '.join(sorted(ok))}")
    if ausentes:
        print(f"    sem dados/artigo: {' '.join(sorted(set(ausentes)))}")
    if falhas:
        print(f"    falhas: {' '.join(sorted(set(falhas)))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
