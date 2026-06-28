/**
 * Padrão 4: smooth-scroll — inicialização de Lenis + GSAP
 * Executar UMA ÚNICA VEZ no BaseLayout.astro.
 * Fonte: .claude/skills/web-motion.md
 *
 * Ordem obrigatória:
 * 1. Verificar prefers-reduced-motion → abortar se true
 * 2. Criar Lenis
 * 3. Sincronizar RAF com GSAP ticker
 * 4. Proxy ScrollTrigger → Lenis
 */

import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export function initMotion(): Lenis | undefined {
  // prefers-reduced-motion: sem smooth scroll, sem animações GSAP
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const lenis = new Lenis({
    lerp: 0.08,
    smoothWheel: true,
    syncTouch: false, // não em touch — evita conflito com iOS momentum scroll
  });

  // Sincronizar RAF do Lenis com o ticker do GSAP (web-motion.md)
  gsap.ticker.add((time) => lenis.raf(time * 1000));
  // Evitar saltos quando aba volta ao foco (web-motion.md guardrail)
  gsap.ticker.lagSmoothing(0);

  // Proxy para ScrollTrigger ler posição do scroll via Lenis
  ScrollTrigger.scrollerProxy(document.documentElement, {
    scrollTop: () => lenis.scroll,
    getBoundingClientRect: () => ({
      top: 0,
      left: 0,
      width: window.innerWidth,
      height: window.innerHeight,
    }),
  });

  lenis.on('scroll', ScrollTrigger.update);

  // Expor para scroll programático (navegação por menu → fireQueryLoader)
  (window as Window & { __lenis?: Lenis }).__lenis = lenis;

  return lenis;
}
