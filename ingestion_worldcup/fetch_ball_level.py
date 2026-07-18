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
ESPN_DELAY = 0.25           # s entre requests (rate-limit friendly)
ESPN_HARD_MAX = 200         # teto de segurança — cobre as ~104 partidas da Copa
ESPN_RETRY_ATTEMPTS = 2     # tentativas extras em falha transitória (429/5xx)
ESPN_RETRY_BACKOFF = 1.5    # multiplicador de backoff entre tentativas
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
    # Variantes adicionais — algumas aparecem em partidas específicas
    "Türkiye": "Turkey",
    "Congo DR": "DR Congo",
    "DR Congo": "DR Congo",  # normalização defensiva
}


# ─── HTTP / IO helpers ────────────────────────────────────────────────
def _http_get(url: str, timeout: int = HTTP_TIMEOUT) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_get_json(url: str, timeout: int = HTTP_TIMEOUT, retries: int = 0):
    """
    GET JSON com retry opcional em falha transitória (HTTP 429/5xx, timeout).
    Em caso de erro definitivo (404, JSON inválido), retorna None sem retry.
    """
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            raw = _http_get(url, timeout=timeout)
            return json.loads(raw.decode("utf-8"))
        except (URLError, HTTPError, TimeoutError, OSError) as e:
            last_err = e
            # 4xx definitivos (exceto 429) não compensam retry
            code = getattr(e, "code", None)
            if code is not None and code != 429 and 400 <= code < 500:
                print(f"    ✗ Falha definitiva {code} em {url}: {e}")
                return None
            if attempt < retries:
                wait = ESPN_RETRY_BACKOFF ** (attempt + 1)
                print(f"    ↻ Tentativa {attempt + 1}/{retries} em {wait:.1f}s… ({e})")
                time.sleep(wait)
                continue
            print(f"    ✗ Falha ao buscar {url}: {e}")
            return None
        except ValueError as e:  # JSON inválido — não retenta
            print(f"    ✗ JSON inválido em {url}: {e}")
            return None
    print(f"    ✗ Esgotadas {retries + 1} tentativas para {url}: {last_err}")
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
    data = _http_get_json(url, timeout=15, retries=ESPN_RETRY_ATTEMPTS)
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
        # ── Chute / finalização ──────────────────────────────────────
        shots = int(_extract_stat(stats, "SHOTS"))
        on_target = int(_extract_stat(stats, "ON GOAL"))
        blocked = int(_extract_stat(stats, "Blocked Shots"))
        goals = int(_extract_stat(stats, "Penalty Goals"))  # nem sempre presente
        # ── Passe / posse ────────────────────────────────────────────
        passes = int(_extract_stat(stats, "Passes"))
        accurate = int(_extract_stat(stats, "Accurate Passes"))
        crosses = int(_extract_stat(stats, "Crosses"))
        acc_crosses = int(_extract_stat(stats, "Accurate Crosses"))
        long_balls = int(_extract_stat(stats, "Long Balls"))
        acc_long_balls = int(_extract_stat(stats, "Accurate Long Balls"))
        possession = _extract_stat(stats, "Possession")
        # ── Defesa / disciplina (novos campos ESPN) ──────────────────
        fouls = int(_extract_stat(stats, "Fouls"))
        yellow_cards = int(_extract_stat(stats, "Yellow Cards"))
        red_cards = int(_extract_stat(stats, "Red Cards"))
        offsides = int(_extract_stat(stats, "Offsides"))
        corners = int(_extract_stat(stats, "Corner Kicks"))
        saves = int(_extract_stat(stats, "Saves"))
        tackles = int(_extract_stat(stats, "Tackles"))
        effective_tackles = int(_extract_stat(stats, "Effective Tackles"))
        interceptions = int(_extract_stat(stats, "Interceptions"))
        clearances = int(_extract_stat(stats, "Clearances"))
        # Percentuais derivados dos contadores brutos (mais precisos que o
        # displayValue arredondado da ESPN, que reporta ex.: 0.9 → 90%
        # quando o real é ~87%). Fail-soft: 0 quando denominador é 0.
        pass_pct = round(accurate / passes * 100, 1) if passes > 0 else 0.0
        on_target_pct = round(on_target / shots * 100, 1) if shots > 0 else 0.0
        return {
            "code": code, "flag": flag, "name": name,
            "shots": shots, "on_target": on_target, "blocked": blocked,
            "on_target_pct": on_target_pct,
            "passes": passes, "accurate_passes": accurate,
            "pass_pct": pass_pct,
            "crosses": crosses, "accurate_crosses": acc_crosses,
            "long_balls": long_balls, "accurate_long_balls": acc_long_balls,
            "possession": round(possession, 1),
            "fouls": fouls, "yellow_cards": yellow_cards, "red_cards": red_cards,
            "offsides": offsides, "corners": corners, "saves": saves,
            "tackles": tackles, "effective_tackles": effective_tackles,
            "interceptions": interceptions, "clearances": clearances,
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


def fetch_espn_stats(
    momentum_matches: list[dict],
) -> tuple[dict, dict, list[dict]]:
    """
    Busca ESPN stats para TODAS as partidas finalizadas disponíveis no
    scoreboard da ESPN (limitado apenas por ESPN_HARD_MAX como teto de
    segurança). Retorna (shot_stats_by_id, pass_stats_by_id,
    espn_only_matches).

    `espn_only_matches` contém metadados (id/label/date) das partidas
    que existem na ESPN mas não tinham momentum (ex.: 0-0 ou falha de
    matching de nome no openfootball) — usados para completar o
    match_list do deepstats.json.
    """
    events = fetch_espn_events()
    if not events:
        return {}, {}, []

    # Indexa momentum por nome normalizado (ordem direta e inversa)
    mom_index: dict[str, dict] = {}
    for m in momentum_matches:
        key = f"{_normalize_name(m['home']['name'])}-{_normalize_name(m['away']['name'])}"
        mom_index[key] = m

    shot_stats: dict[str, dict] = {}
    pass_stats: dict[str, dict] = {}
    espn_only_matches: list[dict] = []
    fetched = 0
    skipped_no_summary = 0

    total = min(len(events), ESPN_HARD_MAX)
    print(f"    ℹ Iterando sobre {total} partidas (ESPN scoreboard)")

    for idx, ev in enumerate(events[:ESPN_HARD_MAX], start=1):
        key = f"{_normalize_name(ev['home_name'])}-{_normalize_name(ev['away_name'])}"
        mom = mom_index.get(key)
        if not mom:
            # Tenta ordem inversa (ESPN pode listar away primeiro)
            key_rev = f"{_normalize_name(ev['away_name'])}-{_normalize_name(ev['home_name'])}"
            mom = mom_index.get(key_rev)

        # Mesmo sem momentum, geramos um ID próprio para a partida ESPN-only.
        # ID canônico: lowercase codes + data. Coincide com o formato do
        # openfootball se a ordem dos times for a mesma.
        home_code, _ = _team_meta(ev["home_name"])
        away_code, _ = _team_meta(ev["away_name"])
        fallback_id = f"{home_code.lower()}-{away_code.lower()}-{ev['date']}"
        fallback_label = f"{ev['home_name']} {ev['home_score']}–{ev['away_score']} {ev['away_name']}"

        match_id = mom["id"] if mom else fallback_id
        label = mom["label"] if mom else fallback_label

        # Evita re-buscar se já temos (pode acontecer se mom e fallback
        # colidirem para partidas diferentes).
        if match_id in shot_stats:
            continue

        summary = fetch_espn_summary(ev["event_id"])
        if not summary:
            skipped_no_summary += 1
            continue

        shot_keys = ("code", "flag", "name", "shots", "on_target",
                     "on_target_pct", "blocked", "goals")
        pass_keys = ("code", "flag", "name", "possession",
                     "passes", "accurate_passes", "pass_pct",
                     "crosses", "accurate_crosses",
                     "long_balls", "accurate_long_balls",
                     "corners", "offsides", "saves",
                     "tackles", "effective_tackles", "interceptions",
                     "clearances", "fouls", "yellow_cards", "red_cards")
        shot_stats[match_id] = {
            "match": label,
            "source": "ESPN",
            "home": {k: summary["home"].get(k, 0) for k in shot_keys},
            "away": {k: summary["away"].get(k, 0) for k in shot_keys},
        }
        pass_stats[match_id] = {
            "match": label,
            "source": "ESPN",
            "home": {k: summary["home"].get(k, 0) for k in pass_keys},
            "away": {k: summary["away"].get(k, 0) for k in pass_keys},
        }
        fetched += 1

        # Se a partida ESPN não tinha momentum, registra metadados para
        # incluir no match_list do deepstats.json (permitindo que ela
        # apareça no seletor do frontend, com stats mas sem chart).
        if not mom:
            espn_only_matches.append({
                "id": fallback_id,
                "label": fallback_label,
                "date": ev["date"],
                "goals": ev["total_goals"],
                "has_momentum": False,
            })

        if fetched % 10 == 0 or idx == total:
            print(f"    … {idx}/{total} processadas — {fetched} com stats")

        time.sleep(ESPN_DELAY)

    print(f"    ✓ {fetched} partidas com stats de ESPN"
          f" ({skipped_no_summary} sem summary)")
    return shot_stats, pass_stats, espn_only_matches


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

    # Phase 2: ESPN stats (todas as partidas disponíveis)
    print(f"\n[2/3] Buscando stats de chute/passe (ESPN, TODAS as finalizadas)…")
    shot_stats, pass_stats, espn_only_matches = fetch_espn_stats(momentum_matches)

    # Phase 3: Monta JSON
    print("\n[3/3] Escrevendo deepstats.json…")

    featured = momentum_matches[0]
    featured_id = featured["id"]

    # match_list = momentum (com gols) + ESPN-only (sem momentum, mas com stats).
    # Ordenação: por gols (desc) → data (desc) — partida com mais gols primeiro.
    match_list = []
    for m in momentum_matches:
        match_list.append({
            "id": m["id"],
            "label": m["label"],
            "date": m["date"],
            "goals": m["total_goals"],
            "has_stats": m["id"] in shot_stats,
            "has_momentum": True,
        })
    for m in espn_only_matches:
        m["has_stats"] = True  # só entram na lista se a ESPN retornou stats
        match_list.append(m)
    match_list.sort(key=lambda x: (x.get("goals", 0), x.get("date", "")), reverse=True)

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
