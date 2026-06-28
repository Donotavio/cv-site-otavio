/**
 * Padrão 3 (variação de hairline-draw): bar-grow
 * Barra de progresso fina cresce de 0 → nível ao entrar no viewport.
 * Fonte: .claude/skills/web-motion.md (Blueprint)
 *
 * É uma variação de hairline-draw: anima APENAS transform: scaleX
 * (transform-origin: left), nunca width direto (evita layout thrash).
 * A largura final (o nível %) já está aplicada via CSS inline `width`;
 * o GSAP faz o from scaleX 0 → 1.
 *
 * Usar em: barras de skill, indicadores de nível.
 * O elemento alvo (fill) deve ter: width:<nível>%; transform-origin: left center.
 *
 * Sem motion / prefers-reduced-motion: a barra já fica cheia (scaleX 1 default),
 * o helper retorna sem animar.
 */

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { DURATIONS, EASINGS, motionOk, STAGGER } from './constants';

gsap.registerPlugin(ScrollTrigger);

export function barGrow(
  fills: Element | Element[] | NodeListOf<Element>,
  trigger: Element,
  stagger: number = STAGGER.tight,
) {
  if (!motionOk) return;

  gsap.from(fills, {
    scaleX: 0,
    transformOrigin: 'left center',
    duration: DURATIONS.slow,
    ease: EASINGS.outStrong,
    stagger,
    scrollTrigger: {
      trigger,
      start: 'top 85%',
      once: true,
    },
  });
}
