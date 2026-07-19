# cap23 — Guia de integração (Capítulo 2 + 3 · bloco 2022 / histórico)

Três seções para costurar no esqueleto `src/pages/world-cup-dashboard.astro`,
**depois** da §[02] Estatísticas (`#estatisticas`) e **antes** de
`<ProjectRecommendations>`. NÃO edite este arquivo `.astro` você mesmo — o
orquestrador faz o stitch. Estes fragmentos assumem as convenções JÁ existentes
do esqueleto (`fetchJSON`, `safe`, `readToken`, `astro:page-load`, motion, jumpnav).

Seções entregues (mono-labels sequenciais em ordem de DOM):

| # | id da `<section>` | render fn |
|---|-------------------|-----------|
| 07 | `wc-classics` | `renderClassics(classics)` |
| 08 | `copa2022-panorama` | `renderPanorama(panorama)` |
| 09 | `comparativo-copas` | `renderComparativo(comparativo, idade)` |
| 10 | `historia-copas` | `renderHistoria(historia, contexto)` |

---

## 1. Markup

Cole o conteúdo de `cap23.html` em ordem, logo após o `</section>` de
`#estatisticas`. Renumere os mono-labels das seções **seguintes** do painel
legado (Monte Carlo passa a 11, etc.) quando forem portadas — estas quatro já
saem 07–10.

Cada `<canvas>` do legado virou um `<div class="...__chart" id="..." role="img"
aria-label="…" data-i18n-aria="…">` com um `<p class="wc-loading">` placeholder.
A lib SVG (`charts.ts`) faz `clear()` + `innerHTML` no container, então o
placeholder some no primeiro render. O `aria-label` é lido pelo TS
(`ariaOf(box, …)`) e repassado ao `<svg role="img">`, preservando a tradução do
`data-i18n-aria`.

---

## 2. Imports de script (bloco `<script>` de dados do `.astro`)

No topo do `<script>` que já importa `countUpAll` / `doughnutChart`:

```ts
import { renderClassics, renderPanorama, renderComparativo, renderHistoria } from '../scripts/worldcup/_frag/cap23';
```

`cap23.ts` importa internamente `barChart`, `lineChart`, `readToken` de
`../charts` (mesma lib que o esqueleto já usa). Sem deps externas.

---

## 3. Fetch + ordem de chamada em `loadWorldCup()`

Arquivos JSON (mesmo diretório `assets/data/worldcup/` do esqueleto):

| variável | arquivo |
|----------|---------|
| classics | `classics_2022.json` |
| panorama | `copa2022_panorama.json` |
| comparativo | `comparativo_copas.json` |
| idade | `idade_copas.json` |
| historia | `historia_copas.json` |
| contexto | `contexto_copas.json` |

Estenda o `Promise.all` e some as chamadas `safe(...)` (a ordem entre elas é
livre — cada seção é independente e fail-soft):

```ts
const [partidas, artil, stats, classics, panorama, comparativo, idade, historia, contexto] = await Promise.all([
  fetchJSON<PartidasPayload>(base, 'partidas.json'),
  fetchJSON<ArtilheirosPayload>(base, 'artilheiros.json'),
  fetchJSON<EstatisticasPayload>(base, 'estatisticas.json'),
  fetchJSON<any>(base, 'classics_2022.json'),
  fetchJSON<any>(base, 'copa2022_panorama.json'),
  fetchJSON<any>(base, 'comparativo_copas.json'),
  fetchJSON<any>(base, 'idade_copas.json'),
  fetchJSON<any>(base, 'historia_copas.json'),
  fetchJSON<any>(base, 'contexto_copas.json'),
]);
safe('hero-kpis', () => renderHeroKPIs(partidas, artil, stats));
safe('scorers',   () => renderScorers(artil));
safe('stats',     () => renderStats(stats));
// ── cap23 (2022 / histórico) ──
safe('classics',    () => renderClassics(classics));
safe('panorama',    () => renderPanorama(panorama));
safe('comparativo', () => renderComparativo(comparativo, idade));
safe('historia',    () => renderHistoria(historia, contexto));
```

As fns são idempotentes (limpam/regravam o host) e no-op se a seção não estiver
no DOM (`getElementById` guard) → seguras em qualquer navegação SPA.

### JUMPNAV
Adicione os quatro itens ao array `NAV` do bloco jumpnav, entre `estatisticas` e
o resto, usando as chaves i18n de nav já existentes (o fallback `fb` é o texto):

```ts
{ id: 'wc-classics',       fb: 'Clássicos 2022' },   // portfolio.world_cup.nav_classicos
{ id: 'copa2022-panorama', fb: 'Panorama 2022' },    // portfolio.world_cup.nav_panorama
{ id: 'comparativo-copas', fb: '2022 × 2026' },      // portfolio.world_cup.nav_comparativo
{ id: 'historia-copas',    fb: 'História' },          // portfolio.world_cup.nav_historia
```

### MOTION
O bloco motion do esqueleto já varre `main section[id]` e revela `.section-head`
+ `.wc-kpi, .wc-scorers-wrap, .wc-stat-card`. Para animar os cards destas
seções, amplie o seletor de cards para incluir os novos containers:
`.wc-cl-block, .wc-c22-block, .wc-insight-card, .wc-c22-context-card`
(opcional — sem isso as seções aparecem sem stagger, o que é aceitável).

---

## 4. Chart.js → SVG (mapeamento por gráfico)

| Legado (Chart.js) | id container | Primitiva SVG | Observações |
|---|---|---|---|
| classics posse (line) | `wc-cl-poss-chart` | `lineChart` | 2 séries home/away; x = índice do intervalo, `xFmt` devolve o rótulo `"1-15"`; `spanGaps` reproduzido filtrando pontos `null` |
| classics passe (line) | `wc-cl-pass-chart` | `lineChart` | idem |
| classics PPDA (line) | `wc-cl-ppda-chart` | `lineChart` | idem (menor = melhor; sem eixo invertido — só nota textual) |
| ranking seleções (bar `indexAxis:y`) | `c22-team-chart` | `barChart({orientation:'h'})` | métrica selecionável; tooltip custom (métrica + xG/gols/jogos); re-render no change do `<select>` |
| finalizadores gols−xG | `c22-finishing-chart` | `barChart({orientation:'h', diverging:true})` | cor por sinal (verde ≥0, ouro <0) via `color` por barra |
| gols por minuto 2022×2026 | `c22-minute-chart` | `barChart({orientation:'v', series:[…]})` | agrupado (2 séries); `values:[pct2022, pct2026]` casados por `range` |
| campeões (bar `indexAxis:y`) | `c22-hist-champions` | `barChart({orientation:'h'})` | ouro; #1 `highlight`; tooltip anos |
| participações (bar `indexAxis:y`) | `c22-hist-participations` | `barChart({orientation:'h'})` | verde; tooltip `note` |
| doughnut halves ([02]) | — | (já no esqueleto) | fora do escopo deste frag |

Todos os tooltips do Chart.js viram `TipContent` (título + rows) das
primitivas. A cor NUNCA é hex fixo — vem de `readToken('--wc-field-ink'…)` /
`--wc-gold-ink` / `--wc-live-ink` (com fallback), respeitando a paleta WC.

Tabelas e bentos (artilharia 2022, campeões/participações tables, highlights,
deltas, big-numbers, contexto) continuam via `innerHTML` — não são charts.

---

## 5. Barras `.wc-stat-row` — animação de fill

As barras de comparação/volume ([09]) são `<div>`s planos com `transition:
width 700ms` no CSS (`.wc-stat-row__bar-home/away`). Bug conhecido do legado: se
você injeta com `style="width:X%"` direto no innerHTML, a barra "nasce" cheia e
a transição não dispara (não há estado inicial). **Correção adotada** (mesma
abordagem do `deepstats.js`): `cmpRow()` injeta `style="width:0"` +
`data-w="X"`, e `fillBars(host)` grava a largura-alvo dentro de um
`requestAnimationFrame` após o `innerHTML` — aí o browser tem um frame com
`width:0` e a transição para `X%` anima. Sob `prefers-reduced-motion` o CSS
zera a `transition` (regra `@media` já existente), então vira snap direto — sem
JS extra. `fillBars` é chamado em `cmpRenderCompare()` e `cmpRenderVolume()`.

---

## 6. `<select>` SPA-safe (classics partida + panorama métrica)

Ambos re-populam o `<option>` set e re-vinculam o `change` a cada render,
guardando o handler em `sel._wcHandler` e fazendo `removeEventListener` antes de
re-adicionar → nunca duplica listener após navegação `astro:page-load`. Não
usam `<astro>` islands; são `<select>` nativos estilizados por `.wc-cl-select`.

---

## 7. CSS a copiar de `public/world-cup-dashboard/css/style.css`

Copie estes blocos para o `<style>` da página Astro. **Tudo que é injetado via
JS (innerHTML) precisa de `:global()`** sob um ancestral estático (CSS scoped do
Astro não alcança innerHTML). Os containers estáticos que existem no markup
(`.wc-cl-block`, `.wc-c22-block`, `.wc-stat-compare`, `.wc-insights-grid`,
`.wc-c22-context`, `.wc-c22-bignumbers`, `.wc-c22-two-col`, `.wc-match-select-wrap`)
podem ficar sem `:global()`; os filhos gerados por JS precisam.

| Bloco no style.css | linhas aprox. | precisa `:global()`? |
|---|---|---|
| `.tag--wc` | 367–371 | **sim** (context cards são injetadas) |
| `.wc-skeleton` / `.wc-skeleton-card` / `@keyframes wc-shimmer` | 1736–1773 | não (placeholders estáticos no markup) |
| `.wc-insights-grid` (+ media) | 2526–2532 | não (container estático) |
| `.wc-insight-card*` (todas as variantes `--field/--gold/--ink/--live/--hero/--md`, `__head/__title/__body/__key`) | 2534–2590 | **sim** (highlights/deltas injetados) |
| `.wc-match-select-wrap` + `> .mono-label` | 3159–3169 | não (estático) |
| `.wc-stat-compare` + `__head/__team/__team--right/__team-name` | 3206–3252 | `.wc-stat-compare` estático; `__head/__team*` **sim** (injetados por cmpHead) |
| `.wc-stat-rows` | 3255–3259 | **sim** |
| `.wc-stat-row` + `__home/__away/__bar/__bar-home/__bar-away/__label` | 3264–3314 | **sim** (todo o row é injetado) |
| `.wc-stat-subhead` | 3317–3322 | **sim** (injetado no compare) |
| `.wc-stat-compare__source` | 3325–3329 | **sim** |
| `@media reduce { .wc-stat-row__bar-* }` | 3332–3337 | **sim** — mantém `!important` (só sob reduced-motion, permitido) |
| `.wc-cl-select` (+ hover/focus) | 3799–3826 | não (estático); o `<option>` interno é injetado mas herda estilo do UA |
| `.wc-cl-meta` | 3828–3832 | não (estático `#wc-classics-meta`) |
| `.wc-cl-block` (+ media) | 3834–3840 | não (estático) |
| `.wc-cl-block__title` / `__unit` | 3841–3857 | `__title` estático; **`__unit` é usado tanto estático quanto em `.wc-c22-block__title .wc-cl-block__unit`** — copie ambos |
| `.wc-cl-table*` (`__corner/__team/__num/__row--lead`, `.wc-flag`, `tbody tr+tr`) | 3860–3898 | **sim** (tabela inteira injetada em `#wc-cl-*-table`) |
| `.wc-cl-block__chart` | 3900 | não (container estático) — mas remova a altura fixa inline: a lib SVG é responsiva (`height:auto`); ver nota abaixo |
| `.wc-cl-note` / `.wc-cl-note strong` | 3902–3908 | `.wc-cl-note` estático; `strong` estático também (está no markup) |
| `.wc-c22-block` / `__head` / `__title` / `__title .wc-cl-block__unit` / `__chart` | 3914–3944 | estáticos (containers) — sem `:global()` |
| `.wc-c22-bignumbers` (+ media, `> .wc-stat-card--wide`) | 3947–3959 | container estático; **os `.wc-stat-card` filhos são injetados → o seletor `> .wc-stat-card--wide` precisa `:global()`** |
| `.wc-c22-two-col` (+ media) | 3962–3970 | não (estático) |
| `.wc-c22-context` / `__head` / `__grid` (+ media) | 3973–3985 | `.wc-c22-context` estático; `__head/__grid` **sim** (injetados) |
| `.wc-c22-context-card*` (`__title/__body/__src`) | 3986–4015 | **sim** (injetados) |

Além disso, os `.wc-stat-card` / `.wc-stat-card__value` / `__sub` /
`--wide` usados pelos big-numbers históricos: o esqueleto **já define
`.wc-stat-card`** (não-global, para o bento estático de [02]). Como os
big-numbers são injetados via JS, adicione versões `:global()` de
`.wc-stat-card`, `.wc-stat-card__value`, `.wc-stat-card__sub`,
`.wc-stat-card--wide` OU envolva-as sob `#c22-hist-bignumbers :global(.wc-stat-card…)`.
Recomendado: escopar por ancestral —
`#c22-hist-bignumbers :global(.wc-stat-card) { … }` — para não colidir com o
`.wc-stat-card` estático do esqueleto.

### Resumo — seletores que EXIGEM `:global()` (todos JS-injected)
`.wc-cl-table` e filhos · `.wc-insight-card` e todas as variantes/filhos ·
`.wc-stat-compare__head/__team/__team-name/__source` · `.wc-stat-rows` ·
`.wc-stat-row` e filhos · `.wc-stat-subhead` · `.wc-c22-context__head/__grid` ·
`.wc-c22-context-card` e filhos · `.tag--wc` · `.wc-c22-bignumbers > .wc-stat-card--wide`
· os `.wc-stat-card*` dos big-numbers · `.wc-scorers-table__*` das linhas de
tabela injetadas (o esqueleto **já tem** `#wc-scorers-body :global(...)`;
replique o padrão para `#c22-scorers-body`, `#c22-hist-scorers`,
`#c22-hist-appearances`).

Fundos alternados das seções (definir no `<style>`, seguindo o padrão do
esqueleto — use tokens `--paper*`):
```css
.wc-classics-section { background: var(--paper); }
.wc-c22-section { background: var(--paper); }
.wc-c22-section--alt { background: var(--paper-soft); }
```

### Nota sobre altura dos charts
No legado o `<canvas>` vivia num wrapper com `height:clamp(...)` inline
(Chart.js precisa de altura fixa). A lib SVG é **responsiva por viewBox**
(`svg { width:100%; height:auto }`), então **removi o `style="height:…"`** dos
containers no `cap23.html`. Se quiser preservar a mancha vertical do legado,
aplique `min-height` via CSS no container (opcional) — não é necessário.

---

## 8. i18n — chaves

Todas as chaves usadas JÁ EXISTEM em `assets/i18n/{pt-BR,en-US,es-ES}.json` sob
`portfolio.world_cup.*` (verificado no pt-BR): `classicos_*`, `panorama_*`,
`comparativo_*`, `historia_*`, `statsbomb_source`, `select_match`,
`select_metric`, `col_rank/player/goals/pen/cups/games`, `nav_classicos`,
`nav_panorama`, `nav_comparativo`, `nav_historia`.

**Nenhuma chave nova foi inventada.** Textos SEM chave i18n (ficam pt-BR fixo,
igual ao legado — são conteúdo dinâmico/dado, não UI traduzível):

- Rótulos `Total / 1º tempo / 2º tempo` da tabela classics (gerados no TS).
- Cabeçalhos das colunas `xG` (panorama) e do compare (`Copa 2022 / Copa 2026`,
  `Copa 2022 · StatsBomb`, `Copa 2026 · ESPN`), `Formato do torneio`.
- Títulos/labels dos cards de highlights, deltas e big-numbers (vêm do dado ou
  são strings editoriais no TS — o legado também não os traduzia).
- Labels das linhas de comparação (`Média de gols por jogo`, etc.) e as métricas
  do `<select>` (`TEAM_METRICS`) — hardcoded no TS, como no legado.

Se a paridade i18n dessas quiser ser ampliada no futuro, criar chaves novas em
`portfolio.world_cup.*` (ex.: `cl_table_total`, `c22_team_2022`, …) nos três
dicionários — **fora do escopo** deste fragmento.

---

## 9. Dados ausentes em `assets/data/worldcup/` (AÇÃO NECESSÁRIA)

No estado atual do repo, `assets/data/worldcup/` tem `classics_2022.json`,
`copa2022_panorama.json`, `comparativo_copas.json`, `idade_copas.json`, mas
**faltam `historia_copas.json` e `contexto_copas.json`** (só existem em
`public/world-cup-dashboard/data/`). A §[10] História degrada sozinha
(fail-soft: mostra `#c22-hist-error` e oculta os cards de contexto) até esses
dois JSONs serem copiados para `assets/data/worldcup/`. Copiar:

```
cp public/world-cup-dashboard/data/historia_copas.json assets/data/worldcup/
cp public/world-cup-dashboard/data/contexto_copas.json assets/data/worldcup/
```

(São dados estáticos/curados — mesmo tratamento dos demais JSONs do bloco 2022.)
