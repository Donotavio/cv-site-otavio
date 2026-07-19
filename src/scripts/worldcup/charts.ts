/**
 * World Cup Dashboard — inline-SVG chart library
 * ================================================
 *
 * Framework-agnostic, dependency-free chart primitives that render hand-rolled
 * inline SVG into a DOM container. Written to replace the 10 Chart.js charts of
 * the legacy `public/world-cup-dashboard/` app during its migration into Astro,
 * following the SAME hand-rolled-SVG pattern already used by the other Astro
 * sub-projects (`brasil-cockpit.astro` → `bandChart`/`trendChart`,
 * `eleicoes-2026.astro` → `renderBarChart`/`attachChartHover`/`niceTicks`).
 *
 * Design rules honoured (see `.opencode/skills/design-system.md` + dataviz):
 *  - Palette is the World Cup family ONLY: `--wc-field-ink` (data / home / 2022),
 *    `--wc-gold-ink` (highlight / away / 2026), plus the neutral ink/paper/line
 *    ramp. NEVER the portfolio navy/cyan. No hardcoded hex — every colour is read
 *    from a CSS custom property via `getComputedStyle` (with a fallback).
 *  - One axis only, recessive gridlines, thin marks, rounded data-ends.
 *  - Accessible: each `<svg>` is `role="img"` + caller-supplied `ariaLabel`; the
 *    hover tooltip is purely decorative (`aria-hidden`).
 *  - Reduced-motion aware: honours `prefers-reduced-motion` (or an explicit
 *    `reduce` flag). When motion is allowed, bars/segments/lines reveal via CSS
 *    transitions triggered by an IntersectionObserver — matching the page's
 *    reveal choreography — with no layout thrash.
 *  - Idempotent: every render clears its container first, so calling again after
 *    an SPA (`astro:page-load`) navigation is safe.
 *
 * The library injects ONE `<style>` block (id `wc-charts-css`) into `<head>` the
 * first time any chart renders, and creates ONE shared floating tooltip element.
 * Both are guarded, so nothing is duplicated across charts or re-renders.
 *
 * ── Chart → primitive map (the 10 legacy charts) ──────────────────────────────
 *   1. #chart-halves            → doughnutChart()  (gols 1º vs 2º tempo)
 *   2. #chart-minutes           → barChart({orientation:'v'})  (gols/faixa-minuto)
 *   3. #chart-efficiency        → barChart({orientation:'h', diverging:true})
 *   4. #chart-momentum          → lineChart()  (2 séries acumuladas home/away)
 *   5. c22-team-chart           → barChart({orientation:'h'})  (ranking por métrica)
 *   6. c22-finishing-chart      → barChart({orientation:'h', diverging:true})  (gols−xG)
 *   7. c22-minute-chart         → barChart({orientation:'v', series:[..]})  (2022 vs 2026)
 *   8. c22-hist-champions       → barChart({orientation:'h'})  (títulos)
 *   9. c22-hist-participations  → barChart({orientation:'h'})  (participações)
 *  10. (momentum minute-overlay variant, if ever split) → lineChart() / barChart()
 *
 * @module worldcup/charts
 */

/* ────────────────────────────────────────────────────────────────────────── */
/* Types                                                                        */
/* ────────────────────────────────────────────────────────────────────────── */

const SVG_NS = 'http://www.w3.org/2000/svg';

/** A single tooltip line: a name/label on the left, a formatted value on the right. */
export interface TipRow {
  name: string;
  value: string;
  /** Renders the row in `--wc-gold-ink` (used for the leader / highlighted item). */
  leader?: boolean;
}

/** Structured tooltip content returned by a chart's `tooltip` formatter. */
export interface TipContent {
  /** Optional bold heading (e.g. the category label). */
  title?: string;
  rows: TipRow[];
}

/** One bar. Use `value` for single-series charts, `values` for grouped charts. */
export interface BarDatum {
  label: string;
  /** Single-series value. Signed values are allowed when `diverging` is set. */
  value?: number;
  /** Grouped-series values, one per entry in `BarChartOpts.series`. */
  values?: number[];
  /** Per-bar colour (a CSS colour string or token value). Overrides the default. */
  color?: string;
  /** Marks this bar as the highlight → painted `--wc-gold-ink` unless `color` set. */
  highlight?: boolean;
  /** Arbitrary payload handed back to the `tooltip` formatter. */
  meta?: unknown;
}

export interface BarChartOpts {
  data: BarDatum[];
  /** 'h' = horizontal bars (category on Y); 'v' = vertical bars (category on X). Default 'v'. */
  orientation?: 'h' | 'v';
  /** Required for accessibility — becomes the SVG `aria-label`. */
  ariaLabel: string;
  /** Format a numeric value for axis ticks + on-bar labels. Default: `String`. */
  valueFmt?: (v: number) => string;
  /** Title printed alongside the value axis (e.g. "saldo de gols por partida"). */
  axisTitle?: string;
  /** Allow negative values → zero baseline in the middle, bars grow both ways. */
  diverging?: boolean;
  /** Draw the value at the end of each bar (single-series only). Default true. */
  showValues?: boolean;
  /** Grouped mode: one entry per series; each `BarDatum.values[i]` maps to `series[i]`. */
  series?: { label: string; color?: string }[];
  /** Tooltip content per bar/group. If omitted a default (label + value) is shown. */
  tooltip?: (d: BarDatum, index: number) => TipContent;
  /** Force-disable reveal animation. Defaults to the `prefers-reduced-motion` query. */
  reduce?: boolean;
  /** Override the intrinsic viewBox width (default 720). */
  width?: number;
  /** Vertical-chart height (default 260). Horizontal charts auto-size by row count. */
  height?: number;
}

export interface DoughnutSegment {
  label: string;
  value: number;
  /** CSS colour string / token value. Defaults cycle field-ink → gold-ink → ink-soft. */
  color?: string;
}

export interface DoughnutOpts {
  segments: DoughnutSegment[];
  ariaLabel: string;
  /** Big number shown in the hole (e.g. total). */
  centerLabel?: string;
  /** Small caption under the center label. */
  centerSub?: string;
  /** Format each segment value for the tooltip / legend. Default `String`. */
  valueFmt?: (v: number) => string;
  /** Draw a legend row beneath the ring. Default true. */
  legend?: boolean;
  reduce?: boolean;
  /** viewBox side length (default 220). */
  size?: number;
}

export interface LinePoint {
  x: number;
  y: number;
}

export interface LineSeries {
  label: string;
  points: LinePoint[];
  /** CSS colour string / token value. Defaults: series 0 field-ink, series 1 gold-ink. */
  color?: string;
}

export interface LineChartOpts {
  series: LineSeries[];
  ariaLabel: string;
  xTitle?: string;
  yTitle?: string;
  /** Format the y value for ticks + tooltip. Default `String`. */
  valueFmt?: (v: number) => string;
  /** Format an x value for the tooltip heading. Default `String`. */
  xFmt?: (x: number) => string;
  /** Draw a legend beneath the plot. Default true. */
  legend?: boolean;
  reduce?: boolean;
  width?: number;
  height?: number;
}

/** One radar series: a label, one value per axis (same order as `axes`), an optional colour. */
export interface RadarSeries {
  label: string;
  /** One value per axis, in the SAME order as `RadarChartOpts.axes`. */
  values: number[];
  /** CSS colour string / token value. Defaults: series 0 field-ink, series 1 gold-ink. */
  color?: string;
}

export interface RadarChartOpts {
  /** Axis labels, one per spoke (N ≥ 3 recommended). Order maps to each series' `values[i]`. */
  axes: string[];
  /** 1–2 series drawn as filled semi-transparent polygons. */
  series: RadarSeries[];
  /** Required for accessibility — becomes the SVG `aria-label`. */
  ariaLabel: string;
  /**
   * Normalisation control. When set, EVERY axis uses this value as its 100 % reach
   * — pass `1` when the series values are already normalised to 0..1. When omitted
   * (default), each axis is normalised INDEPENDENTLY by its own max across all
   * series (so every metric keeps its own scale). Raw values still show in the tooltip.
   */
  max?: number;
  /** Format a raw value for the tooltip. `axisIdx` lets you pick a per-axis unit. Default `String`. */
  valueFmt?: (v: number, axisIdx: number) => string;
  /** Force-disable reveal animation. Defaults to the `prefers-reduced-motion` query. */
  reduce?: boolean;
  /** viewBox side length (default 300). */
  size?: number;
}

/* ────────────────────────────────────────────────────────────────────────── */
/* Shared infrastructure: tokens, tick maths, escaping, CSS, tooltip           */
/* ────────────────────────────────────────────────────────────────────────── */

/**
 * Resolve a CSS custom property to its computed value, with a fallback. Mirrors
 * the `token()` helper of the legacy dashboard. Colours therefore always come
 * from `src/styles/tokens.css` — never hardcoded here.
 */
export function readToken(name: string, fallback: string): string {
  if (typeof window === 'undefined' || typeof document === 'undefined') return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

/** The World Cup chart palette, resolved once per render. */
function palette() {
  return {
    field: readToken('--wc-field-ink', '#0B6B2E'), // data / home / 2022
    gold: readToken('--wc-gold-ink', '#8A5A06'),   // highlight / away / 2026
    ink: readToken('--ink', '#0A0A0A'),
    inkSoft: readToken('--ink-soft', '#545454'),
    inkFaint: readToken('--ink-faint', '#6F6F6F'),
    line: readToken('--line', 'rgba(10,10,10,0.12)'),
    lineStrong: readToken('--line-strong', 'rgba(10,10,10,0.25)'),
    paperCard: readToken('--paper-card', '#FFFFFF'),
  };
}

/** True when the user asked for reduced motion (unless explicitly overridden). */
function prefersReduce(explicit?: boolean): boolean {
  if (explicit != null) return explicit;
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** "Nice" step for an axis range — from eleicoes-2026 / brasil-cockpit. */
function niceNum(range: number, round: boolean): number {
  const exp = Math.floor(Math.log10(range || 1));
  const frac = (range || 1) / Math.pow(10, exp);
  let n: number;
  if (round) { if (frac < 1.5) n = 1; else if (frac < 3) n = 2; else if (frac < 7) n = 5; else n = 10; }
  else { if (frac <= 1) n = 1; else if (frac <= 2) n = 2; else if (frac <= 5) n = 5; else n = 10; }
  return n * Math.pow(10, exp);
}

/**
 * Rounded, evenly-spaced axis ticks spanning [min, max]. Returns the tick array
 * and the (rounded-out) domain bounds actually used. Handles negatives so the
 * diverging bar charts get a symmetric-ish, human-readable scale.
 */
function niceTicks(min: number, max: number, n = 5): { ticks: number[]; niceMin: number; niceMax: number } {
  if (max <= min) max = min + 1;
  const step = niceNum((max - min) / (n - 1), true);
  const niceMin = Math.floor(min / step) * step;
  const niceMax = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = niceMin; v <= niceMax + step * 0.5; v += step) ticks.push(Math.round(v * 1e6) / 1e6);
  return { ticks, niceMin, niceMax };
}

/** Escape text destined for SVG/HTML text nodes. */
function esc(s: string): string {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/**
 * Inject the library's single stylesheet once. All presentation lives here so
 * the library is self-contained (the consuming Astro page needs no extra CSS).
 * Selectors are namespaced under `.wc-chart` and never touch global elements.
 */
function ensureStyles(): void {
  if (typeof document === 'undefined' || document.getElementById('wc-charts-css')) return;
  const css = `
.wc-chart { position: relative; }
.wc-chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.wc-chart text { font-family: var(--font-mono, 'IBM Plex Mono', monospace); }
.wc-chart .wc-grid { stroke: var(--line, rgba(10,10,10,0.12)); stroke-width: 1; }
.wc-chart .wc-axis { stroke: var(--line-strong, rgba(10,10,10,0.25)); stroke-width: 1; }
.wc-chart .wc-tick { font-size: 10px; fill: var(--ink-faint, #6F6F6F); font-variant-numeric: var(--num-tabular, tabular-nums); }
.wc-chart .wc-cat { font-size: 11px; fill: var(--ink-soft, #545454); }
.wc-chart .wc-axis-title { font-size: 10px; fill: var(--ink-faint, #6F6F6F); }
.wc-chart .wc-val { font-size: 10px; fill: var(--ink-soft, #545454); font-variant-numeric: var(--num-tabular, tabular-nums); }
.wc-chart .wc-line { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; vector-effect: non-scaling-stroke; }
.wc-chart .wc-marker { stroke: var(--paper-card, #fff); stroke-width: 1.5; }
.wc-chart .wc-guide { stroke: var(--line-strong, rgba(10,10,10,0.25)); stroke-width: 1; stroke-dasharray: 3 3; pointer-events: none; }
.wc-chart .wc-hoverdot { stroke: var(--paper-card, #fff); stroke-width: 1.5; pointer-events: none; }
.wc-chart .wc-capture { fill: transparent; }
/* radar */
.wc-chart .wc-radar-ring { fill: none; stroke: var(--line, rgba(10,10,10,0.12)); stroke-width: 1; }
.wc-chart .wc-radar-spoke { stroke: var(--line, rgba(10,10,10,0.12)); stroke-width: 1; }
.wc-chart .wc-radar-axis { font-size: 11px; fill: var(--ink-soft, #545454); }
.wc-chart .wc-radar-poly { stroke-width: 2; stroke-linejoin: round; fill-opacity: 0.14; vector-effect: non-scaling-stroke; }
.wc-chart .wc-radar-vertex { stroke: var(--paper-card, #fff); stroke-width: 1.5; }
.wc-chart-legend { display: flex; flex-wrap: wrap; gap: var(--space-2, 8px) var(--space-4, 16px); margin-top: var(--space-3, 12px); font-family: var(--font-mono, monospace); font-size: var(--text-xs, 0.8rem); color: var(--ink-soft, #545454); }
.wc-chart-legend > span { display: inline-flex; align-items: center; gap: var(--space-2, 8px); }
.wc-chart-legend .wc-sw { width: 10px; height: 10px; border-radius: 2px; flex: 0 0 auto; }
/* Reveal animation (opt-in via .wc-chart--anim; skipped entirely under reduced-motion) */
.wc-chart--anim .wc-bar { transform: scale(0); transform-box: fill-box; transition: transform 0.7s cubic-bezier(0.16, 1, 0.3, 1); }
.wc-chart--anim.is-in .wc-bar { transform: scale(1); }
.wc-chart--anim .wc-seg { opacity: 0; transform: scale(0.6); transform-origin: center; transform-box: view-box; transition: opacity 0.5s ease, transform 0.6s cubic-bezier(0.16, 1, 0.3, 1); }
.wc-chart--anim.is-in .wc-seg { opacity: 1; transform: scale(1); }
.wc-chart--anim .wc-line { stroke-dasharray: 1; stroke-dashoffset: 1; transition: stroke-dashoffset 1s ease; }
.wc-chart--anim.is-in .wc-line { stroke-dashoffset: 0; }
.wc-chart--anim .wc-marker, .wc-chart--anim .wc-val, .wc-chart--anim .wc-endlabel { opacity: 0; transition: opacity 0.4s ease 0.4s; }
.wc-chart--anim.is-in .wc-marker, .wc-chart--anim.is-in .wc-val, .wc-chart--anim.is-in .wc-endlabel { opacity: 1; }
.wc-chart--anim .wc-radar-poly { opacity: 0; transform: scale(0.6); transform-origin: center; transform-box: view-box; transition: opacity 0.5s ease, transform 0.6s cubic-bezier(0.16, 1, 0.3, 1); }
.wc-chart--anim.is-in .wc-radar-poly { opacity: 1; transform: scale(1); }
.wc-chart--anim .wc-radar-vertex { opacity: 0; transition: opacity 0.4s ease 0.4s; }
.wc-chart--anim.is-in .wc-radar-vertex { opacity: 1; }
@media (prefers-reduced-motion: reduce) {
  .wc-chart--anim .wc-bar, .wc-chart--anim .wc-seg, .wc-chart--anim .wc-marker,
  .wc-chart--anim .wc-val, .wc-chart--anim .wc-endlabel,
  .wc-chart--anim .wc-radar-poly, .wc-chart--anim .wc-radar-vertex { transform: none; opacity: 1; transition: none; }
  .wc-chart--anim .wc-line { stroke-dasharray: none; stroke-dashoffset: 0; transition: none; }
}
.wc-chart-tip { position: fixed; z-index: 300; pointer-events: none; min-width: 132px; max-width: 260px; padding: var(--space-3, 12px) var(--space-4, 16px); background: var(--paper-card, #fff); border: 1px solid var(--line-strong, rgba(10,10,10,0.25)); border-radius: var(--radius-sm, 4px); box-shadow: var(--shadow-md, 0 8px 32px rgba(0,0,0,0.12)); font-family: var(--font-mono, monospace); font-size: var(--text-xs, 0.8rem); color: var(--ink, #0A0A0A); line-height: 1.5; }
.wc-chart-tip[hidden] { display: none; }
.wc-chart-tip .wc-tip-head { color: var(--ink-faint, #6F6F6F); text-transform: uppercase; letter-spacing: var(--tracking-wide, 0.05em); margin-bottom: var(--space-2, 8px); }
.wc-chart-tip .wc-tip-row { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-4, 16px); }
.wc-chart-tip .wc-tip-row + .wc-tip-row { margin-top: 2px; }
.wc-chart-tip .wc-tip-name { color: var(--ink-soft, #545454); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wc-chart-tip .wc-tip-val { color: var(--ink, #0A0A0A); font-variant-numeric: var(--num-tabular, tabular-nums); }
.wc-chart-tip .wc-tip-row.is-leader .wc-tip-name, .wc-chart-tip .wc-tip-row.is-leader .wc-tip-val { color: var(--wc-gold-ink, #8A5A06); }
`;
  const style = document.createElement('style');
  style.id = 'wc-charts-css';
  style.textContent = css;
  document.head.appendChild(style);
}

/** Lazily create the single shared floating tooltip element. */
function mountTip(): HTMLElement | null {
  if (typeof document === 'undefined') return null;
  let tip = document.getElementById('wc-chart-tip');
  if (!tip) {
    tip = document.createElement('div');
    tip.id = 'wc-chart-tip';
    tip.className = 'wc-chart-tip';
    tip.setAttribute('role', 'presentation');
    tip.setAttribute('aria-hidden', 'true');
    tip.hidden = true;
    document.body.appendChild(tip);
  }
  return tip;
}

/** Render a `TipContent` object into the shared tooltip's innerHTML. */
function tipHTML(c: TipContent): string {
  const head = c.title ? `<div class="wc-tip-head">${esc(c.title)}</div>` : '';
  const rows = c.rows.map(
    (r) => `<div class="wc-tip-row${r.leader ? ' is-leader' : ''}"><span class="wc-tip-name">${esc(r.name)}</span><span class="wc-tip-val">${esc(r.value)}</span></div>`,
  ).join('');
  return head + rows;
}

/** Position the shared fixed tooltip near the pointer, flipping at viewport edges. */
function placeTip(tip: HTMLElement, e: PointerEvent): void {
  const tw = tip.offsetWidth, th = tip.offsetHeight;
  let left = e.clientX + 14, top = e.clientY + 14;
  if (left + tw > window.innerWidth - 8) left = e.clientX - tw - 14;
  if (top + th > window.innerHeight - 8) top = e.clientY - th - 14;
  tip.style.left = Math.max(8, left) + 'px';
  tip.style.top = Math.max(8, top) + 'px';
}

/**
 * Wire a chart's reveal animation. When motion is allowed, adds `wc-chart--anim`
 * and flips `is-in` the first time the container scrolls into view (mirroring the
 * page's IntersectionObserver reveal). Under reduced-motion, does nothing — the
 * SVG is already in its final state.
 */
function armReveal(box: HTMLElement, reduce: boolean): void {
  if (reduce || typeof IntersectionObserver === 'undefined') return;
  box.classList.add('wc-chart--anim');
  const io = new IntersectionObserver((entries, obs) => {
    entries.forEach((en) => {
      if (en.isIntersecting) { box.classList.add('is-in'); obs.disconnect(); }
    });
  }, { threshold: 0.15 });
  io.observe(box);
}

/** Empty a container (idempotency for SPA re-renders). */
function clear(box: HTMLElement): void { while (box.firstChild) box.removeChild(box.firstChild); }

/**
 * Generic bar-chart hover: attach pointer handling to the rendered `<svg>`,
 * mapping the pointer to a bar/group index via caller-supplied hit-testing.
 */
function attachBarHover(
  box: HTMLElement,
  hit: (px: number, py: number, W: number, H: number) => number,
  content: (idx: number) => TipContent | null,
): void {
  const svg = box.querySelector('svg'); const tip = mountTip();
  if (!svg || !tip) return;
  const vb = (svg.getAttribute('viewBox') || '0 0 720 260').split(/\s+/).map(Number);
  const W = vb[2] || 720, H = vb[3] || 260;
  const hide = (): void => { tip.hidden = true; };
  svg.addEventListener('pointermove', (e) => {
    const r = svg.getBoundingClientRect(); if (!r.width) return;
    const px = ((e.clientX - r.left) / r.width) * W;
    const py = ((e.clientY - r.top) / r.height) * H;
    const idx = hit(px, py, W, H);
    const c = idx >= 0 ? content(idx) : null;
    if (!c) { hide(); return; }
    tip.innerHTML = tipHTML(c); tip.hidden = false;
    placeTip(tip, e);
  });
  svg.addEventListener('pointerleave', hide);
}

/* ────────────────────────────────────────────────────────────────────────── */
/* barChart                                                                     */
/* ────────────────────────────────────────────────────────────────────────── */

/**
 * Render a bar chart (single-series or grouped) as inline SVG into `container`.
 * Covers 7 of the 10 legacy charts: the vertical minute-bars (#chart-minutes),
 * the horizontal rankings (#chart-efficiency, c22-team-chart, c22-hist-champions,
 * c22-hist-participations), the diverging goals−xG bars (c22-finishing-chart via
 * `diverging:true` + signed values), and the 2-series minute overlay
 * (c22-minute-chart via `series:[{...},{...}]` + `BarDatum.values`).
 *
 * Highlight a bar with `highlight:true` (→ `--wc-gold-ink`) or an explicit
 * per-bar `color`. Diverging charts colour by sign at the call site (pass
 * `color` per bar). Value labels render at each bar's growing end.
 *
 * @example Horizontal ranking (efficiency top-8, #1 in gold)
 * barChart(document.getElementById('chart-eff')!, {
 *   orientation: 'h',
 *   ariaLabel: 'Saldo de gols por partida — top 8',
 *   axisTitle: 'saldo de gols por partida',
 *   valueFmt: (v) => v.toFixed(2),
 *   data: eff.map((t, i) => ({ label: `${t.flag} ${t.name}`, value: t.diff_per_match, highlight: i === 0, meta: t })),
 *   tooltip: (d) => ({ title: (d.meta as any).name, rows: [{ name: 'saldo/jogo', value: (d.value ?? 0).toFixed(2) }] }),
 * });
 *
 * @example Grouped vertical (minute overlay 2022 vs 2026)
 * barChart(el, {
 *   orientation: 'v', ariaLabel: 'Gols por faixa de minuto — 2022 vs 2026',
 *   axisTitle: '% dos gols', valueFmt: (v) => v + '%',
 *   series: [{ label: 'Copa 2022' }, { label: 'Copa 2026', color: readToken('--wc-gold-ink','#8A5A06') }],
 *   data: ranges.map((r) => ({ label: r.range, values: [r.p2022, r.p2026] })),
 * });
 */
export function barChart(container: HTMLElement, opts: BarChartOpts): void {
  ensureStyles();
  clear(container);
  container.classList.add('wc-chart');
  const P = palette();
  const reduce = prefersReduce(opts.reduce);
  const data = opts.data || [];
  if (!data.length) { container.innerHTML = '<p class="mono-label" style="color:var(--ink-faint)">série indisponível</p>'; return; }

  const orient = opts.orientation ?? 'v';
  const fmt = opts.valueFmt ?? ((v: number) => String(v));
  const showValues = opts.showValues ?? true;
  const grouped = Array.isArray(opts.series) && opts.series.length > 0;
  const nSeries = grouped ? opts.series!.length : 1;
  const seriesColor = (si: number): string =>
    (grouped && opts.series![si].color) || (si === 1 ? P.gold : P.field);

  // Flatten all values to size the value axis.
  const allVals: number[] = [];
  data.forEach((d) => {
    if (grouped) (d.values ?? []).forEach((v) => allVals.push(v));
    else allVals.push(d.value ?? 0);
  });
  const rawMin = Math.min(0, ...allVals);
  const rawMax = Math.max(0, ...allVals);
  const diverging = opts.diverging || rawMin < 0;
  const { ticks, niceMin, niceMax } = niceTicks(
    diverging ? rawMin * 1.08 : 0,
    rawMax * 1.08 || 1,
    5,
  );
  const domMin = diverging ? niceMin : 0;
  const domMax = niceMax || 1;
  const span = domMax - domMin || 1;

  const W = opts.width ?? 720;
  const catN = data.length;

  const svgParts: string[] = [];
  let H: number;

  if (orient === 'h') {
    // Horizontal: category on Y (rows), value on X (bottom). Auto-size height.
    const rowH = 26;
    const PAD = { l: 150, r: 16, t: 8, b: opts.axisTitle ? 40 : 24 };
    H = PAD.t + PAD.b + catN * rowH;
    const plotW = W - PAD.l - PAD.r;
    const xAt = (v: number) => PAD.l + ((v - domMin) / span) * plotW;
    const zeroX = xAt(0);

    ticks.forEach((tk) => {
      const xx = xAt(tk);
      svgParts.push(`<line class="wc-grid" x1="${xx.toFixed(1)}" y1="${PAD.t}" x2="${xx.toFixed(1)}" y2="${(H - PAD.b).toFixed(1)}"></line>`);
      svgParts.push(`<text class="wc-tick" x="${xx.toFixed(1)}" y="${(H - PAD.b + 14).toFixed(1)}" text-anchor="middle">${esc(fmt(tk))}</text>`);
    });
    svgParts.push(`<line class="wc-axis" x1="${zeroX.toFixed(1)}" y1="${PAD.t}" x2="${zeroX.toFixed(1)}" y2="${(H - PAD.b).toFixed(1)}"></line>`);

    data.forEach((d, i) => {
      const v = d.value ?? 0;
      const cy = PAD.t + i * rowH;
      const bh = Math.min(rowH * 0.62, 22);
      const by = cy + (rowH - bh) / 2;
      const x0 = xAt(Math.min(0, v)), x1 = xAt(Math.max(0, v));
      const bw = Math.max(0, x1 - x0);
      const fill = d.color || (d.highlight ? P.gold : P.field);
      // Reveal grows from the zero baseline: origin at the fixed (zero) end.
      const originX = v >= 0 ? x0 : x1;
      svgParts.push(`<rect class="wc-bar" x="${x0.toFixed(1)}" y="${by.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="2" fill="${fill}" style="transform-origin:${originX.toFixed(1)}px ${(by + bh / 2).toFixed(1)}px"></rect>`);
      // Category label (left, truncated by CSS-free ellipsis substring).
      svgParts.push(`<text class="wc-cat" x="${(PAD.l - 8).toFixed(1)}" y="${(cy + rowH / 2 + 4).toFixed(1)}" text-anchor="end">${esc(d.label)}</text>`);
      if (showValues) {
        const lx = v >= 0 ? x1 + 5 : x0 - 5;
        svgParts.push(`<text class="wc-val" x="${lx.toFixed(1)}" y="${(cy + rowH / 2 + 4).toFixed(1)}" text-anchor="${v >= 0 ? 'start' : 'end'}">${esc(fmt(v))}</text>`);
      }
    });
    if (opts.axisTitle) svgParts.push(`<text class="wc-axis-title" x="${((PAD.l + W - PAD.r) / 2).toFixed(1)}" y="${(H - 6).toFixed(1)}" text-anchor="middle">${esc(opts.axisTitle)}</text>`);

    svgParts.push(`<rect class="wc-capture" x="0" y="0" width="${W}" height="${H}"></rect>`);
    container.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.ariaLabel)}">${svgParts.join('')}</svg>`;

    attachBarHover(container,
      (_px, py) => { const i = Math.floor((py - PAD.t) / rowH); return i >= 0 && i < catN ? i : -1; },
      (i) => defaultOrCustomTip(opts, data[i], i, fmt));
  } else {
    // Vertical: category on X, value on Y (left). Fixed height.
    H = opts.height ?? 260;
    const PAD = { l: 44, r: 12, t: 20, b: opts.axisTitle ? 46 : 34 };
    const plotW = W - PAD.l - PAD.r, plotH = H - PAD.t - PAD.b;
    const yAt = (v: number) => PAD.t + (1 - (v - domMin) / span) * plotH;
    const zeroY = yAt(0);
    const cw = plotW / catN;

    ticks.forEach((tk) => {
      const yy = yAt(tk);
      svgParts.push(`<line class="wc-grid" x1="${PAD.l}" y1="${yy.toFixed(1)}" x2="${W - PAD.r}" y2="${yy.toFixed(1)}"></line>`);
      svgParts.push(`<text class="wc-tick" x="${PAD.l - 6}" y="${(yy + 3).toFixed(1)}" text-anchor="end">${esc(fmt(tk))}</text>`);
    });

    data.forEach((d, i) => {
      const gx0 = PAD.l + i * cw;
      const innerN = nSeries;
      const gbw = Math.min(cw * 0.7, innerN > 1 ? 22 * innerN : 56);
      const bwEach = gbw / innerN;
      const groupStart = gx0 + (cw - gbw) / 2;
      const vals = grouped ? (d.values ?? []) : [d.value ?? 0];
      vals.forEach((v, si) => {
        const bx = groupStart + si * bwEach;
        // SVG y cresce p/ baixo: yAt(0) fica embaixo (y maior), yAt(v>0) em cima
        // (y menor). O topo do retângulo é o menor y; altura = |Δy| (não y1-y0,
        // que seria negativo p/ valores positivos → barra some).
        const yZero = yAt(Math.min(0, v)), yVal = yAt(Math.max(0, v));
        const yTop = Math.min(yZero, yVal);
        const bh = Math.abs(yVal - yZero);
        const fill = grouped ? seriesColor(si) : (d.color || (d.highlight ? P.gold : P.field));
        const originY = v >= 0 ? yTop + bh : yTop; // cresce a partir da base (zero)
        const gap = innerN > 1 ? 1 : 0;
        svgParts.push(`<rect class="wc-bar" x="${(bx + gap / 2).toFixed(1)}" y="${yTop.toFixed(1)}" width="${Math.max(0, bwEach - gap).toFixed(1)}" height="${bh.toFixed(1)}" rx="2" fill="${fill}" style="transform-origin:${(bx + bwEach / 2).toFixed(1)}px ${originY.toFixed(1)}px"></rect>`);
      });
      if (showValues && !grouped) {
        const v = d.value ?? 0;
        const ly = v >= 0 ? yAt(v) - 6 : yAt(v) + 12;
        svgParts.push(`<text class="wc-val" x="${(gx0 + cw / 2).toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="middle">${esc(fmt(v))}</text>`);
      }
      svgParts.push(`<text class="wc-tick" x="${(gx0 + cw / 2).toFixed(1)}" y="${(H - PAD.b + 15).toFixed(1)}" text-anchor="middle">${esc(d.label)}</text>`);
    });
    svgParts.push(`<line class="wc-axis" x1="${PAD.l}" y1="${zeroY.toFixed(1)}" x2="${W - PAD.r}" y2="${zeroY.toFixed(1)}"></line>`);
    if (opts.axisTitle) svgParts.push(`<text class="wc-axis-title" x="${PAD.l}" y="${(H - 6).toFixed(1)}" text-anchor="start">${esc(opts.axisTitle)}</text>`);

    svgParts.push(`<rect class="wc-capture" x="0" y="0" width="${W}" height="${H}"></rect>`);
    container.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.ariaLabel)}">${svgParts.join('')}</svg>`;

    attachBarHover(container,
      (px) => { const i = Math.floor((px - PAD.l) / cw); return i >= 0 && i < catN ? i : -1; },
      (i) => defaultOrCustomTip(opts, data[i], i, fmt, grouped ? opts.series : undefined));
  }

  // Legend for grouped charts.
  if (grouped) {
    const legend = document.createElement('div');
    legend.className = 'wc-chart-legend';
    legend.innerHTML = opts.series!.map((s, si) =>
      `<span><span class="wc-sw" style="background:${seriesColor(si)}"></span>${esc(s.label)}</span>`).join('');
    container.appendChild(legend);
  }

  armReveal(container, reduce);
}

/** Build the default tooltip (label + value / per-series values) unless a custom one is supplied. */
function defaultOrCustomTip(
  opts: BarChartOpts, d: BarDatum | undefined, i: number,
  fmt: (v: number) => string, series?: { label: string }[],
): TipContent | null {
  if (!d) return null;
  if (opts.tooltip) return opts.tooltip(d, i);
  if (series && d.values) {
    return { title: d.label, rows: series.map((s, si) => ({ name: s.label, value: fmt(d.values![si] ?? 0) })) };
  }
  return { title: d.label, rows: [{ name: '', value: fmt(d.value ?? 0), leader: !!d.highlight }] };
}

/* ────────────────────────────────────────────────────────────────────────── */
/* doughnutChart                                                                */
/* ────────────────────────────────────────────────────────────────────────── */

/**
 * Render a doughnut (ring) chart. Covers #chart-halves (gols 1º vs 2º tempo).
 * Defaults segment colours to field-ink → gold-ink → ink-soft when unspecified.
 *
 * @example
 * doughnutChart(el, {
 *   ariaLabel: 'Distribuição de gols por tempo',
 *   segments: [
 *     { label: '1º tempo', value: h1 },
 *     { label: '2º tempo + prorrogação', value: h2 },
 *   ],
 *   valueFmt: (v) => `${v} gols`,
 *   centerLabel: String(h1 + h2), centerSub: 'gols',
 * });
 */
export function doughnutChart(container: HTMLElement, opts: DoughnutOpts): void {
  ensureStyles();
  clear(container);
  container.classList.add('wc-chart');
  const P = palette();
  const reduce = prefersReduce(opts.reduce);
  const fmt = opts.valueFmt ?? ((v: number) => String(v));
  const segs = (opts.segments || []).filter((s) => (s.value ?? 0) > 0);
  if (!segs.length) { container.innerHTML = '<p class="mono-label" style="color:var(--ink-faint)">sem dados</p>'; return; }

  const cycle = [P.field, P.gold, P.inkSoft, P.inkFaint];
  const total = segs.reduce((s, x) => s + x.value, 0);
  const size = opts.size ?? 220;
  const cx = size / 2, cy = size / 2;
  const r = size * 0.36;             // ring radius
  const sw = size * 0.14;            // ring thickness (~cutout 62%)
  const C = 2 * Math.PI * r;

  // Segments drawn as stroked-arc circles via dasharray, rotated into place.
  let acc = 0;
  const arcs = segs.map((s, i) => {
    const frac = s.value / total;
    const len = frac * C;
    const offset = -acc * C;         // rotate to start where the previous ended
    acc += frac;
    const color = s.color || cycle[i % cycle.length];
    return `<circle class="wc-seg" cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="${sw}" stroke-dasharray="${len.toFixed(2)} ${(C - len).toFixed(2)}" stroke-dashoffset="${offset.toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"></circle>`;
  }).join('');

  const center = opts.centerLabel
    ? `<text x="${cx}" y="${cy - (opts.centerSub ? 2 : -5)}" text-anchor="middle" style="font-size:${(size * 0.16).toFixed(0)}px;font-weight:600;fill:var(--ink)">${esc(opts.centerLabel)}</text>`
      + (opts.centerSub ? `<text x="${cx}" y="${cy + 16}" text-anchor="middle" class="wc-tick">${esc(opts.centerSub)}</text>` : '')
    : '';

  container.innerHTML = `<svg viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(opts.ariaLabel)}" style="max-width:${size}px;margin:0 auto">${arcs}${center}</svg>`;

  // Legend (default on).
  if (opts.legend ?? true) {
    const legend = document.createElement('div');
    legend.className = 'wc-chart-legend';
    legend.innerHTML = segs.map((s, i) =>
      `<span><span class="wc-sw" style="background:${s.color || cycle[i % cycle.length]}"></span>${esc(s.label)} · ${esc(fmt(s.value))}</span>`).join('');
    container.appendChild(legend);
  }

  // Hover: hit-test by segment angle.
  const tip = mountTip();
  const svg = container.querySelector('svg');
  if (tip && svg) {
    const bounds: { from: number; to: number; seg: DoughnutSegment; i: number }[] = [];
    let a = 0;
    segs.forEach((s, i) => { const f = s.value / total; bounds.push({ from: a, to: a + f, seg: s, i }); a += f; });
    const hide = (): void => { tip.hidden = true; };
    svg.addEventListener('pointermove', (e) => {
      const rect = svg.getBoundingClientRect();
      const px = ((e.clientX - rect.left) / rect.width) * size - cx;
      const py = ((e.clientY - rect.top) / rect.height) * size - cy;
      const dist = Math.hypot(px, py);
      if (dist < r - sw || dist > r + sw) { hide(); return; }
      // Angle from top (12 o'clock), clockwise, normalised to [0,1).
      let ang = Math.atan2(px, -py) / (2 * Math.PI);
      if (ang < 0) ang += 1;
      const b = bounds.find((x) => ang >= x.from && ang < x.to);
      if (!b) { hide(); return; }
      tip.innerHTML = tipHTML({ title: b.seg.label, rows: [{ name: '', value: `${fmt(b.seg.value)} · ${((b.seg.value / total) * 100).toFixed(1)}%`, leader: b.i === 1 }] });
      tip.hidden = false; placeTip(tip, e);
    });
    svg.addEventListener('pointerleave', hide);
  }

  armReveal(container, reduce);
}

/* ────────────────────────────────────────────────────────────────────────── */
/* lineChart                                                                    */
/* ────────────────────────────────────────────────────────────────────────── */

/**
 * Render a multi-series line chart. Covers #chart-momentum (2 cumulative series,
 * home in field-ink, away in gold-ink). Also usable for any minute-overlay when
 * you prefer lines over grouped bars. Series default to field-ink (index 0) and
 * gold-ink (index 1); further series fall back to ink-soft / ink-faint.
 *
 * Hover uses a shared index guide: a vertical rule + one dot per series at the
 * nearest x, with a tooltip listing every series' value at that x.
 *
 * @example
 * lineChart(el, {
 *   ariaLabel: 'Momentum — gols acumulados',
 *   xTitle: 'minuto de jogo', yTitle: 'gols acumulados',
 *   valueFmt: (v) => v.toFixed(0), xFmt: (x) => `minuto ${x}'`,
 *   series: [
 *     { label: 'BRA', points: home.map((v, i) => ({ x: labels[i], y: v })) },
 *     { label: 'ARG', points: away.map((v, i) => ({ x: labels[i], y: v })) },
 *   ],
 * });
 */
export function lineChart(container: HTMLElement, opts: LineChartOpts): void {
  ensureStyles();
  clear(container);
  container.classList.add('wc-chart');
  const P = palette();
  const reduce = prefersReduce(opts.reduce);
  const fmt = opts.valueFmt ?? ((v: number) => String(v));
  const xFmt = opts.xFmt ?? ((x: number) => String(x));
  const series = (opts.series || []).filter((s) => s.points && s.points.length);
  if (!series.length) { container.innerHTML = '<p class="mono-label" style="color:var(--ink-faint)">série indisponível</p>'; return; }

  const seriesColor = (i: number, custom?: string): string =>
    custom || [P.field, P.gold, P.inkSoft, P.inkFaint][i] || P.inkFaint;

  const W = opts.width ?? 720, H = opts.height ?? 300;
  const PAD = { l: 44, r: 16, t: 18, b: opts.xTitle ? 46 : 34 };
  const plotW = W - PAD.l - PAD.r, plotH = H - PAD.t - PAD.b;

  const allX = series.flatMap((s) => s.points.map((p) => p.x));
  const allY = series.flatMap((s) => s.points.map((p) => p.y));
  const xMin = Math.min(...allX), xMax = Math.max(...allX);
  const xSpan = xMax - xMin || 1;
  const { ticks, niceMax } = niceTicks(0, Math.max(...allY, 1) * 1.1, 5);
  const yMax = niceMax || 1;
  const xAt = (x: number) => PAD.l + ((x - xMin) / xSpan) * plotW;
  const yAt = (y: number) => PAD.t + (1 - y / yMax) * plotH;

  const parts: string[] = [];
  ticks.forEach((tk) => {
    const yy = yAt(tk);
    parts.push(`<line class="wc-grid" x1="${PAD.l}" y1="${yy.toFixed(1)}" x2="${W - PAD.r}" y2="${yy.toFixed(1)}"></line>`);
    parts.push(`<text class="wc-tick" x="${PAD.l - 6}" y="${(yy + 3).toFixed(1)}" text-anchor="end">${esc(fmt(tk))}</text>`);
  });
  // X ticks: a few evenly spaced from the actual x domain.
  const xTickN = Math.min(6, allX.length);
  for (let i = 0; i < xTickN; i++) {
    const xv = xMin + (xSpan * i) / (xTickN - 1 || 1);
    const xx = xAt(xv);
    parts.push(`<text class="wc-tick" x="${xx.toFixed(1)}" y="${(H - PAD.b + 15).toFixed(1)}" text-anchor="middle">${esc(xFmt(Math.round(xv)))}</text>`);
  }
  parts.push(`<line class="wc-axis" x1="${PAD.l}" y1="${(H - PAD.b).toFixed(1)}" x2="${W - PAD.r}" y2="${(H - PAD.b).toFixed(1)}"></line>`);
  if (opts.xTitle) parts.push(`<text class="wc-axis-title" x="${((PAD.l + W - PAD.r) / 2).toFixed(1)}" y="${(H - 6).toFixed(1)}" text-anchor="middle">${esc(opts.xTitle)}</text>`);
  if (opts.yTitle) parts.push(`<text class="wc-axis-title" x="${PAD.l}" y="${(PAD.t - 6).toFixed(1)}" text-anchor="start">${esc(opts.yTitle)}</text>`);

  series.forEach((s, si) => {
    const color = seriesColor(si, s.color);
    const pts = s.points.map((p) => `${xAt(p.x).toFixed(1)},${yAt(p.y).toFixed(1)}`).join(' ');
    parts.push(`<polyline class="wc-line" points="${pts}" stroke="${color}" pathLength="1"></polyline>`);
    const last = s.points[s.points.length - 1];
    parts.push(`<circle class="wc-marker" cx="${xAt(last.x).toFixed(1)}" cy="${yAt(last.y).toFixed(1)}" r="3.5" fill="${color}"></circle>`);
  });
  parts.push(`<rect class="wc-capture" x="0" y="0" width="${W}" height="${H}"></rect>`);
  container.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.ariaLabel)}">${parts.join('')}</svg>`;

  // Legend.
  if (opts.legend ?? true) {
    const legend = document.createElement('div');
    legend.className = 'wc-chart-legend';
    legend.innerHTML = series.map((s, si) =>
      `<span><span class="wc-sw" style="background:${seriesColor(si, s.color)}"></span>${esc(s.label)}</span>`).join('');
    container.appendChild(legend);
  }

  // Index-mode hover: vertical guide + per-series dots + tooltip.
  const tip = mountTip();
  const svg = container.querySelector('svg');
  if (tip && svg) {
    const guide = document.createElementNS(SVG_NS, 'line');
    guide.setAttribute('class', 'wc-guide');
    guide.style.display = 'none';
    svg.appendChild(guide);
    const dots: SVGCircleElement[] = [];
    const hide = (): void => { guide.style.display = 'none'; dots.forEach((d) => d.remove()); dots.length = 0; tip.hidden = true; };
    // Use the densest series as the x index reference.
    const ref = series.reduce((a, b) => (b.points.length > a.points.length ? b : a));
    svg.addEventListener('pointermove', (e) => {
      const r = svg.getBoundingClientRect(); if (!r.width) return;
      const vx = ((e.clientX - r.left) / r.width) * W;
      const xv = xMin + ((vx - PAD.l) / plotW) * xSpan;
      // Nearest index in the reference series.
      let bi = 0, bd = Infinity;
      ref.points.forEach((p, i) => { const d = Math.abs(p.x - xv); if (d < bd) { bd = d; bi = i; } });
      const xTarget = ref.points[bi].x;
      const gx = xAt(xTarget);
      guide.setAttribute('x1', gx.toFixed(1)); guide.setAttribute('x2', gx.toFixed(1));
      guide.setAttribute('y1', String(PAD.t)); guide.setAttribute('y2', String(H - PAD.b));
      guide.style.display = '';
      dots.forEach((d) => d.remove()); dots.length = 0;
      const rows: TipRow[] = [];
      series.forEach((s, si) => {
        const pt = s.points.find((p) => p.x === xTarget) ?? s.points[Math.min(bi, s.points.length - 1)];
        if (!pt) return;
        const c = document.createElementNS(SVG_NS, 'circle');
        c.setAttribute('class', 'wc-hoverdot');
        c.setAttribute('cx', xAt(pt.x).toFixed(1)); c.setAttribute('cy', yAt(pt.y).toFixed(1));
        c.setAttribute('r', '3.5'); c.setAttribute('fill', seriesColor(si, s.color));
        svg.appendChild(c); dots.push(c);
        rows.push({ name: s.label, value: fmt(pt.y), leader: si === 1 });
      });
      tip.innerHTML = tipHTML({ title: xFmt(Math.round(xTarget)), rows });
      tip.hidden = false; placeTip(tip, e);
    });
    svg.addEventListener('pointerleave', hide);
  }

  armReveal(container, reduce);
}

/* ────────────────────────────────────────────────────────────────────────── */
/* radarChart                                                                   */
/* ────────────────────────────────────────────────────────────────────────── */

/**
 * Render a radar / spider chart as inline SVG into `container`. N spokes at even
 * angles (first spoke points straight up, 12 o'clock), concentric grid rings,
 * axis labels, and 1–2 filled semi-transparent polygons — one per series.
 *
 * ── Normalisation ────────────────────────────────────────────────────────────
 * Every metric has its own scale, so values are normalised PER-AXIS before being
 * plotted. Two modes:
 *   · `opts.max` set   → every axis reaches 100 % at that value. Pass `max: 1`
 *     when your series values are ALREADY normalised to 0..1.
 *   · `opts.max` omitted (default) → each axis is normalised INDEPENDENTLY by the
 *     largest value that any series has on that axis (so the leader on each metric
 *     touches the outer ring). Raw values are always shown in the tooltip.
 *
 * Colours follow the WC family: series[0] → `--wc-field-ink`, series[1] →
 * `--wc-gold-ink`; grid/labels use `--line` / `--ink-soft`. Hovering a vertex
 * shows that series' raw value on that axis via the shared floating tooltip.
 * Idempotent (clears first), reduced-motion aware, `role="img"` + aria-label.
 *
 * @example Head-to-head across 6 normalised metrics
 * radarChart(el, {
 *   axes: ['xG', 'Posse', 'Finalizações', 'Pressões', 'Distância', 'Precisão'],
 *   ariaLabel: 'Comparação França x Espanha em 6 métricas.',
 *   series: [
 *     { label: 'FRA', values: [2.1, 50.6, 17, 246, 109.9, 89.5] },
 *     { label: 'ESP', values: [1.8, 66.0, 15, 280, 105.2, 91.0] },
 *   ],
 *   valueFmt: (v, i) => (i === 1 || i === 5 ? v.toFixed(1) + '%' : v.toFixed(1)),
 * });
 */
export function radarChart(container: HTMLElement, opts: RadarChartOpts): void {
  ensureStyles();
  clear(container);
  container.classList.add('wc-chart');
  const P = palette();
  const reduce = prefersReduce(opts.reduce);
  const axes = opts.axes || [];
  const series = (opts.series || []).filter((s) => Array.isArray(s.values) && s.values.length);
  const N = axes.length;
  if (N < 3 || !series.length) {
    container.innerHTML = '<p class="mono-label" style="color:var(--ink-faint)">série indisponível</p>';
    return;
  }
  const fmt = opts.valueFmt ?? ((v: number) => String(v));
  const seriesColor = (i: number, custom?: string): string => custom || (i === 1 ? P.gold : P.field);

  // Per-axis 100 % reach: a fixed max, or the largest value any series shows on that axis.
  const axisMax: number[] = axes.map((_, ai) => {
    if (opts.max != null) return opts.max || 1;
    let m = 0;
    series.forEach((s) => { const v = Number(s.values[ai]) || 0; if (v > m) m = v; });
    return m > 0 ? m : 1;
  });

  const size = opts.size ?? 300;
  const cx = size / 2, cy = size / 2;
  const R = size * 0.36;                       // outer ring radius
  const RINGS = 4;                             // concentric grid rings
  // Angle for axis i: start at top (−90°), go clockwise.
  const angleAt = (i: number): number => (-Math.PI / 2) + (i / N) * 2 * Math.PI;
  const pointAt = (i: number, frac: number): [number, number] => {
    const a = angleAt(i);
    const clamped = Math.max(0, Math.min(1, frac));
    return [cx + Math.cos(a) * R * clamped, cy + Math.sin(a) * R * clamped];
  };

  const parts: string[] = [];

  // Concentric grid rings (drawn as polygons through the N spokes → radar grid).
  for (let ring = 1; ring <= RINGS; ring++) {
    const frac = ring / RINGS;
    const pts: string[] = [];
    for (let i = 0; i < N; i++) { const [x, y] = pointAt(i, frac); pts.push(`${x.toFixed(1)},${y.toFixed(1)}`); }
    parts.push(`<polygon class="wc-radar-ring" points="${pts.join(' ')}"></polygon>`);
  }

  // Spokes + axis labels.
  for (let i = 0; i < N; i++) {
    const [ex, ey] = pointAt(i, 1);
    parts.push(`<line class="wc-radar-spoke" x1="${cx.toFixed(1)}" y1="${cy.toFixed(1)}" x2="${ex.toFixed(1)}" y2="${ey.toFixed(1)}"></line>`);
    const a = angleAt(i);
    const lx = cx + Math.cos(a) * (R + 16);
    const ly = cy + Math.sin(a) * (R + 16);
    // Anchor by horizontal position so labels don't overrun the viewBox.
    const cosA = Math.cos(a);
    const anchor = cosA > 0.15 ? 'start' : cosA < -0.15 ? 'end' : 'middle';
    parts.push(`<text class="wc-radar-axis" x="${lx.toFixed(1)}" y="${(ly + 3).toFixed(1)}" text-anchor="${anchor}">${esc(axes[i])}</text>`);
  }

  // Series polygons (drawn last so they sit above the grid).
  series.forEach((s, si) => {
    const color = seriesColor(si, s.color);
    const pts: string[] = [];
    for (let i = 0; i < N; i++) {
      const v = Number(s.values[i]) || 0;
      const [x, y] = pointAt(i, v / axisMax[i]);
      pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
    parts.push(`<polygon class="wc-radar-poly" points="${pts.join(' ')}" stroke="${color}" fill="${color}"></polygon>`);
  });

  // Vertices (hover targets), one per series per axis.
  series.forEach((s, si) => {
    const color = seriesColor(si, s.color);
    for (let i = 0; i < N; i++) {
      const v = Number(s.values[i]) || 0;
      const [x, y] = pointAt(i, v / axisMax[i]);
      parts.push(`<circle class="wc-radar-vertex" data-si="${si}" data-ai="${i}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5" fill="${color}"></circle>`);
    }
  });

  parts.push(`<rect class="wc-capture" x="0" y="0" width="${size}" height="${size}"></rect>`);
  container.innerHTML = `<svg viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(opts.ariaLabel)}" style="max-width:${size}px;margin:0 auto">${parts.join('')}</svg>`;

  // Legend (one swatch per series).
  const legend = document.createElement('div');
  legend.className = 'wc-chart-legend';
  legend.innerHTML = series.map((s, si) =>
    `<span><span class="wc-sw" style="background:${seriesColor(si, s.color)}"></span>${esc(s.label)}</span>`).join('');
  container.appendChild(legend);

  // Hover: nearest vertex within a small radius → raw value on that axis.
  const tip = mountTip();
  const svg = container.querySelector('svg');
  if (tip && svg) {
    const verts = Array.from(svg.querySelectorAll<SVGCircleElement>('.wc-radar-vertex'));
    const hide = (): void => { tip.hidden = true; };
    svg.addEventListener('pointermove', (e) => {
      const r = svg.getBoundingClientRect(); if (!r.width) return;
      const px = ((e.clientX - r.left) / r.width) * size;
      const py = ((e.clientY - r.top) / r.height) * size;
      let best: SVGCircleElement | null = null, bd = Infinity;
      verts.forEach((c) => {
        const dx = Number(c.getAttribute('cx')) - px, dy = Number(c.getAttribute('cy')) - py;
        const d = dx * dx + dy * dy;
        if (d < bd) { bd = d; best = c; }
      });
      // ~14px hit radius in viewBox units.
      if (!best || bd > 14 * 14) { hide(); return; }
      const vc = best as SVGCircleElement;
      const si = Number(vc.getAttribute('data-si'));
      const ai = Number(vc.getAttribute('data-ai'));
      const s = series[si];
      const raw = Number(s.values[ai]) || 0;
      tip.innerHTML = tipHTML({ title: axes[ai], rows: [{ name: s.label, value: fmt(raw, ai), leader: si === 1 }] });
      tip.hidden = false; placeTip(tip, e);
    });
    svg.addEventListener('pointerleave', hide);
  }

  armReveal(container, reduce);
}
