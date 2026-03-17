#!/usr/bin/env python3
"""
Fetch LinkedIn Pulse articles from a public profile.

1. Lists article URLs from the public profile page
2. Extracts metadata (JSON-LD) and full body from each article
3. Outputs assets/data/blog_articles.json
"""

import json
import os
import re
import sys
import time
import math
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

PROFILE_URL = os.environ.get("LINKEDIN_PROFILE_URL", "https://linkedin.com/in/donotavio/")
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "assets" / "data" / "blog_articles.json"
REQUEST_DELAY = 2  # seconds between requests
WORDS_PER_MINUTE = 200
MAX_FEATURED = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


def fetch_page(url: str):
    """Fetch a URL and return parsed HTML."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print(f"  [WARN] Failed to fetch {url}: {e}", file=sys.stderr)
        return None


def extract_article_urls(profile_url: str):
    """Extract Pulse article URLs from a LinkedIn public profile."""
    print(f"Fetching profile: {profile_url}")
    soup = fetch_page(profile_url)
    if not soup:
        return []

    urls = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/pulse/" in href:
            # Clean tracking params
            clean_url = href.split("?")[0]
            urls.add(clean_url)

    # Also check the recent-activity page
    activity_url = profile_url.rstrip("/") + "/recent-activity/articles/"
    print(f"Fetching activity page: {activity_url}")
    time.sleep(REQUEST_DELAY)
    soup_activity = fetch_page(activity_url)
    if soup_activity:
        for a_tag in soup_activity.find_all("a", href=True):
            href = a_tag["href"]
            if "/pulse/" in href:
                clean_url = href.split("?")[0]
                urls.add(clean_url)

    print(f"  Found {len(urls)} article URL(s)")
    return sorted(urls)


def extract_json_ld(soup: BeautifulSoup):
    """Extract JSON-LD structured data from an article page."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Article":
                        return item
            elif data.get("@type") == "Article":
                return data
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def extract_body_text(soup: BeautifulSoup):
    """Extract the main article body text."""
    # Try common LinkedIn article content selectors
    content_selectors = [
        "div.article-content",
        "div.reader-article-content",
        "section.article-body",
        "div.content-body",
        "article",
    ]

    content_el = None
    for selector in content_selectors:
        content_el = soup.select_one(selector)
        if content_el:
            break

    if not content_el:
        # Fallback: find the largest text block
        paragraphs = soup.find_all("p")
        if paragraphs:
            texts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50]
            return "\n\n".join(texts)
        return ""

    paragraphs = []
    for el in content_el.find_all(["p", "h2", "h3", "h4", "blockquote", "li"]):
        text = el.get_text(strip=True)
        if text:
            if el.name in ("h2", "h3", "h4"):
                paragraphs.append(f"## {text}")
            elif el.name == "blockquote":
                paragraphs.append(f"> {text}")
            elif el.name == "li":
                paragraphs.append(f"- {text}")
            else:
                paragraphs.append(text)

    return "\n\n".join(paragraphs)


def extract_tags(soup: BeautifulSoup, body_text: str):
    """Extract hashtags from the article or infer from content."""
    tags = set()

    # Look for hashtags in the page
    for el in soup.find_all(string=re.compile(r"#\w+")):
        for match in re.findall(r"#(\w+)", el):
            if len(match) > 2:
                tags.add(match)

    if not tags:
        # Infer from common keywords
        keywords = {
            "Dados": ["dados", "data"],
            "Liderança": ["liderança", "líder", "gestor", "gestão"],
            "Estratégia": ["estratégia", "estratégico"],
            "Engenharia": ["engenharia", "engineering", "pipeline"],
            "Cloud": ["cloud", "nuvem", "azure", "gcp", "aws"],
            "Databricks": ["databricks"],
            "Analytics": ["analytics", "análise"],
            "IA": ["inteligência artificial", "ia", "ai", "machine learning", "ml"],
        }
        body_lower = body_text.lower()
        for tag, terms in keywords.items():
            if any(term in body_lower for term in terms):
                tags.add(tag)

    return sorted(tags)[:5]


def calculate_read_time(text: str):
    """Estimate reading time in minutes."""
    words = len(text.split())
    minutes = max(1, math.ceil(words / WORDS_PER_MINUTE))
    return f"{minutes} min"


def slugify(text: str):
    """Create a URL-friendly slug from text."""
    text = text.lower().strip()
    text = re.sub(r"[àáâãäå]", "a", text)
    text = re.sub(r"[èéêë]", "e", text)
    text = re.sub(r"[ìíîï]", "i", text)
    text = re.sub(r"[òóôõö]", "o", text)
    text = re.sub(r"[ùúûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:80]


def extract_article(url: str):
    """Extract full article data from a Pulse URL."""
    print(f"  Fetching article: {url}")
    soup = fetch_page(url)
    if not soup:
        return None

    json_ld = extract_json_ld(soup)
    body = extract_body_text(soup)

    # Get title from JSON-LD or page title
    title = ""
    if json_ld:
        title = json_ld.get("name", "") or json_ld.get("headline", "")
    if not title:
        title_el = soup.find("h1")
        if title_el:
            title = title_el.get_text(strip=True)
    if not title:
        return None

    # Get excerpt
    excerpt = ""
    if json_ld:
        excerpt = json_ld.get("description", "") or json_ld.get("headline", "")
    if not excerpt and body:
        # First paragraph as excerpt
        first_para = body.split("\n\n")[0]
        excerpt = first_para[:200] + ("..." if len(first_para) > 200 else "")

    # Get date
    date = ""
    if json_ld:
        date_raw = json_ld.get("datePublished", "") or json_ld.get("dateCreated", "")
        if date_raw:
            date = date_raw[:10]  # YYYY-MM-DD

    # Get image
    image = ""
    if json_ld:
        img_data = json_ld.get("image", {})
        if isinstance(img_data, dict):
            image = img_data.get("url", "")
        elif isinstance(img_data, str):
            image = img_data
        elif isinstance(img_data, list) and img_data:
            image = img_data[0] if isinstance(img_data[0], str) else img_data[0].get("url", "")

    # Get likes
    likes = 0
    if json_ld:
        stats = json_ld.get("interactionStatistic", [])
        if isinstance(stats, list):
            for stat in stats:
                if not isinstance(stat, dict):
                    continue
                interaction_type = stat.get("interactionType", "")
                if isinstance(interaction_type, dict):
                    type_name = interaction_type.get("@type", "")
                elif isinstance(interaction_type, str):
                    type_name = interaction_type
                else:
                    type_name = ""
                if "Like" in type_name:
                    likes = int(stat.get("userInteractionCount", 0))

    tags = extract_tags(soup, body)
    read_time = calculate_read_time(body) if body else "3 min"

    return {
        "id": slugify(title),
        "title": title,
        "excerpt": excerpt,
        "body": body,
        "date": date,
        "image": image,
        "external_url": url,
        "likes": likes,
        "read_time": read_time,
        "tags": tags,
        "featured": False,  # Set later
    }


def main():
    print("=== LinkedIn Articles Fetcher ===\n")

    article_urls = extract_article_urls(PROFILE_URL)
    if not article_urls:
        print("No article URLs found. Writing empty articles file.")
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps({"articles": [], "external_links": {
            "linkedin_posts": PROFILE_URL.rstrip("/") + "/recent-activity/all/"
        }}, indent=2, ensure_ascii=False) + "\n")
        return

    articles = []
    for url in article_urls:
        time.sleep(REQUEST_DELAY)
        article = extract_article(url)
        if article:
            articles.append(article)
            print(f"    ✓ {article['title'][:60]}")
        else:
            print(f"    ✗ Failed to extract: {url}")

    # Sort by date descending
    articles.sort(key=lambda a: a.get("date", ""), reverse=True)

    # Mark top N as featured
    for i, article in enumerate(articles):
        article["featured"] = i < MAX_FEATURED

    output = {
        "articles": articles,
        "external_links": {
            "medium": None,
            "dev_to": None,
            "linkedin_posts": PROFILE_URL.rstrip("/") + "/recent-activity/all/",
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(f"\n✓ Saved {len(articles)} articles to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
