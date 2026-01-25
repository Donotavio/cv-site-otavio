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


def request_graphql(query, variables, token):
    """Faz requisição GraphQL para a API do GitHub"""
    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "profile-updater",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, headers=headers, data=data, method="POST")
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_activity_breakdown_by_year(username, token, year):
    """Busca breakdown de atividades por ano usando GraphQL"""
    if not token:
        return None
    
    from_date = f"{year}-01-01T00:00:00Z"
    to_date = f"{year}-12-31T23:59:59Z"
    
    query = """
    query($username: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $username) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          totalIssueContributions
        }
      }
    }
    """
    
    variables = {
        "username": username,
        "from": from_date,
        "to": to_date
    }
    
    try:
        result = request_graphql(query, variables, token)
        
        if "errors" in result or not result.get("data", {}).get("user"):
            print(f"Error fetching breakdown for {year}: {result.get('errors', 'No user data')}")
            return None
            
        collection = result["data"]["user"]["contributionsCollection"]
        
        commits = collection.get("totalCommitContributions", 0)
        prs = collection.get("totalPullRequestContributions", 0)
        reviews = collection.get("totalPullRequestReviewContributions", 0)
        issues = collection.get("totalIssueContributions", 0)
        
        print(f"Year {year} - Commits: {commits}, PRs: {prs}, Reviews: {reviews}, Issues: {issues}")
        
        total = commits + prs + reviews + issues or 1
        
        breakdown = {
            "commits": round((commits / total) * 100),
            "pull_requests": round((prs / total) * 100),
            "code_review": round((reviews / total) * 100),
            "issues": round((issues / total) * 100)
        }
        
        print(f"Year {year} - Breakdown: {breakdown}")
        
        return breakdown
    except Exception as e:
        print(f"Warning: Could not fetch activity breakdown for {year}: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_contributions_calendar(username, token, year=None):
    """Busca calendário de contribuições usando GraphQL"""
    if not token:
        print("Warning: GITHUB_TOKEN required for contributions calendar")
        return {}
    
    current_year = datetime.utcnow().year
    target_year = year or current_year
    
    # Calcular datas de início e fim do ano
    from_date = f"{target_year}-01-01T00:00:00Z"
    to_date = f"{target_year}-12-31T23:59:59Z"
    
    query = """
    query($username: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $username) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                weekday
              }
            }
          }
        }
      }
    }
    """
    
    variables = {
        "username": username,
        "from": from_date,
        "to": to_date
    }
    
    try:
        result = request_graphql(query, variables, token)
        
        if "errors" in result:
            print(f"GraphQL errors: {result['errors']}")
            return {}
            
        if "data" in result and result["data"] and result["data"]["user"]:
            calendar = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            
            # Processar dados do calendário
            days = []
            for week in calendar["weeks"]:
                for day in week["contributionDays"]:
                    days.append({
                        "date": day["date"],
                        "count": day["contributionCount"],
                        "weekday": day["weekday"]
                    })
            
            return {
                "year": target_year,
                "total": calendar["totalContributions"],
                "days": days
            }
    except Exception as e:
        print(f"Warning: Could not fetch contributions calendar for {target_year}: {e}")
    
    return {}


def main():
    username = os.getenv("GITHUB_USERNAME")
    token = os.getenv("GITHUB_TOKEN")
    
    if not username:
        raise SystemExit("Error: GITHUB_USERNAME environment variable is required")
    
    if not username.strip():
        raise SystemExit("Error: GITHUB_USERNAME cannot be empty")
    
    if not token:
        print("Warning: GITHUB_TOKEN not set. API rate limits will be restrictive.")

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
    push_events = 0
    pr_events = 0
    review_events = 0
    issue_events = 0
    commits_this_month = 0
    repos_contributed = set()
    prs_opened = 0
    prs_reviewed = 0
    
    now_date = datetime.utcnow()
    month_start = now_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Buscar commits do mês atual do repositório curr-don diretamente
    try:
        since_date = month_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        commits_url = f"https://api.github.com/repos/{username}/curr-don/commits?since={since_date}&author={username}"
        curr_don_commits = request_json(commits_url, token)
        commits_this_month = len(curr_don_commits) if isinstance(curr_don_commits, list) else 0
    except Exception as e:
        print(f"Warning: Could not fetch curr-don commits: {e}")
        commits_this_month = 0
    
    if commits_this_month < 0:
        commits_this_month = 0
    
    for event in events:
        event_type = event.get("type")
        event_date = datetime.strptime(event.get("created_at", ""), "%Y-%m-%dT%H:%M:%SZ") if event.get("created_at") else None
        repo_name = event.get("repo", {}).get("name")
        
        if event_type == "PushEvent":
            push_events += 1
            # Nota: commits não vêm no payload de /events, buscar diretamente do repo
            if repo_name:
                repos_contributed.add(repo_name)
        elif event_type == "PullRequestEvent":
            pr_events += 1
            if event.get("payload", {}).get("action") == "opened":
                prs_opened += 1
            if repo_name:
                repos_contributed.add(repo_name)
        elif event_type == "PullRequestReviewEvent":
            review_events += 1
            prs_reviewed += 1
        elif event_type in ["IssuesEvent", "IssueCommentEvent"]:
            issue_events += 1
    
    total_events = push_events + pr_events + review_events + issue_events or 1
    
    activity_breakdown = {
        "commits": round((push_events / total_events) * 100),
        "code_review": round((review_events / total_events) * 100),
        "issues": round((issue_events / total_events) * 100),
        "pull_requests": round((pr_events / total_events) * 100),
    }
    
    recent_activity = {
        "commits_this_month": commits_this_month,
        "repos_contributed": len(repos_contributed),
        "pull_requests_opened": prs_opened,
        "pull_requests_reviewed": prs_reviewed,
    }
    
    # Usar commits_this_month como base para recent_commits
    recent_commits = commits_this_month if commits_this_month > 0 else recent_commits
    
    contributions_last_year = user.get("contributions", 0)
    if not contributions_last_year:
        contributions_last_year = recent_commits * 12

    # Buscar contribuições e breakdown dos últimos 5 anos
    current_year = now_date.year
    contributions_by_year = {}
    breakdown_by_year = {}
    
    for year in range(current_year - 4, current_year + 1):
        calendar_data = fetch_contributions_calendar(username, token, year)
        if calendar_data:
            contributions_by_year[str(year)] = calendar_data
        
        # Buscar breakdown para cada ano
        year_breakdown = fetch_activity_breakdown_by_year(username, token, year)
        if year_breakdown:
            breakdown_by_year[str(year)] = year_breakdown

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
            "contributions_last_year": contributions_last_year,
        },
        "activity_breakdown": activity_breakdown,
        "activity_breakdown_by_year": breakdown_by_year,
        "recent_activity": recent_activity,
        "top_languages": top_languages,
        "projects": projects,
        "contributions_calendar": contributions_by_year,
    }

    output_path = os.path.join("assets", "data", "github_activity.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(f"Successfully wrote GitHub activity data to {output_path}")
    except IOError as e:
        raise SystemExit(f"Error: Failed to write output file: {e}")


if __name__ == "__main__":
    main()
