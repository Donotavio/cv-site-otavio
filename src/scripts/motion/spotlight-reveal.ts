/**
 * spotlight-reveal — "lanterna" que revela a foto real sob o ASCII art.
 * Fonte: vocabulário de motion Blueprint (web-motion.md)
 *
 * Comportamento:
 *  - Por padrão exibe o ASCII art (camada superior).
 *  - Ao passar o mouse, uma máscara radial (raio configurável) acompanha o
 *    cursor e "fura" o ASCII, revelando a foto real por baixo.
 *  - Ao "chacoalhar" o mouse (vários reverses rápidos de direção), revela a
 *    foto INTEIRA por `holdMs` ms, depois volta ao ASCII.
 *
 * Técnica: a máscara é um radial-gradient cuja posição vem de CSS custom
 * properties (--mx, --my) atualizadas no mousemove. Só atualiza variáveis —
 * sem reflow. Anima opacity/mask (composited).
 *
 * Markup esperado (o componente fornece):
 *   <div data-spotlight>
 *     <div data-spotlight-ascii> ...ASCII (pre)... </div>
 *     <div data-spotlight-photo style="background-image:url(...)"></div>
 *   </div>
 *
 * Acessibilidade: puramente decorativo (a foto real acessível fica em <img sr-only>
 * no componente). Desativado em touch e em prefers-reduced-motion.
 *
 * Cleanup: retorna destroy() que remove listeners, cancela o RAF e limpa
 * timers pendentes. Também se auto-registra no cleanup central para teardown
 * automático em SPA / view transitions.
 */

import { motionOk } from './constants';
import { registerCleaner } from './cleanup';

interface SpotlightOptions {
  radius?: number;   // raio da lanterna em px (default 90)
  holdMs?: number;   // duração do reveal completo após shake (default 3000)
}

export function spotlightReveal(root: HTMLElement, opts: SpotlightOptions = {}): () => void {
  const radius = opts.radius ?? 90;
  const holdMs = opts.holdMs ?? 3000;

  const photo = root.querySelector<HTMLElement>('[data-spotlight-photo]');
  if (!photo) return noop;

  // Touch / reduced-motion: não há hover real → mantém ASCII estático.
  const noHover = window.matchMedia('(hover: none)').matches;
  if (!motionOk || noHover) return noop;

  root.style.setProperty('--spot-r', `${radius}px`);

  // ── Lanterna seguindo o cursor ──────────────────────────────
  let raf = 0;
  let pendingX = 0;
  let pendingY = 0;

  const apply = () => {
    raf = 0;
    photo.style.setProperty('--mx', `${pendingX}px`);
    photo.style.setProperty('--my', `${pendingY}px`);
  };

  const onMove = (e: PointerEvent) => {
    const rect = root.getBoundingClientRect();
    pendingX = e.clientX - rect.left;
    pendingY = e.clientY - rect.top;
    if (!fullReveal && !raf) raf = requestAnimationFrame(apply);
    trackShake(e.clientX);
  };

  const onEnter = () => { if (!fullReveal) root.classList.add('is-spotting'); };
  const onLeave = () => { root.classList.remove('is-spotting'); };

  // ── Detecção de "chacoalhar" (shake) ────────────────────────
  // Conta reversões de direção horizontal num curto período.
  let lastX = 0;
  let lastDir = 0;
  let reversals = 0;
  let shakeTimer = 0;
  let fullReveal = false;
  let revealTimer = 0;

  function trackShake(x: number) {
    const dx = x - lastX;
    lastX = x;
    if (Math.abs(dx) < 6) return; // ignora micro-movimentos
    const dir = dx > 0 ? 1 : -1;
    if (lastDir !== 0 && dir !== lastDir) {
      reversals++;
      window.clearTimeout(shakeTimer);
      shakeTimer = window.setTimeout(() => { reversals = 0; }, 400);
      if (reversals >= 4) triggerFullReveal();
    }
    lastDir = dir;
  }

  function triggerFullReveal() {
    if (fullReveal) return;
    fullReveal = true;
    reversals = 0;
    root.classList.remove('is-spotting');
    root.classList.add('is-revealed');
    window.clearTimeout(revealTimer);
    revealTimer = window.setTimeout(() => {
      fullReveal = false;
      root.classList.remove('is-revealed');
    }, holdMs);
  }

  root.addEventListener('pointermove', onMove);
  root.addEventListener('pointerenter', onEnter);
  root.addEventListener('pointerleave', onLeave);

  // ── Teardown: remove listeners, cancela RAF e limpa timers ──
  // Evita leaks em re-init (troca de idioma) e em SPA / view transitions.
  let destroyed = false;
  function destroy() {
    if (destroyed) return;
    destroyed = true;
    root.removeEventListener('pointermove', onMove);
    root.removeEventListener('pointerenter', onEnter);
    root.removeEventListener('pointerleave', onLeave);
    if (raf) cancelAnimationFrame(raf);
    window.clearTimeout(shakeTimer);
    window.clearTimeout(revealTimer);
    root.classList.remove('is-spotting', 'is-revealed');
  }
  registerCleaner(destroy);

  return destroy;
}

function noop() { /* no-op cleanup */ }
