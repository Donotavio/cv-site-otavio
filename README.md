# 🚀 Portfolio Profissional | Otávio Henrique da Silva Ribeiro

<div align="center">

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live-success?style=for-the-badge&logo=github)](https://donotavio.github.io/cv-site-otavio/)
[![Jekyll](https://img.shields.io/badge/Jekyll-4.x-CC0000?style=for-the-badge&logo=jekyll&logoColor=white)](https://jekyllrb.com/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Made with Love](https://img.shields.io/badge/Made%20with-♥-red?style=for-the-badge)](https://github.com/Donotavio)

**Portfolio moderno e responsivo de Engenharia de Dados e Liderança**

[🌐 Ver Site](https://donotavio.github.io/cv-site-otavio/) • [📝 Documentação](AGENTS.md) • [🤖 Automações](AUTOMATIONS.md)

![Preview](https://img.shields.io/badge/Status-Online-brightgreen?style=flat-square)
![Build](https://img.shields.io/badge/Build-Passing-success?style=flat-square)
![Responsive](https://img.shields.io/badge/Responsive-Yes-blue?style=flat-square)

</div>

---

## ✨ Características

### 🎨 **Design Moderno**
- Interface limpa e profissional
- Animações suaves e interativas
- Hero section com background canvas dinâmico
- Tema claro/escuro (em breve)
- Timeline interativa de carreira

### 🌍 **Multilíngue (i18n)**
- 🇧🇷 **Português** (Padrão)
- 🇺🇸 **English**
- 🇪🇸 **Español**
- Troca instantânea sem reload
- URLs e conteúdo dinâmico traduzidos

### 📱 **100% Responsivo**
- Mobile First Design
- Breakpoints: 375px, 768px, 1920px
- Touch-friendly interactions
- Otimizado para todos os dispositivos

### ⚡ **Performance**
- Zero dependências JavaScript externas
- CSS otimizado e modular
- Lazy loading de imagens
- Caching inteligente
- Lighthouse Score: 95+

### ♿ **Acessibilidade**
- WCAG AA Compliant
- Estrutura semântica HTML5
- ARIA labels dinâmicos
- Navegação por teclado completa
- Screen reader friendly

---

## 🛠️ Stack Tecnológica

### Frontend
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=flat&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E?style=flat&logo=javascript&logoColor=black)

### Build & Deploy
![Jekyll](https://img.shields.io/badge/Jekyll-CC0000?style=flat&logo=jekyll&logoColor=white)
![Ruby](https://img.shields.io/badge/Ruby-CC342D?style=flat&logo=ruby&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat&logo=github-actions&logoColor=white)
![GitHub Pages](https://img.shields.io/badge/GitHub_Pages-222222?style=flat&logo=github&logoColor=white)

### Automação
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![GitHub API](https://img.shields.io/badge/GitHub_API-181717?style=flat&logo=github&logoColor=white)
![LinkedIn API](https://img.shields.io/badge/LinkedIn_API-0A66C2?style=flat&logo=linkedin&logoColor=white)

---

## 📂 Estrutura do Projeto

```
cv-site-otavio/
├── 📄 _config.yml              # Configuração Jekyll
├── 📁 _layouts/                # Templates de página
│   ├── default.html            # Layout base
│   └── home.html               # Layout homepage
├── 📁 _includes/               # Componentes reutilizáveis
│   ├── header.html             # Cabeçalho
│   ├── footer.html             # Rodapé
│   ├── navbar.html             # Navegação
│   ├── timeline.html           # Timeline interativa
│   └── language_switcher.html  # Seletor de idioma
├── 📁 assets/
│   ├── 📁 css/                 # Estilos modulares
│   │   ├── main.css            # Estilos principais
│   │   ├── animations.css      # Animações
│   │   ├── timeline.css        # Timeline
│   │   ├── hero-background.css # Hero canvas
│   │   └── impact-section.css  # Seção de impacto
│   ├── 📁 js/                  # JavaScript modular
│   │   ├── main.js             # Orquestrador
│   │   ├── i18n.js             # Internacionalização
│   │   ├── timeline.js         # Timeline interativa
│   │   ├── animations.js       # Animações
│   │   ├── scroll.js           # Scroll effects
│   │   ├── content.js          # Renderização dinâmica
│   │   └── hero-background.js  # Canvas background
│   ├── 📁 data/                # Dados JSON
│   │   ├── profile.json        # Dados do perfil
│   │   ├── github_activity.json # Atividade GitHub
│   │   ├── linkedin_profile.json # Perfil LinkedIn
│   │   ├── projects_extended.json # Projetos
│   │   ├── tech_stack.json     # Stack de tecnologias
│   │   └── blog_articles.json  # Artigos
│   ├── 📁 i18n/                # Traduções
│   │   ├── pt-BR.json          # Português
│   │   ├── en-US.json          # Inglês
│   │   └── es-ES.json          # Espanhol
│   └── 📁 img/                 # Imagens e ícones
├── 📁 scripts/                 # Scripts Python
│   ├── fetch_github_data.py    # Buscar dados GitHub
│   ├── fetch_linkedin_data.py  # Buscar dados LinkedIn
│   ├── build_profile_data.py   # Build profile JSON
│   └── translate_projects.py   # Traduzir projetos
├── 📁 .github/workflows/       # GitHub Actions
│   └── update-profile.yml      # Atualização automática
└── 📄 index.html               # Página principal
```

---

## 🚀 Quick Start

### Pré-requisitos

- **Ruby** 2.7+ ([Instalar Ruby](https://www.ruby-lang.org/))
- **Bundler** (`gem install bundler`)
- **Git**

### Instalação Local

```bash
# 1. Clone o repositório
git clone https://github.com/Donotavio/cv-site-otavio.git
cd cv-site-otavio

# 2. Instale dependências Jekyll
bundle install

# 3. Inicie o servidor local
bundle exec jekyll serve --livereload

# 4. Acesse no navegador
# http://localhost:4000
```

### Build de Produção

```bash
# Gerar site estático
bundle exec jekyll build

# Saída em: _site/
```

---

## 🔄 Automação & CI/CD

### GitHub Actions Workflow

**Atualização Automática de Dados**

- **Trigger:** Diariamente às 00:00 UTC ou manual
- **Jobs:**
  - Buscar atividade do GitHub
  - Buscar dados do LinkedIn
  - Atualizar traduções
  - Commit automático

```yaml
# .github/workflows/update-profile.yml
name: Update Profile Data
on:
  schedule:
    - cron: '0 0 * * *'  # Diário
  workflow_dispatch:      # Manual
```

### Scripts Python

```bash
# Atualizar dados do GitHub
python3 scripts/fetch_github_data.py

# Atualizar dados do LinkedIn
python3 scripts/fetch_linkedin_data.py

# Gerar profile.json
python3 scripts/build_profile_data.py

# Traduzir projetos
python3 scripts/translate_projects.py
```

**Variáveis de Ambiente:**
```bash
export GITHUB_USERNAME="seu-usuario"
export GITHUB_TOKEN="ghp_seu_token"
export LINKEDIN_SESSION_COOKIE="seu_cookie"
```

---

## 🎨 Customização

### Atualizar Informações Pessoais

Edite os arquivos JSON em `assets/data/`:

```json
// assets/data/profile.json
{
  "name": "Seu Nome",
  "title": "Seu Título",
  "bio": "Sua Bio",
  "timeline": [...],
  "projects": [...]
}
```

### Adicionar Idiomas

1. Crie arquivo em `assets/i18n/xx-XX.json`
2. Adicione ao `i18n.js`:

```javascript
const supportedLanguages = {
  'pt-BR': 'Português',
  'en-US': 'English',
  'es-ES': 'Español',
  'xx-XX': 'Novo Idioma'  // Adicione aqui
};
```

### Personalizar Cores

Edite variáveis CSS em `assets/css/main.css`:

```css
:root {
  --primary: #667eea;
  --secondary: #764ba2;
  --accent: #f093fb;
  /* ... */
}
```

---

## 📊 Validação & Qualidade

### Relatórios de Validação

- ✅ **[REVISAO_COMPLETA.md](REVISAO_COMPLETA.md)** - Code review completo
- ✅ **[VALIDACAO_DEVTOOLS.md](VALIDACAO_DEVTOOLS.md)** - Validação runtime
- ✅ **[PUBLICACAO.md](PUBLICACAO.md)** - Detalhes da publicação

### Métricas

| Métrica | Score |
|---------|-------|
| **Funcionalidade** | ✅ 100% |
| **Performance** | ✅ 95% |
| **Responsividade** | ✅ 100% |
| **Acessibilidade** | ✅ 100% (WCAG AA) |
| **SEO** | ✅ 95% |

---

## 📸 Screenshots

### Desktop
![Desktop View](assets/img/screenshots/desktop-preview.png)

### Mobile
<img src="assets/img/screenshots/mobile-preview.png" width="300" alt="Mobile View">

### Tablet
<img src="assets/img/screenshots/tablet-preview.png" width="500" alt="Tablet View">

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Siga o fluxo:

1. **Fork** o projeto
2. **Clone** seu fork: `git clone https://github.com/seu-usuario/cv-site-otavio.git`
3. **Branch** para feature: `git checkout -b feature/nova-feature`
4. **Commit** com Conventional Commits: `git commit -m "feat: adicionar nova feature"`
5. **Push**: `git push origin feature/nova-feature`
6. **Pull Request** para `main`

### Conventional Commits

```
feat: nova funcionalidade
fix: correção de bug
docs: documentação
style: formatação
refactor: refatoração
test: testes
chore: tarefas de manutenção
```

---

## 📝 Documentação Adicional

- 📖 **[AGENTS.md](AGENTS.md)** - Guia completo de desenvolvimento
- 🤖 **[AUTOMATIONS.md](AUTOMATIONS.md)** - Workflows e automações
- 📷 **[COMO_ADICIONAR_FOTOS.md](COMO_ADICIONAR_FOTOS.md)** - Guia de imagens

---

## 🐛 Problemas Conhecidos

### Recursos Externos (CORB)
- **Issue:** Warnings CORB de ícones externos (Delta Lake, dbt, etc.)
- **Impacto:** Nenhum (não afeta funcionalidade)
- **Solução:** Hospedar ícones localmente (opcional)

### Favicon 404
- **Issue:** `favicon.ico` não encontrado
- **Impacto:** Nenhum (navegador usa `favicon.svg`)
- **Solução:** Adicionar `favicon.ico` como backup (opcional)

---

## 📄 Licença

Este projeto está sob a licença **MIT**. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

## 👤 Autor

<div align="center">

**Otávio Henrique da Silva Ribeiro**

Gerente de Engenharia de Dados | Databricks Specialist

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/donotavio)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/donotavio)
[![Email](https://img.shields.io/badge/Email-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:ribeitemp@gmail.com)

</div>

---

## ⭐ Agradecimentos

Obrigado por visitar este projeto! Se gostou, considere dar uma ⭐ no repositório.

---

<div align="center">

**Construído com ❤️ usando Jekyll, HTML5, CSS3 e JavaScript puro**

![Visitors](https://visitor-badge.laobi.icu/badge?page_id=donotavio.cv-site-otavio)
![Last Commit](https://img.shields.io/github/last-commit/donotavio/cv-site-otavio?style=flat-square)
![Repo Size](https://img.shields.io/github/repo-size/donotavio/cv-site-otavio?style=flat-square)

</div>
