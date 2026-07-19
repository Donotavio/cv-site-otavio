"""
World Cup Dashboard — FIFA Official Data Snapshot (one-off, custo zero)
======================================================================
Snapshot dos dados OFICIAIS da FIFA (Copa do Mundo 2026) para as seções
de estatística agregada do painel. Diferente do `fetch_ball_level.py`
(ESPN = totais de jogo, sem xG/PPDA), aqui a fonte é o **FIFA Data Hub**
(`fdh-api.fifa.com`) — o mesmo feed do "Enhanced Football Intelligence"
oficial, com xG, Threat, PitchControl, distância por GPS, top speed, etc.

FONTES (todas HTTP 200, JSON, sem auth):
  - Teams:  fdh-api.fifa.com/v1/stats/season/285023/teams.json
            48 seleções × 141 stats — dict {IdTeam: [[StatName, value, isLive]...]}
            Valores CRUS: Possession fração (0.566), XG float, TotalDistance
            em METROS, TopSpeed km/h, contagens inteiras.
  - Players: fdh-api.fifa.com/v1/stats/season/285023/players.json
            1259 jogadores × 115 stats — mesma forma (sem nome/time embutido).
  - Power:  fdh-api.fifa.com/v1/powerranking/season/285023.json
            {outfieldPlayers[], goalkeepers[], nMatches, ...} — traz playerId,
            teamId, playerName[locale], teamName[locale] → PONTE de nomes.
  - Bridge: api.fifa.com/api/v3/calendar/matches?idCompetition=17&idSeason=285023
            IdTeam → nome oficial FIFA (en-GB) das 48 seleções.

Resolução de nome/bandeira: cada IdTeam da FIFA → nome canônico do projeto
(WC2026_TEAMS, o mesmo do fetch_ball_level) + {code, flag}. FIFA usa
grafias próprias ("Czechia", "Korea Republic", "Cabo Verde", "Türkiye"…)
→ FIFA_NAME_FIX mapeia para o canônico, com fallback fuzzy por slug.
Nomes de jogador em players.json vêm via join playerId ↔ powerranking
(cobertura parcial: só os ~230 do power ranking têm nome).

Saída (em assets/data/worldcup/):
  fifa_team_stats.json     — 48 seleções, ~22 métricas curadas + insights
  fifa_power_ranking.json  — ranking oficial FIFA (ataque/defesa/criatividade)
  fifa_player_stats.json   — top-N por família (finalização/criação/defesa/físico)

Uso (one-off — dado agregado da Copa; NÃO entra no cron diário):
    python3 ingestion_worldcup/fetch_fifa.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ─── Fontes ───────────────────────────────────────────────────────────
SEASON_ID = "285023"
COMPETITION_ID = "17"
FDH = "https://fdh-api.fifa.com/v1"
URL_TEAMS = f"{FDH}/stats/season/{SEASON_ID}/teams.json"
URL_PLAYERS = f"{FDH}/stats/season/{SEASON_ID}/players.json"
URL_POWER = f"{FDH}/powerranking/season/{SEASON_ID}.json"
URL_BRIDGE = (
    f"https://api.fifa.com/api/v3/calendar/matches"
    f"?idCompetition={COMPETITION_ID}&idSeason={SEASON_ID}&count=500&language=en"
)

# ─── Configuração ─────────────────────────────────────────────────────
OUTPUT_DIR = Path("assets/data/worldcup")
HTTP_TIMEOUT = 30
RETRY_ATTEMPTS = 2
RETRY_BACKOFF = 1.6
USER_AGENT = "worldcup-dashboard/1.0 (+https://github.com/Donotavio/cv-site-otavio)"
SOURCE = "FIFA Data Hub — fdh-api.fifa.com (dados oficiais Copa 2026)"

# WC 2026 teams: canonical name → (code, flag). Copiado de fetch_ball_level.py
# (fonte mais completa do campo 2026 no projeto).
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

# FIFA usa grafias oficiais próprias → mapear para o nome canônico do projeto.
# Verificado contra os 48 nomes en-GB do calendar bridge (season 285023):
# todos os que não batem direto estão aqui.
FIFA_NAME_FIX: dict[str, str] = {
    "Czechia": "Czech Republic",
    "Korea Republic": "South Korea",
    "Cabo Verde": "Cape Verde",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Congo DR": "DR Congo",
    "Côte d'Ivoire": "Ivory Coast",
    "IR Iran": "Iran",
    "Türkiye": "Turkey",
    # Variantes de outras fontes/locales do power ranking (defensivo)
    "United States": "USA",
    "USA": "USA",
    "Cote d'Ivoire": "Ivory Coast",
    "Turkiye": "Turkey",
}


# ─── HTTP / IO helpers (padrão fetch_ball_level.py) ───────────────────
def _http_get(url: str, timeout: int = HTTP_TIMEOUT) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_get_json(url: str, timeout: int = HTTP_TIMEOUT, retries: int = RETRY_ATTEMPTS):
    """GET JSON com retry em falha transitória (429/5xx/timeout)."""
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            raw = _http_get(url, timeout=timeout)
            return json.loads(raw.decode("utf-8"))
        except (URLError, HTTPError, TimeoutError, OSError) as e:
            last_err = e
            code = getattr(e, "code", None)
            if code is not None and code != 429 and 400 <= code < 500:
                print(f"    ✗ Falha definitiva {code} em {url}: {e}")
                return None
            if attempt < retries:
                wait = RETRY_BACKOFF ** (attempt + 1)
                print(f"    ↻ Tentativa {attempt + 1}/{retries} em {wait:.1f}s… ({e})")
                time.sleep(wait)
                continue
            print(f"    ✗ Falha ao buscar {url}: {e}")
            return None
        except ValueError as e:
            print(f"    ✗ JSON inválido em {url}: {e}")
            return None
    print(f"    ✗ Esgotadas {retries + 1} tentativas para {url}: {last_err}")
    return None


def _write_json_resilient(path: Path, payload: dict) -> bool:
    import re
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


def _slug(name: str) -> str:
    """Slug para matching fuzzy entre grafias."""
    import unicodedata
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    return "".join(c for c in n.lower() if c.isalnum())


# Índice slug → nome canônico (para fallback fuzzy)
_SLUG_INDEX = {_slug(k): k for k in WC2026_TEAMS}


def _resolve_team(fifa_name: str) -> dict | None:
    """FIFA name → {name, code, flag} canônico, ou None se não resolver."""
    canon = FIFA_NAME_FIX.get(fifa_name, fifa_name)
    if canon in WC2026_TEAMS:
        code, flag = WC2026_TEAMS[canon]
        return {"name": canon, "code": code, "flag": flag}
    # fallback fuzzy por slug
    canon2 = _SLUG_INDEX.get(_slug(canon))
    if canon2:
        code, flag = WC2026_TEAMS[canon2]
        return {"name": canon2, "code": code, "flag": flag}
    return None


def _locale_desc(arr: list[dict], key_locale: str = "locale",
                 key_desc: str = "description", prefer=("pt-BR", "en-GB")) -> str:
    """Extrai descrição de um array [{locale, description}] pela ordem de preferência."""
    if not isinstance(arr, list):
        return ""
    by_loc = {d.get(key_locale): d.get(key_desc) for d in arr if isinstance(d, dict)}
    for loc in prefer:
        if by_loc.get(loc):
            return by_loc[loc]
    # qualquer um
    for v in by_loc.values():
        if v:
            return v
    return ""


# ═══════════════════════════════════════════════════════════════════════
# PONTE DE NOMES — IdTeam → {name, code, flag}
# ═══════════════════════════════════════════════════════════════════════
def build_team_bridge() -> tuple[dict[str, dict], list[str]]:
    """
    Do calendar da FIFA: IdTeam(str) → nome oficial en-GB → resolve canônico.
    Retorna (bridge, unresolved_names).
    """
    data = _http_get_json(URL_BRIDGE)
    bridge: dict[str, dict] = {}
    unresolved: list[str] = []
    if not data or not isinstance(data, dict):
        print("    ✗ Bridge (calendar) indisponível.")
        return bridge, unresolved
    results = data.get("Results", []) or []
    seen_names: dict[str, str] = {}
    for m in results:
        for side in ("Home", "Away"):
            s = m.get(side)
            if not s:
                continue
            tid = s.get("IdTeam")
            if tid is None:
                continue
            tid = str(tid)
            fifa_name = _locale_desc(s.get("TeamName", []),
                                     key_locale="Locale", key_desc="Description",
                                     prefer=("en-GB",))
            if not fifa_name:
                continue
            seen_names[tid] = fifa_name
            if tid in bridge:
                continue
            resolved = _resolve_team(fifa_name)
            if resolved:
                bridge[tid] = resolved
            else:
                if fifa_name not in unresolved:
                    unresolved.append(fifa_name)
    print(f"    ✓ Bridge: {len(bridge)} IdTeam resolvidos "
          f"({len(seen_names)} vistos no calendar)")
    if unresolved:
        print(f"    ⚠ Nomes FIFA não resolvidos: {unresolved}")
    return bridge, unresolved


# ═══════════════════════════════════════════════════════════════════════
# MÉTRICAS CURADAS — 22 selecionadas das 141 do feed
# ═══════════════════════════════════════════════════════════════════════
# transform: raw → display value. per_match: emitir versão por-partida.
def _pct(v):  # fração → percentual
    return round(v * 100, 1)


def _km_total(v):  # metros → km
    return round(v / 1000, 1)


def _r1(v):
    return round(v, 1)


def _int(v):
    return int(round(v))


METRIC_CATALOG = [
    # key, label_pt, unit, higher_is_better, transform, per_match
    {"key": "Goals", "label_pt": "Gols", "unit": "", "higher_is_better": True,
     "transform": _int, "per_match": True},
    {"key": "XG", "label_pt": "Gols esperados (xG)", "unit": "xG", "higher_is_better": True,
     "transform": _r1, "per_match": True},
    {"key": "GoalsConceded", "label_pt": "Gols sofridos", "unit": "", "higher_is_better": False,
     "transform": _int, "per_match": True},
    {"key": "Assists", "label_pt": "Assistências", "unit": "", "higher_is_better": True,
     "transform": _int, "per_match": True},
    {"key": "Possession", "label_pt": "Posse de bola", "unit": "%", "higher_is_better": True,
     "transform": _pct, "per_match": False},
    {"key": "Passes", "label_pt": "Passes tentados", "unit": "", "higher_is_better": True,
     "transform": _int, "per_match": True},
    {"key": "PassesCompleted", "label_pt": "Passes certos", "unit": "", "higher_is_better": True,
     "transform": _int, "per_match": True},
    {"key": "AttemptAtGoal", "label_pt": "Finalizações", "unit": "", "higher_is_better": True,
     "transform": _int, "per_match": True},
    {"key": "AttemptAtGoalOnTarget", "label_pt": "Finalizações no alvo", "unit": "",
     "higher_is_better": True, "transform": _int, "per_match": True},
    {"key": "Threat", "label_pt": "Ameaça ofensiva (Threat)", "unit": "", "higher_is_better": True,
     "transform": _r1, "per_match": True},
    {"key": "PitchControl", "label_pt": "Controle de campo", "unit": "%", "higher_is_better": True,
     "transform": _r1, "per_match": False},
    {"key": "FinalThirdPitchControl", "label_pt": "Controle no terço final", "unit": "%",
     "higher_is_better": True, "transform": _r1, "per_match": False},
    {"key": "DefensivePressuresApplied", "label_pt": "Pressões defensivas", "unit": "",
     "higher_is_better": True, "transform": _int, "per_match": True},
    {"key": "TotalDistance", "label_pt": "Distância percorrida", "unit": "km",
     "higher_is_better": True, "transform": _km_total, "per_match": True},
    {"key": "TopSpeed", "label_pt": "Velocidade máxima", "unit": "km/h", "higher_is_better": True,
     "transform": _r1, "per_match": False},
    {"key": "Corners", "label_pt": "Escanteios", "unit": "", "higher_is_better": True,
     "transform": _int, "per_match": True},
    {"key": "Crosses", "label_pt": "Cruzamentos", "unit": "", "higher_is_better": True,
     "transform": _int, "per_match": True},
    {"key": "Offsides", "label_pt": "Impedimentos", "unit": "", "higher_is_better": False,
     "transform": _int, "per_match": True},
    {"key": "YellowCards", "label_pt": "Cartões amarelos", "unit": "", "higher_is_better": False,
     "transform": _int, "per_match": True},
    {"key": "RedCards", "label_pt": "Cartões vermelhos", "unit": "", "higher_is_better": False,
     "transform": _int, "per_match": False},
    {"key": "CleanSheets", "label_pt": "Jogos sem sofrer gol", "unit": "", "higher_is_better": True,
     "transform": _int, "per_match": False},
    {"key": "GoalkeeperSaves", "label_pt": "Defesas do goleiro", "unit": "", "higher_is_better": True,
     "transform": _int, "per_match": True},
]
# derivado (não é chave crua): precisão de passe = PassesCompleted / Passes.
DERIVED_PASS_PCT = {"key": "pass_pct", "label_pt": "Precisão de passe", "unit": "%",
                    "higher_is_better": True}


def _stats_map(tuples: list) -> dict:
    """[[name, value, isLive], ...] → {name: value}."""
    out = {}
    for row in tuples:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            out[row[0]] = row[1]
    return out


def build_team_stats(teams_raw: dict, bridge: dict) -> tuple[list[dict], list[str]]:
    """Curadoria das 48 seleções. Retorna (teams, unresolved_ids)."""
    teams: list[dict] = []
    unresolved: list[str] = []
    for tid, tuples in teams_raw.items():
        sm = _stats_map(tuples)
        meta = bridge.get(str(tid))
        if not meta:
            unresolved.append(str(tid))
            meta = {"name": "???", "code": "???", "flag": "🏳️"}
        matches = _int(sm.get("MatchesPlayed") or 0) or 0
        stats: dict = {}
        per_match: dict = {}
        for m in METRIC_CATALOG:
            raw = sm.get(m["key"])
            if raw is None:
                continue
            val = m["transform"](raw)
            stats[m["key"]] = val
            if m["per_match"] and matches > 0:
                # per-match sempre a partir do RAW (não do valor já transformado
                # em total), para distância virar km/jogo etc.
                pm_raw = raw / matches
                per_match[m["key"]] = m["transform"](pm_raw)
        # Precisão de passe derivada dos brutos
        passes = sm.get("Passes") or 0
        completed = sm.get("PassesCompleted") or 0
        if passes:
            stats["pass_pct"] = round(completed / passes * 100, 1)
        # ── INSIGHTS cross-métrica ────────────────────────────────────
        goals = sm.get("Goals") or 0
        xg = sm.get("XG") or 0
        shots = sm.get("AttemptAtGoal") or 0
        pressures = sm.get("DefensivePressuresApplied") or 0
        dist = sm.get("TotalDistance") or 0
        insights = {
            "xg_diff": round(goals - xg, 1),
            "shot_conversion": round(goals / shots * 100, 1) if shots else 0.0,
            "pressure_per_match": round(pressures / matches, 1) if matches else 0.0,
            "distance_km_per_match": round(dist / 1000 / matches, 1) if matches else 0.0,
        }
        teams.append({
            "id": str(tid),
            "name": meta["name"],
            "code": meta["code"],
            "flag": meta["flag"],
            "matches": matches,
            "stats": stats,
            "per_match": per_match,
            "insights": insights,
        })
    # ordena por XG desc (fallback Goals)
    teams.sort(key=lambda t: (t["stats"].get("XG", 0), t["stats"].get("Goals", 0)),
               reverse=True)
    return teams, unresolved


# ═══════════════════════════════════════════════════════════════════════
# POWER RANKING
# ═══════════════════════════════════════════════════════════════════════
def build_power_ranking(power_raw: dict, bridge: dict) -> tuple[dict, list[str]]:
    """Ranking oficial FIFA. Retorna ({outfield, goalkeepers, n_matches}, warns)."""
    warns: list[str] = []

    def resolve_flag(item: dict) -> dict:
        tid = str(item.get("teamId"))
        meta = bridge.get(tid)
        if not meta:
            # fallback via teamName (en-GB / pt-BR)
            fifa_name = _locale_desc(item.get("teamName", []), prefer=("en-GB", "pt-BR"))
            meta = _resolve_team(fifa_name) or {"name": "???", "code": "???", "flag": "🏳️"}
            if meta["code"] == "???" and fifa_name not in warns:
                warns.append(fifa_name or f"teamId={tid}")
        return meta

    outfield = []
    for p in power_raw.get("outfieldPlayers", []) or []:
        meta = resolve_flag(p)
        outfield.append({
            "player": _locale_desc(p.get("playerName", [])),
            "team": _locale_desc(p.get("teamName", [])),
            "team_canonical": meta["name"],
            "code": meta["code"],
            "flag": meta["flag"],
            "picture": (p.get("playerPicture") or {}).get("pictureUrl"),
            "attacking_rank": p.get("attackingRank"),
            "attacking_score": p.get("attackingScore"),
            "defensive_rank": p.get("defensiveRank"),
            "defensive_score": p.get("defensiveScore"),
            "creativity_rank": p.get("creativityRank"),
            "creativity_score": p.get("creativityScore"),
            "attacking_change": p.get("attackingRankChange"),
            "defensive_change": p.get("defensiveRankChange"),
            "creativity_change": p.get("creativityRankChange"),
        })
    goalkeepers = []
    for p in power_raw.get("goalkeepers", []) or []:
        meta = resolve_flag(p)
        goalkeepers.append({
            "player": _locale_desc(p.get("playerName", [])),
            "team": _locale_desc(p.get("teamName", [])),
            "team_canonical": meta["name"],
            "code": meta["code"],
            "flag": meta["flag"],
            "picture": (p.get("playerPicture") or {}).get("pictureUrl"),
            "in_possession_rank": p.get("inPossessionRank"),
            "in_possession_score": p.get("inPossessionScore"),
            "defending_rank": p.get("defendingTheGoalRank"),
            "defending_score": p.get("defendingTheGoalScore"),
            "in_possession_change": p.get("inPossessionRankChange"),
            "defending_change": p.get("defendingTheGoalRankChange"),
        })
    # ordena por rank de ataque / defesa do goleiro
    outfield.sort(key=lambda x: (x["attacking_rank"] is None, x["attacking_rank"] or 1e9))
    goalkeepers.sort(key=lambda x: (x["defending_rank"] is None, x["defending_rank"] or 1e9))
    return {
        "n_matches": power_raw.get("nMatches"),
        "outfield": outfield,
        "goalkeepers": goalkeepers,
    }, warns


# ═══════════════════════════════════════════════════════════════════════
# PLAYER STATS — top-N por família (nomes via join com power ranking)
# ═══════════════════════════════════════════════════════════════════════
PLAYER_FAMILIES = [
    {"family": "finishing", "label_pt": "Finalização", "sort_key": "Goals",
     "extra": ["XG", "AttemptAtGoal", "AttemptAtGoalOnTarget"]},
    {"family": "creation", "label_pt": "Criação", "sort_key": "Threat",
     "extra": ["Assists", "Passes", "PassesCompleted"]},
    {"family": "defense", "label_pt": "Defesa/pressão", "sort_key": "DefensivePressuresApplied",
     "extra": ["ForcedTurnovers", "TakeOnsCompleted"]},
    {"family": "physical", "label_pt": "Físico", "sort_key": "TotalDistance",
     "extra": ["TopSpeed", "Sprints", "SpeedRuns"]},
]
PLAYER_TOP_N = 25
# distância exibida em km
_PLAYER_KM_KEYS = {"TotalDistance"}


def build_player_stats(players_raw: dict, power_names: dict) -> tuple[dict, dict]:
    """
    Top-N por família. Nomes/time vêm do join playerId↔power_names.
    Só entram jogadores com nome resolvido. Retorna (payload_families, coverage).
    """
    # pré-computa stats-map por jogador
    parsed = {pid: _stats_map(tuples) for pid, tuples in players_raw.items()}
    resolvable = sum(1 for pid in parsed if pid in power_names)
    coverage = {
        "players_total": len(parsed),
        "players_named": resolvable,
        "names_source": "powerranking (playerId join)",
    }

    families_out = {}
    for fam in PLAYER_FAMILIES:
        sk = fam["sort_key"]
        rows = []
        for pid, sm in parsed.items():
            name_meta = power_names.get(pid)
            if not name_meta:
                continue  # sem nome → não exibe
            val = sm.get(sk)
            if val is None:
                continue
            entry = {
                "player": name_meta["player"],
                "team": name_meta["team_canonical"],
                "code": name_meta["code"],
                "flag": name_meta["flag"],
                "matches": _int(sm.get("MatchesPlayed") or 0),
                sk: round(val / 1000, 1) if sk in _PLAYER_KM_KEYS else _r1(val),
            }
            for ek in fam["extra"]:
                ev = sm.get(ek)
                if ev is not None:
                    entry[ek] = round(ev / 1000, 1) if ek in _PLAYER_KM_KEYS else _r1(ev)
            rows.append(entry)
        rows.sort(key=lambda r: r.get(sk, 0), reverse=True)
        families_out[fam["family"]] = {
            "label_pt": fam["label_pt"],
            "sort_key": sk,
            "stats": [sk] + fam["extra"],
            "players": rows[:PLAYER_TOP_N],
        }
    return families_out, coverage


# ─── Orquestração ─────────────────────────────────────────────────────
def main() -> int:
    print("═" * 64)
    print("FIFA Official Data Snapshot — World Cup 2026 (fdh-api.fifa.com)")
    print("═" * 64)
    now_iso = datetime.now(timezone.utc).isoformat()

    print("\n[1/5] Ponte de nomes (calendar)…")
    bridge, bridge_unresolved = build_team_bridge()

    print("\n[2/5] Baixando team stats…")
    teams_raw = _http_get_json(URL_TEAMS)
    if not teams_raw or not isinstance(teams_raw, dict):
        print("    ✗ teams.json indisponível — abortando.")
        return 1
    print(f"    ✓ {len(teams_raw)} seleções no feed")
    teams, team_unresolved = build_team_stats(teams_raw, bridge)

    print("\n[3/5] Baixando power ranking…")
    power_raw = _http_get_json(URL_POWER)
    power = {"n_matches": None, "outfield": [], "goalkeepers": []}
    power_warns: list[str] = []
    if power_raw and isinstance(power_raw, dict):
        power, power_warns = build_power_ranking(power_raw, bridge)
        print(f"    ✓ outfield={len(power['outfield'])} "
              f"goalkeepers={len(power['goalkeepers'])} nMatches={power['n_matches']}")
    else:
        print("    ⚠ powerranking indisponível — arquivo sairá vazio.")

    # join playerId → nome/time (do power ranking)
    power_names: dict[str, dict] = {}
    for src in (power_raw.get("outfieldPlayers", []) if power_raw else [],
                power_raw.get("goalkeepers", []) if power_raw else []):
        for p in src or []:
            pid = str(p.get("playerId"))
            tid = str(p.get("teamId"))
            meta = bridge.get(tid) or _resolve_team(
                _locale_desc(p.get("teamName", []), prefer=("en-GB", "pt-BR"))
            ) or {"name": "???", "code": "???", "flag": "🏳️"}
            power_names[pid] = {
                "player": _locale_desc(p.get("playerName", [])),
                "team_canonical": meta["name"],
                "code": meta["code"],
                "flag": meta["flag"],
            }

    print("\n[4/5] Baixando player stats (5 MB)…")
    players_raw = _http_get_json(URL_PLAYERS, timeout=60)
    player_families: dict = {}
    player_coverage: dict = {}
    if players_raw and isinstance(players_raw, dict):
        print(f"    ✓ {len(players_raw)} jogadores no feed")
        player_families, player_coverage = build_player_stats(players_raw, power_names)
        print(f"    ✓ nomes resolvidos p/ {player_coverage['players_named']}"
              f"/{player_coverage['players_total']} jogadores")
    else:
        print("    ⚠ players.json indisponível — arquivo sairá vazio.")

    # ── Escreve os 3 JSONs ────────────────────────────────────────────
    print("\n[5/5] Escrevendo JSONs…")
    catalog_public = [
        {"key": m["key"], "label_pt": m["label_pt"], "unit": m["unit"],
         "higher_is_better": m["higher_is_better"], "per_match": m["per_match"]}
        for m in METRIC_CATALOG
    ] + [dict(DERIVED_PASS_PCT, per_match=False, derived=True)]

    team_payload = {
        "updated_at": now_iso,
        "source": SOURCE,
        "note": (
            "Estatística agregada oficial da FIFA (Enhanced Football Intelligence): "
            "xG, Threat, controle de campo, distância por GPS, velocidade máxima. "
            "Valores exibidos já normalizados (posse em %, distância em km, "
            "precisão de passe derivada de passes certos ÷ tentados). "
            "'per_match' = total ÷ jogos disputados."
        ),
        "season_id": SEASON_ID,
        "metrics_catalog": catalog_public,
        "teams": teams,
    }
    power_payload = {
        "updated_at": now_iso,
        "source": SOURCE,
        "note": (
            "FIFA Power Rankings oficiais: rank de ataque, defesa e criatividade "
            "(jogadores de linha) + em-posse e defesa do gol (goleiros). "
            "Change = variação de rank desde a rodada anterior. Nomes em pt-BR."
        ),
        "n_matches": power["n_matches"],
        "outfield": power["outfield"],
        "goalkeepers": power["goalkeepers"],
    }
    player_payload = {
        "updated_at": now_iso,
        "source": SOURCE,
        "note": (
            "Top-25 por família (finalização/criação/defesa/físico) das stats "
            "oficiais da FIFA por jogador. LIMITAÇÃO: players.json não traz "
            "nome/seleção; nomes resolvidos via join com o Power Ranking → só "
            f"~{player_coverage.get('players_named', 0)} dos "
            f"{player_coverage.get('players_total', 0)} jogadores têm nome (o "
            "resto fica de fora). Distância em km."
        ),
        "coverage": player_coverage,
        "families": player_families,
    }

    _write_json_resilient(OUTPUT_DIR / "fifa_team_stats.json", team_payload)
    _write_json_resilient(OUTPUT_DIR / "fifa_power_ranking.json", power_payload)
    _write_json_resilient(OUTPUT_DIR / "fifa_player_stats.json", player_payload)

    # ── Validação / sanity ────────────────────────────────────────────
    print("\n" + "─" * 64)
    print("VALIDAÇÃO")
    print("─" * 64)
    print(f"  Times: {len(teams)} (esperado 48)")
    unresolved_teams = [t for t in teams if t["code"] == "???"]
    if unresolved_teams:
        print(f"  ⚠ Times NÃO resolvidos: "
              f"{[(t['id']) for t in unresolved_teams]}")
    else:
        print("  ✓ Todos os times resolvidos com nome+bandeira reais.")
    if bridge_unresolved:
        print(f"  ⚠ Nomes FIFA sem mapeamento no bridge: {bridge_unresolved}")
    if power_warns:
        print(f"  ⚠ Power ranking — times sem flag: {sorted(set(power_warns))}")

    # sanity numbers — top 5 por XG
    print("\n  Top 5 por XG:")
    for t in teams[:5]:
        s = t["stats"]
        print(f"    {t['flag']} {t['name']:<22} XG={s.get('XG')}  "
              f"Gols={s.get('Goals')}  Threat={s.get('Threat')}  "
              f"Posse={s.get('Possession')}%  pass%={s.get('pass_pct')}  "
              f"xg_diff={t['insights']['xg_diff']}")
    poss = [t["stats"].get("Possession") for t in teams if t["stats"].get("Possession")]
    tops = [t["stats"].get("TopSpeed") for t in teams if t["stats"].get("TopSpeed")]
    dpm = [t["insights"]["distance_km_per_match"] for t in teams
           if t["insights"]["distance_km_per_match"]]
    if poss:
        print(f"\n  Posse: min={min(poss)}% max={max(poss)}% (esperado ~40–65%)")
    if tops:
        print(f"  TopSpeed: min={min(tops)} max={max(tops)} km/h (esperado ~30–36)")
    if dpm:
        print(f"  Distância/jogo: min={min(dpm)} max={max(dpm)} km (esperado ~90–120)")

    # JSON parse check
    print("\n  Parse check:")
    ok = True
    for fn in ("fifa_team_stats.json", "fifa_power_ranking.json", "fifa_player_stats.json"):
        p = OUTPUT_DIR / fn
        try:
            json.loads(p.read_text(encoding="utf-8"))
            print(f"    ✓ {fn} — JSON válido")
        except Exception as e:
            ok = False
            print(f"    ✗ {fn} — INVÁLIDO: {e}")

    print(f"\n✅ Concluído. Power outfield={len(power['outfield'])}, "
          f"players nomeados={player_coverage.get('players_named', 0)}.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
