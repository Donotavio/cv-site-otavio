"""
World Cup Dashboard — Clássicos 2022 (StatsBomb Open Data · Custo Zero)
======================================================================
Reproduz FIELMENTE a análise avançada por partida da Copa de 2022:
posse de bola %, precisão de passe % e PPDA (intensidade de pressão),
com recorte por intervalo de 15 min + Total / 1º tempo / 2º tempo — o
mesmo enquadramento das transmissões, mas com número REAL derivado do
dado de EVENTO (lance a lance) aberto do StatsBomb.

Por que 2022 e não 2026: dado de evento aberto só existe de graça para
Copas passadas (StatsBomb open: 2018/2022). A Copa 2026 ao vivo só tem
totais de jogo (ESPN) — sem intervalo, sem PPDA. Nada é fabricado.

FONTE — StatsBomb Open Data (CC BY-NC-SA), 100% real, sem auth:
    github.com/statsbomb/open-data → competition_id=43, season_id=106

Metodologia (documentada também no painel):
  • Posse %  — base temporal: soma do tempo entre eventos atribuído ao
    time em posse (possession_team), por intervalo. Clamp de 30 s p/
    ignorar paradas longas.
  • Precisão de passe % — passes completos ÷ passes tentados (StatsBomb
    marca `pass.outcome` só quando o passe NÃO é completo).
  • PPDA — passes do adversário ÷ ações defensivas (desarmes +
    interceptações + faltas) do time que pressiona, ambos na zona de
    60% do campo longe do gol de quem pressiona (definição padrão
    Trainor/StatsBomb). Direção de ataque de cada time inferida das
    coordenadas dos chutes (frame fixo do StatsBomb).

    classics_2022.json ← agregados compactos por partida (sem LLM,
    sem runtime — o painel só faz fetch do JSON pronto).

No mesmo passe pelos 64 arquivos de evento (sem re-download), extrai
também o PANORAMA do torneio inteiro a partir do xG por chute
(shot.statsbomb_xg) e dos eventos de gol:
  • Ranking de xG por seleção (xG a favor/contra, over/underperformance
    = gols − xG), + posse/precisão/PPDA médios do torneio.
  • Finalizadores clínicos vs. perdulários (gols − xG por jogador).
  • Artilharia derivada de eventos de gol + distribuição de gols/minuto.
Chutes de disputa de pênaltis (period 5) são EXCLUÍDOS dos agregados de
xG/gol (não são xG de jogo). → copa2022_panorama.json.

Uso (one-off — dado 2022 é estático; NÃO entra no cron diário):
    python ingestion_worldcup/fetch_classics_statsbomb.py
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

# ─── Fonte ────────────────────────────────────────────────────────────
SB_RAW = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
COMP_ID, SEASON_ID = 43, 106                 # FIFA World Cup 2022
MATCHES_URL = f"{SB_RAW}/matches/{COMP_ID}/{SEASON_ID}.json"
EVENTS_URL = f"{SB_RAW}/events/{{match_id}}.json"

# ─── Configuração ─────────────────────────────────────────────────────
OUTPUT = Path("assets/data/worldcup/classics_2022.json")
OUTPUT_PANORAMA = Path("assets/data/worldcup/copa2022_panorama.json")
FINISHING_MIN_SHOTS = 5   # mín. de chutes p/ entrar no ranking de finalização
HTTP_TIMEOUT = 45
FETCH_DELAY = 0.15
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 1.6
USER_AGENT = "worldcup-dashboard/1.0 (+https://github.com/Donotavio/cv-site-otavio)"

PITCH_LEN = 120.0
PPDA_ZONE = 0.60          # 60% do campo longe do gol de quem pressiona
POSS_DT_CLAMP = 30.0      # segundos — teto por gap entre eventos

# Rótulos dos intervalos de 15 min (inclui prorrogação quando houver).
BUCKET_LABELS = ["1-15", "16-30", "31-45+", "46-60", "61-75", "76-90+",
                 "91-105", "106-120+"]

# 32 seleções da Copa 2022 → (código, bandeira). Nomes conforme StatsBomb.
TEAM_META: dict[str, tuple[str, str]] = {
    "Argentina": ("ARG", "🇦🇷"), "Australia": ("AUS", "🇦🇺"),
    "Belgium": ("BEL", "🇧🇪"), "Brazil": ("BRA", "🇧🇷"),
    "Cameroon": ("CMR", "🇨🇲"), "Canada": ("CAN", "🇨🇦"),
    "Costa Rica": ("CRC", "🇨🇷"), "Croatia": ("CRO", "🇭🇷"),
    "Denmark": ("DEN", "🇩🇰"), "Ecuador": ("ECU", "🇪🇨"),
    "England": ("ENG", "🏴󠁧󠁢󠁥󠁮󠁧󠁿"), "France": ("FRA", "🇫🇷"),
    "Germany": ("GER", "🇩🇪"), "Ghana": ("GHA", "🇬🇭"),
    "Iran": ("IRN", "🇮🇷"), "Japan": ("JPN", "🇯🇵"),
    "Mexico": ("MEX", "🇲🇽"), "Morocco": ("MAR", "🇲🇦"),
    "Netherlands": ("NED", "🇳🇱"), "Poland": ("POL", "🇵🇱"),
    "Portugal": ("POR", "🇵🇹"), "Qatar": ("QAT", "🇶🇦"),
    "Saudi Arabia": ("KSA", "🇸🇦"), "Senegal": ("SEN", "🇸🇳"),
    "Serbia": ("SRB", "🇷🇸"), "South Korea": ("KOR", "🇰🇷"),
    "Spain": ("ESP", "🇪🇸"), "Switzerland": ("SUI", "🇨🇭"),
    "Tunisia": ("TUN", "🇹🇳"), "United States": ("USA", "🇺🇸"),
    "Uruguay": ("URU", "🇺🇾"), "Wales": ("WAL", "🏴󠁧󠁢󠁷󠁬󠁳󠁿"),
}

# Ordem de destaque por fase (Final primeiro).
STAGE_RANK = {
    "Final": 0, "3rd Place Final": 1, "Semi-finals": 2,
    "Quarter-finals": 3, "Round of 16": 4, "Group Stage": 5,
}


# ─── HTTP helpers ─────────────────────────────────────────────────────
def _http_get_json(url: str, retries: int = RETRY_ATTEMPTS):
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT,
                                        "Accept": "application/json,*/*"})
            with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (URLError, HTTPError, TimeoutError, OSError, ValueError) as e:
            last_err = e
            code = getattr(e, "code", None)
            if code is not None and code != 429 and 400 <= code < 500:
                print(f"    ✗ {code} definitivo em {url}: {e}")
                return None
            if attempt < retries:
                wait = RETRY_BACKOFF ** (attempt + 1)
                print(f"    ↻ retry {attempt + 1}/{retries} em {wait:.1f}s… ({e})")
                time.sleep(wait)
    print(f"    ✗ Falha em {url}: {last_err}")
    return None


def _team_meta(name: str) -> tuple[str, str]:
    return TEAM_META.get(name, ("???", "🏳️"))


# ─── Cálculo por partida ──────────────────────────────────────────────
def _bucket_index(period: int, minute: int) -> int | None:
    """Índice do intervalo de 15 min (0-7). period 5 (pênaltis) → None."""
    if period == 1:
        return min(minute // 15, 2)                       # 0,1,2
    if period == 2:
        return 3 + min(max(minute - 45, 0) // 15, 2)       # 3,4,5
    if period == 3:
        return 6
    if period == 4:
        return 7
    return None


def _secs(ev: dict) -> float:
    return (ev.get("minute", 0) or 0) * 60 + (ev.get("second", 0) or 0)


def _attack_directions(events: list[dict], teams: list[str]) -> dict[str, bool]:
    """
    Infere, por time, se ataca para x=120 (True) via média do x dos chutes
    (StatsBomb usa frame fixo; cada time ataca um lado a partida inteira).
    Fallback: oposto do outro time; por fim, primeiro time → direita.
    """
    sx: dict[str, list[float]] = {t: [] for t in teams}
    for ev in events:
        if ev.get("type", {}).get("name") == "Shot":
            t = ev.get("team", {}).get("name")
            loc = ev.get("location")
            if t in sx and isinstance(loc, list) and len(loc) >= 1:
                sx[t].append(float(loc[0]))
    dirs: dict[str, bool] = {}
    for t in teams:
        if sx[t]:
            dirs[t] = (sum(sx[t]) / len(sx[t])) > (PITCH_LEN / 2)
    # Fallbacks
    for i, t in enumerate(teams):
        if t not in dirs:
            other = teams[1 - i] if len(teams) == 2 else None
            if other in dirs:
                dirs[t] = not dirs[other]
            else:
                dirs[t] = (i == 0)
    return dirs


def _att_x(x: float, attack_right: bool) -> float:
    """Distância do próprio gol rumo ao gol atacado (0..120)."""
    return x if attack_right else (PITCH_LEN - x)


def _blank_series(n: int) -> list[float]:
    return [0.0] * n


def compute_match(events: list[dict], home: str, away: str) -> dict | None:
    teams = [home, away]
    if not events:
        return None
    dirs = _attack_directions(events, teams)

    # Descobre o maior bucket usado → nº de intervalos a emitir.
    max_bucket = -1
    for ev in events:
        b = _bucket_index(ev.get("period", 0), ev.get("minute", 0) or 0)
        if b is not None:
            max_bucket = max(max_bucket, b)
    if max_bucket < 0:
        return None
    n = max_bucket + 1

    # Acumuladores por time.
    poss_sec = {t: _blank_series(n) for t in teams}      # posse (s) por bucket
    poss_half = {t: [0.0, 0.0] for t in teams}           # [1º, 2º] tempo
    pass_ok = {t: _blank_series(n) for t in teams}
    pass_tot = {t: _blank_series(n) for t in teams}
    pass_ok_half = {t: [0.0, 0.0] for t in teams}
    pass_tot_half = {t: [0.0, 0.0] for t in teams}
    ppda_passes = {t: _blank_series(n) for t in teams}   # passes do adversário
    ppda_actions = {t: _blank_series(n) for t in teams}  # ações defensivas
    ppda_passes_half = {t: [0.0, 0.0] for t in teams}
    ppda_actions_half = {t: [0.0, 0.0] for t in teams}

    def half_idx(period: int) -> int | None:
        if period == 1:
            return 0
        if period == 2:
            return 1
        return None  # prorrogação não entra nas colunas 1º/2º (só no Total)

    # Ordena por (period, index) — StatsBomb já vem em ordem, mas garante.
    evs = sorted(events, key=lambda e: (e.get("period", 0), e.get("index", 0)))

    for i, ev in enumerate(evs):
        period = ev.get("period", 0)
        minute = ev.get("minute", 0) or 0
        b = _bucket_index(period, minute)
        if b is None:
            continue
        h = half_idx(period)
        tname = ev.get("type", {}).get("name", "")

        # ── Posse (tempo entre eventos atribuído ao time em posse) ──
        pt = ev.get("possession_team", {}).get("name")
        if pt in poss_sec and i + 1 < len(evs):
            nxt = evs[i + 1]
            if nxt.get("period", 0) == period:
                dt = _secs(nxt) - _secs(ev)
                if 0 < dt <= POSS_DT_CLAMP:
                    poss_sec[pt][b] += dt
                    if h is not None:
                        poss_half[pt][h] += dt

        team = ev.get("team", {}).get("name")

        # ── Precisão de passe ──
        if tname == "Pass" and team in pass_tot:
            pass_tot[team][b] += 1
            if h is not None:
                pass_tot_half[team][h] += 1
            completed = "outcome" not in ev.get("pass", {})
            if completed:
                pass_ok[team][b] += 1
                if h is not None:
                    pass_ok_half[team][h] += 1

        # ── PPDA — passes do adversário na zona de pressão ──
        # Passe do time P conta para o PPDA de D (=oponente) se estiver
        # nos 60% do campo a partir do gol de P (att_x_P <= 72).
        if tname == "Pass" and team in teams:
            loc = ev.get("location")
            if isinstance(loc, list) and len(loc) >= 1:
                ax = _att_x(float(loc[0]), dirs[team])
                if ax <= PPDA_ZONE * PITCH_LEN:
                    presser = teams[1 - teams.index(team)]
                    ppda_passes[presser][b] += 1
                    if h is not None:
                        ppda_passes_half[presser][h] += 1

        # ── PPDA — ações defensivas de quem pressiona ──
        is_tackle = (tname == "Duel"
                     and ev.get("duel", {}).get("type", {}).get("name") == "Tackle")
        if (tname in ("Interception", "Foul Committed") or is_tackle) and team in teams:
            loc = ev.get("location")
            if isinstance(loc, list) and len(loc) >= 1:
                ax = _att_x(float(loc[0]), dirs[team])
                # Ação na faixa longe do próprio gol (att_x >= 48) = mesma
                # faixa física dos 60% do adversário.
                if ax >= (1 - PPDA_ZONE) * PITCH_LEN:
                    ppda_actions[team][b] += 1
                    if h is not None:
                        ppda_actions_half[team][h] += 1

    # ── Consolida em séries + agregados (Total / 1º / 2º) ──
    def poss_pct_series() -> dict:
        hs = [round(poss_sec[home][k] /
              (poss_sec[home][k] + poss_sec[away][k]) * 100, 1)
              if (poss_sec[home][k] + poss_sec[away][k]) > 0 else None
              for k in range(n)]
        as_ = [round(100 - v, 1) if v is not None else None for v in hs]
        return {"home": hs, "away": as_}

    def half_total_poss(team: str, which) -> float | None:
        if which == "total":
            th = sum(poss_sec[home]); ta = sum(poss_sec[away])
            mine = sum(poss_sec[team])
        else:
            hi = 0 if which == "first" else 1
            th = poss_half[home][hi]; ta = poss_half[away][hi]
            mine = poss_half[team][hi]
        tot = th + ta
        return round(mine / tot * 100, 1) if tot > 0 else None

    def pass_pct_series() -> dict:
        def s(team):
            return [round(pass_ok[team][k] / pass_tot[team][k] * 100, 1)
                    if pass_tot[team][k] > 0 else None for k in range(n)]
        return {"home": s(home), "away": s(away)}

    def pass_pct_agg(team: str, which) -> float | None:
        if which == "total":
            ok = sum(pass_ok[team]); tt = sum(pass_tot[team])
        else:
            hi = 0 if which == "first" else 1
            ok = pass_ok_half[team][hi]; tt = pass_tot_half[team][hi]
        return round(ok / tt * 100, 1) if tt > 0 else None

    def ppda_series() -> dict:
        def s(team):
            return [round(ppda_passes[team][k] / ppda_actions[team][k], 1)
                    if ppda_actions[team][k] > 0 else None for k in range(n)]
        return {"home": s(home), "away": s(away)}

    def ppda_agg(team: str, which) -> float | None:
        if which == "total":
            p = sum(ppda_passes[team]); a = sum(ppda_actions[team])
        else:
            hi = 0 if which == "first" else 1
            p = ppda_passes_half[team][hi]; a = ppda_actions_half[team][hi]
        return round(p / a, 1) if a > 0 else None

    def agg_block(series, agg_fn) -> dict:
        return {
            "labels": BUCKET_LABELS[:n],
            "series": series,
            "total": {"home": agg_fn(home, "total"), "away": agg_fn(away, "total")},
            "first": {"home": agg_fn(home, "first"), "away": agg_fn(away, "first")},
            "second": {"home": agg_fn(home, "second"), "away": agg_fn(away, "second")},
        }

    return {
        "labels": BUCKET_LABELS[:n],
        "possession": agg_block(poss_pct_series(), half_total_poss),
        "pass_accuracy": agg_block(pass_pct_series(), pass_pct_agg),
        "ppda": agg_block(ppda_series(), ppda_agg),
    }


# ─── Panorama do torneio (xG · finalização · artilharia) ──────────────
def _minute_bucket(minute: int) -> str:
    """Bucket de 15 min no formato de estatisticas.json (0-14, 15-29, …)."""
    idx = (max(0, min(120, int(minute))) // 15) * 15
    return f"{idx}-{idx+14}"


# Chutes que chegaram ao gol (StatsBomb shot outcomes).
SHOT_ON_TARGET = {"Goal", "Saved", "Saved To Post"}
# Desfechos de duelo considerados vitória.
DUEL_WON = {"Won", "Success", "Success In Play", "Success Out"}
PROG_CARRY_MIN = 5.0      # avanço mínimo (m rumo ao gol) p/ condução progressiva


def _blank_team_stat() -> dict:
    return {
        "xg": 0.0, "shots": 0, "shots_on": 0, "goals": 0, "og_for": 0,
        "passes": 0, "passes_cmp": 0, "corners": 0, "fouls": 0,
        "pressures": 0, "duels": 0, "duels_won": 0, "tackles": 0,
        "interceptions": 0, "carries": 0, "prog_carries": 0,
    }


def compute_shots(events: list[dict], home: str, away: str) -> dict:
    """
    Extrai xG, finalização e VOLUME DE JOGO de uma partida a partir dos
    eventos StatsBomb (passes, chutes no alvo, escanteios, faltas, pressões,
    duelos, desarmes, interceptações, conduções). Exclui a disputa de
    pênaltis (period 5) — não é volume de jogo.
    """
    teams = [home, away]
    stat = {t: _blank_team_stat() for t in teams}
    players: dict[str, dict] = {}
    goal_minutes: list[int] = []
    dirs = _attack_directions(events, teams)

    for ev in events:
        if ev.get("period", 0) == 5:           # shootout — fora dos agregados
            continue
        tname = ev.get("type", {}).get("name", "")
        team = ev.get("team", {}).get("name")
        if team not in stat:
            continue
        st = stat[team]

        if tname == "Shot":
            sh = ev.get("shot", {})
            try:
                xg = float(sh.get("statsbomb_xg") or 0.0)
            except (TypeError, ValueError):
                xg = 0.0
            outcome = sh.get("outcome", {}).get("name", "")
            is_goal = outcome == "Goal"
            is_pen = sh.get("type", {}).get("name") == "Penalty"
            st["xg"] += xg
            st["shots"] += 1
            if outcome in SHOT_ON_TARGET:
                st["shots_on"] += 1
            pname = ev.get("player", {}).get("name")
            if pname:
                p = players.setdefault(pname, {
                    "name": pname, "team": team,
                    "goals": 0, "xg": 0.0, "shots": 0,
                    "shots_on": 0, "penalties": 0,
                })
                p["shots"] += 1
                p["xg"] += xg
                if outcome in SHOT_ON_TARGET:
                    p["shots_on"] += 1
                if is_goal:
                    p["goals"] += 1
                    if is_pen:
                        p["penalties"] += 1
            if is_goal:
                st["goals"] += 1
                goal_minutes.append(ev.get("minute", 0) or 0)

        elif tname == "Own Goal For":
            st["og_for"] += 1
            goal_minutes.append(ev.get("minute", 0) or 0)

        elif tname == "Pass":
            pa = ev.get("pass", {})
            st["passes"] += 1
            if "outcome" not in pa:          # StatsBomb só marca o incompleto
                st["passes_cmp"] += 1
            if pa.get("type", {}).get("name") == "Corner":
                st["corners"] += 1

        elif tname == "Foul Committed":
            st["fouls"] += 1
        elif tname == "Pressure":
            st["pressures"] += 1
        elif tname == "Interception":
            st["interceptions"] += 1
        elif tname == "Duel":
            st["duels"] += 1
            if ev.get("duel", {}).get("type", {}).get("name") == "Tackle":
                st["tackles"] += 1
            if ev.get("duel", {}).get("outcome", {}).get("name") in DUEL_WON:
                st["duels_won"] += 1
        elif tname == "Carry":
            st["carries"] += 1
            loc = ev.get("location")
            end = ev.get("carry", {}).get("end_location")
            if (isinstance(loc, list) and len(loc) >= 1
                    and isinstance(end, list) and len(end) >= 1):
                adv = _att_x(float(end[0]), dirs[team]) - _att_x(float(loc[0]), dirs[team])
                if adv >= PROG_CARRY_MIN:
                    st["prog_carries"] += 1

    return {"stat": stat, "players": players, "goal_minutes": goal_minutes}


class PanoramaAccumulator:
    """Acumula xG/finalização/artilharia do torneio inteiro (2022)."""

    def __init__(self) -> None:
        self.teams: dict[str, dict] = {}
        self.players: dict[str, dict] = {}
        self.minute_buckets: dict[str, int] = {
            f"{lo}-{lo+14}": 0 for lo in range(0, 121, 15)
        }
        self.matches = 0

    # Campos de volume somados diretamente do stat por partida.
    VOLUME_KEYS = ("shots", "shots_on", "passes", "passes_cmp", "corners",
                   "fouls", "pressures", "duels", "duels_won", "tackles",
                   "interceptions", "carries", "prog_carries")

    def _team(self, name: str) -> dict:
        if name not in self.teams:
            code, flag = _team_meta(name)
            t = {
                "name": name, "code": code, "flag": flag,
                "xg_for": 0.0, "xg_against": 0.0,
                "goals_for": 0, "goals_against": 0, "matches": 0,
                "poss_sum": 0.0, "poss_n": 0, "ppda_sum": 0.0, "ppda_n": 0,
            }
            for k in self.VOLUME_KEYS:
                t[k] = 0
            self.teams[name] = t
        return self.teams[name]

    def add_match(self, sd: dict, stats: dict, home: str, away: str) -> None:
        self.matches += 1
        st = sd["stat"]
        goals = {t: st[t]["goals"] + st[t]["og_for"] for t in (home, away)}
        for me, opp in ((home, away), (away, home)):
            t = self._team(me)
            t["xg_for"] += st[me]["xg"]
            t["xg_against"] += st[opp]["xg"]
            t["goals_for"] += goals[me]
            t["goals_against"] += goals[opp]
            t["matches"] += 1
            for k in self.VOLUME_KEYS:
                t[k] += st[me][k]

        # posse (base temporal) e PPDA vêm dos totais de compute_match.
        for block, field, side, key in (
            ("possession", "poss", "home", home), ("possession", "poss", "away", away),
            ("ppda", "ppda", "home", home), ("ppda", "ppda", "away", away),
        ):
            v = (stats.get(block, {}).get("total", {}) or {}).get(side)
            if v is not None:
                t = self._team(key)
                t[f"{field}_sum"] += v
                t[f"{field}_n"] += 1

        for pname, pd in sd["players"].items():
            pp = self.players.setdefault(pname, {
                "name": pname, "team": pd["team"],
                "goals": 0, "xg": 0.0, "shots": 0, "shots_on": 0, "penalties": 0,
            })
            pp["goals"] += pd["goals"]
            pp["xg"] += pd["xg"]
            pp["shots"] += pd["shots"]
            pp["shots_on"] += pd.get("shots_on", 0)
            pp["penalties"] += pd["penalties"]

        for minute in sd["goal_minutes"]:
            self.minute_buckets[_minute_bucket(minute)] += 1

    def build(self) -> dict:
        def avg(s, n):
            return round(s / n, 1) if n else None

        def pct(a, b):
            return round(a / b * 100, 1) if b else None

        def per_match(v, n):
            return round(v / n, 1) if n else None

        team_xg = []
        for t in self.teams.values():
            n = t["matches"]
            if n == 0:
                continue
            team_xg.append({
                "name": t["name"], "code": t["code"], "flag": t["flag"],
                "matches": n,
                "goals_for": t["goals_for"], "goals_against": t["goals_against"],
                "xg_for": round(t["xg_for"], 2), "xg_against": round(t["xg_against"], 2),
                "xg_diff": round(t["goals_for"] - t["xg_for"], 2),
                "xg_per_match": round(t["xg_for"] / n, 2),
                "possession_avg": avg(t["poss_sum"], t["poss_n"]),
                "ppda_avg": avg(t["ppda_sum"], t["ppda_n"]),
                # Volume de jogo
                "shots": t["shots"], "shots_on": t["shots_on"],
                "shots_on_pct": pct(t["shots_on"], t["shots"]),
                "shots_per_match": per_match(t["shots"], n),
                "passes": t["passes"], "passes_cmp": t["passes_cmp"],
                "pass_accuracy_avg": pct(t["passes_cmp"], t["passes"]),
                "passes_per_match": per_match(t["passes"], n),
                "corners": t["corners"], "fouls": t["fouls"],
                "pressures": t["pressures"],
                "pressures_per_match": per_match(t["pressures"], n),
                "duels": t["duels"], "duels_won": t["duels_won"],
                "duel_win_pct": pct(t["duels_won"], t["duels"]),
                "tackles": t["tackles"], "interceptions": t["interceptions"],
                "carries": t["carries"], "prog_carries": t["prog_carries"],
                "prog_carries_per_match": per_match(t["prog_carries"], n),
            })
        team_xg.sort(key=lambda x: x["xg_for"], reverse=True)

        finishing = []
        for p in self.players.values():
            if p["shots"] < FINISHING_MIN_SHOTS:
                continue
            code, flag = _team_meta(p["team"])
            finishing.append({
                "player": p["name"], "team": p["team"],
                "code": code, "flag": flag,
                "goals": p["goals"], "shots": p["shots"],
                "shots_on": p["shots_on"], "penalties": p["penalties"],
                "xg": round(p["xg"], 2),
                "xg_diff": round(p["goals"] - p["xg"], 2),
                "xg_per_shot": round(p["xg"] / p["shots"], 2) if p["shots"] else None,
                "shots_per_goal": round(p["shots"] / p["goals"], 1) if p["goals"] else None,
                "conversion_pct": pct(p["goals"], p["shots"]),
            })
        finishing.sort(key=lambda x: x["xg_diff"], reverse=True)

        scorers = []
        for p in self.players.values():
            if p["goals"] < 1:
                continue
            code, flag = _team_meta(p["team"])
            scorers.append({
                "player": p["name"], "team": p["team"],
                "code": code, "flag": flag,
                "goals": p["goals"], "penalties": p["penalties"],
                "xg": round(p["xg"], 2),
            })
        scorers.sort(key=lambda x: (x["goals"], -x["penalties"]), reverse=True)

        goals_by_minute = [{"range": k, "count": v}
                           for k, v in self.minute_buckets.items()]

        # Highlights — destaques de mão para os cartões bento.
        highlights = {}
        if team_xg:
            with_ppda = [t for t in team_xg if t["ppda_avg"] is not None]
            with_poss = [t for t in team_xg if t["possession_avg"] is not None]
            highlights["top_xg_team"] = team_xg[0]
            highlights["most_overperforming_team"] = max(
                team_xg, key=lambda x: x["xg_diff"])
            highlights["most_underperforming_team"] = min(
                team_xg, key=lambda x: x["xg_diff"])
            highlights["best_defense_xg"] = min(
                team_xg, key=lambda x: x["xg_against"])
            highlights["most_shots_team"] = max(team_xg, key=lambda x: x["shots"])
            if with_poss:
                highlights["most_possession_team"] = max(
                    with_poss, key=lambda x: x["possession_avg"])
            if with_ppda:
                highlights["most_pressing_team"] = min(
                    with_ppda, key=lambda x: x["ppda_avg"])
        if finishing:
            highlights["most_clinical_player"] = finishing[0]
            highlights["most_wasteful_player"] = finishing[-1]

        return {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": "StatsBomb Open Data (CC BY-NC-SA) — FIFA World Cup 2022",
            "source_url": "https://github.com/statsbomb/open-data",
            "competition": "FIFA World Cup 2022",
            "note": (
                "Panorama do torneio inteiro derivado do xG por chute e dos "
                "eventos de gol do StatsBomb. Disputa de pênaltis excluída dos "
                "agregados de xG/gol. Não há evento aberto para 2026 — estas "
                "métricas são exclusivas da Copa 2022."
            ),
            "methodology": {
                "xg": ("Soma de shot.statsbomb_xg por time/jogador. "
                       "xG a favor/contra, e over/underperformance = gols − xG."),
                "finishing": ("Gols − xG por jogador (mín. "
                              f"{FINISHING_MIN_SHOTS} chutes). "
                              "Positivo = finalizador clínico. Inclui chutes, "
                              "chutes no alvo, conversão %, xG/chute e chutes/gol."),
                "volume": ("Contagem de eventos StatsBomb por seleção no torneio "
                           "inteiro: passes tentados/certos, chutes (no alvo), "
                           "escanteios, faltas, pressões, duelos (ganhos), "
                           "desarmes, interceptações e conduções (progressivas = "
                           f"avanço ≥ {int(PROG_CARRY_MIN)} m rumo ao gol)."),
                "possession_ppda": ("Posse base-temporal e PPDA vêm dos totais "
                                    "por partida (mesma metodologia da seção "
                                    "Clássicos); média simples entre jogos."),
            },
            "matches": self.matches,
            "team_xg": team_xg,
            "finishing": finishing,
            "scorers": scorers,
            "goals_by_minute": goals_by_minute,
            "highlights": highlights,
        }


# ─── Orquestração ─────────────────────────────────────────────────────
def _fmt_score(m: dict) -> str:
    return f"{m.get('home_score', 0)}–{m.get('away_score', 0)}"


def main() -> int:
    print("═" * 60)
    print("Clássicos 2022 — StatsBomb Open Data (posse · passe · PPDA)")
    print("═" * 60)

    print("\n[1/4] Baixando índice de partidas…")
    matches = _http_get_json(MATCHES_URL)
    if not matches or not isinstance(matches, list):
        print("    ✗ Não foi possível baixar o índice de partidas.")
        return 1
    matches.sort(key=lambda m: (STAGE_RANK.get(
        m.get("competition_stage", {}).get("name", ""), 9),
        m.get("match_date", "")))
    print(f"    ✓ {len(matches)} partidas no índice")

    print("\n[2/4] Processando eventos partida a partida…")
    out_matches: dict[str, dict] = {}
    match_list: list[dict] = []
    featured_id = None
    ok = fail = 0
    panorama = PanoramaAccumulator()

    for idx, m in enumerate(matches, start=1):
        mid = str(m.get("match_id"))
        home = m.get("home_team", {}).get("home_team_name", "?")
        away = m.get("away_team", {}).get("away_team_name", "?")
        stage = m.get("competition_stage", {}).get("name", "")
        events = _http_get_json(EVENTS_URL.format(match_id=mid))
        if not events:
            fail += 1
            continue
        stats = compute_match(events, home, away)
        if not stats:
            fail += 1
            continue

        # Mesmo passe pelos eventos → panorama do torneio (xG/finalização).
        panorama.add_match(compute_shots(events, home, away), stats, home, away)

        hc, hf = _team_meta(home)
        ac, af = _team_meta(away)
        label = f"{home} {_fmt_score(m)} {away}"
        out_matches[mid] = {
            "id": mid,
            "label": label,
            "date": m.get("match_date", ""),
            "stage": stage,
            "home": {"name": home, "code": hc, "flag": hf},
            "away": {"name": away, "code": ac, "flag": af},
            **stats,
        }
        match_list.append({
            "id": mid, "label": label, "date": m.get("match_date", ""),
            "stage": stage,
            "stage_rank": STAGE_RANK.get(stage, 9),
        })
        if stage == "Final" and featured_id is None:
            featured_id = mid
        ok += 1
        if ok % 8 == 0 or idx == len(matches):
            print(f"    … {idx}/{len(matches)} — {ok} ok, {fail} falhas")
        time.sleep(FETCH_DELAY)

    if not out_matches:
        print("    ✗ Nenhuma partida processada — abortando (JSON preservado).")
        return 1

    if featured_id is None:
        featured_id = match_list[0]["id"]

    print("\n[3/4] Escrevendo classics_2022.json…")
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "StatsBomb Open Data (CC BY-NC-SA) — FIFA World Cup 2022",
        "source_url": "https://github.com/statsbomb/open-data",
        "competition": "FIFA World Cup 2022",
        "note": (
            "Análise avançada por partida (posse, precisão de passe e PPDA) "
            "por intervalo de 15 min + 1º/2º tempo, derivada do dado de evento "
            "aberto do StatsBomb. Copa 2022 — não há evento aberto para 2026."
        ),
        "methodology": {
            "possession": ("Base temporal: soma do tempo entre eventos "
                           "atribuído ao time em posse, por intervalo "
                           "(clamp de 30 s por gap)."),
            "pass_accuracy": "Passes completos ÷ passes tentados.",
            "ppda": ("Passes do adversário ÷ ações defensivas (desarmes + "
                     "interceptações + faltas) na zona de 60% do campo longe "
                     "do gol de quem pressiona. Menor = pressão mais intensa."),
        },
        "featured_id": featured_id,
        "match_list": match_list,
        "matches": out_matches,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    size = OUTPUT.stat().st_size
    print(f"    ✓ {OUTPUT.name} ({size} bytes) — {ok} partidas")

    print("\n[4/4] Escrevendo copa2022_panorama.json…")
    pan = panorama.build()
    OUTPUT_PANORAMA.write_text(json.dumps(pan, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    psize = OUTPUT_PANORAMA.stat().st_size
    print(f"    ✓ {OUTPUT_PANORAMA.name} ({psize} bytes) — "
          f"{len(pan['team_xg'])} seleções, {len(pan['scorers'])} artilheiros")
    if pan["scorers"]:
        top = pan["scorers"][0]
        print(f"    → Artilheiro: {top['player']} ({top['goals']} gols, "
              f"xG {top['xg']})")

    feat = out_matches.get(featured_id, {})
    print(f"\n✅ Concluído. Destaque: {feat.get('label', featured_id)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
