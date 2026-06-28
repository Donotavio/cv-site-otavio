/**
 * Padrão 2: reveal-up
 * Revela elementos ao entrar no viewport com stagger.
 * Fonte: .claude/skills/web-motion.md
 *
 * Usar em: parágrafos, cards, listas, headings de seção.
 * Nunca usar para o hero — usar resolve.ts.
 */

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { DURATIONS, EASINGS, motionOk, STAGGER } from './constants';

gsap.registerPlugin(ScrollTrigger);

export function revealUp(
  elements: Element | Element[] | NodeListOf<Element>,
  container: Element,
  stagger: number = STAGGER.normal,
) {
  if (!motionOk) return;

  gsap.from(elements, {
    opacity: 0,
    y: 24,
    duration: DURATIONS.normal,
    ease: EASINGS.out,
    stagger,
    scrollTrigger: {
      trigger: container,
      start: 'top 85%',
      once: true, // sem re-trigger (web-motion.md guardrail)
    },
  });
}
