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
   * [04] Render — Probabilidades (Elo)
   * ════════════════════════════════════════════════════════ */
  function renderProbabilities(result) {
    const list = $('#wc-prob-list');
    const method = $('#wc-prob-method');
    if (!list) return;

    if (!result.ok || !result.data || !Array.isArray(result.data.teams) || !result.data.teams.length) {
      list.innerHTML = `<li class="wc-error mono-label">probabilidades indisponíveis</li>`;
      return;
    }

    if (method && result.data.methodology) {
      method.textContent = `metodologia: ${result.data.methodology}`;
    }

    const top = result.data.teams.slice(0, 12);
    // Elo relativo ao líder (para largura da barra visual)
    const maxElo = Math.max.apply(null, top.map(t => Number(t.elo) || 0));
    const minElo = Math.min.apply(null, top.map(t => Number(t.elo) || 0));
    const eloRange = Math.max(1, maxElo - minElo);

    list.innerHTML = top.map((t, i) => {
      const isTop = i === 0;
      const elo = Number(t.elo) || 0;
      const pct = Number(t.win_probability) || 0;
      // Largura relativa ao líder: garante que o #1 = 100% e os demais escalam.
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
              <span class="wc-prob-row__bar" data-width="${widthPct}" style="width:0%"></span>
            </div>
          </div>
          <span class="wc-prob-row__pct" title="probabilidade de título (softmax)">${pct.toFixed(2)}%</span>
        </li>`;
    }).join('');

    // Anima as barras (largura alvo) — respeitando reduced-motion
    const motion = !prefersReducedMotion();
    $$('.wc-prob-row__bar', list).forEach((bar, i) => {
      const target = bar.dataset.width + '%';
      if (motion) {
        // stagger leve
        setTimeout(() => { bar.style.width = target; }, 80 + i * 40);
      } else {
        bar.style.transition = 'none';
        bar.style.width = target;
      }
    });

    // Observa os novos [data-reveal] injetados
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
    const pending = !ft;

    const team1Flag = flagHtml(t1.flag, '—');
    const team2Flag = flagHtml(t2.flag, '—');
    const team1Name = escapeHtml(t1.name || 'A definir');
    const team2Name = escapeHtml(t2.name || 'A definir');
    const isPh1 = !t1.name || t1.name === 'A definir';
    const isPh2 = !t2.name || t2.name === 'A definir';

    const scoreHtml = pending
      ? `<span class="wc-match__score wc-match__score--pending">vs</span>`
      : `<span class="wc-match__score">
           <span class="wc-match__score-num">${ft[0]}</span>
           <span class="wc-match__score-sep">–</span>
           <span class="wc-match__score-num">${ft[1]}</span>
         </span>`;

    const todayBadge = isToday ? `<span class="wc-match__today-badge" aria-label="Jogo de hoje">Hoje</span>` : '';

    const dateTxt = shortDate(m.date);
    const timeTxt = m.time ? escapeHtml(m.time) : '';
    const roundTxt = m.round ? escapeHtml(m.round) : (m.group && m.group !== 'null' ? escapeHtml(m.group) : '');
    const groundTxt = m.ground ? escapeHtml(m.ground) : '';

    return `
      <li class="${cls.join(' ')}">
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

    renderDuel(true);

    $('#wc-game-skip')?.addEventListener('click', () => renderDuel(true));

    const rankingBtn = $('#wc-game-ranking');
    const modal = $('#wc-ranking-modal');

    /* ── Foco preso dentro do modal (WCAG 2.4.3 + aria-modal) ── */
    // Memoriza quem abriu o modal para devolver o foco ao fechar.
    let lastFocusedBeforeOpen = null;

    function getModalFocusables() {
      if (!modal) return [];
      // Seletores de elementos focáveis visíveis dentro do modal
      return $$('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])', modal)
        .filter(el => !el.hasAttribute('disabled')
                   && !el.hidden
                   && el.offsetParent !== null
                   && el.getAttribute('aria-hidden') !== 'true');
    }

    function openModal(trigger) {
      lastFocusedBeforeOpen = trigger || document.activeElement;
      renderLocalRanking();
      modal.hidden = false;
      // Move o foco para o primeiro focável (botão Fechar) — a11y
      setTimeout(() => {
        const focusables = getModalFocusables();
        if (focusables.length) focusables[0].focus({ preventScroll: true });
      }, 30);
    }

    function closeModal() {
      modal.hidden = true;
      if (lastFocusedBeforeOpen && typeof lastFocusedBeforeOpen.focus === 'function') {
        lastFocusedBeforeOpen.focus({ preventScroll: true });
      } else {
        rankingBtn?.focus({ preventScroll: true });
      }
      lastFocusedBeforeOpen = null;
    }

    rankingBtn?.addEventListener('click', () => openModal(rankingBtn));

    // Fecha o modal: backdrop, botão X
    $$('[data-close-modal]', modal).forEach(el =>
      el.addEventListener('click', closeModal));

    // Escape fecha + Tab preso dentro do modal (focus trap)
    document.addEventListener('keydown', (e) => {
      if (modal.hidden) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        closeModal();
        return;
      }
      if (e.key === 'Tab') {
        const focusables = getModalFocusables();
        if (!focusables.length) return;
        const first = focusables[0];
        const last  = focusables[focusables.length - 1];
        const active = document.activeElement;
        if (e.shiftKey) {
          // Shift+Tab no primeiro → vai para o último (wrap)
          if (active === first || !modal.contains(active)) {
            e.preventDefault();
            last.focus({ preventScroll: true });
          }
        } else {
          // Tab no último → volta para o primeiro (wrap)
          if (active === last) {
            e.preventDefault();
            first.focus({ preventScroll: true });
          }
        }
      }
    });

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

    // 6 fetches em paralelo
    const names = ['partidas', 'artilheiros', 'estatisticas', 'probabilidades', 'jogadores', 'noticias'];
    const settled = await Promise.allSettled(
      names.map(n => loadJSON(n))
    );
    // Normaliza para o mesmo shape {ok, data} que as funções esperam
    const results = settled.map(r =>
      r.status === 'fulfilled' ? r.value : { ok: false, error: r.reason, data: null }
    );
    const [partidas, artilheiros, estatisticas, probabilidades, jogadores, noticias] = results;

    // Freshness usa updated_at de todos
    renderFreshness(results);

    // KPIs do hero (depende de 3 JSONs)
    renderHeroKPIs({ partidas, artilheiros, estatisticas });

    // Seções (cada uma é resiliente — fallback gracioso)
    renderNews(noticias);
    renderScorers(artilheiros);
    renderStats(estatisticas);   // inicializa os 3 charts
    renderProbabilities(probabilidades);
    renderMatches(partidas);

    // Jogo (independente)
    setupGame(jogadores);

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
