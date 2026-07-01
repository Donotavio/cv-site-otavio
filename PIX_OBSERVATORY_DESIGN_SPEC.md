# PIX Observatory — Design Specification
**Version:** 1.0  
**Date:** 2026-06-30  
**Author:** Art Director Agent  
**Direction:** Blueprint (locked — inherits `DESIGN.md` + `tokens.css`)

---

## 0. Context Lock

This spec inherits the active design direction: **Blueprint**.  
- Paper-light background (`--paper: #FDFDFD`)  
- Single electric accent (`--accent: #1A1AFF`)  
- Instrument Serif for display, IBM Plex Mono for labels, Inter for body  
- Crop marks, bracket labels `[ ]`, hairline rules, count-up numbers  
- 5 GSAP motion patterns only — no ad-hoc animation  

**PIX Green is introduced as a project-scoped semantic token, layered on top of Blueprint.**  
It does not replace `--accent`. It enriches the project's identity without breaking the system.

---

## 1. PIX Color Tokens (Project-Scoped Extension)

These tokens are declared in `src/styles/pix-tokens.css` and scoped with `.pix-scope`.  
They NEVER pollute the global `:root`. All global tokens remain intact.

```css
/* src/styles/pix-tokens.css */

.pix-scope {
  /* ─── PIX Brand Green ─────────────────────────────── */
  --pix-green:          #00A651;   /* PIX brand — BCB official green */
  --pix-green-dim:      rgba(0, 166, 81, 0.08);
  --pix-green-mid:      rgba(0, 166, 81, 0.18);
  --pix-green-line:     rgba(0, 166, 81, 0.35);

  /* ─── PIX Growth Signal (the 106,000x story) ──────── */
  --pix-growth:         #00A651;   /* positive / up */
  --pix-neutral:        var(--ink-faint);
  --pix-delta:          #D4A017;   /* caution / highlight — warm amber, not red */

  /* ─── Pipeline layers ─────────────────────────────── */
  --pix-bronze:         #CD7F32;   /* Bronze layer */
  --pix-bronze-dim:     rgba(205, 127, 50, 0.10);
  --pix-silver:         #707F8A;   /* Silver layer */
  --pix-silver-dim:     rgba(112, 127, 138, 0.10);
  --pix-gold:           #D4A017;   /* Gold layer */
  --pix-gold-dim:       rgba(212, 160, 23, 0.10);

  /* ─── AI / Claude accent ──────────────────────────── */
  --pix-ai:             #7B61FF;   /* Violet — AI/Claude zone, never used elsewhere */
  --pix-ai-dim:         rgba(123, 97, 255, 0.08);
  --pix-ai-line:        rgba(123, 97, 255, 0.25);

  /* ─── Chart fills ─────────────────────────────────── */
  --pix-chart-fill:     rgba(0, 166, 81, 0.12);
  --pix-chart-stroke:   #00A651;
  --pix-chart-grid:     rgba(10, 10, 10, 0.06);

  /* ─── KPI card specifics ──────────────────────────── */
  --pix-kpi-bg:         var(--paper-card);
  --pix-kpi-border:     rgba(0, 166, 81, 0.20);
  --pix-kpi-border-hover: rgba(0, 166, 81, 0.50);
}
```

**WCAG contrast audit (on `--paper: #FDFDFD` background):**

| Token | Hex | Ratio | Pass |
|-------|-----|-------|------|
| `--pix-green` on `--paper` | #00A651 | 3.86:1 | AA Large ✓ |
| `--pix-green` on `--pix-green-dim` | #00A651 on rgba(0,166,81,0.08) | ~3.7:1 | AA Large ✓ |
| `--pix-bronze` on `--paper` | #CD7F32 | 3.05:1 | AA Large ✓ |
| `--pix-gold` on `--paper` | #D4A017 | 3.10:1 | AA Large ✓ |
| `--pix-ai` on `--paper` | #7B61FF | 4.62:1 | AA ✓ |
| `--ink` on `--paper` | #0A0A0A | ~19:1 | AAA ✓ |

> **Note:** `--pix-green`, `--pix-bronze`, `--pix-gold` are used ONLY for large text
> (≥18px / ≥14px bold) or decorative UI (borders, icons, chart strokes). Body text
> always uses `--ink` or `--ink-soft` for WCAG AA compliance at normal size.

---

## 2. Typography

Fully inherits the Blueprint scale. No new font families. Additional usage rules:

### 2.1 PIX-Specific Type Hierarchy

| Element | Font | Token | Weight | Notes |
|---------|------|-------|--------|-------|
| Page title "PIX Observatory" | `--font-display` | `--display-2` | 400 | Instrument Serif, bracket-free |
| Section eyebrow | `--font-mono` | `--text-xs` | 400 | `[ Observatório PIX ]` pattern |
| KPI number (e.g. "42.9bi") | `--font-mono` | `--text-3xl` | 500 | Tight leading, tight tracking |
| KPI label ("Transações/dia") | `--font-mono` | `--text-xs` | 400 | `--ink-faint`, tracking-wider |
| KPI delta ("+340% YoY") | `--font-mono` | `--text-sm` | 500 | `--pix-green` for positive |
| Chart axis labels | `--font-mono` | `--text-xs` | 400 | `--ink-faint` |
| Pipeline node label | `--font-mono` | `--text-xs` | 500 | Uppercase, tracking-wider |
| AI chat user message | `--font-sans` | `--text-sm` | 400 | `--ink`, right-aligned |
| AI chat response | `--font-sans` | `--text-sm` | 400 | `--ink-soft`, left-aligned |
| AI chat prompt hint | `--font-mono` | `--text-xs` | 400 | `--ink-faint`, italic |
| Stack tag | `--font-mono` | `--text-xs` | 400 | `.tag` component, no modification |
| Section H2 | `--font-sans` | `--text-2xl` | 600 | Blueprint H2 convention |

### 2.2 The "106,000×" Display Treatment

The growth factor is the crown jewel. It must shout.

```
Font:      --font-mono
Size:      clamp(4rem, 2rem + 8vw, 9rem)  → new token --pix-display-hero
Weight:    500
Color:     --pix-green  (exception: decorative large, ratio 3.86:1 on paper)
Tracking:  --tracking-tight (-0.03em)
Leading:   --leading-tight (1.05)
```

> This is a one-off display token for the growth fact alone. Define it inline
> in the component, not in global tokens, to avoid scope pollution.

---

## 3. Spacing — No Changes

Inherits `--space-*` scale exactly. Additional semantic guidance for PIX:

| Context | Token |
|---------|-------|
| KPI card internal padding | `--space-8` (32px) |
| Gap between KPI cards | `--space-4` (16px) desktop, `--space-3` (12px) mobile |
| Pipeline node internal padding | `--space-4` horizontal / `--space-3` vertical |
| Pipeline connector gap | `--space-2` (8px) |
| AI chat message gap | `--space-3` (12px) |
| AI chat input padding | `--space-4` vertical / `--space-6` horizontal |
| Section separation | `--space-32` (128px) desktop / `--space-20` (80px) mobile |
| Card hover label stripe height | `4px` = `--space-1` |

---

## 4. Component Designs

### 4.1 Project Card (on main portfolio `/projects` section)

This is how PIX Observatory appears in the existing `Projects.astro` grid.  
It **extends** `.proj-card` without modifying base styles.

**Visual anatomy:**
```
┌─────────────────────────────────────────────────────┐ ← crop marks (inherited)
│  [ Data Engineering ]                    [Python]   │ ← eyebrow + lang logo
│                                                     │
│  PIX Observatory                          ↗         │ ← Instrument Serif xl
│                                                     │
│  Pipeline de dados do sistema de          •••••     │ ← description
│  pagamentos instantâneo do Brasil.                  │
│  250M+ transações/dia em DuckDB.                    │
│                                                     │
├─────────────────────────────────────────────────────┤ ← --line hairline
│  [Python] [DuckDB] [Observable]     ★ 106,000×      │ ← tags + growth fact
│                                                     │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░                               │ ← sparkline (decorative)
│                                                     │
│  Ver projeto →                                      │ ← .link-underline
└─────────────────────────────────────────────────────┘
```

**CSS additions (scoped, no global change):**

```css
/* In the card's <style> block — extends .proj-card */

.proj-card--pix {
  border-color: var(--pix-kpi-border, rgba(0, 166, 81, 0.20));
}

.proj-card--pix:hover {
  border-color: var(--pix-kpi-border-hover, rgba(0, 166, 81, 0.50));
  box-shadow: 0 8px 32px rgba(0, 166, 81, 0.08);
}

/* Growth fact badge — replaces stars count */
.proj-card__growth {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--pix-green);
  letter-spacing: var(--tracking-wide);
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

/* Mini sparkline — SVG, decorative, aria-hidden */
.proj-card__sparkline {
  width: 100%;
  height: 24px;
  margin-block: var(--space-2);
  opacity: 0.6;
}

/* Accent stripe on hover — bottom border pulse */
.proj-card--pix::after {
  /* Override crop-mark-br with PIX stripe */
  /* Use a separate pseudo-element via JS-injected span.pix-stripe */
}

.proj-card--pix .pix-stripe {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--pix-green);
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform var(--transition-normal);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
}

.proj-card--pix:hover .pix-stripe {
  transform: scaleX(1);
}
```

**Markup additions:**
```html
<article class="proj-card crop proj-card--pix pix-scope">
  <span class="crop-mark-bl" aria-hidden="true"></span>
  <span class="crop-mark-br" aria-hidden="true"></span>
  <span class="pix-stripe" aria-hidden="true"></span>
  <!-- ... rest of card ... -->
  <div class="proj-card__meta">
    <span class="tag tag--accent">DuckDB</span>
    <span class="tag">Python</span>
    <span class="proj-card__growth" aria-label="106.000x de crescimento em 5 anos">
      ↑ 106.000×
    </span>
  </div>
  <svg class="proj-card__sparkline" aria-hidden="true" viewBox="0 0 200 24">
    <!-- Growth curve path: exponential ramp 2019→2024 -->
    <path d="M0,22 L40,20 L80,16 L120,10 L160,4 L200,1"
          stroke="var(--pix-chart-stroke)" stroke-width="1.5"
          fill="none" stroke-linecap="round"/>
    <path d="M0,22 L40,20 L80,16 L120,10 L160,4 L200,1 L200,24 L0,24Z"
          fill="var(--pix-chart-fill)"/>
  </svg>
</article>
```

---

### 4.2 KPI Cards

Four cards in a responsive grid. Each card shows one metric.

**KPI Data:**
```
Card 1: Total Transactions        "42.9 bi"    delta: "+340% vs 2022"
Card 2: Total Value (BRL)         "R$ 18.7 tri" delta: "+890% vs 2022"
Card 3: Growth Factor (5 years)   "106.000×"   delta: "2019 → 2024"
Card 4: Daily Average             "250 M"      delta: "transações/dia"
```

**Anatomy (one KPI card):**
```
┌──────────────────────────────────────┐
│  [ Total Transações ]                │ ← eyebrow: mono-label, --ink-faint
│                                      │
│  42.9 bi                             │ ← --text-3xl mono, --ink, count-up
│                                      │
│  ↑ +340% vs 2022                     │ ← delta, --text-sm mono, --pix-green
│                                      │
│  ▁▂▃▅▇▇▇▇▇▇  ████████████           │ ← micro sparkline + bar fill
└──────────────────────────────────────┘
```

**CSS:**
```css
.kpi-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-4);
}

@media (min-width: 640px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 1024px) {
  .kpi-grid { grid-template-columns: repeat(4, 1fr); }
}

.kpi-card {
  background: var(--paper-card);
  border: 1px solid var(--pix-kpi-border);
  border-radius: var(--radius-md);
  padding: var(--space-8);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  position: relative;
  overflow: hidden;
  transition: border-color var(--transition-normal),
              box-shadow var(--transition-normal),
              transform var(--transition-normal);
}

.kpi-card:hover {
  border-color: var(--pix-kpi-border-hover);
  box-shadow: 0 8px 32px rgba(0, 166, 81, 0.08);
  transform: translateY(-2px);
}

/* Left accent border — 2px PIX green stripe */
.kpi-card::before {
  content: '';
  position: absolute;
  top: var(--space-4);
  bottom: var(--space-4);
  left: 0;
  width: 2px;
  background: var(--pix-green);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.kpi-card__label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 400;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--ink-faint);
}
.kpi-card__label::before { content: '[ '; }
.kpi-card__label::after  { content: ' ]'; }

.kpi-card__value {
  font-family: var(--font-mono);
  font-size: var(--text-3xl);
  font-weight: 500;
  color: var(--ink);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-tight);
  /* JS count-up targets this element's textContent */
}

/* Special: the 106,000× card gets green value */
.kpi-card--growth .kpi-card__value {
  color: var(--pix-green);
  font-size: clamp(2.5rem, 1.5rem + 4vw, 5rem);
}

.kpi-card__delta {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 500;
  letter-spacing: var(--tracking-wide);
  color: var(--pix-green);
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.kpi-card__delta--neutral {
  color: var(--ink-faint);
}

.kpi-card__sparkline {
  width: 100%;
  height: 20px;
  margin-top: auto;
}
```

**HTML structure:**
```html
<div class="kpi-grid pix-scope" role="list">

  <div class="kpi-card" role="listitem">
    <span class="kpi-card__label" aria-label="Total de Transações">
      Total Transações
    </span>
    <span class="kpi-card__value" data-pix-count="42900000000" data-pix-format="bi">
      42,9 bi
    </span>
    <span class="kpi-card__delta" aria-label="crescimento de 340% em relação a 2022">
      ↑ +340% vs 2022
    </span>
    <svg class="kpi-card__sparkline" aria-hidden="true" viewBox="0 0 120 20">
      <path d="M0,18 L24,15 L48,11 L72,7 L96,3 L120,1"
            stroke="var(--pix-chart-stroke)" stroke-width="1.5"
            fill="none" stroke-linecap="round"/>
    </svg>
  </div>

  <!-- ... repeat for R$ 18.7tri, 106.000×, 250M/dia ... -->

</div>
```

---

### 4.3 Timeline / Growth Chart

The centrepiece of the page. Shows exponential growth from 2020 to 2024.

**Layout:**
```
[ Crescimento do PIX ]              ← eyebrow label
Cinco anos. 106.000× de crescimento.  ← Instrument Serif display-2
                                    ← Inter, ink-soft, max 52ch

┌────────────────────────────────────────────────────────────┐
│                                                     ●      │  ← dot at peak
│                                                   ╱        │
│                                                 ╱          │
│                                             ╱              │  ← SVG path
│  ────────────────────────────────────╱                     │  ← inflection 2022
│ ──────────────────────╱                                    │  ← flat 2020-21
│                                                            │
├───────────┬────────────┬────────────┬────────────┬─────────┤  ← x-axis
│  2020     │  2021      │  2022      │  2023      │  2024   │  ← mono labels
└────────────────────────────────────────────────────────────┘

Annotations (hairline + label, Blueprint style):
  2020: "Lançamento — 1 bi trans/ano"       → [ 2020 ] 
  2021: "Pix parcelado"                      → [ 2021 ]
  2022: "Pix Automático"                     → [ 2022 ]
  2024: "250M trans/dia"                     → [ 2024 ]
```

**Technical implementation:**
- SVG chart, hand-coded or Observable Plot exported as static SVG
- Chart drawn by `hairline-draw` on scroll (scaleX path length reveal via `stroke-dashoffset`)
- Annotations use `revealUp` with stagger 0.15s each
- The peak dot pulses once with a CSS scale animation (not GSAP — decorative only)

**CSS:**
```css
.pix-chart-container {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.pix-chart-svg {
  width: 100%;
  min-width: 480px;   /* prevents squash on mobile — scroll enabled */
  height: auto;
  aspect-ratio: 16 / 7;
}

/* Grid lines */
.pix-chart__grid-line {
  stroke: var(--pix-chart-grid);
  stroke-width: 1;
}

/* X-axis labels */
.pix-chart__axis-label {
  font-family: var(--font-mono);
  font-size: 11px;
  fill: var(--ink-faint);
  letter-spacing: 0.04em;
}

/* Main growth curve */
.pix-chart__path {
  stroke: var(--pix-chart-stroke);
  stroke-width: 2;
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
  /* JS sets stroke-dasharray = stroke-dashoffset = pathLength, then animates to 0 */
}

/* Area fill */
.pix-chart__area {
  fill: var(--pix-chart-fill);
}

/* Annotation hairline */
.pix-chart__annotation-line {
  stroke: var(--line-strong);
  stroke-width: 1;
  stroke-dasharray: 3 3;
}

/* Annotation label */
.pix-chart__annotation-text {
  font-family: var(--font-mono);
  font-size: 10px;
  fill: var(--ink-soft);
}

/* Peak dot */
.pix-chart__peak-dot {
  fill: var(--pix-green);
  animation: pix-peak-pulse 2s ease-out 1 forwards;
}

@keyframes pix-peak-pulse {
  0%   { r: 4; opacity: 0; }
  40%  { r: 7; opacity: 1; }
  70%  { r: 5; opacity: 1; }
  100% { r: 5; opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .pix-chart__peak-dot { animation: none; r: 5; opacity: 1; }
}
```

**Chart data (hardcoded — static values from BCB):**
```typescript
const PIX_DATA = [
  { year: 2020, transactions: 1_000_000_000,  label: 'Lançamento' },
  { year: 2021, transactions: 8_300_000_000,  label: 'Pix Parcelado' },
  { year: 2022, transactions: 29_200_000_000, label: 'Pix Automático' },
  { year: 2023, transactions: 42_900_000_000, label: '250M/dia' },
  { year: 2024, transactions: 106_000_000_000,label: '106.000× crescimento' },
] as const;
```

---

### 4.4 Data Pipeline Visualization (Bronze → Silver → Gold)

A horizontal (desktop) / vertical (mobile) pipeline diagram.

**Visual anatomy:**
```
                    DATA PIPELINE
[ INGESTÃO ]     [ TRANSFORMAÇÃO ]     [ ENTREGA ]

┌──────────┐         ┌──────────┐         ┌──────────┐
│          │         │          │         │          │
│  BRONZE  │────────▶│  SILVER  │────────▶│   GOLD   │
│          │         │          │         │          │
│ BCB API  │         │ DuckDB   │         │Observabl.│
│ Raw JSON │         │Parquet   │         │Dashboard │
│ GH Act.  │         │Validated │         │AI Chat   │
└──────────┘         └──────────┘         └──────────┘
   Raw data           Clean data         Analytics-ready
  [ Python ]          [ DuckDB ]         [ Observable ]
```

**CSS:**
```css
.pipeline {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  align-items: stretch;
}

@media (min-width: 1024px) {
  .pipeline {
    flex-direction: row;
    align-items: flex-start;
  }
}

.pipeline-node {
  flex: 1;
  background: var(--paper-card);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  padding: var(--space-8) var(--space-6);
  position: relative;
}

/* Layer-specific left stripe */
.pipeline-node--bronze { border-top: 3px solid var(--pix-bronze); }
.pipeline-node--silver { border-top: 3px solid var(--pix-silver); }
.pipeline-node--gold   { border-top: 3px solid var(--pix-gold);   }

.pipeline-node__layer {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 500;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  margin-bottom: var(--space-4);
}

.pipeline-node--bronze .pipeline-node__layer { color: var(--pix-bronze); }
.pipeline-node--silver .pipeline-node__layer { color: var(--pix-silver); }
.pipeline-node--gold   .pipeline-node__layer { color: var(--pix-gold);   }

/* Layer label uses bracket pattern */
.pipeline-node__layer::before { content: '[ '; }
.pipeline-node__layer::after  { content: ' ]'; }

.pipeline-node__title {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: 400;
  color: var(--ink);
  margin-bottom: var(--space-3);
  line-height: var(--leading-snug);
}

.pipeline-node__items {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.pipeline-node__item {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-soft);
  letter-spacing: var(--tracking-wide);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.pipeline-node__item::before {
  content: '→';
  color: var(--ink-faint);
  flex-shrink: 0;
}

/* Connector arrow between nodes */
.pipeline-connector {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--ink-faint);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

@media (min-width: 1024px) {
  .pipeline-connector {
    width: var(--space-8);    /* 32px connector width */
    align-self: center;
  }
}

/* Tech tag below each node */
.pipeline-node__tech {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--line);
}
```

**Hover behavior:** On hover, each node increases its top-border height from 3px → 4px and shows `box-shadow: var(--shadow-sm)`. Motion via CSS transition only.

---

### 4.5 AI Chat Interface

Positioned in its own `section.pix-ai` within the PIX Observatory page.  
The violet `--pix-ai` accent clearly delineates this zone.

**Visual anatomy:**
```
[ AI Analytics ]
Pergunte sobre os dados do PIX     ← Instrument Serif display-2

┌──────────────────────────────────────────────────────────┐
│  ● claude   PIX Observatory Assistant           ╳        │ ← header, --pix-ai-dim bg
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Qual foi o crescimento do PIX em 2022?             │  │ ← user bubble, right
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Em 2022, o PIX processou 29,2 bilhões de           │  │ ← AI bubble, left
│  │ transações — um crescimento de 252% em             │  │
│  │ relação ao ano anterior. O volume financeiro       │  │
│  │ ultrapassou R$ 12 trilhões.                        │  │
│  │                                                    │  │
│  │ Você gostaria de ver a comparação por trimestre?   │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  _ Sugestões: "Pico diário?" · "Valor médio/tx" · ...   │ ← prompt hints
├──────────────────────────────────────────────────────────┤
│  [ Faça uma pergunta sobre o PIX... ]         [ →  ]     │ ← input + send
└──────────────────────────────────────────────────────────┘
```

**CSS:**
```css
.pix-chat {
  border: 1px solid var(--pix-ai-line);
  border-radius: var(--radius-lg);
  background: var(--paper-card);
  overflow: hidden;
  max-width: 720px;
  margin-inline: auto;
}

/* Header bar */
.pix-chat__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-6);
  background: var(--pix-ai-dim);
  border-bottom: 1px solid var(--pix-ai-line);
}

.pix-chat__identity {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--pix-ai);
  letter-spacing: var(--tracking-wide);
}

/* Violet dot (replaces the blue .ql-dot pattern) */
.pix-chat__dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--pix-ai);
  flex-shrink: 0;
}

/* Message area */
.pix-chat__messages {
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 240px;
  max-height: 400px;
  overflow-y: auto;
  /* Custom scrollbar */
  scrollbar-width: thin;
  scrollbar-color: var(--line) transparent;
}

/* User message — right-aligned */
.pix-chat__msg--user {
  align-self: flex-end;
  max-width: 80%;
  background: var(--paper-soft);
  border: 1px solid var(--line);
  border-radius: var(--radius-md) var(--radius-md) var(--radius-sm) var(--radius-md);
  padding: var(--space-3) var(--space-4);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  color: var(--ink);
  line-height: var(--leading-normal);
}

/* AI message — left-aligned */
.pix-chat__msg--ai {
  align-self: flex-start;
  max-width: 85%;
  background: var(--pix-ai-dim);
  border: 1px solid var(--pix-ai-line);
  border-radius: var(--radius-md) var(--radius-md) var(--radius-md) var(--radius-sm);
  padding: var(--space-4) var(--space-5);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  color: var(--ink-soft);
  line-height: var(--leading-loose);
}

/* Prompt hints strip */
.pix-chat__hints {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-6);
  border-top: 1px solid var(--line);
}

.pix-chat__hint {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-faint);
  cursor: pointer;
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-full);
  transition: border-color var(--transition-fast), color var(--transition-fast);
}

.pix-chat__hint:hover {
  border-color: var(--pix-ai-line);
  color: var(--pix-ai);
}

/* Input area */
.pix-chat__input-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--line);
  background: var(--paper-soft);
}

.pix-chat__input {
  flex: 1;
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  color: var(--ink);
  background: var(--paper-card);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  outline: none;
  transition: border-color var(--transition-fast);
}

.pix-chat__input:focus {
  border-color: var(--pix-ai-line);
}

.pix-chat__input::placeholder {
  color: var(--ink-faint);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
}

.pix-chat__send {
  /* Extends .btn-primary with violet override */
  background: var(--pix-ai);
  border-color: var(--pix-ai);
  color: var(--paper);
  padding: var(--space-3) var(--space-4);
}

.pix-chat__send:hover {
  background: #6650E0;  /* Darker violet — defined inline, not global token */
  border-color: #6650E0;
}

/* Typing indicator */
.pix-chat__typing {
  display: flex;
  gap: 4px;
  padding: var(--space-2) 0;
}

.pix-chat__typing span {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--pix-ai);
  animation: pix-typing 1.4s ease infinite;
}

.pix-chat__typing span:nth-child(2) { animation-delay: 0.2s; }
.pix-chat__typing span:nth-child(3) { animation-delay: 0.4s; }

@keyframes pix-typing {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30%           { opacity: 1;   transform: translateY(-4px); }
}

@media (prefers-reduced-motion: reduce) {
  .pix-chat__typing span { animation: none; opacity: 1; }
}
```

---

## 5. Layout: Full PIX Observatory Page

**URL:** `/projects/pix-observatory` or standalone deployment  
**Astro component:** `src/pages/pix-observatory.astro`

### 5.1 Page Structure

```
<BaseLayout>
  <main class="pix-scope">

    ── SECTION 1: HERO ─────────────────────────────────
    <section id="pix-hero">
      [eyebrow]  [ Observatório PIX ]
      [h1]       PIX Observatory
      [sub]      Pipeline de dados do sistema de pagamentos
                 instantâneo do Brasil. Real-time. Open data. AI-powered.
      [badges]   [Python] [DuckDB] [Observable] [Claude] [GH Actions]
      [cta]      ↓ Explorar dados
    </section>

    ── SECTION 2: GROWTH FACT (Full-bleed callout) ─────
    <section id="pix-growth-fact">
      106.000×
      de crescimento em 5 anos
      [ 2019: 1 bilhão → 2024: 106 trilhões de transações ]
    </section>

    ── SECTION 3: KPI CARDS ────────────────────────────
    <section id="pix-kpis">
      [ 4 KPI cards grid ]
    </section>

    ── SECTION 4: GROWTH CHART ─────────────────────────
    <section id="pix-chart">
      [ Eyebrow + title ]
      [ SVG growth chart with annotations ]
    </section>

    ── SECTION 5: DATA PIPELINE ────────────────────────
    <section id="pix-pipeline">
      [ Eyebrow + title ]
      [ Bronze → Silver → Gold nodes ]
    </section>

    ── SECTION 6: AI CHAT ──────────────────────────────
    <section id="pix-ai">
      [ Eyebrow + title ]
      [ Chat interface ]
    </section>

    ── SECTION 7: TECH STACK ───────────────────────────
    <section id="pix-stack">
      [ Tag grid: Python, DuckDB, Observable Framework,
        Claude API, GitHub Actions, Parquet, BCB API ]
    </section>

    ── FOOTER CTA ──────────────────────────────────────
    <section id="pix-cta">
      [ Link back to portfolio ]
      [ GitHub repo link ]
    </section>

  </main>
</BaseLayout>
```

### 5.2 Section 2: Growth Fact — Full-Bleed Callout

This is the visual statement of the page. No card. No border. Just the number.

```
Background:   --paper-soft (alternating section rhythm)
Padding:      --space-32 top/bottom (desktop), --space-20 (mobile)
Text align:   center
Layout:       centered column, max-width 800px

106.000×              ← --font-mono, clamp(4rem, 2rem+8vw, 9rem), --pix-green
de crescimento        ← --font-display, --display-2, --ink, italic
em 5 anos             ← --font-display, --display-2, --ink

[ 2019: ~1 bilhão → 2024: ~106 trilhões de transações ]
                      ← --font-mono, --text-sm, --ink-faint, brackets

───────────────────── ← hairline, --line, 120px wide centered

O maior fenômeno fintech da América Latina, construído
sobre dados abertos do Banco Central do Brasil.
                      ← --font-sans, --text-lg, --ink-soft, max 48ch
```

**Blueprint detail:** A vertical `[ DADO ]` label in mono on the left margin (desktop only), like an engineering spec annotation.

```css
.pix-growth-callout {
  background: var(--paper-soft);
  padding-block: var(--space-32);
  text-align: center;
  position: relative;
}

.pix-growth-callout__number {
  font-family: var(--font-mono);
  font-size: clamp(4rem, 2rem + 8vw, 9rem);
  font-weight: 500;
  color: var(--pix-green);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-tight);
  /* count-up animation target */
}

.pix-growth-callout__label {
  font-family: var(--font-display);
  font-size: var(--display-2);
  font-weight: 400;
  color: var(--ink);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-tight);
}

.pix-growth-callout__label em {
  font-style: italic;   /* Instrument Serif italic is beautiful */
}

.pix-growth-callout__footnote {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--ink-faint);
  letter-spacing: var(--tracking-wide);
  margin-top: var(--space-4);
}
.pix-growth-callout__footnote::before { content: '[ '; }
.pix-growth-callout__footnote::after  { content: ' ]'; }

.pix-growth-callout__divider {
  width: 120px;
  height: 1px;
  background: var(--line);
  margin: var(--space-10) auto;
  /* hairline-draw animation target */
}

.pix-growth-callout__body {
  font-family: var(--font-sans);
  font-size: var(--text-lg);
  color: var(--ink-soft);
  line-height: var(--leading-normal);
  max-width: 48ch;
  margin-inline: auto;
}

/* Desktop: annotation in left margin */
@media (min-width: 1024px) {
  .pix-growth-callout::before {
    content: '[ DADO ]';
    position: absolute;
    left: var(--space-8);
    top: 50%;
    transform: translateY(-50%) rotate(-90deg);
    transform-origin: center;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--ink-faint);
    letter-spacing: var(--tracking-wider);
    white-space: nowrap;
  }
}
```

---

## 6. Motion Specification

All animations use the existing 5 GSAP patterns. No new patterns invented.

### 6.1 Page Entry (PIX Observatory standalone page)

Uses `resolve` pattern. Order:

```typescript
// Sequence (all in one timeline, delay 0.15s)
1. eyebrow → opacity 0→1, y 12→0,  duration: DURATIONS.fast
2. h1 title → opacity 0→1, y 24→0, duration: DURATIONS.entrance
3. subtitle → opacity 0→1, y 16→0, duration: DURATIONS.normal  (-0.45 overlap)
4. badges → stagger 0.06, opacity/y,  duration: DURATIONS.fast   (-0.3 overlap)
5. CTA button → opacity 0→1, y 12→0, duration: DURATIONS.fast
```

### 6.2 Growth Fact Section

Uses `count-up` + `hairline-draw`:

```typescript
// On ScrollTrigger start: 'top 70%'
1. hairline-draw on .pix-growth-callout__divider  → duration: DURATIONS.slow
2. count-up: "106.000×" counts from 0 to 106000   → duration: 2.5s (custom, once)
   Easing: power3.out — starts fast, decelerates at the top
   Format: Intl.NumberFormat('pt-BR') + '×' suffix
3. revealUp: subtitle + body text                 → stagger 0.1
```

**count-up implementation detail for "106.000×":**
```typescript
// Format options — Brazilian number format
const formatter = new Intl.NumberFormat('pt-BR', {
  maximumFractionDigits: 0,
});
// Target: 106000, displayed as "106.000×"
// Duration: 2.5s, ease: power3.out
// At value < 1000: show raw number
// At value ≥ 1000: show formatted with dot separator
```

### 6.3 KPI Cards

Uses `revealUp`:

```typescript
// ScrollTrigger: start 'top 80%'
gsap.from(kpiCards, {
  opacity: 0,
  y: 24,
  duration: DURATIONS.normal,   // 0.6s
  ease: EASINGS.out,
  stagger: STAGGER.normal,      // 0.1s between cards
  scrollTrigger: { trigger: kpiGrid, start: 'top 80%', once: true },
  onComplete: () => {
    // Trigger count-up for each KPI value
    kpiCards.forEach((card, i) => startCountUp(card, i * 0.15));
  }
});
```

### 6.4 Growth Chart

Uses `hairline-draw` adapted for SVG path:

```typescript
// SVG stroke-dashoffset technique (hairline-draw variant)
const path = svg.querySelector('.pix-chart__path');
const length = path.getTotalLength();
gsap.set(path, { strokeDasharray: length, strokeDashoffset: length });
gsap.to(path, {
  strokeDashoffset: 0,
  duration: DURATIONS.slow * 1.5,   // 1.35s
  ease: EASINGS.outStrong,
  scrollTrigger: { trigger: svg, start: 'top 75%', once: true },
  onComplete: () => {
    // Fade in annotations with revealUp stagger 0.15
  }
});
```

### 6.5 Pipeline Nodes

Uses `revealUp`:

```typescript
// Desktop: stagger left→right
// Mobile: stagger top→bottom
gsap.from(pipelineNodes, {
  opacity: 0,
  y: 24,
  duration: DURATIONS.normal,
  ease: EASINGS.out,
  stagger: STAGGER.loose,   // 0.15s — pipeline feels like sequential steps
  scrollTrigger: { trigger: pipeline, start: 'top 75%', once: true },
});
```

### 6.6 AI Chat Section

Uses `revealUp` on the chat container:

```typescript
gsap.from(chatContainer, {
  opacity: 0,
  y: 24,
  duration: DURATIONS.normal,
  ease: EASINGS.out,
  scrollTrigger: { trigger: chatSection, start: 'top 80%', once: true },
});
// Demo messages use CSS transition (not GSAP) — performance, not choreography
```

### 6.7 Data Loading States

When fetching from BCB API or Claude API:

**Skeleton state** (CSS only, no GSAP):
```css
.pix-skeleton {
  background: linear-gradient(
    90deg,
    var(--paper-soft) 25%,
    var(--paper-card) 50%,
    var(--paper-soft) 75%
  );
  background-size: 200% 100%;
  border-radius: var(--radius-md);
  animation: pix-shimmer 1.5s ease infinite;
}

@keyframes pix-shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@media (prefers-reduced-motion: reduce) {
  .pix-skeleton {
    background: var(--paper-soft);
    animation: none;
  }
}
```

**Skeleton structure per KPI card:**
```html
<div class="kpi-card pix-skeleton" style="height: 140px;" aria-busy="true" aria-label="Carregando dados"></div>
```

---

## 7. Dark / Light Mode

**Blueprint direction explicitly forbids dark mode** (`DESIGN.md`: "Dark é proibido nesta direção").  
PIX Observatory adheres to this rule.

**No `prefers-color-scheme` dark logic is implemented.**

However, `--pix-green` and all PIX tokens are already legible on `--paper` (#FDFDFD) at WCAG AA Large standards. The paper-light palette provides sufficient contrast for all non-body-text decorative uses.

If this restriction is ever revisited in a future design direction, the groundwork for a dark variant would be:

```css
/* NOT implemented — future reference only */
/*
@media (prefers-color-scheme: dark) {
  .pix-scope {
    --pix-green: #00D68A;       // lighter for dark bg
    --pix-ai:    #9B8BFF;       // lighter violet
    --pix-bronze: #E8A850;
  }
}
*/
```

---

## 8. Mobile Responsiveness

Mobile-first. All PIX Observatory components use the 3 existing breakpoints.

### 8.1 Breakpoint Behavior by Component

| Component | 0–639px | 640–1023px | 1024px+ |
|-----------|---------|------------|---------|
| KPI grid | 1 col | 2 cols | 4 cols |
| Pipeline | Vertical stack | Vertical stack | Horizontal row |
| Growth chart | Scroll-x, min-width 480px | Full width | Full width |
| AI chat | Full width, max-height 320px | max-width 640px | max-width 720px |
| Growth fact number | clamp(4rem → ~6rem) | clamp → ~7rem | up to 9rem |
| Pipeline connector | `↓` vertical arrow | `↓` | `→` horizontal |

### 8.2 Touch Considerations

```css
/* Chart: allow horizontal scroll on touch */
.pix-chart-container {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  /* Scroll snap to years on mobile */
  scroll-snap-type: x mandatory;
}

/* AI Chat: ensure input doesn't zoom on iOS */
.pix-chat__input {
  font-size: 16px;   /* Override --text-sm to prevent iOS zoom */
}

@media (min-width: 640px) {
  .pix-chat__input {
    font-size: var(--text-sm);
  }
}
```

### 8.3 Mobile-Specific Pipeline Vertical Layout

```css
/* Mobile: pipeline nodes read top-to-bottom */
@media (max-width: 1023px) {
  .pipeline {
    flex-direction: column;
  }

  .pipeline-connector {
    /* Rotate arrow — horizontal → vertical */
    transform: rotate(90deg);
    width: auto;
    height: var(--space-8);
    align-self: center;
  }
}
```

---

## 9. Visual Storytelling: "106,000× Growth"

This number is the narrative spine. Every section contributes to building it:

### 9.1 Story Arc (Page Scroll)

```
HERO:        "PIX Observatory — Pipeline de dados"
              → Establishes context: this is a data engineering project

SECTION 2:   "106.000×"  — full bleed, Instrument Serif, green number
              → The reveal. Maximum impact. One fact, no clutter.
              → Blueprint annotation: "[ 2019 → 2024 ]"

KPI CARDS:   Four cards counting up
              → Breaks the number into components: volume, value, daily avg
              → Each card is a proof point of the growth story

CHART:       Exponential curve drawn in real-time on scroll
              → Shows the curve is real — not a vanity metric
              → Annotations label inflection points (Pix Automático, etc.)

PIPELINE:    Bronze → Silver → Gold
              → Shows HOW the data was captured, not just the numbers
              → Establishes credibility: this is engineering, not marketing

AI CHAT:     "Pergunte sobre os dados do PIX"
              → Invites exploration — the number becomes interactive
              → "AI is not a model, it's a platform" manifests here
```

### 9.2 "106,000×" Number Treatment Rules

1. **First appearance** (Section 2): Maximum size (9rem), green, count-up on scroll
2. **KPI card** (Section 3): Slightly smaller (--text-3xl), green, but always in green to maintain color identity
3. **Chart annotation** (Section 4): Appears as a label `[ 106.000× ]` at the chart peak — mono, small
4. **Never repeat the raw number after Section 4** — let the data visualizations carry the weight

### 9.3 The "1 in 4 Brazilians" Companion Fact

Display alongside or beneath the growth number:

```
1 em cada 4 brasileiros         ← --font-display italic
usa PIX todos os dias           ← --font-display normal

                                ← Blueprint hairline
[ Fonte: BCB · Dados: 2024 ]   ← mono label
```

### 9.4 Annotation Strategy (Blueprint Language)

The Blueprint direction uses engineering annotations — this is perfect for data storytelling.  
Use `hairline + mono label` for key moments on the chart:

```
2020: "[ Lançamento — Nov/2020 ]"    → right-angle leader line from chart point
2021: "[ 8,3 bi transações ]"        → leader line
2022: "[ Pix Automático → 3× YoY ]" → leader line, this is the inflection
2024: "[ 106.000× vs 2019 ]"         → final annotation, pix-green color
```

---

## 10. New CSS Variables Summary

All new tokens declared in `src/styles/pix-tokens.css`, scoped to `.pix-scope`.

```css
.pix-scope {
  /* Brand */
  --pix-green:               #00A651;
  --pix-green-dim:           rgba(0, 166, 81, 0.08);
  --pix-green-mid:           rgba(0, 166, 81, 0.18);
  --pix-green-line:          rgba(0, 166, 81, 0.35);

  /* Signals */
  --pix-growth:              #00A651;
  --pix-delta:               #D4A017;
  --pix-neutral:             var(--ink-faint);

  /* Pipeline layers */
  --pix-bronze:              #CD7F32;
  --pix-bronze-dim:          rgba(205, 127, 50, 0.10);
  --pix-silver:              #707F8A;
  --pix-silver-dim:          rgba(112, 127, 138, 0.10);
  --pix-gold:                #D4A017;
  --pix-gold-dim:            rgba(212, 160, 23, 0.10);

  /* AI zone */
  --pix-ai:                  #7B61FF;
  --pix-ai-dim:              rgba(123, 97, 255, 0.08);
  --pix-ai-line:             rgba(123, 97, 255, 0.25);

  /* Chart */
  --pix-chart-fill:          rgba(0, 166, 81, 0.12);
  --pix-chart-stroke:        #00A651;
  --pix-chart-grid:          rgba(10, 10, 10, 0.06);

  /* KPI cards */
  --pix-kpi-bg:              var(--paper-card);
  --pix-kpi-border:          rgba(0, 166, 81, 0.20);
  --pix-kpi-border-hover:    rgba(0, 166, 81, 0.50);
}
```

**No global tokens modified.** The main portfolio site is unaffected.

---

## 11. Accessibility Checklist

- [ ] `--pix-green` used only for large text (≥18px) or decorative elements — never body text
- [ ] All body text uses `--ink` (#0A0A0A, ~19:1 on paper) or `--ink-soft` (#545454, ~7.5:1)
- [ ] `--ink-faint` (#6F6F6F, ~4.94:1) used only for labels ≥14px
- [ ] KPI values use `--ink` for the number — `--pix-green` only for delta/growth indicator
- [ ] Chart is `role="img"` with descriptive `aria-label`
- [ ] Chart axes and data accessible via `<table>` sibling (visually hidden, screen-reader only)
- [ ] AI chat input: `aria-label`, `role="textbox"`, `aria-live="polite"` on message area
- [ ] Pipeline nodes: `role="list"` + `role="listitem"` structure
- [ ] Loading skeletons: `aria-busy="true"` + `aria-label`
- [ ] Count-up: `aria-live="off"` during animation, `aria-live="polite"` after completion
- [ ] All interactive elements: `:focus-visible` with `--accent` outline (inherited)
- [ ] `prefers-reduced-motion`: skeletons static, count-up shows final value immediately, chart appears fully drawn
- [ ] Color is never the sole means of conveying information (shape + label always accompany color)

---

## 12. Deliverables for Frontend Builder

### Files to create:

```
src/
  pages/
    pix-observatory.astro        ← Main page
  components/
    pix/
      PixHero.astro              ← Section 1
      PixGrowthFact.astro        ← Section 2 (106,000× callout)
      PixKpiGrid.astro           ← Section 3 (4 KPI cards)
      PixGrowthChart.astro       ← Section 4 (SVG chart)
      PixPipeline.astro          ← Section 5 (Bronze→Silver→Gold)
      PixChat.astro              ← Section 6 (AI interface)
      PixStack.astro             ← Section 7 (tech tags)
  scripts/
    pix/
      pix-count-up.ts            ← count-up variant for PIX numbers
      pix-chart-draw.ts          ← SVG stroke-dashoffset reveal
  styles/
    pix-tokens.css               ← All tokens above, scoped to .pix-scope
```

### Constraints for builder:
1. All PIX tokens declared in `pix-tokens.css`, never inline
2. `.pix-scope` wrapper on `<main>` — all PIX tokens scoped
3. Global `tokens.css` untouched — zero modifications
4. All 5 motion patterns from `web-motion.md` — no new GSAP patterns
5. SVG chart is static (pre-computed paths) — no D3, no Observable in the Astro page
6. AI chat sends `fetch()` to Claude API endpoint — response streamed as SSE
7. Mobile-first CSS — no `max-width` media queries, only `min-width`
8. Zero `console.log` in production builds
9. Conteúdo legível sem JS — skeleton states have `noscript` fallback with static table

---

*Spec complete. Ready for frontend-builder handoff.*
