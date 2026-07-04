/*
 * World Cup Dashboard — deepstats.js
 * ---------------------------------------------------------------------------
 * Ball-level sections [04/05/06]:
 *   04 · Mapa de Finalizações  → renderShotMap(data.shot_map)
 *   05 · Rede de Passes        → renderPassNetwork(data.pass_network)
 *   06 · Trajetória da Bola    → renderMomentum(data.momentum)
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
 *   "updated_at": "2026-07-04T04:34:06Z",
 *   "source": "FBref + StatsBomb Open Data 360",
 *   "shot_map": {
 *     "match": "Brasil 2–1 Argentina",
 *     "date": "2026-06-28",
 *     "shots": [
 *       { "x": 78, "y": 38, "xg": 0.41, "goal": true,
 *         "player": "Vinícius Jr", "minute": 23, "team": "BRA" }
 *     ]
 *   },
 *   "pass_network": {
 *     "available": false,
 *     // quando disponível:
 *     "match": "...",
 *     "teams": { "home": {...}, "away": {...} },
 *     "nodes": [{ "team": "home", "player": "...", "line": "GK|DF|MF|FW",
 *                 "x": 0..100, "y": 0..100, "passes": int }],
 *     "edges": [{ "from": idx, "to": idx, "passes": int }]
 *   },
 *   "momentum": {
 *     "match": "...",
 *     "labels": [0, 10, 20, ...],
 *     "home": { "code": "BRA", "flag": "🇧🇷", "xg_cum": [0, 0.08, ...] },
 *     "away": { "code": "ARG", "flag": "🇦🇷", "xg_cum": [0, 0, ...] },
 *     "goals": [
 *       { "minute": 23, "team": "home", "player": "...", "xg_cum": 0.41 }
 *     ]
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
   * SVG namespace helper
   * ════════════════════════════════════════════════════════ */
  const SVG_NS = 'http://www.w3.org/2000/svg';

  function svgEl(tag, attrs) {
    const e = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      for (const k in attrs) {
        if (attrs[k] != null) e.setAttribute(k, attrs[k]);
      }
    }
    return e;
  }

  /* ════════════════════════════════════════════════════════
   * [04] renderShotMap(data)
   * Pitch SVG (viewBox 0 0 60 80, portrait) + bubbles HTML overlay.
   * Coords do JSON: x,y em % [0..100] do campo.
   * ════════════════════════════════════════════════════════ */
  const shotMapState = { all: [], filter: 'all', match: '' };

  function drawShotMapPitch() {
    const svg = $('#wc-shotmap-svg');
    if (!svg) return;
    // Limpa qualquer conteúdo anterior (mantém <title> se houver)
    Array.from(svg.children).forEach(c => { if (c.tagName.toLowerCase() !== 'title') c.remove(); });

    const sw = 0.4;        // stroke-width thin
    const stroke = 'var(--wc-field-ink)';
    const fill = 'none';

    // viewBox 0 0 60 80 (portrait, atacando para cima/baixo)
    const mkRect  = (x, y, w, h) => svgEl('rect',  { x, y, width: w, height: h, stroke, 'stroke-width': sw, fill });
    const mkLine  = (x1, y1, x2, y2) => svgEl('line',  { x1, y1, x2, y2, stroke, 'stroke-width': sw });
    const mkCirc  = (cx, cy, r) => svgEl('circle', { cx, cy, r, stroke, 'stroke-width': sw, fill });

    // Outer boundary (1u margin)
    svg.appendChild(mkRect(1, 1, 58, 78));
    // Halfway line (horizontal, no meio do campo)
    svg.appendChild(mkLine(1, 40, 59, 40));
    // Center circle + spot
    svg.appendChild(mkCirc(30, 40, 8));
    svg.appendChild(svgEl('circle', { cx: 30, cy: 40, r: 0.5, fill: 'var(--wc-field-ink)' }));
    // Penalty boxes (top + bottom) — 30u wide × 10u tall
    svg.appendChild(mkRect(15, 1,  30, 10));
    svg.appendChild(mkRect(15, 69, 30, 10));
    // 6-yard boxes — 18u wide × 4u tall
    svg.appendChild(mkRect(21, 1,  18, 4));
    svg.appendChild(mkRect(21, 75, 18, 4));
    // Penalty arcs (semicírculos nas bordas das áreas)
    const arcR = 5;
    svg.appendChild(svgEl('path', {
      d: `M ${30 - arcR} 11 A ${arcR} ${arcR} 0 0 0 ${30 + arcR} 11`,
      stroke, 'stroke-width': sw, fill
    }));
    svg.appendChild(svgEl('path', {
      d: `M ${30 - arcR} 69 A ${arcR} ${arcR} 0 0 1 ${30 + arcR} 69`,
      stroke, 'stroke-width': sw, fill
    }));
  }

  function renderShotMap(data) {
    if (!data || data.available === false || !Array.isArray(data.shots) || !data.shots.length) {
      const empty = $('#wc-shotmap-empty');
      if (empty) empty.hidden = false;
      // available=false = FBref ainda não forneceu (esperado, não erro)
      const isWaiting = data && data.available === false;
      const err = $('#wc-shotmap-error');
      if (err) err.hidden = isWaiting;
      if (isWaiting) {
        const m = $('#wc-shotmap-match');
        if (m) m.textContent = 'aguardando FBref · pipeline CI';
      }
      return;
    }

    drawShotMapPitch();

    shotMapState.all = data.shots;
    shotMapState.match = data.match || '';

    const matchEl = $('#wc-shotmap-match');
    if (matchEl) matchEl.textContent = shotMapState.match;

    renderShotMapFilters();
    renderShotMapBubbles();
  }

  function renderShotMapFilters() {
    const host = $('#wc-shotmap-filters');
    if (!host) return;

    const chips = [
      { key: 'all',  label: 'Todas' },
      { key: 'goal', label: 'Gols' },
      { key: 'miss', label: 'Defendidas / fora' },
    ];

    host.innerHTML = chips.map(c => {
      const pressed = shotMapState.filter === c.key;
      return `<button type="button" class="wc-team-chip wc-shotmap-filter"
              data-filter="${escapeHtml(c.key)}"
              aria-pressed="${pressed}">${escapeHtml(c.label)}</button>`;
    }).join('');

    $$('.wc-shotmap-filter', host).forEach(btn => {
      btn.addEventListener('click', () => {
        const f = btn.dataset.filter;
        if (f === shotMapState.filter) return;
        shotMapState.filter = f;
        $$('.wc-shotmap-filter', host).forEach(b =>
          b.setAttribute('aria-pressed', String(b === btn)));

        const bubbleHost = $('#wc-shotmap-bubbles');
        if (!bubbleHost) return;
        if (Motion && Motion.crossfadeSwap) {
          Motion.crossfadeSwap(bubbleHost, renderShotMapBubbles,
            { exitMs: 180, enterStep: 25 });
        } else {
            renderShotMapBubbles();
        }
      });
    });
  }

  function renderShotMapBubbles() {
    const host = $('#wc-shotmap-bubbles');
    if (!host) return;

    const filter = shotMapState.filter;
    const shots = shotMapState.all.filter(s => {
      if (filter === 'all')  return true;
      if (filter === 'goal') return s.goal === true;
      if (filter === 'miss') return s.goal !== true;
      return true;
    });

    host.innerHTML = shots.map(s => {
      const x = Math.max(0, Math.min(100, Number(s.x) || 0));
      const y = Math.max(0, Math.min(100, Number(s.y) || 0));
      const xg = Math.max(0, Math.min(1, Number(s.xg) || 0));
      // R = 4 + sqrt(xg) * 8, clamp 4..18
      const r = Math.max(4, Math.min(18, 4 + Math.sqrt(xg) * 8));
      const kind = s.goal === true ? 'goal' : 'miss';

      const player = escapeHtml(s.player || '—');
      const minute = escapeHtml(String(s.minute ?? ''));
      const team   = escapeHtml(s.team || '');
      const outcome = s.goal === true ? 'gol' : 'defendeu/fora';
      const tip = `${player}${team ? ' · ' + team : ''} · ${minute}' · xG ${xg.toFixed(2)} · ${outcome}`;

      return `<div class="wc-shot-bubble wc-shot-bubble--${kind}"
                   style="left:${x}%;top:${y}%;--r:${r}"
                   data-xg="${xg.toFixed(3)}"
                   data-minute="${minute}"
                   tabindex="0"
                   role="button"
                   aria-label="${tip}">
                <span class="wc-shot-bubble__tip" aria-hidden="true">${tip}</span>
              </div>`;
    }).join('');

    const bubbles = $$('.wc-shot-bubble', host);

    if (Motion && Motion.revealStagger) {
      Motion.revealStagger(bubbles, {
        step: 25,
        sort: (a, b) => Number(b.dataset.xg) - Number(a.dataset.xg)
      });
    } else {
      bubbles.forEach(b => b.classList.add('is-visible'));
    }
  }

  /* ════════════════════════════════════════════════════════
   * [05] renderPassNetwork(data)
   * Pitch SVG (viewBox 0 0 100 64, landscape) + nós + edges.
   * Se data.available === false, mostra #wc-passnet-empty e retorna.
   * ════════════════════════════════════════════════════════ */
  const passNetState = { data: null, currentTeam: 'home' };

  function drawPassNetPitch() {
    const svg = $('#wc-passnet-svg');
    if (!svg) return;
    Array.from(svg.children).forEach(c => { if (c.tagName.toLowerCase() !== 'title') c.remove(); });

    const sw = 0.35;
    const stroke = 'var(--wc-field-ink)';
    const fill = 'none';

    const mkRect = (x, y, w, h) => svgEl('rect',  { x, y, width: w, height: h, stroke, 'stroke-width': sw, fill });
    const mkLine = (x1, y1, x2, y2) => svgEl('line', { x1, y1, x2, y2, stroke, 'stroke-width': sw });
    const mkCirc = (cx, cy, r) => svgEl('circle', { cx, cy, r, stroke, 'stroke-width': sw, fill });

    // viewBox 0 0 100 64 (landscape, atacando esquerda→direita)
    svg.appendChild(mkRect(1, 1, 98, 62));
    // Halfway line (vertical)
    svg.appendChild(mkLine(50, 1, 50, 63));
    // Center circle + spot
    svg.appendChild(mkCirc(50, 32, 9));
    svg.appendChild(svgEl('circle', { cx: 50, cy: 32, r: 0.5, fill: 'var(--wc-field-ink)' }));
    // Penalty boxes (left + right) — 14u wide × 32u tall
    svg.appendChild(mkRect(1, 16,  14, 32));
    svg.appendChild(mkRect(85, 16, 14, 32));
    // 6-yard boxes — 6u wide × 20u tall
    svg.appendChild(mkRect(1, 22,  5, 20));
    svg.appendChild(mkRect(94, 22, 5, 20));
  }

  function renderPassNetwork(data) {
    drawPassNetPitch();

    const empty = $('#wc-passnet-empty');
    const toggle = $('#wc-passnet-toggle');

    if (!data || data.available === false) {
      if (empty) empty.hidden = false;
      if (toggle) toggle.innerHTML = '';
      // Limpa nós/edges desenhados
      const svg = $('#wc-passnet-svg');
      if (svg) {
        Array.from(svg.children).forEach(c => {
          const tag = c.tagName.toLowerCase();
          if (tag !== 'title' && tag !== 'rect' && tag !== 'line' && tag !== 'circle' && tag !== 'path') c.remove();
        });
      }
      return;
    }

    if (empty) empty.hidden = true;
    passNetState.data = data;
    passNetState.currentTeam = 'home';

    // Team toggle
    if (toggle) {
      const teams = data.teams || {};
      const chips = [
        { key: 'home', label: teams.home ? `${teams.home.flag || ''} ${teams.home.code || teams.home.name || 'Casa'}`.trim() : 'Casa' },
        { key: 'away', label: teams.away ? `${teams.away.flag || ''} ${teams.away.code || teams.away.name || 'Fora'}`.trim() : 'Fora' },
      ];
      toggle.innerHTML = chips.map(c => {
        const pressed = passNetState.currentTeam === c.key;
        return `<button type="button" class="wc-team-chip wc-passnet-team-btn"
                data-team="${escapeHtml(c.key)}"
                aria-pressed="${pressed}">${escapeHtml(c.label)}</button>`;
      }).join('');

      $$('.wc-passnet-team-btn', toggle).forEach(btn => {
        btn.addEventListener('click', () => {
          const t = btn.dataset.team;
          if (t === passNetState.currentTeam) return;
          passNetState.currentTeam = t;
          $$('.wc-passnet-team-btn', toggle).forEach(b =>
            b.setAttribute('aria-pressed', String(b === btn)));
          renderPassNetNodes();
        });
      });
    }

    renderPassNetNodes();
  }

  function renderPassNetNodes() {
    const svg = $('#wc-passnet-svg');
    const data = passNetState.data;
    if (!svg || !data || !Array.isArray(data.nodes)) return;

    const team = passNetState.currentTeam;
    const teamNodes = data.nodes.filter(n => n.team === team);

    // Limpa nós/edges existentes (mantém linhas do campo)
    Array.from(svg.children).forEach(c => {
      const tag = c.tagName.toLowerCase();
      if (tag === 'g' && c.classList.contains('wc-pass-node')) c.remove();
      else if (tag === 'line' && c.classList.contains('wc-pass-edge')) c.remove();
    });

    // Mapa de índice global → nó (para resolver edges)
    const nodeIndex = new Map();
    data.nodes.forEach((n, i) => nodeIndex.set(i, n));

    // Mapa player → índice no SVG (para o time selecionado)
    const localIdx = new Map();
    teamNodes.forEach((n, i) => localIdx.set(n, i));

    // Identifica top-5 edges por passes (para --strong)
    const teamEdges = (data.edges || []).filter(e => {
      const a = nodeIndex.get(e.from);
      const b = nodeIndex.get(e.to);
      return a && b && a.team === team && b.team === team;
    });
    const top5 = new Set(
      teamEdges.slice().sort((a, b) => (Number(b.passes) || 0) - (Number(a.passes) || 0))
                .slice(0, 5)
                .map(e => `${e.from}|${e.to}`)
    );

    // Edges primeiro (atrás dos nós)
    const edgeEls = [];
    teamEdges.forEach(e => {
      const a = nodeIndex.get(e.from);
      const b = nodeIndex.get(e.to);
      if (!a || !b) return;
      const x1 = Number(a.x) || 0;
      const y1 = Number(a.y) || 0;
      const x2 = Number(b.x) || 0;
      const y2 = Number(b.y) || 0;
      const isStrong = top5.has(`${e.from}|${e.to}`);
      const line = svgEl('line', {
        x1, y1, x2, y2,
        class: 'wc-pass-edge' + (isStrong ? ' wc-pass-edge--strong' : ''),
        'data-passes': Number(e.passes) || 0
      });
      svg.appendChild(line);
      edgeEls.push(line);
    });

    // Nós (jogadores)
    const nodeEls = [];
    teamNodes.forEach(n => {
      const cx = Number(n.x) || 0;
      const cy = Number(n.y) || 0;
      const line = (n.line || '').toUpperCase();
      const g = svgEl('g', {
        class: 'wc-pass-node',
        'data-line': line,
        'data-player': escapeHtml(n.player || ''),
        transform: `translate(${cx} ${cy})`
      });
      const r = line === 'GK' ? 2.6 : 2.2;
      g.appendChild(svgEl('circle', { cx: 0, cy: 0, r, fill: 'var(--wc-field)', stroke: 'var(--wc-field-ink)', 'stroke-width': 0.3 }));
      // Label (iniciais)
      const initials = String(n.player || '?')
        .split(/\s+/).filter(Boolean).slice(0, 2)
        .map(w => w.charAt(0).toUpperCase()).join('') || '?';
      const label = svgEl('text', {
        x: 0, y: r + 2.6,
        class: 'wc-pass-node__label',
        'text-anchor': 'middle'
      });
      label.textContent = initials;
      g.appendChild(label);
      // Nome completo no <title>
      const title = svgEl('title');
      title.textContent = `${n.player || ''} · ${line} · ${Number(n.passes) || 0} passes`;
      g.appendChild(title);
      svg.appendChild(g);
      nodeEls.push(g);
    });

    // Motion stagger (GK → DF → MF → FW) + draw edges
    const lineOrder = { GK: 0, DF: 1, MF: 2, FW: 3 };
    if (Motion && Motion.revealStagger) {
      Motion.revealStagger(nodeEls, {
        step: 30,
        sort: (a, b) => (lineOrder[a.dataset.line] ?? 9) - (lineOrder[b.dataset.line] ?? 9)
      });
    } else {
      nodeEls.forEach(n => n.classList.add('is-visible'));
    }
    if (Motion && Motion.drawEdges) {
      Motion.drawEdges(edgeEls, { step: 15, delay: 300 });
    } else {
      edgeEls.forEach(e => e.classList.add('is-visible'));
    }
  }

  /* ════════════════════════════════════════════════════════
   * [06] renderMomentum(data)
   * Chart.js line chart (xG acumulado por minuto) + goal pulse markers.
   * ════════════════════════════════════════════════════════ */
  let _momentumChart = null;
  let _momentumResizeTimer = null;

  function renderMomentum(data) {
    const canvas = $('#chart-momentum');
    const errBox = $('#wc-flow-error');
    if (!canvas) return;

    if (typeof Chart === 'undefined') {
      console.warn('[WCDeepStats] Chart.js não carregou — momentum pulado.');
      if (errBox) errBox.hidden = false;
      return;
    }

    if (!data || !Array.isArray(data.labels) ||
        !data.home || !(Array.isArray(data.home.cum) || Array.isArray(data.home.xg_cum)) ||
        !data.away || !(Array.isArray(data.away.cum) || Array.isArray(data.away.xg_cum))) {
      if (errBox) errBox.hidden = false;
      return;
    }

    if (errBox) errBox.hidden = true;

    // Defaults coerentes com Blueprint (idempotente se main.js também setar)
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
    const metricUnit  = data.metric === 'goals' ? '' : ' xG';

    // Destruir chart anterior se existir (re-render seguro)
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
                if (data.metric === 'goals') {
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
            ticks: { color: ticksColor, font: { size: 10 } },
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
    // Guarda goals no chart p/ reuse no resize
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
    const errShot = $('#wc-shotmap-error');
    const errFlow = $('#wc-flow-error');
    const emptyPass = $('#wc-passnet-empty');

    if (errShot) errShot.hidden = false;
    if (errFlow) errFlow.hidden = false;
    if (emptyPass) {
      emptyPass.hidden = false;
      emptyPass.textContent = 'Rede de passes indisponível. Fonte: StatsBomb 360.';
    }
  }

  /* ════════════════════════════════════════════════════════
   * Namespace público
   * ════════════════════════════════════════════════════════ */
  window.WCDeepStats = {
    renderShotMap,
    renderPassNetwork,
    renderMomentum,
    // expose p/ debug / testes
    _loadJSON: loadJSON,
  };

  /* ════════════════════════════════════════════════════════
   * Init
   * ════════════════════════════════════════════════════════ */
  async function init() {
    // Reveal das seções (fallback se main.js não rodar)
    observeReveals(document);

    const result = await loadJSON('deepstats');

    if (!result.ok || !result.data) {
      renderAllErrors();
      return;
    }

    const d = result.data;
    try { renderShotMap(d.shot_map || null); } catch (e) { console.error('[WCDeepStats] renderShotMap falhou:', e); }
    try { renderPassNetwork(d.pass_network || null); } catch (e) { console.error('[WCDeepStats] renderPassNetwork falhou:', e); }
    try { renderMomentum(d.momentum || null); } catch (e) { console.error('[WCDeepStats] renderMomentum falhou:', e); }

    // Reobserva reveals injetados (filtros, etc.)
    observeReveals(document);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
