"""
World Cup Dashboard — Ball-Level Data Pipeline (Custo Zero)
===========================================================
Camada de análise para as seções 04/05/06 do dashboard.

FONTE PRIMÁRIA (garantida, 100% real 2026):
    openfootball/worldcup.json → gols com minuto → momentum do jogo
    A curva mostra gols acumulados por minuto — real, ao vivo, Copa 2026.

FONTE SECUNDÁRIA (best-effort, pode 403):
    FBref → xG + coordenadas de finalização → shot map
    FBref bloqueia scraping local (Cloudflare 403). Do GitHub Actions
    pode funcionar (IP de CI ≠ IP de dev). Se funcionar, o shot map
    popula; se falhar, a seção mostra estado graceful.

HONESTIDADE: a Adidas Trionda (bola oficial 2026) tem um chip IMU, mas
esse stream é privado (FIFA/Kinexion). O momentum aqui vem de gols reais
do openfootball, NÃO do sensor. Quando FBref disponível, o shot map usa
rastreamento óptico (câmeras), também não o chip.

    deepstats.json ← openfootball (momentum) + FBref (shots, best-effort)

Uso:
    python ingestion_worldcup/fetch_ball_level.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ─── Fontes ───────────────────────────────────────────────────────────
OPENFOOTBALL_RAW = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master"
)
URL_MATCHES_2026 = f"{OPENFOOTBALL_RAW}/2026/worldcup.json"

# FBref (best-effort — Cloudflare pode bloquear)
FBREF_WC2026 = "https://fbref.com/en/comps/1/2026/World-Cup-2026-Stats"

# ─── Configuração ─────────────────────────────────────────────────────
OUTPUT_DIR = Path("public/world-cup-dashboard/data")
HTTP_TIMEOUT = 30
FBREF_TIMEOUT = 20
USER_AGENT = "worldcup-dashboard/1.0 (+https://github.com/Donotavio/cv-site-otavio)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 48 seleções da WC 2026 + placeholder (extraído do partidas.json)
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


# ─── HTTP / IO helpers ────────────────────────────────────────────────
def _http_get(url: str, ua: str = USER_AGENT, timeout: int = HTTP_TIMEOUT) -> bytes:
    req = Request(url, headers={"User-Agent": ua, "Accept": "application/json,*/*"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_get_json(url: str) -> list | dict | None:
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


def _parse_minute(raw) -> int:
    """openfootball guarda minutos como string: '9', '67', '45+2', '90+3'."""
    s = str(raw or "0").replace("'", "").strip()
    m = re.match(r"(\d+)", s)
    return int(m.group(1)) if m else 90


# ═══════════════════════════════════════════════════════════════════════
# PHASE 1 — Momentum real (openfootball → gols acumulados por minuto)
# ═══════════════════════════════════════════════════════════════════════
def pick_featured_match(matches: list[dict]) -> dict | None:
    """
    Seleciona a partida mais emocionante já finalizada.
    Critério: mais gols no total → desempate por data mais recente.
    """
    finished = []
    for m in matches:
        ft = m.get("score", {}).get("ft")
        if not ft or not isinstance(ft, list):
            continue
        g1 = m.get("goals1") or []
        g2 = m.get("goals2") or []
        total_goals = len(g1) + len(g2)
        if total_goals == 0:
            continue
        finished.append((total_goals, m.get("date", ""), m))
    if not finished:
        return None
    finished.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return finished[0][2]


def build_momentum(match: dict) -> dict:
    """Constrói série temporal de gols acumulados por minuto (5 em 5 min)."""
    team1 = match.get("team1", "?")
    team2 = match.get("team2", "?")
    ft = match["score"]["ft"]
    goals1 = match.get("goals1") or []
    goals2 = match.get("goals2") or []

    labels = list(range(0, 91, 5))  # 0, 5, 10, ..., 90

    def cumulative(goal_list: list[dict]) -> list[int]:
        minutes = [_parse_minute(g.get("minute")) for g in goal_list]
        return [sum(1 for m in minutes if m <= boundary) for boundary in labels]

    home_cum = cumulative(goals1)
    away_cum = cumulative(goals2)

    # Markers de gol com valor acumulado no instante
    def markers(goal_list: list[dict], side: str) -> list[dict]:
        result = []
        for g in goal_list:
            minute = _parse_minute(g.get("minute"))
            cum = sum(1 for x in goal_list if _parse_minute(x.get("minute")) <= minute)
            result.append({
                "minute": minute,
                "team": side,
                "player": g.get("name", ""),
                "cum": cum,
            })
        return result

    goals = markers(goals1, "home") + markers(goals2, "away")
    goals.sort(key=lambda x: x["minute"])

    code1, flag1 = _team_meta(team1)
    code2, flag2 = _team_meta(team2)

    return {
        "match": f"{team1} {ft[0]}–{ft[1]} {team2}",
        "date": match.get("date", ""),
        "stage": match.get("group") or match.get("round", ""),
        "metric": "goals",
        "metric_label": "Gols acumulados",
        "labels": labels,
        "home": {"code": code1, "flag": flag1, "name": team1, "cum": home_cum},
        "away": {"code": code2, "flag": flag2, "name": team2, "cum": away_cum},
        "goals": goals,
        "source_note": "gols reais do openfootball · não é telemetria do chip",
    }


# ═══════════════════════════════════════════════════════════════════════
# PHASE 2 — FBref shot data (best-effort, pode 403)
# ═══════════════════════════════════════════════════════════════════════
def attempt_fbref_shots() -> dict | None:
    """
    Tenta buscar dados de finalização do FBref.
    Cloudflare pode bloquear (403). Se bloquear, retorna None e a seção
    04 mostra estado graceful. Do GitHub Actions pode funcionar.
    """
    print("    Tentando FBref (pode demorar ou 403)…")
    try:
        req = Request(FBREF_WC2026, headers={
            "User-Agent": BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })
        resp = urlopen(req, timeout=FBREF_TIMEOUT)
        html_body = resp.read().decode("utf-8", errors="replace")
        if len(html_body) < 5000 or "cloudflare" in html_body.lower():
            print("    ✗ FBref retornou página de bloqueio Cloudflare.")
            return None
        print(f"    ✓ FBref respondeu ({len(html_body)} bytes) — parse não implementado nesta versão.")
        # TODO: parse shot tables com beautifulsoup4 quando confirmar acesso do CI.
        # Por enquanto, retorna None — a seção 04 fica em estado graceful.
        return None
    except (HTTPError, URLError, TimeoutError, OSError) as e:
        print(f"    ✗ FBref indisponível: {e}")
        return None


# ─── Orquestração ─────────────────────────────────────────────────────
def main() -> int:
    print("═" * 60)
    print("Ball-Level Data Pipeline — World Cup 2026")
    print("═" * 60)

    # ── Phase 1: openfootball (garantido) ──────────────────────────
    print("\n[1/3] Buscando partidas reais WC 2026 (openfootball)…")
    data = _http_get_json(URL_MATCHES_2026)
    if not data or not isinstance(data, dict) or not data.get("matches"):
        print("    ✗ openfootball WC 2026 indisponível — abortando.")
        return 1
    matches = data["matches"]
    print(f"    ✓ {len(matches)} partidas no índice")

    featured = pick_featured_match(matches)
    if not featured:
        print("    ✗ Nenhuma partida finalizada com gols encontrada.")
        return 1

    momentum = build_momentum(featured)
    n_goals = len(momentum["goals"])
    print(f"    ✓ Partida destaque: {momentum['match']}")
    print(f"      {n_goals} gols · {momentum['date']} · {momentum['stage']}")

    # ── Phase 2: FBref (best-effort) ───────────────────────────────
    print("\n[2/3] Tentando shot data (FBref, best-effort)…")
    fbref_shots = attempt_fbref_shots()

    shot_map = fbref_shots if fbref_shots else {
        "match": "—",
        "shots": [],
        "available": False,
        "note": "Shot data requer FBref. Tentativa automatizada ativa no pipeline CI.",
    }

    # pass_network: sem fonte gratuita para 2026
    pass_network = {
        "available": False,
        "note": "Rede de passes requer rastreamento óptico (StatsBomb 360). "
                "Dados abertos de WC 2026 serão liberados meses após o torneio.",
    }

    # ── Phase 3: Escrita ───────────────────────────────────────────
    print("\n[3/3] Escrevendo deepstats.json…")
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "openfootball (momentum) + FBref (shots, best-effort)",
        "tournament": "FIFA World Cup 2026",
        "shot_map": shot_map,
        "pass_network": pass_network,
        "momentum": momentum,
    }

    output = OUTPUT_DIR / "deepstats.json"
    _write_json_resilient(output, payload)

    print(f"\n✅ Pipeline concluído.")
    print(f"   Momentum: REAL ({momentum['match']}, {n_goals} gols)")
    print(f"   Shot map: {'FBref' if fbref_shots else 'indisponível (aguardando FBref CI)'}")
    print(f"   Pass net: indisponível (sem fonte gratuita 2026)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
