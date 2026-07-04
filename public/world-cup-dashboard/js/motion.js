/*
 * motion.js — ball-level viz motion helpers (vanilla, no deps).
 * Loaded after main.js. Exposes window.WCMotion = { revealStagger,
 * crossfadeSwap, drawEdges, prefersReducedMotion }.
 */
(function () {
  'use strict';

  const prefersReducedMotion = () =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function revealStagger(items, opts) {
    const o = Object.assign({ step: 40, threshold: 0.15, rootMargin: '0px 0px -8% 0px' }, opts || {});
    let arr = Array.from(items || []);

    if (typeof o.sort === 'function') {
      const withIndex = arr.map((el, i) => ({ el, i }));
      withIndex.sort((a, b) => o.sort(a.el, b.el));
      arr = withIndex.map(x => x.el);
    }

    if (prefersReducedMotion() || typeof IntersectionObserver === 'undefined') {
      arr.forEach(el => {
        el.style.transitionDelay = '';
        el.classList.add('is-visible');
      });
      return { cancel() {} };
    }

    arr.forEach((el, i) => {
      el.style.transitionDelay = `${i * o.step}ms`;
    });

    let io;
    const cleanupFns = [];
    io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        el.classList.add('is-visible');
        const cleanup = () => {
          el.style.transitionDelay = '';
          el.removeEventListener('transitionend', cleanup);
        };
        el.addEventListener('transitionend', cleanup, { once: false });
        cleanupFns.push(() => el.removeEventListener('transitionend', cleanup));
        io.unobserve(el);
      });
    }, { threshold: o.threshold, rootMargin: o.rootMargin });

    arr.forEach(el => io.observe(el));

    return {
      cancel() {
        if (io) io.disconnect();
        cleanupFns.forEach(fn => fn());
      }
    };
  }

  function crossfadeSwap(container, render, opts) {
    const o = Object.assign({ exitMs: 180, exitClass: 'is-exiting', enterStep: 20 }, opts || {});

    if (prefersReducedMotion()) {
      render();
      return Promise.resolve();
    }

    const old = Array.from(container.children);
    old.forEach(el => el.classList.add(o.exitClass));
    return new Promise(resolve => {
      setTimeout(() => {
        render();
        const fresh = Array.from(container.children).filter(el => !el.classList.contains('is-visible'));
        if (fresh.length) {
          revealStagger(fresh, { step: o.enterStep });
        }
        resolve();
      }, o.exitMs);
    });
  }

  function drawEdges(edges, opts) {
    const o = Object.assign({ step: 15, delay: 300 }, opts || {});
    const arr = Array.from(edges || []);

    arr.forEach(e => { e.setAttribute('pathLength', '1'); });

    if (prefersReducedMotion() || typeof IntersectionObserver === 'undefined') {
      arr.forEach(e => e.classList.add('is-visible'));
      return { cancel() {} };
    }

    arr.forEach((e, i) => { e.style.transitionDelay = `${o.delay + i * o.step}ms`; });

    let io;
    io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        el.classList.add('is-visible');
        const cleanup = () => {
          el.style.transitionDelay = '';
          el.removeEventListener('transitionend', cleanup);
        };
        el.addEventListener('transitionend', cleanup);
        io.unobserve(el);
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -8% 0px' });

    arr.forEach(e => io.observe(e));
    return { cancel() { io && io.disconnect(); } };
  }

  window.WCMotion = {
    revealStagger,
    crossfadeSwap,
    drawEdges,
    prefersReducedMotion
  };
})();
