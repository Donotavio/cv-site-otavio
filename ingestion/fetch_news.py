"""
PIX Observatory — Coleta de notícias recentes sobre o PIX
==========================================================
Busca o feed RSS do Google News (query "PIX Banco Central") e gera
um JSON enxuto consumido pelo widget de notícias do dashboard.

Sem autenticação, sem custo. Roda no GitHub Actions (cron) junto ao
pipeline de dados. Gera:

    assets/data/pix_news.json

Uso:
    python ingestion/fetch_news.py
"""

import json
import sys
import re
import html
from pathlib import Path
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from urllib.request import Request, urlopen
from urllib.error import URLError

# Google News RSS — query em português, região Brasil.
RSS_URL = (
    "https://news.google.com/rss/search"
    "?q=PIX+Banco+Central+pagamentos&hl=pt-BR&gl=BR&ceid=BR:pt-419"
)

OUTPUT = Path("assets/data/pix_news.json")
MAX_ITEMS = 6
TIMEOUT = 30


def _clean(text: str) -> str:
    """Remove tags HTML e normaliza entidades/espaços."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)      # strip tags
    text = html.unescape(text)                # &amp; → &
    text = re.sub(r"\s+", " ", text).strip()  # colapsa espaços
    return text


def _source_from_title(title: str) -> tuple[str, str]:
    """
    Google News formata o título como 'Manchete - Fonte'.
    Separa a fonte da manchete quando possível.
    """
    if " - " in title:
        head, _, source = title.rpartition(" - ")
        return head.strip(), source.strip()
    return title.strip(), ""


def _parse_date(raw: str) -> str:
    """Converte pubDate RFC-822 para ISO 8601 (ou devolve vazio)."""
    if not raw:
        return ""
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue
    return ""


def fetch_news() -> list[dict]:
    """Busca e parseia o RSS. Retorna lista de notícias normalizadas."""
    req = Request(RSS_URL, headers={"User-Agent": "pix-observatory/1.0"})
    with urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    items = root.findall(".//item")

    news: list[dict] = []
    for item in items[:MAX_ITEMS]:
        title_raw = _clean(item.findtext("title", ""))
        headline, source = _source_from_title(title_raw)
        news.append({
            "title": headline,
            "source": source,
            "url": item.findtext("link", "").strip(),
            "published": _parse_date(item.findtext("pubDate", "")),
        })
    return news


def main() -> int:
    try:
        news = fetch_news()
    except (URLError, ET.ParseError, TimeoutError) as e:
        print(f"  ✗ Falha ao buscar RSS: {e}")
        print("  → Mantendo pix_news.json existente (se houver).")
        return 0  # não quebra o pipeline — widget usa o JSON anterior

    if not news:
        print("  ⚠ RSS retornou vazio — mantendo JSON anterior.")
        return 0

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "query": "PIX Banco Central pagamentos",
        "source_feed": "Google News RSS",
        "items": news,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  ✓ {OUTPUT} ({len(news)} notícias)")
    for n in news:
        print(f"    · {n['title'][:70]}  [{n['source']}]")
    return 0


if __name__ == "__main__":
    print("📰 Coletando notícias recentes do PIX...")
    sys.exit(main())
