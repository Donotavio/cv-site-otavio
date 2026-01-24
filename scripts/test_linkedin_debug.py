import json
import os
import requests
from bs4 import BeautifulSoup


def main():
    profile_url = "https://linkedin.com/in/donotavio/"
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    })

    linkedin_cookie = os.getenv("LINKEDIN_SESSION_COOKIE")
    if linkedin_cookie:
        session.cookies.set("li_at", linkedin_cookie, domain=".linkedin.com")
        print("✓ Cookie de sessão configurado")
    else:
        print("⚠️  Sem cookie de sessão - dados limitados")

    print(f"\n📡 Buscando: {profile_url}")
    response = session.get(profile_url, timeout=30)
    print(f"Status: {response.status_code}")
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Procurar JSON-LD
    scripts = soup.find_all("script", type="application/ld+json")
    print(f"\n🔍 Scripts JSON-LD encontrados: {len(scripts)}")
    
    for i, script in enumerate(scripts):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            print(f"\n📄 Script {i+1}:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
            
            if isinstance(data, dict) and data.get("@type") == "Person":
                print("\n✅ Perfil Person encontrado!")
                print(f"Nome: {data.get('name')}")
                print(f"JobTitle: {data.get('jobTitle')}")
                print(f"Description: {data.get('description', '')[:100]}...")
                
        except json.JSONDecodeError:
            print(f"❌ Erro ao parsear script {i+1}")
    
    # Tentar extrair via HTML direto
    print("\n\n🔍 Tentando extrair via HTML...")
    
    # Nome
    name_selectors = [
        "h1.top-card-layout__title",
        "h1.text-heading-xlarge",
        ".pv-text-details__left-panel h1"
    ]
    for selector in name_selectors:
        name = soup.select_one(selector)
        if name:
            print(f"✓ Nome via {selector}: {name.get_text(strip=True)}")
            break
    
    # Headline
    headline_selectors = [
        ".top-card-layout__headline",
        ".text-body-medium",
        ".pv-text-details__left-panel .text-body-medium"
    ]
    for selector in headline_selectors:
        headline = soup.select_one(selector)
        if headline:
            print(f"✓ Headline via {selector}: {headline.get_text(strip=True)}")
            break
    
    # Salvar HTML para debug
    with open("debug_linkedin.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("\n💾 HTML salvo em debug_linkedin.html")


if __name__ == "__main__":
    main()
