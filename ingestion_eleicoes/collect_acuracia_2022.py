"""
Observatório Eleições 2026 — Retrovisor 2022 (coleta)
=====================================================
Coleta as DUAS matérias-primas do retrovisor de 2022:

A) Wikipedia PT — "Pesquisas de opinião para a eleição presidencial no Brasil
   em 2022": wikitables do 1º turno (cenário estimulado, seção 2022) e do
   confronto final do 2º turno (Bolsonaro x Lula). Grava bronze LONG (uma
   linha por medição × candidato) com instituto, contratante, data de fim do
   campo, amostra e margem. As seções "Hipóteses…" (cenários especulativos)
   ficam de fora por construção do gate de seção.

B) TSE Dados Abertos — dataset de REGISTRO "Pesquisas Eleitorais 2022"
   (pesquisa_eleitoral_2022.zip, mesmo layout do de 2026): bronze com as
   mesmas colunas canônicas do coletor de 2026 (catalog.COLUNAS), para a
   comparação máquina 2022 × 2026 na camada gold.

Uso:
    python ingestion_eleicoes/collect_acuracia_2022.py
Saída:
    data/bronze/eleicoes_acuracia_2022/wiki_2022_AAAA_MM_DD.parquet
    data/bronze/eleicoes_acuracia_2022/tse_pesquisas_2022_AAAA_MM_DD.parquet

Fail-soft: tabela/linha/coluna da Wikipedia fora do padrão é pulada (e
contabilizada no log); cada uma das duas fontes falha de forma independente —
o processo só retorna erro se NENHUMA das duas produzir bronze.
"""

from __future__ import annotations

import io
import re
import sys
import time
import urllib.parse
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from ingestion_eleicoes.catalog import (  # noqa: E402
    ANO_RETROVISOR,
    COL_IGNORAR,
    COLUNAS,
    CSV_DELIMITER,
    CSV_ENCODING,
    RETROVISOR_META_INST_NEEDLES,
    RETROVISOR_SECAO_T1,
    RETROVISOR_SECAO_T2,
    RETROVISOR_TURNO_1,
    RETROVISOR_TURNO_2,
    TSE_CSV_NACIONAL_2022,
    TSE_PESQUISAS_2022_ZIP_URL,
    WIKIPEDIA_ACURACIA_2022_TITLE,
    WIKIPEDIA_API,
    instituto_canonico_2022,
)
from ingestion_eleicoes.collect_pesquisas import _parse_rows  # noqa: E402
from ingestion_eleicoes.tse_dados_abertos import http_get  # noqa: E402

BRONZE_DIR = Path("data/bronze/eleicoes_acuracia_2022")
TIMEOUT = 60
TIMEOUT_TSE = 180
MAX_RETRIES = 4

# Colunas meta das wikitables de 2022 (casadas por substring, minúsculas).
# O cabeçalho de instituto varia por tabela — ver RETROVISOR_META_INST_NEEDLES.
_META_NEEDLES = {
    "data": ("data",),
    "amostra": ("amostra",),
    "margem": ("margem",),
}

# Meses PT (mesma tabela do catálogo, importada indiretamente via regex local).
from ingestion_eleicoes.catalog import MESES_PT  # noqa: E402


# ─── Wikipedia: download ─────────────────────────────────────────────────────

def _baixar_html() -> str:
    """HTML renderizado do artigo 2022 via API MediaWiki (action=parse).

    Mesmo padrão anti-oscilação do coletor presidencial: retry/backoff que
    respeita Retry-After em 429/503 e User-Agent descritivo.
    """
    url = WIKIPEDIA_API + "?" + urllib.parse.urlencode(
        {
            "action": "parse",
            "page": WIKIPEDIA_ACURACIA_2022_TITLE,
            "prop": "text",
            "format": "json",
            "formatversion": "2",
        }
    )
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers={
                    "User-Agent": (
                        "observatorio-eleicoes-2026/1.0 "
                        "(https://github.com/Donotavio/cv-site-otavio; retrovisor-2022) requests"
                    )
                },
                timeout=TIMEOUT,
            )
            if resp.status_code in (429, 503):
                wait = int(resp.headers.get("Retry-After", 0) or 0) or attempt * 5
                print(f"  · Wikipedia {resp.status_code} — aguardando {wait}s ({attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"API MediaWiki: {data['error']}")
            return data["parse"]["text"]
        except requests.RequestException as e:  # noqa: BLE001
            last_exc = e
            if attempt < MAX_RETRIES:
                wait = attempt * 5
                print(f"  · falha de rede ({attempt}/{MAX_RETRIES}): {e.__class__.__name__} — retry em {wait}s")
                time.sleep(wait)
    raise last_exc if last_exc else RuntimeError("download da Wikipedia falhou após retries")


# ─── Wikipedia: parsing ──────────────────────────────────────────────────────

def _texto_heading(node) -> str:
    return re.sub(r"\s+", " ", node.text_content()).strip().lower()


def _secao_da_tabela(tbl) -> str | None:
    """turno1/turno2 pelo par (h2, h3) mais próximo acima da tabela.

    Gates no catálogo (RETROVISOR_SECAO_T1/T2). Tabelas fora dos dois pares —
    gráficos, agregadores, outros anos, "Hipóteses…" — devolvem None.
    """
    h2s = tbl.xpath("preceding::h2")
    h3s = tbl.xpath("preceding::h3")
    h2 = _texto_heading(h2s[-1]) if h2s else ""
    h3 = _texto_heading(h3s[-1]) if h3s else ""
    if RETROVISOR_SECAO_T1[0] in h2 and RETROVISOR_SECAO_T1[1] in h3:
        return RETROVISOR_TURNO_1
    if RETROVISOR_SECAO_T2[0] in h2 and RETROVISOR_SECAO_T2[1] in h3:
        return RETROVISOR_TURNO_2
    return None


def _nomes_colunas(df) -> list[str]:
    """Nome útil por coluna: o artigo de 2022 alterna o nível que carrega
    'Nome PARTIDO' (1º turno no nível 1; 2º turno no nível 0) — pega o nível 1
    quando ele tem conteúdo, senão cai para o nível 0. Remove refs [n]."""
    import pandas as pd

    def _limpo(v: str) -> str:
        v = re.sub(r"\[.*?\]", "", str(v)).strip()
        return "" if v.lower() in ("nan", "") or v.startswith("Unnamed") else v

    if isinstance(df.columns, pd.MultiIndex):
        nomes = []
        for c0, c1 in zip(df.columns.get_level_values(0), df.columns.get_level_values(1)):
            nomes.append(_limpo(c1) or _limpo(c0))
        return nomes
    return [_limpo(c) for c in df.columns]


def _classificar_colunas(names: list[str]) -> tuple[dict, list[tuple[int, str, str]]]:
    """(meta_idx, cand_cols) — cand_cols = [(idx, nome_curto, partido)]."""
    meta_idx: dict[str, int] = {}
    cand_cols: list[tuple[int, str, str]] = []
    for ci, nm in enumerate(names):
        low = nm.lower()
        if not nm:
            continue
        if "inst" not in meta_idx and any(k in low for k in RETROVISOR_META_INST_NEEDLES):
            meta_idx["inst"] = ci
            continue
        matched_meta = False
        for key, needles in _META_NEEDLES.items():
            if key not in meta_idx and any(k in low for k in needles):
                meta_idx[key] = ci
                matched_meta = True
                break
        if matched_meta:
            continue
        if any(k in low for k in COL_IGNORAR):
            continue
        parts = nm.rsplit(" ", 1)  # 'Lula PT' / 'Tebet MDB'
        if len(parts) == 2 and parts[1]:
            cand_cols.append((ci, parts[0].strip(), parts[1].strip()))
    return meta_idx, cand_cols


def _parse_dt_fim_2022(cell: str, ano_heading: int | None) -> str | None:
    """Última data 'dd mmm' da célula → ISO. O ano vem da própria célula quando
    presente ('28–29 Out 2022' — padrão do 2º turno, cuja tabela única cobre
    2020-2022), senão do heading, senão do ano do retrovisor."""
    s = str(cell).lower()
    m_ano = re.search(r"\b(20\d{2})\b", s)
    year = int(m_ano.group(1)) if m_ano else (ano_heading or ANO_RETROVISOR)
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


def _ano_do_heading(tbl) -> int | None:
    """Ano da seção (heading mais próximo, subindo, que contenha 20XX)."""
    prevs = tbl.xpath("preceding::*[self::h2 or self::h3 or self::h4]")
    for h in reversed(prevs):
        m = re.search(r"\b(20\d{2})\b", h.text_content())
        if m:
            return int(m.group(1))
    return None


def _parse_int(v) -> int | None:
    """Amostra: já numérica via read_html(thousands='.'), ou string suja."""
    if v is None:
        return None
    s = re.sub(r"\[.*?\]", "", str(v))
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return None
    try:
        n = int(s)
    except ValueError:
        return None
    return n if n > 0 else None


def _parse_float(v) -> float | None:
    if v is None:
        return None
    s = re.sub(r"\[.*?\]", "", str(v)).replace("%", "").replace(",", ".").strip()
    m = re.match(r"^-?\d+(\.\d+)?$", s)
    if not m:
        return None
    return float(s)


def _linhas_wiki(html: str) -> tuple[list[dict], dict]:
    """Extrai as linhas LONG das wikitables dos dois turnos.

    Fail-soft POR TABELA: exceção em uma tabela é registrada e não derruba as
    demais. Devolve (linhas, stats) com contadores para o log/relatório.
    """
    import pandas as pd
    from lxml import html as lh

    doc = lh.fromstring(html)
    # thousands='.' + decimal=',' — sem isso o read_html lê '2.000' (amostra)
    # como 2.0 e '2,2' (margem) como 22.
    dfs = pd.read_html(io.StringIO(html), thousands=".", decimal=",")
    tables = doc.xpath("//table")

    rows: list[dict] = []
    stats = {"tabelas_ok": [], "tabelas_puladas": [], "tabelas_erro": []}
    for pos, tbl in enumerate(tables):
        if "wikitable" not in (tbl.get("class") or ""):
            continue
        turno = _secao_da_tabela(tbl)
        if not turno or pos >= len(dfs):
            continue
        try:
            df = dfs[pos]
            if df.shape[1] < 5:
                stats["tabelas_puladas"].append((pos, turno, "menos de 5 colunas"))
                continue
            meta_idx, cand_cols = _classificar_colunas(_nomes_colunas(df))
            if "inst" not in meta_idx or "data" not in meta_idx or not cand_cols:
                stats["tabelas_puladas"].append((pos, turno, "sem meta inst/data ou sem candidatos"))
                continue
            ano_heading = _ano_do_heading(tbl)
            n_antes = len(rows)
            for ri, (_, r) in enumerate(df.iterrows()):
                inst_raw = str(r.iloc[meta_idx["inst"]])
                low = inst_raw.lower()
                # linha de repetição de cabeçalho no meio da tabela
                if inst_raw == "nan" or "identificação" in low or low.strip() == "instituto de pesquisa":
                    continue
                instituto, contratante = instituto_canonico_2022(inst_raw)
                if not instituto:
                    continue
                dt_fim = _parse_dt_fim_2022(r.iloc[meta_idx["data"]], ano_heading)
                amostra = _parse_int(r.iloc[meta_idx["amostra"]]) if "amostra" in meta_idx else None
                margem = _parse_float(r.iloc[meta_idx["margem"]]) if "margem" in meta_idx else None
                # margem digitada sem vírgula em parte das linhas ('22' = 2,2;
                # '245' = 2,45): margem real de pesquisa nacional é < 10 pp.
                if margem is not None:
                    while margem >= 10:
                        margem /= 10
                    margem = round(margem, 2)
                medicao_id = f"{turno}:{pos}:{ri}"
                for ci, nome_curto, partido in cand_cols:
                    pct = _parse_float(r.iloc[ci])
                    if pct is None:
                        continue
                    rows.append(
                        {
                            "turno": turno,
                            "medicao_id": medicao_id,
                            "instituto": instituto,
                            "contratante": contratante,
                            "instituto_raw": re.sub(r"\[.*?\]", "", inst_raw).strip(),
                            "dt_fim": dt_fim,
                            "amostra": amostra,
                            "margem_pp": margem,
                            "candidato": nome_curto,
                            "partido": partido,
                            "pct": pct,
                        }
                    )
            stats["tabelas_ok"].append((pos, turno, len(rows) - n_antes))
        except Exception as e:  # noqa: BLE001 — fail-soft por tabela
            stats["tabelas_erro"].append((pos, turno, f"{e.__class__.__name__}: {e}"))
    return rows, stats


# ─── TSE: dataset de registro 2022 ───────────────────────────────────────────

def _baixar_csv_tse_2022() -> str:
    """ZIP de registro de pesquisas 2022 → texto do CSV nacional.

    Todo acesso a domínio do TSE passa por tse_dados_abertos.http_get
    (fingerprint TLS de browser — `requests` direto leva 403 do Akamai).
    """
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = http_get(TSE_PESQUISAS_2022_ZIP_URL, timeout=TIMEOUT_TSE)
            if resp.status_code in (429, 503):
                wait = int(resp.headers.get("Retry-After", 0) or 0) or attempt * 5
                print(f"  · TSE {resp.status_code} — aguardando {wait}s ({attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                with zf.open(TSE_CSV_NACIONAL_2022) as fh:
                    return fh.read().decode(CSV_ENCODING)
        except Exception as e:  # noqa: BLE001 - curl_cffi tem hierarquia própria de erro
            last_exc = e
            if attempt < MAX_RETRIES:
                wait = attempt * 5
                print(f"  · falha de rede ({attempt}/{MAX_RETRIES}): {e.__class__.__name__} — retry em {wait}s")
                time.sleep(wait)
    raise last_exc if last_exc else RuntimeError("download do TSE 2022 falhou após retries")


def _checar_header_tse(csv_text: str) -> None:
    """Loga colunas do catálogo ausentes no CSV 2022 (não falha — o parse via
    dict.get degrada para string vazia e o gold acusa na agregação)."""
    import csv as _csv

    header = next(_csv.reader(io.StringIO(csv_text), delimiter=CSV_DELIMITER), [])
    faltantes = [c for c in COLUNAS if c not in header]
    if faltantes:
        print(f"  ! CSV 2022: colunas esperadas ausentes: {faltantes}")


# ─── bronze ──────────────────────────────────────────────────────────────────

def _save_parquet(rows: list[dict], prefixo: str) -> Path:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    now = datetime.now(timezone.utc)
    df = pd.DataFrame(rows)
    df["_ingest_ts"] = now.isoformat()

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out = BRONZE_DIR / f"{prefixo}_{now.year}_{now.month:02d}_{now.day:02d}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out, compression="snappy")
    return out


def main() -> int:
    print("🗳  Observatório Eleições 2026 — Retrovisor 2022 (coleta)")
    ok_algum = False

    # A) Wikipedia 2022 (acurácia)
    print("  → Wikipedia PT: pesquisas presidenciais 2022")
    try:
        html = _baixar_html()
        rows, stats = _linhas_wiki(html)
        if rows:
            out = _save_parquet(rows, "wiki_2022")
            n_t1 = sum(1 for r in rows if r["turno"] == RETROVISOR_TURNO_1)
            n_t2 = sum(1 for r in rows if r["turno"] == RETROVISOR_TURNO_2)
            print(f"  ✓ {out} ({len(rows):,} linhas · 1º turno {n_t1:,} · 2º turno {n_t2:,})")
            for pos, turno, motivo in stats["tabelas_puladas"]:
                print(f"    · tabela {pos} ({turno}) pulada: {motivo}")
            for pos, turno, erro in stats["tabelas_erro"]:
                print(f"    ! tabela {pos} ({turno}) com erro: {erro}")
            ok_algum = True
        else:
            print("  ✗ nenhuma linha extraída das wikitables de 2022 — layout pode ter mudado.")
    except (requests.RequestException, RuntimeError) as e:  # noqa: BLE001
        print(f"  ✗ falha ao baixar o artigo da Wikipedia: {e}")

    # B) TSE registro de pesquisas 2022 (máquina)
    print("  → TSE Dados Abertos: registro de pesquisas 2022")
    try:
        csv_text = _baixar_csv_tse_2022()
        _checar_header_tse(csv_text)
        rows_tse = _parse_rows(csv_text)  # mesmas colunas canônicas de 2026
        if rows_tse:
            out = _save_parquet(rows_tse, "tse_pesquisas_2022")
            print(f"  ✓ {out} ({len(rows_tse):,} pesquisas registradas em 2022)")
            ok_algum = True
        else:
            print("  ✗ CSV 2022 do TSE sem linhas — nada a gravar.")
    except Exception as e:  # noqa: BLE001 - curl_cffi tem hierarquia própria de erro
        print(f"  ✗ falha ao baixar o dataset 2022 do TSE: {e}")

    return 0 if ok_algum else 1


if __name__ == "__main__":
    sys.exit(main())
