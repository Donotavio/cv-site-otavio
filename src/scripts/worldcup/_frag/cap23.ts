/**
 * cap23.ts — Capítulo 2 + 3 do World Cup Dashboard (bloco 2022 / histórico).
 * ============================================================================
 * Porta os módulos vanilla `public/world-cup-dashboard/js/classics.js` e
 * `copa2022.js` para dentro do Astro, trocando TODO uso de Chart.js pelas
 * primitivas SVG hand-rolled de `../charts` (barChart / lineChart). Zero
 * dependência externa; runtime só faz fetch dos JSONs já prontos.
 *
 * Seções cobertas (mono-labels em cap23.html):
 *   [07] wc-classics        → renderClassics(classics)
 *   [08] copa2022-panorama  → renderPanorama(panorama)
 *   [09] comparativo-copas  → renderComparativo(comparativo, idade)
 *   [10] historia-copas     → renderHistoria(historia, contexto)
 *
 * Mapa Chart.js → primitiva SVG:
 *   classics: 3 line charts (posse/passe/PPDA por intervalo)  → lineChart()
 *   c22-team-chart  (ranking por métrica, barras horizontais) → barChart({orientation:'h'})
 *   c22-finishing-chart (gols−xG, diverge por sinal)          → barChart({orientation:'h', diverging})
 *   c22-minute-chart (2022 vs 2026, agrupado vertical)        → barChart({orientation:'v', series})
 *   c22-hist-champions (títulos)                              → barChart({orientation:'h'})
 *   c22-hist-participations (participações)                   → barChart({orientation:'h'})
 *   As tabelas (Total/1º/2º, artilharia, campeões, participações) e os bentos
 *   (highlights, deltas, big-numbers, contexto) continuam via innerHTML.
 *
 * Barras .wc-stat-row (comparação/volume): são <div>s planos com transição CSS
 * `width 700ms`. Para a animação disparar, injetamos com `width:0` e o alvo em
 * `data-w`, e no `requestAnimationFrame` seguinte gravamos a largura real —
 * mesmo truque do deepstats (evita o bug de a barra "nascer" cheia sem animar).
 * Sob prefers-reduced-motion a transição é neutralizada por CSS → snap direto.
 *
 * Idempotente + fail-soft: cada render limpa/regrava seu host; erro em uma parte
 * não derruba as outras (o orquestrador chama cada uma via safe()). SPA-safe:
 * os <select> re-vinculam o handler a cada render (removeEventListener guardado).
 *
 * @module worldcup/_frag/cap23
 */

import { barChart, lineChart, readToken } from '../charts';
import type { BarDatum } from '../charts';

/* ────────────────────────────────────────────────────────────────────────── */
/* Helpers compartilhados                                                       */
/* ────────────────────────────────────────────────────────────────────────── */

const $ = (sel: string, root?: ParentNode): HTMLElement | null =>
  (root || document).querySelector(sel);

function esc(s: unknown): string {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

const reduceMotion = (): boolean =>
  typeof window !== 'undefined' && !!window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Número pt-BR: vírgula decimal, "—" p/ nulo. */
function fmtNum(v: unknown, dec?: number): string {
  if (v == null || Number.isNaN(Number(v))) return '—';
  return Number(v).toFixed(dec == null ? 0 : dec).replace('.', ',');
}
/** Número com sinal explícito (+/−). */
function signed(v: unknown, dec?: number): string {
  if (v == null || Number.isNaN(Number(v))) return '—';
  const n = Number(v);
  return (n > 0 ? '+' : '') + fmtNum(n, dec);
}
/** Número + unidade (classics: %, anos…). */
function fmtUnit(v: unknown, dec: number, unit?: string): string {
  const s = fmtNum(v, dec);
  return s === '—' ? s : (unit ? s + unit : s);
}

/** Paleta WC resolvida dos tokens (nunca hex fixo). */
function pal() {
  return {
    field: readToken('--wc-field-ink', '#0B6B2E'),
    gold: readToken('--wc-gold-ink', '#8A5A06'),
    live: readToken('--wc-live-ink', '#B23A48'),
    ink: readToken('--ink', '#0A0A0A'),
  };
}

/** Rótulo acessível do container (já traduzido em runtime via data-i18n-aria). */
function ariaOf(el: HTMLElement, fallback: string): string {
  return el.getAttribute('aria-label') || fallback;
}

/**
 * Reveal local para conteúdo injetado ([data-reveal]) — espelha o
 * observeReveals do copa2022.js. Se não houver IO ou motion reduzida, mostra na
 * hora. (Se a página não copiar o CSS de [data-reveal], os cards já ficam
 * visíveis — o observer só adiciona is-visible, nunca esconde.)
 */
function observeReveals(root: HTMLElement): void {
  const items = Array.from(root.querySelectorAll<HTMLElement>('[data-reveal]'));
  if (!('IntersectionObserver' in window) || reduceMotion()) {
    items.forEach((el) => el.classList.add('is-visible'));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) { (e.target as HTMLElement).classList.add('is-visible'); io.unobserve(e.target); }
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
  items.forEach((el) => io.observe(el));
}

/**
 * Linha comparativa .wc-stat-row (home = 2022/verde, away = 2026/ouro).
 * Injeta as barras com width:0 + data-w (alvo). fillBars() grava a largura real
 * no próximo frame → dispara a transição CSS. Fiel ao componente da ficha ESPN.
 */
function cmpRow(label: string, v22: unknown, v26: unknown, dec: number, unit?: string): string {
  const f = (v: unknown) => (v == null ? '—' : fmtNum(v, dec) + (unit || ''));
  const a = Math.max(0, Number(v22) || 0);
  const b = Math.max(0, Number(v26) || 0);
  const tot = a + b;
  const pa = tot > 0 ? (a / tot) * 100 : 50;
  const pb = tot > 0 ? (b / tot) * 100 : 50;
  return `
    <div class="wc-stat-row">
      <span class="wc-stat-row__home">${esc(f(v22))}</span>
      <div class="wc-stat-row__bar" aria-hidden="true">
        <span class="wc-stat-row__bar-home" style="width:0" data-w="${pa.toFixed(2)}"></span>
        <span class="wc-stat-row__bar-away" style="width:0" data-w="${pb.toFixed(2)}"></span>
      </div>
      <span class="wc-stat-row__away">${esc(f(v26))}</span>
      <span class="wc-stat-row__label">${esc(label)}</span>
    </div>`;
}

/** Aplica as larguras-alvo das barras no frame seguinte à inserção (anima o fill). */
function fillBars(host: HTMLElement): void {
  const bars = Array.from(host.querySelectorAll<HTMLElement>('.wc-stat-row__bar-home[data-w], .wc-stat-row__bar-away[data-w]'));
  if (!bars.length) return;
  requestAnimationFrame(() => {
    bars.forEach((b) => { b.style.width = (b.dataset.w || '0') + '%'; });
  });
}

/* ══════════════════════════════════════════════════════════════════════════ */
/* [07] CLÁSSICOS 2022                                                          */
/* ══════════════════════════════════════════════════════════════════════════ */

interface ClTeam { name?: string; code?: string; flag?: string }
interface ClSide { home?: number | null; away?: number | null }
interface ClBlock {
  labels?: string[];
  series?: { home?: (number | null)[]; away?: (number | null)[] };
  total?: ClSide; first?: ClSide; second?: ClSide;
}
interface ClMatch {
  id: string; label: string; date?: string; stage?: string;
  home: ClTeam; away: ClTeam; labels?: string[];
  possession?: ClBlock; pass_accuracy?: ClBlock; ppda?: ClBlock;
}
interface ClassicsData {
  featured_id?: string;
  match_list?: { id: string; label: string; stage?: string }[];
  matches?: Record<string, ClMatch>;
}

interface ClMetric {
  key: 'possession' | 'pass_accuracy' | 'ppda';
  host: string; title: string; unit: string; decimals: number; betterHigh: boolean;
}
const CL_METRICS: ClMetric[] = [
  { key: 'possession',    host: 'poss', title: 'Posse de bola',    unit: '%', decimals: 1, betterHigh: true },
  { key: 'pass_accuracy', host: 'pass', title: 'Precisão de passe', unit: '%', decimals: 1, betterHigh: true },
  { key: 'ppda',          host: 'ppda', title: 'PPDA (pressão)',    unit: '',  decimals: 1, betterHigh: false },
];
const STAGE_PT: Record<string, string> = {
  'Final': 'Final', '3rd Place Final': 'Disputa de 3º lugar',
  'Semi-finals': 'Semifinal', 'Quarter-finals': 'Quartas de final',
  'Round of 16': 'Oitavas de final', 'Group Stage': 'Fase de grupos',
};

let _clData: ClassicsData | null = null;
let _clSelectedId: string | null = null;

/** Tabela Total / 1º / 2º de uma métrica (líder da coluna Total em ouro). */
function clTableHtml(match: ClMatch, block: ClBlock, metric: ClMetric): string {
  const cell = (side: 'home' | 'away', which: 'total' | 'first' | 'second') => {
    const b = block[which] as ClSide | undefined;
    return fmtUnit(b ? b[side] : null, metric.decimals, metric.unit);
  };
  const ht = block.total ? block.total.home : null;
  const at = block.total ? block.total.away : null;
  let homeLead = false, awayLead = false;
  if (ht != null && at != null && ht !== at) {
    const homeBetter = metric.betterHigh ? ht > at : ht < at;
    homeLead = homeBetter; awayLead = !homeBetter;
  }
  const row = (side: 'home' | 'away', team: ClTeam, lead: boolean) => `
    <tr${lead ? ' class="wc-cl-table__row--lead"' : ''}>
      <th scope="row" class="wc-cl-table__team">
        <span class="wc-flag" aria-hidden="true">${esc(team.flag || '🏳️')}</span>
        <span>${esc(team.name || team.code || '')}</span>
      </th>
      <td class="wc-cl-table__num">${cell(side, 'total')}</td>
      <td class="wc-cl-table__num">${cell(side, 'first')}</td>
      <td class="wc-cl-table__num">${cell(side, 'second')}</td>
    </tr>`;
  return `
    <table class="wc-cl-table">
      <thead>
        <tr>
          <th scope="col" class="wc-cl-table__corner"></th>
          <th scope="col" class="wc-cl-table__num">Total</th>
          <th scope="col" class="wc-cl-table__num">1º tempo</th>
          <th scope="col" class="wc-cl-table__num">2º tempo</th>
        </tr>
      </thead>
      <tbody>
        ${row('home', match.home, homeLead)}
        ${row('away', match.away, awayLead)}
      </tbody>
    </table>`;
}

/** Gráfico de linha por intervalo (home vs away) via lineChart SVG. */
function clRenderChart(hostId: string, match: ClMatch, block: ClBlock, metric: ClMetric): void {
  const box = document.getElementById(hostId);
  if (!box) return;
  const labels = block.labels || match.labels || [];
  const homeLbl = match.home.code || match.home.name || 'Casa';
  const awayLbl = match.away.code || match.away.name || 'Fora';
  const P = pal();
  // x numérico = índice do intervalo; xFmt devolve o rótulo textual ("1-15"…).
  const toPts = (arr?: (number | null)[]) =>
    (arr || []).map((y, i) => ({ x: i, y })).filter((p): p is { x: number; y: number } => p.y != null);
  const home = toPts(block.series?.home);
  const away = toPts(block.series?.away);
  if (!home.length && !away.length) {
    box.innerHTML = '<p class="wc-error mono-label">série indisponível</p>';
    return;
  }
  lineChart(box, {
    ariaLabel: ariaOf(box, `${metric.title} por intervalo de 15 minutos, casa vs. fora.`),
    xTitle: 'intervalo (min)',
    yTitle: metric.title + (metric.unit ? ` (${metric.unit})` : ''),
    valueFmt: (v) => fmtUnit(v, metric.decimals, metric.unit),
    xFmt: (x) => labels[Math.round(x)] ?? String(x),
    series: [
      { label: homeLbl, points: home, color: P.field },
      { label: awayLbl, points: away, color: P.gold },
    ],
  });
}

function clRenderMetric(match: ClMatch, metric: ClMetric): void {
  const tableHost = document.getElementById(`wc-cl-${metric.host}-table`);
  const block = (match[metric.key] as ClBlock) || {};
  if (tableHost) tableHost.innerHTML = clTableHtml(match, block, metric);
  clRenderChart(`wc-cl-${metric.host}-chart`, match, block, metric);
}

function clRenderAll(): void {
  const err = $('#wc-classics-error');
  const match = _clData?.matches && _clSelectedId ? _clData.matches[_clSelectedId] : null;
  if (!match) { if (err) (err as HTMLElement).hidden = false; return; }
  if (err) (err as HTMLElement).hidden = true;

  const meta = $('#wc-classics-meta');
  if (meta) {
    const stage = STAGE_PT[match.stage || ''] || match.stage || '';
    meta.textContent = [stage, match.label].filter(Boolean).join(' · ');
  }
  CL_METRICS.forEach((m) => {
    try { clRenderMetric(match, m); }
    catch (e) { console.error(`[wc-cap23] classics ${m.key}:`, e); }
  });
}

/** Popula o <select> agrupado por fase e (re)vincula o change — SPA-safe. */
function clPopulateSelect(matchList: NonNullable<ClassicsData['match_list']>, featuredId: string | null): void {
  const sel = document.getElementById('wc-classics-select') as (HTMLSelectElement & { _wcHandler?: () => void }) | null;
  if (!sel || !Array.isArray(matchList) || !matchList.length) return;
  const groups = new Map<string, typeof matchList>();
  matchList.forEach((m) => {
    const g = m.stage || 'Partidas';
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g)!.push(m);
  });
  let html = '';
  for (const [stage, items] of groups) {
    html += `<optgroup label="${esc(STAGE_PT[stage] || stage)}">`;
    html += items.map((m) =>
      `<option value="${esc(m.id)}"${m.id === featuredId ? ' selected' : ''}>${esc(m.label)}</option>`).join('');
    html += '</optgroup>';
  }
  sel.innerHTML = html;
  if (featuredId) sel.value = featuredId;
  if (sel._wcHandler) sel.removeEventListener('change', sel._wcHandler);
  const handler = () => { if (sel.value) { _clSelectedId = sel.value; clRenderAll(); } };
  sel._wcHandler = handler;
  sel.addEventListener('change', handler);
}

export function renderClassics(data: ClassicsData | null): void {
  const host = document.getElementById('wc-classics');
  if (!host) return;
  const err = $('#wc-classics-error');
  if (!data || !data.matches) { if (err) (err as HTMLElement).hidden = false; return; }
  if (err) (err as HTMLElement).hidden = true;
  _clData = data;
  _clSelectedId = data.featured_id || data.match_list?.[0]?.id || null;
  if (Array.isArray(data.match_list)) clPopulateSelect(data.match_list, _clSelectedId);
  clRenderAll();
}

/* ══════════════════════════════════════════════════════════════════════════ */
/* [08] COPA 2022 — PANORAMA                                                    */
/* ══════════════════════════════════════════════════════════════════════════ */

interface TeamRow {
  name: string; code?: string; flag?: string; matches?: number;
  goals_for?: number; xg_for?: number; xg_diff?: number;
  [k: string]: unknown;
}
interface FinishingRow {
  player: string; flag?: string; goals?: number; shots?: number;
  xg?: number; xg_diff?: number; xg_per_shot?: number; conversion_pct?: number;
}
interface ScorerRow { player: string; team?: string; flag?: string; goals?: number; penalties?: number; xg?: number }
interface PanoramaData {
  matches?: number;
  team_xg: TeamRow[];
  finishing: FinishingRow[];
  scorers?: ScorerRow[];
  highlights?: Record<string, any>;
}

interface TeamMetric { key: string; label: string; dec: number; high: boolean; unit?: string; signed?: boolean }
const TEAM_METRICS: TeamMetric[] = [
  { key: 'xg_for',                 label: 'xG a favor',              dec: 2, high: true },
  { key: 'xg_diff',                label: 'Gols − xG (finalização)', dec: 2, high: true, signed: true },
  { key: 'goals_for',              label: 'Gols marcados',           dec: 0, high: true },
  { key: 'possession_avg',         label: 'Posse média',             dec: 1, high: true, unit: '%' },
  { key: 'ppda_avg',               label: 'PPDA (pressão)',          dec: 1, high: false },
  { key: 'passes_per_match',       label: 'Passes por jogo',         dec: 0, high: true },
  { key: 'pass_accuracy_avg',      label: 'Precisão de passe',       dec: 1, high: true, unit: '%' },
  { key: 'shots_per_match',        label: 'Chutes por jogo',         dec: 1, high: true },
  { key: 'shots_on_pct',           label: 'Chutes no alvo',          dec: 1, high: true, unit: '%' },
  { key: 'pressures_per_match',    label: 'Pressões por jogo',       dec: 1, high: true },
  { key: 'duel_win_pct',           label: 'Duelos ganhos',           dec: 1, high: true, unit: '%' },
  { key: 'prog_carries_per_match', label: 'Conduções progr./jogo',   dec: 1, high: true },
];

let _panorama: PanoramaData | null = null;
let _teamMetric: TeamMetric = TEAM_METRICS[0];

/** Encurta nomes StatsBomb: "Lionel Andrés Messi Cuccittini" → "L. Messi". */
function shortName(name?: string): string {
  if (!name) return '';
  const parts = String(name).trim().split(/\s+/);
  if (parts.length <= 2) return name;
  return parts[0][0] + '. ' + parts[parts.length - 1];
}

function panRenderTeamChart(): void {
  const box = document.getElementById('c22-team-chart');
  if (!box || !_panorama) return;
  const m = _teamMetric;
  const rows = _panorama.team_xg
    .filter((t) => t[m.key] != null)
    .sort((a, b) => (m.high ? Number(b[m.key]) - Number(a[m.key]) : Number(a[m.key]) - Number(b[m.key])))
    .slice(0, 12);
  const data: BarDatum[] = rows.map((t) => ({
    label: `${t.flag || ''} ${t.code || t.name}`.trim(),
    value: Number(t[m.key]) || 0,
    meta: t,
  }));
  barChart(box, {
    orientation: 'h',
    ariaLabel: ariaOf(box, 'Ranking das seleções da Copa 2022 pela métrica selecionada.'),
    axisTitle: m.label + (m.unit ? ` (${m.unit})` : ''),
    valueFmt: (v) => fmtNum(v, m.dec) + (m.unit || ''),
    data,
    tooltip: (d) => {
      const t = d.meta as TeamRow;
      const val = m.signed ? signed(t[m.key], m.dec) : fmtNum(t[m.key], m.dec) + (m.unit || '');
      return {
        title: t.name,
        rows: [
          { name: m.label, value: val },
          { name: 'xG · gols · jogos', value: `${fmtNum(t.xg_for, 2)} · ${t.goals_for} · ${t.matches}` },
        ],
      };
    },
  });
  const note = $('#c22-team-note');
  if (note) {
    note.textContent = m.key === 'ppda_avg'
      ? 'PPDA: menor = pressão mais intensa (ranking do mais pressionador ao menos).'
      : `Top 12 seleções por ${m.label.toLowerCase()} — Copa 2022 (torneio inteiro).`;
  }
}

function panPopulateMetricSelect(): void {
  const sel = document.getElementById('c22-metric-select') as (HTMLSelectElement & { _wcHandler?: () => void }) | null;
  if (!sel) return;
  sel.innerHTML = TEAM_METRICS.map((m) =>
    `<option value="${esc(m.key)}">${esc(m.label)}${m.unit ? ' (' + m.unit + ')' : ''}</option>`).join('');
  sel.value = _teamMetric.key;
  if (sel._wcHandler) sel.removeEventListener('change', sel._wcHandler);
  const handler = () => {
    _teamMetric = TEAM_METRICS.find((m) => m.key === sel.value) || TEAM_METRICS[0];
    try { panRenderTeamChart(); } catch (e) { console.error('[wc-cap23] team chart:', e); }
  };
  sel._wcHandler = handler;
  sel.addEventListener('change', handler);
}

function panRenderFinishing(): void {
  const box = document.getElementById('c22-finishing-chart');
  if (!box || !_panorama) return;
  const P = pal();
  const all = _panorama.finishing.filter((f) => f.xg_diff != null);
  const top = all.slice(0, 8);                          // já vem ordenado desc
  const bottom = all.slice(-6).filter((f) => (f.xg_diff ?? 0) < 0);
  const rows = top.concat(bottom.reverse());
  const data: BarDatum[] = rows.map((f) => {
    const v = Number(f.xg_diff) || 0;
    return { label: `${f.flag || ''} ${shortName(f.player)}`.trim(), value: v, color: v >= 0 ? P.field : P.gold, meta: f };
  });
  barChart(box, {
    orientation: 'h',
    diverging: true,
    ariaLabel: ariaOf(box, 'Jogadores da Copa 2022 por diferença entre gols e xG.'),
    axisTitle: 'gols acima (+) / abaixo (−) do xG',
    valueFmt: (v) => signed(v, 2),
    data,
    tooltip: (d) => {
      const f = d.meta as FinishingRow;
      return {
        title: f.player,
        rows: [
          { name: 'gols − xG', value: signed(f.xg_diff, 2), leader: (f.xg_diff ?? 0) >= 0 },
          { name: 'gols / chutes', value: `${f.goals} / ${f.shots} (xG ${fmtNum(f.xg, 2)})` },
          { name: 'conversão · xG/chute', value: `${fmtNum(f.conversion_pct, 1)}% · ${fmtNum(f.xg_per_shot, 2)}` },
        ],
      };
    },
  });
}

function panRenderScorers(): void {
  const body = $('#c22-scorers-body');
  if (!body || !_panorama) return;
  const top = (_panorama.scorers || []).slice(0, 10);
  if (!top.length) {
    body.innerHTML = '<tr><td colspan="5" class="wc-error mono-label">artilharia indisponível</td></tr>';
    return;
  }
  body.innerHTML = top.map((s, i) => {
    const rank = i + 1;
    const isGold = rank === 1;
    const badge = isGold ? ' <span class="wc-scorers-table__gold-badge" aria-label="Chuteira de Ouro">🏆 Ouro</span>' : '';
    return `
      <tr class="${isGold ? 'wc-scorers-table__row--gold' : ''}">
        <td class="wc-scorers-table__rank-cell">${rank}${badge}</td>
        <td>
          <div class="wc-scorers-table__player-cell">
            <span class="wc-flag" aria-hidden="true">${s.flag ? esc(s.flag) : '—'}</span>
            <span class="wc-scorers-table__name-block">
              <span class="wc-scorers-table__name">${esc(s.player)}</span>
              <span class="wc-scorers-table__sub">${esc(s.team || '')}</span>
            </span>
          </div>
        </td>
        <td class="wc-scorers-table__goals-cell">${s.goals}</td>
        <td class="wc-scorers-table__pen-cell">${s.penalties || 0}</td>
        <td class="wc-scorers-table__pen-cell">${fmtNum(s.xg, 2)}</td>
      </tr>`;
  }).join('');
}

function panRenderHighlights(): void {
  const host = $('#c22-highlights');
  if (!host || !_panorama) return;
  const h = _panorama.highlights || {};
  const card = (title: string, obj: any, cat: string, key: string, nameField: string, sub: string) =>
    obj ? { cat, title, key, name: `${obj.flag || ''} ${esc(obj[nameField] || '')}`.trim(), sub } : null;
  const cw = h.most_clinical_player, ww = h.most_wasteful_player;
  const cards = [
    card('Melhor ataque (xG)', h.top_xg_team, 'gold', fmtNum(h.top_xg_team?.xg_for, 1), 'name', 'xG a favor no torneio'),
    card('Mais eficiente', h.most_overperforming_team, 'field', signed(h.most_overperforming_team?.xg_diff, 1), 'name', 'gols acima do xG'),
    card('Mais clínico', cw, 'field', signed(cw?.xg_diff, 1), 'player', cw ? `${cw.goals} gols · xG ${fmtNum(cw.xg, 1)} · ${cw.shots} chutes` : ''),
    card('Mais perdulário', ww, 'live', signed(ww?.xg_diff, 1), 'player', ww ? `${ww.goals} gol(s) em ${ww.shots} chutes · xG ${fmtNum(ww.xg, 1)}` : ''),
    card('Melhor defesa (xG)', h.best_defense_xg, 'ink', fmtNum(h.best_defense_xg?.xg_against, 1), 'name', 'menor xG sofrido'),
    card('Mais pressão (PPDA)', h.most_pressing_team, 'field', fmtNum(h.most_pressing_team?.ppda_avg, 1), 'name', 'PPDA — menor = +intenso'),
    card('Mais posse', h.most_possession_team, 'gold', fmtNum(h.most_possession_team?.possession_avg, 1) + '%', 'name', 'posse média'),
    card('Mais finalizadora', h.most_shots_team, 'ink', String(h.most_shots_team ? h.most_shots_team.shots : '—'), 'name', 'chutes no torneio'),
  ].filter(Boolean) as { cat: string; title: string; key: string; name: string; sub: string }[];
  const layout = ['hero', 'hero', 'md', 'md', 'md', 'md', 'hero', 'hero'];
  host.innerHTML = cards.map((c, i) => `
    <article class="wc-insight-card wc-insight-card--${c.cat} wc-insight-card--${layout[i] || 'md'}" data-reveal>
      <header class="wc-insight-card__head"><h3 class="mono-label wc-insight-card__cat">${esc(c.title)}</h3></header>
      <p class="wc-insight-card__title" aria-hidden="true"><span class="wc-insight-card__key">${esc(c.key)}</span></p>
      <p class="wc-insight-card__body">${c.name}<br><span class="mono-label" style="color:var(--ink-faint)">${esc(c.sub || '')}</span></p>
    </article>`).join('');
  observeReveals(host);
}

export function renderPanorama(data: PanoramaData | null): void {
  const host = document.getElementById('copa2022-panorama');
  if (!host) return;
  const err = $('#c22-pan-error');
  if (!data || !Array.isArray(data.team_xg)) { if (err) (err as HTMLElement).hidden = false; return; }
  if (err) (err as HTMLElement).hidden = true;
  _panorama = data;
  const meta = $('#c22-pan-meta');
  if (meta) meta.textContent = `${data.matches || 64} partidas · ${data.team_xg.length} seleções · dado de evento StatsBomb`;
  panPopulateMetricSelect();
  panRenderTeamChart();
  panRenderFinishing();
  panRenderScorers();
  panRenderHighlights();
}

/* ══════════════════════════════════════════════════════════════════════════ */
/* [09] COPA 2022 × 2026                                                        */
/* ══════════════════════════════════════════════════════════════════════════ */

interface TournBlock {
  teams?: number; total_matches?: number; total_goals?: number;
  avg_goals_per_match?: number; goals_first_half_pct?: number; goals_second_half_pct?: number;
  penalties_scored?: number; own_goals?: number;
  biggest_win?: { diff?: number } | null;
  goals_by_minute?: { range: string; pct: number }[];
}
interface ComparativoData {
  source?: string;
  tournaments?: Record<string, TournBlock>;
  deltas?: Record<string, number>;
  volume?: { note?: string; metrics?: { key: string; label: string; unit?: string; dec: number; v2022: number | null; v2026: number | null; only_2022?: boolean }[] };
}
interface IdadeData {
  tournaments?: Record<string, { avg_age?: number }>;
  deltas?: { avg_age?: number };
}

let _comparativo: ComparativoData | null = null;
let _idade: IdadeData | null = null;

function cmpHead(left: string, right: string, leftFlag = '🏆', rightFlag = '⚽'): string {
  return `
    <div class="wc-stat-compare__head">
      <span class="wc-stat-compare__team">
        <span class="wc-flag" aria-hidden="true">${leftFlag}</span>
        <span class="wc-stat-compare__team-name">${esc(left)}</span>
      </span>
      <span class="wc-stat-compare__team wc-stat-compare__team--right">
        <span class="wc-stat-compare__team-name">${esc(right)}</span>
        <span class="wc-flag" aria-hidden="true">${rightFlag}</span>
      </span>
    </div>`;
}

function cmpRenderCompare(): void {
  const host = $('#c22-compare-host');
  if (!host || !_comparativo) return;
  const t = _comparativo.tournaments || {};
  const a = t['2022'] || {}, b = t['2026'] || {};
  const bwDiff = (blk: TournBlock) => (blk.biggest_win ? blk.biggest_win.diff : null);
  const idadeRow = _idade?.tournaments
    ? cmpRow('Idade média do elenco', (_idade.tournaments['2022'] || {}).avg_age, (_idade.tournaments['2026'] || {}).avg_age, 1, ' anos')
    : '';
  const rows =
    cmpRow('Média de gols por jogo', a.avg_goals_per_match, b.avg_goals_per_match, 2) +
    cmpRow('Gols no 1º tempo (%)', a.goals_first_half_pct, b.goals_first_half_pct, 1, '%') +
    cmpRow('Gols no 2º tempo (%)', a.goals_second_half_pct, b.goals_second_half_pct, 1, '%') +
    cmpRow('Pênaltis marcados', a.penalties_scored, b.penalties_scored, 0) +
    cmpRow('Gols contra', a.own_goals, b.own_goals, 0) +
    cmpRow('Maior goleada (dif. de gols)', bwDiff(a), bwDiff(b), 0) +
    idadeRow +
    '<div class="wc-stat-subhead mono-label">Formato do torneio</div>' +
    cmpRow('Seleções', a.teams, b.teams, 0) +
    cmpRow('Jogos', a.total_matches, b.total_matches, 0) +
    cmpRow('Total de gols', a.total_goals, b.total_goals, 0);
  host.innerHTML =
    cmpHead('Copa 2022', 'Copa 2026') +
    `<div class="wc-stat-rows">${rows}</div>` +
    `<p class="wc-stat-compare__source mono-label">${esc(_comparativo.source || '')}</p>`;
  fillBars(host);
}

function cmpRenderMinute(): void {
  const box = document.getElementById('c22-minute-chart');
  if (!box || !_comparativo) return;
  const P = pal();
  const t = _comparativo.tournaments || {};
  const a = (t['2022'] || {}).goals_by_minute || [];
  const b = (t['2026'] || {}).goals_by_minute || [];
  if (!a.length && !b.length) { box.innerHTML = '<p class="wc-error mono-label">série indisponível</p>'; return; }
  const byRange: Record<string, number> = {};
  b.forEach((x) => { byRange[x.range] = x.pct; });
  const data: BarDatum[] = a.map((x) => ({ label: x.range, values: [x.pct, byRange[x.range] ?? 0] }));
  barChart(box, {
    orientation: 'v',
    ariaLabel: ariaOf(box, 'Distribuição percentual dos gols por faixa de minuto — 2022 vs 2026.'),
    axisTitle: '% dos gols do torneio',
    valueFmt: (v) => fmtNum(v, 1) + '%',
    series: [
      { label: 'Copa 2022', color: P.field },
      { label: 'Copa 2026', color: P.gold },
    ],
    data,
  });
}

function cmpRenderVolume(): void {
  const host = $('#c22-volume-host');
  if (!host || !_comparativo) return;
  const vol = _comparativo.volume;
  if (!vol || !Array.isArray(vol.metrics) || !vol.metrics.length) { (host as HTMLElement).hidden = true; return; }
  (host as HTMLElement).hidden = false;
  const rows = vol.metrics.map((m) => {
    const label = m.only_2022 ? `${m.label} · só 2022` : m.label;
    return cmpRow(label, m.v2022, m.v2026, m.dec, m.unit || '');
  }).join('');
  host.innerHTML =
    cmpHead('Copa 2022 · StatsBomb', 'Copa 2026 · ESPN') +
    `<div class="wc-stat-rows">${rows}</div>` +
    `<p class="wc-stat-compare__source mono-label">${esc(vol.note || '')}</p>`;
  fillBars(host);
}

function cmpRenderDeltas(): void {
  const host = $('#c22-deltas');
  if (!host || !_comparativo) return;
  const d = _comparativo.deltas || {};
  const idadeDelta = _idade?.deltas ? _idade.deltas.avg_age : null;
  const cards = [
    { cat: 'field', title: 'Gols por jogo', key: signed(d.avg_goals_per_match, 2), body: '2026 vs 2022 — média de gols por partida' },
    { cat: 'gold', title: 'Peso do 2º tempo', key: signed(d.goals_second_half_pct, 1) + ' pp', body: 'variação na fatia de gols do segundo tempo' },
    { cat: 'ink', title: 'Gols contra', key: signed(d.own_goals, 0), body: 'diferença no total de gols contra' },
    { cat: 'live', title: 'Pênaltis', key: signed(d.penalties_scored, 0), body: 'diferença em pênaltis convertidos' },
  ];
  if (idadeDelta != null) {
    cards.push({ cat: 'gold', title: 'Idade do elenco', key: signed(idadeDelta, 1) + ' anos', body: 'variação na idade média das seleções' });
  }
  const layout = ['hero', 'md', 'md', 'md', 'md'];
  host.innerHTML = cards.map((c, i) => `
    <article class="wc-insight-card wc-insight-card--${c.cat} wc-insight-card--${layout[i] || 'md'}" data-reveal>
      <header class="wc-insight-card__head"><h3 class="mono-label wc-insight-card__cat">${esc(c.title)}</h3></header>
      <p class="wc-insight-card__title" aria-hidden="true"><span class="wc-insight-card__key">${esc(c.key)}</span></p>
      <p class="wc-insight-card__body">${esc(c.body)}</p>
    </article>`).join('');
  observeReveals(host);
}

export function renderComparativo(cmp: ComparativoData | null, idade: IdadeData | null): void {
  const host = document.getElementById('comparativo-copas');
  if (!host) return;
  const err = $('#c22-cmp-error');
  if (!cmp || !cmp.tournaments) { if (err) (err as HTMLElement).hidden = false; return; }
  if (err) (err as HTMLElement).hidden = true;
  _comparativo = cmp;
  _idade = idade;
  cmpRenderCompare();
  cmpRenderMinute();
  cmpRenderVolume();
  cmpRenderDeltas();
}

/* ══════════════════════════════════════════════════════════════════════════ */
/* [10] COPAS NA HISTÓRIA                                                       */
/* ══════════════════════════════════════════════════════════════════════════ */

interface BigNumber { label?: string; value?: string | number; detail?: string; country?: string; flag?: string; sub?: string }
interface Champion { country: string; flag?: string; titles?: number; years?: number[] }
interface HistScorer { name: string; country?: string; flag?: string; goals?: number; editions?: number; years?: string }
interface Participation { country: string; flag?: string; participations?: number; note?: string }
interface Appearance { name: string; country?: string; flag?: string; matches?: number }
interface HistoriaData {
  big_numbers?: BigNumber[];
  top_scorers_alltime?: HistScorer[];
  most_appearances_players?: Appearance[];
  champions?: Champion[];
  most_participations?: Participation[];
}
interface ContextCard { tag?: string; title?: string; body?: string; source_url?: string }
interface ContextoData { cards_2022?: ContextCard[]; cards_2026?: ContextCard[] }

let _historia: HistoriaData | null = null;

function histBigNumbers(): void {
  const host = $('#c22-hist-bignumbers');
  if (!host || !_historia) return;
  const nums = (_historia.big_numbers || []).slice(0, 10);
  if (!nums.length) { host.innerHTML = ''; return; }
  host.innerHTML = nums.map((b, i) => {
    const wide = i === 0 ? ' wc-stat-card--wide' : '';
    const detail = [b.flag, b.detail].filter(Boolean).join(' ');
    const country = b.country ? ` · ${esc(b.country)}` : '';
    return `
      <div class="wc-stat-card${wide} crop" role="listitem" data-reveal>
        <span class="crop-mark-bl" aria-hidden="true"></span>
        <span class="crop-mark-br" aria-hidden="true"></span>
        <span class="mono-label">${esc(b.label || '')}</span>
        <span class="wc-stat-card__value">${esc(String(b.value))}</span>
        <span class="wc-stat-card__sub">${detail}${country}</span>
        ${b.sub ? `<span class="wc-stat-card__sub" style="color:var(--ink-faint)">${esc(b.sub)}</span>` : ''}
      </div>`;
  }).join('');
  observeReveals(host);
}

function histChampions(): void {
  const box = document.getElementById('c22-hist-champions');
  if (!box || !_historia) return;
  const P = pal();
  const champs = (_historia.champions || []).slice().sort((a, b) => (b.titles || 0) - (a.titles || 0)).slice(0, 10);
  if (!champs.length) { box.innerHTML = '<p class="wc-error mono-label">indisponível</p>'; return; }
  const data: BarDatum[] = champs.map((c, i) => ({
    label: `${c.flag || ''} ${c.country}`.trim(),
    value: c.titles || 0,
    color: P.gold,
    highlight: i === 0,
    meta: c,
  }));
  barChart(box, {
    orientation: 'h',
    ariaLabel: ariaOf(box, 'Ranking das seleções campeãs do mundo por número de títulos.'),
    axisTitle: 'títulos mundiais',
    valueFmt: (v) => fmtNum(v, 0),
    data,
    tooltip: (d) => {
      const c = d.meta as Champion;
      const yrs = Array.isArray(c.years) ? c.years.join(', ') : '';
      return { title: c.country, rows: [{ name: 'títulos', value: String(c.titles), leader: true }, ...(yrs ? [{ name: 'anos', value: yrs }] : [])] };
    },
  });
}

function histParticipations(): void {
  const box = document.getElementById('c22-hist-participations');
  if (!box || !_historia) return;
  const rows = (_historia.most_participations || []).slice().sort((a, b) => (b.participations || 0) - (a.participations || 0)).slice(0, 10);
  if (!rows.length) { box.innerHTML = '<p class="wc-error mono-label">indisponível</p>'; return; }
  const data: BarDatum[] = rows.map((r) => ({ label: `${r.flag || ''} ${r.country}`.trim(), value: r.participations || 0, meta: r }));
  barChart(box, {
    orientation: 'h',
    ariaLabel: ariaOf(box, 'Seleções com mais participações em Copas do Mundo.'),
    axisTitle: 'Copas disputadas',
    valueFmt: (v) => fmtNum(v, 0),
    data,
    tooltip: (d) => {
      const r = d.meta as Participation;
      return { title: r.country, rows: [{ name: 'Copas', value: String(r.participations) }, ...(r.note ? [{ name: '', value: r.note }] : [])] };
    },
  });
}

function histScorers(): void {
  const body = $('#c22-hist-scorers');
  if (!body || !_historia) return;
  const top = (_historia.top_scorers_alltime || []).slice().sort((a, b) => (b.goals || 0) - (a.goals || 0)).slice(0, 10);
  if (!top.length) { body.innerHTML = '<tr><td colspan="4" class="wc-error mono-label">indisponível</td></tr>'; return; }
  body.innerHTML = top.map((s, i) => {
    const rank = i + 1;
    const isGold = rank === 1;
    const badge = isGold ? ' <span class="wc-scorers-table__gold-badge" aria-label="Maior artilheiro">🏆</span>' : '';
    return `
      <tr class="${isGold ? 'wc-scorers-table__row--gold' : ''}">
        <td class="wc-scorers-table__rank-cell">${rank}${badge}</td>
        <td>
          <div class="wc-scorers-table__player-cell">
            <span class="wc-flag" aria-hidden="true">${s.flag ? esc(s.flag) : '—'}</span>
            <span class="wc-scorers-table__name-block">
              <span class="wc-scorers-table__name">${esc(s.name)}</span>
              <span class="wc-scorers-table__sub">${esc(s.country || '')}${s.years ? ' · ' + esc(s.years) : ''}</span>
            </span>
          </div>
        </td>
        <td class="wc-scorers-table__goals-cell">${s.goals}</td>
        <td class="wc-scorers-table__pen-cell">${s.editions != null ? s.editions : '—'}</td>
      </tr>`;
  }).join('');
}

function histAppearances(): void {
  const body = $('#c22-hist-appearances');
  if (!body || !_historia) return;
  const top = (_historia.most_appearances_players || []).slice().sort((a, b) => (b.matches || 0) - (a.matches || 0)).slice(0, 10);
  if (!top.length) { body.innerHTML = '<tr><td colspan="3" class="wc-error mono-label">indisponível</td></tr>'; return; }
  body.innerHTML = top.map((s, i) => {
    const rank = i + 1;
    return `
      <tr class="${rank === 1 ? 'wc-scorers-table__row--gold' : ''}">
        <td class="wc-scorers-table__rank-cell">${rank}</td>
        <td>
          <div class="wc-scorers-table__player-cell">
            <span class="wc-flag" aria-hidden="true">${s.flag ? esc(s.flag) : '—'}</span>
            <span class="wc-scorers-table__name-block">
              <span class="wc-scorers-table__name">${esc(s.name)}</span>
              <span class="wc-scorers-table__sub">${esc(s.country || '')}</span>
            </span>
          </div>
        </td>
        <td class="wc-scorers-table__goals-cell">${s.matches}</td>
      </tr>`;
  }).join('');
}

function histContextCards(hostId: string, cards: ContextCard[] | undefined, heading: string): void {
  const host = document.getElementById(hostId);
  if (!host) return;
  if (!Array.isArray(cards) || !cards.length) { host.hidden = true; return; }
  host.hidden = false;
  const head = heading ? `<h3 class="wc-c22-context__head mono-label">${esc(heading)}</h3>` : '';
  host.innerHTML = head + '<div class="wc-c22-context__grid">' + cards.map((c) => `
    <article class="wc-c22-context-card" data-reveal>
      <span class="tag tag--wc">${esc(c.tag || '')}</span>
      <h4 class="wc-c22-context-card__title">${esc(c.title || '')}</h4>
      <p class="wc-c22-context-card__body">${esc(c.body || '')}</p>
      ${c.source_url ? `<a class="wc-c22-context-card__src mono-label" href="${esc(c.source_url)}" target="_blank" rel="noopener noreferrer" aria-label="Fonte: ${esc(c.title || '')}">fonte ↗</a>` : ''}
    </article>`).join('') + '</div>';
  observeReveals(host);
}

export function renderHistoria(historia: HistoriaData | null, contexto: ContextoData | null): void {
  const host = document.getElementById('historia-copas');
  if (!host) return;
  // Contexto editorial (marcos 2022/2026) — degrada sozinho se faltar.
  if (contexto) {
    histContextCards('c22-context-2022', contexto.cards_2022, 'Marcos da Copa 2022');
    histContextCards('c22-context-2026', contexto.cards_2026, 'A nova Copa — 2026');
  }
  const err = $('#c22-hist-error');
  if (!historia) { if (err) (err as HTMLElement).hidden = false; return; }
  if (err) (err as HTMLElement).hidden = true;
  _historia = historia;
  histBigNumbers();
  histChampions();
  histScorers();
  histParticipations();
  histAppearances();
}
