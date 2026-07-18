/*
 * World Cup Dashboard — deepstats.js
 * ---------------------------------------------------------------------------
 * Ball-level sections [04/05/06]:
 *   04 · Finalizações       → renderShotStats(data.shot_stats.matches[id])
 *   05 · Posse e Passes     → renderPassStats(data.pass_stats.matches[id])
 *   06 · Trajetória da Bola → renderMomentum(data.momentum.matches[id])
 *
 * Módulo ISOLADO e autossuficiente (mesmo estilo do main.js: IIFE, sem
 * imports). Funciona mesmo se main.js falhar. Não toca em state de main.js.
 * Motion delegado a window.WCMotion (js/motion.js) — este módulo só orquestra
 * a chamada; se WCMotion estiver ausente, renderiza estático (sem stagger).
 *
 * Helpers DUPLICADOS de main.js (loadJSON, escapeHtml, token,
 * prefersReducedMotion, observeReveals) — intencional, para isolamento.
 *
 * ---------------------------------------------------------------------------
 * SCHEMA esperado de data/deepstats.json:
 * ---------------------------------------------------------------------------
 * {
 *   "updated_at": "...",
 *   "source": "openfootball (momentum) + ESPN (match stats)",
 *   "featured_id": "ger-cuw-2026-06-14",
 *   "match_list": [
 *     { "id": "...", "label": "...", "date": "...", "goals": 8, "has_stats": true }
 *   ],
 *   "shot_stats": {
 *     "available": true,
 *     "source": "ESPN",
 *     "matches": {
 *       "<id>": {
 *         "match": "Germany 7–1 Curaçao",
 *         "source": "ESPN",
 *         "home": { "code": "GER", "flag": "🇩🇪", "name": "Germany",
 *                   "shots": 26, "on_target": 12, "on_target_pct": 46.2,
 *                   "blocked": 8, "goals": 7 },
 *         "away": { ... }
 *       }
 *     }
 *   },
 *   "pass_stats": {
 *     "available": true,
 *     "source": "ESPN",
 *     "matches": {
 *       "<id>": {
 *         "match": "...",
 *         "home": { "code": "GER", "flag": "🇩🇪", "name": "Germany",
 *                   "possession": 65.2,
 *                   "passes": 620, "accurate_passes": 580, "pass_pct": 93.5,
 *                   "crosses": 15, "accurate_crosses": 8,
 *                   "long_balls": 40, "accurate_long_balls": 22,
 *                   "corners": 9, "offsides": 2, "saves": 3,
 *                   "tackles": 18, "effective_tackles": 12, "interceptions": 7,
 *                   "clearances": 24, "fouls": 11,
 *                   "yellow_cards": 2, "red_cards": 0 },
 *         "away": { ... }
 *       }
 *     }
 *   },
 *   "momentum": {
 *     "available": true,
 *     "metric": "goals",
 *     "metric_label": "Gols acumulados",
 *     "matches": {
 *       "<id>": {
 *         "id": "...", "label": "...", "date": "...",
 *         "total_goals": 8,
 *         "metric": "goals", "metric_label": "Gols acumulados",
 *         "labels": [0, 5, 10, ..., 90],
 *         "home": { "code": "GER", "flag": "🇩🇪", "name": "Germany",
 *                   "cum": [0, 0, 1, ...] },
 *         "away": { "code": "CUW", "flag": "🇨🇼", "name": "Curaçao",
 *                   "cum": [0, 0, 0, ...] },
 *         "goals": [ { "minute": 6, "team": "home", "player": "...", "cum": 1 } ]
 *       }
 *     }
 *   }
 * }
 * ---------------------------------------------------------------------------
 */

'use strict';

(function () {

  /* ════════════════════════════════════════════════════════
   * Helpers (duplicados de main.js — isolamento intencional)
   * ════════════════════════════════════════════════════════ */
  const $  = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  const prefersReducedMotion = () =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /** Escape HTML de strings externas (nomes de jogadores). Previne XSS. */
  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /** Lê um token CSS do :root, com fallback. */
  function token(name, fallback) {
    try {
      const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      return v || fallback;
    } catch (e) { return fallback; }
  }

  /** fetch resiliente: retorna {ok, data} | {ok:false, error}. */
  async function loadJSON(name) {
    try {
      const res = await fetch(`data/${name}.json`, { cache: 'no-cache' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return { ok: true, data };
    } catch (e) {
      console.warn(`[WCDeepStats] fetch data/${name}.json falhou:`, e);
      return { ok: false, error: e, data: null };
    }
  }

  /** Reveal de [data-reveal] via IntersectionObserver (cópia do main.js). */
  let _revealObserver = null;
  function observeReveals(root) {
    if (prefersReducedMotion()) {
      $$('[data-reveal]', root || document).forEach(el => el.classList.add('is-visible'));
      return;
    }
    if (!_revealObserver) {
      _revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            _revealObserver.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    }
    $$('[data-reveal]:not(.is-visible)', root || document).forEach(el => _revealObserver.observe(el));
  }

  /** Atalho seguro para WCMotion (fallback estático se motion.js falhar). */
  const Motion = window.WCMotion || null;

  /* ════════════════════════════════════════════════════════
   * Paleta local (mesmas cores que main.js usa nos charts)
   * ════════════════════════════════════════════════════════ */
  const C = {
    paper:     token('--paper-card', '#FFFFFF'),
    ink:       token('--ink', '#0A0A0A'),
    inkSoft:   token('--ink-soft', '#545454'),
    inkFaint:  token('--ink-faint', '#6C6C6C'),
    line:      token('--line', 'rgba(10,10,10,0.12)'),
    field:     token('--wc-field', '#2E8B2E'),
    fieldInk:  token('--wc-field-ink', '#0B6B2E'),
    fieldDim:  token('--wc-field-dim', 'rgba(46,139,46,0.08)'),
    gold:      token('--wc-gold', '#B0820D'),
    goldInk:   token('--wc-gold-ink', '#8A5A06'),
  };

  /* ════════════════════════════════════════════════════════
   * Estado compartilhado entre as 3 seções
   * ════════════════════════════════════════════════════════ */
  let _data = null;
  let _selectedMatchId = null;
  let _momentumChart = null;
  let _momentumResizeTimer = null;

  /* ════════════════════════════════════════════════════════
   * Match selector (compartilhado por 04/05/06)
   * ════════════════════════════════════════════════════════ */
  function populateSelectors(matchList, featuredId) {
    if (!Array.isArray(matchList) || !matchList.length) return;
    const options = matchList.map(m =>
      `<option value="${escapeHtml(m.id)}"${m.id === featuredId ? ' selected' : ''}>${escapeHtml(m.label)}</option>`
    ).join('');
    $$('.wc-match-select').forEach(sel => {
      sel.innerHTML = options;
      sel.value = featuredId;
      // Evita duplo binding se init() rodar mais de uma vez.
      sel.removeEventListener('change', sel._wcDeepStatsHandler);
      const handler = () => onMatchChange(sel.value);
      sel._wcDeepStatsHandler = handler;
      sel.addEventListener('change', handler);
    });
  }

  function onMatchChange(matchId) {
    if (!matchId) return;
    _selectedMatchId = matchId;
    // Sincroniza todos os selects (um em cada seção).
    $$('.wc-match-select').forEach(sel => { sel.value = matchId; });
    // Re-renderiza as 3 seções — falha isolada por seção.
    try { renderShotStats(); } catch(e) { console.error('[WCDeepStats] shotStats:', e); }
    try { renderPassStats(); } catch(e) { console.error('[WCDeepStats] passStats:', e); }
    try { renderMomentum(); } catch(e) { console.error('[WCDeepStats] momentum:', e); }
  }

  /* ════════════════════════════════════════════════════════
   * Helpers de renderização de stat comparison
   * ════════════════════════════════════════════════════════ */
  function num(v) { return Number(v) || 0; }

  function fmtInt(v) {
    return num(v).toLocaleString('pt-BR');
  }

  function fmtPct(v, decimals) {
    const d = (decimals == null) ? 1 : decimals;
    return num(v).toFixed(d).replace('.', ',') + '%';
  }

  /** Escala as duas pontas de uma barra para um flex home/away proporcional.
   *  Sempre retorna valores ≥ 0. Se ambos forem 0, retorna 1/1 para a barra
   *  não colapsar. */
  function flexPair(h, a) {
    const hv = Math.max(0, num(h));
    const av = Math.max(0, num(a));
    if (hv === 0 && av === 0) return { h: 1, a: 1 };
    return { h: hv, a: av };
  }

  /** Cabeçalho com flags + nomes das duas seleções. */
  function statHeadHtml(home, away) {
    const homeName = escapeHtml(home.name || home.code || 'Casa');
    const awayName = escapeHtml(away.name || away.code || 'Fora');
    return `
      <div class="wc-stat-compare__head">
        <span class="wc-stat-compare__team">
          <span class="wc-flag" aria-hidden="true">${escapeHtml(home.flag || '🏳️')}</span>
          <span class="wc-stat-compare__team-name">${homeName}</span>
        </span>
        <span class="wc-stat-compare__team wc-stat-compare__team--right">
          <span class="wc-stat-compare__team-name">${awayName}</span>
          <span class="wc-flag" aria-hidden="true">${escapeHtml(away.flag || '🏳️')}</span>
        </span>
      </div>`;
  }

  /** Linha de estatística: home-value | barra dupla | away-value + label. */
  function statRowHtml(label, homeVal, awayVal, homeFlex, awayFlex) {
    const hv = Math.max(0, num(homeFlex));
    const av = Math.max(0, num(awayFlex));
    const total = hv + av;
    // Largura relativa em % — evita flex negativo/zero em layouts antigos.
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
        <span class="wc-stat-row__label">${escapeHtml(label)}</span>
      </div>`;
  }

  /** Sub-cabeçalho de grupo dentro da ficha (ex.: "Defesa & disciplina"). */
  function statSubheadHtml(label) {
    return `<div class="wc-stat-subhead mono-label">${escapeHtml(label)}</div>`;
  }

  /**
   * Constrói uma linha a partir de uma chave, respeitando presença do campo.
   * - Se a chave não existir em nenhum dos dois times → '' (não renderiza).
   *   Protege deepstats.json antigo/cacheado antes do próximo cron.
   * - opts.pct: formata como percentual (opts.dec casas, default 0).
   * - opts.hideZero: omite a linha se ambos os valores forem 0 (ex.: cartões).
   */
  function rowFromKey(home, away, key, label, opts) {
    opts = opts || {};
    if (!(key in home) && !(key in away)) return '';
    const hv = num(home[key]);
    const av = num(away[key]);
    if (opts.hideZero && hv === 0 && av === 0) return '';
    const fmt = opts.pct
      ? (v) => fmtPct(v, opts.dec == null ? 0 : opts.dec)
      : fmtInt;
    return statRowHtml(label, fmt(hv), fmt(av), hv, av);
  }

  /** Estado vazio amigável (não é erro — apenas sem ESPN p/ esta partida). */
  function unavailableHtml(host, errId, msg) {
    const hostEl = host;
    const errEl = document.getElementById(errId);
    if (hostEl) {
      hostEl.innerHTML = `<p class="wc-loading mono-label" style="padding:var(--space-5)">${escapeHtml(msg)}</p>`;
    }
    if (errEl) errEl.hidden = false;
  }

  /* ════════════════════════════════════════════════════════
   * [04] renderShotStats()
   * Lê _data.shot_stats.matches[_selectedMatchId]. Se não houver, exibe
   * mensagem amigável (não é erro — apenas sem ESPN p/ a partida).
   * ════════════════════════════════════════════════════════ */
  function renderShotStats() {
    const host = $('#wc-shotstats-host');
    const err  = $('#wc-shotstats-error');
    if (!host) return;
    if (err) err.hidden = true;

    if (!_data || !_data.shot_stats || !_data.shot_stats.matches) {
      unavailableHtml(host, 'wc-shotstats-error',
        'Estatísticas de finalização indisponíveis para esta partida.');
      return;
    }

    const m = _data.shot_stats.matches[_selectedMatchId];
    if (!m || !m.home || !m.away) {
      unavailableHtml(host, 'wc-shotstats-error',
        'Estatísticas de finalização indisponíveis para esta partida.');
      return;
    }

    const home = m.home;
    const away = m.away;

    // % no alvo = chutes no alvo / chutes. Usa o campo do pipeline quando
    // presente; senão deriva (compat com deepstats.json antigo).
    const homeAcc = ('on_target_pct' in home)
      ? num(home.on_target_pct)
      : (num(home.shots) > 0 ? (num(home.on_target) / num(home.shots)) * 100 : 0);
    const awayAcc = ('on_target_pct' in away)
      ? num(away.on_target_pct)
      : (num(away.shots) > 0 ? (num(away.on_target) / num(away.shots)) * 100 : 0);

    // Aproveitamento = gols / chutes * 100
    const homeConv = (num(home.shots) > 0)
      ? (num(home.goals) / num(home.shots)) * 100 : 0;
    const awayConv = (num(away.shots) > 0)
      ? (num(away.goals) / num(away.shots)) * 100 : 0;

    const rows = [
      statRowHtml('Chutes',
        fmtInt(home.shots), fmtInt(away.shots),
        home.shots, away.shots),
      statRowHtml('No alvo',
        fmtInt(home.on_target), fmtInt(away.on_target),
        home.on_target, away.on_target),
      statRowHtml('No alvo %',
        fmtPct(homeAcc, 0), fmtPct(awayAcc, 0),
        homeAcc, awayAcc),
      statRowHtml('Bloqueados',
        fmtInt(home.blocked), fmtInt(away.blocked),
        home.blocked, away.blocked),
      statRowHtml('Gols',
        fmtInt(home.goals), fmtInt(away.goals),
        home.goals, away.goals),
      statRowHtml('Aproveitamento',
        fmtPct(homeConv, 0), fmtPct(awayConv, 0),
        homeConv, awayConv),
    ].join('');

    host.innerHTML =
      statHeadHtml(home, away) +
      `<div class="wc-stat-rows">${rows}</div>` +
      `<span class="wc-stat-compare__source mono-label">fonte: ${escapeHtml(m.source || 'ESPN')}</span>`;

    // Re-observa reveal + motion de barras (se WCMotion disponível).
    observeReveals(host);
    const bars = $$('.wc-stat-row__bar-home, .wc-stat-row__bar-away', host);
    if (Motion && Motion.revealStagger && !prefersReducedMotion()) {
      Motion.revealStagger(bars, { step: 25 });
    } else {
      bars.forEach(b => b.classList.add('is-visible'));
    }
  }

  /* ════════════════════════════════════════════════════════
   * [05] renderPassStats()
   * Lê _data.pass_stats.matches[_selectedMatchId]. Mesmo padrão do 04.
   * ════════════════════════════════════════════════════════ */
  function renderPassStats() {
    const host = $('#wc-passstats-host');
    const err  = $('#wc-passstats-error');
    if (!host) return;
    if (err) err.hidden = true;

    if (!_data || !_data.pass_stats || !_data.pass_stats.matches) {
      unavailableHtml(host, 'wc-passstats-error',
        'Estatísticas de passes indisponíveis para esta partida.');
      return;
    }

    const m = _data.pass_stats.matches[_selectedMatchId];
    if (!m || !m.home || !m.away) {
      unavailableHtml(host, 'wc-passstats-error',
        'Estatísticas de passes indisponíveis para esta partida.');
      return;
    }

    const home = m.home;
    const away = m.away;

    // Grupo 1 — Posse & construção
    const buildRows = [
      statRowHtml('Posse %',
        fmtPct(home.possession, 1), fmtPct(away.possession, 1),
        home.possession, away.possession),
      statRowHtml('Passes',
        fmtInt(home.passes), fmtInt(away.passes),
        home.passes, away.passes),
      statRowHtml('Precisão %',
        fmtPct(home.pass_pct, 1), fmtPct(away.pass_pct, 1),
        home.pass_pct, away.pass_pct),
      statRowHtml('Cruzamentos',
        fmtInt(home.crosses), fmtInt(away.crosses),
        home.crosses, away.crosses),
      statRowHtml('Bolas longas',
        fmtInt(home.long_balls), fmtInt(away.long_balls),
        home.long_balls, away.long_balls),
      rowFromKey(home, away, 'corners', 'Escanteios'),
    ].filter(Boolean).join('');

    // Grupo 2 — Defesa & disciplina (campos novos; ausentes = não renderizam)
    const defRows = [
      rowFromKey(home, away, 'tackles', 'Desarmes'),
      rowFromKey(home, away, 'interceptions', 'Interceptações'),
      rowFromKey(home, away, 'clearances', 'Cortes'),
      rowFromKey(home, away, 'saves', 'Defesas do goleiro'),
      rowFromKey(home, away, 'offsides', 'Impedimentos'),
      rowFromKey(home, away, 'fouls', 'Faltas'),
      rowFromKey(home, away, 'yellow_cards', 'Cartões amarelos'),
      rowFromKey(home, away, 'red_cards', 'Cartões vermelhos', { hideZero: true }),
    ].filter(Boolean).join('');

    const rows = buildRows +
      (defRows ? statSubheadHtml('Defesa & disciplina') + defRows : '');

    host.innerHTML =
      statHeadHtml(home, away) +
      `<div class="wc-stat-rows">${rows}</div>` +
      `<span class="wc-stat-compare__source mono-label">fonte: ${escapeHtml(m.source || 'ESPN')}</span>`;

    observeReveals(host);
    const bars = $$('.wc-stat-row__bar-home, .wc-stat-row__bar-away', host);
    if (Motion && Motion.revealStagger && !prefersReducedMotion()) {
      Motion.revealStagger(bars, { step: 25 });
    } else {
      bars.forEach(b => b.classList.add('is-visible'));
    }
  }

  /* ════════════════════════════════════════════════════════
   * [06] renderMomentum()
   * Chart.js line chart (métrica acumulada por minuto) + goal pulse markers.
   * A metric label e a unidade do tooltip dependem de data.metric
   * ('goals' → gols; senão → xG). Mantém compat com schema antigo
   * (cum | xg_cum).
   * ════════════════════════════════════════════════════════ */
  function renderMomentum() {
    const canvas = $('#chart-momentum');
    const errBox = $('#wc-flow-error');
    if (!canvas) return;

    if (typeof Chart === 'undefined') {
      console.warn('[WCDeepStats] Chart.js não carregou — momentum pulado.');
      if (errBox) errBox.hidden = false;
      return;
    }

    const data = _data && _data.momentum && _data.momentum.matches
      ? _data.momentum.matches[_selectedMatchId]
      : null;

    if (!data || !Array.isArray(data.labels) ||
        !data.home || !(Array.isArray(data.home.cum) || Array.isArray(data.home.xg_cum)) ||
        !data.away || !(Array.isArray(data.away.cum) || Array.isArray(data.away.xg_cum))) {
      if (errBox) errBox.hidden = false;
      // Limpa chart anterior, se houver.
      if (_momentumChart) { _momentumChart.destroy(); _momentumChart = null; }
      const markers = $('#wc-momentum-markers');
      if (markers) markers.innerHTML = '';
      return;
    }

    if (errBox) errBox.hidden = true;

    // Defaults coerentes com Blueprint (idempotente se main.js também setar).
    Chart.defaults.font.family = token('--font-mono', 'IBM Plex Mono, monospace');
    Chart.defaults.font.size = 11;
    Chart.defaults.color = C.inkFaint;

    const labels      = data.labels;
    const homeData    = data.home.cum || data.home.xg_cum;
    const awayData    = data.away.cum || data.away.xg_cum;
    const goals       = Array.isArray(data.goals) ? data.goals : [];
    const homeLbl     = data.home.code || data.home.name || 'Casa';
    const awayLbl     = data.away.code || data.away.name || 'Fora';
    const metricLabel = data.metric_label || 'xG acumulado';
    const isGoals     = data.metric === 'goals';

    // Destruir chart anterior se existir (re-render seguro).
    if (_momentumChart) { _momentumChart.destroy(); _momentumChart = null; }

    const gridColor  = C.line;
    const ticksColor = C.inkFaint;

    const momentumAnimation = prefersReducedMotion() ? false : {
      duration: 1200,
      easing: 'easeOutQuart',
      delay: (ctx) => (ctx.type === 'data' && ctx.mode === 'default') ? ctx.dataIndex * 12 : 0
    };

    _momentumChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: `${homeLbl} · ${metricLabel}`,
            data: homeData,
            borderColor: C.fieldInk,
            backgroundColor: 'rgba(0,0,0,0)',
            borderWidth: 2,
            tension: 0.3,
            fill: false,
            pointRadius: 0,
          },
          {
            label: `${awayLbl} · ${metricLabel}`,
            data: awayData,
            borderColor: C.goldInk,
            backgroundColor: 'rgba(0,0,0,0)',
            borderWidth: 2,
            tension: 0.3,
            fill: false,
            pointRadius: 0,
          }
        ]
      },
      options: {
        animation: momentumAnimation,
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 10, boxHeight: 10,
              color: C.inkSoft,
              font: { size: 10 },
              padding: 12
            }
          },
          tooltip: {
            backgroundColor: C.ink,
            titleColor: C.paper,
            bodyColor: C.paper,
            padding: 10,
            callbacks: {
              title: (items) => `minuto ${items[0].label}'`,
              label: (ctx) => {
                const tag = ctx.dataset.label.split(' · ')[0];
                const v = Number(ctx.parsed.y);
                if (isGoals) {
                  return ` ${tag}: ${v} ${v === 1 ? 'gol' : 'gols'}`;
                }
                return ` ${tag}: ${v.toFixed(2)} xG`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            border: { color: gridColor },
            ticks: { color: ticksColor, font: { size: 10 } },
            title: { display: true, text: 'minuto de jogo', color: C.inkFaint, font: { size: 10 } }
          },
          y: {
            beginAtZero: true,
            grid: { color: gridColor },
            border: { display: false },
            ticks: {
              color: ticksColor, font: { size: 10 },
              precision: isGoals ? 0 : 2
            },
            title: { display: true, text: metricLabel, color: C.inkFaint, font: { size: 10 } }
          }
        }
      }
    });

    // Goal pulse markers — posicionados após o primeiro render do Chart.js.
    // requestAnimationFrame garante que scales estejam calculados.
    requestAnimationFrame(() => placeMomentumMarkers(_momentumChart, goals));

    // Re-posiciona markers no resize (debounced 150ms)
    if (_momentumResizeTimer) window.removeEventListener('resize', _momentumResizeFn);
    _momentumResizeTimer = null;
    window.addEventListener('resize', _momentumResizeFn);
  }

  function _momentumResizeFn() {
    if (_momentumResizeTimer) clearTimeout(_momentumResizeTimer);
    _momentumResizeTimer = setTimeout(() => {
      if (_momentumChart && _momentumChart.data && _momentumChart.data._goals) {
        placeMomentumMarkers(_momentumChart, _momentumChart.data._goals);
      }
    }, 150);
  }

  /** Converte minuto → pixel X no eixo category via interpulação linear. */
  function minuteToPixelX(chart, minute) {
    const labels = chart.data.labels;
    if (!labels || !labels.length) return 0;
    const m = Number(minute);
    let i = 0;
    while (i < labels.length - 1 && Number(labels[i + 1]) <= m) i++;
    const lo = Number(labels[i]);
    const hi = i + 1 < labels.length ? Number(labels[i + 1]) : lo;
    const frac = hi > lo ? (m - lo) / (hi - lo) : 0;
    const pxLo = chart.scales.x.getPixelForValue(i);
    const pxHi = chart.scales.x.getPixelForValue(Math.min(i + 1, labels.length - 1));
    return pxLo + (pxHi - pxLo) * frac;
  }

  function placeMomentumMarkers(chart, goals) {
    const host = $('#wc-momentum-markers');
    if (!host || !chart || !chart.scales) return;
    // Guarda goals no chart p/ reuse no resize.
    chart.data._goals = goals;

    host.innerHTML = '';
    if (!goals || !goals.length) return;

    goals.forEach(g => {
      const minute = Number(g.minute) || 0;
      const cumVal = Number(g.cum != null ? g.cum : g.xg_cum) || 0;
      const px = minuteToPixelX(chart, minute);
      const py = chart.scales.y.getPixelForValue(cumVal);

      const span = document.createElement('span');
      span.className = 'wc-goal-pulse';
      span.style.left = `${px}px`;
      span.style.top  = `${py}px`;
      span.setAttribute('aria-hidden', 'true');
      span.title = `${g.player || ''} · ${minute}'`;

      const dot = document.createElement('span');
      dot.className = 'wc-goal-pulse__dot';
      span.appendChild(dot);

      const ring = document.createElement('span');
      ring.className = 'wc-goal-pulse__ring';
      span.appendChild(ring);

      host.appendChild(span);
    });
  }

  /* ════════════════════════════════════════════════════════
   * Estado de erro global (fetch falhou → 3 sections em erro)
   * ════════════════════════════════════════════════════════ */
  function renderAllErrors() {
    const errShot = $('#wc-shotstats-error');
    const errPass = $('#wc-passstats-error');
    const errFlow = $('#wc-flow-error');
    const hostShot = $('#wc-shotstats-host');
    const hostPass = $('#wc-passstats-host');

    if (hostShot) hostShot.innerHTML =
      `<p class="wc-error mono-label" style="padding:var(--space-5)">Falha ao carregar estatísticas de finalização.</p>`;
    if (hostPass) hostPass.innerHTML =
      `<p class="wc-error mono-label" style="padding:var(--space-5)">Falha ao carregar estatísticas de passes.</p>`;
    if (errShot) errShot.hidden = false;
    if (errPass) errPass.hidden = false;
    if (errFlow) errFlow.hidden = false;
  }

  /* ════════════════════════════════════════════════════════
   * Namespace público (debug / testes)
   * ════════════════════════════════════════════════════════ */
  window.WCDeepStats = {
    populateSelectors,
    onMatchChange,
    renderShotStats,
    renderPassStats,
    renderMomentum,
    _loadJSON: loadJSON,
  };

  /* ════════════════════════════════════════════════════════
   * Init
   * ════════════════════════════════════════════════════════ */
  async function init() {
    // Reveal das seções (fallback se main.js não rodar).
    observeReveals(document);

    const result = await loadJSON('deepstats');

    if (!result.ok || !result.data) {
      renderAllErrors();
      return;
    }

    _data = result.data;
    _selectedMatchId = _data.featured_id ||
      (Array.isArray(_data.match_list) && _data.match_list[0] && _data.match_list[0].id) ||
      null;

    // Popula os 3 selects com a lista de partidas (81 no total).
    if (Array.isArray(_data.match_list)) {
      populateSelectors(_data.match_list, _selectedMatchId);
    }

    // Render inicial — falha isolada por seção.
    try { renderShotStats(); } catch (e) { console.error('[WCDeepStats] renderShotStats falhou:', e); }
    try { renderPassStats(); } catch (e) { console.error('[WCDeepStats] renderPassStats falhou:', e); }
    try { renderMomentum(); } catch (e) { console.error('[WCDeepStats] renderMomentum falhou:', e); }

    // Reobserva reveals injetados dinamicamente.
    observeReveals(document);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
