/**
 * cleanup.ts — registro central de teardown para motion.
 *
 * Cada helper de motion registra aqui um "cleaner" (callback idempotente).
 * O `motion-init.ts` conecta `pagehide` e `astro:before-swap` a
 * `destroyAllMotion()`, garantindo teardown automático em:
 *   - navegação SPA / Astro View Transitions (quando adicionadas)
 *   - troca de página (defensivo — o contexto JS morre, mas limpamos antes)
 *
 * Isso evita leaks de:
 *   - ScrollTriggers órfãos
 *   - timelines GSAP rodando em nodes detachados
 *   - event listeners (pointermove, scroll, etc.)
 *   - requestAnimationFrames pendentes
 *   - setTimeouts pendentes
 *
 * Cleaners são envolvidos em try/catch: um cleaner com bug não deve impedir
 * os demais de rodar. Idempotentes: podem ser chamados mais de vez (seguro).
 */

const cleaners = new Set<() => void>();

/** Registra um callback de teardown. Retorna uma função para desregistrar. */
export function registerCleaner(fn: () => void): () => void {
  cleaners.add(fn);
  return () => cleaners.delete(fn);
}

/** Executa TODOS os cleaners registrados e zera o registro. */
export function destroyAllMotion(): void {
  if (!cleaners.size) return;
  // Copia para iterar com segurança (cleaners podem se desregistrar).
  const snapshot = Array.from(cleaners);
  cleaners.clear();
  for (const fn of snapshot) {
    try {
      fn();
    } catch {
      // Cleaner com bug não pode travar o teardown dos demais.
    }
  }
}

/** Reseta estilos de lock aplicados por scroll-lock.ts (defensivo). */
function resetScrollLock(): void {
  if (typeof document === 'undefined') return;
  document.body.style.overflow = '';
  document.body.style.touchAction = '';
}

/** Wired uma única vez pelo motion-init: conecta teardown aos ciclos de vida. */
let lifecycleWired = false;
export function wireLifecycleTeardown(): void {
  if (lifecycleWired || typeof window === 'undefined') return;
  lifecycleWired = true;

  // pagehide: cobre unload + navegação clássica (mobile/desktop).
  window.addEventListener('pagehide', destroyAllMotion, { once: true });

  // Astro View Transitions / ClientRouter (defensivo — ainda não habilitado,
  // mas se for adicionado no futuro, o teardown já está pronto).
  document.addEventListener('astro:before-swap', destroyAllMotion);

  // Fim de página oculta (bfcache restore dispara pageshow, mas o motion-init
  // re-roda no DOMContentLoaded seguinte; aqui só garantimos limpeza na saída).
  window.addEventListener('pagehide', resetScrollLock, { once: true });
}
