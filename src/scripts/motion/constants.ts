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

/**
 * LOADER — cadências do Query Loader (query-loader.ts).
 *
 * Centralizados aqui (não ad-hoc) para consistência e ajuste fino num só
 * lugar. Valores em MILISSEGUNDOS exceto onde marcado (s).
 * Feel premium calmo: pausas generosas, sem pressa.
 */
export const LOADER = {
  // ── Typewriter (effect 'type' / 'insert') ──
  charMs:        24,    // ms por caractere
  charMsInsert:  26,    // 'insert' é marginalmente mais lento
  spaceFactor:   0.5,   // espaços fluem mais rápido (ritmo natural)

  // ── Aparição de linhas (stream / import / paginate) ──
  lineMs:        130,   // delay base entre linhas de código
  lineMsBlank:   60,    // linhas vazias aparecem mais rápido
  lineMsStream:  170,   // stdout Python (stream) ligeiramente mais lento
  lineMsBlankStream: 90,

  // ── Efeitos específicos ──
  planMs:        160,   // EXPLAIN plan: linha a linha
  scanMs:        180,   // scan: cursor por linha
  sortFrameMs:   130,   // sort: frame de shuffle
  sortSettleMs:  220,   // sort: pausa do frame final ordenado
  progressMs:    55,    // import: tick da barra ASCII
  paginateMs:    150,   // paginate: delay entre lotes do feed
  fetchTickMs:   26,    // fetch: tick do contador de rows

  // ── Pausas de "execução" / resultado ──
  preEffectMs:   120,   // pausa inicial antes do efeito (após render)
  preEffectPlanMs: 120,
  fetchHoldMs:   200,   // fetch: pausa "fetching…" antes de contar
  runMs:         320,   // "▸ executando"
  resultMs:      240,   // exibição do resultado final
  resultMsInsert: 320,  // 'insert' fica um pouco mais no "1 row affected"

  // ── Fades do overlay (em SEGUNDOS — são durações GSAP) ──
  fadeIn:        0.22,
  fadeOut:       0.45,
  aggregateDur:  1.0,   // duration (s) do roll dos contadores (aggregate)

  // ── ScrollTrigger.refresh() pós-reveal (debounce) ──
  refreshMs:     120,
} as const;

/** Delay inicial da timeline do hero (padrão resolve). */
export const HERO_DELAY = 0.15;
