# Skill: content-i18n

Como o conteúdo é estruturado a partir dos JSON e como manter paridade entre pt-BR / en-US / es-ES no cv-site-otavio.

---

## Arquitetura de dados

```
assets/data/          ← gerado pelo pipeline Python (GitHub Actions diário)
  profile.json              ← timeline, projetos, recomendações (estrutura)
  github_activity.json      ← heatmap, stats, repositórios
  linkedin_profile.json     ← perfil e experiência LinkedIn
  linkedin_recommendations.json ← dados dos autores de recomendações
  projects_extended.json    ← 3 projetos curados (impacto, stack, desafios)
  tech_stack.json           ← categorias e tecnologias com nível e logo
  blog_articles.json        ← artigos LinkedIn (atualmente vazio)
  blog_articles_en-US.json  ← artigos traduzidos
  blog_articles_es-ES.json  ← artigos traduzidos

assets/i18n/          ← strings de UI e texto de conteúdo (pt-BR é a fonte)
  pt-BR.json
  en-US.json
  es-ES.json
```

**Regra de separação:**
- **Dados estruturais** (nomes, datas, URLs, caminhos de imagem, números) → `assets/data/*.json`
- **Texto exibível ao usuário** (rótulos, descrições, títulos de seção, texto de recomendações) → `assets/i18n/*.json`
- Nunca misturar: dados dinâmicos do pipeline não vão nos JSON de i18n; texto de UI não vai nos JSON de dados.

---

## Namespaces de i18n

Cada namespace corresponde a uma seção ou conjunto de componentes:

```
nav.*               Navegação principal (10 chaves)
hero.*              Seção hero (13 chaves)
about.*             Sobre (9 chaves)
impact.*            Métricas de impacto (8 chaves)
timeline.*          Timeline de experiência (5 chaves)
skills.*            Skills section (9 chaves + objeto items.*)
projects.*          Grade de projetos do GitHub (7 chaves + descriptions.*)
featured_projects.* Projetos curados (5 chaves)
tech_stack.*        Grade de tecnologias (3 chaves)
blog.*              Blog/artigos (5 chaves)
recommendations.*   Recomendações (3 chaves + items.{id}.{text,date,relationship})
stats.*             GitHub stats e heatmap (10+ chaves)
contact.*           Seção de contato (8+ chaves)
roi_calculator.*    Calculadora ROI (10+ chaves)
footer.*            Rodapé (2 chaves)
```

**Caso especial — recomendações:**
O texto de cada recomendação fica no i18n, não nos dados. O `profile.json` só tem `id`, `author`, `role`, `company`, `linkedin`, `photo`. O texto é resolvido via:
```
recommendations.items.{id}.text
recommendations.items.{id}.date
recommendations.items.{id}.relationship
```

---

## Sistema i18n em runtime

O sistema é completamente client-side — não há i18n no build do Astro.

### Como funciona (`assets/js/i18n.js`)

1. Detecta idioma: `localStorage['portfolio-lang']` → `navigator.languages` → default `pt-BR`
2. Faz `fetch('/cv-site-otavio/assets/i18n/{lang}.json')`
3. Percorre todos os `[data-i18n-key]` no DOM e aplica `element.textContent = value`
4. Percorre todos os `[data-i18n-aria]` e aplica `element.setAttribute('aria-label', value)`
5. Atualiza `document.documentElement.lang` e `document.title`
6. Faz patch no `href` do `#cv-download` com o caminho correto do PDF
7. Emite `window.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang } }))`

### Acessar traduções em JS

```javascript
// window.i18n é exposto após i18n.js carregar
window.i18n.t('hero.role')         // → string traduzida
window.i18n.lang                   // → 'pt-BR' | 'en-US' | 'es-ES'
```

Para aguardar o i18n estar pronto antes de renderizar:
```javascript
window.addEventListener('languageChanged', () => {
  renderDynamicContent();
}, { once: true });

// Se já carregou (re-render ao trocar língua):
window.addEventListener('languageChanged', renderDynamicContent);
```

### Markup HTML

```html
<!-- Texto simples -->
<h2 data-i18n-key="timeline.title"></h2>

<!-- ARIA label -->
<button data-i18n-aria="timeline.close_modal" aria-label="">×</button>

<!-- Conteúdo que não usa i18n (dados do JSON) -->
<span class="company-name"><!-- preenchido por main.js --></span>
```

**Regra:** Todo texto visível ao usuário que não vem dos JSON de dados deve ter `data-i18n-key`. Nunca hardcodar strings de UI no HTML.

---

## Paridade de chaves entre idiomas

**pt-BR.json é a fonte da verdade.** Qualquer nova chave deve ser adicionada ao pt-BR primeiro, depois replicada para en-US e es-ES.

### Script de validação

```python
# scripts/validate_i18n.py
import json, sys
from pathlib import Path

def flatten(obj, prefix=''):
    keys = set()
    for k, v in obj.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= flatten(v, full)
        else:
            keys.add(full)
    return keys

base = Path('assets/i18n')
langs = ['pt-BR', 'en-US', 'es-ES']
data = {l: flatten(json.loads((base / f'{l}.json').read_text())) for l in langs}
reference = data['pt-BR']
errors = 0

for lang in langs[1:]:
    missing = reference - data[lang]
    extra   = data[lang] - reference
    if missing:
        print(f"FALTANDO em {lang}:")
        for k in sorted(missing): print(f"  - {k}")
        errors += 1
    if extra:
        print(f"EXTRA em {lang} (não existe em pt-BR):")
        for k in sorted(extra): print(f"  + {k}")
        errors += 1

if not errors:
    print("✓ Paridade de i18n validada para todos os idiomas.")
sys.exit(errors)
```

Rodar com: `python3 scripts/validate_i18n.py`

---

## Como adicionar uma nova chave de i18n

1. **Decidir o namespace.** Qual seção? Usar namespace existente, não criar novos sem necessidade.
2. **Adicionar ao pt-BR.json primeiro.**
3. **Adicionar ao en-US.json e es-ES.json** com a tradução correspondente.
4. **Rodar `python3 scripts/validate_i18n.py`** para confirmar paridade.
5. **Adicionar `data-i18n-key` no markup.**
6. **Verificar manualmente** em todas as três línguas no browser.

---

## Dados que vêm do pipeline (NÃO do i18n)

Os scripts Python geram dados frescos diariamente. Estes campos **nunca** entram nos arquivos i18n:

| Campo | Fonte | Quem consome |
|-------|-------|-------------|
| Nome, cargo, localização, resumo | `profile.json` | `main.js` |
| Empresa, período, highlights de experiência | `profile.json` | `main.js` / `timeline.js` |
| Logos de empresa | `profile.json` (caminhos) | `main.js` |
| Estatísticas GitHub (repos, stars, commits) | `github_activity.json` | `main.js` |
| Heatmap de contribuições | `github_activity.json` | `main.js` |
| Repositórios do GitHub | `github_activity.json` | `main.js` |
| Artigos de blog | `blog_articles.json` | `content.js` |
| Categorias e tech com logos | `tech_stack.json` | `content.js` |
| Projetos curados | `projects_extended.json` | `content.js` |
| Foto e dados dos autores de recomendações | `profile.json` | `main.js` |

---

## Dados que ficam no i18n (NÃO nos data JSONs)

| Campo | Namespace | Nota |
|-------|-----------|------|
| Texto completo de recomendações | `recommendations.items.{id}.text` | Texto longo, traduzível |
| Descrições de projetos do GitHub | `projects.descriptions.{name}` | `translate_projects.py` gera |
| Todos os rótulos de UI | vários | Qualquer texto de botão, título, label |
| Mensagens de estado (empty, loading) | vários | `blog.coming_soon`, `timeline.empty` etc. |

---

## Estrutura de dados dos JSON principais

### `profile.json`

```typescript
interface ProfileData {
  profile: {
    name: string;
    title: string;
    location: string;
    summary: string;
    updated_at: string;
  };
  timeline: Array<{
    role: string;
    company: string;
    period: string;        // e.g. "Jan 2025 - Presente"
    location: string;
    highlights: string[];
    description: string;
    skills: string;        // delimitado por " · "
    companyLogo: string;   // caminho absoluto com baseurl
    extraRole?: string;
    extraPeriod?: string;
    extraDescription?: string;
    companyUrl?: string;
  }>;
  projects: Array<{
    name: string;
    description: string;
    language: string;
    stars: number;
    url: string;
  }>;
  recommendations: Array<{
    id: string;            // chave para lookup em i18n
    author: string;
    role: string;
    company: string;
    linkedin: string;
    photo: string;         // caminho sem baseurl
  }>;
}
```

### `tech_stack.json`

```typescript
interface TechStackData {
  categories: Array<{
    name: string;
    icon: string;
    technologies: Array<{
      name: string;
      level: 'expert' | 'advanced' | 'intermediate';
      logo: string;        // caminho com baseurl
    }>;
  }>;
}
```

### `projects_extended.json`

```typescript
interface ProjectsExtendedData {
  featured_projects: Array<{
    id: string;
    name: string;
    category: string;
    year: number;
    impact_metrics: Record<string, string>;
    tech_stack: string[];
    diagram: string;
    challenges: string[];
    solutions: string[];
  }>;
}
```

---

## Convenção de caminhos de imagem

Os scripts Python geram caminhos com o baseurl embutido:

```
/cv-site-otavio/assets/img/profiles/companies/databricks.jpg
/cv-site-otavio/assets/img/logos/python.svg
```

No Astro, usar `import.meta.env.BASE_URL` para prefixar caminhos gerados em runtime:

```typescript
// Se o caminho já tem o baseurl (vindo de profile.json):
<img src={item.companyLogo} alt={item.company} />

// Se o caminho não tem baseurl (vindo de linkedin_recommendations.json → photo):
<img src={`${import.meta.env.BASE_URL}${item.photo}`} alt={item.author} />
```

---

## Checklist de i18n por componente

- [ ] Todo texto estático usa `data-i18n-key` (nenhuma string hardcoded em HTML)
- [ ] Todos os `aria-label` dinâmicos usam `data-i18n-aria`
- [ ] Conteúdo dinâmico (do JSON) acessa `window.i18n.t()` para rótulos
- [ ] Nova chave adicionada em pt-BR **e** en-US **e** es-ES
- [ ] `python3 scripts/validate_i18n.py` passa sem erros
- [ ] Testado manualmente nas 3 línguas (trocar via botões PT/EN/ES)
- [ ] `languageChanged` event escutado onde o componente re-renderiza texto
- [ ] Download de CV aponta para o PDF correto por idioma
