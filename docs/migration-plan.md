# Plano de Migração — Redesign cv-site-otavio

> **Status:** ✅ **GATE 0 aprovado.** Decisões travadas (ver §0.1). Próximo passo: Phase 1 (direção de arte) → GATE 1.
> Documento produzido na Phase 0 (auditoria).

## 0.1 Decisões do GATE 0 (travadas)

| # | Decisão | Escolha |
|---|---|---|
| D1 | Stack | **Astro** |
| D2 | i18n | **Rotas estáticas** `/`, `/en/`, `/es/` |
| D3 | Limpeza de cruft | **Revisar item a item** antes de apagar (sem remoção em lote) |
| D4 | ROI calculator | **Aposentar** (remover include + JS + CSS + chaves i18n) |

---

## 0. Resumo executivo

O site hoje é Jekyll + JS vanilla, com um pipeline Python → JSON → GitHub Actions
que atualiza o conteúdo diariamente. A auditoria confirma que a **camada de dados é
totalmente desacoplada da apresentação**: todos os scripts escrevem em
`assets/data/*.json` e `assets/i18n/*.json` (caminhos relativos à raiz do repo) e o
Action faz commit exatamente desses globs. Isso significa que **podemos trocar a
camada de apresentação sem tocar em uma linha da lógica de dados**, desde que esses
diretórios continuem existindo.

**Recomendação:** migrar para **Astro**, lendo os mesmos JSON em build time, com
**GSAP + Lenis** para motion. Risco para o pipeline: **baixo**. Risco principal e
real está no **deploy** (GitHub Pages deixa de buildar Jekyll nativamente e passa a
exigir um workflow de build Astro) — gerenciável e padrão.

### Correção importante de premissa

O kickoff pede para "matar o gradiente roxo `#667eea → #764ba2`". **Esse gradiente
não existe no código.** A auditoria de CSS não encontrou nenhuma ocorrência desses
hex. O visual atual é:

- Fundo navy quase-preto `--bg: #070c16`
- Acento azul→ciano `--primary: #3b82f6` → `--accent: #22d3ee`
- Único roxo: partículas do canvas do hero (`rgba(168,85,247,…)`)

Ou seja, o problema não é "gradiente roxo de template" — é o **look "dashboard SaaS
dark" genérico** (navy + glow azul/ciano + canvas de partículas + "badge soup"). O
mandato de "matar o template" continua válido, só muda o alvo. Isso é insumo direto
para a Phase 1.

---

## 1. Stack final recomendada

| Camada | Hoje | Proposto | Observação |
|---|---|---|---|
| Framework | Jekyll (Liquid) | **Astro** (estático) | HTML estático → ótimo p/ Lighthouse e a11y |
| Conteúdo | `assets/data/*.json` | **Os mesmos JSON**, via Content Layer (`file()` loader) + Zod | Zero mudança de path |
| i18n | Runtime client (`data-i18n-key` + fetch) | **Rotas estáticas por idioma** (build time) | Conteúdo visível sem JS, SEO por idioma |
| Motion (scroll) | CSS + IntersectionObserver + canvas | **GSAP ScrollTrigger** | Coreografia de scroll |
| Smooth scroll | nativo | **Lenis** (integrado ao `gsap.ticker`) | |
| Microinteração | vanilla | Islands Astro (vanilla ou React pontual) | Framer Motion permitido **só dentro de island** |
| Deploy | GitHub Pages (build Jekyll nativo) | GitHub Pages via **Action `actions/deploy-pages`** | Mudança obrigatória (ver §4) |

**[D1 — APROVADO] Astro.** Fallback (Jekyll + GSAP/Lenis) descartado.

---

## 2. Mapeamento JSON → Astro

A camada de dados tem **dois grupos**: arquivos auto-gerados pelo pipeline e arquivos
curados à mão. Astro lê todos em build time, sem fetch em runtime.

### 2.1 Grafo do pipeline (preservar intacto)

```
fetch_github_data.py              → assets/data/github_activity.json
fetch_linkedin_data_enhanced.py   → assets/data/linkedin_profile.json
                                  → assets/data/linkedin_recommendations.json
translate_projects.py             → atualiza assets/i18n/*.json (só projects.descriptions)
fetch_linkedin_articles.py        → assets/data/blog_articles.json
build_profile_data.py             → assets/data/profile.json   (consome os 3 acima)
translate_articles.js             → assets/data/blog_articles_{en-US,es-ES}.json
```

`build_profile_data.py` roda por último e **consolida** linkedin + github em
`profile.json`. Consequência prática: **o site só precisa ler os arquivos
"finais"** — os dois `linkedin_*.json` são intermediários já fundidos em
`profile.json` e não viram collection.

### 2.2 Collections / fontes de dados no Astro

| Fonte JSON | Auto? | Collection / módulo | Forma | Renderiza |
|---|---|---|---|---|
| `profile.json` | sim | `profile` (singleton import + Zod) | objeto: `profile`, `timeline[]`, `projects[]`, `recommendations[]` | hero, about, timeline, projects, recommendations |
| `github_activity.json` | sim | `github` (singleton, ~9k linhas, só build) | summary, top_languages[], contributions_calendar, activity_breakdown | seção stats (heatmap, radar, contadores) |
| `tech_stack.json` | **não (curado)** | `techStack` (`file()` + Zod) | `categories[].technologies[]` | seção tech-stack |
| `projects_extended.json` | **não (curado)** | `featuredProjects` (`file()` + Zod) | `featured_projects[]` | projetos em destaque |
| `blog_articles.json` (+ `_en-US`, `_es-ES`) | sim | `blog` por idioma | `articles[]`, `external_links` | seção blog + modal |
| `linkedin_profile.json` | sim | — (intermediário) | — | consumido só pelo pipeline |
| `linkedin_recommendations.json` | parcial | — (intermediário) | — | já fundido em `profile.json` |

**Estratégia técnica:** Content Layer (`file()` loader) com schemas **Zod** para os
arrays (timeline, projects, recommendations, techStack, featuredProjects, blog). Os
schemas servem de **rede de segurança contra drift de shape** do pipeline — se o
Python mudar uma chave, o build falha alto em vez de renderizar quebrado. Os
singletons (`profile.json` header, `github_activity.json`) entram por import direto
validado. Tudo continua morando em `assets/data/` — **nenhum path muda**.

> Conteúdo curado à mão (`tech_stack.json`, `projects_extended.json`) e os ~182
> textos de i18n hand-maintained NÃO são tocados pelo pipeline diário (exceto
> `projects.descriptions`, escrito por `translate_projects.py`). Documentado na skill
> `content-i18n`.

---

## 3. Estratégia de i18n

### 3.1 Hoje
Runtime no cliente: `i18n.js` faz fetch de `assets/i18n/{lang}.json`, resolve chaves
aninhadas (`section.key`) e popula `data-i18n-key` via `textContent`. Idioma em
`localStorage.preferredLanguage`, default `pt-BR`, troca sem reload.
**Problema:** sem JS, o conteúdo traduzido não aparece; e não há URL por idioma (ruim
para SEO).

### 3.2 Proposto — rotas estáticas por idioma
Astro pré-renderiza **três versões do site** em build time, lendo `assets/i18n/*.json`:

```
/                 → pt-BR (default)
/en/              → en-US
/es/              → es-ES
```

- Strings injetadas como **props nos componentes** em build — sem engine de i18n em
  runtime, sem fetch, conteúdo 100% presente **sem JavaScript** nos três idiomas.
- O language switcher vira `<a href>` real (funciona sem JS); um script mínimo de
  realce lembra a preferência (`localStorage`) e faz redirect na primeira visita.
- `<html lang>` correto por rota (hoje é estático em `pt-BR` — ganho de a11y/SEO).
- Paridade de chaves hoje é **perfeita** (auditoria: chaves idênticas nos 3 arquivos).
  A skill `content-i18n` adiciona um check de paridade no build.

**[D2 — APROVADO] Rotas estáticas** `/`, `/en/`, `/es/`. Swap em runtime descartado.

> Pequena melhoria pendente (não bloqueante): `hero.expertise_value` e alguns valores
> de `impact.*` estão idênticos nos 3 idiomas; alguns deveriam ser localizados.
> Tratado na Phase de conteúdo, não aqui.

---

## 4. Deploy — o risco real

Hoje o GitHub Pages **builda Jekyll nativamente**; o Action diário só faz commit dos
JSON e o Pages reconstrói sozinho. Astro precisa de um **passo de build próprio**.

### Plano
1. Workflow novo `deploy.yml`: em `push` na `main`, roda `astro build` e publica com
   `actions/upload-pages-artifact` + `actions/deploy-pages`.
2. **Coordenação com o pipeline:** o Action diário (`update-profile.yml`) faz commit
   dos JSON na `main` → esse commit dispara o `deploy.yml` → site rebuilda com dados
   frescos. (Hoje o rebuild era automático via Jekyll; agora é explícito.) Garantir
   que o commit do bot não seja ignorado pelo trigger (sem `paths:` restritivo
   excludente, ou disparar `deploy` no fim do `update-profile`).
3. `astro.config`: `site: 'https://donotavio.github.io'`, `base: '/cv-site-otavio'`.
   Links internos via `import.meta.env.BASE_URL` / helpers do Astro (resolve o
   problema atual de baseurl em paths de fetch — que somem, viram import em build).
4. Settings do repo: Pages → source = **GitHub Actions** (não mais "branch").

### Riscos e mitigação
| Risco | Severidade | Mitigação |
|---|---|---|
| Deploy Astro quebra publicação | Média | Cutover só no fim; `main` segue Jekyll até a virada |
| Commit do bot não redispara build | Média | Testar trigger; encadear deploy no fim do `update-profile.yml` |
| `base`/links quebrados no subpath | Baixa | Usar helpers do Astro; checar em preview antes do cutover |
| Schema do JSON muda e quebra o build | Baixa | Zod falha alto e cedo; check no CI |
| Pipeline Python afetado | **Muito baixa** | Não tocamos em scripts nem em paths |

---

## 5. Rollback

- Todo o redesign acontece na branch **`redesign/astro-gsap`**. A `main` permanece o
  site Jekyll funcional até o cutover.
- Cutover = um único PR + mudar a fonte do Pages para "GitHub Actions". Se algo der
  errado: reverter o PR e voltar a fonte do Pages para a branch Jekyll → site antigo
  volta no ar, pipeline nunca parou.
- Como **não alteramos os scripts nem os paths de saída**, o pipeline diário continua
  produzindo os mesmos JSON independentemente de qual front-end está publicado.

---

## 6. O que preservar (a todo custo)

- `scripts/*` (lógica de dados) — **intocado**.
- `.github/workflows/update-profile.yml` — preservado; só ganha (talvez) um gatilho
  de deploy no fim.
- `assets/data/*.json` e `assets/i18n/*.json` — **mesmos paths**.
- Conteúdo das 11 seções (hero, about, impact, timeline, skills, tech-stack, blog,
  projects, recommendations, stats, contact) + footer — zero regressão.
- Paridade trilíngue pt/en/es (hoje perfeita).
- Assets em `assets/img`, `assets/cv` (PDFs por idioma), favicons, webmanifest.

## 7. O que remover / limpar

| Item | Ação | Motivo |
|---|---|---|
| `debug_linkedin.html` (348 KB) | **remover** | Snapshot de scraping, artefato de debug |
| `linkedin_raw.html` (62 B) | **remover** | Placeholder morto |
| `scripts/fetch_linkedin_data.py` | **remover** | Superado por `_enhanced` |
| `scripts/test_linkedin_debug.py` | **remover** | Harness de debug, fora do CI |
| `scripts/fetch_linkedin_articles.py` | **manter** | É o passo 4 do workflow (gera `blog_articles.json`) |
| `scripts/fetch_github_data_local.py` | **manter** | Conveniência de dev local |
| `netlify.toml`, `_headers` | **remover** | Sobra de Netlify; Pages é canônico e ignora ambos |
| `PUBLICACAO.md` | **remover/atualizar** | Aponta repo antigo `curr-don`, info de deploy obsoleta |
| `SECURITY_REPORT.md`, `VALIDACAO_COMPLETA.md` | **arquivar** em `docs/audits/` | Auditorias históricas |
| `COMO_ADICIONAR_FOTOS.md` | **consolidar** em AUTOMATIONS.md | Vago/curto |
| "Badge soup" (~6 classes de pill) | **consolidar** em 1–2 (design-system) | `meta-pill`, `about-tag`, `tech-badge`, `skill-tag`, `blog-tag`, `blog-featured-badge` |
| Canvas de partículas roxas do hero | **repensar na Phase 1** | Marca registrada do look "template" |
| ~65% do CSS atual (layout/component one-off) | **re-autorar** | Só ~35% é material de design-system |

**[D3 — APROVADO] Revisar item a item.** Nada é apagado em lote. Quando a limpeza
acontecer (Phase 2/3), cada item da tabela acima é apresentado para OK individual.

---

## 8. Interatividade → Islands (Phase 3/4)

| Comportamento | Hoje | Astro | Tipo |
|---|---|---|---|
| Tema claro/escuro | `theme.js` + localStorage | Island + script inline no `<head>` (anti-flash) | interatividade real |
| Language switcher | `.lang-btn` + re-render | `<a href>` + realce mínimo | quase-estático |
| Timeline (expand/modal) | `timeline.js` | CSS-first + island pequeno p/ expandir | interatividade real |
| Modal de artigo (blog) | `content.js` | `<dialog>` nativo ou island | interatividade real |
| ROI calculator | `roi-calculator.js` | island (se mantido) | **ver [DECISÃO 4]** |
| Hero background (canvas) | `hero-background.js` | island decorativo, OFF em reduced-motion | decoração |
| Reveal no scroll | IntersectionObserver | GSAP ScrollTrigger (helper nomeado) | decoração |
| Scroll progress / smooth | `scroll.js` | Lenis + barra via CSS | decoração |

**[D4 — APROVADO] Aposentar.** Remover include + JS + CSS + chaves i18n do ROI
(sujeito ao fluxo de "revisar item a item" do D3 na hora de apagar).

---

## 9. Vocabulário de motion (a definir na Phase 1, teto de 5 padrões)

Reserva-se aqui o slot — os padrões concretos saem da direção escolhida. Candidatos:
(1) hero text reveal, (2) reveal-on-scroll por seção, (3) hover lift em cards,
(4) transição de troca de idioma/rota, (5) parallax sutil. Helpers nomeados em
`web-motion`, nunca copy-paste. Reduced-motion desliga tudo que for decorativo.

---

## 10. Próximos passos após aprovação

1. **GATE 0 (agora):** aprovar stack (D1), i18n (D2), limpeza (D3), ROI (D4).
2. **Phase 1 — art direction:** KB de gosto + 2–3 direções → **GATE 1**.
3. **Phase 2 — scaffolding:** skills, agentes, KBs, `DESIGN.md`, tokens.
4. **Phase 3 — base:** Astro + collections + i18n por rota + GSAP/Lenis + deploy.
5. **Phases 4–6:** seção a seção, hardening a11y/perf, deploy e verificação do
   pipeline em produção.
