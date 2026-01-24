import json
import os
from datetime import datetime

import requests
from bs4 import BeautifulSoup


def parse_jsonld(soup):
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and entry.get("@type") == "Person":
                    return entry
        if isinstance(data, dict) and data.get("@type") == "Person":
            return data
    return {}


def build_experience(person):
    experience = []
    works_for = person.get("worksFor")
    if isinstance(works_for, dict):
        works_for = [works_for]
    if isinstance(works_for, list):
        for org in works_for:
            if not isinstance(org, dict):
                continue
            experience.append(
                {
                    "role": person.get("jobTitle") or "",
                    "company": org.get("name") or "",
                    "period": "",
                    "location": "",
                    "highlights": [],
                }
            )
    return experience


def main():
    profile_url = os.getenv("LINKEDIN_PROFILE_URL")
    if not profile_url:
        raise SystemExit("LINKEDIN_PROFILE_URL is required")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
    )

    linkedin_cookie = os.getenv("LINKEDIN_SESSION_COOKIE")
    if linkedin_cookie:
        session.cookies.set("li_at", linkedin_cookie, domain=".linkedin.com")

    response = session.get(profile_url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    person = parse_jsonld(soup)
    profile = {
        "name": person.get("name") or "",
        "headline": person.get("jobTitle") or "",
        "location": "",
        "about": person.get("description") or "",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }

    address = person.get("address") or {}
    if isinstance(address, dict):
        profile["location"] = address.get("addressLocality") or address.get("addressRegion") or ""

    linkedin_profile = {
        "profile": profile,
        "experience": build_experience(person),
        "education": [],
    }

    linkedin_recommendations = {"recommendations": []}

    with open("assets/data/linkedin_profile.json", "w", encoding="utf-8") as handle:
        json.dump(linkedin_profile, handle, ensure_ascii=False, indent=2)

    with open(
        "assets/data/linkedin_recommendations.json", "w", encoding="utf-8"
    ) as handle:
        json.dump(linkedin_recommendations, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
