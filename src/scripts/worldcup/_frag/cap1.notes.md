# cap1 — Integration guide (Chapter 1 · live-2026)

Stitch `cap1.html` + `cap1.ts` into `src/pages/world-cup-dashboard.astro`. This is a
hand-merge guide: exact imports, fetch filenames, `safe()` call order, `:global()`
CSS list, and which legacy CSS blocks to copy.

Deliverables in this dir:
- `cap1.html` — 12 `<section>` shells + hero companions + estatísticas-extra blocks
- `cap1.ts` — render functions (one export per section), idempotent + fail-soft
- `cap1.notes.md` — this file

Everything type-checks under `--strict` against `../charts` (verified with tsc).

---

## 1. Where the HTML goes

`cap1.html` is a flat list of blocks. Place them like this inside `<main id="main-content">`:

1. **Hero companions (optional).** Three snippets at the top of the file, each
   flagged `(a)/(b)/(c)`:
   - `(a)` freshness badge `#wc-freshness` → into `<header class="wc-hero__head">`
   - `(b)` `#wc-tournament-progress` → between `.wc-hero__card` and `.wc-kpi-bento`
   - `(c)` `#wc-team-filter` → first child of `<main>`, before the hero `<section>`
   Omit any and its render fn no-ops (fail-soft).
2. **Estatísticas-extra blocks.** Three cards (minute chart `#wc-chart-minutes`,
   efficiency chart `#wc-chart-efficiency`, "jogo com mais gols" `#wc-stat-hi`) →
   append inside the existing `#estatisticas` `.wc-stats-grid` (or the bento). They
   reuse the skeleton's own `.wc-stat-card` styles.
3. **The 12 `<section>` blocks** → after `#estatisticas`, before `<ProjectRecommendations/>`.
   File order is legacy layout order: noticias, grupos, mata-mata, monte-carlo,
   partidas, shot-map, pass-network, momentum, selecao-copa, insights, bolao, craque.
   Reorder freely to match the final page; then fix the two numbering concerns below.

### Renumbering (CLAUDE.md rule: mono-labels sequential in DOM order)
The `<span class="mono-label">NN</span>` in each `.section-head` currently carries the
**legacy** number (01, 12, 13, 11, 17, 04, 05, 06, 14, 15, 18, 16). After you decide the
final DOM order (skeleton has 00 hero, 01 artilheiros, 02 estatisticas already), renumber
ALL section mono-labels 01…N sequentially. Also extend the jumpnav `NAV` array in the page
(currently `wc-hero / artilheiros / estatisticas`) with the new section ids **in the same
order** — the jumpnav auto-numbers from array position, so keep them in sync.

---

## 2. Imports to add (in the page's data `<script>`)

The page already imports `countUpAll` and `{ doughnutChart, readToken }`. Extend the
charts import and add the cap1 module:

```ts
import { doughnutChart, barChart, lineChart, readToken } from '../scripts/worldcup/charts';
import * as cap1 from '../scripts/worldcup/_frag/cap1';
```

(`barChart`/`lineChart` are only needed if you inline the chart calls; cap1 already imports
them itself, so you can just `import * as cap1` and call `cap1.renderStatsExtra(...)`.)

No other libraries. No Chart.js. The 3 Chart.js charts were converted:

| Legacy Chart.js         | cap1 fn                  | charts.ts primitive        |
|-------------------------|--------------------------|----------------------------|
| `#chart-minutes` (bar)  | `renderStatsExtra`       | `barChart({orientation:'v'})` |
| `#chart-efficiency` (barh) | `renderStatsExtra`    | `barChart({orientation:'h'})` |
| `#chart-momentum` (line)| `renderMomentum` (via `setupDeepStats`) | `lineChart()`     |

Shot/pass compare rows stay plain divs (`statRowHtml`) — no chart lib, ported as-is.

---

## 3. Fetch filenames (all under `assets/data/worldcup/`)

Use the page's existing `fetchJSON<T>(base, file)`. The page already fetches
`partidas.json`, `artilheiros.json`, `estatisticas.json`. Add:

| File                | Consumed by                                           |
|---------------------|-------------------------------------------------------|
| `noticias.json`     | `renderNews`                                          |
| `simulacao.json`    | `renderProbabilities`                                 |
| `grupos.json`       | `renderGroups`                                        |
| `selecao_copa.json` | `renderSelection`                                     |
| `insights.json`     | `renderInsights`                                      |
| `jogadores.json`    | `setupGame`                                           |
| `deepstats.json`    | `setupDeepStats` (shot + pass + momentum)             |
| `partidas.json`     | (already fetched) also feeds `renderBracket`, `renderMatches`, `renderBolao` |
| `estatisticas.json` | (already fetched) also feeds `renderStatsExtra`, `renderTournamentProgress` |

Add to the `Promise.all` in `loadWorldCup()`:

```ts
const [partidas, artil, stats, noticias, simulacao, grupos, selecao, insights, jogadores, deep] =
  await Promise.all([
    fetchJSON<cap1.PartidasPayload>(base, 'partidas.json'),
    fetchJSON<ArtilheirosPayload>(base, 'artilheiros.json'),
    fetchJSON<cap1.EstatisticasPayload>(base, 'estatisticas.json'),
    fetchJSON<cap1.NoticiasPayload>(base, 'noticias.json'),
    fetchJSON<cap1.SimulacaoPayload>(base, 'simulacao.json'),
    fetchJSON<cap1.GruposPayload>(base, 'grupos.json'),
    fetchJSON<cap1.SelecaoPayload>(base, 'selecao_copa.json'),
    fetchJSON<cap1.InsightsPayload>(base, 'insights.json'),
    fetchJSON<cap1.JogadoresPayload>(base, 'jogadores.json'),
    fetchJSON<cap1.DeepStatsPayload>(base, 'deepstats.json'),
  ]);
```

The skeleton's `EstatisticasPayload` is a subset — either widen it to `cap1.EstatisticasPayload`
or cast; the fields overlap. cap1 exports all its payload interfaces for reuse.

---

## 4. Render call order (inside `loadWorldCup()`, via the page's `safe()`)

Order below matches legacy `init()`. **`setupTeamFilter` must run after `renderMatches`**
(it reads `WC_STATE.matches`, populated by `renderMatches`/`renderBolao`).

```ts
cap1.resetCap1State();                                    // SPA re-entry hygiene (optional)

safe('freshness',   () => cap1.renderFreshness([partidas, artil, stats, noticias, simulacao, grupos, selecao, insights, jogadores, deep]));
safe('progress',    () => cap1.renderTournamentProgress(stats));
// (skeleton already calls renderHeroKPIs / renderScorers / renderStats here)
safe('stats-extra', () => cap1.renderStatsExtra(stats));
safe('news',        () => cap1.renderNews(noticias));
safe('probs',       () => cap1.renderProbabilities(simulacao));
safe('groups',      () => cap1.renderGroups(grupos));
safe('bracket',     () => cap1.renderBracket(partidas));
safe('selection',   () => cap1.renderSelection(selecao));
safe('insights',    () => cap1.renderInsights(insights));
safe('game',        () => cap1.setupGame(jogadores));
safe('matches',     () => cap1.renderMatches(partidas));
safe('bolao',       () => cap1.renderBolao(partidas));
safe('deepstats',   () => cap1.setupDeepStats(deep));
safe('team-filter', () => cap1.setupTeamFilter());        // AFTER matches
```

All fns are internally try/safe too, but wrap in `safe()` for parity with the skeleton.

### i18n note
Every text node in `cap1.html` carries `data-i18n-key` (aria via `data-i18n-aria`), so the
runtime language switcher covers the static shells. **Content injected by cap1.ts (rows,
cards, tooltips) is NOT i18n-keyed** — it is pt-BR hardcoded, exactly like the legacy app
(the World Cup dashboard has no i18n; strings live in the JS). This matches CLAUDE.md
("Sem i18n (pt-BR hardcoded)"). If full i18n of injected content is later wanted, that's a
separate pass. **No i18n keys were invented** — all keys used already exist under
`portfolio.world_cup.*` in `assets/i18n/pt-BR.json`. See §7 for keys with no exact match.

---

## 5. `:global()` — classes styled by injected HTML

The page's scoped `<style>` cannot reach innerHTML-injected nodes. Wrap these selectors in
`:global()` **under a static ancestor** (the pattern already used for `#wc-scorers-body`),
OR — simpler and recommended — copy the legacy blocks into a single `is:global` style /
the shared stylesheet (see §6). If you keep them in the page's scoped block, `:global()`
every class below.

Injected-content class families (all rendered by cap1.ts via innerHTML):

- **News:** `.wc-news-item`, `.wc-news-link`, `.wc-news-headline-text`, `.wc-news-summary`,
  `.wc-news-meta`, `.wc-news-source-tag`, `.wc-news-time` (+ `.is-highlighted`/`.is-dimmed`)
- **Monte Carlo:** `.wc-prob-row` (+ `.is-top`), `.wc-prob-row__rank/__flag/__main/__name-line/__name/__elo/__bar-wrap/__bar/__pct`
- **Groups:** `.wc-group-card` (+ `__head`), `.wc-group-rows`, `.wc-group-row` (+ `.is-qualified`),
  `.wc-group-row__flag/__name-block/__name/__badge/__pts/__played/__gca/__diff` (+ `.is-positive/.is-negative`)
- **Bracket:** `.wc-bracket-tree` (+ `__side/__side--left/--right/__head/__cols/__center/__trophy`),
  `.wc-bracket-side__col` (+ `__col-head/__matches`), `.wc-bracket-match` (+ `.is-today/.is-final-done/--empty`),
  `.wc-bracket-match__row/__team/__flag/__name` (+ `--winner/--loser/--placeholder`), `__score` (+ `--winner/--loser/--pending`), `__today-tag`,
  `.wc-bracket-mobile` (+ `details/summary/__round/__round-head/__body`)
- **Matches:** `.wc-match` (+ `--today/--placeholder/.is-highlighted/.is-dimmed`),
  `.wc-match__team` (+ `--right`), `__flag` (+ `--empty`), `__name` (+ `--placeholder`),
  `__score` (+ `--pending`), `__score-num/__score-sep/__score-pen/__today-badge/__meta/__round/__time`
- **Selection:** `.wc-pitch` (+ `__row/--gk/--df/--mf/--fw`), `.wc-player-token` (+ `--gk/--topscorer`),
  `.wc-player-token__circle/__initials/__name/__stat`, `.wc-top-gks` (+ `__head/__list`),
  `.wc-top-gk` (+ `--best/__avatar/__flag/__name/__stat`)
- **Insights:** `.wc-insight-card` (+ `--field/--gold/--ink/--live/--hero/--md`),
  `.wc-insight-card__head/__title/__body/__key`
- **Bolão:** `.wc-bolao-item` (+ `.is-today/.is-finished`), `.wc-bolao-team` (+ `--right/__name/--placeholder`),
  `.wc-bolao-mid/__inputs`, `.wc-bolao-input` (+ `-sep`), `.wc-bolao-submit`,
  `.wc-bolao-result` (+ `--exact/--winner`), `.wc-bolao-meta`,
  `.wc-bolao-score__row`, `.wc-bolao-score__pts` (+ `--exact/--winner`)
- **Craque game:** `.wc-player-card` (+ `__flag/__name/__meta/__stat/__goals/__goals-label/__cta`),
  `.wc-game__empty`, `.wc-game__duel` states `.is-voting/.is-entering`,
  `.wc-ranking-row` (+ `__rank/__name/__name-text/__team/__winrate`)
- **Deep stats (shot/pass compare):** `.wc-stat-compare__head/__team/--right/__team-name/__source`,
  `.wc-stat-rows`, `.wc-stat-row` (+ `__home/__away/__bar/__bar-home/__bar-away/__label`),
  `.wc-stat-subhead`
- **Shared flag glyph:** `.wc-flag` (+ `--empty`) — used by nearly every injected block.

> Note: the skeleton **already** declares `.wc-flag` styling inside `#wc-scorers-body :global(...)`.
> Injected flags elsewhere need `.wc-flag` reachable too — copying the base `.wc-flag` block
> from legacy CSS (line ~1030) into the shared/global stylesheet covers all sections at once.

Static shells (present at build, styled by the page's scoped CSS directly, **no `:global()`
needed** for the wrapper itself, but their injected children do): `.wc-news-list`,
`.wc-groups-grid`, `#wc-bracket-host`, `.wc-matches-list`, `.wc-bolao-list`, `.wc-prob-list`,
`.wc-selection-wrap`, `.wc-insights-grid`, `.wc-game__duel`, `.wc-stat-compare`,
`.wc-match-select` / `-wrap`, `.wc-progress*`, `.wc-freshness`, `.wc-team-filter*`,
`.wc-modal*`, `.wc-mc-*`.

---

## 6. Legacy CSS to copy (from `public/world-cup-dashboard/css/style.css`)

Recommended: copy these selector blocks into a **single global stylesheet** the page imports
(e.g. a new `src/styles/worldcup.css` with `is:global`, or an `is:global` `<style>` in the
page). That avoids `:global()`-wrapping ~150 selectors by hand. All use WC tokens already
present in `src/styles/tokens.css` (`--wc-field*/--wc-gold*/--wc-live*/--wc-amber*` + neutral
ramp) — no hardcoded hex, nothing to retune.

Copy by section (line numbers approximate, from the legacy file):

| Block                         | Legacy selectors (start line)                                  |
|-------------------------------|----------------------------------------------------------------|
| Freshness                     | `.wc-freshness*` (598)                                         |
| Tournament progress           | `.wc-progress*` (629)                                          |
| Section bg + news             | `.wc-news-section` (811), `.wc-news-headline` (813), `.wc-live-dot` (821), `.wc-live-text*` (837), `.wc-news-source` (843), `.wc-news-list/-item/-link/-headline-text/-summary/-meta/-source-tag/-time` (845–950) |
| Stats bento + card + chart    | `.wc-stats-bento` (1081), `.wc-stat-card*` (1103–1155) — needed by the estatísticas-extra cards if not already covered by skeleton |
| Monte Carlo rows              | `.wc-prob-section` (1156), `.wc-prob-list` (1158), `.wc-prob-row*` (1167–1265) |
| Game / craque + modal         | `.wc-game-section` (1266), `.wc-game__duel/__actions` (1268–1283), `.wc-player-card*` (1285–1392), `.wc-game__empty` (1392), `.wc-modal*` (1402–1540), `.wc-ranking-*` (1477–1531) |
| Matches                       | `.wc-matches-section` (1541), `.wc-matches-grid/-col*` (1543–1569), `.wc-matches-list` (1570), `.wc-match*` (1580–1710) |
| Skeleton (optional)           | `.wc-skeleton*` (1736–1783) — only if you keep skeleton loaders |
| Team filter + highlight/dim   | `.wc-team-filter*` (1785), `.wc-team-chip*` (1803–1846), `.wc-match.is-highlighted` (1847), `.wc-news-link.is-highlighted` (1851) |
| Groups                        | `.wc-groups-section` (1863), `.wc-groups-grid` (1865), `.wc-group-card*` (1874–1896), `.wc-group-rows/-row*` (1897–1990) |
| Bracket                       | `.wc-bracket-section` (1993) through `.wc-bracket-mobile*` (…2334) — the whole bracket block (desktop tree + mobile details) |
| Selection / pitch             | `.wc-selection-section` (2340), `.wc-selection-wrap` (2342), `.wc-pitch*` (2349–2392), `.wc-player-token*` (2394–2449), `.wc-top-gks/-gk*` (2451–2522) |
| Insights                      | `.wc-insights-section` (2524), `.wc-insights-grid` (2526), `.wc-insight-card*` (2534–2590) |
| Bolão                         | `.wc-bolao-section` (2595) through `.wc-bolao-reset` (2802) |
| Deep-stats compare + selects  | `.wc-shotmap-section/.wc-passnet-section/.wc-flow-section` (3048–3053), `.wc-match-select*` (3159–3206), `.wc-stat-compare*` (3206–3336) |
| Momentum wrapper (optional)   | `.wc-goal-pulse*` (3127) — only relevant if you re-add goal markers; the SVG lineChart does NOT use them, so this can be **skipped** |
| Base flag glyph               | `.wc-flag` (1030) — copy once, covers all sections |

**Do NOT copy** the legacy `.wc-momentum-chart__markers` / `canvas`-specific rules or any
Chart.js styling — the SVG lib injects its own `<style id="wc-charts-css">` and floating
tooltip. The `.wc-momentum-chart` wrapper only needs a height; the skeleton's chart cards
already give `.wc-stat-card__chart` a min-height, and the `#momentum` block sets it inline.

---

## 7. Deviations / things the orchestrator should know

1. **Container IDs renamed.** The skeleton uses `wc-`-prefixed ids and I followed that. cap1
   targets: `#wc-chart-minutes`, `#wc-chart-efficiency`, `#wc-chart-momentum`, `#wc-stat-hi`,
   `#wc-news-list`, `#wc-prob-list`, `#wc-groups-grid`, `#wc-bracket-host`,
   `#wc-matches-recent/-upcoming`, `#wc-selection-host`, `#wc-insights-grid`,
   `#wc-bolao-list/-total/-score-list`, `#wc-game-duel`, `#wc-shotstats-host/-error`,
   `#wc-passstats-host/-error`, `#wc-flow-error`, `.wc-match-select` (×3, ids `-04/-05/-06`).
   The legacy `chart-halves/chart-minutes/chart-efficiency/chart-momentum` `<canvas>` ids are
   gone (charts render into `<div>`s via the SVG lib).

2. **Momentum goal-pulse markers dropped.** The legacy `placeMomentumMarkers()` read Chart.js
   pixel scales to overlay pulsing goal dots. The SVG `lineChart` has no equivalent hook and
   ships its own index-hover tooltip, so markers are omitted (the goal minutes still show as
   the line's step-ups + hover values). If markers are wanted later, they'd need custom SVG
   coords from lineChart — out of scope. The `#wc-momentum-markers` div is therefore NOT in
   `cap1.html` (not needed).

3. **ModalController simplified.** The legacy shared focus-trap `ModalController` (stack +
   Tab-trap) is replaced by lightweight per-modal open/close handlers in `wireMonteCarloModal`
   and `setupGame` (Escape + backdrop close + focus return). Full Tab focus-trap was dropped
   for brevity; re-add the legacy `ModalController` if strict WCAG 2.4.3/2.1.2 trap is required
   for the two modals (`#wc-mc-modal`, `#wc-ranking-modal`).

4. **localStorage keys preserved exactly:** `wc-bolao` (bolão picks), `wc-craque-votes`
   (duel votes), `wc-filter` (team filter). Same shapes and scoring as legacy.

5. **SPA-safe:** all render fns clear their container (innerHTML =) before writing and are
   idempotent across `astro:page-load`. Module state (`WC_STATE`, `GAME`, `_deep`,
   `_deepSelectedId`) is resettable via exported `resetCap1State()` — call it at the top of
   `loadWorldCup()` if you observe stale state on SPA navigation.

6. **`data-reveal` reveal.** Injected nodes carry `data-reveal`; cap1's `revealInjected()`
   attaches its own IntersectionObserver (or marks `.is-visible` under reduced-motion). This
   depends on the legacy `[data-reveal]` / `html.has-js [data-reveal].is-visible` CSS
   (legacy lines 482–502). Either copy that CSS block, OR drop the `data-reveal` attrs from
   `cap1.html` and rely on the page's GSAP `revealUp` motion (the page already reveals
   `main section[id]` heads + `.wc-*` cards). If you keep GSAP-only, remove `revealInjected`
   calls' dependency by ensuring `.is-visible`/default opacity is 1 (no `[data-reveal]` CSS =
   nodes stay visible, which is fine).

7. **i18n keys with no exact match (used a close existing key or hardcoded):**
   - The estatísticas-extra "média/partida", "maior goleada", "pênaltis", "gols contra"
     labels already exist and belong to the skeleton's bento; I only added `stat_hi_label`
     (exists) + the two chart-card labels `stat_minutes_label`/`stat_eff_label` (exist).
   - `partidas_recent_hint` = "últimos finalizados", `partidas_upcoming_hint` = "hoje e
     agendados" — exist. `select_match` = "partida" — exists (reused for all 3 selects).
   - **No missing keys.** Every `data-i18n-key`/`data-i18n-aria` in `cap1.html` resolves to an
     existing `portfolio.world_cup.*` key (verified against `assets/i18n/pt-BR.json`). Keep the
     three dictionaries (pt-BR/en-US/es-ES) in parity if en/es are later filled.

8. **Type-check.** `cap1.ts` passes `tsc --strict --lib es2020,dom,dom.iterable` cleanly
   against `../charts` (`barChart`/`lineChart`/`readToken` signatures). All payload interfaces
   are exported for the page to reuse in its `fetchJSON<T>` calls.
