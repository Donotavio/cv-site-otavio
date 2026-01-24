# 🤖 Automações do Site

## Visão Geral

O site possui automações que atualizam dados automaticamente via GitHub Actions toda segunda-feira às 6h UTC.

## Scripts Disponíveis

### 1. `fetch_github_data.py` / `fetch_github_data_local.py`
Busca dados da API do GitHub:
- Repositórios públicos e stars
- Top 6 linguagens de programação
- Top 6 projetos (por stars)
- Commits recentes

**Variáveis de ambiente:**
- `GITHUB_USERNAME` (obrigatória): usuário do GitHub
- `GITHUB_TOKEN` (opcional): token para aumentar rate limit

**Saída:** `assets/data/github_activity.json`

### 2. `fetch_linkedin_data_enhanced.py`
Busca dados do perfil LinkedIn com fallback automático:
- Perfil (nome, headline, localização, sobre)
- Experiência profissional
- Educação

**Variáveis de ambiente:**
- `LINKEDIN_PROFILE_URL` (obrigatória): URL do perfil
- `LINKEDIN_SESSION_COOKIE` (opcional): cookie `li_at` para dados completos
- `USE_LINKEDIN_FALLBACK` (padrão: "true"): usar dados fallback se scraping falhar

**Saída:** 
- `assets/data/linkedin_profile.json`
- `assets/data/linkedin_recommendations.json`

**Fallback de Dados:**
Quando o LinkedIn bloqueia scraping (sem cookie de sessão), o script usa dados fallback pré-configurados no próprio arquivo. Você pode editar esses dados em:
```python
FALLBACK_DATA = {
    "profile": { ... },
    "experience": [ ... ],
    "education": [ ... ]
}
```

### 3. `translate_projects.py` ✨ NOVO
Atualiza traduções de descrições de projetos automaticamente:
- Lê traduções hard-coded do próprio script
- Atualiza arquivos `assets/i18n/*.json`
- Suporta pt-BR, en-US, es-ES

**Como adicionar novas traduções:**
Edite o dicionário `TRANSLATIONS` no arquivo:
```python
TRANSLATIONS = {
    "pt-BR": {
        "nome-do-projeto": "Descrição em português",
    },
    "en-US": {
        "nome-do-projeto": "Description in English",
    },
    "es-ES": {
        "nome-do-projeto": "Descripción en español",
    }
}
```

**Saída:** Atualiza arquivos em `assets/i18n/`

### 4. `build_profile_data.py`
Consolida todos os dados em um único arquivo:
- Mescla dados do LinkedIn e GitHub
- Aplica fallbacks para campos vazios
- Gera timestamp de atualização

**Saída:** `assets/data/profile.json`

## Workflow CI/CD

**Arquivo:** `.github/workflows/update-profile.yml`

**Trigger:**
- Agendado: toda segunda-feira às 6h UTC
- Manual: via "Actions" > "Update profile data" > "Run workflow"

**Passos:**
1. Checkout do repositório
2. Setup Python 3.11
3. Instalar dependências (`requests`, `beautifulsoup4`)
4. Executar `fetch_github_data.py`
5. Executar `fetch_linkedin_data_enhanced.py`
6. Executar `translate_projects.py` ✨ NOVO
7. Executar `build_profile_data.py`
8. Commit e push das mudanças

**Secrets necessários:**
- `GITHUB_TOKEN` (automático)
- `LINKEDIN_SESSION_COOKIE` (opcional - configure em Settings > Secrets)

## Executar Localmente

```bash
# 1. Dados do GitHub
export GITHUB_USERNAME=donotavio
python3 scripts/fetch_github_data_local.py

# 2. Dados do LinkedIn (com fallback)
export LINKEDIN_PROFILE_URL=https://linkedin.com/in/donotavio/
export USE_LINKEDIN_FALLBACK=true
python3 scripts/fetch_linkedin_data_enhanced.py

# 3. Traduções automáticas
python3 scripts/translate_projects.py

# 4. Consolidar dados
python3 scripts/build_profile_data.py
```

## Obter Cookie do LinkedIn

Para dados completos do LinkedIn, você precisa do cookie de sessão:

1. Faça login no LinkedIn
2. Abra DevTools (F12)
3. Vá em Application > Cookies > https://www.linkedin.com
4. Copie o valor de `li_at`
5. Adicione como secret no GitHub: `LINKEDIN_SESSION_COOKIE`

**⚠️ Importante:** 
- Nunca commite o cookie no repositório
- O cookie expira periodicamente (renovar quando necessário)
- Sem o cookie, o script usa dados fallback automaticamente

## Traduções Automáticas

As traduções de projetos agora são **automáticas** no CI:

1. Script `translate_projects.py` roda após buscar dados do GitHub
2. Atualiza `assets/i18n/*.json` com descrições traduzidas
3. Commit inclui tanto dados quanto traduções

**Para adicionar traduções de novos projetos:**
1. Edite `scripts/translate_projects.py`
2. Adicione entradas no dicionário `TRANSLATIONS`
3. Execute localmente para testar
4. Commit - o CI aplicará nas próximas execuções

## Arquivos Gerados

```
assets/data/
├── github_activity.json       # Dados brutos do GitHub
├── linkedin_profile.json      # Dados brutos do LinkedIn
├── linkedin_recommendations.json
└── profile.json              # Dados consolidados (usado pelo site)

assets/i18n/
├── pt-BR.json                # Inclui traduções de projetos
├── en-US.json
└── es-ES.json
```

## Debugging

**Ver logs de execução do CI:**
- GitHub > Actions > "Update profile data" > último run

**Testar localmente:**
```bash
# Logs detalhados no navegador
1. Abra http://localhost:4000
2. DevTools (F12) > Console
3. Veja logs: 🚀 📡 ✅ ❌
```

**Problemas comuns:**
- LinkedIn retorna vazio → Cookie expirou ou scraping bloqueado (fallback ativo)
- Traduções não atualizam → Verificar `translate_projects.py` rodou no CI
- GitHub rate limit → Adicionar `GITHUB_TOKEN` nos secrets

## Manutenção

**Atualizar dados de fallback do LinkedIn:**
Edite `scripts/fetch_linkedin_data_enhanced.py` > `FALLBACK_DATA`

**Adicionar novo idioma:**
1. Criar `assets/i18n/[lang].json`
2. Adicionar no dicionário `TRANSLATIONS` do `translate_projects.py`
3. Atualizar `assets/js/i18n.js` com novo idioma

**Modificar frequência do CI:**
Edite `.github/workflows/update-profile.yml` > `schedule` > `cron`
