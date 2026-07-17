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
 *
 * Robustez:
 * - Guard de idempotência: initMotion() chamado duas vezes não cria duas
 *   instâncias de Lenis nem dois callbacks no ticker (evita double-RAF).
 * - Teardown via cleanup.ts: destroyAllMotion() remove o ticker callback,
 *   destrói o Lenis e mata todos os ScrollTriggers em pagehide /
 *   astro:before-swap (defensivo para view transitions futuras).
 */

import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { wireLifecycleTeardown } from './motion/cleanup';

gsap.registerPlugin(ScrollTrigger);

// Guard de idempotência: initMotion() só cria uma instância mesmo se chamado
// várias vezes (defesa contra re-montagem / scripts duplicados).
let activeLenis: Lenis | null = null;

export function initMotion(): Lenis | undefined {
  // prefers-reduced-motion: sem smooth scroll, sem animações GSAP
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    // Mesmo sem motion, conectamos o teardown do ciclo de vida (defensivo).
    wireLifecycleTeardown();
    return;
  }

  // Já inicializado — não recriar (evita double-RAF / instâncias órfãs).
  if (activeLenis) return activeLenis;

  const lenis = new Lenis({
    lerp: 0.08,
    smoothWheel: true,
    syncTouch: false, // não em touch — evita conflito com iOS momentum scroll
    // wheelMultiplier/touchMultiplier mantêm o default (1) — feel calmo já
    // garantido pelo lerp 0.08. Aumentar causaria "saltos" pouco premium.
  });
  activeLenis = lenis;

  // Sincronizar RAF do Lenis com o ticker do GSAP (web-motion.md)
  const tickerCb = (time: number) => lenis.raf(time * 1000);
  gsap.ticker.add(tickerCb);
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

  const onScroll = () => ScrollTrigger.update();
  lenis.on('scroll', onScroll);

  // Expor para scroll programático (navegação por menu → fireQueryLoader)
  (window as Window & { __lenis?: Lenis }).__lenis = lenis;

  // ── Teardown do Lenis SÓ no unload real (pagehide) ──────────
  // O Lenis, o proxy do ScrollTrigger, o ticker e o listener de scroll são
  // criados UMA vez e PERSISTEM entre navegações SPA (ClientRouter). Destruí-
  // los no astro:before-swap (como um cleaner central) recriava o Lenis a cada
  // página e dessincronizava o scrollerProxy: `ScrollTrigger.scroll()` passava
  // a ler 0 enquanto o Lenis vivo estava rolado → seções com reveal-up ficavam
  // presas em opacity:0 ao re-entrar via navegação SPA. Por isso NÃO usamos o
  // registro central aqui — só desmontamos no pagehide (o contexto JS morre no
  // reload de verdade; os ScrollTriggers por-página já são revertidos pelos
  // seus próprios gsap.context() em astro:before-swap). O guard `activeLenis`
  // faz initMotion() sair cedo nas navegações seguintes (sem recriar).
  const teardownLenis = () => {
    try { lenis.off('scroll', onScroll); } catch { /* noop */ }
    try { gsap.ticker.remove(tickerCb); } catch { /* noop */ }
    try { lenis.destroy(); } catch { /* noop */ }
    activeLenis = null;
    (window as Window & { __lenis?: Lenis }).__lenis = undefined;
  };
  window.addEventListener('pagehide', teardownLenis, { once: true });

  // Conecta destroyAllMotion a pagehide / astro:before-swap (uma única vez) —
  // isso reverte os gsap.context() dos padrões por-página (reveal-up, hairline,
  // count-up, etc.), mas não toca no Lenis persistente acima.
  wireLifecycleTeardown();

  return lenis;
}
