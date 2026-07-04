"""
World Cup Dashboard — Ball-Level Data Pipeline (Custo Zero)
===========================================================
Camada de análise para as seções 04/05/06 do dashboard.

FONTE 1 — openfootball (garantido, 100% real 2026):
    gols com minuto → momentum (gols acumulados por minuto)
    Cobertura: todas as partidas finalizadas da Copa 2026.

FONTE 2 — ESPN API (garantido, 100% real 2026, sem auth):
    site.api.espn.com/.../fifa.world → 28 stats por time por partida
    Inclui: chutes, chutes no alvo, posse, passes, cruzamentos, etc.
    Cobertura: 90+ partidas finalizadas da Copa 2026.

HONESTIDADE: a Adidas Trionda tem chip IMU, mas esse stream é privado.
As estatísticas aqui vêm de tracking agregado da ESPN e gols do
openfootball — rastreamento óptico, não telemetria do chip.

    deepstats.json ← openfootball (momentum) + ESPN (stats de chute/passe)

Uso:
    python ingestion_worldcup/fetch_ball_level.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ─── Fontes ───────────────────────────────────────────────────────────
OPENFOOTBALL_RAW = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master"
)
URL_MATCHES_2026 = f"{OPENFOOTBALL_RAW}/2026/worldcup.json"

ESPN_SCOREBOARD = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
    "/scoreboard?dates=20260611-20260719"
)
ESPN_SUMMARY = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
    "/summary?event={event_id}"
)

# ─── Configuração ─────────────────────────────────────────────────────
OUTPUT_DIR = Path("public/world-cup-dashboard/data")
HTTP_TIMEOUT = 30
ESPN_DELAY = 0.4  # segundos entre requests de summary (rate-limit friendly)
MAX_ESPN_SUMMARIES = 20  # top N partidas por gols
USER_AGENT = "worldcup-dashboard/1.0 (+https://github.com/Donotavio/cv-site-otavio)"

# WC 2026 teams: name → (code, flag)
WC2026_TEAMS: dict[str, tuple[str, str]] = {
    "Algeria": ("ALG", "🇩🇿"), "Argentina": ("ARG", "🇦🇷"),
    "Australia": ("AUS", "🇦🇺"), "Austria": ("AUT", "🇦🇹"),
    "Belgium": ("BEL", "🇧🇪"), "Bosnia & Herzegovina": ("BIH", "🇧🇦"),
    "Brazil": ("BRA", "🇧🇷"), "Canada": ("CAN", "🇨🇦"),
    "Cape Verde": ("CPV", "🇨🇻"), "Colombia": ("COL", "🇨🇴"),
    "Croatia": ("CRO", "🇭🇷"), "Curaçao": ("CUW", "🇨🇼"),
    "Czech Republic": ("CZE", "🇨🇿"), "DR Congo": ("COD", "🇨🇩"),
    "Ecuador": ("ECU", "🇪🇨"), "Egypt": ("EGY", "🇪🇬"),
    "England": ("ENG", "🏴󠁧󠁢󠁥󠁮󠁧󠁿"), "France": ("FRA", "🇫🇷"),
    "Germany": ("GER", "🇩🇪"), "Ghana": ("GHA", "🇬🇭"),
    "Haiti": ("HAI", "🇭🇹"), "Iran": ("IRN", "🇮🇷"),
    "Iraq": ("IRQ", "🇮🇶"), "Ivory Coast": ("CIV", "🇨🇮"),
    "Japan": ("JPN", "🇯🇵"), "Jordan": ("JOR", "🇯🇴"),
    "Mexico": ("MEX", "🇲🇽"), "Morocco": ("MAR", "🇲🇦"),
    "Netherlands": ("NED", "🇳🇱"), "New Zealand": ("NZL", "🇳🇿"),
    "Norway": ("NOR", "🇳🇴"), "Panama": ("PAN", "🇵🇦"),
    "Paraguay": ("PAR", "🇵🇾"), "Portugal": ("POR", "🇵🇹"),
    "Qatar": ("QAT", "🇶🇦"), "Saudi Arabia": ("KSA", "🇸🇦"),
    "Scotland": ("SCO", "🏴󠁧󠁢󠁳󠁣󠁴󠁿"), "Senegal": ("SEN", "🇸🇳"),
    "South Africa": ("RSA", "🇿🇦"), "South Korea": ("KOR", "🇰🇷"),
    "Spain": ("ESP", "🇪🇸"), "Sweden": ("SWE", "🇸🇪"),
    "Switzerland": ("SUI", "🇨🇭"), "Tunisia": ("TUN", "🇹🇳"),
    "Turkey": ("TUR", "🇹🇷"), "USA": ("USA", "🇺🇸"),
    "Uruguay": ("URU", "🇺🇾"), "Uzbekistan": ("UZB", "🇺🇿"),
}

# ESPN usa nomes ligeiramente diferentes → mapear para o nosso padrão
ESPN_NAME_FIX: dict[str, str] = {
    "Czechia": "Czech Republic",
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
    "United States": "USA",
    "IR Iran": "Iran",
    "Korea Republic": "South Korea",
    "Côte d'Ivoire": "Ivory Coast",
}


# ─── HTTP / IO helpers ────────────────────────────────────────────────
def _http_get(url: str, timeout: int = HTTP_TIMEOUT) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_get_json(url: str, timeout: int = HTTP_TIMEOUT) -> list | dict | None:
    try:
        return json.loads(_http_get(url, timeout).decode("utf-8"))
    except (URLError, HTTPError, TimeoutError, ValueError, OSError) as e:
        print(f"    ✗ Falha ao buscar {url}: {e}")
        return None


def _write_json_resilient(path: Path, payload: dict) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if path.exists():
        try:
            old_text = path.read_text(encoding="utf-8")
            norm = lambda t: re.sub(r'"updated_at"\s*:\s*"[^"]*"', '"updated_at": "@@"', t)
            if norm(old_text) == norm(new_text):
                print(f"    = {path.name} sem alterações — mantido.")
                return False
        except OSError:
            pass
    path.write_text(new_text, encoding="utf-8")
    print(f"    ✓ {path.name} ({len(new_text)} bytes)")
    return True


def _team_meta(name: str) -> tuple[str, str]:
    return WC2026_TEAMS.get(name, ("???", "🏳️"))


def _normalize_name(name: str) -> str:
    """Normaliza nome de seleção para matching entre fontes."""
    name = ESPN_NAME_FIX.get(name, name)
    return name.lower().strip()


def _parse_minute(raw) -> int:
    s = str(raw or "0").replace("'", "").strip()
    m = re.match(r"(\d+)", s)
    return int(m.group(1)) if m else 90


def _match_id(team1: str, team2: str, date: str) -> str:
    c1 = _team_meta(team1)[0].lower()
    c2 = _team_meta(team2)[0].lower()
    return f"{c1}-{c2}-{date}"


# ═══════════════════════════════════════════════════════════════════════
# PHASE 1 — openfootball: momentum de TODAS as partidas finalizada
# ═══════════════════════════════════════════════════════════════════════
def build_momentum(match: dict) -> dict | None:
    """Constrói série temporal de gols acumulados (5 em 5 min)."""
    team1 = match.get("team1", "?")
    team2 = match.get("team2", "?")
    ft = match.get("score", {}).get("ft")
    if not ft or not isinstance(ft, list):
        return None
    goals1 = match.get("goals1") or []
    goals2 = match.get("goals2") or []
    total = len(goals1) + len(goals2)
    if total == 0:
        return None

    labels = list(range(0, 91, 5))

    def cumulative(gl: list[dict]) -> list[int]:
        minutes = [_parse_minute(g.get("minute")) for g in gl]
        return [sum(1 for m in minutes if m <= b) for b in labels]

    def markers(gl: list[dict], side: str) -> list[dict]:
        result = []
        for g in gl:
            minute = _parse_minute(g.get("minute"))
            cum = sum(1 for x in gl if _parse_minute(x.get("minute")) <= minute)
            result.append({"minute": minute, "team": side, "player": g.get("name", ""), "cum": cum})
        return result

    code1, flag1 = _team_meta(team1)
    code2, flag2 = _team_meta(team2)

    return {
        "id": _match_id(team1, team2, match.get("date", "")),
        "label": f"{team1} {ft[0]}–{ft[1]} {team2}",
        "date": match.get("date", ""),
        "total_goals": total,
        "metric": "goals",
        "metric_label": "Gols acumulados",
        "labels": labels,
        "home": {"code": code1, "flag": flag1, "name": team1, "cum": cumulative(goals1)},
        "away": {"code": code2, "flag": flag2, "name": team2, "cum": cumulative(goals2)},
        "goals": markers(goals1, "home") + markers(goals2, "away"),
    }


def fetch_openfootball_momentum() -> list[dict]:
    """Busca openfootball e computa momentum de todas as partidas com gols."""
    data = _http_get_json(URL_MATCHES_2026)
    if not data or not isinstance(data, dict) or not data.get("matches"):
        return []
    matches = data["matches"]
    print(f"    ✓ {len(matches)} partidas no índice openfootball")

    results = []
    for m in matches:
        mom = build_momentum(m)
        if mom:
            results.append(mom)

    # Ordena por mais gols → data mais recente
    results.sort(key=lambda x: (x["total_goals"], x["date"]), reverse=True)
    print(f"    ✓ {len(results)} partidas com gols → momentum computado")
    return results


# ═══════════════════════════════════════════════════════════════════════
# PHASE 2 — ESPN: stats de chute e passe das top partidas
# ═══════════════════════════════════════════════════════════════════════
def fetch_espn_events() -> list[dict]:
    """Busca o scoreboard da ESPN e retorna partidas finalizadas."""
    data = _http_get_json(ESPN_SCOREBOARD)
    if not data or not isinstance(data, dict):
        return []

    events = data.get("events", [])
    completed = []
    for e in events:
        comps = e.get("competitions", [{}])
        c = comps[0] if comps else {}
        if not c.get("status", {}).get("type", {}).get("completed", False):
            continue

        competitors = c.get("competitors", [])
        if len(competitors) < 2:
            continue

        # home = primeiro, away = segundo (ESPN ordena por homeAway)
        home_data = next((x for x in competitors if x.get("homeAway") == "home"), competitors[0])
        away_data = next((x for x in competitors if x.get("homeAway") == "away"), competitors[1])

        home_name = home_data.get("team", {}).get("displayName", "?")
        away_name = away_data.get("team", {}).get("displayName", "?")
        home_score = int(home_data.get("score", 0))
        away_score = int(away_data.get("score", 0))

        completed.append({
            "event_id": e.get("id", ""),
            "home_name": ESPN_NAME_FIX.get(home_name, home_name),
            "away_name": ESPN_NAME_FIX.get(away_name, away_name),
            "home_score": home_score,
            "away_score": away_score,
            "total_goals": home_score + away_score,
            "date": c.get("date", "")[:10],
        })

    completed.sort(key=lambda x: x["total_goals"], reverse=True)
    print(f"    ✓ {len(completed)} partidas finalizadas na ESPN")
    return completed


def _extract_stat(stats: list[dict], label: str) -> int | float:
    """Extrai um valor de estatística do array stats da ESPN."""
    for s in stats:
        if s.get("label", "").lower() == label.lower():
            val = s.get("displayValue", "0")
            try:
                return float(val)
            except (ValueError, TypeError):
                return 0
    return 0


def fetch_espn_summary(event_id: str) -> dict | None:
    """Busca o summary da ESPN e extrai stats de chute e passe."""
    url = ESPN_SUMMARY.format(event_id=event_id)
    data = _http_get_json(url, timeout=15)
    if not data or not isinstance(data, dict):
        return None

    box = data.get("boxscore", {})
    teams = box.get("teams", [])
    if len(teams) < 2:
        return None

    def parse_team(t: dict) -> dict:
        stats = t.get("statistics", [])
        team_info = t.get("team", {})
        name = team_info.get("displayName", "?")
        name = ESPN_NAME_FIX.get(name, name)
        code, flag = _team_meta(name)
        shots = int(_extract_stat(stats, "SHOTS"))
        on_target = int(_extract_stat(stats, "ON GOAL"))
        blocked = int(_extract_stat(stats, "Blocked Shots"))
        goals = int(_extract_stat(stats, "Penalty Goals"))  # nem sempre presente
        passes = int(_extract_stat(stats, "Passes"))
        accurate = int(_extract_stat(stats, "Accurate Passes"))
        pct = _extract_stat(stats, "Pass Completion %")
        crosses = int(_extract_stat(stats, "Crosses"))
        acc_crosses = int(_extract_stat(stats, "Accurate Crosses"))
        long_balls = int(_extract_stat(stats, "Long Balls"))
        possession = _extract_stat(stats, "Possession")
        return {
            "code": code, "flag": flag, "name": name,
            "shots": shots, "on_target": on_target, "blocked": blocked,
            "passes": passes, "accurate_passes": accurate,
            "pass_pct": round(pct * 100, 1) if pct < 1 else round(pct, 1),
            "crosses": crosses, "accurate_crosses": acc_crosses,
            "long_balls": long_balls,
            "possession": round(possession, 1),
        }

    home = parse_team(teams[0])
    away = parse_team(teams[1])

    # Score do header (mais confiável que stats)
    header = data.get("header", {})
    comps = header.get("competitions", [{}])
    if comps:
        competitors = comps[0].get("competitors", [])
        for c in competitors:
            if c.get("homeAway") == "home":
                home["goals"] = int(c.get("score", 0))
            elif c.get("homeAway") == "away":
                away["goals"] = int(c.get("score", 0))

    return {"home": home, "away": away}


def fetch_espn_stats(momentum_matches: list[dict]) -> tuple[dict, dict]:
    """
    Busca ESPN stats para as top N partidas (por gols).
    Retorna (shot_stats_by_id, pass_stats_by_id).
    """
    events = fetch_espn_events()
    if not events:
        return {}, {}

    # Indexa momentum por nome normalizado para matching
    mom_index: dict[str, dict] = {}
    for m in momentum_matches:
        key = f"{_normalize_name(m['home']['name'])}-{_normalize_name(m['away']['name'])}"
        mom_index[key] = m

    shot_stats: dict[str, dict] = {}
    pass_stats: dict[str, dict] = {}
    fetched = 0

    for ev in events[:MAX_ESPN_SUMMARIES]:
        key = f"{_normalize_name(ev['home_name'])}-{_normalize_name(ev['away_name'])}"
        mom = mom_index.get(key)
        if not mom:
            # Tenta ordem inversa (ESPN pode listar away primeiro)
            key_rev = f"{_normalize_name(ev['away_name'])}-{_normalize_name(ev['home_name'])}"
            mom = mom_index.get(key_rev)
        if not mom:
            continue

        match_id = mom["id"]
        summary = fetch_espn_summary(ev["event_id"])
        if not summary:
            continue

        label = mom["label"]
        shot_stats[match_id] = {
            "match": label,
            "source": "ESPN",
            "home": {k: summary["home"].get(k, 0) for k in ("code", "flag", "name", "shots", "on_target", "blocked", "goals")},
            "away": {k: summary["away"].get(k, 0) for k in ("code", "flag", "name", "shots", "on_target", "blocked", "goals")},
        }
        pass_stats[match_id] = {
            "match": label,
            "source": "ESPN",
            "home": {k: summary["home"].get(k, 0) for k in
                     ("code", "flag", "name", "passes", "accurate_passes", "pass_pct", "crosses", "accurate_crosses", "long_balls", "possession")},
            "away": {k: summary["away"].get(k, 0) for k in
                     ("code", "flag", "name", "passes", "accurate_passes", "pass_pct", "crosses", "accurate_crosses", "long_balls", "possession")},
        }
        fetched += 1
        print(f"    ✓ ESPN stats: {label}")
        time.sleep(ESPN_DELAY)

    print(f"    ✓ {fetched} partidas com stats de ESPN")
    return shot_stats, pass_stats


# ─── Orquestração ─────────────────────────────────────────────────────
def main() -> int:
    print("═" * 60)
    print("Ball-Level Data Pipeline — World Cup 2026")
    print("  Fontes: openfootball (momentum) + ESPN (match stats)")
    print("═" * 60)

    # Phase 1: openfootball momentum (todas as partidas com gols)
    print("\n[1/3] Buscando momentum (openfootball)…")
    momentum_matches = fetch_openfootball_momentum()
    if not momentum_matches:
        print("    ✗ Nenhuma partida com gols — abortando.")
        return 1

    # Phase 2: ESPN stats (top N partidas)
    print(f"\n[2/3] Buscando stats de chute/passe (ESPN, top {MAX_ESPN_SUMMARIES})…")
    shot_stats, pass_stats = fetch_espn_stats(momentum_matches)

    # Phase 3: Monta JSON
    print("\n[3/3] Escrevendo deepstats.json…")

    featured = momentum_matches[0]
    featured_id = featured["id"]

    # Marca quais partidas têm stats
    match_list = []
    for m in momentum_matches:
        match_list.append({
            "id": m["id"],
            "label": m["label"],
            "date": m["date"],
            "goals": m["total_goals"],
            "has_stats": m["id"] in shot_stats,
        })

    # Momentum: dict indexado por ID (para lookup rápido no frontend)
    momentum_index = {m["id"]: m for m in momentum_matches}

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "openfootball (momentum) + ESPN (match stats)",
        "tournament": "FIFA World Cup 2026",
        "note": (
            "Momentum: gols reais por minuto via openfootball. "
            "Stats de chute/passe: ESPN. Rastreamento óptico, não "
            "telemetria do chip Trionda (privado)."
        ),
        "featured_id": featured_id,
        "match_list": match_list,
        "shot_stats": {
            "available": len(shot_stats) > 0,
            "source": "ESPN",
            "matches": shot_stats,
        },
        "pass_stats": {
            "available": len(pass_stats) > 0,
            "source": "ESPN",
            "matches": pass_stats,
        },
        "momentum": {
            "available": True,
            "metric": "goals",
            "metric_label": "Gols acumulados",
            "matches": momentum_index,
        },
    }

    output = OUTPUT_DIR / "deepstats.json"
    _write_json_resilient(output, payload)

    print(f"\n✅ Pipeline concluído.")
    print(f"   Momentum: {len(momentum_matches)} partidas")
    print(f"   Shot stats (ESPN): {len(shot_stats)} partidas")
    print(f"   Pass stats (ESPN): {len(pass_stats)} partidas")
    print(f"   Featured: {featured['label']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
