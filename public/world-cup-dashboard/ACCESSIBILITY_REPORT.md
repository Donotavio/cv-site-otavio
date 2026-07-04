# Accessibility & Performance Report — World Cup 2026 Dashboard

**Audit scope:** New sections 04 Shot Map, 05 Pass Network, 06 Momentum + verification that restructuring (renumbered 01–03, 07–14) did not break existing sections.

- **Auditor:** A11y & Performance Auditor (automated agent)
- **Date:** 2026-07-04
- **Page under test:** `http://localhost:4321/cv-site-otavio/world-cup-dashboard/index.html` (Astro dev server, HTTP 200)
- **Stack:** Static HTML + vanilla JS + Chart.js 4.4.4 (CDN, `defer`) + CSS with design tokens
- **Lighthouse:** v 12.x, Chrome 150 headless

---

## 1. Executive Summary

| Category | Status | Notes |
|---|---|---|
| Accessibility (WCAG 2.1 AA) | ⚠ **PARTIAL PASS** | 1 critical bug (latent crash) + 1 wrong aria-label + 4 pre-existing contrast fails |
| Performance | ⚠ **PARTIAL PASS** | LCP/CLS targets missed (pre-existing); new code itself is clean |
| Functional verification | ✅ **PASS** for seed-data state; 🔴 **FAIL** for production data state |
| Cross-check / data flow | ✅ **PASS** for current seed; 🔴 **FAIL** when real data arrives |

**Verdict:** 🔴 **BLOCKED — DO NOT SHIP TO PRODUCTION**

There is a **critical latent bug** in `js/motion.js:17–18` that will crash the Shot Map (04) and Pass Network (05) renderers the moment the FBref/StatsBomb pipeline populates `deepstats.json` with real data. The dashboard "works" only because the seed data marks both sections as `available: false`. As soon as that flag flips, the page throws `TypeError` and the entire deep-stats module aborts. This is a guaranteed production failure on first data refresh.

Fix is **one line** in `motion.js` (see §3).

---

## 2. PASS/FAIL per Category

### 2.1 Accessibility (WCAG 2.1 AA) — ⚠ PARTIAL PASS

| Check | Result | Detail |
|---|---|---|
| All 14 sections have `aria-labelledby` → real `<h2>` | ✅ PASS | Verified programmatically; 14/14 valid (`allSections` in probe output). Hero section uses `wc-hero-title` on `<h1>` (intentional). |
| Section numbering sequential 01–14, no gaps/dupes | ✅ PASS | 01 Notícias → 02 Artilharia → 03 Estatísticas → **04 Shot Map → 05 Pass Network → 06 Momentum** → 07 Monte Carlo → 08 Grupos → 09 Mata-mata → 10 Seleção → 11 Insights → 12 Craque → 13 Partidas → 14 Bolão. No dupes. |
| Shot map bubbles: `role="button"` + `tabindex="0"` + descriptive `aria-label` | ✅ PASS (in code) | `js/deepstats.js:289–297` emits correct attrs. **Note:** Cannot be exercised at runtime because of the crash bug (§3.1) — the renderer dies at line 303 before bubbles are injected. |
| Pass network SVG `role="img"` + `aria-labelledby` → title+desc | ✅ PASS | `index.html:414–416`. SVG `<title id="wc-passnet-desc">` is the description. |
| Pass network toggle uses `aria-pressed` | ✅ PASS (in code) | `js/deepstats.js:380–383`. Same caveat as above — toggle is only rendered when `data.available !== false`, which means it has never been rendered in production. |
| Momentum canvas `role="img"` + descriptive `aria-label` | ⚠ **PARTIAL** | `role="img"` ✅. `aria-label` is **WRONG**: HTML hardcodes *"Linha do tempo horizontal mostrando o **xG acumulado** por seleção ao longo da partida"* but the chart actually renders **gols acumulados** (`metric: "goals"` in JSON). The renderer never updates the canvas aria-label dynamically. Also fails the spec criterion "mentions the match, the final score, number of goals". See §4.1. |
| Goal pulse markers `aria-hidden="true"` | ✅ PASS | `js/deepstats.js:689` `span.setAttribute('aria-hidden', 'true')`. Verified 8 markers present, all hidden from AT. |
| Color contrast (new classes) | ✅ PASS for new code | `.wc-shot-bubble--goal` (gold `#B0820D` w/ gold-ink ring `#8A5A06`) on paper: ≥5.8:1 ✓. `.wc-pass-edge` decorative SVG line, not text — 3:1 N/A. `.wc-goal-pulse__dot` gold on chart bg — decorative, N/A. |
| Color contrast (pre-existing, **not in audit scope**) | ⚠ **FAIL** | 4 instances of `--ink-faint` `#6C6C6C` on `--wc-live-dim` (rendered `#f3e5e4`) = **4.28:1** < 4.5:1. Found in news-source tag, freshness, etc. Pre-existing in main.js sections — **not introduced by this PR**. |
| Keyboard navigation, `:focus-visible` visible | ✅ PASS | Tab chain verified: skip-link → nav back → team filter chips → … All 8 sampled stops report `hasFocusVisible: true`. |
| `prefers-reduced-motion` neutralizes new animations | ✅ PASS | Three layers all verified: (a) CSS `@media (prefers-reduced-motion: reduce)` at `css/style.css:2924–2933` overrides `.wc-shot-bubble`, `.wc-pass-node`, `.wc-pass-edge`, hides `.wc-goal-pulse__ring`. (b) JS guard `prefersReducedMotion()` in `motion.js:9, 22, 64, 89` short-circuits to instant. (c) Chart.js animation disabled — measured `chart.options.animation === false` under emulated reduced-motion. |
| `IntersectionObserver` fallback | ✅ PASS | `motion.js:22` and `motion.js:89` check `typeof IntersectionObserver === 'undefined'` and add `.is-visible` immediately. `deepstats.js:101` does the same. |

### 2.2 Performance — ⚠ PARTIAL PASS

| Metric | Desktop | Mobile | Target | Status |
|---|---|---|---|---|
| Lighthouse Performance | 59 | 65 | ≥90 | 🔴 (pre-existing) |
| Lighthouse Accessibility | 96 | 96 | ≥90 | ✅ |
| Lighthouse Best Practices | 96 | 96 | ≥90 | ✅ (only fail is favicon 404, pre-existing) |
| Lighthouse SEO | 100 | 100 | ≥90 | ✅ |
| FCP | 1.8s | 1.8s | <2.5s | ✅ |
| LCP | 3.6s | 3.6s | <2.5s | 🔴 (pre-existing — hero font swap) |
| CLS | **0.625** | **0.625** | <0.1 | 🔴 (pre-existing — hero font swap) |
| TBT | 330ms | 130ms | <200ms | ⚠ desktop only |

**Performance findings specific to the new code:**

- ✅ **No layout thrash.** New CSS (`css/style.css:2854–2933`) only transitions `transform`, `opacity`, `stroke-dashoffset`. No `width`/`top`/`left` transitions. ✓
- ✅ **No new render-blocking resources.** New scripts (`motion.js`, `deepstats.js`) load via existing `<script defer>` chain. ✓
- ✅ **No new long tasks attributable to new code.** Existing 10 long tasks all originate from `cdn.jsdelivr.net/.../chart.umd.min.js` (Chart.js parse). New code (`deepstats.js`/`motion.js`) adds negligible parse cost.
- ⚠ **Unused JS:** 28 KiB from Chart.js (deepstats uses only line chart). Pre-existing pattern (other charts in main.js also use Chart.js). Not blocking.
- ✅ **CSP compliance.** Verified no inline event handlers introduced; Chart.js still loaded from whitelisted `https://cdn.jsdelivr.net`. Page-level `<meta http-equiv="Content-Security-Policy">` (`index.html:17–24`) is honored by browsers even though Astro dev server doesn't echo it as a header.
- ✅ **Chart.js load order.** All four scripts are `defer`, executed in document order: Chart.js → main.js → motion.js → deepstats.js. `Chart` is guaranteed defined when `renderMomentum` runs. Defensive `typeof Chart === 'undefined'` guard exists at `js/deepstats.js:517`. ✓

### 2.3 Functional Verification — ✅ for seed state, 🔴 for production state

| Check | Result |
|---|---|
| `main.js` unchanged | ✅ PASS — `md5(e6c6f409ba9d31229a84d64d89d1bdfb)` matches HEAD exactly. `git diff HEAD -- main.js` returns empty. |
| Sections 01–03 render | ✅ PASS — skeletons present, mono-labels 01/02/03, h2 titles valid. |
| Sections 07–14 (renumbered) render | ✅ PASS — labels sequential 07–14, all `aria-labelledby` valid, no broken refs. |
| Section 04 graceful empty state | ✅ PASS — `#wc-shotmap-empty` shown with `"Aguardando dados de finalizações para a partida selecionada."`, `#wc-shotmap-error` correctly hidden, `#wc-shotmap-match` reads `"aguardando FBref · pipeline CI"`. |
| Section 05 graceful empty state | ✅ PASS — `#wc-passnet-empty` shown with `"Selecione uma partida para montar a rede de passes."`. |
| Section 06 momentum chart renders | ✅ PASS — canvas 696×270, Chart.js instance created, 8 goal markers placed, error box hidden. Dataset labels: `"GER · Gols acumulados"` and `"CUW · Gols acumulados"` (matches `metric_label`). Axis Y title: `"Gols acumulados"`. Tooltip callback returns `"${tag}: ${v} gols"` (verified in code, `deepstats.js:610–613`). |
| Section 04 with data | 🔴 **FAIL** — see §3.1 (motion.js crash). |
| Section 05 with data | 🔴 **FAIL** — see §3.1 (same bug). |

### 2.4 Cross-check Data Flow — ✅ for seed, 🔴 when populated

| Check | Result |
|---|---|
| `data/deepstats.json` fetches with HTTP 200 | ✅ PASS |
| `deepstats.js` parses JSON and dispatches to 3 renderers | ✅ PASS (`init()` at `deepstats.js:734–752`) |
| Renderer reads `data.home.cum` (not `xg_cum`) | ✅ PASS — `deepstats.js:538` `const homeData = data.home.cum || data.home.xg_cum;`. Backwards-compatible. |
| `metric_label` used for axis title | ✅ PASS — `deepstats.js:630` `title: { display: true, text: metricLabel }` |
| `metric === 'goals'` switches tooltip to `"gols"` | ✅ PASS — `deepstats.js:610–613` |

---

## 3. Critical Issues (must fix before production)

### 3.1 🔴 `motion.js:17–18` — sort-wrapper bug crashes both new renderers

**Symptom (live reproduction):**

```
TypeError: Cannot read properties of undefined (reading 'xg')
    at sort (deepstats.js:305:42)
    at Array.sort (<anonymous>)
    at Object.revealStagger (motion.js:18:17)
    at renderShotMapBubbles (deepstats.js:303:14)

TypeError: Cannot read properties of undefined (reading 'line')
    at sort (deepstats.js:493:46)
    at Array.sort (<anonymous>)
    at Object.revealStagger (motion.js:18:17)
    at renderPassNetNodes (deepstats.js:491:14)
```

**Root cause:**

`js/motion.js:16–20`:

```js
if (typeof o.sort === 'function') {
  const withIndex = arr.map((el, i) => ({ el, i }));
  withIndex.sort(o.sort);          // ❌ passes {el, i} wrappers, not raw els
  arr = withIndex.map(x => x.el);
}
```

The `withIndex` array holds `{el, i}` wrapper objects, but `withIndex.sort(o.sort)` invokes the **user-supplied** `o.sort` with those wrappers. The user sort callbacks in `deepstats.js` access element APIs directly:

- `js/deepstats.js:305` — `sort: (a, b) => Number(b.dataset.xg) - Number(a.dataset.xg)`
- `js/deepstats.js:493` — `sort: (a, b) => (lineOrder[a.dataset.line] ?? 9) - (lineOrder[b.dataset.line] ?? 9)`

So `b.dataset` is `undefined` (because `b` is `{el, i}`, not the DOM node) → `undefined.xg` → TypeError. The whole `renderShotMapBubbles` (and `renderPassNetNodes`) call aborts.

**Why this is critical:**

1. The dashboard ships with `shot_map.available === false` and `pass_network.available === false` (seed JSON), so the crash is **latent** — early-exit in `renderShotMap` (`deepstats.js:200`) and `renderPassNetwork` (`deepstats.js:353`) prevents the buggy code path from running.
2. The pipeline is described as *"currently aguardando FBref · pipeline CI"* and *"Tentativa automatizada ativa no pipeline CI."* The moment CI writes real shots/edges, `data.available` flips `true` and **the page breaks on next refresh.**
3. The crash is **uncaught** — it propagates out of `renderShotMapBubbles` → `renderShotMap` → `init()`. The third renderer (`renderMomentum`) is called immediately after at `deepstats.js:748`; whether it still runs depends on whether the IIFE-level `init()` catches. It does **not** — there is no try/catch around lines 746–748. So **a single bad shots array also kills the working momentum chart.**
4. Even if momentum were guarded, two of the three new sections (the headline features of this PR) would silently fail and leave empty pitches with no error UI.

**Fix (one line):**

`js/motion.js:18`:

```diff
- withIndex.sort(o.sort);
+ withIndex.sort((a, b) => o.sort(a.el, b.el));
```

This adapts the wrapper objects to the documented user-facing API. The original `i` index is preserved (currently unused but kept for future use).

**Additional defensive recommendation (should also do):**

Wrap each renderer call in `init()` so a failure in one section doesn't kill the others:

`js/deepstats.js:745–748`:

```diff
- const d = result.data;
- renderShotMap(d.shot_map || null);
- renderPassNetwork(d.pass_network || null);
- renderMomentum(d.momentum || null);
+ const d = result.data;
+ const safe = (fn, arg) => { try { fn(arg); } catch (e) { console.warn('[WCDeepStats]', e); } };
+ safe(renderShotMap,     d.shot_map     || null);
+ safe(renderPassNetwork, d.pass_network || null);
+ safe(renderMomentum,    d.momentum     || null);
```

---

## 4. Warnings (should fix, not strictly blocking)

### 4.1 ⚠ Momentum canvas aria-label is stale / wrong

**Location:** `index.html:439`

```html
<canvas id="chart-momentum" role="img" aria-label="Linha do tempo horizontal mostrando o xG acumulado por seleção ao longo da partida."></canvas>
```

**Problem:** Hardcoded text says **"xG acumulado"** but the chart actually renders **"Gols acumulados"** (`data.metric === "goals"`, axis title verified at runtime). Screen-reader users hear a description that contradicts what sighted users see. Also fails the spec criterion *"mentions the match, the final score, number of goals"*.

**Fix:** Update the canvas aria-label dynamically inside `renderMomentum` after `metricLabel` is computed (`deepstats.js:~543`):

```js
const matchStr   = data.match ? `${data.match} — ` : '';
const finalScore = data.home && data.away
  ? `Placar final ${data.home.code} ${homeData[homeData.length-1]}–${awayData[awayData.length-1]} ${data.away.code}. `
  : '';
const totalGoals = Array.isArray(data.goals) ? `${data.goals.length} gols.` : '';
canvas.setAttribute('aria-label',
  `${matchStr}linha do tempo horizontal mostrando ${metricLabel.toLowerCase()} por seleção ao longo da partida. ${finalScore}${totalGoals}`);
```

### 4.2 ⚠ LCP 3.6s, target <2.5s

**Pre-existing** (not introduced by this PR). LCP element is the hero display title `<h1>23WC A Copa em dados…>`, blocked by font swap on `Instrument Serif` (preloaded at `index.html:31–32` but with metric fallback only). New PR changed only the hero lead paragraph text, not the structure — diff is +9 lines of body copy.

### 4.3 ⚠ CLS 0.625 (Lighthouse), 0.126 (Puppeteer session)

**Pre-existing** (not introduced by this PR). Puppeteer session trace attributes the largest shift to `SECTION.wc-hero` (height 858→679) and `DIV.wc-hero__actions` collapsing during web-font swap at ~283 ms after FCP. New code does **not** contribute to this — the new sections all use `aspect-ratio` (shot map `3/4` at `index.html:373`, pass network `16/10` at `index.html:411`, momentum `clamp(280px,38vw,360px)` at `index.html:438`) so their boxes are reserved before content arrives.

### 4.4 ⚠ Color contrast: `--ink-faint` on `--wc-live-dim` — 4.28:1

**Pre-existing** (not introduced by this PR). 4 instances reported by Lighthouse, all in main.js-driven news/freshness chrome (color `#6C6C6C` on rendered `#f3e5e4`). Spec target 4.5:1 for normal text. Fix would be either:
- Darken `--ink-faint` token to `#666666` (4.85:1) — global change, needs visual review.
- Or scope `.wc-news-source, .wc-freshness { color: var(--ink-soft); }` — surgical.

### 4.5 ⚠ `.wc-shot-bubble--miss` effective contrast ~1.5:1 on field-green over paper

**Location:** `css/style.css:2870–2871`

The miss-bubble is `--wc-field` `#2E8B2E` at `opacity: .55` once visible. Composited on `--paper` `#FDFDFD`, effective color is roughly `#94C294`, contrast ≈ 1.5:1 against the paper. These are decorative dots, not text or meaningful UI affordances (the legend at `index.html:386–389` conveys meaning textually), so strict 3:1 does not apply — but consider raising to `opacity: .7` so colour-blind users can distinguish goal vs miss without hovering.

### 4.6 ⚠ `/favicon.ico` 404

Pre-existing. Triggers Lighthouse "errors-in-console" best-practices flag (otherwise best-practices would be 100). Add `<link rel="icon" href="data:,">` or ship a real favicon.

### 4.7 ⚠ `wc-passnet-empty` is not `hidden` initially

**Location:** `index.html:417`

Unlike `#wc-shotmap-empty` (which has `hidden`) and `#wc-shotmap-error` / `#wc-flow-error` (both `hidden`), `#wc-passnet-empty` is visible by default. This is intentional (so the message shows before fetch resolves), but means screen-reader users encounter *"Selecione uma partida para montar a rede de passes."* even if JS is disabled and they have no way to "select" anything. Consider `aria-live="polite"` so AT doesn't announce it eagerly, and gate the message on JS availability via the existing `.has-js` class on `<html>`.

---

## 5. Lighthouse Scores

### Desktop (form factor: desktop, no throttling)

| Category | Score |
|---|---|
| Performance | **59**/100 |
| Accessibility | **96**/100 |
| Best Practices | **96**/100 |
| SEO | **100**/100 |

Metrics: FCP **1.8s** · LCP **3.6s** · CLS **0.625** · TBT **330ms** · SI **1.8s** · TTI **4.2s**

### Mobile (form factor: mobile, Lighthouse default 4G throttling)

| Category | Score |
|---|---|
| Performance | **65**/100 |
| Accessibility | **96**/100 |
| Best Practices | **96**/100 |
| SEO | **100**/100 |

Metrics: FCP **1.8s** · LCP **3.6s** · CLS **0.625** · TBT **130ms**

### A11y audit failures (score < 1)

- `color-contrast` — 4 instances (see §4.4, pre-existing).

### A11y manual audits (score=null)

All relevant manual audits (heading-order, label, link-name, landmark-one-main, target-size, svg-img-alt, button-name, aria-* family, html-has-lang, skip-link, meta-viewport) were checked programmatically and pass.

---

## 6. Console Errors

Captured via Puppeteer on a fresh cold load (no data injection):

```
Failed to load resource: the server responded with a status of 404 (Not Found)
  → http://localhost:4321/favicon.ico
```

That is the **only** console error. No JS errors from `deepstats.js`, `motion.js`, or `main.js`. No CSP violations. No 404s on any of the new assets (CSS, both new JS files, deepstats.json — all HTTP 200).

**When shot-map or pass-network data is injected at runtime** (simulating the moment the pipeline populates the JSON), the following uncaught errors appear in console:

```
TypeError: Cannot read properties of undefined (reading 'xg')
    at sort (deepstats.js:305:42)
    at Array.sort (<anonymous>)
    at Object.revealStagger (motion.js:18:17)
    at renderShotMapBubbles (deepstats.js:303:14)

TypeError: Cannot read properties of undefined (reading 'line')
    at sort (deepstats.js:493:46)
    at Array.sort (<anonymous>)
    at Object.revealStagger (motion.js:18:17)
    at renderPassNetNodes (deepstats.js:491:14)
```

See §3.1 for fix.

---

## 7. Browser / Device Compatibility

Not exhaustively tested in this audit (no Sauce Labs / BrowserStack available). Verified:

- Chrome 150 (headless, Puppeteer) ✅
- Chrome 150 (Lighthouse desktop + mobile emulation) ✅

Untested but expected to work (vanilla JS, no platform-specific APIs in new code):
- Firefox latest, Safari 14+, Edge latest, iOS Safari 14+, Chrome Android.

The only platform-specific APIs used are `IntersectionObserver`, `matchMedia('(prefers-reduced-motion: reduce)')`, `PerformanceObserver` (audit only), `fetch`, `Chart.js`. All have fallbacks in place.

---

## 8. Recommendations for Maintenance

1. **CI gate on the bug fixed in §3.1.** Add a smoke test that injects non-empty `shots` and `nodes`/`edges` and asserts no `pageerror` — would have caught this regression before merge.
2. **Quarterly Lighthouse runs** to catch CLS/LCP drift, especially after font changes.
3. **Dynamic ARIA for chart canvas** — see §4.1; generalise to all Chart.js canvases (existing stats charts at `index.html:288, 301, 314` have static aria-labels too).
4. **Token review** — `--ink-faint` at 4.28:1 on tinted backgrounds is a recurring pain point; consider splitting into `--ink-faint` (decorative) and `--ink-meta` (text on tint) at WCAG-AA compliant value.
5. **CSP header** — currently delivered via `<meta http-equiv>`. Production hosts (GitHub Pages) don't add headers, so meta is the only enforcement. Consider adding `Reporting-Endpoints` / `report-to` for production visibility on violations.

---

## 9. Sign-Off

- **Auditor:** A11y & Performance Auditor (automated)
- **Date:** 2026-07-04
- **Status:** 🔴 **BLOCKED — DO NOT LAUNCH**

The single one-line fix in §3.1 unblocks production. Once applied and re-verified, plus the §4.1 aria-label fix, the dashboard can ship. Performance issues (LCP/CLS) are pre-existing and out of scope for this audit cycle.
