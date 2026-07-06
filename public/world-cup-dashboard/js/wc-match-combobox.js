/*
 * World Cup Dashboard — wc-match-combobox.js
 * ---------------------------------------------------------------------------
 * Substitui o <select class="wc-match-select"> por um combobox buscável:
 *   <input> + <button>▾ + dropdown filtrado em tempo real.
 *
 * Mantém o <select> original no DOM (escondido) como fonte da verdade —
 * deepstats.js continua populando options e ouvindo 'change'. Este
 * módulo apenas wrap-e-render o select, então é totalmente compatível.
 *
 * Acessibilidade:
 *   - role="combobox" no input, aria-expanded, aria-controls
 *   - role="listbox" no dropdown, role="option" em cada item
 *   - Navegação por teclado: ArrowUp/Down, Enter, Esc, Tab
 *   - aria-selected no item atual
 *
 * Performance:
 *   - MutationObserver detecta quando options mudam (populateSelectors)
 *   - Object.defineProperty patch value setter para sincronizar quando
 *     deepstats.js faz `select.value = X` programaticamente
 * ---------------------------------------------------------------------------
 */

'use strict';

(function () {

  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const $  = (sel, root) => (root || document).querySelector(sel);

  function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /**
   * Transforma um <select> em combobox buscável.
   * Retorna { sync } para permitir refresh manual.
   */
  function buildCombobox(select) {
    if (select.dataset.wcCombobox === '1') return null;
    select.dataset.wcCombobox = '1';

    // Container externo
    const wrap = document.createElement('div');
    wrap.className = 'wc-match-combobox';
    select.parentNode.insertBefore(wrap, select);

    // Input
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'wc-match-combobox__input';
    input.placeholder = 'Buscar partida…';
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-controls', select.id + '-listbox');
    input.setAttribute('aria-label', 'Buscar partida');
    input.autocomplete = 'off';
    input.spellcheck = false;

    // Botão toggle (▼)
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'wc-match-combobox__btn';
    btn.setAttribute('aria-label', 'Abrir lista de partidas');
    btn.setAttribute('tabindex', '-1');
    btn.innerHTML = '<span aria-hidden="true">▾</span>';

    // Lista dropdown
    const listbox = document.createElement('ul');
    listbox.className = 'wc-match-combobox__list';
    listbox.id = select.id + '-listbox';
    listbox.setAttribute('role', 'listbox');
    listbox.setAttribute('aria-label', 'Partidas disponíveis');
    listbox.hidden = true;

    // Esconde select mas mantém acessível para SR/JS
    select.classList.add('wc-match-select--hidden');

    wrap.appendChild(input);
    wrap.appendChild(btn);
    wrap.appendChild(listbox);
    wrap.appendChild(select);

    let items = [];          // [{value, label}]
    let filtered = [];       // items filtrados pelo query atual
    let highlightIdx = -1;
    let isOpen = false;

    function sync() {
      items = Array.from(select.options).map(opt => ({
        value: opt.value,
        label: opt.textContent,
      }));
      // Sincroniza input com seleção atual
      const selOpt = select.options[select.selectedIndex];
      if (selOpt && document.activeElement !== input) {
        input.value = selOpt.textContent;
      } else if (document.activeElement !== input) {
        input.value = '';
      }
      // Se a lista estiver aberta, refiltra
      if (isOpen) filter(input.value);
    }

    function filter(query) {
      const q = (query || '').toLowerCase().trim();
      // Normaliza: remove acentos para match mais flexível
      const norm = s => s.normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
      const qn = norm(q);
      filtered = qn
        ? items.filter(it => norm(it.label.toLowerCase()).includes(qn))
        : items.slice();
      highlightIdx = qn ? (filtered.length ? 0 : -1) : -1;
      render();
    }

    function render() {
      if (!filtered.length) {
        listbox.innerHTML = `<li class="wc-match-combobox__empty" role="status">Nenhuma partida encontrada</li>`;
        return;
      }
      listbox.innerHTML = filtered.map((it, i) => {
        const selected = it.value === select.value;
        const highlighted = i === highlightIdx;
        const cls = 'wc-match-combobox__option' +
          (selected ? ' is-selected' : '') +
          (highlighted ? ' is-highlighted' : '');
        return `<li role="option"
                    data-value="${escapeHtml(it.value)}"
                    data-idx="${i}"
                    aria-selected="${selected}"
                    class="${cls}">${escapeHtml(it.label)}</li>`;
      }).join('');
    }

    function open() {
      if (isOpen) return;
      isOpen = true;
      listbox.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      filter('');
      input.focus();
      input.select();
    }

    function close() {
      if (!isOpen) return;
      isOpen = false;
      listbox.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      // Restaura input para o label do selecionado
      const selOpt = select.options[select.selectedIndex];
      input.value = selOpt ? selOpt.textContent : '';
    }

    function choose(value) {
      select.value = value;
      // Avisa o deepstats.js (que escuta 'change' no select)
      select.dispatchEvent(new Event('change', { bubbles: true }));
      close();
    }

    function setHighlight(idx) {
      highlightIdx = Math.max(-1, Math.min(idx, filtered.length - 1));
      $$('[role="option"]', listbox).forEach((li, i) => {
        li.classList.toggle('is-highlighted', i === highlightIdx);
      });
      const li = $('.is-highlighted', listbox);
      if (li) li.scrollIntoView({ block: 'nearest' });
    }

    /* ── Event handlers ───────────────────────────────────── */
    input.addEventListener('focus', () => {
      if (!isOpen) open();
    });

    input.addEventListener('input', () => {
      if (!isOpen) open();
      filter(input.value);
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (!isOpen) { open(); return; }
        setHighlight(highlightIdx + 1);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlight(highlightIdx - 1);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (highlightIdx >= 0 && filtered[highlightIdx]) {
          choose(filtered[highlightIdx].value);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        close();
      } else if (e.key === 'Tab') {
        if (isOpen) close();
      }
    });

    btn.addEventListener('click', (e) => {
      e.preventDefault();
      if (isOpen) close();
      else open();
    });

    listbox.addEventListener('mousedown', (e) => {
      // Evita blur do input antes do click
      e.preventDefault();
    });

    listbox.addEventListener('click', (e) => {
      const li = e.target.closest('[role="option"]');
      if (li && li.dataset.value) choose(li.dataset.value);
    });

    // Fecha ao clicar fora ou perder foco
    document.addEventListener('mousedown', (e) => {
      if (!wrap.contains(e.target) && isOpen) close();
    });

    /* ── Observa mudanças no select (options ou value) ───── */
    // childList: detecta quando populateSelectors preenche os options
    const obs = new MutationObserver(() => sync());
    obs.observe(select, { childList: true });

    // Patch value setter para detectar `select.value = X` programático
    // (deepstats.js faz isso no onMatchChange para sincronizar selects)
    try {
      const proto = Object.getPrototypeOf(select);
      const desc = Object.getOwnPropertyDescriptor(proto, 'value') ||
                   Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
      if (desc && desc.set) {
        Object.defineProperty(select, 'value', {
          get() { return desc.get.call(this); },
          set(v) {
            desc.set.call(this, v);
            sync();
          },
          configurable: true,
        });
      }
    } catch (err) {
      // Alguns browsers podem rejeitar — fallback: polling leve
      console.warn('[WCMatchCombobox] value setter patch falhou, usando polling', err);
      setInterval(sync, 300);
    }

    // Sync inicial
    sync();

    return { sync };
  }

  /* ── Auto-init ────────────────────────────────────────── */
  function init() {
    $$('.wc-match-select').forEach(buildCombobox);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
