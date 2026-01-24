import json
import re
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
    
    # Ler profile.json existente para preservar dados antigos
    output_path = data_dir / "profile.json"
    existing_profile = read_json(output_path) if output_path.exists() else {}
    existing_timeline = existing_profile.get("timeline", [])
    
    # Experiências que devem ser preservadas (não estão no LinkedIn)
    # Baseado no período: experiências antes de 2016
    linkedin_timeline = linkedin.get("experience", [])
    
    # Identificar experiências antigas que não estão no LinkedIn (antes de 2016)
    preserved_experiences = []
    for exp in existing_timeline:
        period = exp.get("period", "")
        # Extrair ano inicial do período
        year_match = re.search(r'\b(20\d{2})\b', period)
        if year_match:
            year = int(year_match.group(1))
            # Preservar experiências antes de 2016
            if year < 2016:
                preserved_experiences.append(exp)
    
    # Combinar: dados do LinkedIn + experiências antigas preservadas
    combined_timeline = linkedin_timeline + preserved_experiences

    profile = linkedin.get("profile", {})
    merged = {
        "profile": {
            "name": profile.get("name") or "Otávio Henrique da Silva Ribeiro",
            "title": profile.get("headline") or "Gerente de Engenharia de Dados",
            "location": profile.get("location") or "Curitiba, Brasil",
            "summary": profile.get("about") or "",
            "updated_at": datetime.utcnow().isoformat() + "Z",
        },
        "timeline": combined_timeline,
        "projects": github.get("projects", []),
        "recommendations": recommendations.get("recommendations", []),
    }

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(merged, handle, ensure_ascii=False, indent=2)

    print(f"✓ Merged profile data saved to {output_path}")
    print(f"  - LinkedIn experiences: {len(linkedin_timeline)}")
    print(f"  - Preserved old experiences: {len(preserved_experiences)}")
    print(f"  - Total timeline entries: {len(combined_timeline)}")


if __name__ == "__main__":
    main()
