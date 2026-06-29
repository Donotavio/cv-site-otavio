# Phase 0 — Migration Plan: Jekyll → Astro (Conditional)

**Date:** June 28, 2026
**Status:** Ready for GATE 0 Review
**Decision Point:** Stack finalization before Phase 1 begins

---

## Executive Summary

**Recommendation: GO for Astro migration.**

Full codebase audit confirms Astro migration is the correct path. The critical finding that changes the risk calculus: **Jekyll never reads `assets/data/*.json` at build time.** All data is fetched client-side at runtime by `main.js` and `content.js`. This means the data pipeline is already stack-agnostic — moving to Astro does not affect the Python scripts, Actions workflow, or JSON files at all.

The "data sync between pipeline and build" risk (the main concern in earlier analysis) is a non-issue. The JSON files are served as static assets and fetched fresh by every browser visit, identical to today.

All four `.claude/agents/` were pre-written for Astro + GSAP + Lenis. The architectural decisions are already documented. Using Jekyll would mean rewriting the agents and losing that investment.

**Conditions for GO:**
- Python data pipeline continues unchanged (writes JSON only)
- GitHub Pages source switches to "GitHub Actions" (not branch)
- New `build-and-deploy.yml` workflow added; existing `update-profile.yml` unchanged
- `jekyll-stable` rollback branch created before any migration commit

**If migration fails at Phase 3:** Revert to `jekyll-stable` in ~30 minutes. GSAP + Lenis can be added to Jekyll as a same-day fallback.

---

## 1. Current State Analysis

### Architecture Overview

```
┌─ Data Layer (Python + GitHub Actions) ─────────────┐
│  GitHub API  → fetch_github_data.py                │
│  LinkedIn    → fetch_linkedin_data_enhanced.py     │
│                         ↓                          │
│  build_profile_data.py (merges all)                │
│                         ↓                          │
│  assets/data/*.json  (9 files, served as static)   │
└──────────────────────────────────────────────────────┘
                         ↓ (client-side fetch at runtime)
┌─ Presentation Layer (Jekyll, to be replaced) ───────┐
│  _config.yml → _layouts/ _includes/                │
│  assets/css/ (7 files, 6,187 lines)                │
│  assets/js/  (9 files, 2,483 lines, vanilla ES6)   │
│  assets/i18n/*.json  (3 locales, ~236 keys each)   │
│                         ↓                          │
│  index.html → _site/ → GitHub Pages                │
└──────────────────────────────────────────────────────┘
```

**Key insight:** The arrow between data layer and presentation layer is a runtime browser fetch, not a build-time dependency. Jekyll does not process the JSON files. This is why both Astro and Jekyll are equally valid from a data-pipeline perspective.

### Current Metrics (Baseline)

| Metric | Value | Target |
|--------|-------|--------|
| Lighthouse Performance | 95 | ≥ 95 |
| Lighthouse Accessibility | 100 | ≥ 95 |
| Lighthouse Best Practices | — | ≥ 90 |
| Lighthouse SEO | — | ≥ 90 |
| Build Time | ~2s | < 30s |
| Dependencies (JS) | 0 external | ≤ 2 (GSAP + Lenis only) |
| i18n Coverage | 3 languages | 3 languages |
| Data Freshness | Daily @ 06:00 UTC | Unchanged |

### Stack Inventory

**Build:** Jekyll 3.x via `github-pages` gem (frozen, Ruby-based)
**CSS:** 7 files, 6,187 lines, vanilla, CSS custom properties
**JS:** 9 files, 2,483 lines, vanilla ES6+, no module system (all global)
**i18n:** Runtime JS (`assets/js/i18n.js`), `data-i18n-key` attribute pattern
**Data:** 9 JSON files in `assets/data/`, fetched client-side
**Deploy:** GitHub Pages, native Jekyll auto-build on push

---

## 2. What Must Be Preserved

| Item | Location | How to preserve |
|------|----------|-----------------|
| Python data pipeline | `scripts/*.py` | Zero changes needed |
| JSON data files | `assets/data/*.json` | Stay at same paths |
| i18n JSON + keys | `assets/i18n/*.json` | Stay at same paths |
| GitHub Actions workflow | `.github/workflows/update-profile.yml` | Zero changes needed |
| All images and CVs | `assets/img/`, `assets/cv/` | Copy to `public/` in Astro |
| i18n JS runtime | `assets/js/i18n.js` | Port as-is to Astro |
| Tech logos | `assets/img/logos/` | Copy to `public/` in Astro |
| Company/people photos | `assets/img/profiles/` | Copy to `public/` in Astro |
| PDF CVs (3 languages) | `assets/cv/` | Copy to `public/` in Astro |
| baseurl: `/cv-site-otavio` | `_config.yml` | Set `base: '/cv-site-otavio'` in `astro.config.mjs` |

---

## 3. Noise Files to Remove

Remove these before Phase 1 to reduce repo size and eliminate misleading files.

| File | Size | Reason |
|------|------|--------|
| `debug_linkedin.html` | ~348 KB | LinkedIn scraper debug dump. Sensitive, never linked. |
| `linkedin_raw.html` | ~75 B | Empty placeholder from scraper testing. |
| `netlify.toml` | Small | Netlify-specific. Site deploys to GitHub Pages. |
| `_headers` | Small | Netlify-specific headers. Not served by GitHub Pages. |
| `scripts/test_linkedin_debug.py` | Small | Debug script not in production pipeline. |
| `scripts/fetch_linkedin_data_local.py` | Small | Deprecated local dev variant. |
| `scripts/fetch_github_data_local.py` | Small | Deprecated local dev variant. |
| `.DS_Store` | Small | macOS artifact. Add to `.gitignore`. |
| `scripts/__pycache__/` | Compiled | Add `scripts/__pycache__/` to `.gitignore`. |

---

## 4. Stack Decision

**Decision: Astro 4.x + GSAP 3.x + Lenis 1.x**

| Criterion | Astro | Jekyll + GSAP |
|-----------|-------|---------------|
| Data pipeline risk | None (client-side fetch unchanged) | None |
| i18n system | Preserve exact runtime JS | Preserve exact runtime JS |
| Motion library integration | Native ESM imports | Global window scope injection |
| TypeScript & content schemas | Yes | No |
| Agent compatibility | All 4 agents pre-written for Astro | Would require rewriting |
| GitHub Pages deploy | Custom Actions workflow | Native (auto-build) |
| Build system | Modern Vite-based | Frozen Jekyll 3.x/Ruby |
| Code organization | ESM modules, component scoping | Global scope congestion |
| Lighthouse risk | Neutral to positive | Neutral |

**Deciding factors:**

1. All four `.claude/agents/` are pre-written specifically for Astro. Using Jekyll means rewriting them.
2. Data layer is already decoupled (client-side fetch). Stack change has zero impact on the pipeline.
3. GSAP + Lenis integrate cleanly as ESM imports in Astro; in Jekyll they require `window` globals on top of an already-global-congested codebase.
4. Astro's `base` config resolves the baseurl problem systematically.

---

## 5. Data Pipeline Integration

### The Key Finding

The existing migration plan draft described a "rebuild on data change" problem. **This problem does not exist.**

After full audit: Jekyll never reads `assets/data/*.json` at build time. The HTML output is a static shell. All data — timeline, GitHub stats, recommendations, blog articles — is fetched by the browser via `main.js` and `content.js` at runtime.

This means:
- The Python pipeline commits updated JSON to the repo
- GitHub Pages serves the JSON as a static file
- The browser fetches it fresh on every page load
- No Astro rebuild is needed when JSON changes

### Pipeline Flow (Unchanged)

```
GitHub Actions (Daily @ 06:00 UTC)
    ↓
fetch_github_data.py   → assets/data/github_activity.json
fetch_linkedin_data_enhanced.py → assets/data/linkedin_*.json
build_profile_data.py  → assets/data/profile.json
translate_projects.py  → patches assets/i18n/*.json
fetch_linkedin_articles.py → assets/data/blog_articles.json
translate_articles.js  → assets/data/blog_articles_{en,es}.json
    ↓
git commit && push (if changes detected)
    ↓
build-and-deploy.yml fires → Astro build → GitHub Pages deploy
```

### GitHub Actions: Two Workflows

**Workflow 1: `update-profile.yml` (UNCHANGED)**
Keep exactly as-is. Zero modifications.

**Workflow 2: `build-and-deploy.yml` (NEW)**

```yaml
name: Build and Deploy (Astro)

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm run build
        env:
          BASE_URL: /cv-site-otavio
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ./dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/deploy-pages@v4
        id: deployment
```

**GitHub Pages settings change:** Repository Settings → Pages → Source: change from "Deploy from a branch" to "GitHub Actions".

### Build Time Impact

| Scenario | Duration |
|----------|----------|
| Python data fetch steps | ~2-5 min (unchanged) |
| Astro build (estimated) | ~5-10s |
| Total additional time | Negligible |

---

## 6. i18n Strategy

### Current System

The i18n system is entirely client-side runtime:
- `assets/js/i18n.js` fetches `/assets/i18n/{lang}.json` on page load
- Applies to all `[data-i18n-key]` elements via `element.textContent = value`
- `[data-i18n-aria]` sets `aria-label` attributes
- `window.i18n.t("key")` global accessor for JS-rendered content
- Language stored in `localStorage`; detection order: localStorage → navigator.languages → default pt-BR
- `languageChanged` custom event for reactive JS components

### Migration Strategy: Preserve, Don't Replace

Do not rewrite the i18n system. Port `assets/js/i18n.js` as-is to Astro. Include it in `BaseLayout.astro`:

```astro
<!-- src/layouts/BaseLayout.astro -->
<body data-baseurl={import.meta.env.BASE_URL}>
  <slot />
  <script src="/assets/js/i18n.js" defer></script>
</body>
```

The `data-baseurl` body attribute enables `i18n.js` to correctly prefix fetch paths. Set it to `import.meta.env.BASE_URL`.

### URL Strategy

**Maintain single-URL pattern.** No `/en/`, `/es/` routes in v1:
- `/cv-site-otavio/` serves all languages
- Language selected via localStorage + browser detection
- Identical URL structure to today → no broken external links

Future optional: static per-language pages via `getStaticPaths()` in Phase 4+. Additive, non-breaking.

### i18n Key Namespaces

```
nav.*              – Navigation (10 keys)
hero.*             – Hero section (13 keys)
about.*            – About section (9 keys)
impact.*           – Impact metrics (8 keys)
timeline.*         – Timeline section (5 keys)
skills.*           – Skills section (9 keys + items object)
projects.*         – GitHub projects (7 keys + descriptions object)
featured_projects.* – Featured projects (5 keys)
tech_stack.*       – Tech stack (3 keys)
blog.*             – Blog/articles (5+ keys)
recommendations.*  – Recommendations (3 keys + items object with author text)
stats.*            – GitHub stats (10+ keys)
contact.*          – Contact section (8+ keys)
roi_calculator.*   – ROI calculator (10+ keys)
footer.*           – Footer (2 keys)
```

**Note:** Recommendation text lives in i18n files, not in `linkedin_recommendations.json`. The JSON only carries `id`, `author`, `role`, `company`, `linkedin`, `photo`. Text is resolved via `window.i18n.t('recommendations.items.{id}.text')`.

---

## 7. JSON → Astro Data Loading

### Guiding Principle

Keep `assets/data/*.json` at their existing paths. Do not move them into `src/content/`. The Python pipeline continues writing to the same locations. Astro reads them directly.

### Loading Strategy per File

| JSON File | Loading Strategy | Reason |
|-----------|-----------------|--------|
| `profile.json` | Build-time import (meta tags) + runtime fetch (dynamic sections) | Name/title needed for `<head>` SEO; timeline/projects change daily |
| `github_activity.json` | Runtime fetch only | Large (9,294 lines); changes daily; never embed in HTML |
| `projects_extended.json` | Build-time import | Static curated data; benefits from type safety |
| `tech_stack.json` | Build-time import | Static curated data; benefits from type safety |
| `linkedin_profile.json` | Not directly used | Merged into `profile.json` by `build_profile_data.py` |
| `linkedin_recommendations.json` | Not directly used | Merged into `profile.json` |
| `blog_articles.json` | Runtime fetch | Changes daily (currently empty) |
| `blog_articles_en-US.json` | Runtime fetch | Loaded when `lang === 'en-US'` |
| `blog_articles_es-ES.json` | Runtime fetch | Loaded when `lang === 'es-ES'` |

### Optional: Typed Content Collections

For `tech_stack.json` and `projects_extended.json` only (static, curated):

```typescript
// src/content/config.ts
import { defineCollection, z } from 'astro:content';

export const collections = {
  techStack: defineCollection({
    type: 'data',
    schema: z.object({
      categories: z.array(z.object({
        name: z.string(),
        icon: z.string(),
        technologies: z.array(z.object({
          name: z.string(),
          level: z.enum(['expert', 'advanced', 'intermediate']),
          logo: z.string(),
        })),
      })),
    }),
  }),
};
```

Files would be symlinked or copied at build time from `assets/data/` → `src/content/`. Not required for v1.

---

## 8. Astro Project Configuration

```javascript
// astro.config.mjs
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://donotavio.github.io',
  base: '/cv-site-otavio',
  output: 'static',
  build: {
    assets: 'assets',
  },
  vite: {
    build: {
      assetsInlineLimit: 0, // keep SVGs as separate files
    },
  },
});
```

```json
// package.json (minimal)
{
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview",
    "check": "astro check"
  },
  "dependencies": {
    "astro": "^4.x",
    "gsap": "^3.x",
    "lenis": "^1.x"
  },
  "devDependencies": {
    "typescript": "^5.x"
  }
}
```

---

## 9. Rollback Plan

### Before Migration Begins

```bash
git checkout -b jekyll-stable
git push origin jekyll-stable
```

This branch is the production-stable Jekyll snapshot. Never delete it.

### Rollback Triggers

Roll back to `jekyll-stable` if:
- `build-and-deploy.yml` fails to produce working GitHub Pages after 2 debugging sessions
- i18n runtime shows regressions vs. Jekyll baseline
- Lighthouse drops below 85 and cannot be resolved in 1 working day
- Any section fails to render content from JSON

### Rollback Procedure

```bash
# Preserve the Astro work
git checkout -b redesign/astro-v1-attempt
git push origin redesign/astro-v1-attempt

# Restore Jekyll to main
git checkout main
git reset --hard jekyll-stable
git push origin main --force-with-lease

# GitHub Pages Settings → Pages → Source: Deploy from branch → main → / (root)
```

Time cost: ~30 minutes. Zero impact on data pipeline.

### Jekyll + GSAP Fallback

If Astro is abandoned, GSAP + Lenis work in Jekyll with one day of setup:

1. Copy `gsap.min.js` and `lenis.min.js` to `assets/js/vendors/`
2. Create `assets/js/motion.js` — initializes Lenis scroll + GSAP ScrollTrigger
3. Add `<script src="assets/js/motion.js" defer>` to `_layouts/default.html`
4. All design tokens (CSS custom properties) from Phase 1 remain valid

No other architectural changes. Same motion goals achievable at the cost of ESM organization.

---

## 10. Phase Timeline

| Phase | Duration | Gate | Deliverable |
|-------|----------|------|-------------|
| **0** | In progress | **GATE 0** | This plan, approved |
| **1** | 1 day | — | Repo cleaned, `jekyll-stable` branch created |
| **2** | 3–4 days | **GATE 2** | Art direction: 3 visual options → 1 chosen |
| **3** | 2–3 days | **GATE 3** | Astro skeleton deploying to Pages |
| **4** | 7–10 days | — | All sections with motion |
| **5** | 3–5 days | — | Lighthouse ≥90, WCAG AA, a11y report |
| **6** | 1–2 days | — | Production launch, pipeline validated |
| **Total** | ~5 weeks | | Full Astro site in production |

---

## 11. Definition of Done (Phase 0)

- [x] Codebase audited (full directory tree, all JS, CSS, data, i18n)
- [x] Existing Lighthouse baseline noted (Performance 95, Accessibility 100)
- [x] Data pipeline decoupling confirmed (runtime fetch, not build-time)
- [x] Migration risks identified and mitigated
- [x] Cleanup items documented
- [x] i18n preservation strategy defined (port as-is)
- [x] Data loading strategy per JSON file defined
- [x] GitHub Actions changes specified (2 workflows, existing unchanged)
- [x] Rollback procedure documented
- [x] Jekyll + GSAP fallback path documented
- [ ] **Approval received at GATE 0 before proceeding**

---

## Appendix A: Astro vs Jekyll Full Comparison

| Criterion | Astro | Jekyll |
|-----------|-------|--------|
| Data pipeline risk | None | None |
| GSAP + Lenis integration | ESM imports (clean) | Window globals (congested) |
| i18n system | Port runtime JS as-is | No change |
| TypeScript support | Yes | No |
| Build system | Vite (modern) | Jekyll 3.x (frozen) |
| Ruby dependency | No | Yes (brittle on macOS) |
| Agent compatibility | All 4 agents designed for Astro | Would require rewrites |
| Content schemas | Optional typed collections | None |
| GitHub Pages deploy | Custom Actions workflow | Native auto-build |
| Scoped CSS | Component-level | Global only |
| Learning curve | Low-Medium | Low |

---

## Appendix B: Sensitive File Note

`debug_linkedin.html` contains a full raw HTML dump of the LinkedIn profile page including authenticated session content. It is 348 KB and was likely committed by accident during scraper development. **Remove immediately before any public work on this branch.**

---

**Prepared by:** OpenCode / Architecture Review
**Date:** June 28, 2026
**Status:** Ready for GATE 0 Approval
**Next action:** Review → Confirm GO/NO-GO on Astro → Signal to proceed to Phase 1
