/*
 * World Cup Dashboard — classics.js
 * ---------------------------------------------------------------------------
 * Seção [07] · Clássicos 2022 — análise avançada por partida:
 *   Posse de bola %, Precisão de passe % e PPDA (intensidade de pressão),
 *   cada um com tabela Total / 1º tempo / 2º tempo + gráfico de linha por
 *   intervalo de 15 min (casa vs. fora). Fiel ao enquadramento das
 *   transmissões, com número REAL do dado de evento aberto do StatsBomb.
 *
 * Módulo ISOLADO (mesmo padrão de deepstats.js): IIFE, sem imports.
 * Fonte: data/classics_2022.json (gerado por
 * ingestion_worldcup/fetch_classics_statsbomb.py). Zero LLM em runtime.
 *
 * ---------------------------------------------------------------------------
 * SCHEMA esperado de data/classics_2022.json:
 * ---------------------------------------------------------------------------
 * {
 *   "featured_id": "3869685",
 *   "match_list": [ { "id","label","date","stage","stage_rank" } ],
 *   "matches": {
 *     "<id>": {
 *       "id","label","date","stage",
 *       "home": { "name","code","flag" }, "away": { ... },
 *       "labels": ["1-15","16-30",...],
 *       "possession":   { "labels",[series:{home:[],away:[]}],
 *                         "total":{home,away},"first":{...},"second":{...} },
 *       "pass_accuracy":{ ...igual... },
 *       "ppda":         { ...igual... }
 *     }
 *   }
 * }
 * ---------------------------------------------------------------------------
 */

'use strict';

(function () {

  const $  = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  const prefersReducedMotion = () =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function token(name, fallback) {
    try {
      const v = getComputedStyle(document.documentElement)
        .getPropertyValue(name).trim();
      return v || fallback;
    } catch (e) { return fallback; }
  }

  async function loadJSON(name) {
    try {
      const res = await fetch(`data/${name}.json`, { cache: 'no-cache' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return { ok: true, data: await res.json() };
    } catch (e) {
      console.warn(`[WCClassics] fetch data/${name}.json falhou:`, e);
      return { ok: false, error: e, data: null };
    }
  }

  const C = {
    paper:    token('--paper-card', '#FFFFFF'),
    ink:      token('--ink', '#0A0A0A'),
    inkSoft:  token('--ink-soft', '#545454'),
    inkFaint: token('--ink-faint', '#6C6C6C'),
    line:     token('--line', 'rgba(10,10,10,0.12)'),
    fieldInk: token('--wc-field-ink', '#0B6B2E'),
    goldInk:  token('--wc-gold-ink', '#8A5A06'),
  };

  // Métricas renderizadas (ordem = ordem na página).
  const METRICS = [
    { key: 'possession',    host: 'poss',
      title: 'Posse de bola',   unit: '%', decimals: 1,
      // maior é melhor (destaque em ouro no maior valor)
      betterHigh: true },
    { key: 'pass_accuracy', host: 'pass',
      title: 'Precisão de passe', unit: '%', decimals: 1,
      betterHigh: true },
    { key: 'ppda',          host: 'ppda',
      title: 'PPDA (pressão)',  unit: '', decimals: 1,
      // menor PPDA = pressão mais intensa
      betterHigh: false },
  ];

  let _data = null;
  let _selectedMatchId = null;
  let _charts = {};   // host → Chart instance

  /* ─── Formatação ─────────────────────────────────────────── */
  function fmt(v, decimals, unit) {
    if (v == null || Number.isNaN(Number(v))) return '—';
    const s = Number(v).toFixed(decimals).replace('.', ',');
    return unit ? s + unit : s;
  }

  /* ─── Seletor de partida (agrupado por fase) ─────────────── */
  function populateSelector(matchList, featuredId) {
    const sel = $('#wc-classics-select');
    if (!sel || !Array.isArray(matchList) || !matchList.length) return;

    // Agrupa por fase preservando a ordem já vinda do pipeline.
    const groups = new Map();
    matchList.forEach(m => {
      const g = m.stage || 'Partidas';
      if (!groups.has(g)) groups.set(g, []);
      groups.get(g).push(m);
    });
    const STAGE_PT = {
      'Final': 'Final', '3rd Place Final': 'Disputa de 3º lugar',
      'Semi-finals': 'Semifinais', 'Quarter-finals': 'Quartas de final',
      'Round of 16': 'Oitavas de final', 'Group Stage': 'Fase de grupos',
    };
    let html = '';
    for (const [stage, items] of groups) {
      html += `<optgroup label="${escapeHtml(STAGE_PT[stage] || stage)}">`;
      html += items.map(m =>
        `<option value="${escapeHtml(m.id)}"${m.id === featuredId ? ' selected' : ''}>${escapeHtml(m.label)}</option>`
      ).join('');
      html += `</optgroup>`;
    }
    sel.innerHTML = html;
    sel.value = featuredId;
    sel.removeEventListener('change', sel._wcClassicsHandler);
    const handler = () => onMatchChange(sel.value);
    sel._wcClassicsHandler = handler;
    sel.addEventListener('change', handler);
  }

  function onMatchChange(matchId) {
    if (!matchId) return;
    _selectedMatchId = matchId;
    renderAll();
  }

  /* ─── Tabela Total / 1º / 2º ─────────────────────────────── */
  function tableHtml(match, block, metric) {
    const h = match.home, a = match.away;
    const cell = (side, which) => {
      const v = block[which] ? block[which][side] : null;
      return fmt(v, metric.decimals, metric.unit);
    };
    // Destaque (ouro) no melhor da coluna Total.
    const ht = block.total ? block.total.home : null;
    const at = block.total ? block.total.away : null;
    let homeLead = false, awayLead = false;
    if (ht != null && at != null && ht !== at) {
      const homeBetter = metric.betterHigh ? ht > at : ht < at;
      homeLead = homeBetter; awayLead = !homeBetter;
    }
    const row = (side, team, lead) => `
      <tr${lead ? ' class="wc-cl-table__row--lead"' : ''}>
        <th scope="row" class="wc-cl-table__team">
          <span class="wc-flag" aria-hidden="true">${escapeHtml(team.flag || '🏳️')}</span>
          <span>${escapeHtml(team.name || team.code || '')}</span>
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
          ${row('home', h, homeLead)}
          ${row('away', a, awayLead)}
        </tbody>
      </table>`;
  }

  /* ─── Gráfico de linha por intervalo (Chart.js) ──────────── */
  function renderChart(canvasId, match, block, metric) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    if (_charts[canvasId]) { _charts[canvasId].destroy(); _charts[canvasId] = null; }
    if (typeof Chart === 'undefined') return;

    Chart.defaults.font.family = token('--font-mono', 'IBM Plex Mono, monospace');
    Chart.defaults.font.size = 11;
    Chart.defaults.color = C.inkFaint;

    const labels = block.labels || match.labels || [];
    const homeLbl = match.home.code || match.home.name || 'Casa';
    const awayLbl = match.away.code || match.away.name || 'Fora';

    const anim = prefersReducedMotion() ? false
      : { duration: 900, easing: 'easeOutQuart' };

    _charts[canvasId] = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: homeLbl, data: block.series ? block.series.home : [],
            borderColor: C.fieldInk, backgroundColor: 'rgba(0,0,0,0)',
            borderWidth: 2, tension: 0.3, pointRadius: 2.5,
            pointBackgroundColor: C.fieldInk, spanGaps: true,
          },
          {
            label: awayLbl, data: block.series ? block.series.away : [],
            borderColor: C.goldInk, backgroundColor: 'rgba(0,0,0,0)',
            borderWidth: 2, tension: 0.3, pointRadius: 2.5,
            pointBackgroundColor: C.goldInk, spanGaps: true,
          },
        ],
      },
      options: {
        animation: anim,
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            position: 'bottom',
            labels: { boxWidth: 10, boxHeight: 10, color: C.inkSoft,
                      font: { size: 10 }, padding: 12 },
          },
          tooltip: {
            backgroundColor: C.ink, titleColor: C.paper, bodyColor: C.paper,
            padding: 10,
            callbacks: {
              title: (items) => `intervalo ${items[0].label} min`,
              label: (ctx) => {
                const v = ctx.parsed.y;
                if (v == null) return ` ${ctx.dataset.label}: —`;
                return ` ${ctx.dataset.label}: ${fmt(v, metric.decimals, metric.unit)}`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            border: { color: C.line },
            ticks: { color: C.inkFaint, font: { size: 10 } },
            title: { display: true, text: 'intervalo (min)',
                     color: C.inkFaint, font: { size: 10 } },
          },
          y: {
            beginAtZero: metric.betterHigh ? false : true,
            grid: { color: C.line },
            border: { display: false },
            ticks: { color: C.inkFaint, font: { size: 10 } },
            title: { display: true, text: metric.title + (metric.unit ? ` (${metric.unit})` : ''),
                     color: C.inkFaint, font: { size: 10 } },
          },
        },
      },
    });
  }

  /* ─── Render de uma métrica (tabela + chart) ─────────────── */
  function renderMetric(match, metric) {
    const tableHost = document.getElementById(`wc-cl-${metric.host}-table`);
    if (tableHost) tableHost.innerHTML = tableHtml(match, match[metric.key] || {}, metric);
    renderChart(`wc-cl-${metric.host}-chart`, match, match[metric.key] || {}, metric);
  }

  function renderAll() {
    const err = $('#wc-classics-error');
    const match = _data && _data.matches ? _data.matches[_selectedMatchId] : null;
    if (!match) {
      if (err) err.hidden = false;
      return;
    }
    if (err) err.hidden = true;

    // Legenda contextual (fase + placar).
    const meta = $('#wc-classics-meta');
    if (meta) {
      const STAGE_PT = {
        'Final': 'Final', '3rd Place Final': 'Disputa de 3º lugar',
        'Semi-finals': 'Semifinal', 'Quarter-finals': 'Quartas de final',
        'Round of 16': 'Oitavas de final', 'Group Stage': 'Fase de grupos',
      };
      const stage = STAGE_PT[match.stage] || match.stage || '';
      meta.textContent = `${stage} · ${match.label}`;
    }

    METRICS.forEach(m => {
      try { renderMetric(match, m); }
      catch (e) { console.error(`[WCClassics] ${m.key}:`, e); }
    });
  }

  window.WCClassics = { populateSelector, onMatchChange, renderAll,
                        _loadJSON: loadJSON };

  async function init() {
    const host = $('#wc-classics');
    if (!host) return;   // seção ausente → nada a fazer
    const result = await loadJSON('classics_2022');
    if (!result.ok || !result.data) {
      const err = $('#wc-classics-error');
      if (err) err.hidden = false;
      return;
    }
    _data = result.data;
    _selectedMatchId = _data.featured_id ||
      (Array.isArray(_data.match_list) && _data.match_list[0] &&
       _data.match_list[0].id) || null;
    if (Array.isArray(_data.match_list)) {
      populateSelector(_data.match_list, _selectedMatchId);
    }
    renderAll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
