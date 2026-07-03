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
OUTPUT_DIR = Path("public/world-cup-dashboard/data")
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
    scorers = sorted(
        players.values(),
        key=lambda p: (p["goals"], -max(p["minutes"]) if p["minutes"] else 0),
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
            "Probabilidade de título via softmax (temp=180)."
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
    Ordenação: pts → SG → GP → nome. Top 2 marcados como classificados.
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
            t["qualified"] = i < 2
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
            ft = score.get("ft") if isinstance(score, dict) else None
            t1_raw, t2_raw = m.get("team1") or "", m.get("team2") or ""
            if ft and not _is_placeholder(t1_raw) and not _is_placeholder(t2_raw):
                s1, s2 = int(ft[0]), int(ft[1])
                if s1 > s2:
                    sim_results[n] = (t1, t2)
                elif s2 > s1:
                    sim_results[n] = (t2, t1)
                else:
                    pen = score.get("p") if isinstance(score, dict) else None
                    if pen:
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

    # Seleção com 100%
    for g in grupos.get("groups", []):
        for t in g["teams"]:
            if t["played"] >= 3 and t["wins"] == t["played"] and t["played"] > 0:
                _add("💯", "Aproveitamento perfeito",
                     f"{t['flag']} {t['name']} venceu todos os {t['played']} jogos "
                     f"do {g['group']} sem ceder pontos.")
                break
        else:
            continue
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
