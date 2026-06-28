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

export const DURATIONS = {
  micro:    0.2,   // hover states, icon swaps
  fast:     0.35,  // button feedback, tag reveals
  normal:   0.6,   // card entrances, list items
  slow:     0.9,   // underline draws, section triggers
  entrance: 1.2,   // hero, page-level entrances
} as const;

export const EASINGS = {
  out:       'power2.out',
  outStrong: 'power3.out',
  inOut:     'power2.inOut',
  snap:      'back.out(1.2)', // apenas micro-interactions com feedback snappy
} as const;

export const STAGGER = {
  tight:  0.06,
  normal: 0.1,
  loose:  0.15,
} as const;
