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
 *   [data-hero-portrait]  — ASCII portrait (revela com efeito scan)
 *   [data-hero-detail]    — detalhes de blueprint (labels, linhas conectoras)
 */

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { DURATIONS, EASINGS, HERO_DELAY, motionOk } from './constants';
import { registerCleaner } from './cleanup';

gsap.registerPlugin(ScrollTrigger);

export function resolveHero(heroEl: Element): void {
  if (!motionOk) return;

  const eyebrow  = heroEl.querySelector('[data-hero-eyebrow]');
  const title    = heroEl.querySelector('[data-hero-title]');
  const subtitle = heroEl.querySelector('[data-hero-subtitle]');
  const ctas     = heroEl.querySelectorAll('[data-hero-ctas] > *');
  const portrait = heroEl.querySelector<HTMLElement>('[data-hero-portrait]');
  const details  = heroEl.querySelectorAll('[data-hero-detail]');

  // gsap.context() rastreia a timeline + o ScrollTrigger de parallax para
  // teardown limpo (ctx.revert()) em SPA / view transitions.
  const ctx = gsap.context(() => {
    const tl = gsap.timeline({ delay: HERO_DELAY });

    // ASCII portrait — revela com "scan" (clip vertical de cima→baixo).
    // Animamos apenas clip-path + opacity (sem layout/paint pesado).
    if (portrait) {
      tl.fromTo(
        portrait,
        { opacity: 0, clipPath: 'inset(0 0 100% 0)' },
        {
          opacity: 1,
          clipPath: 'inset(0 0 0% 0)',
          duration: DURATIONS.entrance,
          ease: EASINGS.out,
          // limpa will-change após o scan (guardrail web-motion.md)
          onComplete: () => {
            portrait.style.willChange = 'auto';
          },
        },
        0,
      );
    }

    // Texto entra em cascata em paralelo ao scan do portrait (ambos a partir de 0).
    if (eyebrow) {
      tl.from(eyebrow, {
        opacity: 0,
        y: 12,
        duration: DURATIONS.fast,
        ease: EASINGS.out,
      }, 0);
    }

    // Posições absolutas para a cascata de texto correr em paralelo ao scan,
    // sem ser empurrada pela duração maior do portrait.
    if (title) {
      tl.from(title, {
        opacity: 0,
        y: 48, // momentum maior — feel premium (StackGrid/Mattis)
        duration: DURATIONS.entrance,
        ease: EASINGS.outStrong,
      }, 0.2);
    }

    if (subtitle) {
      tl.from(subtitle, {
        opacity: 0,
        y: 24,
        duration: DURATIONS.normal,
        ease: EASINGS.out,
      }, 0.55);
    }

    if (ctas.length) {
      tl.from(ctas, {
        opacity: 0,
        y: 12,
        duration: DURATIONS.fast,
        ease: EASINGS.out,
        stagger: 0.08,
      }, 0.85);
    }

    if (details.length) {
      tl.from(details, {
        opacity: 0,
        duration: DURATIONS.fast,
        ease: EASINGS.out,
        stagger: 0.1,
      }, 1.0);
    }

    // Parallax sutil do portrait ligado ao scroll (ref: Mattis/StackGrid).
    // Move o ASCII mais devagar que o scroll — profundidade sem distração.
    if (portrait) {
      gsap.to(portrait, {
        yPercent: -12,
        ease: 'none',
        scrollTrigger: {
          trigger: heroEl,
          start: 'top top',
          end: 'bottom top',
          scrub: true,
        },
      });
    }
  });
  registerCleaner(() => ctx.revert());
}
