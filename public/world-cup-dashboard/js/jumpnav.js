/*
 * World Cup Dashboard — jumpnav.js
 * ---------------------------------------------------------------------------
 * Navegação por seções (jump-nav):
 *   - Desktop (>= 1024px): dock vertical fixo à direita com bullets
 *   - Mobile/Tablet (< 1024px): FAB no canto inferior direito que abre
 *     um bottom sheet com a lista numerada
 *
 * Módulo ISOLADO e autossuficiente (mesmo padrão de deepstats.js): IIFE,
 * sem imports. Funciona independentemente do main.js. Coleta as <section
 * id="..." aria-labelledby="..."> da página e constrói a lista a partir
 * dos títulos (<h2>) encontrados.
 *
 * Acessibilidade:
 *   - <nav aria-label="Navegação entre seções">
 *   - aria-current="true" na seção ativa
 *   - FAB com aria-expanded/aria-controls
 *   - backdrop fecha o sheet no mobile
 *   - Esc fecha o sheet
 *   - Reduced motion: sem animações
 *
 * Performance:
 *   - IntersectionObserver para detectar seção ativa (1 observador)
 *   - requestAnimationFrame para scroll suave com fallback
 * ---------------------------------------------------------------------------
 */

'use strict';

(function () {

  /* ════════════════════════════════════════════════════════
   * Helpers
   * ════════════════════════════════════════════════════════ */
  const $  = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  const prefersReducedMotion = () =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const isMobile = () => window.matchMedia('(max-width: 1023px)').matches;

  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /* ════════════════════════════════════════════════════════
   * Coleta as seções da página
   * ════════════════════════════════════════════════════════ */
  function collectSections() {
    const sections = $$('main section[id]');
    const result = [];

    for (const sec of sections) {
      const id = sec.id;
      if (!id) continue;

      // Tenta achar o título: h2 com id referenciado por aria-labelledby,
      // depois qualquer h2, depois .wc-display, fallback para o id.
      const labelledBy = sec.getAttribute('aria-labelledby');
      let titleEl = null;
      if (labelledBy) {
        titleEl = document.getElementById(labelledBy);
      }
      if (!titleEl) {
        titleEl = sec.querySelector('h2, h1, .wc-display');
      }
      const title = titleEl ? titleEl.textContent.trim() : id;

      // Pula seções que são internas (ex.: modais, sub-blocos)
      // — Detecta por não ter heading visível ou role="dialog"
      if (sec.getAttribute('role') === 'dialog') continue;
      if (!titleEl) continue;

      // Pega posição para calcular distância do topo
      result.push({
        id,
        title,
        el: sec,
      });
    }

    return result;
  }

  /* ════════════════════════════════════════════════════════
   * Renderiza a lista
   * ════════════════════════════════════════════════════════ */
  function renderList(sections) {
    const list = $('#wc-jumpnav-list');
    if (!list) return;

    list.innerHTML = sections.map((s, idx) => {
      const num = String(idx + 1).padStart(2, '0');
      return `
        <li class="wc-jumpnav__item">
          <a href="#${escapeHtml(s.id)}"
             class="wc-jumpnav__link"
             data-target="${escapeHtml(s.id)}"
             aria-current="false">
            <span class="wc-jumpnav__label">${escapeHtml(s.title)}</span>
            <span class="wc-jumpnav__bullet" aria-hidden="true"></span>
            <span class="wc-jumpnav__num">${num}</span>
          </a>
        </li>`;
    }).join('');
  }

  /* ════════════════════════════════════════════════════════
   * Observador de seção ativa
   * ════════════════════════════════════════════════════════ */
  let _activeObserver = null;

  function setupActiveObserver(sections) {
    if (_activeObserver) _activeObserver.disconnect();

    // Marca a primeira como ativa por padrão
    setActive(sections[0]?.id);

    _activeObserver = new IntersectionObserver((entries) => {
      // Pega a entrada mais "visível" (maior intersectionRatio) que está intersecting
      const visible = entries
        .filter(e => e.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
      if (visible.length === 0) return;

      const activeId = visible[0].target.id;
      setActive(activeId);
    }, {
      // Considera "centro" da tela como ponto de ativação
      rootMargin: '-30% 0px -50% 0px',
      threshold: [0, 0.1, 0.3, 0.5, 1.0],
    });

    sections.forEach(s => _activeObserver.observe(s.el));
  }

  function setActive(id) {
    if (!id) return;
    $$('.wc-jumpnav__link').forEach(link => {
      const isActive = link.dataset.target === id;
      if (link.getAttribute('aria-current') !== String(isActive)) {
        link.setAttribute('aria-current', String(isActive));
      }
    });
  }

  /* ════════════════════════════════════════════════════════
   * Click — scroll suave com fallback
   * ════════════════════════════════════════════════════════ */
  function setupClickHandlers() {
    const list = $('#wc-jumpnav-list');
    if (!list) return;

    list.addEventListener('click', (e) => {
      const link = e.target.closest('.wc-jumpnav__link');
      if (!link) return;

      const id = link.dataset.target;
      const target = document.getElementById(id);
      if (!target) return;

      e.preventDefault();

      const reduce = prefersReducedMotion();

      try {
        target.scrollIntoView({
          behavior: reduce ? 'auto' : 'smooth',
          block: 'start',
        });
      } catch {
        // Fallback: scroll manual
        const top = target.getBoundingClientRect().top + window.pageYOffset - 80;
        window.scrollTo(0, top);
      }

      // Atualiza hash sem causar scroll nativo
      history.replaceState(null, '', '#' + id);

      // Fecha o sheet no mobile após click
      if (isMobile()) closeSheet();
    });
  }

  /* ════════════════════════════════════════════════════════
   * FAB + Sheet (mobile)
   * ════════════════════════════════════════════════════════ */
  let _backdrop = null;

  function ensureBackdrop() {
    if (_backdrop) return _backdrop;
    _backdrop = document.createElement('div');
    _backdrop.className = 'wc-jumpnav-backdrop';
    _backdrop.setAttribute('aria-hidden', 'true');
    _backdrop.addEventListener('click', closeSheet);
    document.body.appendChild(_backdrop);
    return _backdrop;
  }

  function openSheet() {
    const nav = $('#wc-jumpnav');
    const fab = $('#wc-jumpnav-fab');
    const bd = ensureBackdrop();
    if (!nav || !fab) return;
    nav.hidden = false;
    fab.setAttribute('aria-expanded', 'true');
    requestAnimationFrame(() => bd.classList.add('is-visible'));
    // Lock scroll
    document.body.style.overflow = 'hidden';
  }

  function closeSheet() {
    const nav = $('#wc-jumpnav');
    const fab = $('#wc-jumpnav-fab');
    const bd = _backdrop;
    if (!nav || !fab) return;
    fab.setAttribute('aria-expanded', 'false');
    if (bd) bd.classList.remove('is-visible');
    // Pequeno delay para a transição do backdrop
    setTimeout(() => {
      if (fab.getAttribute('aria-expanded') === 'false') {
        nav.hidden = true;
      }
    }, 250);
    document.body.style.overflow = '';
  }

  function setupFab() {
    const fab = $('#wc-jumpnav-fab');
    if (!fab) return;

    fab.addEventListener('click', () => {
      const expanded = fab.getAttribute('aria-expanded') === 'true';
      if (expanded) closeSheet();
      else openSheet();
    });

    // Esc fecha o sheet
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && fab.getAttribute('aria-expanded') === 'true') {
        closeSheet();
        fab.focus();
      }
    });
  }

  /* ════════════════════════════════════════════════════════
   * Responsivo — reseta estado ao cruzar breakpoint
   * ════════════════════════════════════════════════════════ */
  function setupResponsive() {
    const mq = window.matchMedia('(min-width: 1024px)');
    mq.addEventListener('change', (e) => {
      const nav = $('#wc-jumpnav');
      const fab = $('#wc-jumpnav-fab');
      if (!nav || !fab) return;
      if (e.matches) {
        // Desktop: dock sempre visível, fecha sheet
        nav.hidden = false;
        fab.setAttribute('aria-expanded', 'false');
        if (_backdrop) _backdrop.classList.remove('is-visible');
        document.body.style.overflow = '';
      } else {
        // Mobile: dock vira sheet, FAB fecha
        fab.setAttribute('aria-expanded', 'false');
        if (fab.getAttribute('aria-expanded') === 'false') {
          nav.hidden = true;
        }
      }
    });
  }

  /* ════════════════════════════════════════════════════════
   * Inicialização
   * ════════════════════════════════════════════════════════ */
  function init() {
    const sections = collectSections();
    if (sections.length === 0) {
      console.warn('[WCJumpnav] Nenhuma seção encontrada');
      return;
    }

    renderList(sections);
    setupClickHandlers();
    setupFab();
    setupResponsive();
    setupActiveObserver(sections);

    // Mostra os controles (começam hidden no HTML)
    const nav = $('#wc-jumpnav');
    const fab = $('#wc-jumpnav-fab');
    if (nav && isMobile()) {
      // No mobile, nav fica hidden até o FAB ser clicado
      fab.hidden = false;
    } else if (nav) {
      nav.hidden = false;
      fab.hidden = true;
    }

    // Estado inicial do hash (se vier de deep-link)
    if (location.hash) {
      const id = location.hash.slice(1);
      setActive(id);
    }
  }

  // DOMContentLoaded ou imediato
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
