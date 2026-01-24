import json
import os
from pathlib import Path


TRANSLATIONS = {
    "pt-BR": {
        "saul_goodman": "Extensão MV3 para Chrome/Chromium que assume o alter ego vendedor de Saul Goodman para monitorar quanto tempo você passa em sites produtivos versus procrastinatórios.",
        "Avaliador-de-Prompt-IA": "Sistema inteligente de avaliação de prompts para modelos de IA.",
        "Sentinel": "Aplicativo iOS de monitoramento e segurança.",
        "DON-Auto-Clicker": "Software de auto clicker escrito em Assembly, compatível com Linux, macOS e Windows. Permite definir duração e taxa de cliques, útil para automação de tarefas repetitivas.",
        "GSheetsETL": "Pipeline ETL para Google Sheets com automação de extração, transformação e carga de dados.",
        "Donotavio": "Repositório de perfil pessoal com automações e configurações.",
        "curr-don": "Site executivo pessoal com integração automática de dados do GitHub e LinkedIn.",
    },
    "en-US": {
        "saul_goodman": "MV3 Chrome/Chromium extension that takes on Saul Goodman's salesman alter ego to monitor time spent on productive versus procrastination sites.",
        "Avaliador-de-Prompt-IA": "Intelligent prompt evaluation system for AI models.",
        "Sentinel": "iOS monitoring and security application.",
        "DON-Auto-Clicker": "Auto clicker software written in Assembly, compatible with Linux, macOS, and Windows. Allows setting execution duration and click rate, useful for automating repetitive tasks.",
        "GSheetsETL": "ETL pipeline for Google Sheets with automated data extraction, transformation, and loading.",
        "Donotavio": "Personal profile repository with automations and configurations.",
        "curr-don": "Executive personal website with automated GitHub and LinkedIn data integration.",
    },
    "es-ES": {
        "saul_goodman": "Extensión MV3 para Chrome/Chromium que asume el alter ego vendedor de Saul Goodman para monitorear el tiempo en sitios productivos versus procrastinación.",
        "Avaliador-de-Prompt-IA": "Sistema inteligente de evaluación de prompts para modelos de IA.",
        "Sentinel": "Aplicación iOS de monitoreo y seguridad.",
        "DON-Auto-Clicker": "Software de auto clicker escrito en Assembly, compatible con Linux, macOS y Windows. Permite definir duración y tasa de clics, útil para automatizar tareas repetitivas.",
        "GSheetsETL": "Pipeline ETL para Google Sheets con automatización de extracción, transformación y carga de datos.",
        "Donotavio": "Repositorio de perfil personal con automatizaciones y configuraciones.",
        "curr-don": "Sitio web ejecutivo personal con integración automática de datos de GitHub y LinkedIn.",
    }
}


def update_i18n_file(lang_code, translations):
    """Atualiza arquivo i18n com traduções de projetos"""
    i18n_path = Path("assets/i18n") / f"{lang_code}.json"
    
    if not i18n_path.exists():
        print(f"⚠️  Arquivo não encontrado: {i18n_path}")
        return
    
    with i18n_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    if "projects" not in data:
        data["projects"] = {}
    
    if "descriptions" not in data["projects"]:
        data["projects"]["descriptions"] = {}
    
    # Atualizar apenas traduções que existem
    for project_name, description in translations.items():
        data["projects"]["descriptions"][project_name] = description
    
    with i18n_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ {lang_code}: {len(translations)} traduções atualizadas")


def main():
    """Atualiza traduções de projetos em todos os idiomas"""
    print("🌐 Atualizando traduções de projetos...")
    
    for lang_code, translations in TRANSLATIONS.items():
        update_i18n_file(lang_code, translations)
    
    print("\n🎉 Traduções atualizadas com sucesso!")


if __name__ == "__main__":
    main()
