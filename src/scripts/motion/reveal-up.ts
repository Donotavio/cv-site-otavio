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
import { registerCleaner } from './cleanup';

gsap.registerPlugin(ScrollTrigger);

export function revealUp(
  elements: Element | Element[] | NodeListOf<Element>,
  container: Element,
  stagger: number = STAGGER.normal,
): void {
  if (!motionOk) return;

  // gsap.context() rastreia o tween + ScrollTrigger para teardown limpo em
  // SPA / view transitions. ctx.revert() mata ambos de uma vez.
  const ctx = gsap.context(() => {
    gsap.from(elements, {
      opacity: 0,
      y: 32,
      duration: DURATIONS.normal,
      ease: EASINGS.out, // expo.out — desaceleração longa, feel premium
      stagger,
      scrollTrigger: {
        trigger: container,
        start: 'top 88%',
        once: true, // sem re-trigger (web-motion.md guardrail)
      },
    });
  });
  registerCleaner(() => ctx.revert());
}
