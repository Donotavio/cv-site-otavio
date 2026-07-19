# fifa — Guia de integração (3 seções de dado FIFA)

Três seções para costurar no esqueleto `src/pages/world-cup-dashboard.astro`.
NÃO edite o `.astro` como parte deste frag — o orquestrador faz o stitch. Estes
fragmentos assumem as convenções JÁ existentes do esqueleto (`fetchJSON`, `safe`,
`readToken`, `astro:page-load`, motion, jumpnav), idênticas às usadas por cap23.

Seções entregues (mono-labels sequenciais em ordem de DOM — assumem inserção
DEPOIS de `historia-copas` [10]; renumere se a posição mudar):

| # | id da `<section>` | render fn | JSON |
|---|-------------------|-----------|------|
| 11 | `fifa-team-stats`    | `renderFifaTeamStats(fifaTeam)`   | `fifa_team_stats.json` |
| 12 | `fifa-power-ranking` | `renderFifaPowerRanking(fifaPower)` | `fifa_power_ranking.json` |
| 13 | `fifa-compare`       | `renderFifaCompare(fifaTeam)`     | `fifa_team_stats.json` (reusa) |

> `fifa_player_stats.json` NÃO é consumido por estas 3 seções (o power ranking já
> cobre jogadores). O schema está tipado/disponível se uma 4ª seção quiser famílias
> por-jogador no futuro — fora do escopo agora.

---

## 1. Markup

A marcação das 3 seções está EXPORTADA como string em `fifa.ts`:

```ts
import { FIFA_SECTIONS_HTML } from '../scripts/worldcup/_frag/fifa';
```

Como o esqueleto é HTML estático no `.astro` (não injeta seções via JS), a forma
mais limpa é **colar o conteúdo de `FIFA_SECTIONS_HTML` diretamente no markup do
`.astro`**, logo após o `</section>` de `#historia-copas` (§10) e antes de
`<ProjectRecommendations>`. A string é idêntica ao que o esqueleto usaria à mão
(mesmas classes/ids/`data-i18n-*`). Está exportada só para manter tudo num lugar
revisável; a constante em si não precisa ser importada em runtime se você colar o
HTML. (Se preferir manter como string, o esqueleto teria que fazer
`main.insertAdjacentHTML` — não recomendado; prefira colar o HTML.)

Cada `<canvas>`/gráfico é um `<div ... id role="img" aria-label data-i18n-aria>`
com um `<p class="wc-loading">` placeholder; a lib SVG (`charts.ts`) faz
`clear()` + `innerHTML`, então o placeholder some no 1º render. O `aria-label` é
lido pelo TS (`ariaOf`) e repassado ao `<svg role="img">` (i18n preservado).

---

## 2. Imports de script (bloco `<script>` de dados do `.astro`)

No topo do `<script>` que já importa cap1/cap23:

```ts
import { renderFifaTeamStats, renderFifaPowerRanking, renderFifaCompare } from '../scripts/worldcup/_frag/fifa';
```

`fifa.ts` importa internamente `barChart`, `radarChart`, `readToken` de
`../charts` — **`radarChart` é a nova primitiva** adicionada a `charts.ts` nesta
entrega (Parte A). Sem deps externas.

---

## 3. Fetch + ordem de chamada em `loadWorldCup()`

Estenda o `Promise.all` (adicione 2 fetches; `fifa-compare` reusa `fifaTeam`):

```ts
const [
  /* …itens existentes… */,
  fifaTeam, fifaPower,
] = await Promise.all([
  /* …fetches existentes… */
  fetchJSON<any>(base, 'fifa_team_stats.json'),
  fetchJSON<any>(base, 'fifa_power_ranking.json'),
]);
```

E some as chamadas `safe(...)` (ordem livre — cada seção é independente/fail-soft):

```ts
// ── FIFA (dado oficial) ──
safe('fifa-team',    () => renderFifaTeamStats(fifaTeam));
safe('fifa-power',   () => renderFifaPowerRanking(fifaPower));
safe('fifa-compare', () => renderFifaCompare(fifaTeam));   // reusa fifa_team_stats
```

As fns são idempotentes (limpam/regravam o host) e no-op se a seção não estiver
no DOM (`getElementById` guard) → seguras em qualquer navegação SPA.

> Opcional: se quiser tipar os payloads em vez de `<any>`, `fifa.ts` exporta
> `FifaTeamStats` e `FifaPowerRanking`:
> `import type { FifaTeamStats, FifaPowerRanking } from '../scripts/worldcup/_frag/fifa';`

---

## 4. JUMPNAV

Adicione os três itens ao array `NAV` do bloco jumpnav, DEPOIS de
`historia-copas` (o fallback `fb` é o texto; as chaves i18n de nav vão à parte):

```ts
{ id: 'fifa-team-stats',    fb: 'Estatísticas FIFA' },  // portfolio.world_cup.nav_fifa_team
{ id: 'fifa-power-ranking', fb: 'Power Ranking' },       // portfolio.world_cup.nav_fifa_power
{ id: 'fifa-compare',       fb: 'Comparador' },          // portfolio.world_cup.nav_fifa_compare
```

O jumpnav auto-numera pela ordem do array + presença no DOM; não há número
hardcoded.

---

## 5. MOTION

O bloco motion do esqueleto varre `main section[id]`, revela `.section-head` e um
conjunto de cards. Os containers destas seções (`.wc-c22-block`,
`.wc-insight-card`, `.wc-stat-compare`) **já estão** no seletor de cards do
esqueleto (veja a linha `revealUp(cards, …)` em `animateWorldCup()`), então
nenhuma mudança é necessária. Se algum card novo não animar, o seletor já cobre;
não há classe de card exclusiva do FIFA que precise ser somada.

---

## 6. i18n — chaves

**Chaves NOVAS** a autorar nos três `assets/i18n/{pt-BR,en-US,es-ES}.json` sob
`portfolio.world_cup.*` (paridade obrigatória). O texto embutido no markup é o
fallback pt-BR — a seção funciona sem as chaves, só não troca de idioma.

`data-i18n-key` (texto):
- `fifa_team_title`, `fifa_team_lead`, `fifa_team_error`, `fifa_team_ranking_title`, `fifa_team_note`
- `fifa_power_title`, `fifa_power_lead`, `fifa_power_error`, `fifa_power_outfield_title`, `fifa_power_gk_title`
- `fifa_compare_title`, `fifa_compare_lead`, `fifa_compare_error`, `fifa_compare_loading`
- `fifa_source` (tagline "dado oficial FIFA"), `fifa_select_axis` (label "eixo"),
  `fifa_team_a`, `fifa_team_b`, `fifa_col_score` ("Nota"), `fifa_col_change` ("Var.")

`data-i18n-aria` (aria-label de gráfico/tabela):
- `fifa_team_bento_aria`, `fifa_team_chart_aria`
- `fifa_power_outfield_aria`, `fifa_power_gk_aria`
- `fifa_compare_radar_aria`

Nav (opcional, mesmo padrão de `nav_*` existentes):
- `nav_fifa_team`, `nav_fifa_power`, `nav_fifa_compare`

**Reutilizadas (JÁ existem):** `select_metric` (label "métrica"),
`col_rank`, `col_player`.

Textos SEM chave i18n (pt-BR fixo, igual ao legado — conteúdo dinâmico/dado, não
UI traduzível): rótulos de métrica do `<select>` (`metrics_catalog[].label_pt`,
vêm do JSON), labels dos eixos do power ranking (`Ataque/Defesa/Criatividade`),
labels dos eixos do radar (`xG/jogo`, `Posse`, …), títulos/subs dos cards do
bento, e as strings de `meta`.

---

## 7. CSS — `:global()` + novas classes

Regra do repo: **tudo injetado via JS (innerHTML) precisa de `:global()`** sob um
ancestral estático (o CSS scoped do Astro não alcança innerHTML). Os containers
estáticos que já estão no markup podem ficar sem `:global()`.

### 7a. Classes REUSADAS (já têm CSS via cap23 — confirme que os blocos de cap23 já foram costurados)

Estas seções reaproveitam componentes de cap23. Se o CSS de cap23 já está na
página, **nada a fazer**; senão, copie os mesmos blocos (todos JS-injected →
`:global()`):
- `.wc-insight-card` + variantes `--field/--gold/--ink/--live/--hero/--md` + `__head/__cat/__title/__key/__body` (bento do FIFA-01) — **`:global()`**
- `.wc-scorers-table__*` das linhas injetadas — replique o padrão
  `#fifa-power-body :global(...)`, `#fifa-gk-body :global(...)` (como o esqueleto
  já faz p/ `#wc-scorers-body`)
- `.wc-stat-compare__head/__team/__team--right/__team-name/__source` +
  `.wc-stat-rows` + `.wc-stat-row` + `__home/__away/__label` — **`:global()`**
  (o comparador FIFA-03 injeta a lista de deltas com essas classes)
- `.wc-insights-grid`, `.wc-c22-block` (+ `__head/__title/__chart`),
  `.wc-c22-two-col`, `.wc-match-select-wrap`, `.wc-cl-select`, `.wc-cl-tagline`,
  `.wc-cl-note`, `.wc-skeleton*` — **containers estáticos** (no markup) → sem `:global()`

### 7b. Classes NOVAS (exclusivas do FIFA — adicionar ao `<style>` da página)

Fundos alternados das seções (containers estáticos → sem `:global()`; use tokens):
```css
.wc-fifa-section { background: var(--paper); }
.wc-fifa-section--alt { background: var(--paper-soft); }
```

Radar / comparador — layout (containers ESTÁTICOS no markup → sem `:global()`):
```css
.fifa-compare-head { display: flex; flex-wrap: wrap; gap: var(--space-4); align-items: flex-end; }
.fifa-compare-grid { display: grid; grid-template-columns: 1fr; gap: var(--space-6); align-items: start; }
@media (min-width: 1024px) { .fifa-compare-grid { grid-template-columns: minmax(300px, 1.1fr) 1fr; } }
.fifa-radar-host { min-height: 300px; display: flex; align-items: center; justify-content: center; }
.fifa-compare-deltas { padding: var(--space-4); }
```

Variação de posição no power ranking (INJETADAS via innerHTML → **`:global()`**).
Cor WC-family only: sobe = `--wc-field-ink`, cai = `--wc-live-ink`, estável = `--ink-faint`:
```css
:global(.fifa-change) { font-family: var(--font-mono); font-size: var(--text-xs); font-variant-numeric: var(--num-tabular); }
:global(.fifa-change--up)   { color: var(--wc-field-ink); }
:global(.fifa-change--down) { color: var(--wc-live-ink); }
:global(.fifa-change--flat) { color: var(--ink-faint); }
```

Barra de delta do comparador (INJETADA → **`:global()`**):
```css
:global(.fifa-delta-bar) { display: flex; align-items: center; justify-content: center; }
:global(.fifa-delta-bar__val) { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--ink-soft); font-variant-numeric: var(--num-tabular); }
:global(.wc-stat-row__home.is-lead), :global(.wc-stat-row__away.is-lead) { color: var(--wc-gold-ink); font-weight: 600; }
```

> `.wc-stat-row__home.is-lead` / `.wc-stat-row__away.is-lead` é um modificador NOVO
> (o líder de cada métrica no comparador). Se preferir não introduzi-lo, remova o
> `.is-lead` do markup gerado em `cmpRenderDeltas()` — é puramente cosmético.

### Resumo — seletores que EXIGEM `:global()` (todos JS-injected)
`.wc-insight-card` e variantes/filhos · `.wc-stat-compare__head/__team*/__source`
· `.wc-stat-rows` · `.wc-stat-row` e filhos (+ `.is-lead`) · `.fifa-change*` ·
`.fifa-delta-bar*` · `.wc-scorers-table__*` das linhas de `#fifa-power-body`,
`#fifa-gk-body` (replicar o padrão `#…-body :global(...)` do esqueleto).

Classes SEM `:global()` (containers estáticos no markup): `.wc-fifa-section(-alt)`,
`.fifa-compare-head/-grid`, `.fifa-radar-host`, `.fifa-compare-deltas`,
`.wc-insights-grid`, `.wc-c22-block*`, `.wc-c22-two-col`, `.wc-match-select-wrap`,
`.wc-cl-select`, `.wc-cl-tagline`, `.wc-cl-note`, `.wc-scorers-wrap`, `.wc-skeleton*`.

### Nota sobre altura do radar
A lib SVG é responsiva por `viewBox` (`svg { width:100%; height:auto }`) e o
radar tem `size=300` (max-width 300px, centralizado). `.fifa-radar-host` só dá um
`min-height` p/ estabilidade de layout enquanto carrega.

---

## 8. radarChart (Parte A) — assinatura e normalização

Adicionada a `src/scripts/worldcup/charts.ts` (exporta `RadarChartOpts` +
`RadarSeries`):

```ts
radarChart(container: HTMLElement, opts: {
  axes: string[];
  series: { label: string; values: number[]; color?: string }[];
  ariaLabel: string;
  max?: number;                              // ver normalização
  valueFmt?: (v: number, axisIdx: number) => string;
  reduce?: boolean;
  size?: number;                             // viewBox side, default 300
})
```

**Normalização por-eixo** (cada métrica na própria escala):
- `max` OMITIDO (o comparador usa este modo) → cada eixo é normalizado pelo MAIOR
  valor que qualquer série tem naquele eixo (o líder da métrica toca a borda).
- `max` = `1` → série já vem normalizada 0..1; `max` = N → todos os eixos usam N
  como 100%.
O valor CRU sempre aparece no tooltip (hover no vértice), via `valueFmt(raw, axisIdx)`.

Cores: série[0] → `--wc-field-ink`, série[1] → `--wc-gold-ink`; grade/labels →
`--line`/`--ink-soft`. Idempotente (clear first), `role="img"`+aria-label,
reduced-motion aware, CSS no mesmo `<style id="wc-charts-css">`. `charts.ts`
type-check limpo (tsc --noEmit --strict).
