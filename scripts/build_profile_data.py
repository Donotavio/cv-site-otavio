import json
from datetime import datetime
from pathlib import Path


def read_json(path):
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main():
    base_dir = Path(__file__).resolve().parents[1]
    data_dir = base_dir / "assets" / "data"

    linkedin = read_json(data_dir / "linkedin_profile.json")
    recommendations = read_json(data_dir / "linkedin_recommendations.json")
    github = read_json(data_dir / "github_activity.json")

    profile = linkedin.get("profile", {})
    experience = linkedin.get("experience", [])
    merged = {
        "profile": {
            "name": profile.get("name") or "Otávio Henrique da Silva Ribeiro",
            "title": profile.get("headline") or "Gerente de Engenharia de Dados",
            "location": profile.get("location") or "Curitiba, Brasil",
            "summary": profile.get("about") or "",
            "updated_at": datetime.utcnow().isoformat() + "Z",
        },
        "timeline": experience,
        "projects": github.get("projects", []),
        "recommendations": recommendations.get("recommendations", []),
    }

    output_path = data_dir / "profile.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(merged, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
