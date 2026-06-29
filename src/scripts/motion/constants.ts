/**
 * Constantes de motion — The Architect
 * Fonte: .claude/skills/web-motion.md
 *
 * NUNCA adicionar durações ou easings ad-hoc.
 * Se precisar de algo fora daqui, discutir com art-director.
 */

export const motionOk =
  typeof window !== 'undefined' &&
  !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/*
 * Feel "premium calmo" (ref: StackGrid, Mattis): durações longas + easing
 * exponencial. Entradas lentas e suaves criam ritmo, não espetáculo.
 */
export const DURATIONS = {
  micro:    0.3,   // hover states, icon swaps
  fast:     0.5,   // button feedback, tag reveals
  normal:   0.9,   // card entrances, list items
  slow:     1.1,   // underline draws, section triggers
  entrance: 1.4,   // hero, page-level entrances
} as const;

export const EASINGS = {
  out:       'expo.out',          // entrada premium — desacelera muito no fim
  outStrong: 'expo.out',
  smooth:    'power3.out',
  inOut:     'power2.inOut',
} as const;

export const STAGGER = {
  tight:  0.08,
  normal: 0.12,
  loose:  0.18,
} as const;
