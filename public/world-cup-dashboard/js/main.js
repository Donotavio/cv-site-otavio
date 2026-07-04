/*
 * World Cup Dashboard — main.js
 * Vanilla JS isolado (sem Astro, sem TypeScript, sem GSAP/Lenis).
 *
 * Pipeline:
 *   1. Promise.allSettled dos 6 JSONs em data/
 *   2. Render de cada seção (com fallback gracioso se fetch falhar)
 *   3. Chart.js (3 charts) inicializados só após estatisticas.json
 *   4. Jogo "Quem é o craque?" com localStorage
 *   5. Motion via IntersectionObserver + count-up
 *
 * XSS: todo conteúdo externo (títulos de notícias, nomes) passa por escapeHtml().
 */

'use strict';

(function () {

  /* ════════════════════════════════════════════════════════
   * Helpers
   * ════════════════════════════════════════════════════════ */
  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const prefersReducedMotion = () =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const LS_KEY = 'wc-craque-votes';

  /** Estado partilhado entre render functions (matches usado por bolão + filtro). */
  const WC_STATE = {
    matches: [],
    groups: [],
  };

  /** Escape HTML de strings externas (títulos de RSS, nomes). Previne XSS. */
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

  /** Flag emoji para flag vazia (placeholder). */
  function flagHtml(flag, fallback) {
    if (flag && flag.trim()) {
      return `<span class="wc-flag" aria-hidden="true">${escapeHtml(flag)}</span>`;
    }
    return `<span class="wc-flag wc-flag--empty" aria-hidden="true">${escapeHtml(fallback || '—')}</span>`;
  }

  /* ════════════════════════════════════════════════════════
   * ModalController — helper único para modais acessíveis
   * Pilha de modais abertos; um único listener de teclado global.
   * Reaproveita o padrão de focus-trap validado (WCAG 2.4.3/2.1.2).
   * ════════════════════════════════════════════════════════ */
  const ModalController = (() => {
    const stack = []; // topo = modal ativo

    function focusables(modalEl) {
      if (!modalEl) return [];
      return $$('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])', modalEl)
        .filter(el => !el.disabled && !el.hidden
                   && el.offsetParent !== null
                   && el.getAttribute('aria-hidden') !== 'true');
    }

    function top() { return stack[stack.length - 1] || null; }

    function _lockScroll(on) {
      // Lock só quando o 1º modal abre; libera quando a pilha esvazia.
      document.body.style.overflow = on ? 'hidden' : '';
    }

    function open(modalEl, trigger) {
      if (!modalEl || !modalEl.hidden) return;
      stack.push({ modal: modalEl, trigger: trigger || document.activeElement });
      modalEl.hidden = false;
      if (trigger && trigger.tagName === 'BUTTON') trigger.setAttribute('aria-expanded', 'true');
      if (stack.length === 1) _lockScroll(true);
      // Delay de 1 tick para o elemento aceitar foco após hidden→visible.
      setTimeout(() => {
        const f = focusables(modalEl);
        if (f.length) f[0].focus({ preventScroll: true });
      }, 30);
    }

    function close(modalEl) {
      const idx = stack.findIndex(e => e.modal === modalEl);
      if (idx === -1) return;
      const entry = stack.splice(idx, 1)[0];
      entry.modal.hidden = true;
      const t = entry.trigger;
      if (t && t.tagName === 'BUTTON') t.setAttribute('aria-expanded', 'false');
      if (typeof t?.focus === 'function') t.focus({ preventScroll: true });
      if (stack.length === 0) _lockScroll(false);
    }

    function isOpen(modalEl) {
      return stack.some(e => e.modal === modalEl);
    }

    // ÚNICO listener de teclado — despacha só p/ o modal ativo (topo da pilha).
    document.addEventListener('keydown', (e) => {
      const active = top();
      if (!active) return;
      const modalEl = active.modal;
      if (e.key === 'Escape') {
        e.preventDefault();
        close(modalEl);
        return;
      }
      if (e.key === 'Tab') {
        const f = focusables(modalEl);
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1], a = document.activeElement;
        if (e.shiftKey) {
          if (a === first || !modalEl.contains(a)) { e.preventDefault(); last.focus({ preventScroll: true }); }
        } else if (a === last) {
          e.preventDefault();
          first.focus({ preventScroll: true });
        }
      }
    });

    return { open, close, isOpen, focusables };
  })();

  /* ════════════════════════════════════════════════════════
   * Fetch resiliente
   * ════════════════════════════════════════════════════════ */
  async function loadJSON(name) {
    try {
      const res = await fetch(`data/${name}.json`, { cache: 'no-cache' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return { ok: true, data };
    } catch (e) {
      console.warn(`[WC] fetch data/${name}.json falhou:`, e);
      return { ok: false, error: e, data: null };
    }
  }

  /* ════════════════════════════════════════════════════════
   * Tempo
   * ════════════════════════════════════════════════════════ */

  /** "há 2h", "há 3 dias", ou data curta se antigo. */
  function relativeTime(iso) {
    if (!iso) return '';
    const then = new Date(iso);
    if (isNaN(then)) return '';
    const now = new Date();
    const diffMs = now - then;
    const sec = Math.round(diffMs / 1000);
    const min = Math.round(sec / 60);
    const hr  = Math.round(min / 60);
    const day = Math.round(hr / 24);

    if (sec < 45)   return 'agora';
    if (min < 60)   return `há ${min}min`;
    if (hr  < 24)   return `há ${hr}h`;
    if (day < 7)    return `há ${day}d`;
    return then.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
  }

  /** Data curta pt-BR: "02/07". */
  function shortDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
  }

  /** Staleness de updated_at. Retorna { label, level } onde level ∈ ok|amber. */
  function freshness(updatedAt) {
    if (!updatedAt) return null;
    const then = new Date(updatedAt);
    if (isNaN(then)) return null;
    const hr = (Date.now() - then.getTime()) / 36e5;
    if (hr < 24) return { label: `atualizado há ${Math.round(hr)}h`, level: 'ok' };
    const days = Math.round(hr / 24);
    if (hr < 48) return { label: `atualizado há ${days}d`, level: 'ok' };
    return { label: `atualizado há ${days}d`, level: 'amber' };
  }

  /* ════════════════════════════════════════════════════════
   * Render — Hero KPIs
   * ════════════════════════════════════════════════════════ */
  function renderHeroKPIs({ partidas, artilheiros, estatisticas }) {
    // KPI 01 — total de jogos
    const elMatches = $('#kpi-total-matches');
    if (elMatches) {
      const total = (partidas.ok && partidas.data.total) || 0;
      elMatches.dataset.countTo = String(total);
      if (prefersReducedMotion()) elMatches.textContent = String(total);
    }

    // KPI 02 — total de gols
    const elGoals = $('#kpi-total-goals');
    if (elGoals) {
      const total = (estatisticas.ok && estatisticas.data.total_goals) || 0;
      elGoals.dataset.countTo = String(total);
      if (prefersReducedMotion()) elGoals.textContent = total.toLocaleString('pt-BR');
    }

    // KPI 03 — média de gols / partida
    const elAvg = $('#kpi-avg-goals');
    if (elAvg) {
      const avg = (estatisticas.ok && estatisticas.data.avg_goals_per_match) || 0;
      elAvg.dataset.countTo = String(avg);
      elAvg.dataset.countDecimals = '2';
      if (prefersReducedMotion()) elAvg.textContent = avg.toFixed(2);
    }

    // KPI 04 — artilheiro atual (Chuteira de Ouro)
    const elScorer = $('#kpi-top-scorer');
    const elTeam   = $('#kpi-top-scorer-team');
    if (elScorer && elTeam) {
      if (artilheiros.ok && artilheiros.data.scorers && artilheiros.data.scorers.length) {
        const top = artilheiros.data.scorers[0];
        elScorer.textContent = top.name;
        const subParts = [];
        if (top.team && top.team.flag) subParts.push(top.team.flag);
        if (top.team && top.team.code) subParts.push(top.team.code);
        subParts.push(`${top.goals} gols`);
        elTeam.textContent = subParts.join(' · ');
        // Limpa o data-count-to que vinha no HTML (não animamos o nome)
        delete elScorer.dataset.countTo;
      } else {
        elScorer.textContent = '—';
        elTeam.textContent = 'artilheiro indisponível';
      }
    }
  }

  /* ════════════════════════════════════════════════════════
   * Render — Freshness badge (hero + footer)
   * ════════════════════════════════════════════════════════ */
  function renderFreshness(results) {
    // Pega o updated_at mais recente entre os JSONs que carregaram
    const times = results
      .filter(r => r.ok && r.data && r.data.updated_at)
      .map(r => new Date(r.data.updated_at).getTime())
      .filter(t => !isNaN(t));
    if (!times.length) return;

    const latest = new Date(Math.max.apply(null, times));
    const f = freshness(latest.toISOString());
    if (!f) return;

    const badge = $('#wc-freshness');
    if (badge) {
      badge.textContent = f.label;
      badge.hidden = false;
      if (f.level === 'amber') badge.dataset.stale = 'amber';
    }

    const footer = $('#wc-footer-updated');
    if (footer) {
      footer.textContent = latest.toLocaleString('pt-BR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    }
  }

  /* ════════════════════════════════════════════════════════
   * [01] Render — Notícias
   * ════════════════════════════════════════════════════════ */
  function renderNews(result) {
    const list = $('#wc-news-list');
    const sourceTag = $('#wc-news-source');
    if (!list) return;

    if (!result.ok || !result.data || !Array.isArray(result.data.items) || !result.data.items.length) {
      list.innerHTML = `<li class="wc-error mono-label">feed de notícias indisponível</li>`;
      return;
    }

    const items = result.data.items.slice(0, 10);

    if (sourceTag && result.data.source_feeds) {
      sourceTag.textContent = result.data.source_feeds.join(' · ');
      sourceTag.hidden = false;
    }

    list.innerHTML = items.map(item => {
      const title    = escapeHtml(item.title);
      const source   = escapeHtml(item.source || 'fonte');
      const url      = escapeHtml(item.url || '#');
      const summary  = escapeHtml((item.summary || '').replace(source + '$', '').trim());
      const time     = relativeTime(item.published);
      const safeUrl  = (url && /^https?:\/\//i.test(url)) ? url : '#';
      const external = safeUrl !== '#' ? ' target="_blank" rel="noopener noreferrer"' : '';

      return `
        <li class="wc-news-item">
          <a class="wc-news-link" href="${safeUrl}"${external}>
            <span class="wc-news-headline-text">${title}</span>
            ${summary ? `<span class="wc-news-summary">${summary}</span>` : ''}
            <span class="wc-news-meta">
              <span class="wc-news-source-tag">${source}</span>
              <span class="wc-news-time" title="${escapeHtml(item.published || '')}">${time}</span>
            </span>
          </a>
        </li>`;
    }).join('');
  }

  /* ════════════════════════════════════════════════════════
   * [02] Render — Artilharia
   * ════════════════════════════════════════════════════════ */
  function renderScorers(result) {
    const body = $('#wc-scorers-body');
    if (!body) return;

    if (!result.ok || !result.data || !Array.isArray(result.data.scorers) || !result.data.scorers.length) {
      body.innerHTML = `<tr><td colspan="5" class="wc-error mono-label">artilharia indisponível</td></tr>`;
      return;
    }

    const top = result.data.scorers.slice(0, 10);

    body.innerHTML = top.map((s, i) => {
      const rank = i + 1;
      const isGold = rank === 1;
      const flag = s.team && s.team.flag ? escapeHtml(s.team.flag) : '';
      const teamCode = s.team && s.team.code ? escapeHtml(s.team.code) : '';
      const teamName = s.team && s.team.name ? escapeHtml(s.team.name) : '';
      const pen = s.penalties || 0;

      const flagCell = flag
        ? `<span class="wc-flag" aria-hidden="true">${flag}</span>`
        : `<span class="wc-flag wc-flag--empty" aria-hidden="true">—</span>`;

      const goldBadge = isGold
        ? ` <span class="wc-scorers-table__gold-badge" aria-label="Chuteira de Ouro">🏆 Ouro</span>`
        : '';

      return `
        <tr class="${isGold ? 'wc-scorers-table__row--gold' : ''}">
          <td class="wc-scorers-table__rank-cell">${rank}${goldBadge}</td>
          <td>
            <div class="wc-scorers-table__player-cell">
              ${flagCell}
              <span class="wc-scorers-table__name-block">
                <span class="wc-scorers-table__name">${escapeHtml(s.name)}</span>
                <span class="wc-scorers-table__sub">${teamName}</span>
              </span>
            </div>
          </td>
          <td><span class="mono-label" style="letter-spacing:var(--tracking-wide)">${teamCode}</span></td>
          <td class="wc-scorers-table__goals-cell">${s.goals}</td>
          <td class="wc-scorers-table__pen-cell">${pen}</td>
        </tr>`;
    }).join('');
  }

  /* ════════════════════════════════════════════════════════
   * [03] Render — Estatísticas + Charts
   * ════════════════════════════════════════════════════════ */
  function renderStats(result) {
    // Cards auxiliares
    const setVal = (id, v) => { const el = $(id); if (el) el.textContent = v; };

    if (!result.ok || !result.data) {
      ['#stat-avg-value','#stat-bigwin-value','#stat-hi-value','#stat-pen-value','#stat-og-value']
        .forEach(id => setVal(id, '—'));
      setVal('#stat-avg-sub', '');
      setVal('#stat-bigwin-sub', '');
      setVal('#stat-hi-sub', '');
      return;
    }

    const d = result.data;

    // doughnut card (média)
    setVal('#stat-avg-value',
      (typeof d.avg_goals_per_match === 'number') ? d.avg_goals_per_match.toFixed(2) : '—');
    const h1 = d.goals_first_half || 0;
    const h2 = (d.goals_second_half || 0) + (d.goals_extra_time || 0);
    setVal('#stat-avg-sub', `${h1} no 1º tempo · ${h2} no 2º (+prorrogação)`);

    // recordes
    if (d.biggest_win) {
      setVal('#stat-bigwin-value', escapeHtml(d.biggest_win.match || '—'));
      setVal('#stat-bigwin-sub', `diferença de ${d.biggest_win.diff || 0} gols`);
    }
    if (d.highest_scoring_match) {
      setVal('#stat-hi-value', escapeHtml(d.highest_scoring_match.match || '—'));
      setVal('#stat-hi-sub', `${d.highest_scoring_match.goals || 0} gols no total`);
    }
    setVal('#stat-pen-value', String(d.penalties_scored ?? 0));
    setVal('#stat-og-value',  String(d.own_goals ?? 0));

    // ── Charts ────────────────────────────────────────────
    if (typeof Chart === 'undefined') {
      console.warn('[WC] Chart.js não carregou (CDN bloqueado?) — pulando gráficos.');
      return;
    }

    // Defaults coerentes com Blueprint
    Chart.defaults.font.family = token('--font-mono', 'IBM Plex Mono, monospace');
    Chart.defaults.font.size = 11;
    Chart.defaults.color = token('--ink-soft', '#545454');

    const C = {
      paper:     token('--paper-card', '#FFFFFF'),
      paperSoft: token('--paper-soft', '#F4F4F2'),
      ink:       token('--ink', '#0A0A0A'),
      inkSoft:   token('--ink-soft', '#545454'),
      inkFaint:  token('--ink-faint', '#6F6F6F'),
      line:      token('--line', 'rgba(10,10,10,0.12)'),
      field:     token('--wc-field', '#1B8A4B'),
      fieldInk:  token('--wc-field-ink', '#0B6E33'),
      gold:      token('--wc-gold', '#C9941A'),
      goldInk:   token('--wc-gold-ink', '#8A6206'),
      accent:    token('--accent', '#1A1AFF'),
    };

    const gridColor = C.line;
    const ticksColor = C.inkFaint;

    // Reduced-motion → desabilita animações do Chart.js (também já coberto
    // globalmente pela media query no CSS, mas canvas não responde a ela).
    const chartAnimation = prefersReducedMotion() ? false : undefined;

    /* Chart 1 — Doughnut: gols 1º vs 2º tempo (+prorrogação) */
    const c1 = document.getElementById('chart-halves');
    if (c1) {
      new Chart(c1, {
        type: 'doughnut',
        data: {
          labels: ['1º tempo', '2º tempo + prorrogação'],
          datasets: [{
            data: [h1, h2],
            backgroundColor: [C.field, C.gold],
            borderColor: C.paper,
            borderWidth: 2,
            hoverOffset: 4
          }]
        },
        options: {
          animation: chartAnimation,
          responsive: true,
          maintainAspectRatio: false,
          cutout: '62%',
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
                label: (ctx) => ` ${ctx.label}: ${ctx.parsed} gols`
              }
            }
          }
        }
      });
    }

    /* Chart 2 — Bar: gols por faixa de minuto */
    const c2 = document.getElementById('chart-minutes');
    if (c2 && Array.isArray(d.goals_by_minute)) {
      const gm = d.goals_by_minute.filter(r => r && typeof r.count === 'number');
      new Chart(c2, {
        type: 'bar',
        data: {
          labels: gm.map(r => r.range),
          datasets: [{
            label: 'Gols',
            data: gm.map(r => r.count),
            backgroundColor: C.field,
            hoverBackgroundColor: C.fieldInk,
            borderRadius: 2,
            maxBarThickness: 48
          }]
        },
        options: {
          animation: chartAnimation,
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: C.ink,
              titleColor: C.paper,
              bodyColor: C.paper,
              padding: 10,
              callbacks: {
                title: (items) => `Minuto ${items[0].label}`,
                label: (ctx) => ` ${ctx.parsed.y} gols`
              }
            }
          },
          scales: {
            x: {
              grid: { display: false },
              border: { color: gridColor },
              ticks: { color: ticksColor, font: { size: 10 } },
              title: { display: true, text: 'faixa de minuto', color: C.inkFaint, font: { size: 10 } }
            },
            y: {
              beginAtZero: true,
              grid: { color: gridColor },
              border: { display: false },
              ticks: { color: ticksColor, font: { size: 10 }, precision: 0 }
            }
          }
        }
      });
    }

    /* Chart 3 — Bar horizontal: top 8 eficiência (saldo por jogo) */
    const c3 = document.getElementById('chart-efficiency');
    if (c3 && Array.isArray(d.teams_efficiency)) {
      const eff = d.teams_efficiency.slice(0, 8);
      // Cores: o #1 recebe ouro, demais field
      const bg = eff.map((_, i) => i === 0 ? C.gold : C.field);
      const labels = eff.map(t => `${(t.flag || '').trim()} ${t.name}`.trim());
      new Chart(c3, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Saldo / jogo',
            data: eff.map(t => Number(t.diff_per_match) || 0),
            backgroundColor: bg,
            hoverBackgroundColor: C.fieldInk,
            borderRadius: 2,
            maxBarThickness: 22
          }]
        },
        options: {
          animation: chartAnimation,
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: C.ink,
              titleColor: C.paper,
              bodyColor: C.paper,
              padding: 10,
              callbacks: {
                label: (ctx) => {
                  const t = eff[ctx.dataIndex];
                  return [
                    ` saldo/jogo: ${ctx.parsed.x.toFixed(2)}`,
                    ` saldo total: ${t.diff > 0 ? '+' : ''}${t.diff} (${t.goals_for}–${t.goals_against})`,
                    ` jogos: ${t.matches} (${t.wins}V ${t.draws}E ${t.losses}D)`
                  ];
                }
              }
            }
          },
          scales: {
            x: {
              beginAtZero: true,
              grid: { color: gridColor },
              border: { display: false },
              ticks: { color: ticksColor, font: { size: 10 }, precision: 1 },
              title: { display: true, text: 'saldo de gols por partida', color: C.inkFaint, font: { size: 10 } }
            },
            y: {
              grid: { display: false },
              border: { color: gridColor },
              ticks: { color: C.inkSoft, font: { size: 11 } }
            }
          }
        }
      });
    }
  }

  /* ════════════════════════════════════════════════════════
   * [04] Render — Monte Carlo (simulação 10k)
   * Substituiu Probabilidades (Elo). Mesma UI, schema diferente:
   *   teams[] → { rank, name, code, flag, elo, titles, title_probability }
   * ════════════════════════════════════════════════════════ */
  function renderProbabilities(result) {
    const list = $('#wc-prob-list');
    const method = $('#wc-prob-method');
    if (!list) return;

    if (!result.ok || !result.data || !Array.isArray(result.data.teams) || !result.data.teams.length) {
      list.innerHTML = `<li class="wc-error mono-label">simulação indisponível</li>`;
      return;
    }

    // Badge no methodology: Monte Carlo · 10.000 simulações
    if (method) {
      const sims = result.data.simulations
        ? result.data.simulations.toLocaleString('pt-BR')
        : '10.000';
      method.textContent = `metodologia: Monte Carlo · ${sims} simulações`;
    }

    // Linha de fonte dentro do modal de metodologia (mesmo fetch, sem custo extra)
    const mcSource = $('#wc-mc-modal-source');
    if (mcSource) {
      const methodology = result.data.methodology || '';
      const updated = result.data.updated_at
        ? new Date(result.data.updated_at).toLocaleString('pt-BR', { timeZone: 'UTC' })
        : '';
      if (methodology) {
        mcSource.textContent = (updated ? `${updated} UTC · ` : '') + methodology;
        mcSource.hidden = false;
      } else {
        mcSource.hidden = true;
      }
    }

    const top = result.data.teams.slice(0, 12);
    // Barra = Elo relativo ao líder (#1 = 100%)
    const maxElo = Math.max.apply(null, top.map(t => Number(t.elo) || 0));
    const minElo = Math.min.apply(null, top.map(t => Number(t.elo) || 0));
    const eloRange = Math.max(1, maxElo - minElo);

    list.innerHTML = top.map((t, i) => {
      const isTop = i === 0;
      const elo = Number(t.elo) || 0;
      const pct = Number(t.title_probability) || 0;
      const widthPct = Math.round(((elo - minElo) / eloRange) * 100);
      const flag = t.flag ? escapeHtml(t.flag) : '';

      const flagCell = flag
        ? `<span class="wc-prob-row__flag" aria-hidden="true">${flag}</span>`
        : `<span class="wc-prob-row__flag wc-flag--empty" aria-hidden="true">—</span>`;

      return `
        <li class="wc-prob-row ${isTop ? 'is-top' : ''}" data-reveal>
          <span class="wc-prob-row__rank">${t.rank || (i + 1)}</span>
          ${flagCell}
          <div class="wc-prob-row__main">
            <div class="wc-prob-row__name-line">
              <span class="wc-prob-row__name">${escapeHtml(t.name)}</span>
              <span class="wc-prob-row__elo">Elo ${elo.toFixed(1)}</span>
            </div>
            <div class="wc-prob-row__bar-wrap" aria-hidden="true">
              <span class="wc-prob-row__bar" data-width="${widthPct}"></span>
            </div>
          </div>
          <span class="wc-prob-row__pct" title="probabilidade de título (Monte Carlo)">${pct.toFixed(2)}%</span>
        </li>`;
    }).join('');

    // Anima as barras via transform: scaleX (perf-friendly — sem layout thrash)
    const motion = !prefersReducedMotion();
    $$('.wc-prob-row__bar', list).forEach((bar, i) => {
      const scale = (Number(bar.dataset.width) || 0) / 100;
      if (motion) {
        setTimeout(() => { bar.style.transform = `scaleX(${scale})`; }, 80 + i * 40);
      } else {
        bar.style.transition = 'none';
        bar.style.transform = `scaleX(${scale})`;
      }
    });

    observeReveals(list);
  }

  /* ════════════════════════════════════════════════════════
   * [06] Render — Partidas
   * ════════════════════════════════════════════════════════ */
  function renderMatches(result) {
    const recentEl   = $('#wc-matches-recent');
    const upcomingEl = $('#wc-matches-upcoming');
    if (!recentEl || !upcomingEl) return;

    if (!result.ok || !result.data || !Array.isArray(result.data.matches)) {
      const msg = `<li class="wc-error mono-label">partidas indisponíveis</li>`;
      recentEl.innerHTML = msg;
      upcomingEl.innerHTML = msg;
      return;
    }

    const matches = result.data.matches;
    WC_STATE.matches = matches;

    // Separa: finalizados (com placar) | hoje | agendados
    const finished = matches.filter(m => m.status === 'finished' || (m.score && m.score.ft));
    const today    = matches.filter(m => m.status === 'today');
    const sched    = matches.filter(m => m.status === 'scheduled' && m.status !== 'today');

    // Resultados recentes: últimos finalizados (ordenados por data desc)
    const recent = finished
      .slice()
      .sort((a, b) => (new Date(b.date) - new Date(a.date)))
      .slice(0, 8)
      .reverse();

    // Próximos: hoje + agendados (ordenados por data asc)
    const upcoming = today.concat(sched)
      .filter(m => m)
      .sort((a, b) => (new Date(a.date + ' ' + (a.time || '')) - new Date(b.date + ' ' + (b.time || ''))))
      .slice(0, 10);

    recentEl.innerHTML = recent.length
      ? recent.map(matchRowHtml).join('')
      : `<li class="wc-loading mono-label">sem resultados recentes</li>`;

    upcomingEl.innerHTML = upcoming.length
      ? upcoming.map(matchRowHtml).join('')
      : `<li class="wc-loading mono-label">sem jogos agendados</li>`;
  }

  function matchRowHtml(m) {
    const isToday = m.status === 'today';
    const isPlaceholder = m.has_placeholder === true;
    const cls = ['wc-match'];
    if (isToday) cls.push('wc-match--today');
    if (isPlaceholder) cls.push('wc-match--placeholder');

    const t1 = m.team1 || {};
    const t2 = m.team2 || {};
    const ft = (m.score && Array.isArray(m.score.ft)) ? m.score.ft : null;
    const pen = (m.score && Array.isArray(m.score.pen)) ? m.score.pen : null;
    const pending = !ft;

    const team1Flag = flagHtml(t1.flag, '—');
    const team2Flag = flagHtml(t2.flag, '—');
    const team1Name = escapeHtml(t1.name || 'A definir');
    const team2Name = escapeHtml(t2.name || 'A definir');
    const isPh1 = !t1.name || t1.name === 'A definir';
    const isPh2 = !t2.name || t2.name === 'A definir';

    const penNote = (!pending && pen && ft[0] === ft[1])
      ? `<span class="wc-match__score-pen" title="Pênaltis">(${pen[0]}–${pen[1]})</span>`
      : '';
    const scoreHtml = pending
      ? `<span class="wc-match__score wc-match__score--pending">vs</span>`
      : `<span class="wc-match__score">
           <span class="wc-match__score-num">${ft[0]}</span>
           <span class="wc-match__score-sep">–</span>
           <span class="wc-match__score-num">${ft[1]}</span>
           ${penNote}
         </span>`;

    const todayBadge = isToday ? `<span class="wc-match__today-badge" aria-label="Jogo de hoje">Hoje</span>` : '';

    const dateTxt = shortDate(m.date);
    const timeTxt = m.time ? escapeHtml(m.time) : '';
    const roundTxt = m.round ? escapeHtml(m.round) : (m.group && m.group !== 'null' ? escapeHtml(m.group) : '');
    const groundTxt = m.ground ? escapeHtml(m.ground) : '';

    return `
      <li class="${cls.join(' ')}" data-match-num="${m.num || ''}" data-team1="${escapeHtml(t1.name || '')}" data-team2="${escapeHtml(t2.name || '')}" data-team1-code="${escapeHtml(t1.code || '')}" data-team2-code="${escapeHtml(t2.code || '')}">
        <div class="wc-match__team">
          ${team1Flag}
          <span class="wc-match__name ${isPh1 ? 'wc-match__name--placeholder' : ''}">${team1Name}</span>
        </div>
        ${scoreHtml}
        <div class="wc-match__team wc-match__team--right">
          ${team2Flag}
          <span class="wc-match__name ${isPh2 ? 'wc-match__name--placeholder' : ''}">${team2Name}</span>
        </div>
        <div class="wc-match__meta">
          <span class="wc-match__round">${roundTxt}${todayBadge}</span>
          <span class="wc-match__time">${dateTxt}${timeTxt ? ' · ' + timeTxt : ''}${groundTxt ? ' · ' + groundTxt : ''}</span>
        </div>
      </li>`;
  }

  /* ════════════════════════════════════════════════════════
   * [05] Render — Grupos (fase de grupos, 12 × 4)
   * ════════════════════════════════════════════════════════ */
  function renderGroups(result) {
    const host = $('#wc-groups-grid');
    if (!host) return;

    if (!result.ok || !result.data || !Array.isArray(result.data.groups) || !result.data.groups.length) {
      host.innerHTML = `<div class="wc-error mono-label" style="grid-column:1/-1">tabela de grupos indisponível</div>`;
      return;
    }

    host.innerHTML = result.data.groups.map(g => groupCardHtml(g)).join('');
    observeReveals(host);
  }

  function groupCardHtml(g) {
    // "Group A" → "GRUPO A"
    const letter = (g.group || '').replace(/.*Group\s*/i, '').trim() || '?';
    const headLabel = `GRUPO ${letter}`;

    const rows = (g.teams || []).slice().sort((a, b) => (a.position || 99) - (b.position || 99));

    const rowsHtml = rows.map(t => {
      const isQ = t.qualified === true;
      const diff = Number(t.diff) || 0;
      const diffCls = diff > 0 ? 'is-positive' : (diff < 0 ? 'is-negative' : '');
      const diffTxt = (diff > 0 ? '+' : '') + diff;
      const ved = `${t.wins || 0}-${t.draws || 0}-${t.losses || 0}`;
      const gpGc = `${t.goals_for || 0}:${t.goals_against || 0}`;
      const flag = t.flag ? escapeHtml(t.flag) : '';
      const flagCell = flag
        ? `<span class="wc-group-row__flag" aria-hidden="true">${flag}</span>`
        : `<span class="wc-group-row__flag" aria-hidden="true">·</span>`;
      const badge = isQ ? `<span class="wc-group-row__badge" aria-label="classificado" title="Classificado">✓</span>` : '';
      const cls = ['wc-group-row'];
      if (isQ) cls.push('is-qualified');

      return `
        <div class="${cls.join(' ')}" role="listitem">
          ${flagCell}
          <span class="wc-group-row__name-block">
            <span class="wc-group-row__name">${escapeHtml(t.name || '—')}</span>
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
          <span class="mono-label">${escapeHtml(headLabel)}</span>
          <span class="mono-label" style="color:var(--ink-faint)">${rows.length} sel.</span>
        </header>
        <div class="wc-group-rows" role="list">${rowsHtml}</div>
      </div>`;
  }

  /* ════════════════════════════════════════════════════════
   * [06] Render — Bracket do mata-mata
   * ════════════════════════════════════════════════════════ */
  // Ordem canônica das fases + label curto.
  const BRACKET_ROUNDS = [
    { match: 'Round of 32',          short: '16 AVOS',  full: '16 avos de final' },
    { match: 'Round of 16',          short: 'OITAVAS',  full: 'Oitavas de final' },
    { match: 'Quarter-final',        short: 'QUARTAS',  full: 'Quartas de final' },
    { match: 'Semi-final',           short: 'SEMIS',    full: 'Semifinal' },
    { match: 'Final',                short: 'FINAL',    full: 'Final' },
    { match: 'Match for third place',short: '3º LUGAR', full: 'Disputa de 3º lugar' },
  ];

  function renderBracket(result) {
    const host = $('#wc-bracket-host');
    if (!host) return;

    if (!result.ok || !result.data || !Array.isArray(result.data.matches)) {
      host.innerHTML = `<p class="wc-error mono-label">bracket indisponível</p>`;
      return;
    }

    // Filtra só mata-mata (round sem "Matchday"), ordena por num.
    const ko = result.data.matches
      .filter(m => m.round && !/matchday/i.test(m.round))
      .sort((a, b) => (a.num || 0) - (b.num || 0));

    // Indexa por round.
    const byRound = {};
    BRACKET_ROUNDS.forEach(r => { byRound[r.match] = []; });
    ko.forEach(m => {
      if (byRound[m.round]) byRound[m.round].push(m);
    });

    // Desktop: 6-col grid.
    const desktopHtml = `
      <div class="wc-bracket" role="region" aria-label="Chave do mata-mata (desktop)">
        ${BRACKET_ROUNDS.map(r => {
          const ms = byRound[r.match] || [];
          return `
            <div class="wc-bracket__col">
              <div class="wc-bracket__col-head">
                <span class="mono-label">${r.short}</span>
              </div>
              <div class="wc-bracket__matches">
                ${ms.length
                  ? ms.map(m => bracketMatchHtml(m)).join('')
                  : `<div class="wc-bracket-match wc-bracket-match--empty" aria-hidden="true"></div>`}
              </div>
            </div>`;
        }).join('')}
      </div>`;

    // Mobile: <details> por fase.
    const mobileHtml = `
      <div class="wc-bracket-mobile" role="region" aria-label="Chave do mata-mata">
        ${BRACKET_ROUNDS.map((r, i) => {
          const ms = byRound[r.match] || [];
          if (!ms.length) return '';
          return `
            <details ${i < 2 ? 'open' : ''}>
              <summary>
                <span class="mono-label">${r.short}</span>
                <span class="wc-bracket-mobile__count">${ms.length} jogo${ms.length > 1 ? 's' : ''}</span>
              </summary>
              <div class="wc-bracket-mobile__body">
                ${ms.map(m => bracketMatchHtml(m)).join('')}
              </div>
            </details>`;
        }).join('')}
      </div>`;

    host.innerHTML = desktopHtml + mobileHtml;
    observeReveals(host);
  }

  function bracketMatchHtml(m) {
    const isToday = m.status === 'today';
    const isFinished = m.status === 'finished' || (m.score && m.score.ft);
    const isPlaceholder = m.has_placeholder === true ||
      (!m.team1 || !m.team1.name || m.team1.name === 'A definir') ||
      (!m.team2 || !m.team2.name || m.team2.name === 'A definir');
    const isFinalDone = isFinished && m.round === 'Final';

    const cls = ['wc-bracket-match'];
    if (isToday) cls.push('is-today');
    if (isFinalDone) cls.push('is-final-done');

    const t1 = m.team1 || {};
    const t2 = m.team2 || {};
    const s = m.score || {};
    const ft = Array.isArray(s.ft) && s.ft.length === 2 ? s.ft : null;
    const et = Array.isArray(s.et) && s.et.length === 2 ? s.et : null;
    const pen = Array.isArray(s.pen) && s.pen.length === 2 ? s.pen : null;

    // Determina vencedor/perdedor: tempo normal → prorrogação → pênaltis
    let w1 = null, w2 = null;
    let sc1 = ft ? ft[0] : null;
    let sc2 = ft ? ft[1] : null;
    if (ft && isFinished) {
      if (ft[0] > ft[1]) { w1 = true; }
      else if (ft[1] > ft[0]) { w2 = true; }
      else {
        // Empate no tempo normal — verifica prorrogação
        if (et && et[0] !== et[1]) {
          sc1 = et[0]; sc2 = et[1];
          if (et[0] > et[1]) { w1 = true; } else { w2 = true; }
        } else if (pen && pen[0] !== pen[1]) {
          // Decisão por pênaltis — mostra ft com notação (pen)
          sc1 = `${ft[0]} (${pen[0]})`;
          sc2 = `${ft[1]} (${pen[1]})`;
          if (pen[0] > pen[1]) { w1 = true; } else { w2 = true; }
        }
      }
    }

    function teamRow(team, winner, score, isPending) {
      const isPh = !team || !team.name || team.name === 'A definir';
      const name = isPh ? 'A definir' : escapeHtml(team.name);
      const nameCls = ['wc-bracket-match__name'];
      if (isPh) nameCls.push('wc-bracket-match__name--placeholder');
      else if (winner === true) nameCls.push('wc-bracket-match__name--winner');
      else if (winner === false) nameCls.push('wc-bracket-match__name--loser');

      const flag = (team && team.flag) ? escapeHtml(team.flag) : '';
      const flagCell = flag && !isPh
        ? `<span class="wc-bracket-match__flag" aria-hidden="true">${flag}</span>`
        : '';

      let scoreHtml = '';
      if (isPending) {
        scoreHtml = `<span class="wc-bracket-match__score wc-bracket-match__score--pending">—</span>`;
      } else {
        const sCls = ['wc-bracket-match__score'];
        if (winner === true) sCls.push('wc-bracket-match__score--winner');
        else if (winner === false) sCls.push('wc-bracket-match__score--loser');
        scoreHtml = `<span class="${sCls.join(' ')}">${score}</span>`;
      }

      return `
        <div class="wc-bracket-match__row">
          <span class="wc-bracket-match__team">
            ${flagCell}
            <span class="${nameCls.join(' ')}">${name}</span>
          </span>
          ${scoreHtml}
        </div>`;
    }

    const pending = !ft;
    const html = teamRow(t1, w1 === true ? true : (w2 === true ? false : null), sc1, pending) +
                 teamRow(t2, w2 === true ? true : (w1 === true ? false : null), sc2, pending);

    const todayTag = isToday ? `<span class="wc-bracket-match__today-tag">HOJE</span>` : '';

    return `
      <div class="${cls.join(' ')}" data-match-num="${m.num || ''}">
        ${html}
        ${todayTag}
      </div>`;
  }

  /* ════════════════════════════════════════════════════════
   * [07] Render — Seleção da Copa (XI em campo 4-3-3)
   * ════════════════════════════════════════════════════════ */
  function renderSelection(result) {
    const host = $('#wc-selection-host');
    if (!host) return;

    if (!result.ok || !result.data || !Array.isArray(result.data.xi) || !result.data.xi.length) {
      host.innerHTML = `<p class="wc-error mono-label">seleção da copa indisponível</p>`;
      return;
    }

    const d = result.data;
    const formation = d.formation || '4-3-3';

    // Agrupa por posição
    const byPos = { GK: [], DF: [], MF: [], FW: [] };
    d.xi.forEach(p => {
      const pos = (p.position || '').toUpperCase();
      if (byPos[pos]) byPos[pos].push(p);
    });

    // Artilheiro entre FW = max gols parseado de stat ("6 gols")
    function parseGoals(p) {
      if (typeof p.goals === 'number') return p.goals;
      const s = String(p.stat || '');
      const m = s.match(/(\d+)\s*gol/i);
      return m ? parseInt(m[1], 10) : 0;
    }
    let topScorerId = null;
    let topScorerGoals = -1;
    byPos.FW.forEach(p => {
      const g = parseGoals(p);
      if (g > topScorerGoals) { topScorerGoals = g; topScorerId = playerKey(p); }
    });

    function playerKey(p) {
      return (p.name || '') + '|' + ((p.team && p.team.code) || '');
    }
    // Resolves after we know topScorerId
    function isTopScorer(p) {
      return topScorerId !== null && playerKey(p) === topScorerId;
    }

    function tokenHtml(p, isGK) {
      const isTop = !isGK && isTopScorer(p);
      const team = p.team || {};
      const initials = (p.name || '?')
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map(w => w.charAt(0).toUpperCase())
        .join('') || '?';
      const flag = team.flag ? escapeHtml(team.flag) : '';
      const stat = escapeHtml(p.stat || '');
      const cls = ['wc-player-token'];
      if (isGK) cls.push('wc-player-token--gk');
      if (isTop) cls.push('wc-player-token--topscorer');
      const titleParts = [
        p.name ? escapeHtml(p.name) : '',
        team.name ? escapeHtml(team.name) : '',
        team.code ? escapeHtml(team.code) : '',
        p.position ? escapeHtml(p.position) : '',
        stat,
        isTop ? 'artilheiro da seleção' : '',
      ].filter(Boolean);

      return `
        <div class="${cls.join(' ')}" title="${titleParts.join(' · ')}">
          <div class="wc-player-token__circle">
            <span class="wc-player-token__initials" aria-hidden="true">${escapeHtml(initials)}</span>
          </div>
          <span class="wc-player-token__name">${escapeHtml(shortName(p.name))}</span>
          <span class="wc-player-token__stat">${flag} ${stat}</span>
        </div>`;
    }

    function rowHtml(players, rowCls, isGK) {
      const cells = players.map(p => tokenHtml(p, isGK)).join('');
      return `<div class="wc-pitch__row ${rowCls}">${cells}</div>`;
    }

    const gkRow  = rowHtml(byPos.GK, 'wc-pitch__row--gk', true);
    const dfRow  = rowHtml(byPos.DF, 'wc-pitch__row--df', false);
    const mfRow  = rowHtml(byPos.MF, 'wc-pitch__row--mf', false);
    const fwRow  = rowHtml(byPos.FW, 'wc-pitch__row--fw', false);

    // Faixa de goleiros
    const topGks = Array.isArray(d.top_goalkeepers) ? d.top_goalkeepers.slice(0, 5) : [];
    const bestGkName = d.best_goalkeeper && d.best_goalkeeper.name;
    const gksHtml = topGks.map(gk => {
      const team = gk.team || {};
      const initials = (gk.name || '?').split(/\s+/).slice(0, 2)
        .map(w => w.charAt(0).toUpperCase()).join('') || '?';
      const flag = team.flag ? escapeHtml(team.flag) : '';
      const isBest = bestGkName && gk.name === bestGkName;
      const stat = `${gk.clean_sheets || 0} CS · GA ${typeof gk.ga_per_game === 'number' ? gk.ga_per_game.toFixed(2) : '—'}`;
      return `
        <div class="wc-top-gk ${isBest ? 'wc-top-gk--best' : ''}" title="${escapeHtml(gk.name || '')} · ${escapeHtml(stat)}">
          <div class="wc-top-gk__avatar">${escapeHtml(initials)}</div>
          <span class="wc-top-gk__flag" aria-hidden="true">${flag}</span>
          <span class="wc-top-gk__name">${escapeHtml(shortName(gk.name))}</span>
          <span class="wc-top-gk__stat">${escapeHtml(stat)}</span>
        </div>`;
    }).join('');

    host.innerHTML = `
      <div class="wc-pitch crop" role="img" aria-label="Campo 4-3-3 com a seleção da Copa">
        <span class="crop-mark-bl" aria-hidden="true"></span>
        <span class="crop-mark-br" aria-hidden="true"></span>
        ${gkRow}${dfRow}${mfRow}${fwRow}
      </div>
      ${topGks.length ? `
        <div class="wc-top-gks">
          <header class="wc-top-gks__head">
            <span class="mono-label">goleiros</span>
            <span class="mono-label" style="color:var(--ink-faint)">top ${topGks.length}</span>
          </header>
          <div class="wc-top-gks__list">${gksHtml}</div>
        </div>` : ''}
    `;
    observeReveals(host);
  }

  /** Encurta "Kylian Mbappé" → "Mbappé" (último sobrenome). */
  function shortName(full) {
    if (!full) return '—';
    const parts = String(full).trim().split(/\s+/);
    if (parts.length <= 1) return parts[0];
    // Mantém os 2 últimos tokens (e.g. "Raúl Rangel", "Lionel Messi")
    return parts.slice(-2).join(' ');
  }

  /* ════════════════════════════════════════════════════════
   * [08] Render — Insights editoriais (bento)
   * ════════════════════════════════════════════════════════ */
  function categorizeInsight(text) {
    const t = String(text || '').toLowerCase();
    // Defesa/solidão primeiro (antes de gold, pra não capturar "0 gols sofridos")
    if (/(defesa|sólid|sofreu|clean sheet|goleiro|sem ceder|levou|gols contra)/.test(t)) return 'field';
    // Tempo/penal/método → live
    if (/(pênalti|penal|quando|tempo|minuto|marca penal)/.test(t)) return 'live';
    // Ataque/artilharia/gols → gold
    if (/(artilheiro|chuteira|ataque|letal|ofensiv|marcou|gols?|aproveitamento|goleada|ritmo)/.test(t)) return 'gold';
    return 'ink';
  }

  function renderInsights(result) {
    const host = $('#wc-insights-grid');
    if (!host) return;

    if (!result.ok || !result.data || !Array.isArray(result.data.insights) || !result.data.insights.length) {
      host.innerHTML = `<div class="wc-error mono-label" style="grid-column:1/-1">insights indisponíveis</div>`;
      return;
    }

    // Layout: 2 hero (idx 0,1) + 4 md (idx 2-5) + 2 hero (idx 6,7)
    const layout = ['hero','hero','md','md','md','md','hero','hero'];

    host.innerHTML = result.data.insights.slice(0, 8).map((ins, i) => {
      const num = String(i + 1).padStart(2, '0');
      const title = escapeHtml(ins.title || '');
      // Descarta emoji do JSON — só corpo vira HTML (com key destacada)
      const body = escapeHtml(ins.body || '');
      const cat = categorizeInsight((ins.title || '') + ' ' + (ins.body || ''));

      // Heurística: destaca o primeiro número forte no corpo (gols, jogos, %)
      const bodyWithKey = body.replace(
        /(\b\d+(?:[.,]\d+)?\b)/,
        '<span class="wc-insight-card__key">$1</span>'
      );

      const cls = ['wc-insight-card', `wc-insight-card--${cat}`, `wc-insight-card--${layout[i] || 'md'}`];

      return `
        <article class="${cls.join(' ')}" data-reveal>
          <header class="wc-insight-card__head">
            <span class="mono-label">${num}</span>
          </header>
          <h3 class="wc-insight-card__title">${title}</h3>
          <p class="wc-insight-card__body">${bodyWithKey}</p>
        </article>`;
    }).join('');

    observeReveals(host);
  }

  /* ════════════════════════════════════════════════════════
   * [11] Bolão Local (localStorage)
   * ════════════════════════════════════════════════════════ */
  const BOLAO_KEY = 'wc-bolao';

  function readBolao() {
    try {
      const raw = localStorage.getItem(BOLAO_KEY);
      if (!raw) return {};
      const obj = JSON.parse(raw);
      return (obj && typeof obj === 'object') ? obj : {};
    } catch (e) { return {}; }
  }
  function writeBolao(data) {
    try { localStorage.setItem(BOLAO_KEY, JSON.stringify(data)); }
    catch (e) { console.warn('[WC] bolão: não foi possível salvar:', e); }
  }

  function renderBolao(result) {
    const list = $('#wc-bolao-list');
    const resetBtn = $('#wc-bolao-reset');
    if (!list) return;

    if (!result.ok || !result.data || !Array.isArray(result.data.matches)) {
      list.innerHTML = `<li class="wc-error mono-label">bolão indisponível</li>`;
      return;
    }

    const matches = result.data.matches;
    const todayIso = new Date().toISOString().slice(0, 10);

    // Próximos 5: today OU scheduled com data >= hoje, ordenados por data asc.
    const upcoming = matches
      .filter(m => (m.status === 'today' || m.status === 'scheduled') && (m.date || '') >= todayIso)
      .sort((a, b) => {
        const ka = (a.date || '') + ' ' + (a.time || '');
        const kb = (b.date || '') + ' ' + (b.time || '');
        return ka.localeCompare(kb);
      })
      .slice(0, 5);

    // Adiciona também finalizados que tenham palpite do usuário (para mostrar resultado)
    const picks = readBolao();
    const finishedWithPick = matches.filter(m =>
      (m.status === 'finished' || (m.score && m.score.ft)) &&
      picks[String(m.num)]
    );

    const allToShow = upcoming.concat(finishedWithPick.filter(m => !upcoming.find(u => u.num === m.num)));

    if (!allToShow.length) {
      list.innerHTML = `<li class="wc-loading mono-label">nenhum jogo disponível para palpite</li>`;
      renderBolaoScore(result);
      return;
    }

    list.innerHTML = allToShow.map(m => bolaoItemHtml(m, picks)).join('');

    // Wiring: inputs + submit
    $$('.wc-bolao-submit', list).forEach(btn => {
      btn.addEventListener('click', onBolaoSubmit);
    });

    // Reset
    if (resetBtn) {
      resetBtn.onclick = () => {
        if (Object.keys(picks).length === 0) return;
        if (!window.confirm('Apagar todos os seus palpites?')) return;
        writeBolao({});
        renderBolao(result);
      };
    }

    renderBolaoScore(result);
  }

  function bolaoItemHtml(m, picks) {
    const isToday = m.status === 'today';
    const isFinished = m.status === 'finished' || (m.score && m.score.ft);
    const cls = ['wc-bolao-item'];
    if (isToday) cls.push('is-today');
    if (isFinished) cls.push('is-finished');

    const t1 = m.team1 || {};
    const t2 = m.team2 || {};
    const ft = (m.score && Array.isArray(m.score.ft) && m.score.ft.length === 2) ? m.score.ft : null;

    const isPh1 = !t1.name || t1.name === 'A definir';
    const isPh2 = !t2.name || t2.name === 'A definir';

    const pick = picks[String(m.num)] || {};
    const hasPick = typeof pick.golsA === 'number' || typeof pick.golsB === 'number';

    let resultHtml = '';
    let resultCls = '';
    if (isFinished && hasPick) {
      const pts = computeBolaoPoints(pick, ft);
      if (pts === 3) { resultHtml = `acerto exato · +3 pts`; resultCls = 'wc-bolao-result--exact'; }
      else if (pts === 1) { resultHtml = `vencedor certo · +1 pt`; resultCls = 'wc-bolao-result--winner'; }
      else { resultHtml = `errou · 0 pts`; }
    } else if (isFinished && !hasPick) {
      resultHtml = `sem palpite`;
    }

    const inputs = isFinished
      ? `<div class="wc-bolao-result ${resultCls}">${resultHtml}</div>`
      : `
        <div class="wc-bolao-inputs">
          <input type="number" min="0" max="30" class="wc-bolao-input" data-side="a" data-match="${m.num}"
                 value="${pick.golsA != null ? pick.golsA : ''}" aria-label="Gols ${escapeHtml(t1.name || 'time A')}">
          <span class="wc-bolao-input-sep">×</span>
          <input type="number" min="0" max="30" class="wc-bolao-input" data-side="b" data-match="${m.num}"
                 value="${pick.golsB != null ? pick.golsB : ''}" aria-label="Gols ${escapeHtml(t2.name || 'time B')}">
        </div>
        <button type="button" class="wc-bolao-submit" data-match="${m.num}">Palpitar</button>`;

    const dateTxt = shortDate(m.date);
    const timeTxt = m.time ? escapeHtml(m.time) : '';
    const roundTxt = m.round ? escapeHtml(m.round) : '';

    return `
      <li class="${cls.join(' ')}" data-match-num="${m.num}">
        <div class="wc-bolao-team">
          ${flagHtml(t1.flag, '—')}
          <span class="wc-bolao-team__name ${isPh1 ? 'wc-bolao-team__name--placeholder' : ''}">${escapeHtml(t1.name || 'A definir')}</span>
        </div>
        <div class="wc-bolao-mid">
          ${inputs}
        </div>
        <div class="wc-bolao-team wc-bolao-team--right">
          ${flagHtml(t2.flag, '—')}
          <span class="wc-bolao-team__name ${isPh2 ? 'wc-bolao-team__name--placeholder' : ''}">${escapeHtml(t2.name || 'A definir')}</span>
        </div>
        <div class="wc-bolao-meta">
          <span>${roundTxt}</span>
          <span>${dateTxt}${timeTxt ? ' · ' + timeTxt : ''}</span>
        </div>
      </li>`;
  }

  function onBolaoSubmit(e) {
    const btn = e.currentTarget;
    const matchNum = btn.dataset.match;
    const item = btn.closest('.wc-bolao-item');
    if (!item || !matchNum) return;

    const inputA = item.querySelector('.wc-bolao-input[data-side="a"]');
    const inputB = item.querySelector('.wc-bolao-input[data-side="b"]');
    if (!inputA || !inputB) return;

    const ga = parseInt(inputA.value, 10);
    const gb = parseInt(inputB.value, 10);
    if (isNaN(ga) || isNaN(gb) || ga < 0 || gb < 0) {
      inputA.focus();
      inputA.style.borderColor = 'var(--wc-live)';
      return;
    }

    const picks = readBolao();
    picks[matchNum] = { golsA: ga, golsB: gb, points: null };
    writeBolao(picks);

    // Feedback no botão
    const original = btn.textContent;
    btn.textContent = '✓ salvo';
    btn.disabled = true;
    setTimeout(() => {
      btn.textContent = 'atualizar';
      btn.disabled = false;
    }, 1200);

    renderBolaoScore({ ok: true, data: { matches: WC_STATE.matches } });
  }

  /** Acerto exato = 3pts; acerto só do vencedor (ou empate) = 1pt; senão 0. */
  function computeBolaoPoints(pick, ft) {
    if (!ft || !pick) return 0;
    const ga = Number(pick.golsA);
    const gb = Number(pick.golsB);
    if (isNaN(ga) || isNaN(gb)) return 0;
    if (ga === ft[0] && gb === ft[1]) return 3;
    const pickWinner = ga > gb ? 1 : (gb > ga ? 2 : 0);
    const realWinner = ft[0] > ft[1] ? 1 : (ft[1] > ft[0] ? 2 : 0);
    return pickWinner === realWinner ? 1 : 0;
  }

  function renderBolaoScore(result) {
    const totalEl = $('#wc-bolao-total');
    const listEl = $('#wc-bolao-score-list');
    if (!totalEl || !listEl) return;

    const picks = readBolao();
    const matches = (result.ok && result.data && Array.isArray(result.data.matches)) ? result.data.matches : [];

    // Computa apenas picks de partidas finalizadas
    const computed = Object.keys(picks).map(numStr => {
      const m = matches.find(mm => String(mm.num) === String(numStr));
      const pick = picks[numStr];
      if (!m) return null;
      const ft = (m.score && Array.isArray(m.score.ft) && m.score.ft.length === 2) ? m.score.ft : null;
      const isFinished = m.status === 'finished' || ft;
      if (!isFinished) return null;
      const pts = computeBolaoPoints(pick, ft);
      return { num: Number(numStr), match: m, pick, pts, ft };
    }).filter(Boolean);

    const total = computed.reduce((acc, r) => acc + r.pts, 0);
    totalEl.textContent = String(total);

    if (!computed.length) {
      listEl.innerHTML = `<li class="wc-loading mono-label">sem palpites computados ainda</li>`;
      return;
    }

    listEl.innerHTML = computed
      .sort((a, b) => b.pts - a.pts)
      .map(r => {
        const ptsCls = r.pts === 3 ? 'wc-bolao-score__pts--exact'
                     : r.pts === 1 ? 'wc-bolao-score__pts--winner' : '';
        const t1 = r.match.team1 || {};
        const t2 = r.match.team2 || {};
        const name = `${t1.code || t1.name || '?'} v ${t2.code || t2.name || '?'}`;
        const pick = `${r.pick.golsA}×${r.pick.golsB}`;
        const real = r.ft ? `${r.ft[0]}×${r.ft[1]}` : '—';
        return `
          <li class="wc-bolao-score__row">
            <span>${escapeHtml(name)}</span>
            <span title="seu palpite / placar real">${escapeHtml(pick)} / ${real}</span>
            <span class="wc-bolao-score__pts ${ptsCls}">+${r.pts}</span>
          </li>`;
      }).join('');
  }

  /* ════════════════════════════════════════════════════════
   * [Filtro] Minha Seleção — chips + highlight/dim
   * ════════════════════════════════════════════════════════ */
  const FILTER_KEY = 'wc-filter';
  // Lista de seleções candidatas (códigos ISO/OF). Suficiente para destaque.
  // Populada dinamicamente a partir de partidas + grupos ao render.
  function setupTeamFilter() {
    const host = $('#wc-team-filter');
    const chips = $('#wc-team-filter-chips');
    if (!host || !chips) return;

    // Coleta seleções únicas (nome + flag + code) das partidas.
    const teams = {};
    (WC_STATE.matches || []).forEach(m => {
      [m.team1, m.team2].forEach(t => {
        if (!t || !t.name || t.name === 'A definir') return;
        const key = t.code || t.name;
        if (!teams[key]) teams[key] = { name: t.name, code: t.code || '', flag: t.flag || '' };
      });
    });
    const arr = Object.values(teams).sort((a, b) => a.name.localeCompare(b.name));
    if (!arr.length) { host.hidden = true; return; }

    host.hidden = false;
    renderTeamChips(chips, arr);
    wireTeamChips(chips, arr);

    // Estado inicial: aplica filtro salvo
    let saved = '';
    try { saved = localStorage.getItem(FILTER_KEY) || ''; } catch (e) {}
    if (saved) applyTeamFilter(saved, arr);
  }

  function renderTeamChips(container, arr) {
    let saved = '';
    try { saved = localStorage.getItem(FILTER_KEY) || ''; } catch (e) {}

    container.innerHTML = arr.map(t => {
      const pressed = !!(saved && saved === (t.code || t.name));
      const flag = t.flag ? `<span class="wc-team-chip__flag" aria-hidden="true">${escapeHtml(t.flag)}</span>` : '';
      return `<button type="button" class="wc-team-chip" data-team="${escapeHtml(t.code || t.name)}" aria-pressed="${pressed}">${flag}<span>${escapeHtml(t.name)}</span></button>`;
    }).join('') + (saved ? `<button type="button" class="wc-team-chip__clear" id="wc-team-filter-clear">limpar filtro ✕</button>` : '');
  }

  function wireTeamChips(container, arr) {
    $$('.wc-team-chip', container).forEach(chip => {
      chip.addEventListener('click', () => {
        const team = chip.dataset.team;
        const isPressed = chip.getAttribute('aria-pressed') === 'true';
        try {
          if (isPressed) localStorage.removeItem(FILTER_KEY);
          else localStorage.setItem(FILTER_KEY, team);
        } catch (e) {}
        renderTeamChips(container, arr);
        applyTeamFilter(isPressed ? '' : team, arr);
        wireTeamChips(container, arr);
      });
    });
    const clear = $('#wc-team-filter-clear', container);
    if (clear) {
      clear.addEventListener('click', () => {
        try { localStorage.removeItem(FILTER_KEY); } catch (e) {}
        renderTeamChips(container, arr);
        applyTeamFilter('', arr);
        wireTeamChips(container, arr);
      });
    }
  }

  function applyTeamFilter(name, arr) {
    const team = arr ? arr.find(t => (t.code || t.name) === name) : null;
    const keyword = team ? team.name.toLowerCase() : '';
    const code = (team && team.code) ? team.code.toLowerCase() : '';

    // Partidas
    $$('.wc-match').forEach(el => {
      if (!name) {
        el.classList.remove('is-highlighted', 'is-dimmed');
        return;
      }
      const t1 = (el.dataset.team1 || '').toLowerCase();
      const t2 = (el.dataset.team2 || '').toLowerCase();
      const t1c = (el.dataset.team1Code || '').toLowerCase();
      const t2c = (el.dataset.team2Code || '').toLowerCase();
      const hit = t1 === keyword || t2 === keyword || t1c === code || t2c === code;
      el.classList.toggle('is-highlighted', hit);
      el.classList.toggle('is-dimmed', !hit);
    });

    // Notícias (highlight por keyword no título)
    $$('.wc-news-link').forEach(el => {
      if (!name) {
        el.classList.remove('is-highlighted', 'is-dimmed');
        return;
      }
      const txt = (el.textContent || '').toLowerCase();
      const hit = keyword && txt.includes(keyword);
      el.classList.toggle('is-highlighted', hit);
      el.classList.toggle('is-dimmed', !hit);
    });
  }

  /* ════════════════════════════════════════════════════════
   * [05] Jogo — Quem é o Craque?
   * ════════════════════════════════════════════════════════ */
  const GAME = {
    players: [],
    current: null, // [a, b]
  };

  function pickTwoPlayers(players) {
    if (!players || players.length < 2) return null;
    const eligible = players.filter(p => p && p.id && p.name);
    if (eligible.length < 2) return null;
    let a = eligible[Math.floor(Math.random() * eligible.length)];
    let b = eligible[Math.floor(Math.random() * eligible.length)];
    let guard = 0;
    while (b.id === a.id && guard < 20) {
      b = eligible[Math.floor(Math.random() * eligible.length)];
      guard++;
    }
    if (b.id === a.id) return null;
    // Embaralha a ordem de exibição
    return Math.random() < 0.5 ? [a, b] : [b, a];
  }

  function readVotes() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return {};
      const obj = JSON.parse(raw);
      return (obj && typeof obj === 'object') ? obj : {};
    } catch (e) {
      console.warn('[WC] localStorage corrompido, resetando:', e);
      return {};
    }
  }

  function writeVotes(votes) {
    try { localStorage.setItem(LS_KEY, JSON.stringify(votes)); }
    catch (e) { console.warn('[WC] não foi possível salvar votos:', e); }
  }

  function vote(winnerId, loserId) {
    const votes = readVotes();
    const ensure = (id) => {
      if (!votes[id]) votes[id] = { wins: 0, losses: 0, matches: 0 };
      return votes[id];
    };
    ensure(winnerId).wins++;
    ensure(winnerId).matches++;
    ensure(loserId).losses++;
    ensure(loserId).matches++;
    writeVotes(votes);
  }

  /** Ranking local: [{ player, wins, losses, matches, winrate }], top N por winrate. */
  function getLocalRanking(topN) {
    const votes = readVotes();
    const ids = Object.keys(votes).filter(id => votes[id].matches > 0);
    if (!ids.length) return [];

    const rows = ids.map(id => {
      const v = votes[id];
      const player = GAME.players.find(p => p.id === id);
      const winrate = v.matches > 0 ? v.wins / v.matches : 0;
      return {
        id,
        name: player ? player.name : id,
        team: player && player.team ? player.team : null,
        wins: v.wins,
        losses: v.losses,
        matches: v.matches,
        winrate,
      };
    });

    // Ordena: winrate desc, depois matches desc (desempate por experiência)
    rows.sort((a, b) =>
      (b.winrate - a.winrate) || (b.matches - a.matches));

    return typeof topN === 'number' ? rows.slice(0, topN) : rows;
  }

  function playerCardHtml(p, side) {
    const team = p.team || {};
    const flag = team.flag ? escapeHtml(team.flag) : '';
    const flagCell = flag
      ? `<span class="wc-player-card__flag" aria-hidden="true">${flag}</span>`
      : `<span class="wc-player-card__flag wc-flag--empty" aria-hidden="true">⚽</span>`;

    const posMap = { FW: 'Atacante', MF: 'Meia', DF: 'Zagueiro', GK: 'Goleiro' };
    const pos = posMap[p.position] || p.position || '';

    // Sem aria-label explícito: o nome acessível do botão vem do texto
    // visível (nome + seleção + posição + gols + CTA), o que satisfaz
    // WCAG 2.5.3 Label in Name — todo texto visível está no nome.
    // A flag-emoji é aria-hidden então não polui o nome.
    return `
      <button type="button" class="wc-player-card" data-side="${side}" data-id="${escapeHtml(p.id)}">
        ${flagCell}
        <span class="wc-player-card__name">${escapeHtml(p.name)}</span>
        <span class="wc-player-card__meta">
          <span>${escapeHtml(team.name || '')}${team.code ? ' · ' + escapeHtml(team.code) : ''}</span>
          ${pos ? `<span>${escapeHtml(pos)}${p.goals != null ? ' · ' + p.goals + ' gol(s)' : ''}</span>` : ''}
        </span>
        <span class="wc-player-card__stat">
          <span class="wc-player-card__goals">${p.goals != null ? p.goals : '—'}</span>
          <span class="wc-player-card__goals-label">gols na Copa</span>
        </span>
        <span class="wc-player-card__cta">▸ votar neste jogador</span>
      </button>`;
  }

  function renderDuel(entering) {
    const host = $('#wc-game-duel');
    if (!host) return;

    if (!GAME.players.length) {
      host.innerHTML = `<p class="wc-game__empty">jogadores indisponíveis</p>`;
      return;
    }

    const pair = pickTwoPlayers(GAME.players);
    if (!pair) {
      host.innerHTML = `<p class="wc-game__empty">Não há jogadores suficientes para o duelo.</p>`;
      return;
    }
    GAME.current = pair;

    host.classList.toggle('is-entering', !!entering);
    host.innerHTML =
      playerCardHtml(pair[0], 'a') +
      playerCardHtml(pair[1], 'b');

    // Limpa a flag de "entering" depois da animação
    if (entering) {
      setTimeout(() => host.classList.remove('is-entering'), 400);
    }

    // Wiring dos cliques
    $$('.wc-player-card', host).forEach(btn => {
      btn.addEventListener('click', onPlayerVote);
      btn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onPlayerVote({ currentTarget: btn });
        }
      });
    });
  }

  function onPlayerVote(e) {
    const btn = e.currentTarget;
    const winnerId = btn.dataset.id;
    const loser = GAME.current && GAME.current.find(p => p.id !== winnerId);
    if (!loser) return;

    const host = $('#wc-game-duel');
    if (host) host.classList.add('is-voting');

    const next = () => {
      vote(winnerId, loser.id);
      if (host) host.classList.remove('is-voting');
      renderDuel(true);
      // Atualiza ranking se o modal estiver aberto
      if (!$('#wc-ranking-modal').hidden) renderLocalRanking();
    };

    if (prefersReducedMotion()) {
      next();
    } else {
      setTimeout(next, 260);
    }
  }

  function renderLocalRanking() {
    const list = $('#wc-ranking-list');
    if (!list) return;

    const rows = getLocalRanking(10);
    if (!rows.length) {
      list.innerHTML = `<li class="wc-loading mono-label">0 votos — comece a jogar!</li>`;
      return;
    }

    list.innerHTML = rows.map((r, i) => {
      const flag = r.team && r.team.flag ? escapeHtml(r.team.flag) : '';
      const teamCode = r.team && r.team.code ? escapeHtml(r.team.code) : '';
      const flagCell = flag
        ? `<span class="wc-prob-row__flag" aria-hidden="true" style="font-size:var(--text-lg)">${flag}</span>`
        : '';
      return `
        <li class="wc-ranking-row">
          <span class="wc-ranking-row__rank">${i + 1}</span>
          <span class="wc-ranking-row__name">
            ${flagCell}
            <span class="wc-ranking-row__name-text">${escapeHtml(r.name)}</span>
          </span>
          <span class="wc-ranking-row__team">${teamCode} · ${r.wins}V-${r.losses}D</span>
          <span class="wc-ranking-row__winrate">${(r.winrate * 100).toFixed(0)}%</span>
        </li>`;
    }).join('');
  }

  function setupGame(jogadores) {
    if (!jogadores.ok || !jogadores.data || !Array.isArray(jogadores.data.players)) {
      const host = $('#wc-game-duel');
      if (host) host.innerHTML = `<p class="wc-game__empty">jogadores indisponíveis</p>`;
      return;
    }
    // Só jogadores com ao menos 1 gol (duelos fazem sentido)
    GAME.players = jogadores.data.players.filter(p => p && p.id && p.name && (p.goals || 0) >= 1);

    // Initial render is instant (no fade-in) to avoid contrast failures
    // during the brief animation window. Transitions between duels use
    // the fade-in (entering=true) which is fine since those are user-triggered.
    renderDuel(false);

    $('#wc-game-skip')?.addEventListener('click', () => renderDuel(true));

    const rankingBtn   = $('#wc-game-ranking');
    const rankingModal = $('#wc-ranking-modal');

    rankingBtn?.addEventListener('click', () => {
      renderLocalRanking();
      ModalController.open(rankingModal, rankingBtn);
    });
    $$('[data-close-modal]', rankingModal).forEach(el =>
      el.addEventListener('click', () => ModalController.close(rankingModal)));

    // Reset
    $('#wc-ranking-reset')?.addEventListener('click', () => {
      if (Object.keys(readVotes()).length === 0) return;
      const ok = window.confirm('Apagar todos os seus votos locais? Esta ação não pode ser desfeita.');
      if (ok) {
        writeVotes({});
        renderLocalRanking();
      }
    });
  }

  /* ════════════════════════════════════════════════════════
   * Motion — IntersectionObserver reveal + count-up
   * ════════════════════════════════════════════════════════ */
  let _revealObserver = null;

  function observeReveals(root) {
    if (prefersReducedMotion()) {
      // Sem animação: marca tudo como visível
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

  function setupCountUp() {
    const targets = $$('[data-count-to]');
    if (!targets.length) return;

    if (prefersReducedMotion()) {
      targets.forEach(el => finalizeCount(el));
      return;
    }

    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          animateCount(entry.target);
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.4 });

    targets.forEach(el => {
      // Evita flutuar "—" antes da animação começar
      if (!el.textContent.trim() || el.textContent.trim() === '—') {
        el.textContent = '0';
      }
      io.observe(el);
    });
  }

  function finalizeCount(el) {
    const target = parseFloat(el.dataset.countTo || '0');
    const decimals = parseInt(el.dataset.countDecimals || '0', 10);
    const suffix = el.dataset.countSuffix || '';
    el.textContent = formatNumber(target, decimals) + suffix;
  }

  function animateCount(el) {
    const target = parseFloat(el.dataset.countTo || '0');
    const decimals = parseInt(el.dataset.countDecimals || '0', 10);
    const suffix = el.dataset.countSuffix || '';
    const duration = 900;
    const start = performance.now();

    function tick(now) {
      const t = Math.min(1, (now - start) / duration);
      // easeOutCubic
      const eased = 1 - Math.pow(1 - t, 3);
      const value = target * eased;
      el.textContent = formatNumber(value, decimals) + suffix;
      if (t < 1) requestAnimationFrame(tick);
      else el.textContent = formatNumber(target, decimals) + suffix;
    }
    requestAnimationFrame(tick);
  }

  function formatNumber(value, decimals) {
    const v = Number(value) || 0;
    if (decimals > 0) return v.toFixed(decimals).replace('.', ',');
    return Math.round(v).toLocaleString('pt-BR');
  }

  /* ════════════════════════════════════════════════════════
   * Init
   * ════════════════════════════════════════════════════════ */
  async function init() {
    // Motion setup independente do fetch (revela o esqueleto imediatamente)
    observeReveals(document);
    setupCountUp();

    // 9 fetches em paralelo (6 originais, probabilidades→simulacao; +3 novos)
    const names = [
      'partidas', 'artilheiros', 'estatisticas', 'simulacao', 'jogadores', 'noticias',
      'grupos', 'selecao_copa', 'insights'
    ];
    const settled = await Promise.allSettled(
      names.map(n => loadJSON(n))
    );
    // Normaliza para o mesmo shape {ok, data} que as funções esperam
    const results = settled.map(r =>
      r.status === 'fulfilled' ? r.value : { ok: false, error: r.reason, data: null }
    );
    const [partidas, artilheiros, estatisticas, simulacao, jogadores, noticias,
           grupos, selecaoCopa, insights] = results;

    // Freshness usa updated_at de todos
    renderFreshness(results);

    // KPIs do hero (depende de 3 JSONs)
    renderHeroKPIs({ partidas, artilheiros, estatisticas });

    // Seções (cada uma é resiliente — fallback gracioso)
    renderNews(noticias);
    renderScorers(artilheiros);
    renderStats(estatisticas);        // inicializa os 3 charts
    renderProbabilities(simulacao);   // [04] agora Monte Carlo
    renderGroups(grupos);             // [05]
    renderBracket(partidas);          // [06]
    renderSelection(selecaoCopa);     // [07]
    renderInsights(insights);         // [08]
    // Jogo (independente)
    setupGame(jogadores);             // [09]
    renderMatches(partidas);          // [10]
    renderBolao(partidas);            // [11]

    /* ── Modal Monte Carlo: metodologia ── */
    const mcBtn   = $('#wc-mc-info-btn');
    const mcModal = $('#wc-mc-modal');
    mcBtn?.addEventListener('click', () => {
      // Evita empilhar dois modais com backdrop-filter (custo GPU + foco ambíguo)
      const rankingModal = $('#wc-ranking-modal');
      if (ModalController.isOpen(rankingModal)) ModalController.close(rankingModal);
      ModalController.open(mcModal, mcBtn);
    });
    $$('[data-close-modal]', mcModal).forEach(el =>
      el.addEventListener('click', () => ModalController.close(mcModal)));

    /* ── Nudge único do ícone de info ao entrar na viewport (uma vez) ── */
    if (mcBtn && !prefersReducedMotion() && 'IntersectionObserver' in window) {
      const nudge = new IntersectionObserver((entries, obs) => {
        entries.forEach(en => {
          if (en.isIntersecting) {
            mcBtn.classList.add('is-nudged');
            mcBtn.addEventListener('animationend',
              () => mcBtn.classList.remove('is-nudged'), { once: true });
            obs.unobserve(mcBtn);
          }
        });
      }, { threshold: 0.6 });
      nudge.observe(mcBtn);
    }

    // Filtro "Minha Seleção" (depois das partidas renderizadas)
    setupTeamFilter();

    // Reobserva reveals injetados via innerHTML
    observeReveals(document);
    // Dispara count-up dos KPIs que acabaram de ser populados
    setupCountUp();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
