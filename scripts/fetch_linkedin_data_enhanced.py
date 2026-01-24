import json
import os
from datetime import datetime
import requests
from bs4 import BeautifulSoup


FALLBACK_DATA = {
    "profile": {
        "name": "Otávio Ribeiro",
        "headline": "Liderando a transformação da jornada de Dados & AI na Educbank",
        "location": "Curitiba, Paraná, Brasil",
        "about": """Com mais de 10 anos de experiência em Engenharia de Dados, atuo na construção de arquiteturas modernas e escaláveis em nuvem, com foco em Data Lakes, Data Warehouses e plataformas de Machine Learning. Minha especialização envolve Databricks e seu ecossistema (Delta Lake, Unity Catalog, Delta Live Tables, Feature Store e MLflow), aplicando boas práticas de governança, automação e qualidade de dados em ambientes de grande escala.

Tenho forte atuação na liderança de equipes multidisciplinares e na implementação de estratégias data-driven, impulsionando a tomada de decisão baseada em dados.

Minha experiência inclui:
✔ Modelagem de Data Warehouses (Kimball, Star Schema e Snowflake Schema) para eficiência analítica.
✔ Orquestração e automação de pipelines com Databricks Workflows, Airflow e dbt, garantindo desempenho e escalabilidade.
✔ Governança e qualidade de dados com Unity Catalog, Delta Expectations e validações automatizadas.
✔ Experiência em Google Cloud Platform (GCP) e Azure, integrando serviços nativos de Big Data e AI.
✔ Liderança técnica e gestão de times, promovendo cultura data-driven e DevOps, além de capacitação em engenharia de dados avançada.

Estou sempre em busca de desafios onde possa aplicar minha experiência em Big Data, governança e plataformas em nuvem, desenvolvendo soluções escaláveis, performáticas e sustentáveis.

📩 Interessado em trocar ideias sobre inovação em engenharia de dados e Databricks? Vamos conversar!""",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    },
    "experience": [
        {
            "role": "Gerente de Engenharia de Dados",
            "company": "Educbank",
            "period": "Jan 2025 - Presente",
            "location": "São Paulo, Brasil (Remoto)",
            "highlights": [
                "Liderança de time de engenharia responsável pela transformação da jornada de dados",
                "Migração de Data Warehouse tradicional para arquitetura Lakehouse no Databricks",
                "Implementação de Unity Catalog, Delta Live Tables e Spark Structured Streaming",
                "Governança de dados com foco em LGPD e boas práticas cloud",
                "Engenharia de ML: validação, operacionalização e deploy de modelos em produção"
            ]
        },
        {
            "role": "Especialista em Dados",
            "company": "Oto CRM",
            "period": "Jan 2024 - Jan 2025",
            "location": "Porto Alegre, Brasil (Remoto)",
            "highlights": [
                "Otimização de performance em Clickhouse, MySQL e PostgreSQL",
                "Liderança de time de integração de dados",
                "Desenvolvimento de engines Python para ingestão em Data Lakes",
                "Coleta dinâmica de dados de múltiplas fontes (bancos, APIs, plataformas)"
            ]
        },
        {
            "role": "Líder Técnico",
            "company": "DEEP ESG",
            "period": "Ago 2023 - Out 2024",
            "location": "São José dos Campos, Brasil (Remoto)",
            "highlights": [
                "Liderança de equipe multidisciplinar (engenheiros de dados + backend)",
                "Modelagem de Data Warehouse com Star Schema (Kimball)",
                "Arquitetura de calculadoras de emissão de CO₂ e KPIs ESG",
                "Stack: Airflow, DataProc, Cloud Functions (GCP), PostgreSQL, BigQuery"
            ]
        },
        {
            "role": "Líder Técnico",
            "company": "HeroSpark",
            "period": "Dez 2021 - Jul 2023",
            "location": "Curitiba, Brasil",
            "highlights": [
                "Criação e liderança de equipe de dados do zero",
                "Implementação de Data Lake e Data Warehouse",
                "Pipeline de dados com validação e controle de qualidade",
                "Promoção de cultura data-driven e capacitação de analistas",
                "Stack: AWS, Metabase, PostgreSQL, Airflow"
            ]
        },
        {
            "role": "Engenheiro de Dados",
            "company": "Grupo Voalle",
            "period": "Jan 2020 - Out 2020",
            "location": "Santa Maria, Brasil",
            "highlights": [
                "Soluções de manutenção em massa e migração de dados",
                "Migração MariaDB → PostgreSQL",
                "Automação com Shell Script e Python",
                "Análise de processos empresariais para aplicação no ERP"
            ]
        },
        {
            "role": "Founder",
            "company": "AdvanceWEB",
            "period": "Jun 2016 - Jan 2020",
            "location": "Águas de Chapecó, Brasil",
            "highlights": [
                "Fundação e gestão de startup de software",
                "Desenvolvimento de ImovPedidos (CRM para gestão de pedidos)",
                "Desenvolvimento de QTMov - Eventos (gestão de eventos internos)",
                "Administração, planejamento estratégico e comercial"
            ]
        }
    ],
    "education": [
        {
            "degree": "Curso Superior em Gestão de Projetos de TI",
            "field": "Gestão de Projetos de Tecnologia da Informação",
            "institution": "Estácio",
            "period": "2024 - 2027 (em andamento)"
        },
        {
            "degree": "Tecnólogo",
            "field": "Sistemas para Internet / Análise e Desenvolvimento de Sistemas",
            "institution": "Universidade Federal de Santa Maria (UFSM)",
            "period": "2013 - 2016"
        }
    ]
}


def parse_jsonld(soup):
    """Extrai dados do JSON-LD"""
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


def parse_html_fallback(soup):
    """Tenta extrair dados diretamente do HTML"""
    profile = {}
    
    # Nome
    name_selectors = [
        "h1.top-card-layout__title",
        "h1.text-heading-xlarge",
        ".pv-text-details__left-panel h1"
    ]
    for selector in name_selectors:
        element = soup.select_one(selector)
        if element:
            profile["name"] = element.get_text(strip=True)
            break
    
    # Headline
    headline_selectors = [
        ".top-card-layout__headline",
        ".text-body-medium.break-words",
        ".pv-text-details__left-panel .text-body-medium"
    ]
    for selector in headline_selectors:
        element = soup.select_one(selector)
        if element:
            profile["headline"] = element.get_text(strip=True)
            break
    
    return profile


def build_experience(person):
    """Constrói lista de experiências do JSON-LD"""
    experience = []
    works_for = person.get("worksFor")
    if isinstance(works_for, dict):
        works_for = [works_for]
    if isinstance(works_for, list):
        for org in works_for:
            if not isinstance(org, dict):
                continue
            experience.append({
                "role": person.get("jobTitle") or "",
                "company": org.get("name") or "",
                "period": "",
                "location": "",
                "highlights": [],
            })
    return experience


def main():
    profile_url = os.getenv("LINKEDIN_PROFILE_URL", "https://linkedin.com/in/donotavio/")
    use_fallback = os.getenv("USE_LINKEDIN_FALLBACK", "true").lower() == "true"
    
    print(f"📡 Fetching LinkedIn profile: {profile_url}")
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    })

    linkedin_cookie = os.getenv("LINKEDIN_SESSION_COOKIE")
    if linkedin_cookie:
        session.cookies.set("li_at", linkedin_cookie, domain=".linkedin.com")
        print("✓ Session cookie configured")
    else:
        print("⚠️  No session cookie - using fallback data")

    try:
        response = session.get(profile_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Tentar JSON-LD
        person = parse_jsonld(soup)
        html_data = parse_html_fallback(soup)
        
        profile = {
            "name": person.get("name") or html_data.get("name") or "",
            "headline": person.get("jobTitle") or html_data.get("headline") or "",
            "location": "",
            "about": person.get("description") or "",
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        
        address = person.get("address") or {}
        if isinstance(address, dict):
            profile["location"] = (
                address.get("addressLocality") or 
                address.get("addressRegion") or 
                ""
            )
        
        experience = build_experience(person)
        
        # Se não conseguiu dados suficientes e fallback está habilitado
        if use_fallback and (not profile["name"] or not experience):
            print("⚠️  Insufficient data from scraping, using fallback")
            profile = FALLBACK_DATA["profile"]
            experience = FALLBACK_DATA["experience"]
            education = FALLBACK_DATA["education"]
        else:
            education = []
        
        print(f"✓ Profile extracted: {profile.get('name', 'Unknown')}")
        print(f"  - Headline: {profile.get('headline', 'N/A')}")
        print(f"  - Experience entries: {len(experience)}")
        
    except Exception as e:
        print(f"❌ Error scraping LinkedIn: {e}")
        if use_fallback:
            print("✓ Using fallback data")
            profile = FALLBACK_DATA["profile"]
            experience = FALLBACK_DATA["experience"]
            education = FALLBACK_DATA["education"]
        else:
            raise

    linkedin_profile = {
        "profile": profile,
        "experience": experience,
        "education": education if 'education' in locals() else [],
    }

    # Preserve existing recommendations instead of overwriting
    recommendations_path = "assets/data/linkedin_recommendations.json"
    if os.path.exists(recommendations_path):
        try:
            with open(recommendations_path, "r", encoding="utf-8") as handle:
                linkedin_recommendations = json.load(handle)
            print("✓ Preserved existing recommendations")
        except Exception as e:
            print(f"⚠️  Could not read existing recommendations: {e}")
            linkedin_recommendations = {"recommendations": []}
    else:
        linkedin_recommendations = {"recommendations": []}

    os.makedirs("assets/data", exist_ok=True)
    
    with open("assets/data/linkedin_profile.json", "w", encoding="utf-8") as handle:
        json.dump(linkedin_profile, handle, ensure_ascii=False, indent=2)

    with open(recommendations_path, "w", encoding="utf-8") as handle:
        json.dump(linkedin_recommendations, handle, ensure_ascii=False, indent=2)
    
    print("✅ LinkedIn data saved successfully")


if __name__ == "__main__":
    main()
