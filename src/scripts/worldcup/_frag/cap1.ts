/**
 * cap1.ts — CHAPTER 1 (live-2026) render functions
 * ============================================================================
 * Ported from the legacy standalone app:
 *   public/world-cup-dashboard/js/main.js       (news, groups, bracket, MC,
 *                                                 matches, selection, insights,
 *                                                 bolão, "quem é o craque?",
 *                                                 tournament-progress, freshness,
 *                                                 stats-extra charts, team filter)
 *   public/world-cup-dashboard/js/deepstats.js  (shot stats, pass stats, momentum)
 *
 * Chart conversions (Chart.js → src/scripts/worldcup/charts.ts inline-SVG lib):
 *   chart-minutes    (vertical bar)   → barChart({ orientation: 'v' })
 *   chart-efficiency (horizontal bar) → barChart({ orientation: 'h' })
 *   chart-momentum   (2-series line)  → lineChart()
 * The shot/pass "stat-compare" rows are plain divs (as in deepstats.js) — no chart lib.
 *
 * Contract: each exported render fn takes the parsed JSON (already fetched by the
 * page) and hydrates its container. Every fn is:
 *   - idempotent  → clears its container before writing (safe across astro:page-load)
 *   - fail-soft   → null / malformed data renders a friendly message, never throws
 *   - SPA-safe    → module state (WC_STATE, deep-stats cache) is resettable; call
 *                   resetCap1State() at the top of the page's loader if desired.
 *
 * NO external deps. Palette comes only from tokens via readToken() (WC family).
 */

import { barChart, lineChart, readToken } from '../charts';

/* ────────────────────────────────────────────────────────────────────────── */
/* Types (loose — the pipeline JSON is the source of truth)                     */
/* ────────────────────────────────────────────────────────────────────────── */

export interface Team { name?: string; code?: string; flag?: string }

export interface Match {
  num?: number;
  round?: string;
  group?: string;
  status?: string;
  date?: string;
  time?: string;
  ground?: string;
  has_placeholder?: boolean;
  team1?: Team;
  team2?: Team;
  score?: { ft?: number[]; et?: number[]; pen?: number[] };
}
export interface PartidasPayload { matches?: Match[]; total?: number; updated_at?: string }

export interface NewsItem { title?: string; source?: string; url?: string; summary?: string; published?: string }
export interface NoticiasPayload { items?: NewsItem[]; source_feeds?: string[]; updated_at?: string }

export interface MinuteBucket { range?: string; count?: number }
export interface EfficiencyTeam {
  name?: string; code?: string; flag?: string;
  goals_for?: number; goals_against?: number; diff?: number;
  matches?: number; wins?: number; draws?: number; losses?: number;
  diff_per_match?: number;
}
export interface EstatisticasPayload {
  total_goals?: number;
  avg_goals_per_match?: number;
  penalties_scored?: number;
  own_goals?: number;
  biggest_win?: { match?: string; diff?: number } | null;
  highest_scoring_match?: { match?: string; goals?: number } | null;
  goals_by_minute?: MinuteBucket[];
  teams_efficiency?: EfficiencyTeam[];
  tournament_progress?: {
    current_phase?: string;
    progress_pct?: number;
    remaining_matches?: number;
    is_complete?: boolean;
    next_match?: { team1?: string; team2?: string; date?: string; time?: string } | null;
  } | null;
  updated_at?: string;
}

export interface GroupTeam {
  name?: string; flag?: string; position?: number; qualified?: boolean;
  pts?: number; played?: number; goals_for?: number; goals_against?: number; diff?: number;
}
export interface Group { group?: string; teams?: GroupTeam[] }
export interface GruposPayload { groups?: Group[]; updated_at?: string }

export interface SimTeam { rank?: number; name?: string; code?: string; flag?: string; elo?: number; title_probability?: number }
export interface SimulacaoPayload { teams?: SimTeam[]; simulations?: number; methodology?: string; updated_at?: string }

export interface XIPlayer { name?: string; position?: string; stat?: string; goals?: number; team?: Team }
export interface Goalkeeper { name?: string; team?: Team; clean_sheets?: number; ga_per_game?: number }
export interface SelecaoPayload { xi?: XIPlayer[]; top_goalkeepers?: Goalkeeper[]; best_goalkeeper?: { name?: string }; updated_at?: string }

export interface Insight { title?: string; body?: string }
export interface InsightsPayload { insights?: Insight[]; updated_at?: string }

export interface GamePlayer { id?: string; name?: string; position?: string; goals?: number; team?: Team }
export interface JogadoresPayload { players?: GamePlayer[]; updated_at?: string }

export interface DeepTeamShot {
  code?: string; flag?: string; name?: string;
  shots?: number; on_target?: number; on_target_pct?: number; blocked?: number; goals?: number;
}
export interface DeepTeamPass {
  code?: string; flag?: string; name?: string;
  possession?: number; passes?: number; accurate_passes?: number; pass_pct?: number;
  crosses?: number; long_balls?: number; corners?: number; offsides?: number; saves?: number;
  tackles?: number; interceptions?: number; clearances?: number; fouls?: number;
  yellow_cards?: number; red_cards?: number;
}
export interface DeepMomentum {
  labels?: number[];
  metric?: string; metric_label?: string;
  home?: { code?: string; name?: string; flag?: string; cum?: number[]; xg_cum?: number[] };
  away?: { code?: string; name?: string; flag?: string; cum?: number[]; xg_cum?: number[] };
  goals?: { minute?: number; team?: string; player?: string; cum?: number; xg_cum?: number }[];
}
export interface DeepStatsPayload {
  featured_id?: string;
  match_list?: { id?: string; label?: string }[];
  shot_stats?: { matches?: Record<string, { match?: string; source?: string; home?: DeepTeamShot; away?: DeepTeamShot }> };
  pass_stats?: { matches?: Record<string, { match?: string; source?: string; home?: DeepTeamPass; away?: DeepTeamPass }> };
  momentum?: { matches?: Record<string, DeepMomentum> };
  updated_at?: string;
}

/* ────────────────────────────────────────────────────────────────────────── */
/* Helpers                                                                      */
/* ────────────────────────────────────────────────────────────────────────── */

const $ = (id: string): HTMLElement | null => document.getElementById(id);

function esc(s: unknown): string {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

function reduced(): boolean {
  return typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false;
}

function num(v: unknown): number { return Number(v) || 0; }
function fmtInt(v: unknown): string { return num(v).toLocaleString('pt-BR'); }
function fmtPct(v: unknown, dec = 1): string { return num(v).toFixed(dec).replace('.', ',') + '%'; }

function flagHtml(flag?: string, fallback = '—'): string {
  return flag && flag.trim()
    ? `<span class="wc-flag" aria-hidden="true">${esc(flag)}</span>`
    : `<span class="wc-flag wc-flag--empty" aria-hidden="true">${esc(fallback)}</span>`;
}

/** Short date pt-BR: "02/07". */
function shortDate(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

/** ISO YYYY-MM-DD → "hoje" / "amanhã" / "06/07". */
function formatLocalDate(iso?: string): string {
  if (!iso) return '';
  try {
    const d = new Date(iso + 'T00:00:00');
    const today = new Date();
    if (d.toDateString() === today.toDateString()) return 'hoje';
    const tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1);
    if (d.toDateString() === tomorrow.toDateString()) return 'amanhã';
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
  } catch { return iso || ''; }
}

/** "há 2h" / "há 3d" / short date. */
function relativeTime(iso?: string): string {
  if (!iso) return '';
  const then = new Date(iso);
  if (isNaN(then.getTime())) return '';
  const sec = Math.round((Date.now() - then.getTime()) / 1000);
  const min = Math.round(sec / 60), hr = Math.round(min / 60), day = Math.round(hr / 24);
  if (sec < 45) return 'agora';
  if (min < 60) return `há ${min}min`;
  if (hr < 24) return `há ${hr}h`;
  if (day < 7) return `há ${day}d`;
  return then.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
}

/** Staleness of updated_at → { label, level: 'ok'|'amber' } | null. */
function freshness(updatedAt?: string): { label: string; level: 'ok' | 'amber' } | null {
  if (!updatedAt) return null;
  const then = new Date(updatedAt);
  if (isNaN(then.getTime())) return null;
  const hr = (Date.now() - then.getTime()) / 36e5;
  if (hr < 24) return { label: `atualizado há ${Math.round(hr)}h`, level: 'ok' };
  const days = Math.round(hr / 24);
  if (hr < 48) return { label: `atualizado há ${days}d`, level: 'ok' };
  return { label: `atualizado há ${days}d`, level: 'amber' };
}

/** Shorten "Kylian Mbappé" → last two tokens. */
function shortName(full?: string): string {
  if (!full) return '—';
  const parts = String(full).trim().split(/\s+/);
  return parts.length <= 1 ? parts[0] : parts.slice(-2).join(' ');
}

/**
 * Reveal any [data-reveal] descendants that were injected via innerHTML. The
 * page's own IntersectionObserver only watches nodes present at page-load; nodes
 * we inject need to be revealed here. Under reduced-motion (or if the page has
 * `html.has-js`), just mark them visible — the .is-visible class is the page CSS
 * contract (see cap1.notes.md).
 */
function revealInjected(root: HTMLElement | null): void {
  if (!root) return;
  const nodes = Array.from(root.querySelectorAll<HTMLElement>('[data-reveal]:not(.is-visible)'));
  if (!nodes.length) return;
  if (reduced() || typeof IntersectionObserver === 'undefined') {
    nodes.forEach((n) => n.classList.add('is-visible'));
    return;
  }
  const io = new IntersectionObserver((entries, obs) => {
    entries.forEach((en) => {
      if (en.isIntersecting) { en.target.classList.add('is-visible'); obs.unobserve(en.target); }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
  nodes.forEach((n) => io.observe(n));
}

/* ────────────────────────────────────────────────────────────────────────── */
/* Shared module state (resettable for SPA re-entry)                            */
/* ────────────────────────────────────────────────────────────────────────── */

const WC_STATE: { matches: Match[] } = { matches: [] };

const LS_CRAQUE = 'wc-craque-votes';
const LS_BOLAO = 'wc-bolao';
const LS_FILTER = 'wc-filter';

interface DuelState { players: GamePlayer[]; current: [GamePlayer, GamePlayer] | null }
const GAME: DuelState = { players: [], current: null };

let _deep: DeepStatsPayload | null = null;
let _deepSelectedId: string | null = null;

/** Reset all module-level caches. Call at the top of the page loader if re-entering. */
export function resetCap1State(): void {
  WC_STATE.matches = [];
  GAME.players = [];
  GAME.current = null;
  _deep = null;
  _deepSelectedId = null;
}

/* ────────────────────────────────────────────────────────────────────────── */
/* Hero companions: tournament progress + freshness                            */
/* ────────────────────────────────────────────────────────────────────────── */

export function renderTournamentProgress(stats: EstatisticasPayload | null): void {
  const wrap = $('wc-tournament-progress');
  if (!wrap) return;
  const tp = stats?.tournament_progress;
  if (!tp) { wrap.hidden = true; return; }
  wrap.hidden = false;

  const set = (id: string, v: string): void => { const n = $(id); if (n) n.textContent = v; };
  set('wc-progress-phase', tp.current_phase || '—');
  set('wc-progress-pct', (tp.progress_pct || 0).toFixed(1).replace('.', ',') + '%');

  const bar = $('wc-progress-bar');
  if (bar) bar.setAttribute('aria-valuenow', String(tp.progress_pct || 0));

  const fill = $('wc-progress-fill');
  if (fill) requestAnimationFrame(() => { fill.style.width = (tp.progress_pct || 0) + '%'; });

  const rem = $('wc-progress-remaining');
  if (rem) {
    if (tp.is_complete || tp.remaining_matches === 0) rem.textContent = 'Torneio finalizado 🏆';
    else { const n = tp.remaining_matches ?? 0; rem.textContent = `${n} ${n === 1 ? 'partida restante' : 'partidas restantes'}`; }
  }

  const next = $('wc-progress-next');
  if (next) {
    if (tp.is_complete || !tp.next_match) next.textContent = 'Campeão definido 🏆';
    else {
      const nm = tp.next_match;
      const dateStr = nm.date ? formatLocalDate(nm.date) : '';
      const timeStr = nm.time ? ` · ${nm.time}` : '';
      next.textContent = `Próxima: ${nm.team1} x ${nm.team2}${dateStr ? ' · ' + dateStr : ''}${timeStr}`;
    }
  }
}

/** Pass every loaded payload; picks the most recent updated_at. */
export function renderFreshness(payloads: Array<{ updated_at?: string } | null>): void {
  const times = payloads
    .map((p) => (p?.updated_at ? new Date(p.updated_at).getTime() : NaN))
    .filter((t) => !isNaN(t));
  if (!times.length) return;
  const latest = new Date(Math.max(...times));
  const f = freshness(latest.toISOString());
  if (!f) return;
  const badge = $('wc-freshness');
  if (badge) {
    badge.textContent = f.label;
    badge.hidden = false;
    if (f.level === 'amber') badge.dataset.stale = 'amber';
  }
  const footer = $('wc-footer-updated');
  if (footer) {
    footer.textContent = latest.toLocaleString('pt-BR', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  }
}

/* ────────────────────────────────────────────────────────────────────────── */
/* [01] Notícias                                                                */
/* ────────────────────────────────────────────────────────────────────────── */

export function renderNews(data: NoticiasPayload | null): void {
  const list = $('wc-news-list');
  if (!list) return;
  const items = data?.items;
  if (!Array.isArray(items) || !items.length) {
    list.innerHTML = '<li class="wc-error mono-label">feed de notícias indisponível</li>';
    return;
  }
  const sourceTag = $('wc-news-source');
  if (sourceTag && data!.source_feeds) {
    sourceTag.textContent = data!.source_feeds.join(' · ');
    sourceTag.hidden = false;
  }
  list.innerHTML = items.slice(0, 10).map((item) => {
    const title = esc(item.title);
    const source = esc(item.source || 'fonte');
    const rawUrl = String(item.url || '#');
    const safeUrl = /^https?:\/\//i.test(rawUrl) ? esc(rawUrl) : '#';
    const summary = esc((item.summary || '').replace(new RegExp(esc(item.source || '') + '$'), '').trim());
    const time = relativeTime(item.published);
    const external = safeUrl !== '#' ? ' target="_blank" rel="noopener noreferrer"' : '';
    return `
      <li class="wc-news-item">
        <a class="wc-news-link" href="${safeUrl}"${external}>
          <span class="wc-news-headline-text">${title}</span>
          ${summary ? `<span class="wc-news-summary">${summary}</span>` : ''}
          <span class="wc-news-meta">
            <span class="wc-news-source-tag">${source}</span>
            <span class="wc-news-time" title="${esc(item.published || '')}">${time}</span>
          </span>
        </a>
      </li>`;
  }).join('');
}

/* ────────────────────────────────────────────────────────────────────────── */
/* [03-extra] Estatísticas — minute bar + efficiency bar + "jogo com mais gols" */
/* (the doughnut + the four small cards already live in the skeleton)           */
/* ────────────────────────────────────────────────────────────────────────── */

export function renderStatsExtra(stats: EstatisticasPayload | null): void {
  // "jogo com mais gols" key-card
  const hi = $('wc-stat-hi'), hiSub = $('wc-stat-hi-sub');
  if (hi) hi.textContent = stats?.highest_scoring_match?.match ?? '—';
  if (hiSub) hiSub.textContent = stats?.highest_scoring_match?.goals != null
    ? `${stats.highest_scoring_match.goals} gols no total` : '';

  // Chart: gols por faixa de minuto (vertical bars). chart-minutes → barChart v.
  const minBox = $('wc-chart-minutes');
  if (minBox) {
    const gm = (stats?.goals_by_minute ?? []).filter((r) => r && typeof r.count === 'number');
    if (!gm.length) {
      minBox.innerHTML = '<p class="wc-error mono-label">série indisponível</p>';
    } else {
      barChart(minBox, {
        orientation: 'v',
        ariaLabel: 'Gols marcados em cada faixa de 15 minutos de jogo',
        axisTitle: 'faixa de minuto',
        valueFmt: (v) => String(v),
        data: gm.map((r) => ({ label: r.range ?? '', value: r.count ?? 0 })),
        tooltip: (d) => ({ title: `minuto ${d.label}`, rows: [{ name: 'gols', value: String(d.value ?? 0) }] }),
      });
    }
  }

  // Chart: ranking de eficiência top-8 (horizontal bars). chart-efficiency → barChart h.
  const effBox = $('wc-chart-efficiency');
  if (effBox) {
    const eff = (stats?.teams_efficiency ?? []).slice(0, 8);
    if (!eff.length) {
      effBox.innerHTML = '<p class="wc-error mono-label">série indisponível</p>';
    } else {
      barChart(effBox, {
        orientation: 'h',
        ariaLabel: 'Ranking das 8 seleções mais eficientes por saldo de gols por partida',
        axisTitle: 'saldo de gols por partida',
        valueFmt: (v) => v.toFixed(2).replace('.', ','),
        data: eff.map((t, i) => ({
          label: `${(t.flag || '').trim()} ${t.name ?? ''}`.trim(),
          value: num(t.diff_per_match),
          highlight: i === 0, // líder recebe ouro
          meta: t,
        })),
        tooltip: (d) => {
          const t = d.meta as EfficiencyTeam;
          const diff = num(t.diff);
          return {
            title: `${(t.flag || '').trim()} ${t.name ?? ''}`.trim(),
            rows: [
              { name: 'saldo/jogo', value: num(t.diff_per_match).toFixed(2), leader: !!d.highlight },
              { name: 'saldo total', value: `${diff > 0 ? '+' : ''}${diff} (${num(t.goals_for)}–${num(t.goals_against)})` },
              { name: 'jogos', value: `${num(t.matches)} (${num(t.wins)}V ${num(t.draws)}E ${num(t.losses)}D)` },
            ],
          };
        },
      });
    }
  }
}

/* ────────────────────────────────────────────────────────────────────────── */
/* [11] Monte Carlo                                                             */
/* ────────────────────────────────────────────────────────────────────────── */

export function renderProbabilities(data: SimulacaoPayload | null): void {
  const list = $('wc-prob-list');
  if (!list) return;
  const teams = data?.teams;
  if (!Array.isArray(teams) || !teams.length) {
    list.innerHTML = '<li class="wc-error mono-label">simulação indisponível</li>';
    return;
  }

  const method = $('wc-prob-method');
  if (method) {
    const sims = data!.simulations ? data!.simulations.toLocaleString('pt-BR') : '10.000';
    method.textContent = `metodologia: Monte Carlo · ${sims} simulações`;
  }
  const mcSource = $('wc-mc-modal-source');
  if (mcSource) {
    const methodology = data!.methodology || '';
    const updated = data!.updated_at ? new Date(data!.updated_at).toLocaleString('pt-BR', { timeZone: 'UTC' }) : '';
    if (methodology) { mcSource.textContent = (updated ? `${updated} UTC · ` : '') + methodology; mcSource.hidden = false; }
    else mcSource.hidden = true;
  }

  const top = teams.slice(0, 12);
  const elos = top.map((t) => num(t.elo));
  const maxElo = Math.max(...elos), minElo = Math.min(...elos);
  const eloRange = Math.max(1, maxElo - minElo);

  list.innerHTML = top.map((t, i) => {
    const isTop = i === 0;
    const elo = num(t.elo);
    const pct = num(t.title_probability);
    const widthPct = Math.round(((elo - minElo) / eloRange) * 100);
    const flagCell = t.flag
      ? `<span class="wc-prob-row__flag" aria-hidden="true">${esc(t.flag)}</span>`
      : `<span class="wc-prob-row__flag wc-flag--empty" aria-hidden="true">—</span>`;
    return `
      <li class="wc-prob-row ${isTop ? 'is-top' : ''}" data-reveal>
        <span class="wc-prob-row__rank">${t.rank || (i + 1)}</span>
        ${flagCell}
        <div class="wc-prob-row__main">
          <div class="wc-prob-row__name-line">
            <span class="wc-prob-row__name">${esc(t.name)}</span>
            <span class="wc-prob-row__elo">Elo ${elo.toFixed(1)}</span>
          </div>
          <div class="wc-prob-row__bar-wrap" aria-hidden="true">
            <span class="wc-prob-row__bar" data-width="${widthPct}"></span>
          </div>
        </div>
        <span class="wc-prob-row__pct" title="probabilidade de título (Monte Carlo)">${pct.toFixed(2)}%</span>
      </li>`;
  }).join('');

  // Anima as barras via transform: scaleX (perf-friendly).
  const motion = !reduced();
  Array.from(list.querySelectorAll<HTMLElement>('.wc-prob-row__bar')).forEach((bar, i) => {
    const scale = (num(bar.dataset.width)) / 100;
    if (motion) setTimeout(() => { bar.style.transform = `scaleX(${scale})`; }, 80 + i * 40);
    else { bar.style.transition = 'none'; bar.style.transform = `scaleX(${scale})`; }
  });

  revealInjected(list);
  wireMonteCarloModal();
}

/** Wire the info button + modal (idempotent — replaces handlers via onclick). */
function wireMonteCarloModal(): void {
  const btn = $('wc-mc-info-btn') as HTMLButtonElement | null;
  const modal = $('wc-mc-modal');
  if (!btn || !modal) return;
  const open = (): void => {
    modal.hidden = false;
    btn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
    const close = modal.querySelector<HTMLElement>('[data-close-modal]');
    setTimeout(() => close?.focus({ preventScroll: true }), 30);
  };
  const close = (): void => {
    modal.hidden = true;
    btn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
    btn.focus({ preventScroll: true });
  };
  btn.onclick = open;
  modal.querySelectorAll<HTMLElement>('[data-close-modal]').forEach((el) => { el.onclick = close; });
  modal.onkeydown = (e) => {
    const ev = e as KeyboardEvent;
    if (ev.key === 'Escape') { close(); return; }
    if (ev.key === 'Tab') trapTab(ev, modal);
  };
}

/** Focus-trap: cicla Tab/Shift+Tab entre os focáveis do painel do modal
 *  (aria-modal exige que o foco não escape p/ a página atrás). */
function trapTab(ev: KeyboardEvent, modal: HTMLElement): void {
  const panel = modal.querySelector<HTMLElement>('.wc-modal__panel') || modal;
  const f = Array.from(panel.querySelectorAll<HTMLElement>(
    'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])',
  )).filter((el) => el.offsetParent !== null);
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  const active = document.activeElement as HTMLElement | null;
  if (ev.shiftKey && active === first) { ev.preventDefault(); last.focus(); }
  else if (!ev.shiftKey && active === last) { ev.preventDefault(); first.focus(); }
}

/* ────────────────────────────────────────────────────────────────────────── */
/* [12] Grupos                                                                  */
/* ────────────────────────────────────────────────────────────────────────── */

export function renderGroups(data: GruposPayload | null): void {
  const host = $('wc-groups-grid');
  if (!host) return;
  const groups = data?.groups;
  if (!Array.isArray(groups) || !groups.length) {
    host.innerHTML = '<div class="wc-error mono-label" style="grid-column:1/-1">tabela de grupos indisponível</div>';
    return;
  }
  host.innerHTML = groups.map(groupCardHtml).join('');
  revealInjected(host);
}

function groupCardHtml(g: Group): string {
  const letter = (g.group || '').replace(/.*Group\s*/i, '').trim() || '?';
  const rows = (g.teams || []).slice().sort((a, b) => (a.position || 99) - (b.position || 99));
  const rowsHtml = rows.map((t) => {
    const isQ = t.qualified === true;
    const diff = num(t.diff);
    const diffCls = diff > 0 ? 'is-positive' : (diff < 0 ? 'is-negative' : '');
    const diffTxt = (diff > 0 ? '+' : '') + diff;
    const gpGc = `${t.goals_for || 0}:${t.goals_against || 0}`;
    const flagCell = t.flag
      ? `<span class="wc-group-row__flag" aria-hidden="true">${esc(t.flag)}</span>`
      : `<span class="wc-group-row__flag" aria-hidden="true">·</span>`;
    const badge = isQ ? '<span class="wc-group-row__badge" aria-label="classificado" title="Classificado">✓</span>' : '';
    return `
      <div class="wc-group-row ${isQ ? 'is-qualified' : ''}" role="listitem">
        ${flagCell}
        <span class="wc-group-row__name-block">
          <span class="wc-group-row__name">${esc(t.name || '—')}</span>
          ${badge}
        </span>
        <span class="wc-group-row__pts" title="pontos">${t.pts || 0}</span>
        <span class="wc-group-row__played" title="jogos">${t.played || 0}</span>
        <span class="wc-group-row__gca" title="gols pró : gols contra">${gpGc}</span>
        <span class="wc-group-row__diff ${diffCls}" title="saldo">${diffTxt}</span>
      </div>`;
  }).join('');
  return `
    <div class="card crop wc-group-card" role="listitem" data-reveal>
      <span class="crop-mark-bl" aria-hidden="true"></span>
      <span class="crop-mark-br" aria-hidden="true"></span>
      <header class="wc-group-card__head">
        <span class="mono-label">${esc('GRUPO ' + letter)}</span>
        <span class="mono-label" style="color:var(--ink-faint)">${rows.length} sel.</span>
      </header>
      <div class="wc-group-rows" role="list">${rowsHtml}</div>
    </div>`;
}

/* ────────────────────────────────────────────────────────────────────────── */
/* [13] Mata-mata (bracket)                                                     */
/* ────────────────────────────────────────────────────────────────────────── */

const BRACKET_ROUNDS = [
  { match: 'Round of 32', short: '16 AVOS' },
  { match: 'Round of 16', short: 'OITAVAS' },
  { match: 'Quarter-final', short: 'QUARTAS' },
  { match: 'Semi-final', short: 'SEMIS' },
  { match: 'Final', short: 'FINAL' },
  { match: 'Match for third place', short: '3º LUGAR' },
];
const BRACKET_CROSSING: Record<number, number[]> = {
  89: [74, 77], 90: [73, 75], 91: [76, 78], 92: [79, 80],
  93: [83, 84], 94: [81, 82], 95: [86, 88], 96: [85, 87],
  97: [89, 90], 98: [93, 94], 99: [91, 92], 100: [95, 96],
  101: [97, 98], 102: [99, 100], 104: [101, 102],
};
const BRACKET_SIDES: Record<number, string> = {
  101: 'A', 97: 'A', 98: 'A', 89: 'A', 90: 'A', 93: 'A', 94: 'A',
  73: 'A', 74: 'A', 75: 'A', 77: 'A', 81: 'A', 82: 'A', 83: 'A', 84: 'A',
  102: 'B', 99: 'B', 100: 'B', 91: 'B', 92: 'B', 95: 'B', 96: 'B',
  76: 'B', 78: 'B', 79: 'B', 80: 'B', 85: 'B', 86: 'B', 87: 'B', 88: 'B',
  103: 'C', 104: 'C',
};
const BRACKET_SIDE_ROUNDS = ['Round of 32', 'Round of 16', 'Quarter-final', 'Semi-final'];

function buildBracketVisualOrder(matches: Match[]): Record<string, Match[]> {
  const byNum = new Map<number, Match>();
  matches.forEach((m) => { if (m.num) byNum.set(m.num, m); });
  const PH_RE = /^W(\d+)$/;
  const getPlaceholder = (t?: Team): number | null => {
    if (!t) return null;
    const c = String(t.code || '').match(PH_RE); if (c) return parseInt(c[1], 10);
    const n = String(t.name || '').match(PH_RE); if (n) return parseInt(n[1], 10);
    return null;
  };
  const sourcesByNum = new Map<number, number[]>();
  matches.forEach((m) => {
    if (!m.num) return;
    const srcs: number[] = [];
    const s1 = getPlaceholder(m.team1), s2 = getPlaceholder(m.team2);
    if (s1) srcs.push(s1); if (s2) srcs.push(s2);
    if (!srcs.length && BRACKET_CROSSING[m.num]) srcs.push(...BRACKET_CROSSING[m.num]);
    if (srcs.length) sourcesByNum.set(m.num, srcs);
  });
  const byRound: Record<string, Match[]> = {};
  BRACKET_ROUNDS.forEach((r) => { byRound[r.match] = []; });
  matches.forEach((m) => { if (m.round && byRound[m.round]) byRound[m.round].push(m); });
  Object.values(byRound).forEach((arr) => arr.sort((a, b) => (a.num || 0) - (b.num || 0)));

  const order = ['Round of 32', 'Round of 16', 'Quarter-final', 'Semi-final', 'Final'];
  for (let i = order.length - 2; i >= 0; i--) {
    const curr = order[i], next = order[i + 1];
    const nextOrdered = byRound[next] || [];
    const reordered: Match[] = [];
    const added = new Set<number>();
    nextOrdered.forEach((nm) => {
      (sourcesByNum.get(nm.num!) || []).forEach((srcNum) => {
        if (added.has(srcNum)) return;
        const src = byNum.get(srcNum);
        if (src && src.round === curr) { reordered.push(src); added.add(srcNum); }
      });
    });
    (byRound[curr] || []).forEach((m) => { if (!added.has(m.num!)) { reordered.push(m); added.add(m.num!); } });
    byRound[curr] = reordered;
  }
  return byRound;
}

export function renderBracket(data: PartidasPayload | null): void {
  const host = $('wc-bracket-host');
  if (!host) return;
  if (!Array.isArray(data?.matches)) {
    host.innerHTML = '<p class="wc-error mono-label">bracket indisponível</p>';
    return;
  }
  const ko = data!.matches!.filter((m) => m.round && !/matchday/i.test(m.round));
  const byRound = buildBracketVisualOrder(ko);
  const split: Record<string, Record<string, Match[]>> = { A: {}, B: {}, C: {} };
  Object.entries(byRound).forEach(([round, ms]) => {
    ms.forEach((m) => {
      const side = BRACKET_SIDES[m.num!] || 'C';
      (split[side][round] ||= []).push(m);
    });
  });

  const sideColHtml = (round: string, side: string): string => {
    const ms = split[side][round] || [];
    const meta = BRACKET_ROUNDS.find((r) => r.match === round);
    const label = meta ? meta.short : round;
    return `
      <div class="wc-bracket-side__col" data-round="${esc(round)}">
        <div class="wc-bracket-side__col-head mono-label">${label}</div>
        <div class="wc-bracket-side__matches">
          ${ms.length ? ms.map(bracketMatchHtml).join('') : '<div class="wc-bracket-match wc-bracket-match--empty" aria-hidden="true"></div>'}
        </div>
      </div>`;
  };

  const desktopHtml = `
    <div class="wc-bracket-tree" role="region" aria-label="Chave do mata-mata">
      <div class="wc-bracket-tree__side wc-bracket-tree__side--left">
        <div class="wc-bracket-tree__head mono-label">Lado A → SF1</div>
        <div class="wc-bracket-tree__cols">${BRACKET_SIDE_ROUNDS.map((r) => sideColHtml(r, 'A')).join('')}</div>
      </div>
      <div class="wc-bracket-tree__center">
        <div class="wc-bracket-tree__head mono-label">Final</div>
        ${(split.C['Final'] || []).map(bracketMatchHtml).join('')}
        <div class="wc-bracket-tree__trophy" aria-hidden="true">🏆</div>
        ${split.C['Match for third place']?.length
          ? `<div class="wc-bracket-tree__head mono-label" style="margin-top:var(--space-2)">3º lugar</div>${split.C['Match for third place'].map(bracketMatchHtml).join('')}`
          : ''}
      </div>
      <div class="wc-bracket-tree__side wc-bracket-tree__side--right">
        <div class="wc-bracket-tree__head mono-label">SF2 ← Lado B</div>
        <div class="wc-bracket-tree__cols">${[...BRACKET_SIDE_ROUNDS].reverse().map((r) => sideColHtml(r, 'B')).join('')}</div>
      </div>
    </div>`;

  const mobileSideHtml = (side: string, label: string, open: boolean): string => {
    const rounds = side === 'B' ? [...BRACKET_SIDE_ROUNDS].reverse() : BRACKET_SIDE_ROUNDS;
    const sections = rounds.map((r) => {
      const ms = split[side][r] || [];
      if (!ms.length) return '';
      const meta = BRACKET_ROUNDS.find((rr) => rr.match === r);
      return `<div class="wc-bracket-mobile__round"><div class="wc-bracket-mobile__round-head mono-label">${meta ? meta.short : r}</div>${ms.map(bracketMatchHtml).join('')}</div>`;
    }).join('');
    const center = side === 'C' && split.C['Final'];
    if (!sections && !center) return '';
    return `
      <details ${open ? 'open' : ''}>
        <summary><span class="mono-label">${label}</span></summary>
        <div class="wc-bracket-mobile__body">
          ${center ? `
            <div class="wc-bracket-mobile__round"><div class="wc-bracket-mobile__round-head mono-label">Final</div>${split.C['Final'].map(bracketMatchHtml).join('')}</div>
            ${split.C['Match for third place']?.length ? `<div class="wc-bracket-mobile__round"><div class="wc-bracket-mobile__round-head mono-label">3º lugar</div>${split.C['Match for third place'].map(bracketMatchHtml).join('')}</div>` : ''}
          ` : sections}
        </div>
      </details>`;
  };

  const mobileHtml = `
    <div class="wc-bracket-mobile" role="region" aria-label="Chave do mata-mata">
      ${mobileSideHtml('A', 'Lado A → SF1', true)}
      ${mobileSideHtml('C', 'Final', false)}
      ${mobileSideHtml('B', 'SF2 ← Lado B', true)}
    </div>`;

  host.innerHTML = desktopHtml + mobileHtml;
  revealInjected(host);
}

function bracketMatchHtml(m: Match): string {
  const isToday = m.status === 'today';
  const isFinished = m.status === 'finished' || !!(m.score && m.score.ft);
  const isFinalDone = isFinished && m.round === 'Final';
  const cls = ['wc-bracket-match'];
  if (isToday) cls.push('is-today');
  if (isFinalDone) cls.push('is-final-done');

  const t1 = m.team1 || {}, t2 = m.team2 || {};
  const s = m.score || {};
  const ft = Array.isArray(s.ft) && s.ft.length === 2 ? s.ft : null;
  const et = Array.isArray(s.et) && s.et.length === 2 ? s.et : null;
  const pen = Array.isArray(s.pen) && s.pen.length === 2 ? s.pen : null;

  let w1: boolean | null = null, w2: boolean | null = null;
  let sc1: string | number | null = ft ? ft[0] : null;
  let sc2: string | number | null = ft ? ft[1] : null;
  if (ft && isFinished) {
    if (ft[0] > ft[1]) w1 = true;
    else if (ft[1] > ft[0]) w2 = true;
    else if (et && et[0] !== et[1]) { sc1 = et[0]; sc2 = et[1]; if (et[0] > et[1]) w1 = true; else w2 = true; }
    else if (pen && pen[0] !== pen[1]) { sc1 = `${ft[0]} (${pen[0]})`; sc2 = `${ft[1]} (${pen[1]})`; if (pen[0] > pen[1]) w1 = true; else w2 = true; }
  }
  const pending = !ft;

  const teamRow = (team: Team, winner: boolean | null, score: string | number | null): string => {
    const isPh = !team || !team.name || team.name === 'A definir';
    const name = isPh ? 'A definir' : esc(team.name);
    const nameCls = ['wc-bracket-match__name'];
    if (isPh) nameCls.push('wc-bracket-match__name--placeholder');
    else if (winner === true) nameCls.push('wc-bracket-match__name--winner');
    else if (winner === false) nameCls.push('wc-bracket-match__name--loser');
    const flagCell = team && team.flag && !isPh ? `<span class="wc-bracket-match__flag" aria-hidden="true">${esc(team.flag)}</span>` : '';
    let scoreHtml: string;
    if (pending) scoreHtml = '<span class="wc-bracket-match__score wc-bracket-match__score--pending">—</span>';
    else {
      const sCls = ['wc-bracket-match__score'];
      if (winner === true) sCls.push('wc-bracket-match__score--winner');
      else if (winner === false) sCls.push('wc-bracket-match__score--loser');
      scoreHtml = `<span class="${sCls.join(' ')}">${esc(score)}</span>`;
    }
    return `<div class="wc-bracket-match__row"><span class="wc-bracket-match__team">${flagCell}<span class="${nameCls.join(' ')}">${name}</span></span>${scoreHtml}</div>`;
  };

  const rowsHtml =
    teamRow(t1, w1 === true ? true : (w2 === true ? false : null), sc1) +
    teamRow(t2, w2 === true ? true : (w1 === true ? false : null), sc2);
  const todayTag = isToday ? '<span class="wc-bracket-match__today-tag">HOJE</span>' : '';
  return `<div class="${cls.join(' ')}" data-match-num="${m.num || ''}">${rowsHtml}${todayTag}</div>`;
}

/* ────────────────────────────────────────────────────────────────────────── */
/* [17] Partidas + [Filtro] Minha Seleção                                       */
/* ────────────────────────────────────────────────────────────────────────── */

export function renderMatches(data: PartidasPayload | null): void {
  const recentEl = $('wc-matches-recent'), upcomingEl = $('wc-matches-upcoming');
  if (!recentEl || !upcomingEl) return;
  if (!Array.isArray(data?.matches)) {
    const msg = '<li class="wc-error mono-label">partidas indisponíveis</li>';
    recentEl.innerHTML = msg; upcomingEl.innerHTML = msg;
    return;
  }
  const matches = data!.matches!;
  WC_STATE.matches = matches;

  const finished = matches.filter((m) => m.status === 'finished' || (m.score && m.score.ft));
  const today = matches.filter((m) => m.status === 'today');
  const sched = matches.filter((m) => m.status === 'scheduled');

  const recent = finished.slice()
    .sort((a, b) => new Date(b.date || '').getTime() - new Date(a.date || '').getTime())
    .slice(0, 8).reverse();
  const upcoming = today.concat(sched)
    .sort((a, b) => new Date(`${a.date} ${a.time || ''}`).getTime() - new Date(`${b.date} ${b.time || ''}`).getTime())
    .slice(0, 10);

  recentEl.innerHTML = recent.length ? recent.map(matchRowHtml).join('') : '<li class="wc-loading mono-label">sem resultados recentes</li>';
  upcomingEl.innerHTML = upcoming.length ? upcoming.map(matchRowHtml).join('') : '<li class="wc-loading mono-label">sem jogos agendados</li>';
}

function matchRowHtml(m: Match): string {
  const isToday = m.status === 'today';
  const cls = ['wc-match'];
  if (isToday) cls.push('wc-match--today');
  if (m.has_placeholder === true) cls.push('wc-match--placeholder');

  const t1 = m.team1 || {}, t2 = m.team2 || {};
  const ft = m.score && Array.isArray(m.score.ft) ? m.score.ft : null;
  const pen = m.score && Array.isArray(m.score.pen) ? m.score.pen : null;
  const pending = !ft;

  const isPh1 = !t1.name || t1.name === 'A definir';
  const isPh2 = !t2.name || t2.name === 'A definir';
  const penNote = (!pending && pen && ft![0] === ft![1]) ? `<span class="wc-match__score-pen" title="Pênaltis">(${pen[0]}–${pen[1]})</span>` : '';
  const scoreHtml = pending
    ? '<span class="wc-match__score wc-match__score--pending">vs</span>'
    : `<span class="wc-match__score"><span class="wc-match__score-num">${ft![0]}</span><span class="wc-match__score-sep">–</span><span class="wc-match__score-num">${ft![1]}</span>${penNote}</span>`;
  const todayBadge = isToday ? '<span class="wc-match__today-badge" aria-label="Jogo de hoje">Hoje</span>' : '';
  const dateTxt = shortDate(m.date);
  const timeTxt = m.time ? esc(m.time) : '';
  const roundTxt = m.round ? esc(m.round) : (m.group && m.group !== 'null' ? esc(m.group) : '');
  const groundTxt = m.ground ? esc(m.ground) : '';

  return `
    <li class="${cls.join(' ')}" data-match-num="${m.num || ''}" data-team1="${esc(t1.name || '')}" data-team2="${esc(t2.name || '')}" data-team1-code="${esc(t1.code || '')}" data-team2-code="${esc(t2.code || '')}">
      <div class="wc-match__team">${flagHtml(t1.flag)}<span class="wc-match__name ${isPh1 ? 'wc-match__name--placeholder' : ''}">${esc(t1.name || 'A definir')}</span></div>
      ${scoreHtml}
      <div class="wc-match__team wc-match__team--right">${flagHtml(t2.flag)}<span class="wc-match__name ${isPh2 ? 'wc-match__name--placeholder' : ''}">${esc(t2.name || 'A definir')}</span></div>
      <div class="wc-match__meta">
        <span class="wc-match__round">${roundTxt}${todayBadge}</span>
        <span class="wc-match__time">${dateTxt}${timeTxt ? ' · ' + timeTxt : ''}${groundTxt ? ' · ' + groundTxt : ''}</span>
      </div>
    </li>`;
}

/** Team filter chips (highlight/dim across matches + news). Call after renderMatches. */
export function setupTeamFilter(): void {
  const host = $('wc-team-filter'), chips = $('wc-team-filter-chips');
  if (!host || !chips) return;
  const teams: Record<string, { name: string; code: string; flag: string }> = {};
  (WC_STATE.matches || []).forEach((m) => {
    [m.team1, m.team2].forEach((t) => {
      if (!t || !t.name || t.name === 'A definir') return;
      const key = t.code || t.name;
      if (!teams[key]) teams[key] = { name: t.name, code: t.code || '', flag: t.flag || '' };
    });
  });
  const arr = Object.values(teams).sort((a, b) => a.name.localeCompare(b.name));
  if (!arr.length) { host.hidden = true; return; }
  host.hidden = false;

  const read = (): string => { try { return localStorage.getItem(LS_FILTER) || ''; } catch { return ''; } };
  const renderChips = (): void => {
    const saved = read();
    chips.innerHTML = arr.map((t) => {
      const pressed = !!(saved && saved === (t.code || t.name));
      const flag = t.flag ? `<span class="wc-team-chip__flag" aria-hidden="true">${esc(t.flag)}</span>` : '';
      return `<button type="button" class="wc-team-chip" data-team="${esc(t.code || t.name)}" aria-pressed="${pressed}">${flag}<span>${esc(t.name)}</span></button>`;
    }).join('') + (saved ? '<button type="button" class="wc-team-chip__clear" id="wc-team-filter-clear">limpar filtro ✕</button>' : '');
  };
  const applyFilter = (name: string): void => {
    const team = arr.find((t) => (t.code || t.name) === name) || null;
    const keyword = team ? team.name.toLowerCase() : '';
    const code = team && team.code ? team.code.toLowerCase() : '';
    document.querySelectorAll<HTMLElement>('.wc-match').forEach((el) => {
      if (!name) { el.classList.remove('is-highlighted', 'is-dimmed'); return; }
      const t1 = (el.dataset.team1 || '').toLowerCase();
      const t2 = (el.dataset.team2 || '').toLowerCase();
      const t1c = (el.dataset.team1Code || '').toLowerCase();
      const t2c = (el.dataset.team2Code || '').toLowerCase();
      const hit = t1 === keyword || t2 === keyword || t1c === code || t2c === code;
      el.classList.toggle('is-highlighted', hit); el.classList.toggle('is-dimmed', !hit);
    });
    document.querySelectorAll<HTMLElement>('.wc-news-link').forEach((el) => {
      if (!name) { el.classList.remove('is-highlighted', 'is-dimmed'); return; }
      const txt = (el.textContent || '').toLowerCase();
      const hit = !!keyword && txt.includes(keyword);
      el.classList.toggle('is-highlighted', hit); el.classList.toggle('is-dimmed', !hit);
    });
  };
  const wire = (): void => {
    chips.querySelectorAll<HTMLElement>('.wc-team-chip').forEach((chip) => {
      chip.onclick = () => {
        const team = chip.dataset.team || '';
        const isPressed = chip.getAttribute('aria-pressed') === 'true';
        try { if (isPressed) localStorage.removeItem(LS_FILTER); else localStorage.setItem(LS_FILTER, team); } catch { /* ignore */ }
        renderChips(); applyFilter(isPressed ? '' : team); wire();
      };
    });
    const clear = chips.querySelector<HTMLElement>('#wc-team-filter-clear');
    if (clear) clear.onclick = () => {
      try { localStorage.removeItem(LS_FILTER); } catch { /* ignore */ }
      renderChips(); applyFilter(''); wire();
    };
  };
  renderChips(); wire();
  const saved = read();
  if (saved) applyFilter(saved);
}

/* ────────────────────────────────────────────────────────────────────────── */
/* [14] Seleção da Copa                                                         */
/* ────────────────────────────────────────────────────────────────────────── */

export function renderSelection(data: SelecaoPayload | null): void {
  const host = $('wc-selection-host');
  if (!host) return;
  if (!Array.isArray(data?.xi) || !data!.xi!.length) {
    host.innerHTML = '<p class="wc-error mono-label">seleção da copa indisponível</p>';
    return;
  }
  const byPos: Record<string, XIPlayer[]> = { GK: [], DF: [], MF: [], FW: [] };
  data!.xi!.forEach((p) => { const pos = (p.position || '').toUpperCase(); if (byPos[pos]) byPos[pos].push(p); });

  const parseGoals = (p: XIPlayer): number => {
    if (typeof p.goals === 'number') return p.goals;
    const m = String(p.stat || '').match(/(\d+)\s*gol/i);
    return m ? parseInt(m[1], 10) : 0;
  };
  const playerKey = (p: XIPlayer): string => (p.name || '') + '|' + ((p.team && p.team.code) || '');
  let topScorerId: string | null = null, topScorerGoals = -1;
  byPos.FW.forEach((p) => { const g = parseGoals(p); if (g > topScorerGoals) { topScorerGoals = g; topScorerId = playerKey(p); } });
  const isTopScorer = (p: XIPlayer): boolean => topScorerId !== null && playerKey(p) === topScorerId;

  const tokenHtml = (p: XIPlayer, isGK: boolean): string => {
    const isTop = !isGK && isTopScorer(p);
    const team = p.team || {};
    const initials = (p.name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join('') || '?';
    const flag = team.flag ? esc(team.flag) : '';
    const stat = esc(p.stat || '');
    const cls = ['wc-player-token'];
    if (isGK) cls.push('wc-player-token--gk');
    if (isTop) cls.push('wc-player-token--topscorer');
    const titleParts = [p.name, team.name, team.code, p.position, p.stat, isTop ? 'artilheiro da seleção' : ''].filter(Boolean).map((s) => esc(s));
    return `
      <div class="${cls.join(' ')}" title="${titleParts.join(' · ')}">
        <div class="wc-player-token__circle"><span class="wc-player-token__initials" aria-hidden="true">${esc(initials)}</span></div>
        <span class="wc-player-token__name">${esc(shortName(p.name))}</span>
        <span class="wc-player-token__stat">${flag} ${stat}</span>
      </div>`;
  };
  const rowHtml = (players: XIPlayer[], rowCls: string, isGK: boolean): string =>
    `<div class="wc-pitch__row ${rowCls}">${players.map((p) => tokenHtml(p, isGK)).join('')}</div>`;

  const topGks = Array.isArray(data!.top_goalkeepers) ? data!.top_goalkeepers!.slice(0, 5) : [];
  const bestGkName = data!.best_goalkeeper && data!.best_goalkeeper.name;
  const gksHtml = topGks.map((gk) => {
    const team = gk.team || {};
    const initials = (gk.name || '?').split(/\s+/).slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join('') || '?';
    const flag = team.flag ? esc(team.flag) : '';
    const isBest = bestGkName && gk.name === bestGkName;
    const stat = `${gk.clean_sheets || 0} CS · GA ${typeof gk.ga_per_game === 'number' ? gk.ga_per_game.toFixed(2) : '—'}`;
    return `
      <div class="wc-top-gk ${isBest ? 'wc-top-gk--best' : ''}" title="${esc(gk.name || '')} · ${esc(stat)}">
        <div class="wc-top-gk__avatar">${esc(initials)}</div>
        <span class="wc-top-gk__flag" aria-hidden="true">${flag}</span>
        <span class="wc-top-gk__name">${esc(shortName(gk.name))}</span>
        <span class="wc-top-gk__stat">${esc(stat)}</span>
      </div>`;
  }).join('');

  host.innerHTML = `
    <div class="wc-pitch crop" role="img" aria-label="Campo 4-3-3 com a seleção da Copa">
      <span class="crop-mark-bl" aria-hidden="true"></span>
      <span class="crop-mark-br" aria-hidden="true"></span>
      ${rowHtml(byPos.GK, 'wc-pitch__row--gk', true)}${rowHtml(byPos.DF, 'wc-pitch__row--df', false)}${rowHtml(byPos.MF, 'wc-pitch__row--mf', false)}${rowHtml(byPos.FW, 'wc-pitch__row--fw', false)}
    </div>
    ${topGks.length ? `
      <div class="wc-top-gks">
        <header class="wc-top-gks__head"><span class="mono-label">goleiros</span><span class="mono-label" style="color:var(--ink-faint)">top ${topGks.length}</span></header>
        <div class="wc-top-gks__list">${gksHtml}</div>
      </div>` : ''}`;
  revealInjected(host);
}

/* ────────────────────────────────────────────────────────────────────────── */
/* [15] Insights                                                                */
/* ────────────────────────────────────────────────────────────────────────── */

function categorizeInsight(text: string): string {
  const t = String(text || '').toLowerCase();
  if (/(defesa|sólid|sofreu|clean sheet|goleiro|sem ceder|levou|gols contra)/.test(t)) return 'field';
  if (/(pênalti|penal|quando|tempo|minuto|marca penal)/.test(t)) return 'live';
  if (/(artilheiro|chuteira|ataque|letal|ofensiv|marcou|gols?|aproveitamento|goleada|ritmo)/.test(t)) return 'gold';
  return 'ink';
}

export function renderInsights(data: InsightsPayload | null): void {
  const host = $('wc-insights-grid');
  if (!host) return;
  if (!Array.isArray(data?.insights) || !data!.insights!.length) {
    host.innerHTML = '<div class="wc-error mono-label" style="grid-column:1/-1">insights indisponíveis</div>';
    return;
  }
  const layout = ['hero', 'hero', 'md', 'md', 'md', 'md', 'hero', 'hero'];
  host.innerHTML = data!.insights!.slice(0, 8).map((ins, i) => {
    const numLabel = String(i + 1).padStart(2, '0');
    const title = esc(ins.title || '');
    const body = esc(ins.body || '');
    const cat = categorizeInsight((ins.title || '') + ' ' + (ins.body || ''));
    const bodyWithKey = body.replace(/(\b\d+(?:[.,]\d+)?\b)/, '<span class="wc-insight-card__key">$1</span>');
    const cls = ['wc-insight-card', `wc-insight-card--${cat}`, `wc-insight-card--${layout[i] || 'md'}`];
    return `
      <article class="${cls.join(' ')}" data-reveal>
        <header class="wc-insight-card__head"><span class="mono-label">${numLabel}</span></header>
        <h3 class="wc-insight-card__title">${title}</h3>
        <p class="wc-insight-card__body">${bodyWithKey}</p>
      </article>`;
  }).join('');
  revealInjected(host);
}

/* ────────────────────────────────────────────────────────────────────────── */
/* [18] Bolão local (localStorage key: wc-bolao)                                */
/* ────────────────────────────────────────────────────────────────────────── */

interface Pick { golsA?: number; golsB?: number }
type BolaoStore = Record<string, Pick>;

function readBolao(): BolaoStore {
  try { const raw = localStorage.getItem(LS_BOLAO); if (!raw) return {}; const o = JSON.parse(raw); return (o && typeof o === 'object') ? o : {}; } catch { return {}; }
}
function writeBolao(data: BolaoStore): void { try { localStorage.setItem(LS_BOLAO, JSON.stringify(data)); } catch { /* ignore */ } }

function computeBolaoPoints(pick: Pick, ft: number[] | null): number {
  if (!ft || !pick) return 0;
  const ga = Number(pick.golsA), gb = Number(pick.golsB);
  if (isNaN(ga) || isNaN(gb)) return 0;
  if (ga === ft[0] && gb === ft[1]) return 3;
  const pw = ga > gb ? 1 : (gb > ga ? 2 : 0);
  const rw = ft[0] > ft[1] ? 1 : (ft[1] > ft[0] ? 2 : 0);
  return pw === rw ? 1 : 0;
}

export function renderBolao(data: PartidasPayload | null): void {
  const list = $('wc-bolao-list'), resetBtn = $('wc-bolao-reset');
  if (!list) return;
  if (!Array.isArray(data?.matches)) {
    list.innerHTML = '<li class="wc-error mono-label">bolão indisponível</li>';
    return;
  }
  const matches = data!.matches!;
  if (!WC_STATE.matches.length) WC_STATE.matches = matches;
  const todayIso = new Date().toISOString().slice(0, 10);
  const picks = readBolao();

  const upcoming = matches
    .filter((m) => (m.status === 'today' || m.status === 'scheduled') && (m.date || '') >= todayIso)
    .sort((a, b) => `${a.date} ${a.time || ''}`.localeCompare(`${b.date} ${b.time || ''}`))
    .slice(0, 5);
  const finishedWithPick = matches.filter((m) => (m.status === 'finished' || (m.score && m.score.ft)) && picks[String(m.num)]);
  const allToShow = upcoming.concat(finishedWithPick.filter((m) => !upcoming.find((u) => u.num === m.num)));

  if (!allToShow.length) {
    list.innerHTML = '<li class="wc-loading mono-label">nenhum jogo disponível para palpite</li>';
    renderBolaoScore(matches);
    return;
  }
  list.innerHTML = allToShow.map((m) => bolaoItemHtml(m, picks)).join('');

  list.querySelectorAll<HTMLButtonElement>('.wc-bolao-submit').forEach((btn) => { btn.onclick = () => onBolaoSubmit(btn, matches); });
  if (resetBtn) (resetBtn as HTMLButtonElement).onclick = () => {
    if (Object.keys(readBolao()).length === 0) return;
    if (!window.confirm('Apagar todos os seus palpites?')) return;
    writeBolao({}); renderBolao(data);
  };
  renderBolaoScore(matches);
}

function bolaoItemHtml(m: Match, picks: BolaoStore): string {
  const isToday = m.status === 'today';
  const isFinished = m.status === 'finished' || !!(m.score && m.score.ft);
  const cls = ['wc-bolao-item'];
  if (isToday) cls.push('is-today');
  if (isFinished) cls.push('is-finished');

  const t1 = m.team1 || {}, t2 = m.team2 || {};
  const ft = m.score && Array.isArray(m.score.ft) && m.score.ft.length === 2 ? m.score.ft : null;
  const isPh1 = !t1.name || t1.name === 'A definir';
  const isPh2 = !t2.name || t2.name === 'A definir';
  const pick = picks[String(m.num)] || {};
  const hasPick = typeof pick.golsA === 'number' || typeof pick.golsB === 'number';

  let resultHtml = '', resultCls = '';
  if (isFinished && hasPick) {
    const pts = computeBolaoPoints(pick, ft);
    if (pts === 3) { resultHtml = 'acerto exato · +3 pts'; resultCls = 'wc-bolao-result--exact'; }
    else if (pts === 1) { resultHtml = 'vencedor certo · +1 pt'; resultCls = 'wc-bolao-result--winner'; }
    else resultHtml = 'errou · 0 pts';
  } else if (isFinished && !hasPick) resultHtml = 'sem palpite';

  const inputs = isFinished
    ? `<div class="wc-bolao-result ${resultCls}">${resultHtml}</div>`
    : `
      <div class="wc-bolao-inputs">
        <input type="number" min="0" max="30" class="wc-bolao-input" data-side="a" data-match="${m.num}" value="${pick.golsA != null ? pick.golsA : ''}" aria-label="Gols ${esc(t1.name || 'time A')}">
        <span class="wc-bolao-input-sep">×</span>
        <input type="number" min="0" max="30" class="wc-bolao-input" data-side="b" data-match="${m.num}" value="${pick.golsB != null ? pick.golsB : ''}" aria-label="Gols ${esc(t2.name || 'time B')}">
      </div>
      <button type="button" class="wc-bolao-submit" data-match="${m.num}">Palpitar</button>`;

  const dateTxt = shortDate(m.date), timeTxt = m.time ? esc(m.time) : '', roundTxt = m.round ? esc(m.round) : '';
  return `
    <li class="${cls.join(' ')}" data-match-num="${m.num}">
      <div class="wc-bolao-team">${flagHtml(t1.flag)}<span class="wc-bolao-team__name ${isPh1 ? 'wc-bolao-team__name--placeholder' : ''}">${esc(t1.name || 'A definir')}</span></div>
      <div class="wc-bolao-mid">${inputs}</div>
      <div class="wc-bolao-team wc-bolao-team--right">${flagHtml(t2.flag)}<span class="wc-bolao-team__name ${isPh2 ? 'wc-bolao-team__name--placeholder' : ''}">${esc(t2.name || 'A definir')}</span></div>
      <div class="wc-bolao-meta"><span>${roundTxt}</span><span>${dateTxt}${timeTxt ? ' · ' + timeTxt : ''}</span></div>
    </li>`;
}

function onBolaoSubmit(btn: HTMLButtonElement, matches: Match[]): void {
  const matchNum = btn.dataset.match;
  const item = btn.closest('.wc-bolao-item');
  if (!item || !matchNum) return;
  const inputA = item.querySelector<HTMLInputElement>('.wc-bolao-input[data-side="a"]');
  const inputB = item.querySelector<HTMLInputElement>('.wc-bolao-input[data-side="b"]');
  if (!inputA || !inputB) return;
  const ga = parseInt(inputA.value, 10), gb = parseInt(inputB.value, 10);
  if (isNaN(ga) || isNaN(gb) || ga < 0 || gb < 0) { inputA.focus(); inputA.style.borderColor = 'var(--wc-live)'; return; }
  const picks = readBolao();
  picks[matchNum] = { golsA: ga, golsB: gb };
  writeBolao(picks);
  btn.textContent = '✓ salvo'; btn.disabled = true;
  setTimeout(() => { btn.textContent = 'atualizar'; btn.disabled = false; }, 1200);
  renderBolaoScore(matches);
}

function renderBolaoScore(matches: Match[]): void {
  const totalEl = $('wc-bolao-total'), listEl = $('wc-bolao-score-list');
  if (!totalEl || !listEl) return;
  const picks = readBolao();
  const computed = Object.keys(picks).map((numStr) => {
    const m = matches.find((mm) => String(mm.num) === String(numStr));
    if (!m) return null;
    const ft = m.score && Array.isArray(m.score.ft) && m.score.ft.length === 2 ? m.score.ft : null;
    const isFinished = m.status === 'finished' || !!ft;
    if (!isFinished) return null;
    return { num: Number(numStr), match: m, pick: picks[numStr], pts: computeBolaoPoints(picks[numStr], ft), ft };
  }).filter(Boolean) as { num: number; match: Match; pick: Pick; pts: number; ft: number[] | null }[];

  totalEl.textContent = String(computed.reduce((acc, r) => acc + r.pts, 0));
  if (!computed.length) { listEl.innerHTML = '<li class="wc-loading mono-label">sem palpites computados ainda</li>'; return; }

  listEl.innerHTML = computed.sort((a, b) => b.pts - a.pts).map((r) => {
    const ptsCls = r.pts === 3 ? 'wc-bolao-score__pts--exact' : r.pts === 1 ? 'wc-bolao-score__pts--winner' : '';
    const t1 = r.match.team1 || {}, t2 = r.match.team2 || {};
    const name = `${t1.code || t1.name || '?'} v ${t2.code || t2.name || '?'}`;
    const pick = `${r.pick.golsA}×${r.pick.golsB}`;
    const real = r.ft ? `${r.ft[0]}×${r.ft[1]}` : '—';
    return `<li class="wc-bolao-score__row"><span>${esc(name)}</span><span title="seu palpite / placar real">${esc(pick)} / ${real}</span><span class="wc-bolao-score__pts ${ptsCls}">+${r.pts}</span></li>`;
  }).join('');
}

/* ────────────────────────────────────────────────────────────────────────── */
/* [16] Quem é o craque? (localStorage key: wc-craque-votes)                    */
/* ────────────────────────────────────────────────────────────────────────── */

interface VoteRec { wins: number; losses: number; matches: number }
type VoteStore = Record<string, VoteRec>;

function readVotes(): VoteStore {
  try { const raw = localStorage.getItem(LS_CRAQUE); if (!raw) return {}; const o = JSON.parse(raw); return (o && typeof o === 'object') ? o : {}; } catch { return {}; }
}
function writeVotes(v: VoteStore): void { try { localStorage.setItem(LS_CRAQUE, JSON.stringify(v)); } catch { /* ignore */ } }

function vote(winnerId: string, loserId: string): void {
  const votes = readVotes();
  const ensure = (id: string): VoteRec => (votes[id] ||= { wins: 0, losses: 0, matches: 0 });
  ensure(winnerId).wins++; ensure(winnerId).matches++;
  ensure(loserId).losses++; ensure(loserId).matches++;
  writeVotes(votes);
}

function pickTwoPlayers(players: GamePlayer[]): [GamePlayer, GamePlayer] | null {
  const eligible = players.filter((p) => p && p.id && p.name);
  if (eligible.length < 2) return null;
  const a = eligible[Math.floor(Math.random() * eligible.length)];
  let b = eligible[Math.floor(Math.random() * eligible.length)];
  let guard = 0;
  while (b.id === a.id && guard < 20) { b = eligible[Math.floor(Math.random() * eligible.length)]; guard++; }
  if (b.id === a.id) return null;
  return Math.random() < 0.5 ? [a, b] : [b, a];
}

function playerCardHtml(p: GamePlayer, side: string): string {
  const team = p.team || {};
  const flagCell = team.flag
    ? `<span class="wc-player-card__flag" aria-hidden="true">${esc(team.flag)}</span>`
    : '<span class="wc-player-card__flag wc-flag--empty" aria-hidden="true">⚽</span>';
  const posMap: Record<string, string> = { FW: 'Atacante', MF: 'Meia', DF: 'Zagueiro', GK: 'Goleiro' };
  const pos = posMap[p.position || ''] || p.position || '';
  return `
    <button type="button" class="wc-player-card" data-side="${side}" data-id="${esc(p.id)}">
      ${flagCell}
      <span class="wc-player-card__name">${esc(p.name)}</span>
      <span class="wc-player-card__meta">
        <span>${esc(team.name || '')}${team.code ? ' · ' + esc(team.code) : ''}</span>
        ${pos ? `<span>${esc(pos)}${p.goals != null ? ' · ' + p.goals + ' gol(s)' : ''}</span>` : ''}
      </span>
      <span class="wc-player-card__stat">
        <span class="wc-player-card__goals">${p.goals != null ? p.goals : '—'}</span>
        <span class="wc-player-card__goals-label">gols na Copa</span>
      </span>
      <span class="wc-player-card__cta">▸ votar neste jogador</span>
    </button>`;
}

function renderDuel(entering: boolean): void {
  const host = $('wc-game-duel');
  if (!host) return;
  if (!GAME.players.length) { host.innerHTML = '<p class="wc-game__empty">jogadores indisponíveis</p>'; return; }
  const pair = pickTwoPlayers(GAME.players);
  if (!pair) { host.innerHTML = '<p class="wc-game__empty">Não há jogadores suficientes para o duelo.</p>'; return; }
  GAME.current = pair;
  host.classList.toggle('is-entering', !!entering);
  host.innerHTML = playerCardHtml(pair[0], 'a') + playerCardHtml(pair[1], 'b');
  if (entering) setTimeout(() => host.classList.remove('is-entering'), 400);
  host.querySelectorAll<HTMLButtonElement>('.wc-player-card').forEach((btn) => {
    btn.onclick = () => onPlayerVote(btn);
    btn.onkeydown = (e) => { const k = (e as KeyboardEvent).key; if (k === 'Enter' || k === ' ') { e.preventDefault(); onPlayerVote(btn); } };
  });
}

function onPlayerVote(btn: HTMLButtonElement): void {
  const winnerId = btn.dataset.id || '';
  const loser = GAME.current && GAME.current.find((p) => p.id !== winnerId);
  if (!loser) return;
  const host = $('wc-game-duel');
  host?.classList.add('is-voting');
  const next = (): void => {
    vote(winnerId, loser.id!);
    host?.classList.remove('is-voting');
    renderDuel(true);
    const modal = $('wc-ranking-modal');
    if (modal && !modal.hidden) renderLocalRanking();
  };
  if (reduced()) next(); else setTimeout(next, 260);
}

function renderLocalRanking(): void {
  const list = $('wc-ranking-list');
  if (!list) return;
  const votes = readVotes();
  const ids = Object.keys(votes).filter((id) => votes[id].matches > 0);
  const rows = ids.map((id) => {
    const v = votes[id];
    const player = GAME.players.find((p) => p.id === id);
    return {
      id, name: player ? player.name! : id,
      team: player && player.team ? player.team : null,
      wins: v.wins, losses: v.losses, matches: v.matches,
      winrate: v.matches > 0 ? v.wins / v.matches : 0,
    };
  }).sort((a, b) => (b.winrate - a.winrate) || (b.matches - a.matches)).slice(0, 10);

  if (!rows.length) { list.innerHTML = '<li class="wc-loading mono-label">0 votos — comece a jogar!</li>'; return; }
  list.innerHTML = rows.map((r, i) => {
    const flag = r.team && r.team.flag ? esc(r.team.flag) : '';
    const teamCode = r.team && r.team.code ? esc(r.team.code) : '';
    const flagCell = flag ? `<span class="wc-prob-row__flag" aria-hidden="true" style="font-size:var(--text-lg)">${flag}</span>` : '';
    return `
      <li class="wc-ranking-row">
        <span class="wc-ranking-row__rank">${i + 1}</span>
        <span class="wc-ranking-row__name">${flagCell}<span class="wc-ranking-row__name-text">${esc(r.name)}</span></span>
        <span class="wc-ranking-row__team">${teamCode} · ${r.wins}V-${r.losses}D</span>
        <span class="wc-ranking-row__winrate">${(r.winrate * 100).toFixed(0)}%</span>
      </li>`;
  }).join('');
}

export function setupGame(data: JogadoresPayload | null): void {
  const host = $('wc-game-duel');
  if (!Array.isArray(data?.players)) { if (host) host.innerHTML = '<p class="wc-game__empty">jogadores indisponíveis</p>'; return; }
  GAME.players = data!.players!.filter((p) => p && p.id && p.name && (p.goals || 0) >= 1);
  renderDuel(false);

  const skip = $('wc-game-skip'); if (skip) (skip as HTMLButtonElement).onclick = () => renderDuel(true);
  const rankingBtn = $('wc-game-ranking') as HTMLButtonElement | null;
  const rankingModal = $('wc-ranking-modal');
  const openModal = (): void => {
    if (!rankingModal) return;
    renderLocalRanking();
    rankingModal.hidden = false;
    document.body.style.overflow = 'hidden';
    const close = rankingModal.querySelector<HTMLElement>('[data-close-modal]');
    setTimeout(() => close?.focus({ preventScroll: true }), 30);
  };
  const closeModal = (): void => {
    if (!rankingModal) return;
    rankingModal.hidden = true;
    document.body.style.overflow = '';
    rankingBtn?.focus({ preventScroll: true });
  };
  if (rankingBtn) rankingBtn.onclick = openModal;
  if (rankingModal) {
    rankingModal.querySelectorAll<HTMLElement>('[data-close-modal]').forEach((el) => { el.onclick = closeModal; });
    rankingModal.onkeydown = (e) => {
      const ev = e as KeyboardEvent;
      if (ev.key === 'Escape') { closeModal(); return; }
      if (ev.key === 'Tab') trapTab(ev, rankingModal);
    };
  }
  const resetBtn = $('wc-ranking-reset'); if (resetBtn) (resetBtn as HTMLButtonElement).onclick = () => {
    if (Object.keys(readVotes()).length === 0) return;
    if (window.confirm('Apagar todos os seus votos locais? Esta ação não pode ser desfeita.')) { writeVotes({}); renderLocalRanking(); }
  };
}

/* ────────────────────────────────────────────────────────────────────────── */
/* Deep stats [04/05/06] — shot compare, pass compare, momentum line           */
/* Call setupDeepStats(deepstats) once; it populates the 3 selects and renders  */
/* the featured match. Selecting a match re-renders all three.                  */
/* ────────────────────────────────────────────────────────────────────────── */

function statHeadHtml(home: { name?: string; code?: string; flag?: string }, away: { name?: string; code?: string; flag?: string }): string {
  const homeName = esc(home.name || home.code || 'Casa');
  const awayName = esc(away.name || away.code || 'Fora');
  return `
    <div class="wc-stat-compare__head">
      <span class="wc-stat-compare__team"><span class="wc-flag" aria-hidden="true">${esc(home.flag || '🏳️')}</span><span class="wc-stat-compare__team-name">${homeName}</span></span>
      <span class="wc-stat-compare__team wc-stat-compare__team--right"><span class="wc-stat-compare__team-name">${awayName}</span><span class="wc-flag" aria-hidden="true">${esc(away.flag || '🏳️')}</span></span>
    </div>`;
}

function statRowHtml(label: string, homeVal: string, awayVal: string, homeFlex: number, awayFlex: number): string {
  const hv = Math.max(0, num(homeFlex)), av = Math.max(0, num(awayFlex));
  const total = hv + av;
  const homePct = total > 0 ? (hv / total) * 100 : 50;
  const awayPct = total > 0 ? (av / total) * 100 : 50;
  return `
    <div class="wc-stat-row">
      <span class="wc-stat-row__home">${homeVal}</span>
      <div class="wc-stat-row__bar" aria-hidden="true">
        <span class="wc-stat-row__bar-home" style="width:${homePct.toFixed(2)}%"></span>
        <span class="wc-stat-row__bar-away" style="width:${awayPct.toFixed(2)}%"></span>
      </div>
      <span class="wc-stat-row__away">${awayVal}</span>
      <span class="wc-stat-row__label">${esc(label)}</span>
    </div>`;
}

function statSubheadHtml(label: string): string { return `<div class="wc-stat-subhead mono-label">${esc(label)}</div>`; }

function rowFromKey<T extends Record<string, unknown>>(home: T, away: T, key: keyof T, label: string, opts: { pct?: boolean; dec?: number; hideZero?: boolean } = {}): string {
  if (!(key in home) && !(key in away)) return '';
  const hv = num(home[key]), av = num(away[key]);
  if (opts.hideZero && hv === 0 && av === 0) return '';
  const fmt = opts.pct ? (v: number) => fmtPct(v, opts.dec == null ? 0 : opts.dec) : fmtInt;
  return statRowHtml(label, fmt(hv), fmt(av), hv, av);
}

function unavailable(host: HTMLElement | null, errId: string, msg: string): void {
  if (host) host.innerHTML = `<p class="wc-loading mono-label" style="padding:var(--space-5)">${esc(msg)}</p>`;
  const err = $(errId); if (err) err.hidden = false;
}

function renderShotStats(): void {
  const host = $('wc-shotstats-host'), err = $('wc-shotstats-error');
  if (!host) return;
  if (err) err.hidden = true;
  const m = _deep?.shot_stats?.matches?.[_deepSelectedId || ''];
  if (!m || !m.home || !m.away) { unavailable(host, 'wc-shotstats-error', 'Estatísticas de finalização indisponíveis para esta partida.'); return; }
  const home = m.home, away = m.away;
  const homeAcc = 'on_target_pct' in home ? num(home.on_target_pct) : (num(home.shots) > 0 ? (num(home.on_target) / num(home.shots)) * 100 : 0);
  const awayAcc = 'on_target_pct' in away ? num(away.on_target_pct) : (num(away.shots) > 0 ? (num(away.on_target) / num(away.shots)) * 100 : 0);
  const homeConv = num(home.shots) > 0 ? (num(home.goals) / num(home.shots)) * 100 : 0;
  const awayConv = num(away.shots) > 0 ? (num(away.goals) / num(away.shots)) * 100 : 0;
  const rows = [
    statRowHtml('Chutes', fmtInt(home.shots), fmtInt(away.shots), num(home.shots), num(away.shots)),
    statRowHtml('No alvo', fmtInt(home.on_target), fmtInt(away.on_target), num(home.on_target), num(away.on_target)),
    statRowHtml('No alvo %', fmtPct(homeAcc, 0), fmtPct(awayAcc, 0), homeAcc, awayAcc),
    statRowHtml('Bloqueados', fmtInt(home.blocked), fmtInt(away.blocked), num(home.blocked), num(away.blocked)),
    statRowHtml('Gols', fmtInt(home.goals), fmtInt(away.goals), num(home.goals), num(away.goals)),
    statRowHtml('Aproveitamento', fmtPct(homeConv, 0), fmtPct(awayConv, 0), homeConv, awayConv),
  ].join('');
  host.innerHTML = statHeadHtml(home, away) + `<div class="wc-stat-rows">${rows}</div>` + `<span class="wc-stat-compare__source mono-label">fonte: ${esc(m.source || 'ESPN')}</span>`;
  revealInjected(host);
  host.querySelectorAll<HTMLElement>('.wc-stat-row__bar-home, .wc-stat-row__bar-away').forEach((b) => b.classList.add('is-visible'));
}

function renderPassStats(): void {
  const host = $('wc-passstats-host'), err = $('wc-passstats-error');
  if (!host) return;
  if (err) err.hidden = true;
  const m = _deep?.pass_stats?.matches?.[_deepSelectedId || ''];
  if (!m || !m.home || !m.away) { unavailable(host, 'wc-passstats-error', 'Estatísticas de passes indisponíveis para esta partida.'); return; }
  const home = m.home, away = m.away;
  const buildRows = [
    statRowHtml('Posse %', fmtPct(home.possession, 1), fmtPct(away.possession, 1), num(home.possession), num(away.possession)),
    statRowHtml('Passes', fmtInt(home.passes), fmtInt(away.passes), num(home.passes), num(away.passes)),
    statRowHtml('Precisão %', fmtPct(home.pass_pct, 1), fmtPct(away.pass_pct, 1), num(home.pass_pct), num(away.pass_pct)),
    statRowHtml('Cruzamentos', fmtInt(home.crosses), fmtInt(away.crosses), num(home.crosses), num(away.crosses)),
    statRowHtml('Bolas longas', fmtInt(home.long_balls), fmtInt(away.long_balls), num(home.long_balls), num(away.long_balls)),
    rowFromKey(home as Record<string, unknown>, away as Record<string, unknown>, 'corners', 'Escanteios'),
  ].filter(Boolean).join('');
  const defRows = [
    rowFromKey(home as Record<string, unknown>, away as Record<string, unknown>, 'tackles', 'Desarmes'),
    rowFromKey(home as Record<string, unknown>, away as Record<string, unknown>, 'interceptions', 'Interceptações'),
    rowFromKey(home as Record<string, unknown>, away as Record<string, unknown>, 'clearances', 'Cortes'),
    rowFromKey(home as Record<string, unknown>, away as Record<string, unknown>, 'saves', 'Defesas do goleiro'),
    rowFromKey(home as Record<string, unknown>, away as Record<string, unknown>, 'offsides', 'Impedimentos'),
    rowFromKey(home as Record<string, unknown>, away as Record<string, unknown>, 'fouls', 'Faltas'),
    rowFromKey(home as Record<string, unknown>, away as Record<string, unknown>, 'yellow_cards', 'Cartões amarelos'),
    rowFromKey(home as Record<string, unknown>, away as Record<string, unknown>, 'red_cards', 'Cartões vermelhos', { hideZero: true }),
  ].filter(Boolean).join('');
  const rows = buildRows + (defRows ? statSubheadHtml('Defesa & disciplina') + defRows : '');
  host.innerHTML = statHeadHtml(home, away) + `<div class="wc-stat-rows">${rows}</div>` + `<span class="wc-stat-compare__source mono-label">fonte: ${esc(m.source || 'ESPN')}</span>`;
  revealInjected(host);
  host.querySelectorAll<HTMLElement>('.wc-stat-row__bar-home, .wc-stat-row__bar-away').forEach((b) => b.classList.add('is-visible'));
}

/** chart-momentum (Chart.js line) → lineChart(). Goal-pulse markers are dropped
 *  (they required Chart.js pixel scales); the SVG lineChart has its own hover. */
function renderMomentum(): void {
  const box = $('wc-chart-momentum'), err = $('wc-flow-error');
  if (!box) return;
  const data = _deep?.momentum?.matches?.[_deepSelectedId || ''];
  const homeCum = data?.home?.cum || data?.home?.xg_cum;
  const awayCum = data?.away?.cum || data?.away?.xg_cum;
  if (!data || !Array.isArray(data.labels) || !Array.isArray(homeCum) || !Array.isArray(awayCum)) {
    if (err) err.hidden = false;
    box.innerHTML = '<p class="wc-error mono-label">série temporal indisponível</p>';
    return;
  }
  if (err) err.hidden = true;
  const labels = data.labels;
  const isGoals = data.metric === 'goals';
  const metricLabel = data.metric_label || (isGoals ? 'Gols acumulados' : 'xG acumulado');
  const homeLbl = data.home?.code || data.home?.name || 'Casa';
  const awayLbl = data.away?.code || data.away?.name || 'Fora';
  const fmtY = isGoals ? (v: number) => String(Math.round(v)) : (v: number) => v.toFixed(2);
  lineChart(box, {
    ariaLabel: `Trajetória do jogo minuto a minuto: ${metricLabel}, ${homeLbl} vs ${awayLbl}`,
    xTitle: 'minuto de jogo',
    yTitle: metricLabel,
    valueFmt: fmtY,
    xFmt: (x) => `minuto ${x}'`,
    series: [
      { label: homeLbl, color: readToken('--wc-field-ink', '#0B6B2E'), points: homeCum.map((v, i) => ({ x: num(labels[i]), y: num(v) })) },
      { label: awayLbl, color: readToken('--wc-gold-ink', '#8A5A06'), points: awayCum.map((v, i) => ({ x: num(labels[i]), y: num(v) })) },
    ],
  });
}

/** Populate the 3 match selects and render the featured match. Idempotent. */
export function setupDeepStats(data: DeepStatsPayload | null): void {
  const selects = Array.from(document.querySelectorAll<HTMLSelectElement>('.wc-match-select'));
  if (!data || !Array.isArray(data.match_list) || !data.match_list.length) {
    // Fail-soft: mark the three sections unavailable.
    unavailable($('wc-shotstats-host'), 'wc-shotstats-error', 'Estatísticas de finalização indisponíveis para esta partida.');
    unavailable($('wc-passstats-host'), 'wc-passstats-error', 'Estatísticas de passes indisponíveis para esta partida.');
    const err = $('wc-flow-error'); if (err) err.hidden = false;
    return;
  }
  _deep = data;
  // Default: 1ª partida do match_list que REALMENTE tenha stats ESPN (o
  // featured_id costuma apontar p/ o próximo jogo, ainda sem dados → seção
  // "indisponível" no load). Cai para featured_id / 1º item se nenhuma tiver.
  const shotM = data.shot_stats?.matches ?? {};
  const passM = data.pass_stats?.matches ?? {};
  const firstWithData = data.match_list.find(
    (m) => m.id && (m.id in shotM || m.id in passM),
  );
  _deepSelectedId = (firstWithData?.id) || data.featured_id || data.match_list[0].id || null;

  const options = data.match_list.map((m) => `<option value="${esc(m.id)}"${m.id === _deepSelectedId ? ' selected' : ''}>${esc(m.label)}</option>`).join('');
  selects.forEach((sel) => {
    sel.innerHTML = options;
    if (_deepSelectedId) sel.value = _deepSelectedId;
    sel.onchange = () => onDeepMatchChange(sel.value);
  });

  renderShotStats();
  renderPassStats();
  renderMomentum();
}

function onDeepMatchChange(matchId: string): void {
  if (!matchId) return;
  _deepSelectedId = matchId;
  document.querySelectorAll<HTMLSelectElement>('.wc-match-select').forEach((sel) => { sel.value = matchId; });
  try { renderShotStats(); } catch (e) { console.error('[cap1] renderShotStats:', e); }
  try { renderPassStats(); } catch (e) { console.error('[cap1] renderPassStats:', e); }
  try { renderMomentum(); } catch (e) { console.error('[cap1] renderMomentum:', e); }
}
