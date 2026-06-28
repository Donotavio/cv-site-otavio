# Skill: web-motion

Padrões GSAP + Lenis para o cv-site-otavio. Direção "The Architect".

## Stack

- **GSAP 3.x** — coreografia de scroll e entrances
- **GSAP ScrollTrigger** — triggers baseados em viewport
- **Lenis 1.x** — smooth scroll; sincronizado com o ticker do GSAP
- Sem Framer Motion para scroll choreography (permitido apenas dentro de React islands, se houver)

---

## Setup obrigatório (BaseLayout.astro)

```typescript
// src/scripts/motion-init.ts
import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export function initMotion() {
  // prefers-reduced-motion: encerra antes de criar qualquer animação
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const lenis = new Lenis({
    lerp: 0.08,
    smoothWheel: true,
    syncTouch: false, // não aplicar em touch — evita conflito com iOS momentum
  });

  // Sincronizar o RAF do Lenis com o ticker do GSAP
  gsap.ticker.add((time) => lenis.raf(time * 1000));
  gsap.ticker.lagSmoothing(0);

  // Proxy para ScrollTrigger ler a posição do Lenis
  ScrollTrigger.scrollerProxy(document.documentElement, {
    scrollTop: () => lenis.scroll,
    getBoundingClientRect: () => ({
      top: 0, left: 0,
      width: window.innerWidth,
      height: window.innerHeight,
    }),
  });
  lenis.on('scroll', ScrollTrigger.update);

  return lenis;
}
```

Chamar `initMotion()` uma única vez, no `<script>` do `BaseLayout.astro`, após o DOM estar pronto.

---

## Os 5 padrões de motion (vocabulário completo)

### 1. `reveal-up` — entrada de elementos no scroll

```typescript
// src/scripts/motion/reveal-up.ts
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { DURATIONS, EASINGS, motionOk } from './constants';

/**
 * Revela um conjunto de elementos ao entrar no viewport.
 * Usar em: parágrafos, cards, listas, headings de seção.
 * @param elements - NodeList ou array de elementos
 * @param container - elemento pai para o ScrollTrigger
 * @param stagger  - delay entre elementos (default 0.1s)
 */
export function revealUp(
  elements: Element | Element[] | NodeListOf<Element>,
  container: Element,
  stagger = 0.1,
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
      once: true,
    },
  });
}
```

### 2. `hairline-draw` — underline cresce

```typescript
// src/scripts/motion/hairline-draw.ts
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { DURATIONS, EASINGS, motionOk } from './constants';

/**
 * Linha de 1px cresce de left para right ao scroll.
 * Usar em: separadores de seção, títulos principais.
 * O elemento deve ter: width: 100%; height: 1px; transform-origin: left center
 */
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
```

### 3. `hover-glow` — glow cyan no hover

Implementado em CSS puro (não GSAP) para performance máxima em elementos repetidos.

```css
/* Aplicar na classe do elemento interativo */
.hover-glow {
  position: relative;
  transition: color var(--transition-fast);
}
.hover-glow::before {
  content: '';
  position: absolute;
  inset: -4px -8px;
  background: var(--primary-dim);
  border-radius: var(--radius-sm);
  opacity: 0;
  transition: opacity var(--transition-fast);
  pointer-events: none;
}
.hover-glow:hover::before { opacity: 1; }
.hover-glow:hover         { color: var(--primary); }

/* Desabilitado quando não há mouse */
@media (hover: none) {
  .hover-glow::before { display: none; }
}
```

### 4. `smooth-scroll` — Lenis no root

Configurado em `motion-init.ts` (acima). Não há código adicional por componente.

**Nunca** usar `scroll-behavior: smooth` no CSS — conflita com o Lenis.

### 5. `resolve` — entrance do hero (uma vez, no load)

```typescript
// src/scripts/motion/resolve.ts
import gsap from 'gsap';
import { DURATIONS, EASINGS, motionOk } from './constants';

/**
 * Entrance sequencial do hero na carga da página.
 * Executar apenas uma vez, sem ScrollTrigger.
 * Seletores esperados no markup:
 *   [data-hero-eyebrow], [data-hero-title],
 *   [data-hero-subtitle], [data-hero-ctas]
 */
export function resolveHero(heroEl: Element) {
  if (!motionOk) return;

  const tl = gsap.timeline({ delay: 0.15 });
  tl.from(heroEl.querySelector('[data-hero-eyebrow]'), {
    opacity: 0, y: 12,
    duration: DURATIONS.fast, ease: EASINGS.out,
  })
  .from(heroEl.querySelector('[data-hero-title]'), {
    opacity: 0, y: 24,
    duration: DURATIONS.entrance, ease: EASINGS.outStrong,
  }, '-=0.15')
  .from(heroEl.querySelector('[data-hero-subtitle]'), {
    opacity: 0, y: 16,
    duration: DURATIONS.normal, ease: EASINGS.out,
  }, '-=0.45')
  .from(heroEl.querySelectorAll('[data-hero-ctas] > *'), {
    opacity: 0, y: 12,
    duration: DURATIONS.fast, ease: EASINGS.out,
    stagger: 0.08,
  }, '-=0.3');

  return tl;
}
```

---

## Constantes

```typescript
// src/scripts/motion/constants.ts

export const motionOk =
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
```

---

## Guardrails de performance

| Regra | Motivo |
|-------|--------|
| Animar apenas `transform` e `opacity` | Não causam layout/paint |
| Não animar `width`, `height`, `top`, `left` | Causam layout thrash |
| Usar `will-change: transform` apenas em elementos animando continuamente | Excesso consome VRAM |
| Remover `will-change` após a animação terminar | `onComplete: () => el.style.willChange = 'auto'` |
| `once: true` em ScrollTriggers de entrada | Evita re-trigger desnecessário |
| Nunca usar `requestAnimationFrame` manual | Lenis + GSAP ticker já gerenciam o RAF |
| `gsap.ticker.lagSmoothing(0)` sempre | Evita saltos após aba em background |

---

## Guardrails de acessibilidade

```typescript
// Verificação antes de qualquer animação
if (!motionOk) {
  // Aplicar estado final diretamente
  gsap.set(elements, { opacity: 1, y: 0, scaleX: 1 });
  return;
}
```

```css
/* CSS reset de fallback — garante que sem JS o conteúdo aparece */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration:        0.01ms !important;
    animation-iteration-count: 1      !important;
    transition-duration:       0.01ms !important;
    scroll-behavior:           auto   !important;
  }
}
```

---

## Checklist de "pronto" (rodar antes de marcar seção como done)

- [ ] Todos os 5 padrões usados são os do vocabulário acima — sem ad-hoc
- [ ] `motionOk` verificado antes de cada animação
- [ ] CSS reduced-motion reset presente no layout global
- [ ] Apenas `transform` e `opacity` animados via GSAP
- [ ] `once: true` em todos os ScrollTriggers de entrada
- [ ] Lenis inicializado uma única vez no layout root
- [ ] `gsap.ticker.lagSmoothing(0)` presente no init
- [ ] Testado com `prefers-reduced-motion: reduce` ativo (macOS System Settings)
- [ ] Conteúdo visível sem JS (CSS default state = visível)
- [ ] FPS estável em 60fps no Chrome DevTools Performance panel
- [ ] Nenhum layout thrash detectado (painel Rendering do DevTools)
- [ ] `console.log` removidos do código de motion
