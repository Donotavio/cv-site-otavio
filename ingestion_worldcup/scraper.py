"""
World Cup Dashboard — Coleta de dados (Custo Zero)
===================================================
Fonte real: Openfootball (github.com/openfootball/worldcup.json) — JSON puro,
atualizado pela comunidade, domínio público (CC0). Sem Cloudflare, sem HTML
dinâmico, sem chaves de API. Para notícias, RSS Feeds do Google News via
feedparser (mesmo padrão de ingestion/fetch_news.py).

Arquitetura anti-bloqueio — 6 arquivos JSON estáticos publicados em
world-cup-dashboard/data/, consumidos pelo frontend em runtime:

    partidas.json      ← Openfootball (worldcup.json)
    artilheiros.json   ← agregação de gols do Openfootball
    estatisticas.json  ← cálculo local (média, gols por minuto, etc.)
    jogadores.json     ← Openfootball (gols + squads.json para posição)
    probabilidades.json ← Elo Rating local a partir dos resultados reais
    noticias.json      ← RSS Feeds (Google News) via feedparser

Resiliência: cada coletor é independente. Se uma fonte falhar, o JSON
anterior é preservado (o frontend mostra "última atualização" e nunca
quebra). Saída sempre UTF-8 com ensure_ascii=False. O commit só acontece
se houver alteração real de conteúdo (updated_at é ignorado no diff).

Uso:
    python ingestion_worldcup/scraper.py

Saída:
    public/world-cup-dashboard/data/{partidas,artilheiros,estatisticas,
                                     jogadores,probabilidades,noticias}.json
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import random
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

try:
    import feedparser
except ImportError:  # pragma: no cover
    feedparser = None


# ─── Fontes ───────────────────────────────────────────────────────────
OPENFOOTBALL_RAW = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master"
)
URL_MATCHES = f"{OPENFOOTBALL_RAW}/2026/worldcup.json"
URL_MATCHES_FALLBACK = f"{OPENFOOTBALL_RAW}/2022/worldcup.json"
URL_TEAMS = f"{OPENFOOTBALL_RAW}/2026/worldcup.teams.json"
URL_TEAMS_FALLBACK = f"{OPENFOOTBALL_RAW}/2022/worldcup.teams.json"
URL_SQUADS = f"{OPENFOOTBALL_RAW}/2026/worldcup.squads.json"
# 2022 não tem squads.json no worldcup.json — mas o repo texto openfootball/
# world-cup traz os 32 elencos com data de nascimento (b. YYYY/MM/DD).
URL_SQUADS_2022_TXT = (
    "https://raw.githubusercontent.com/openfootball/world-cup/master/"
    "more/2022_squads.txt"
)

# Datas de abertura (referência p/ cálculo de idade) de cada Copa.
KICKOFF_2022 = date(2022, 11, 20)  # Catar × Equador (Al Bayt)
KICKOFF_2026 = date(2026, 6, 11)   # abertura no Estádio Azteca (Cidade do México)

# Google News agrega múltiplas fontes sem bloqueio. PT + EN cobrem
# cobertura brasileira e internacional.
RSS_FEEDS = [
    (
        "Google News (PT)",
        "https://news.google.com/rss/search?q=Copa+do+Mundo+2026+OR+"
        "World+Cup+2026&hl=pt-BR&gl=BR&ceid=BR:pt-419",
    ),
    (
        "Google News (EN)",
        "https://news.google.com/rss/search?q=World+Cup+2026+football"
        "+OR+soccer&hl=en&gl=US&ceid=US:en",
    ),
]
NEWS_KEYWORDS = (
    "world cup", "copa do mundo", "copa 2026", "world cup 2026", "fifa",
    "seleção", "brasile", "argentina", "messi", "mbappé", "mbappe",
    "ronaldo", "vinicius", "haaland",
)
MAX_NEWS = 10

# ─── Configuração ─────────────────────────────────────────────────────
OUTPUT_DIR = Path("assets/data/worldcup")
HTTP_TIMEOUT = 30
USER_AGENT = "worldcup-dashboard/1.0 (+https://github.com/Donotavio/cv-site-otavio)"

# Elo Rating — K alto para Copa (poucos jogos, alta variância).
ELO_K = 40
ELO_INIT = 1500.0
ELO_MAX_DIFF = 400


# ─── HTTP / IO helpers ────────────────────────────────────────────────
def _http_get(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read()


def _http_get_json(url: str):
    try:
        return json.loads(_http_get(url).decode("utf-8"))
    except (URLError, HTTPError, TimeoutError, ValueError, OSError) as e:
        print(f"    ✗ Falha ao buscar {url}: {e}")
        return None


def _write_json_resilient(path: Path, payload: dict) -> bool:
    """Escreve só se o conteúdo mudou (evita commits vazios no Actions)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    new_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if path.exists():
        try:
            old_text = path.read_text(encoding="utf-8")
            if _normalize_for_diff(old_text) == _normalize_for_diff(new_text):
                print(f"    = {path.name} sem alterações — mantido.")
                return False
        except OSError:
            pass
    path.write_text(new_text, encoding="utf-8")
    print(f"    ✓ {path.name} ({len(new_text)} bytes)")
    return True


def _normalize_for_diff(text: str) -> str:
    """updated_at sempre muda — ignorado na comparação de conteúdo."""
    return re.sub(r'"updated_at"\s*:\s*"[^"]*"', '"updated_at": "@@"', text)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_str() -> str:
    return date.today().isoformat()


# ─── Parsers do Openfootball ──────────────────────────────────────────
def _parse_minute(raw) -> int | None:
    """
    Minuto do gol. Dois formatos no Openfootball:
      • 2022: int (90) + campo offset separado (5) → chamador soma
      • 2026: string ("9", "90+5", "45+12") → soma interno
    Aqui recebemos o campo `minute` cru e devolvemos o minuto absoluto.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    s = str(raw).strip()
    if not s:
        return None
    m = re.match(r"^(\d+)(?:\+(\d+))?$", s)
    if m:
        base = int(m.group(1))
        off = int(m.group(2)) if m.group(2) else 0
        return base + off
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None


def _slug(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_ = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[-\s]+", "-", re.sub(r"[^\w\s-]", "", ascii_).lower().strip())


def _build_team_index(teams_data) -> dict[str, dict]:
    """Indexa seleções por nome + variantes (USA/United States, slug)."""
    index: dict[str, dict] = {}
    if not isinstance(teams_data, list):
        return index
    for t in teams_data:
        if not isinstance(t, dict):
            continue
        name = t.get("name") or t.get("title") or ""
        if not name:
            continue
        entry = {
            "code": t.get("code") or t.get("fifa_code") or "",
            "flag": t.get("flag_icon") or t.get("flag") or "",
            "group": t.get("group") or "",
            "confed": t.get("confed") or "",
        }
        index[name] = entry
        for key in ("name_normalised", "title", "fifa_name"):
            alt = t.get(key)
            if alt and alt not in index:
                index[alt] = entry
        index[_slug(name)] = entry
    return index


def _team_info(name: str, teams_index: dict) -> dict:
    """Resolve nome → {name, code, flag}. Placeholders W83/L101 → TBD."""
    if not name:
        return {"name": "TBD", "code": "", "flag": ""}
    if re.match(r"^[WL]\d+$", name):
        return {"name": "A definir", "code": name, "flag": ""}
    info = teams_index.get(name) or teams_index.get(_slug(name))
    if info:
        return {
            "name": name,
            "code": info.get("code") or "",
            "flag": info.get("flag") or "",
        }
    return {"name": name, "code": "", "flag": ""}


def _match_status(match: dict, today: str) -> str:
    score = match.get("score") or {}
    if isinstance(score, dict) and score.get("ft"):
        return "finished"
    if (match.get("date") or "")[:10] == today:
        return "today"
    return "scheduled"


def _final_score(score: dict) -> tuple[int, int] | None:
    """Placar decisivo: ft, senão et. None se não houve."""
    if not isinstance(score, dict):
        return None
    for key in ("ft", "et"):
        vals = score.get(key)
        if isinstance(vals, list) and len(vals) == 2 and vals[0] is not None:
            try:
                return int(vals[0]), int(vals[1])
            except (TypeError, ValueError):
                continue
    return None


def _is_placeholder(name: str) -> bool:
    return bool(name) and bool(re.match(r"^[WL]\d+$", name))


# ─── Coleta Openfootball ──────────────────────────────────────────────
def fetch_openfootball() -> tuple[list, dict]:
    """Tenta 2026 primeiro; se vazio/falhar, cai para 2022 (demo)."""
    for matches_url, teams_url, label in (
        (URL_MATCHES, URL_TEAMS, "2026"),
        (URL_MATCHES_FALLBACK, URL_TEAMS_FALLBACK, "2022 (fallback)"),
    ):
        print(f"  → Openfootball [{label}]...")
        data = _http_get_json(matches_url)
        if not data:
            continue
        matches = data.get("matches") or []
        teams_index = _build_team_index(_http_get_json(teams_url) or [])
        if matches:
            print(f"    ✓ {len(matches)} partidas, {len(teams_index)} seleções.")
            return matches, teams_index
    print("  ✗ Nenhuma fonte do Openfootball disponível.")
    return [], {}


# ─── partidas.json ────────────────────────────────────────────────────
def build_partidas(matches: list, teams_index: dict) -> dict:
    today = _today_str()
    out = []
    for m in matches:
        score = m.get("score") or {}
        t1, t2 = m.get("team1") or "", m.get("team2") or ""
        out.append(
            {
                "num": m.get("num"),
                "round": m.get("round") or "",
                "date": (m.get("date") or "")[:10],
                "time": m.get("time") or "",
                "team1": _team_info(t1, teams_index),
                "team2": _team_info(t2, teams_index),
                "score": {
                    "ft": score.get("ft") if isinstance(score, dict) else None,
                    "ht": score.get("ht") if isinstance(score, dict) else None,
                    "et": score.get("et") if isinstance(score, dict) else None,
                    "pen": score.get("p") if isinstance(score, dict) else None,
                },
                "status": _match_status(m, today),
                "group": m.get("group") or "",
                "ground": m.get("ground") or "",
                "has_placeholder": _is_placeholder(t1) or _is_placeholder(t2),
            }
        )
    out.sort(key=lambda x: (x["date"], x["time"]))
    return {
        "updated_at": _now_iso(),
        "source": "openfootball/worldcup.json",
        "tournament": "FIFA World Cup 2026",
        "total": len(out),
        "matches": out,
    }


# ─── artilheiros.json + base para jogadores.json ──────────────────────
def _aggregate_goals(matches: list, teams_index: dict) -> dict[str, dict]:
    players: dict[str, dict] = {}

    def _add(name, team_name, minute, penalty, owngoal):
        if not name:
            return
        slug = _slug(name) + "-" + _slug(team_name)
        info = _team_info(team_name, teams_index)
        entry = players.setdefault(
            slug,
            {
                "id": slug,
                "name": name,
                "team": info,
                "goals": 0,
                "penalties": 0,
                "owngoals": 0,
                "minutes": [],
            },
        )
        if owngoal:
            entry["owngoals"] += 1
            return
        entry["goals"] += 1
        if penalty:
            entry["penalties"] += 1
        m = _parse_minute(minute)
        if m is not None:
            entry["minutes"].append(m)

    for m in matches:
        if not _final_score(m.get("score") or {}):
            continue
        t1, t2 = m.get("team1") or "", m.get("team2") or ""
        for g in m.get("goals1") or []:
            _add(g.get("name"), t1, g.get("minute"), bool(g.get("penalty")), bool(g.get("owngoal")))
        for g in m.get("goals2") or []:
            _add(g.get("name"), t2, g.get("minute"), bool(g.get("penalty")), bool(g.get("owngoal")))
    return players


def build_artilheiros(matches: list, teams_index: dict) -> dict:
    players = _aggregate_goals(matches, teams_index)
    # Critério de desempate FIFA: 1) gols, 2) menos pênaltis, 3) menor último gol
    scorers = sorted(
        players.values(),
        key=lambda p: (
            p["goals"],
            -p["penalties"],           # menos pênaltis = mais gols de jogo
            -(max(p["minutes"]) if p["minutes"] else 999),  # chegou ao total mais cedo
        ),
        reverse=True,
    )
    for s in scorers:
        s.pop("minutes", None)
    return {
        "updated_at": _now_iso(),
        "source": "openfootball/worldcup.json",
        "top_scorer": scorers[0]["name"] if scorers else None,
        "scorers": scorers,
    }


# ─── estatisticas.json (cálculo local) ────────────────────────────────
def build_estatisticas(matches: list, teams_index: dict) -> dict:
    total_goals = 0
    goals_first_half = 0
    goals_second_half = 0
    goals_extra_time = 0
    penalties_scored = 0
    own_goals = 0
    finished = 0
    biggest_win = None
    highest_scoring = None
    minute_buckets = {f"{lo}-{lo+14}": 0 for lo in range(0, 121, 15)}
    teams_stats: dict[str, dict] = {}

    def _team_stat(name):
        if name not in teams_stats:
            info = _team_info(name, teams_index)
            teams_stats[name] = {
                "name": name, "code": info.get("code", ""), "flag": info.get("flag", ""),
                "goals_for": 0, "goals_against": 0, "matches": 0,
                "wins": 0, "draws": 0, "losses": 0,
            }
        return teams_stats[name]

    def _bucket(minute):
        idx = (max(0, min(120, minute)) // 15) * 15
        return f"{idx}-{idx+14}"

    for m in matches:
        final = _final_score(m.get("score") or {})
        if final is None:
            continue
        finished += 1
        s1, s2 = final
        t1, t2 = m.get("team1") or "", m.get("team2") or ""
        if _is_placeholder(t1) or _is_placeholder(t2):
            continue

        ts1, ts2 = _team_stat(t1), _team_stat(t2)
        ts1["goals_for"] += s1; ts1["goals_against"] += s2
        ts2["goals_for"] += s2; ts2["goals_against"] += s1
        ts1["matches"] += 1; ts2["matches"] += 1
        if s1 > s2: ts1["wins"] += 1; ts2["losses"] += 1
        elif s1 < s2: ts1["losses"] += 1; ts2["wins"] += 1
        else: ts1["draws"] += 1; ts2["draws"] += 1

        match_goals = s1 + s2
        total_goals += match_goals
        label = f"{t1} {s1}–{s2} {t2}"
        diff = abs(s1 - s2)
        if biggest_win is None or diff > biggest_win["diff"]:
            biggest_win = {"match": label, "diff": diff, "score": [s1, s2]}
        if highest_scoring is None or match_goals > highest_scoring["goals"]:
            highest_scoring = {"match": label, "goals": match_goals, "score": [s1, s2]}

        for g in (m.get("goals1") or []) + (m.get("goals2") or []):
            if g.get("owngoal"):
                own_goals += 1
                continue
            minute = _parse_minute(g.get("minute"))
            if minute is None:
                continue
            if minute <= 45: goals_first_half += 1
            elif minute <= 90: goals_second_half += 1
            else: goals_extra_time += 1
            if g.get("penalty"): penalties_scored += 1
            minute_buckets[_bucket(minute)] += 1

    avg = round(total_goals / finished, 2) if finished else 0.0

    efficiency = []
    for name, ts in teams_stats.items():
        if ts["matches"] == 0:
            continue
        diff = ts["goals_for"] - ts["goals_against"]
        efficiency.append({
            "name": name, "code": ts["code"], "flag": ts["flag"],
            "goals_for": ts["goals_for"], "goals_against": ts["goals_against"],
            "diff": diff, "matches": ts["matches"],
            "wins": ts["wins"], "draws": ts["draws"], "losses": ts["losses"],
            "diff_per_match": round(diff / ts["matches"], 2),
        })
    efficiency.sort(key=lambda x: x["diff_per_match"], reverse=True)

    return {
        "updated_at": _now_iso(),
        "source": "openfootball/worldcup.json (cálculo local)",
        "total_matches": finished,
        "total_goals": total_goals,
        "avg_goals_per_match": avg,
        "goals_first_half": goals_first_half,
        "goals_second_half": goals_second_half,
        "goals_extra_time": goals_extra_time,
        "penalties_scored": penalties_scored,
        "own_goals": own_goals,
        "biggest_win": biggest_win,
        "highest_scoring_match": highest_scoring,
        "goals_by_minute": [{"range": k, "count": v} for k, v in minute_buckets.items()],
        "teams_efficiency": efficiency[:16],
        "tournament_progress": _build_tournament_progress(matches),
    }


# ─── comparativo_copas.json (2022 × 2026, mesma fonte) ────────────────
def _count_teams(matches: list) -> int:
    names = set()
    for m in matches:
        for t in (m.get("team1"), m.get("team2")):
            if t and not _is_placeholder(t):
                names.add(t)
    return len(names)


def _comparativo_block(matches: list, teams_index: dict, year: str,
                       format_teams: int, format_matches: int) -> dict:
    """Um lado da comparação, calculado com o MESMO pipeline dos dois anos."""
    st = build_estatisticas(matches, teams_index)
    art = build_artilheiros(matches, teams_index)

    gfh, gsh, get_ = (st["goals_first_half"], st["goals_second_half"],
                      st["goals_extra_time"])
    gtot = gfh + gsh + get_

    def pct(x):
        return round(x / gtot * 100, 1) if gtot else 0.0

    gbm = st["goals_by_minute"]
    gbm_total = sum(b["count"] for b in gbm) or 1
    goals_by_minute = [{
        "range": b["range"], "count": b["count"],
        "pct": round(b["count"] / gbm_total * 100, 1),
    } for b in gbm]

    scorers = art.get("scorers") or []
    top = scorers[0] if scorers else None
    top_scorer = {
        "name": top["name"], "goals": top["goals"], "team": top.get("team", {}),
    } if top else None

    return {
        "year": year,
        "format_teams": format_teams,
        "format_matches": format_matches,
        "total_matches": st["total_matches"],
        "total_goals": st["total_goals"],
        "teams": _count_teams(matches) or format_teams,
        "avg_goals_per_match": st["avg_goals_per_match"],
        "goals_first_half": gfh,
        "goals_second_half": gsh,
        "goals_extra_time": get_,
        "goals_first_half_pct": pct(gfh),
        "goals_second_half_pct": pct(gsh),
        "goals_extra_time_pct": pct(get_),
        "penalties_scored": st["penalties_scored"],
        "own_goals": st["own_goals"],
        "biggest_win": st["biggest_win"],
        "highest_scoring_match": st["highest_scoring_match"],
        "goals_by_minute": goals_by_minute,
        "top_scorer": top_scorer,
    }


def _build_volume_comparison() -> dict | None:
    """
    Volume de jogo 2022 × 2026 nos indicadores que os DOIS torneios têm.
    Fontes diferentes (2022 = StatsBomb evento; 2026 = ESPN óptico) → o bloco
    traz um disclaimer. xG e PPDA ficam só em 2022 (não existem para 2026).
    Lê os JSONs-companheiros já no disco; fail-soft se faltarem.

    Convenção: valores POR TIME POR JOGO (total ÷ nº de duplas time-jogo).
    """
    pan = None
    try:
        pan = json.loads((OUTPUT_DIR / "copa2022_panorama.json").read_text("utf-8"))
    except (OSError, ValueError):
        pass
    ds = None
    try:
        ds = json.loads((OUTPUT_DIR / "deepstats.json").read_text("utf-8"))
    except (OSError, ValueError):
        pass
    if not pan or not ds:
        return None

    # ── 2022 (StatsBomb) — soma os totais por seleção do panorama ──
    teams = pan.get("team_xg") or []
    if not teams:
        return None
    def s22(k):
        return sum((t.get(k) or 0) for t in teams)
    tm22 = s22("matches") or 1                       # duplas time-jogo (≈128)
    ppda_vals = [t["ppda_avg"] for t in teams if t.get("ppda_avg") is not None]
    v22 = {
        "shots_per_match": s22("shots") / tm22,
        "shots_on_pct": (s22("shots_on") / s22("shots") * 100) if s22("shots") else None,
        "passes_per_match": s22("passes") / tm22,
        "pass_accuracy_pct": (s22("passes_cmp") / s22("passes") * 100) if s22("passes") else None,
        "tackles_per_match": s22("tackles") / tm22,
        "interceptions_per_match": s22("interceptions") / tm22,
        "fouls_per_match": s22("fouls") / tm22,
        "corners_per_match": s22("corners") / tm22,
        "xg_per_match": s22("xg_for") / tm22,
        "ppda": (sum(ppda_vals) / len(ppda_vals)) if ppda_vals else None,
    }

    # ── 2026 (ESPN) — agrega os totais de jogo por partida ──
    sm = (ds.get("shot_stats") or {}).get("matches") or {}
    pm = (ds.get("pass_stats") or {}).get("matches") or {}
    S = {"shots": 0, "on": 0, "tm": 0}
    for m in sm.values():
        for side in ("home", "away"):
            t = m.get(side) or {}
            S["shots"] += t.get("shots") or 0
            S["on"] += t.get("on_target") or 0
            S["tm"] += 1
    P = {"passes": 0, "acc": 0, "tk": 0, "int": 0, "foul": 0, "corner": 0, "tm": 0}
    for m in pm.values():
        for side in ("home", "away"):
            t = m.get(side) or {}
            P["passes"] += t.get("passes") or 0
            P["acc"] += t.get("accurate_passes") or 0
            P["tk"] += t.get("tackles") or 0
            P["int"] += t.get("interceptions") or 0
            P["foul"] += t.get("fouls") or 0
            P["corner"] += t.get("corners") or 0
            P["tm"] += 1
    if S["tm"] == 0 and P["tm"] == 0:
        return None
    stm = S["tm"] or 1
    ptm = P["tm"] or 1
    v26 = {
        "shots_per_match": S["shots"] / stm,
        "shots_on_pct": (S["on"] / S["shots"] * 100) if S["shots"] else None,
        "passes_per_match": P["passes"] / ptm,
        "pass_accuracy_pct": (P["acc"] / P["passes"] * 100) if P["passes"] else None,
        "tackles_per_match": P["tk"] / ptm,
        "interceptions_per_match": P["int"] / ptm,
        "fouls_per_match": P["foul"] / ptm,
        "corners_per_match": P["corner"] / ptm,
        "xg_per_match": None,   # não há xG para 2026
        "ppda": None,           # não há PPDA para 2026
    }

    # ── Monta as linhas (só 2022 quando 2026 não tem) ──
    SPEC = [
        ("shots_per_match",         "Chutes por time/jogo",       1, ""),
        ("shots_on_pct",            "Chutes no alvo",             1, "%"),
        ("passes_per_match",        "Passes por time/jogo",       0, ""),
        ("pass_accuracy_pct",       "Precisão de passe",          1, "%"),
        ("tackles_per_match",       "Desarmes por time/jogo",     1, ""),
        ("interceptions_per_match", "Interceptações por time/jogo", 1, ""),
        ("fouls_per_match",         "Faltas por time/jogo",       1, ""),
        ("corners_per_match",       "Escanteios por time/jogo",   1, ""),
        ("xg_per_match",            "xG por time/jogo",           2, ""),
        ("ppda",                    "PPDA (pressão)",             1, ""),
    ]
    def r(v, dec):
        return round(v, dec) if v is not None else None
    metrics = []
    for key, label, dec, unit in SPEC:
        metrics.append({
            "key": key, "label": label, "unit": unit, "dec": dec,
            "v2022": r(v22.get(key), dec),
            "v2026": r(v26.get(key), dec),
            "only_2022": v26.get(key) is None,
        })

    return {
        "note": ("Volume de jogo — fontes diferentes: 2022 vem do dado de evento "
                 "StatsBomb (lance a lance); 2026, dos totais de jogo da ESPN "
                 "(rastreamento óptico). Compare a ordem de grandeza, não a casa "
                 "decimal. xG e PPDA só existem para 2022."),
        "metrics": metrics,
    }


def build_comparativo(matches_2026: list, teams_index_2026: dict) -> dict:
    """
    Compara 2022 × 2026 usando openfootball nos DOIS lados (mesma metodologia,
    sem viés de fonte). 2026 vem do fetch principal; 2022 via fallback direto.
    """
    data22 = _http_get_json(URL_MATCHES_FALLBACK) or {}
    matches_2022 = data22.get("matches") or []
    # O arquivo de seleções de 2022 pode não existir (404): resolve bandeiras/
    # códigos com o índice de 2026 como fallback (seleções recorrentes).
    teams_index_2022 = {**teams_index_2026,
                        **_build_team_index(_http_get_json(URL_TEAMS_FALLBACK) or [])}

    b26 = _comparativo_block(matches_2026, teams_index_2026, "2026", 48, 104)
    b22 = _comparativo_block(matches_2022, teams_index_2022, "2022", 32, 64)

    def _delta(a, b):
        if a is None or b is None:
            return None
        return round(a - b, 2)

    deltas = {
        "avg_goals_per_match": _delta(b26["avg_goals_per_match"],
                                      b22["avg_goals_per_match"]),
        "goals_first_half_pct": _delta(b26["goals_first_half_pct"],
                                       b22["goals_first_half_pct"]),
        "goals_second_half_pct": _delta(b26["goals_second_half_pct"],
                                        b22["goals_second_half_pct"]),
        "penalties_scored": _delta(b26["penalties_scored"],
                                   b22["penalties_scored"]),
        "own_goals": _delta(b26["own_goals"], b22["own_goals"]),
    }

    return {
        "updated_at": _now_iso(),
        "source": "openfootball/worldcup.json (2022 + 2026 — mesma metodologia)",
        "note": (
            "Comparação apples-to-apples: mesma fonte e mesmo cálculo local nos "
            "dois torneios. Mudança de formato: 32 seleções / 64 jogos (2022) → "
            "48 / 104 (2026). A distribuição de gols por minuto é normalizada em "
            "% para comparar torneios de tamanhos diferentes. O volume de jogo "
            "(abaixo) usa fontes distintas — ver disclaimer no bloco."
        ),
        "tournaments": {"2022": b22, "2026": b26},
        "deltas": deltas,
        "volume": _build_volume_comparison(),
    }


# ─── idade_copas.json ─────────────────────────────────────────────────
_AGE_BUCKETS = (
    ("<21", lambda a: a < 21),
    ("21-24", lambda a: 21 <= a <= 24),
    ("25-28", lambda a: 25 <= a <= 28),
    ("29-32", lambda a: 29 <= a <= 32),
    ("33+", lambda a: a >= 33),
)


def _age_at(dob: date, ref: date) -> int:
    """Idade em anos completos de `dob` na data `ref`."""
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))


def _parse_dob(raw) -> date | None:
    """Aceita 'YYYY-MM-DD' (JSON 2026) ou 'YYYY/MM/DD' (texto 2022)."""
    if not raw:
        return None
    m = re.match(r"^\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})", str(raw))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _players_2026(squads_data) -> list[dict]:
    """[{name, team, pos, dob:date}] a partir do worldcup.squads.json (2026)."""
    out: list[dict] = []
    if not isinstance(squads_data, list):
        return out
    for sq in squads_data:
        if not isinstance(sq, dict):
            continue
        team = sq.get("name") or ""
        for p in sq.get("players") or []:
            if not isinstance(p, dict) or not p.get("name"):
                continue
            out.append({
                "name": p["name"],
                "team": team,
                "pos": (p.get("pos") or "")[:2].upper(),
                "dob": _parse_dob(p.get("date_of_birth")),
            })
    return out


def _players_2022(text: str) -> list[dict]:
    """
    Parseia o texto openfootball dos elencos de 2022:
      == Brazil     # 26 Players
          10, NEYMAR,   FW,  b. 1992/02/05
    Devolve [{name, team, pos, dob:date}].
    """
    out: list[dict] = []
    if not text:
        return out
    team_re = re.compile(r"^==\s+(.+?)\s*(?:#.*)?$")
    player_re = re.compile(
        r"^\s*\d+,\s*(.+?),\s*([A-Za-z]{2}),\s*b\.\s*(\d{4}/\d{1,2}/\d{1,2})"
    )
    team = None
    for line in text.splitlines():
        mt = team_re.match(line)
        if mt:
            team = mt.group(1).strip()
            continue
        mp = player_re.match(line)
        if mp and team:
            out.append({
                "name": mp.group(1).strip(),
                "team": team,
                "pos": mp.group(2).upper(),
                "dob": _parse_dob(mp.group(3)),
            })
    return out


def _idade_block(players: list[dict], teams_index: dict, ref: date) -> dict:
    """Bloco de idade de um torneio: médias, extremos, buckets e por seleção."""
    ages: list[int] = []
    skipped = 0
    by_team: dict[str, list[int]] = {}
    extremes: list[dict] = []  # (age, name, team) via lista de dicts

    for p in players:
        dob = p.get("dob")
        if not isinstance(dob, date):
            skipped += 1
            continue
        age = _age_at(dob, ref)
        # Guarda-corpo contra datas absurdas (mantém 15–55 anos).
        if age < 15 or age > 55:
            skipped += 1
            continue
        ages.append(age)
        by_team.setdefault(p["team"], []).append(age)
        extremes.append({"age": age, "name": p["name"], "team": p["team"]})

    if not ages:
        return {
            "avg_age": None, "median_age": None, "youngest": None,
            "oldest": None, "players_counted": 0, "skipped": skipped,
            "age_buckets": [{"range": r, "count": 0} for r, _ in _AGE_BUCKETS],
            "teams": [],
        }

    ages_sorted = sorted(ages)
    n = len(ages_sorted)
    median = (ages_sorted[n // 2] if n % 2
              else (ages_sorted[n // 2 - 1] + ages_sorted[n // 2]) / 2)

    def _extreme(pick_max: bool) -> dict:
        e = (max if pick_max else min)(extremes, key=lambda x: x["age"])
        info = _team_info(e["team"], teams_index)
        return {
            "name": e["name"], "team": info["name"],
            "age": e["age"], "flag": info["flag"],
        }

    buckets = [
        {"range": label, "count": sum(1 for a in ages if pred(a))}
        for label, pred in _AGE_BUCKETS
    ]

    teams = []
    for team, tages in by_team.items():
        info = _team_info(team, teams_index)
        teams.append({
            "name": info["name"],
            "code": info["code"],
            "flag": info["flag"],
            "avg_age": round(sum(tages) / len(tages), 2),
            "players": len(tages),
        })
    teams.sort(key=lambda t: (-t["avg_age"], t["name"]))

    return {
        "avg_age": round(sum(ages) / n, 2),
        "median_age": round(median, 1),
        "youngest": _extreme(pick_max=False),
        "oldest": _extreme(pick_max=True),
        "players_counted": n,
        "skipped": skipped,
        "age_buckets": buckets,
        "teams": teams,
    }


def build_idade_copas(matches_2026: list, teams_index_2026: dict) -> dict:
    """
    Idade dos elencos 2022 × 2026 (openfootball nos dois lados, mesma
    metodologia). Idade = anos completos na data de abertura de cada Copa.
    2026: worldcup.squads.json (campo date_of_birth). 2022: não há squads.json
    — usa o texto openfootball/world-cup/more/2022_squads.txt (b. YYYY/MM/DD).
    `matches_2026` é aceito por simetria com os outros builders (não usado).
    """
    squads_2026 = _http_get_json(URL_SQUADS) or []
    players_2026 = _players_2026(squads_2026)

    txt_2022 = None
    try:
        txt_2022 = _http_get(URL_SQUADS_2022_TXT).decode("utf-8")
    except (URLError, HTTPError, TimeoutError, OSError) as e:
        print(f"    ✗ Falha ao buscar squads 2022: {e}")
    players_2022 = _players_2022(txt_2022 or "")

    # Seleções de 2022 podem faltar no índice (arquivo 2022 costuma dar 404):
    # usa o índice de 2026 como fallback p/ bandeiras/códigos (nações recorrentes).
    teams_index_2022 = {
        **teams_index_2026,
        **_build_team_index(_http_get_json(URL_TEAMS_FALLBACK) or []),
    }

    b22 = _idade_block(players_2022, teams_index_2022, KICKOFF_2022)
    b26 = _idade_block(players_2026, teams_index_2026, KICKOFF_2026)

    avg_delta = (round(b26["avg_age"] - b22["avg_age"], 2)
                 if b26["avg_age"] is not None and b22["avg_age"] is not None
                 else None)

    return {
        "updated_at": _now_iso(),
        "source": "openfootball squads (2022 + 2026)",
        "note": (
            "Idade calculada na data de abertura de cada Copa "
            f"(2022: {KICKOFF_2022.isoformat()}; 2026: {KICKOFF_2026.isoformat()}). "
            "2026 vem do worldcup.squads.json (elencos preliminares); 2022 do "
            "texto openfootball/world-cup (more/2022_squads.txt), com data de "
            "nascimento por jogador. Mesma metodologia nos dois torneios."
        ),
        "tournaments": {"2022": b22, "2026": b26},
        "deltas": {"avg_age": avg_delta},
    }


# ─── progresso do torneio ─────────────────────────────────────────────
# Mapeamento round (openfootball) → (label PT-BR, ordem cronológica)
_PHASE_ORDER = {
    "groups":        ("Fase de Grupos",          0),
    "round_32":      ("32 Avos de Final",        1),
    "round_16":      ("Oitavas de Final",        2),
    "quarter":       ("Quartas de Final",        3),
    "semi":          ("Semifinal",               4),
    "third_place":   ("Disputa de 3º lugar",     5),
    "final":         ("Final",                   6),
}


def _phase_key(round_name: str) -> str | None:
    """Converte nome do round do openfootball em chave canônica."""
    r = (round_name or "").lower().strip()
    if r.startswith("matchday"):
        return "groups"
    if "round of 32" in r or "round-of-32" in r:
        return "round_32"
    if "round of 16" in r or "round-of-16" in r:
        return "round_16"
    if "quarter" in r:
        return "quarter"
    if "semi" in r:
        return "semi"
    if "third" in r or "3rd" in r:
        return "third_place"
    if r == "final":
        return "final"
    return None


def _build_tournament_progress(matches: list) -> dict:
    """
    Detecta a fase atual do torneio e partidas restantes.
    Lógica: primeira fase (em ordem cronológica) com partidas agendadas.
    """
    # Contadores por fase
    by_phase: dict[str, dict] = {}
    next_match = None

    for m in matches:
        round_name = m.get("round", "")
        pkey = _phase_key(round_name)
        if pkey is None:
            continue
        if pkey not in by_phase:
            by_phase[pkey] = {"total": 0, "finished": 0, "scheduled": 0}
        by_phase[pkey]["total"] += 1

        is_finished = bool((m.get("score") or {}).get("ft"))
        if is_finished:
            by_phase[pkey]["finished"] += 1
        else:
            by_phase[pkey]["scheduled"] += 1
            # Próxima partida: menor data entre as agendadas
            date = m.get("date", "")
            t1 = m.get("team1") or ""
            t2 = m.get("team2") or ""
            if isinstance(t1, dict): t1 = t1.get("name", "?")
            if isinstance(t2, dict): t2 = t2.get("name", "?")
            candidate = {
                "date": date,
                "time": m.get("time", ""),
                "round": round_name,
                "team1": t1,
                "team2": t2,
            }
            if next_match is None or (date and date < next_match["date"]):
                next_match = candidate

    # Determina fase atual: primeira com partidas agendadas
    current_key = None
    for pkey in sorted(_PHASE_ORDER.keys(), key=lambda k: _PHASE_ORDER[k][1]):
        stats = by_phase.get(pkey)
        if stats and stats["scheduled"] > 0:
            current_key = pkey
            break

    total_matches = sum(s["total"] for s in by_phase.values())
    finished_total = sum(s["finished"] for s in by_phase.values())
    scheduled_total = sum(s["scheduled"] for s in by_phase.values())

    progress_pct = round(finished_total / total_matches * 100, 1) if total_matches else 0.0

    current_label = _PHASE_ORDER[current_key][0] if current_key else "Torneio finalizado"

    # Detalhe por fase (em ordem cronológica)
    phases = []
    for pkey in sorted(_PHASE_ORDER.keys(), key=lambda k: _PHASE_ORDER[k][1]):
        if pkey not in by_phase:
            continue
        stats = by_phase[pkey]
        phases.append({
            "key": pkey,
            "label": _PHASE_ORDER[pkey][0],
            "total": stats["total"],
            "finished": stats["finished"],
            "scheduled": stats["scheduled"],
            "completed": stats["scheduled"] == 0,
        })

    return {
        "total_matches": total_matches,
        "finished_matches": finished_total,
        "remaining_matches": scheduled_total,
        "progress_pct": progress_pct,
        "current_phase": current_label,
        "current_phase_key": current_key or "completed",
        "is_complete": current_key is None,
        "phases": phases,
        "next_match": next_match,
    }


# ─── probabilidades.json (Elo Rating local) ───────────────────────────
def _elo_expected(ra: float, rb: float) -> float:
    diff = max(-ELO_MAX_DIFF, min(ELO_MAX_DIFF, rb - ra))
    return 1.0 / (1.0 + 10.0 ** (diff / 400.0))


def _elo_k(goal_diff: int) -> float:
    if goal_diff <= 1: return ELO_K
    if goal_diff == 2: return ELO_K * 1.25
    return ELO_K * 1.5


def build_probabilidades(matches: list, teams_index: dict) -> dict:
    """
    Elo a partir dos resultados reais. Pênaltis contam como empate (prática
    padrão — não refletem força). Probabilidade de título via softmax do
    Elo final (temperatura baixa concentra no topo).
    """
    ratings: dict[str, float] = {}
    played: dict[str, dict] = {}

    def _rating(name):
        if name not in ratings:
            ratings[name] = ELO_INIT
            played[name] = {"matches": 0, "wins": 0, "draws": 0, "losses": 0}
        return ratings[name]

    chronological = sorted(
        matches,
        key=lambda m: ((m.get("date") or "")[:10], m.get("time") or ""),
    )
    for m in chronological:
        t1, t2 = m.get("team1") or "", m.get("team2") or ""
        if _is_placeholder(t1) or _is_placeholder(t2):
            continue
        final = _final_score(m.get("score") or {})
        if final is None:
            continue
        s1, s2 = final
        if s1 > s2: sa, sb = 1.0, 0.0
        elif s1 < s2: sa, sb = 0.0, 1.0
        else: sa, sb = 0.5, 0.5

        ra, rb = _rating(t1), _rating(t2)
        ea = _elo_expected(ra, rb)
        eb = 1.0 - ea
        k = _elo_k(abs(s1 - s2))
        ratings[t1] = ra + k * (sa - ea)
        ratings[t2] = rb + k * (sb - eb)
        played[t1]["matches"] += 1; played[t2]["matches"] += 1
        if sa > sb: played[t1]["wins"] += 1; played[t2]["losses"] += 1
        elif sa < sb: played[t1]["losses"] += 1; played[t2]["wins"] += 1
        else: played[t1]["draws"] += 1; played[t2]["draws"] += 1

    if not ratings:
        return {
            "updated_at": _now_iso(),
            "methodology": "Elo Rating local — sem partidas decididas ainda.",
            "teams": [],
        }

    TEMP = 180.0
    exps = {name: math.exp(r / TEMP) for name, r in ratings.items()}
    total = sum(exps.values())

    teams = []
    for name, r in ratings.items():
        info = _team_info(name, teams_index)
        teams.append({
            "name": name, "code": info.get("code", ""), "flag": info.get("flag", ""),
            "elo": round(r, 1),
            "win_probability": round((exps[name] / total) * 100, 2),
            "matches_played": played[name]["matches"],
            "wins": played[name]["wins"], "draws": played[name]["draws"], "losses": played[name]["losses"],
        })
    teams.sort(key=lambda x: x["elo"], reverse=True)
    for i, t in enumerate(teams, 1):
        t["rank"] = i

    return {
        "updated_at": _now_iso(),
        "methodology": (
            f"Elo Rating local (K={ELO_K}, init={int(ELO_INIT)}). "
            "Pênaltis contam como empate. Bônus de margem de gols no K. "
            "Probabilidade de título via softmax (temp=180). "
            "NOTA: Elo pondera a FORÇA dos adversários — uma seleção invicta "
            "contra times fracos pode ter Elo menor que uma com derrotas vs "
            "favoritos (ex: México 0 sofridos vs times fracos < França 13 gols "
            "vs times fortes)."
        ),
        "total_teams": len(teams),
        "teams": teams,
    }


# ─── jogadores.json (para o duelo "Quem é o Craque?") ─────────────────
def _build_squads_index(data=None) -> dict[str, str]:
    """slug → posição. squads.json é opcional; se falhar, sem posição."""
    if data is None:
        print("  → squads.json (posição dos jogadores)...")
        data = _http_get_json(URL_SQUADS)
    if not data:
        print("    ⚠ indisponível — jogadores sem posição.")
        return {}
    index: dict[str, str] = {}

    def _walk(obj):
        if isinstance(obj, dict):
            name, pos = obj.get("name"), obj.get("pos") or obj.get("position")
            if name and pos:
                index[_slug(str(name))] = str(pos).upper()[:3]
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(data)
    print(f"    ✓ {len(index)} jogadores indexados.")
    return index


def build_jogadores(matches: list, teams_index: dict, squads_index: dict) -> dict:
    players = _aggregate_goals(matches, teams_index)
    out = []
    for slug, p in players.items():
        if p["goals"] <= 0:
            continue
        pos = squads_index.get(_slug(p["name"])) or ""
        out.append({
            "id": slug,
            "name": p["name"],
            "team": p["team"],
            "position": pos or "FW",
            "goals": p["goals"],
            "penalties": p["penalties"],
        })
    out.sort(key=lambda x: x["goals"], reverse=True)
    return {
        "updated_at": _now_iso(),
        "source": "openfootball (gols) + squads.json (posição)",
        "total": len(out),
        "players": out,
    }


# ─── noticias.json (RSS via feedparser) ───────────────────────────────
def _clean_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text))).strip()


def _split_source(title: str) -> tuple[str, str]:
    if " - " in title:
        head, _, source = title.rpartition(" - ")
        return head.strip(), source.strip()
    return title.strip(), ""


def _matches_keywords(text: str) -> bool:
    low = (text or "").lower()
    return any(kw in low for kw in NEWS_KEYWORDS)


def _parse_entry_date(entry) -> str:
    if entry.get("published_parsed"):
        t = entry["published_parsed"]
        try:
            return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
    return entry.get("published") or entry.get("updated") or ""


def fetch_noticias() -> dict:
    if feedparser is None:
        print("    ✗ feedparser não instalado — pulando notícias.")
        return {"items": []}

    seen: set[str] = set()
    items: list[dict] = []

    for feed_name, url in RSS_FEEDS:
        print(f"  → RSS [{feed_name}]...")
        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            print(f"    ✗ Erro no feed: {e}")
            continue
        if parsed.bozo and not parsed.entries:
            print("    ⚠ Feed malformado, sem entradas.")
            continue
        for entry in parsed.entries:
            headline, source = _split_source(_clean_html(entry.get("title") or ""))
            if not headline:
                continue
            summary = _clean_html(entry.get("summary") or "")
            if not _matches_keywords(headline + " " + summary):
                continue
            link = (entry.get("link") or "").strip()
            key = hashlib.md5(link.encode("utf-8")).hexdigest() if link else headline
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "title": headline,
                "source": source or feed_name,
                "url": link,
                "summary": summary[:280],
                "published": _parse_entry_date(entry),
            })
            if len(items) >= MAX_NEWS:
                break
        if len(items) >= MAX_NEWS:
            break

    items.sort(key=lambda x: x.get("published") or "", reverse=True)
    return {
        "updated_at": _now_iso(),
        "source_feeds": [name for name, _ in RSS_FEEDS],
        "query": "Copa do Mundo 2026 / World Cup 2026",
        "total": len(items),
        "items": items[:MAX_NEWS],
    }


# ─── Builder: grupos.json (classificação da fase de grupos) ───────────
def build_grupos(matches: list, teams_index: dict) -> dict:
    """
    Classificação completa dos grupos (A–L): pts/V/E/D/GP/GC/SG/jogos.
    Ordenação: pts → SG → GP → nome. Top 3 marcados como classificados.
    """
    groups: dict[str, dict[str, dict]] = {}

    def _stat(g, name):
        if name not in g:
            info = _team_info(name, teams_index)
            g[name] = {
                "name": name, "code": info["code"], "flag": info["flag"],
                "pts": 0, "wins": 0, "draws": 0, "losses": 0,
                "goals_for": 0, "goals_against": 0, "played": 0,
            }
        return g[name]

    for m in matches:
        round_name = m.get("round") or ""
        if "Matchday" not in round_name:
            continue
        final = _final_score(m.get("score") or {})
        if final is None:
            continue
        grp = m.get("group") or ""
        if not grp:
            continue
        if grp not in groups:
            groups[grp] = {}
        g = groups[grp]
        t1, t2 = m.get("team1") or "", m.get("team2") or ""
        if _is_placeholder(t1) or _is_placeholder(t2):
            continue
        s1, s2 = final
        st1, st2 = _stat(g, t1), _stat(g, t2)
        st1["played"] += 1; st2["played"] += 1
        st1["goals_for"] += s1; st1["goals_against"] += s2
        st2["goals_for"] += s2; st2["goals_against"] += s1
        if s1 > s2:
            st1["pts"] += 3; st1["wins"] += 1; st2["losses"] += 1
        elif s1 < s2:
            st2["pts"] += 3; st2["wins"] += 1; st1["losses"] += 1
        else:
            st1["pts"] += 1; st2["pts"] += 1
            st1["draws"] += 1; st2["draws"] += 1

    out_groups = []
    for grp_name in sorted(groups):
        teams = list(groups[grp_name].values())
        for t in teams:
            t["diff"] = t["goals_for"] - t["goals_against"]
        teams.sort(key=lambda x: (x["pts"], x["diff"], x["goals_for"], -ord(x["name"][0])), reverse=True)
        for i, t in enumerate(teams):
            t["position"] = i + 1
            t["qualified"] = i < 3
        out_groups.append({"group": grp_name, "teams": teams})

    return {
        "updated_at": _now_iso(),
        "source": "openfootball/worldcup.json (cálculo local)",
        "total_groups": len(out_groups),
        "groups": out_groups,
    }


# ─── Builder: simulacao.json (Monte Carlo do mata-mata) ───────────────
def _elo_ratings(matches: list) -> dict[str, float]:
    """Ratings Elo atuais (pós todos os jogos decididos). Helper reusável."""
    ratings: dict[str, float] = {}
    chronological = sorted(
        matches, key=lambda m: ((m.get("date") or "")[:10], m.get("time") or "")
    )
    for m in chronological:
        t1, t2 = m.get("team1") or "", m.get("team2") or ""
        if _is_placeholder(t1) or _is_placeholder(t2):
            continue
        final = _final_score(m.get("score") or {})
        if final is None:
            continue
        s1, s2 = final
        sa, sb = (1.0, 0.0) if s1 > s2 else (0.0, 1.0) if s1 < s2 else (0.5, 0.5)
        ra = ratings.setdefault(t1, ELO_INIT)
        rb = ratings.setdefault(t2, ELO_INIT)
        ea = _elo_expected(ra, rb)
        k = _elo_k(abs(s1 - s2))
        ratings[t1] = ra + k * (sa - ea)
        ratings[t2] = rb + k * (sb - (1 - ea))
    return ratings


def _resolve_slot(name: str, sim_results: dict) -> str | None:
    """Resolve placeholder W83/L101 → nome real (ou None se dependência pendente)."""
    if not name:
        return None
    m = re.match(r"^W(\d+)$", name)
    if m:
        n = int(m.group(1))
        return sim_results.get(n, (None, None))[0]
    m = re.match(r"^L(\d+)$", name)
    if m:
        n = int(m.group(1))
        return sim_results.get(n, (None, None))[1]
    return name


def build_simulacao(matches: list, teams_index: dict) -> dict:
    """
    Monte Carlo: simula o mata-mata restante 10k× usando probabilidades Elo,
    propagando vencedores pelos placeholders (W83/L101) até a final.
    Retorna a distribuição REAL de probabilidade de título por seleção.
    """
    ratings = _elo_ratings(matches)
    by_num = {m["num"]: m for m in matches if m.get("num") is not None}
    ko_nums = sorted(
        n for n, m in by_num.items()
        if m.get("round") and "Matchday" not in m["round"]
    )
    if not ko_nums:
        return {
            "updated_at": _now_iso(),
            "methodology": "Monte Carlo — mata-mata ainda não definido.",
            "simulations": 0, "teams": [],
        }

    final_nums = [n for n in ko_nums if by_num[n]["round"] == "Final"]
    final_num = final_nums[0] if final_nums else max(ko_nums)

    SIMS = 10000
    title_counts: dict[str, int] = {}

    for _ in range(SIMS):
        sim_results: dict[int, tuple[str, str]] = {}
        for n in ko_nums:
            m = by_num[n]
            t1 = _resolve_slot(m.get("team1") or "", sim_results)
            t2 = _resolve_slot(m.get("team2") or "", sim_results)
            if not t1 or not t2:
                continue
            score = m.get("score") or {}
            t1_raw, t2_raw = m.get("team1") or "", m.get("team2") or ""
            ft = score.get("ft") if isinstance(score, dict) else None
            if ft and not _is_placeholder(t1_raw) and not _is_placeholder(t2_raw):
                # Resultado real — determina vencedor pela progressão KO:
                # tempo normal → prorrogação → pênaltis
                s1, s2 = int(ft[0]), int(ft[1])
                et = score.get("et") if isinstance(score, dict) else None
                pen = score.get("p") if isinstance(score, dict) else None
                if s1 > s2:
                    sim_results[n] = (t1, t2)
                elif s2 > s1:
                    sim_results[n] = (t2, t1)
                elif et and int(et[0]) != int(et[1]):
                    sim_results[n] = (t1, t2) if int(et[0]) > int(et[1]) else (t2, t1)
                elif pen:
                    sim_results[n] = (t1, t2) if int(pen[0]) > int(pen[1]) else (t2, t1)
                else:
                    sim_results[n] = (t1, t2)
            else:
                ra = ratings.get(t1, ELO_INIT)
                rb = ratings.get(t2, ELO_INIT)
                p1 = _elo_expected(ra, rb)
                sim_results[n] = (t1, t2) if random.random() < p1 else (t2, t1)
        if final_num in sim_results:
            champ = sim_results[final_num][0]
            title_counts[champ] = title_counts.get(champ, 0) + 1

    teams = []
    for name, count in sorted(title_counts.items(), key=lambda x: -x[1]):
        info = _team_info(name, teams_index)
        teams.append({
            "name": name, "code": info["code"], "flag": info["flag"],
            "elo": round(ratings.get(name, ELO_INIT), 1),
            "titles": count,
            "title_probability": round(count / SIMS * 100, 2),
        })
    for i, t in enumerate(teams, 1):
        t["rank"] = i

    return {
        "updated_at": _now_iso(),
        "methodology": (
            f"Monte Carlo com {SIMS} simulações do mata-mata restante. "
            "Cada jogo não-decidido é sorteado via probabilidade Elo "
            "(1/(1+10^((Rb-Ra)/400))). Placeholders W83/L101 resolvidos "
            "sequencialmente. Resultados reais (já jogados) são fixos."
        ),
        "simulations": SIMS,
        "total_teams": len(teams),
        "teams": teams,
    }


# ─── Builder: insights.json (estatística editorial automática) ────────
def build_insights(matches: list, teams_index: dict) -> dict:
    """Gera fatos editoriais automáticos a partir dos dados do torneio."""
    stats = build_estatisticas(matches, teams_index)
    agg = _aggregate_goals(matches, teams_index)
    grupos = build_grupos(matches, teams_index)
    insights: list[dict] = []

    def _add(icon: str, title: str, body: str):
        insights.append({"icon": icon, "title": title, "body": body})

    # Artilheiro
    if stats.get("total_goals", 0) > 0 and agg:
        top = max(agg.values(), key=lambda p: p["goals"])
        if top["goals"] > 0:
            _add("⚽", "Artilheiro isolado",
                 f"{top['name']} ({top['team']['flag']} {top['team']['code']}) "
                 f"lidera com {top['goals']} gols em {top['team']['name']}.")

    # Média de gols
    avg = stats.get("avg_goals_per_match", 0)
    total = stats.get("total_matches", 0)
    if total > 0:
        verdict = "acima" if avg > 2.5 else "abaixo" if avg < 2.0 else "alinhada com"
        _add("📊", "Ritmo ofensivo",
             f"Média de {avg} gols por jogo em {total} partidas — "
             f"{verdict} da histórica (~2.5).")

    # Maior goleada
    bw = stats.get("biggest_win")
    if bw:
        _add("🔥", "Maior goleada", f"{bw['match']} — diferença de {bw['diff']} gols.")

    # Seleção com 100% em TODOS os jogos (não só fase de grupos)
    all_records: dict[str, dict] = {}
    for m in matches:
        final = _final_score(m.get("score") or {})
        if final is None:
            continue
        t1, t2 = m.get("team1") or "", m.get("team2") or ""
        if _is_placeholder(t1) or _is_placeholder(t2):
            continue
        s1, s2 = final
        for name, gf, ga in ((t1, s1, s2), (t2, s2, s1)):
            if name not in all_records:
                all_records[name] = {"wins": 0, "played": 0}
            all_records[name]["played"] += 1
            if gf > ga:
                all_records[name]["wins"] += 1
    for name, r in all_records.items():
        if r["played"] >= 3 and r["wins"] == r["played"]:
            info = _team_info(name, teams_index)
            _add("💯", "Aproveitamento perfeito",
                 f"{info['flag']} {name} venceu todos os {r['played']} jogos sem ceder pontos.")
            break

    # Melhor ataque
    eff = stats.get("teams_efficiency", [])
    if eff:
        best_atk = max(eff, key=lambda x: x["goals_for"])
        _add("🚀", "Ataque mais letal",
             f"{best_atk['flag']} {best_atk['name']} marcou {best_atk['goals_for']} gols "
             f"em {best_atk['matches']} jogos.")
        best_def = min(eff, key=lambda x: x["goals_against"])
        if best_def["goals_against"] < best_atk["goals_for"]:
            _add("🛡️", "Defesa mais sólida",
                 f"{best_def['flag']} {best_def['name']} sofreu apenas "
                 f"{best_def['goals_against']} gols em {best_def['matches']} jogos.")

    # Distribuição por tempo
    fh = stats.get("goals_first_half", 0)
    sh = stats.get("goals_second_half", 0)
    if fh + sh > 0:
        half = "segundo" if sh > fh else "primeiro" if fh > sh else "empate"
        _add("⏱️", "Quando os gols caem",
             f"{fh} no 1º tempo vs {sh} no 2º — maioria no {half} tempo.")

    # Pênaltis
    pens = stats.get("penalties_scored", 0)
    if pens > 0:
        _add("🎯", "Da marca penal", f"{pens} gols de pênalti marcados no torneio.")

    return {
        "updated_at": _now_iso(),
        "source": "cálculo local sobre openfootball/worldcup.json",
        "total": len(insights),
        "insights": insights,
    }


# ─── Builder: selecao_copa.json (11 ideal + goleiro menos vazado) ─────
def _build_squads_by_team(squads_data) -> dict[str, list[dict]]:
    """Indexa elencos: {team_name: [{name, pos, number}]}."""
    out: dict[str, list[dict]] = {}
    if not isinstance(squads_data, list):
        return out
    for squad in squads_data:
        if not isinstance(squad, dict):
            continue
        team = squad.get("name") or ""
        players = squad.get("players") or []
        out[team] = [
            {"name": p.get("name", ""), "pos": (p.get("pos") or "")[:2].upper(), "number": p.get("number")}
            for p in players if isinstance(p, dict) and p.get("name")
        ]
        # Alias de nome (USA/United States etc.)
        for alt in ("name_normalised", "title"):
            alt_name = squad.get(alt)
            if alt_name and alt_name not in out:
                out[alt_name] = out[team]
    return out


def build_selecao_copa(matches: list, teams_index: dict, squads_by_team: dict) -> dict:
    """
    Seleção da Copa até o momento — 11 ideal baseado em desempenho real:
      • GK: goleiro da seleção com menos gols sofridos/jogo (clean sheets)
      • DF: 4 defensores — das seleções com melhor defesa que marcaram,
            completados com titulares das melhores defesas
      • MF: 3 meio-campistas com mais gols
      • FW: 3 artilheiros
    Métricas derivadas das partidas (não há stats individuais defensivas
    no Openfootball — goleiro é inferido pela defesa da seleção).
    """
    # 1. Defesa por seleção (gols sofridos, jogos, clean sheets)
    defense: dict[str, dict] = {}
    scorers = _aggregate_goals(matches, teams_index)

    for m in matches:
        final = _final_score(m.get("score") or {})
        if final is None:
            continue
        t1, t2 = m.get("team1") or "", m.get("team2") or ""
        if _is_placeholder(t1) or _is_placeholder(t2):
            continue
        s1, s2 = final
        for name, conceded in ((t1, s2), (t2, s1)):
            if name not in defense:
                defense[name] = {"goals_against": 0, "played": 0, "clean_sheets": 0}
            defense[name]["goals_against"] += conceded
            defense[name]["played"] += 1
            if conceded == 0:
                defense[name]["clean_sheets"] += 1

    for name, d in defense.items():
        d["ga_per_game"] = round(d["goals_against"] / d["played"], 2) if d["played"] else 99

    # 2. Ranking de goleiros (melhor defesa → goleiro titular = primeiro GK)
    best_defense = sorted(
        [(n, d) for n, d in defense.items() if d["played"] >= 2],
        key=lambda x: (x[1]["ga_per_game"], -x[1]["clean_sheets"], x[1]["goals_against"]),
    )

    def _first_pos(team: str, pos: str) -> dict | None:
        players = squads_by_team.get(team) or []
        for p in players:
            if p["pos"] == pos:
                return {"name": p["name"], "team": _team_info(team, teams_index), "position": pos}
        return None

    xi: list[dict] = []
    used_teams: set[str] = set()

    # GK: melhor defesa
    gk_entry = None
    for team, d in best_defense:
        gk = _first_pos(team, "GK")
        if gk:
            gk_entry = {**gk, "stat": f"{d['clean_sheets']} clean sheets · {d['ga_per_game']} GA/jogo"}
            used_teams.add(team)
            xi.append(gk_entry)
            break

    # FW: top 3 artilheiros
    top_scorers = sorted(scorers.values(), key=lambda p: p["goals"], reverse=True)
    fw_added = 0
    for s in top_scorers:
        if fw_added >= 3 or s["goals"] == 0:
            break
        xi.append({
            "name": s["name"], "team": s["team"], "position": "FW",
            "stat": f"{s['goals']} gols",
        })
        fw_added += 1

    # MF: meio-campistas com mais gols
    mf_pool = [
        (slug, p) for slug, p in scorers.items()
        if p["goals"] > 0
        and squads_by_team
        and any(
            squads_by_team.get(p["team"]["name"], [{}])[0].get("pos") == "MF"
            or any(pl["pos"] == "MF" and pl["name"] == p["name"]
                   for pl in squads_by_team.get(p["team"]["name"], []))
            for _ in [0]
        )
    ]
    # Fallback: se não há dados de posição, pega artilheiros não-FW por eliminação
    if not mf_pool:
        mf_pool = [(slug, p) for slug, p in scorers.items() if p["goals"] > 0]
    mf_pool.sort(key=lambda x: x[1]["goals"], reverse=True)
    mf_added = 0
    used_names = {p["name"] for p in xi}
    for slug, p in mf_pool:
        if mf_added >= 3 or p["name"] in used_names:
            continue
        # Confirma posição MF se possível
        pos = "MF"
        players = squads_by_team.get(p["team"]["name"]) or []
        for pl in players:
            if pl["name"] == p["name"]:
                pos = pl["pos"] or "MF"
                break
        xi.append({
            "name": p["name"], "team": p["team"], "position": pos,
            "stat": f"{p['goals']} gols",
        })
        used_names.add(p["name"])
        mf_added += 1

    # DF: completar 4 — das melhores defesas restantes
    df_added = 0
    for team, d in best_defense:
        if df_added >= 4:
            break
        df = _first_pos(team, "DF")
        if df and df["name"] not in {p["name"] for p in xi}:
            xi.append({**df, "stat": f"defesa {d['ga_per_game']} GA/jogo · {d['clean_sheets']} CS"})
            df_added += 1

    # Ordena por posição (GK, DF, MF, FW)
    pos_order = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}
    xi.sort(key=lambda p: pos_order.get(p.get("position", "FW"), 4))

    # Top goleiros (ranking completo para destaque)
    top_gks = []
    for team, d in best_defense[:5]:
        gk = _first_pos(team, "GK")
        if gk:
            top_gks.append({**gk, "clean_sheets": d["clean_sheets"], "ga_per_game": d["ga_per_game"], "goals_against": d["goals_against"]})

    return {
        "updated_at": _now_iso(),
        "source": "openfootball (partidas + squads) — inferência defensiva",
        "formation": "4-3-3",
        "best_goalkeeper": gk_entry,
        "top_goalkeepers": top_gks,
        "xi": xi,
    }


# ─── Orquestrador ─────────────────────────────────────────────────────
def main() -> int:
    print("🏆 World Cup Dashboard — coleta iniciada")
    print(f"   UTC: {_now_iso()}")
    print(f"   Saída: {OUTPUT_DIR}/\n")

    exit_code = 0

    matches, teams_index = fetch_openfootball()
    if not matches:
        print("  ⚠ Sem partidas — 9 arquivos não atualizados.")
        exit_code = 1
    else:
        squads_data = _http_get_json(URL_SQUADS) or []
        squads_index = _build_squads_index(squads_data)
        squads_by_team = _build_squads_by_team(squads_data)
        for name, builder, args in (
            ("partidas", build_partidas, (matches, teams_index)),
            ("artilheiros", build_artilheiros, (matches, teams_index)),
            ("estatisticas", build_estatisticas, (matches, teams_index)),
            ("probabilidades", build_probabilidades, (matches, teams_index)),
            ("jogadores", build_jogadores, (matches, teams_index, squads_index)),
            ("grupos", build_grupos, (matches, teams_index)),
            ("simulacao", build_simulacao, (matches, teams_index)),
            ("selecao_copa", build_selecao_copa, (matches, teams_index, squads_by_team)),
            ("insights", build_insights, (matches, teams_index)),
            ("comparativo_copas", build_comparativo, (matches, teams_index)),
            ("idade_copas", build_idade_copas, (matches, teams_index)),
        ):
            print(f"  ▸ {name}.json...")
            try:
                _write_json_resilient(OUTPUT_DIR / f"{name}.json", builder(*args))
            except Exception as e:
                print(f"    ✗ Erro em {name}.json: {e}")
                exit_code = 1

    print("  ▸ noticias.json...")
    try:
        _write_json_resilient(OUTPUT_DIR / "noticias.json", fetch_noticias())
    except Exception as e:
        print(f"    ✗ Erro em noticias.json: {e}")
        exit_code = 1

    print("\n✅ Coleta finalizada." if exit_code == 0 else "\n⚠ Coleta finalizada com avisos.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
