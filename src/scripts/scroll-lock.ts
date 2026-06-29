/**
 * scroll-lock.ts — trava/destrava o scroll da página por trás de um modal.
 *
 * Importante: o site usa Lenis (smooth scroll programático). Apenas
 * `body.style.overflow = 'hidden'` NÃO basta — o Lenis continua processando
 * wheel/touch e rola a página atrás do modal. Precisamos parar o Lenis também.
 */

interface LenisLike {
  stop: () => void;
  start: () => void;
}

let locks = 0;

function getLenis(): LenisLike | undefined {
  return (window as unknown as { __lenis?: LenisLike }).__lenis;
}

/** Trava o scroll da página (Lenis + body). Reentrante (conta locks). */
export function lockScroll() {
  locks++;
  if (locks > 1) return;
  getLenis()?.stop();
  document.body.style.overflow = 'hidden';
  // iOS: impede o "rubber band" da página de fundo
  document.body.style.touchAction = 'none';
}

/** Destrava o scroll da página. */
export function unlockScroll() {
  locks = Math.max(0, locks - 1);
  if (locks > 0) return;
  getLenis()?.start();
  document.body.style.overflow = '';
  document.body.style.touchAction = '';
}
