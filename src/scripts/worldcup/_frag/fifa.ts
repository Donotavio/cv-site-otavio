/**
 * fifa.ts — Três seções de dados FIFA do World Cup Dashboard (Astro).
 * ============================================================================
 * Consome os JSONs oficiais gerados em `assets/data/worldcup/`:
 *   fifa_team_stats.json   → renderFifaTeamStats(data)   → #fifa-team-stats
 *   fifa_power_ranking.json→ renderFifaPowerRanking(data)→ #fifa-power-ranking
 *   fifa_team_stats.json   → renderFifaCompare(data)     → #fifa-compare (radar)
 *
 * Zero dependência externa: usa as primitivas SVG hand-rolled de `../charts`
 * (barChart + o novo radarChart) e o `readToken` para toda cor (paleta WC only,
 * nunca hex fixo). Runtime só faz fetch dos JSONs prontos (zero LLM).
 *
 * Convenções herdadas de cap23.ts:
 *   · Cada render fn é IDEMPOTENTE (limpa/regrava o host) e no-op se a seção não
 *     está no DOM (guard getElementById) → segura em navegação SPA (astro:page-load).
 *   · FAIL-SOFT: dado nulo/ inválido → mostra o `.wc-error` da seção e retorna;
 *     um erro numa seção não derruba as outras (o orquestrador chama via safe()).
 *   · `<select>` SPA-safe: handler guardado em `sel._wcHandler`, removeEventListener
 *     antes de re-adicionar → nunca duplica listener após navegação.
 *   · Cor via readToken (WC family) + esc() local para todo texto injetado.
 *   · Reuso dos padrões de markup de cap23: `.wc-insight-card` (bento),
 *     `.wc-c22-block` (chart card), `.wc-stat-compare`/`.wc-stat-row` (delta list).
 *
 * @module worldcup/_frag/fifa
 */

import { barChart, radarChart, readToken } from '../charts';
import type { BarDatum, RadarSeries } from '../charts';

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
/** Número + unidade opcional. */
function fmtUnit(v: unknown, dec: number, unit?: string): string {
  const s = fmtNum(v, dec);
  return s === '—' ? s : (unit ? s + unit : s);
}

/** Paleta WC resolvida dos tokens (nunca hex fixo). */
function pal() {
  return {
    field: readToken('--wc-field-ink', '#0B6B2E'),
    gold: readToken('--wc-gold-ink', '#8A5A06'),
    live: readToken('--wc-live-ink', '#A82A26'),
    ink: readToken('--ink', '#0A0A0A'),
  };
}

/** Rótulo acessível do container (já traduzido em runtime via data-i18n-aria). */
function ariaOf(el: HTMLElement, fallback: string): string {
  return el.getAttribute('aria-label') || fallback;
}

/**
 * Reveal local para conteúdo injetado ([data-reveal]) — espelha o padrão de
 * cap23. Se não houver IO ou motion reduzida, mostra na hora.
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

/* ════════════════════════════════════════════════════════════════════════ */
/* Tipos dos JSONs FIFA                                                        */
/* ════════════════════════════════════════════════════════════════════════ */

interface MetricMeta {
  key: string;
  label_pt: string;
  unit: string;
  higher_is_better: boolean;
  per_match: boolean;
}
interface TeamInsights {
  xg_diff?: number;
  shot_conversion?: number;
  pressure_per_match?: number;
  distance_km_per_match?: number;
}
interface FifaTeam {
  id: string;
  name: string;
  code?: string;
  flag?: string;
  matches?: number;
  stats?: Record<string, number>;
  per_match?: Record<string, number>;
  insights?: TeamInsights;
}
export interface FifaTeamStats {
  updated_at?: string;
  source?: string;
  metrics_catalog?: MetricMeta[];
  teams?: FifaTeam[];
}

interface OutfieldRow {
  player: string; team?: string; code?: string; flag?: string; picture?: string;
  attacking_rank?: number; attacking_score?: number; attacking_change?: number;
  defensive_rank?: number; defensive_score?: number; defensive_change?: number;
  creativity_rank?: number; creativity_score?: number; creativity_change?: number;
}
interface GoalkeeperRow {
  player: string; team?: string; code?: string; flag?: string; picture?: string;
  in_possession_rank?: number; in_possession_score?: number; in_possession_change?: number;
  defending_rank?: number; defending_score?: number; defending_change?: number;
}
export interface FifaPowerRanking {
  updated_at?: string;
  source?: string;
  n_matches?: number;
  outfield?: OutfieldRow[];
  goalkeepers?: GoalkeeperRow[];
}

/* ════════════════════════════════════════════════════════════════════════ */
/* [FIFA-01] ESTATÍSTICAS DE SELEÇÃO — ranking por métrica + bento             */
/* ════════════════════════════════════════════════════════════════════════ */

let _teamData: FifaTeamStats | null = null;
let _teamMetric: MetricMeta | null = null;

/** Valor de ranking de um time p/ uma métrica: usa per_match quando disponível. */
function metricVal(t: FifaTeam, m: MetricMeta): number | null {
  const pm = m.per_match ? t.per_match?.[m.key] : undefined;
  const raw = pm != null ? pm : t.stats?.[m.key];
  return raw == null ? null : Number(raw);
}

function teamRenderChart(): void {
  const box = document.getElementById('fifa-team-chart');
  if (!box || !_teamData || !_teamMetric) return;
  const m = _teamMetric;
  const teams = (_teamData.teams || []).filter((t) => metricVal(t, m) != null);
  teams.sort((a, b) => {
    const va = metricVal(a, m) as number, vb = metricVal(b, m) as number;
    return m.higher_is_better ? vb - va : va - vb; // "menor é melhor" ordena asc
  });
  const top = teams.slice(0, 16);
  const suffix = (m.per_match ? '/jogo' : '') + (m.unit ? ` ${m.unit}` : '');
  const data: BarDatum[] = top.map((t, i) => ({
    label: `${t.flag || ''} ${t.code || t.name}`.trim(),
    value: metricVal(t, m) as number,
    highlight: i === 0,
    meta: t,
  }));
  barChart(box, {
    orientation: 'h',
    ariaLabel: ariaOf(box, 'Ranking das 48 seleções da Copa 2026 pela métrica FIFA selecionada.'),
    axisTitle: m.label_pt + (suffix ? ` (${suffix.trim()})` : ''),
    valueFmt: (v) => fmtNum(v, m.per_match || m.unit === '%' || m.unit === 'xG' ? 1 : 0) + (m.unit ? ` ${m.unit}` : ''),
    data,
    tooltip: (d) => {
      const t = d.meta as FifaTeam;
      const dec = m.per_match || m.unit === '%' || m.unit === 'xG' ? 1 : 0;
      return {
        title: `${t.flag || ''} ${t.name}`.trim(),
        rows: [
          { name: m.label_pt + (m.per_match ? '/jogo' : ''), value: fmtNum(d.value, dec) + (m.unit ? ` ${m.unit}` : '') },
          { name: 'jogos', value: String(t.matches ?? '—') },
        ],
      };
    },
  });
  const note = $('#fifa-team-note');
  if (note) {
    note.textContent = m.higher_is_better
      ? `Top 16 seleções por ${m.label_pt.toLowerCase()}${m.per_match ? ' por jogo' : ''} — Copa 2026 (dado oficial FIFA).`
      : `Top 16 seleções por ${m.label_pt.toLowerCase()} — menor é melhor (dado oficial FIFA).`;
  }
}

function teamPopulateSelect(): void {
  const sel = document.getElementById('fifa-metric-select') as (HTMLSelectElement & { _wcHandler?: () => void }) | null;
  if (!sel || !_teamData) return;
  const cat = _teamData.metrics_catalog || [];
  sel.innerHTML = cat.map((m) =>
    `<option value="${esc(m.key)}">${esc(m.label_pt)}${m.per_match ? ' · por jogo' : ''}${m.unit ? ' (' + esc(m.unit) + ')' : ''}</option>`).join('');
  if (_teamMetric) sel.value = _teamMetric.key;
  if (sel._wcHandler) sel.removeEventListener('change', sel._wcHandler);
  const handler = () => {
    _teamMetric = (_teamData!.metrics_catalog || []).find((m) => m.key === sel.value) || _teamMetric;
    try { teamRenderChart(); } catch (e) { console.error('[wc-fifa] team chart:', e); }
  };
  sel._wcHandler = handler;
  sel.addEventListener('change', handler);
}

function teamRenderBento(): void {
  const host = $('#fifa-team-bento');
  if (!host || !_teamData) return;
  const teams = _teamData.teams || [];
  const tag = (t: FifaTeam) => `${t.flag || ''} ${t.name}`.trim();

  // Melhor de cada dimensão cruzada (respeita "maior é melhor" por métrica).
  const bestBy = (get: (t: FifaTeam) => number | null | undefined, high = true): FifaTeam | null => {
    let best: FifaTeam | null = null, bv = high ? -Infinity : Infinity;
    teams.forEach((t) => {
      const v = get(t);
      if (v == null || Number.isNaN(Number(v))) return;
      const n = Number(v);
      if (high ? n > bv : n < bv) { bv = n; best = t; }
    });
    return best;
  };

  const xgTeam = bestBy((t) => t.stats?.XG);
  const effTeam = bestBy((t) => t.insights?.xg_diff);            // gols − xG (eficiência)
  const pressTeam = bestBy((t) => t.insights?.pressure_per_match);
  const runTeam = bestBy((t) => t.insights?.distance_km_per_match);
  const possTeam = bestBy((t) => t.stats?.Possession);

  interface Card { cat: string; title: string; key: string; team: FifaTeam | null; sub: string }
  const cards: Card[] = [
    { cat: 'gold',  title: 'Maior xG',          key: fmtNum(xgTeam?.stats?.XG, 1) + ' xG',        team: xgTeam,   sub: 'gols esperados no torneio' },
    { cat: 'field', title: 'Mais eficiente',    key: signed(effTeam?.insights?.xg_diff, 1),       team: effTeam,  sub: 'gols acima do xG (finalização)' },
    { cat: 'field', title: 'Mais pressão',      key: fmtNum(pressTeam?.insights?.pressure_per_match, 0), team: pressTeam, sub: 'pressões defensivas por jogo' },
    { cat: 'ink',   title: 'Quem mais correu',  key: fmtNum(runTeam?.insights?.distance_km_per_match, 1) + ' km', team: runTeam, sub: 'distância percorrida por jogo' },
    { cat: 'gold',  title: 'Mais posse',        key: fmtNum(possTeam?.stats?.Possession, 1) + '%', team: possTeam, sub: 'posse de bola média' },
  ];
  const layout = ['hero', 'hero', 'md', 'md', 'md'];
  host.innerHTML = cards.map((c, i) => `
    <article class="wc-insight-card wc-insight-card--${c.cat} wc-insight-card--${layout[i] || 'md'}" data-reveal>
      <header class="wc-insight-card__head"><h3 class="mono-label wc-insight-card__cat">${esc(c.title)}</h3></header>
      <p class="wc-insight-card__title" aria-hidden="true"><span class="wc-insight-card__key">${esc(c.key)}</span></p>
      <p class="wc-insight-card__body">${c.team ? esc(tag(c.team)) : '—'}<br><span class="mono-label" style="color:var(--ink-faint)">${esc(c.sub)}</span></p>
    </article>`).join('');
  observeReveals(host);
}

export function renderFifaTeamStats(data: FifaTeamStats | null): void {
  const host = document.getElementById('fifa-team-stats');
  if (!host) return;
  const err = $('#fifa-team-error');
  if (!data || !Array.isArray(data.teams) || !data.teams.length || !Array.isArray(data.metrics_catalog)) {
    if (err) (err as HTMLElement).hidden = false; return;
  }
  if (err) (err as HTMLElement).hidden = true;
  _teamData = data;
  // Default: xG a favor (2ª métrica do catálogo), caindo p/ a 1ª se faltar.
  _teamMetric = (data.metrics_catalog!.find((m) => m.key === 'XG') || data.metrics_catalog![0]) || null;
  const meta = $('#fifa-team-meta');
  if (meta) meta.textContent = `${data.teams.length} seleções · dado oficial FIFA · ${data.metrics_catalog!.length} métricas`;
  teamPopulateSelect();
  teamRenderBento();
  teamRenderChart();
}

/* ════════════════════════════════════════════════════════════════════════ */
/* [FIFA-02] POWER RANKING — jogadores por eixo + goleiros                     */
/* ════════════════════════════════════════════════════════════════════════ */

let _powerData: FifaPowerRanking | null = null;

interface PowerAxis {
  key: 'attacking' | 'defensive' | 'creativity';
  label: string;
}
const POWER_AXES: PowerAxis[] = [
  { key: 'attacking',  label: 'Ataque' },
  { key: 'defensive',  label: 'Defesa' },
  { key: 'creativity', label: 'Criatividade' },
];
let _powerAxis: PowerAxis = POWER_AXES[0];

/** Seta de variação de ranking (+ sobe = verde/field, − cai = live/vermelho). */
function changeBadge(change: number | undefined): string {
  if (change == null || change === 0) return '<span class="fifa-change fifa-change--flat" aria-label="estável">—</span>';
  // rank melhora quando o NÚMERO cai; a API já entrega o delta de posição (positivo = subiu).
  const up = change > 0;
  const arrow = up ? '▲' : '▼';
  const cls = up ? 'fifa-change--up' : 'fifa-change--down';
  return `<span class="fifa-change ${cls}" aria-label="${up ? 'subiu' : 'caiu'} ${Math.abs(change)}">${arrow} ${Math.abs(change)}</span>`;
}

function powerRenderTable(): void {
  const body = $('#fifa-power-body');
  if (!body || !_powerData) return;
  const ax = _powerAxis;
  const rows = (_powerData.outfield || [])
    .filter((p) => (p as any)[`${ax.key}_rank`] != null)
    .slice()
    .sort((a, b) => (Number((a as any)[`${ax.key}_rank`]) || 1e9) - (Number((b as any)[`${ax.key}_rank`]) || 1e9))
    .slice(0, 15);
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="4" class="wc-error mono-label">power ranking indisponível</td></tr>';
    return;
  }
  body.innerHTML = rows.map((p, i) => {
    const rank = Number((p as any)[`${ax.key}_rank`]);
    const score = Number((p as any)[`${ax.key}_score`]);
    const change = (p as any)[`${ax.key}_change`] as number | undefined;
    const isGold = i === 0;
    const badge = isGold ? ' <span class="wc-scorers-table__gold-badge" aria-label="Líder">🏆</span>' : '';
    return `
      <tr class="${isGold ? 'wc-scorers-table__row--gold' : ''}">
        <td class="wc-scorers-table__rank-cell">${rank}${badge}</td>
        <td>
          <div class="wc-scorers-table__player-cell">
            <span class="wc-flag" aria-hidden="true">${p.flag ? esc(p.flag) : '—'}</span>
            <span class="wc-scorers-table__name-block">
              <span class="wc-scorers-table__name">${esc(p.player)}</span>
              <span class="wc-scorers-table__sub">${esc(p.team || '')}</span>
            </span>
          </div>
        </td>
        <td class="wc-scorers-table__goals-cell">${fmtNum(score, 2)}</td>
        <td class="wc-scorers-table__pen-cell">${changeBadge(change)}</td>
      </tr>`;
  }).join('');
}

function powerPopulateSelect(): void {
  const sel = document.getElementById('fifa-power-select') as (HTMLSelectElement & { _wcHandler?: () => void }) | null;
  if (!sel) return;
  sel.innerHTML = POWER_AXES.map((a) => `<option value="${esc(a.key)}">${esc(a.label)}</option>`).join('');
  sel.value = _powerAxis.key;
  if (sel._wcHandler) sel.removeEventListener('change', sel._wcHandler);
  const handler = () => {
    _powerAxis = POWER_AXES.find((a) => a.key === sel.value) || POWER_AXES[0];
    try { powerRenderTable(); } catch (e) { console.error('[wc-fifa] power table:', e); }
  };
  sel._wcHandler = handler;
  sel.addEventListener('change', handler);
}

function powerRenderGK(): void {
  const body = $('#fifa-gk-body');
  if (!body || !_powerData) return;
  const rows = (_powerData.goalkeepers || [])
    .filter((g) => g.defending_rank != null)
    .slice()
    .sort((a, b) => (a.defending_rank || 1e9) - (b.defending_rank || 1e9))
    .slice(0, 5);
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="3" class="wc-error mono-label">goleiros indisponíveis</td></tr>';
    return;
  }
  body.innerHTML = rows.map((g, i) => `
    <tr class="${i === 0 ? 'wc-scorers-table__row--gold' : ''}">
      <td class="wc-scorers-table__rank-cell">${g.defending_rank}</td>
      <td>
        <div class="wc-scorers-table__player-cell">
          <span class="wc-flag" aria-hidden="true">${g.flag ? esc(g.flag) : '—'}</span>
          <span class="wc-scorers-table__name-block">
            <span class="wc-scorers-table__name">${esc(g.player)}</span>
            <span class="wc-scorers-table__sub">${esc(g.team || '')}</span>
          </span>
        </div>
      </td>
      <td class="wc-scorers-table__goals-cell">${fmtNum(g.defending_score, 2)}</td>
    </tr>`).join('');
}

export function renderFifaPowerRanking(data: FifaPowerRanking | null): void {
  const host = document.getElementById('fifa-power-ranking');
  if (!host) return;
  const err = $('#fifa-power-error');
  if (!data || !Array.isArray(data.outfield) || !data.outfield.length) {
    if (err) (err as HTMLElement).hidden = false; return;
  }
  if (err) (err as HTMLElement).hidden = true;
  _powerData = data;
  const meta = $('#fifa-power-meta');
  if (meta) {
    const nOut = data.outfield.length, nGk = (data.goalkeepers || []).length;
    meta.textContent = `${nOut} jogadores de linha · ${nGk} goleiros · ${data.n_matches ?? '—'} jogos · dado oficial FIFA`;
  }
  powerPopulateSelect();
  powerRenderTable();
  powerRenderGK();
}

/* ════════════════════════════════════════════════════════════════════════ */
/* [FIFA-03] COMPARADOR — radar head-to-head + lista de deltas                 */
/* ════════════════════════════════════════════════════════════════════════ */

let _cmpData: FifaTeamStats | null = null;

/** Métricas do radar (6 eixos), com o extrator de valor por time. */
interface RadarAxisDef { label: string; unit: string; dec: number; get: (t: FifaTeam) => number | null }
const RADAR_AXES: RadarAxisDef[] = [
  { label: 'xG/jogo',    unit: 'xG',  dec: 1, get: (t) => t.per_match?.XG ?? null },
  { label: 'Posse',      unit: '%',   dec: 1, get: (t) => t.stats?.Possession ?? null },
  { label: 'Finaliz./jogo', unit: '', dec: 1, get: (t) => t.per_match?.AttemptAtGoal ?? null },
  { label: 'Pressões/jogo', unit: '', dec: 0, get: (t) => t.per_match?.DefensivePressuresApplied ?? null },
  { label: 'Distância/jogo', unit: 'km', dec: 1, get: (t) => t.per_match?.TotalDistance ?? null },
  { label: 'Precisão passe', unit: '%', dec: 1, get: (t) => t.stats?.pass_pct ?? null },
];

function teamById(id: string): FifaTeam | null {
  return (_cmpData?.teams || []).find((t) => t.id === id) || null;
}

function cmpValues(t: FifaTeam): number[] {
  return RADAR_AXES.map((a) => Number(a.get(t)) || 0);
}

function cmpRenderRadar(): void {
  const box = document.getElementById('fifa-compare-radar');
  const selA = document.getElementById('fifa-compare-a') as HTMLSelectElement | null;
  const selB = document.getElementById('fifa-compare-b') as HTMLSelectElement | null;
  if (!box || !selA || !selB || !_cmpData) return;
  const a = teamById(selA.value), b = teamById(selB.value);
  if (!a || !b) { box.innerHTML = '<p class="wc-error mono-label">selecione duas seleções</p>'; return; }
  const P = pal();
  const series: RadarSeries[] = [
    { label: `${a.flag || ''} ${a.code || a.name}`.trim(), values: cmpValues(a), color: P.field },
    { label: `${b.flag || ''} ${b.code || b.name}`.trim(), values: cmpValues(b), color: P.gold },
  ];
  radarChart(box, {
    axes: RADAR_AXES.map((x) => x.label),
    ariaLabel: ariaOf(box, `Comparação de ${a.name} contra ${b.name} em seis métricas FIFA.`),
    series,
    // max omitido → normalização por-eixo (cada métrica na própria escala, líder toca a borda).
    valueFmt: (v, i) => fmtUnit(v, RADAR_AXES[i].dec, RADAR_AXES[i].unit ? ` ${RADAR_AXES[i].unit}` : ''),
  });
  cmpRenderDeltas(a, b);
}

function cmpRenderDeltas(a: FifaTeam, b: FifaTeam): void {
  const host = $('#fifa-compare-deltas');
  if (!host) return;
  const rows = RADAR_AXES.map((ax) => {
    const va = Number(ax.get(a)), vb = Number(ax.get(b));
    const okA = ax.get(a) != null, okB = ax.get(b) != null;
    const d = okA && okB ? va - vb : null;
    const leadA = d != null && d > 0, leadB = d != null && d < 0;
    const u = ax.unit ? ` ${ax.unit}` : '';
    return `
      <div class="wc-stat-row">
        <span class="wc-stat-row__home${leadA ? ' is-lead' : ''}">${esc(fmtUnit(okA ? va : null, ax.dec, u))}</span>
        <div class="fifa-delta-bar" aria-hidden="true">
          <span class="fifa-delta-bar__val">${d == null ? '—' : signed(d, ax.dec) + u}</span>
        </div>
        <span class="wc-stat-row__away${leadB ? ' is-lead' : ''}">${esc(fmtUnit(okB ? vb : null, ax.dec, u))}</span>
        <span class="wc-stat-row__label">${esc(ax.label)}</span>
      </div>`;
  }).join('');
  host.innerHTML =
    `<div class="wc-stat-compare__head">
      <span class="wc-stat-compare__team"><span class="wc-flag" aria-hidden="true">${esc(a.flag || '⚽')}</span><span class="wc-stat-compare__team-name">${esc(a.name)}</span></span>
      <span class="wc-stat-compare__team wc-stat-compare__team--right"><span class="wc-stat-compare__team-name">${esc(b.name)}</span><span class="wc-flag" aria-hidden="true">${esc(b.flag || '⚽')}</span></span>
    </div>
    <div class="wc-stat-rows">${rows}</div>
    <p class="wc-stat-compare__source mono-label">${esc(_cmpData?.source || 'dado oficial FIFA · por jogo')}</p>`;
}

function cmpPopulateSelect(sel: HTMLSelectElement & { _wcHandler?: () => void }, teams: FifaTeam[], selectedId: string): void {
  sel.innerHTML = teams.map((t) =>
    `<option value="${esc(t.id)}"${t.id === selectedId ? ' selected' : ''}>${esc(`${t.flag || ''} ${t.name}`.trim())}</option>`).join('');
  sel.value = selectedId;
  if (sel._wcHandler) sel.removeEventListener('change', sel._wcHandler);
  const handler = () => { try { cmpRenderRadar(); } catch (e) { console.error('[wc-fifa] compare:', e); } };
  sel._wcHandler = handler;
  sel.addEventListener('change', handler);
}

export function renderFifaCompare(data: FifaTeamStats | null): void {
  const host = document.getElementById('fifa-compare');
  if (!host) return;
  const err = $('#fifa-compare-error');
  if (!data || !Array.isArray(data.teams) || data.teams.length < 2) {
    if (err) (err as HTMLElement).hidden = false; return;
  }
  if (err) (err as HTMLElement).hidden = true;
  _cmpData = data;
  const selA = document.getElementById('fifa-compare-a') as (HTMLSelectElement & { _wcHandler?: () => void }) | null;
  const selB = document.getElementById('fifa-compare-b') as (HTMLSelectElement & { _wcHandler?: () => void }) | null;
  if (!selA || !selB) return;
  // Opções ordenadas por nome; default = as duas seleções com maior XG.
  const teams = (data.teams || []).slice().sort((a, b) => a.name.localeCompare(b.name));
  const byXg = (data.teams || []).slice().sort((a, b) => (Number(b.stats?.XG) || 0) - (Number(a.stats?.XG) || 0));
  const defA = byXg[0]?.id || teams[0].id;
  const defB = byXg[1]?.id || teams[1].id;
  cmpPopulateSelect(selA, teams, defA);
  cmpPopulateSelect(selB, teams, defB);
  cmpRenderRadar();
}

/* ════════════════════════════════════════════════════════════════════════ */
/* MARKUP das 3 seções (string p/ colar no monólito .astro)                    */
/* ════════════════════════════════════════════════════════════════════════ */

/**
 * Markup das três `<section>`s FIFA, no MESMO padrão do esqueleto/cap23:
 *   .section > .container > .section-head (mono-label + .wc-display + .wc-lead)
 *   + <hr class="section-line"> + hosts com os ids que as render fns miram +
 *   <select>s + bento host + `.wc-error` placeholders + data-i18n-key.
 *
 * Os mono-labels [ 11 12 13 ] assumem inserção DEPOIS de historia-copas ([10]).
 * Renumere se a posição de stitch mudar. Chaves i18n sob
 * `portfolio.world_cup.fifa_*` (autoradas à parte; o texto embutido é o fallback).
 */
export const FIFA_SECTIONS_HTML = `
<!-- ═══════════════════ [11] FIFA · ESTATÍSTICAS DE SELEÇÃO ═══════════════════ -->
<section id="fifa-team-stats" class="section wc-fifa-section" aria-labelledby="fifa-team-title">
  <div class="container">
    <div class="section-head" data-reveal>
      <span class="mono-label">11</span>
      <h2 id="fifa-team-title" class="wc-display" data-i18n-key="portfolio.world_cup.fifa_team_title">Estatísticas de seleção · dado FIFA</h2>
      <p class="wc-lead" data-i18n-key="portfolio.world_cup.fifa_team_lead">
        As 48 seleções da Copa 2026 pelo dado oficial da FIFA: xG, posse, pressão, distância percorrida e mais de 20 métricas por jogo. Escolha a métrica e veja o ranking; o bento destaca quem lidera cada dimensão do jogo.
      </p>
    </div>
    <hr class="section-line" aria-hidden="true" data-reveal />

    <span class="mono-label wc-cl-tagline" id="fifa-team-meta" data-i18n-key="portfolio.world_cup.fifa_team_source">dado oficial FIFA</span>

    <p class="wc-error mono-label" id="fifa-team-error" hidden data-i18n-key="portfolio.world_cup.fifa_team_error">Estatísticas FIFA de seleção indisponíveis.</p>

    <!-- Bento de destaques cruzados -->
    <div class="wc-insights-grid" id="fifa-team-bento" aria-label="Destaques FIFA das seleções"
         data-i18n-aria="portfolio.world_cup.fifa_team_bento_aria">
      <div class="wc-skeleton-card"><span class="wc-skeleton" style="height:140px"></span></div>
      <div class="wc-skeleton-card"><span class="wc-skeleton" style="height:140px"></span></div>
      <div class="wc-skeleton-card"><span class="wc-skeleton" style="height:140px"></span></div>
    </div>

    <!-- Ranking por métrica selecionável -->
    <div class="wc-c22-block card crop">
      <span class="crop-mark-bl" aria-hidden="true"></span>
      <span class="crop-mark-br" aria-hidden="true"></span>
      <header class="wc-c22-block__head">
        <h3 class="wc-c22-block__title" data-i18n-key="portfolio.world_cup.fifa_team_ranking_title">Ranking de seleções</h3>
        <div class="wc-match-select-wrap">
          <label for="fifa-metric-select" class="mono-label" data-i18n-key="portfolio.world_cup.select_metric">métrica</label>
          <select id="fifa-metric-select" class="wc-cl-select"></select>
        </div>
      </header>
      <div class="wc-c22-block__chart" id="fifa-team-chart" role="img"
           aria-label="Ranking das 48 seleções da Copa 2026 pela métrica FIFA selecionada."
           data-i18n-aria="portfolio.world_cup.fifa_team_chart_aria">
        <p class="wc-loading mono-label">carregando gráfico…</p>
      </div>
      <p class="wc-cl-note mono-label" id="fifa-team-note" data-i18n-key="portfolio.world_cup.fifa_team_note">Top 16 seleções pela métrica selecionada — Copa 2026 (dado oficial FIFA).</p>
    </div>
  </div>
</section>

<!-- ═══════════════════ [12] FIFA · POWER RANKING DE JOGADORES ═══════════════ -->
<section id="fifa-power-ranking" class="section wc-fifa-section wc-fifa-section--alt" aria-labelledby="fifa-power-title">
  <div class="container">
    <div class="section-head" data-reveal>
      <span class="mono-label">12</span>
      <h2 id="fifa-power-title" class="wc-display" data-i18n-key="portfolio.world_cup.fifa_power_title">Power Ranking de jogadores</h2>
      <p class="wc-lead" data-i18n-key="portfolio.world_cup.fifa_power_lead">
        O ranking oficial da FIFA por jogador, em três eixos — ataque, defesa e criatividade — com a nota e a variação de posição na rodada. Escolha o eixo; ao lado, o top-5 de goleiros por defesa.
      </p>
    </div>
    <hr class="section-line" aria-hidden="true" data-reveal />

    <span class="mono-label wc-cl-tagline" id="fifa-power-meta" data-i18n-key="portfolio.world_cup.fifa_team_source">dado oficial FIFA</span>

    <p class="wc-error mono-label" id="fifa-power-error" hidden data-i18n-key="portfolio.world_cup.fifa_power_error">Power Ranking FIFA indisponível.</p>

    <div class="wc-c22-two-col">
      <!-- Jogadores de linha por eixo -->
      <div class="wc-c22-block card crop">
        <span class="crop-mark-bl" aria-hidden="true"></span>
        <span class="crop-mark-br" aria-hidden="true"></span>
        <header class="wc-c22-block__head">
          <h3 class="wc-c22-block__title" data-i18n-key="portfolio.world_cup.fifa_power_outfield_title">Jogadores de linha · top 15</h3>
          <div class="wc-match-select-wrap">
            <label for="fifa-power-select" class="mono-label" data-i18n-key="portfolio.world_cup.fifa_select_axis">eixo</label>
            <select id="fifa-power-select" class="wc-cl-select"></select>
          </div>
        </header>
        <div class="wc-scorers-wrap crop">
          <span class="crop-mark-bl" aria-hidden="true"></span>
          <span class="crop-mark-br" aria-hidden="true"></span>
          <table class="wc-scorers-table" aria-label="Power ranking FIFA de jogadores de linha pelo eixo selecionado"
                 data-i18n-aria="portfolio.world_cup.fifa_power_outfield_aria">
            <thead>
              <tr>
                <th scope="col" class="wc-scorers-table__rank" data-i18n-key="portfolio.world_cup.col_rank">#</th>
                <th scope="col" class="wc-scorers-table__player" data-i18n-key="portfolio.world_cup.col_player">Jogador</th>
                <th scope="col" class="wc-scorers-table__goals" data-i18n-key="portfolio.world_cup.fifa_power_col_score">Nota</th>
                <th scope="col" class="wc-scorers-table__pen" data-i18n-key="portfolio.world_cup.fifa_power_col_change">Var.</th>
              </tr>
            </thead>
            <tbody id="fifa-power-body">
              <tr><td colspan="4"><p class="wc-loading mono-label">carregando ranking…</p></td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Goleiros top-5 por defesa -->
      <div class="wc-c22-block card crop">
        <span class="crop-mark-bl" aria-hidden="true"></span>
        <span class="crop-mark-br" aria-hidden="true"></span>
        <h3 class="wc-c22-block__title" data-i18n-key="portfolio.world_cup.fifa_power_gk_title">Goleiros · top 5 por defesa</h3>
        <div class="wc-scorers-wrap crop">
          <span class="crop-mark-bl" aria-hidden="true"></span>
          <span class="crop-mark-br" aria-hidden="true"></span>
          <table class="wc-scorers-table" aria-label="Top 5 goleiros do power ranking FIFA por defesa"
                 data-i18n-aria="portfolio.world_cup.fifa_power_gk_aria">
            <thead>
              <tr>
                <th scope="col" class="wc-scorers-table__rank" data-i18n-key="portfolio.world_cup.col_rank">#</th>
                <th scope="col" class="wc-scorers-table__player" data-i18n-key="portfolio.world_cup.col_player">Goleiro</th>
                <th scope="col" class="wc-scorers-table__goals" data-i18n-key="portfolio.world_cup.fifa_power_col_score">Nota</th>
              </tr>
            </thead>
            <tbody id="fifa-gk-body">
              <tr><td colspan="3"><p class="wc-loading mono-label">carregando…</p></td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════════════ [13] FIFA · COMPARADOR DE SELEÇÕES ═══════════════════ -->
<section id="fifa-compare" class="section wc-fifa-section" aria-labelledby="fifa-compare-title">
  <div class="container">
    <div class="section-head" data-reveal>
      <span class="mono-label">13</span>
      <h2 id="fifa-compare-title" class="wc-display" data-i18n-key="portfolio.world_cup.fifa_compare_title">Comparador de seleções</h2>
      <p class="wc-lead" data-i18n-key="portfolio.world_cup.fifa_compare_lead">
        Duas seleções, seis métricas FIFA, um radar. Cada eixo está na sua própria escala (a líder daquela métrica toca a borda), então o desenho mostra o PERFIL de jogo — quem ataca, quem controla, quem pressiona. A lista abaixo traz o número cru e a diferença.
      </p>
    </div>
    <hr class="section-line" aria-hidden="true" data-reveal />

    <p class="wc-error mono-label" id="fifa-compare-error" hidden data-i18n-key="portfolio.world_cup.fifa_compare_error">Comparador FIFA indisponível.</p>

    <div class="wc-c22-block card crop">
      <span class="crop-mark-bl" aria-hidden="true"></span>
      <span class="crop-mark-br" aria-hidden="true"></span>
      <header class="wc-c22-block__head fifa-compare-head">
        <div class="wc-match-select-wrap">
          <label for="fifa-compare-a" class="mono-label" data-i18n-key="portfolio.world_cup.fifa_compare_team_a">seleção A</label>
          <select id="fifa-compare-a" class="wc-cl-select"></select>
        </div>
        <div class="wc-match-select-wrap">
          <label for="fifa-compare-b" class="mono-label" data-i18n-key="portfolio.world_cup.fifa_compare_team_b">seleção B</label>
          <select id="fifa-compare-b" class="wc-cl-select"></select>
        </div>
      </header>
      <div class="fifa-compare-grid">
        <div class="wc-c22-block__chart fifa-radar-host" id="fifa-compare-radar" role="img"
             aria-label="Radar comparando duas seleções em seis métricas FIFA por jogo."
             data-i18n-aria="portfolio.world_cup.fifa_compare_radar_aria">
          <p class="wc-loading mono-label">carregando radar…</p>
        </div>
        <div class="wc-stat-compare fifa-compare-deltas" id="fifa-compare-deltas" aria-live="polite">
          <p class="wc-loading mono-label" style="padding:var(--space-5)" data-i18n-key="portfolio.world_cup.fifa_compare_loading">Carregando comparação…</p>
        </div>
      </div>
    </div>
  </div>
</section>
`;
