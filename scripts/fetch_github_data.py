import json
import os
from datetime import datetime, timedelta
from urllib.request import Request, urlopen


def request_json(url, token):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    username = os.getenv("GITHUB_USERNAME")
    token = os.getenv("GITHUB_TOKEN")
    if not username:
        raise SystemExit("GITHUB_USERNAME is required")

    user = request_json(f"https://api.github.com/users/{username}", token)
    repos = request_json(
        f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated",
        token,
    )

    repos = [repo for repo in repos if not repo.get("fork")]
    total_stars = sum(repo.get("stargazers_count", 0) for repo in repos)

    sorted_repos = sorted(
        repos,
        key=lambda repo: (repo.get("stargazers_count", 0), repo.get("updated_at", "")),
        reverse=True,
    )

    projects = []
    for repo in sorted_repos[:6]:
        projects.append(
            {
                "name": repo.get("name"),
                "description": repo.get("description") or "",
                "language": repo.get("language") or "",
                "stars": repo.get("stargazers_count", 0),
                "url": repo.get("html_url"),
            }
        )

    language_totals = {}
    for repo in sorted_repos[:8]:
        languages_url = repo.get("languages_url")
        if not languages_url:
            continue
        languages = request_json(languages_url, token)
        for lang, size in languages.items():
            language_totals[lang] = language_totals.get(lang, 0) + size

    total_bytes = sum(language_totals.values()) or 1
    top_languages = [
        {
            "name": lang,
            "bytes": size,
            "percentage": round(size / total_bytes * 100, 2),
        }
        for lang, size in sorted(
            language_totals.items(), key=lambda item: item[1], reverse=True
        )
    ][:6]

    events = request_json(
        f"https://api.github.com/users/{username}/events/public?per_page=100",
        token,
    )
    recent_commits = 0
    for event in events:
        if event.get("type") == "PushEvent":
            payload = event.get("payload", {})
            recent_commits += len(payload.get("commits", []))

    now = datetime.utcnow()
    payload = {
        "generated_at": now.isoformat() + "Z",
        "next_update": (now + timedelta(days=1)).isoformat() + "Z",
        "update_frequency": "daily",
        "data_version": "2.0",
        "summary": {
            "public_repos": user.get("public_repos", 0),
            "total_stars": total_stars,
            "recent_commits": recent_commits,
        },
        "top_languages": top_languages,
        "projects": projects,
    }

    output_path = os.path.join("assets", "data", "github_activity.json")
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
