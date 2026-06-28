/**
 * Padrão 5: resolve
 * Entrance sequencial do hero — executa uma única vez no load.
 * Fonte: .claude/skills/web-motion.md
 *
 * Seletores esperados no markup:
 *   [data-hero-eyebrow]   — overline/eyebrow acima do título
 *   [data-hero-title]     — H1 principal
 *   [data-hero-subtitle]  — subtítulo / resumo
 *   [data-hero-ctas]      — wrapper dos botões CTA
 */

import gsap from 'gsap';
import { DURATIONS, EASINGS, motionOk } from './constants';

export function resolveHero(heroEl: Element) {
  if (!motionOk) return;

  const eyebrow  = heroEl.querySelector('[data-hero-eyebrow]');
  const title    = heroEl.querySelector('[data-hero-title]');
  const subtitle = heroEl.querySelector('[data-hero-subtitle]');
  const ctas     = heroEl.querySelectorAll('[data-hero-ctas] > *');

  const tl = gsap.timeline({ delay: 0.15 });

  if (eyebrow) {
    tl.from(eyebrow, {
      opacity: 0,
      y: 12,
      duration: DURATIONS.fast,
      ease: EASINGS.out,
    });
  }

  if (title) {
    tl.from(title, {
      opacity: 0,
      y: 24,
      duration: DURATIONS.entrance,
      ease: EASINGS.outStrong,
    }, eyebrow ? '-=0.15' : 0);
  }

  if (subtitle) {
    tl.from(subtitle, {
      opacity: 0,
      y: 16,
      duration: DURATIONS.normal,
      ease: EASINGS.out,
    }, '-=0.45');
  }

  if (ctas.length) {
    tl.from(ctas, {
      opacity: 0,
      y: 12,
      duration: DURATIONS.fast,
      ease: EASINGS.out,
      stagger: 0.08,
    }, '-=0.3');
  }

  return tl;
}
