/**
 * Padrão 2: hairline-draw
 * Linha de 1px cresce da esquerda para a direita ao scroll.
 * Fonte: .claude/skills/web-motion.md
 *
 * Usar em: separadores de seção, após títulos H2 principais.
 * O elemento alvo deve ter: width:100%; height:1px; transform-origin: left center
 */

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { DURATIONS, EASINGS, motionOk } from './constants';

gsap.registerPlugin(ScrollTrigger);

export function hairlineDraw(line: Element, trigger: Element) {
  if (!motionOk) return;

  gsap.from(line, {
    scaleX: 0,
    transformOrigin: 'left center',
    duration: DURATIONS.slow,
    ease: EASINGS.outStrong,
    scrollTrigger: {
      trigger,
      start: 'top 80%',
      once: true,
    },
  });
}
