# DESIGN.md — The Architect

**Direction:** The Architect
**POV:** "Como sentar de frente para um engenheiro sênior que codifica elegantemente e explica claramente — nenhum movimento desperdiçado, cada escolha serve a um propósito."
**Locked at GATE 1 — June 28, 2026**

---

## Intenção

O site deve sentir como **precisão técnica com calor humano**. Navy ancora credibilidade; cyan sinaliza inteligência de dados; coral humaniza os pontos de ação. Nenhum gradiente — restrição como gosto. Cada animação guia o olho ou cria hierarquia; se não faz isso, não entra.

---

## Paleta

```css
:root {
  /* Backgrounds */
  --bg:          #0A0E27;   /* Deep navy — fundação, profundidade técnica */
  --bg-soft:     #141830;   /* Navy ligeiramente mais claro — camadas */
  --bg-card:     rgba(20, 24, 48, 0.7); /* Superfície de cards com vidro */

  /* Texto */
  --text:        #F5F7FA;   /* Off-white — legibilidade máxima, não harsh */
  --muted:       #94A3B8;   /* Slate — texto secundário, sem gritar */

  /* Acento principal */
  --primary:     #00D9FF;   /* Cyan — clareza, inteligência de dados */
  --primary-dim: rgba(0, 217, 255, 0.15); /* Cyan translúcido para fundos */

  /* Acento de ação */
  --cta:         #FF6B6B;   /* Coral — calor nos CTAs, humaniza */
  --cta-hover:   #FF4F4F;   /* Coral mais saturado no hover */

  /* Bordas e divisores */
  --line:        rgba(148, 163, 184, 0.12);
  --line-accent: rgba(0, 217, 255, 0.25);

  /* Sombras */
  --shadow-sm:   0 2px 8px rgba(0, 0, 0, 0.3);
  --shadow-md:   0 8px 32px rgba(0, 0, 0, 0.4);
  --shadow-glow: 0 0 24px rgba(0, 217, 255, 0.12);
}
```

**Regra de uso:**
- `--bg` / `--bg-soft` / `--bg-card` — fundos de página, seções, cards
- `--primary` — links ativos, underlines, ícones de destaque, highlights de hover
- `--cta` — botão principal, CTA de contato, download de CV
- `--text` / `--muted` — hierarquia tipográfica, sem cores extras para texto
- Sem gradientes em backgrounds de página ou seções
- Glassmorphism (`backdrop-filter: blur`) permitido apenas em cards e nav sticky

---

## Tipografia

### Par tipográfico

| Papel | Família | Peso | Racional |
|-------|---------|------|---------|
| Display / H1 | IBM Plex Mono | 700 | Monospace em display = rigor de sistemas. Peso pesado comanda atenção. |
| H2 / H3 | Inter | 700 | Sans moderna, legível em escala menor. Contraste com o mono. |
| Corpo | Inter | 400 | Alta legibilidade. Curvas suaves equilibram o mono nos titles. |
| Labels / Dados | IBM Plex Mono | 400 | Dados, datas, métricas — reforça o mindset de engenharia. |

### Carregamento de fontes

```html
<!-- Prioridade: apenas os pesos usados -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
```

### Escala tipográfica fluida

```css
:root {
  --font-mono: 'IBM Plex Mono', 'Fira Code', monospace;
  --font-sans: 'Inter', system-ui, sans-serif;

  /* Escala fluida — clamp(min, preferred, max) */
  --text-xs:   clamp(0.75rem,  0.7rem  + 0.25vw, 0.875rem); /* 12–14px */
  --text-sm:   clamp(0.875rem, 0.825rem + 0.25vw, 1rem);     /* 14–16px */
  --text-base: clamp(1rem,     0.95rem  + 0.25vw, 1.125rem); /* 16–18px */
  --text-lg:   clamp(1.125rem, 1rem     + 0.5vw,  1.375rem); /* 18–22px */
  --text-xl:   clamp(1.375rem, 1.125rem + 1vw,    1.75rem);  /* 22–28px */
  --text-2xl:  clamp(1.75rem,  1.375rem + 1.5vw,  2.5rem);   /* 28–40px */
  --text-3xl:  clamp(2.25rem,  1.5rem   + 2.5vw,  3.5rem);   /* 36–56px */
  --text-4xl:  clamp(3rem,     2rem     + 3.5vw,  5rem);     /* 48–80px */

  /* Line-heights */
  --leading-tight:  1.2;
  --leading-snug:   1.4;
  --leading-normal: 1.6;
  --leading-loose:  1.8;

  /* Letter-spacing */
  --tracking-tight:  -0.02em;
  --tracking-normal: 0;
  --tracking-wide:   0.05em;
  --tracking-wider:  0.1em;
}
```

**Regras de uso:**
- H1 / display: `--font-mono`, `--text-4xl`, `--leading-tight`, `--tracking-tight`
- H2: `--font-sans`, `--text-2xl`, `--leading-snug`, `700`
- H3: `--font-sans`, `--text-xl`, `--leading-snug`, `700`
- Corpo: `--font-sans`, `--text-base`, `--leading-normal`, `400`
- Labels de dados / datas / métricas: `--font-mono`, `--text-sm`, `--tracking-wide`
- Eyebrow / overline: `--font-mono`, `--text-xs`, `--tracking-wider`, `uppercase`

---

## Régua de Espaçamento

Base unit: **4px**. Todos os valores são múltiplos do base.

```css
:root {
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;
  --space-24: 96px;
  --space-32: 128px;
}
```

**Uso semântico:**
- `--space-1` / `--space-2` — gaps inline, ícones
- `--space-3` / `--space-4` — padding de botões, gaps de tags
- `--space-6` / `--space-8` — padding de cards
- `--space-12` / `--space-16` — margens de seção (mobile)
- `--space-20` / `--space-32` — margens de seção (desktop), hero

---

## Vocabulário de Motion

**Regra de ouro:** ≤ 5 padrões no site inteiro. Se a animação não guia o olho, não cria hierarquia ou não dá ritmo, não entra.

### Padrão 1 — `reveal-up` (Reveal staggerado)
Texto e cards revelam linha a linha ao entrar no viewport. Cria leitura guiada.

```typescript
// gsap + ScrollTrigger
gsap.from(elements, {
  opacity: 0,
  y: 24,
  duration: 0.7,
  ease: 'power2.out',
  stagger: 0.1,
  scrollTrigger: {
    trigger: container,
    start: 'top 85%',
    once: true,
  },
});
```

### Padrão 2 — `hairline-draw` (Underline cresce)
Linha underline (1px) cresce de 0 → 100% ao rolar. Sinaliza seção ativa.

```typescript
gsap.from(line, {
  scaleX: 0,
  transformOrigin: 'left center',
  duration: 0.9,
  ease: 'power3.out',
  scrollTrigger: { trigger: section, start: 'top 80%', once: true },
});
```

### Padrão 3 — `hover-glow` (Glow no hover)
Cyan suave aparece atrás do texto/card no hover. Sinal de interatividade, não ruído.

```css
.interactive {
  position: relative;
  transition: color 0.2s ease;
}
.interactive::before {
  content: '';
  position: absolute;
  inset: -4px -8px;
  background: var(--primary-dim);
  border-radius: 4px;
  opacity: 0;
  transition: opacity 0.2s ease;
}
.interactive:hover::before { opacity: 1; }
.interactive:hover { color: var(--primary); }
```

### Padrão 4 — `smooth-scroll` (Lenis)
Lenis smooth scroll no root — velocidade `1.0`, easing `lerp: 0.08`. Toda a página respira.

```typescript
import Lenis from 'lenis';
import gsap from 'gsap';
import ScrollTrigger from 'gsap/ScrollTrigger';

const lenis = new Lenis({ lerp: 0.08, smoothWheel: true });
gsap.ticker.add((time) => lenis.raf(time * 1000));
gsap.ticker.lagSmoothing(0);
ScrollTrigger.scrollerProxy(document.documentElement, {
  scrollTop: () => lenis.scroll,
  getBoundingClientRect: () => ({ top: 0, left: 0, width: window.innerWidth, height: window.innerHeight }),
});
lenis.on('scroll', ScrollTrigger.update);
```

### Padrão 5 — `resolve` (Entrance do hero)
Hero entra em cena uma vez, no carregamento da página. Título revela carácter a carácter (SplitText ou manual), depois subtítulo e CTAs em cascata.

```typescript
const heroTl = gsap.timeline({ delay: 0.2 });
heroTl
  .from('.hero-eyebrow',  { opacity: 0, y: 12, duration: 0.5, ease: 'power2.out' })
  .from('.hero-title',    { opacity: 0, y: 24, duration: 0.8, ease: 'power3.out' }, '-=0.2')
  .from('.hero-subtitle', { opacity: 0, y: 16, duration: 0.6, ease: 'power2.out' }, '-=0.4')
  .from('.hero-ctas',     { opacity: 0, y: 12, duration: 0.5, ease: 'power2.out' }, '-=0.3');
```

### Durações e easings padrão

```typescript
export const DURATIONS = {
  micro:    0.2,  // hover states, icon swaps
  fast:     0.35, // button feedback, tag reveals
  normal:   0.6,  // card entrances, section transitions
  slow:     0.9,  // underline draws, parallax
  entrance: 1.2,  // hero, page-level entrances
} as const;

export const EASINGS = {
  out:      'power2.out',
  outStrong: 'power3.out',
  inOut:    'power2.inOut',
  snap:     'back.out(1.2)', // só para micro-interactions que precisam de snap
} as const;
```

### `prefers-reduced-motion`

**Obrigatório em toda animação.** Fallback: estado final aplicado instantaneamente.

```typescript
export const motionOk = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export function animate(fn: () => gsap.core.Tween | gsap.core.Timeline) {
  if (!motionOk) return;
  return fn();
}

// CSS fallback paralelo
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Outros tokens

```css
:root {
  /* Border radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 20px;
  --radius-full: 9999px;

  /* Transitions (micro-interactions, sem GSAP) */
  --transition-fast:   0.2s ease;
  --transition-normal: 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow:   0.6s cubic-bezier(0.16, 1, 0.3, 1);

  /* Z-index scale */
  --z-below:   -1;
  --z-base:     0;
  --z-raised:  10;
  --z-nav:     100;
  --z-modal:   200;
  --z-toast:   300;
}
```

---

## O que foi eliminado desta direção

| Eliminado | Motivo |
|-----------|--------|
| Gradiente roxo `#667eea → #764ba2` | Não estava no site, mas documentado: nunca entra |
| Canvas particle background | Ruído visual, custo de performance, sem propósito semântico |
| 21 `@keyframes` ad-hoc | Substituídos por 5 padrões nomeados |
| Dark/light theme toggle | Tema único: dark navy. Sem toggle. |
| Badge soup (6 variantes de pill) | Substituído por `.tag` + `.tag--accent` |
| `scroll.js` blur/scale/shift effects | Substituído por Lenis + GSAP ScrollTrigger |
| Custom cursor | Sem propósito de UX, custo de implementação sem retorno |
| `console.log` em produção | Remover todos antes de qualquer commit |

---

## Breakpoints responsivos

```css
/* Mobile: 0–639px (default — mobile first) */
/* Tablet: 640px+ */
@media (min-width: 640px)  { /* ... */ }
/* Desktop: 1024px+ */
@media (min-width: 1024px) { /* ... */ }
/* Widescreen: 1440px+ */
@media (min-width: 1440px) { /* ... */ }
```

---

## Checklist de "pronto" por componente

Antes de marcar qualquer componente como done:

- [ ] Usa apenas tokens definidos neste arquivo (sem hex hardcoded)
- [ ] Tipografia: apenas `--font-mono` e `--font-sans`, escala fluida
- [ ] Animações: apenas os 5 padrões acima, sem ad-hoc extras
- [ ] `prefers-reduced-motion` testado manualmente (macOS Settings)
- [ ] Conteúdo legível com JS desabilitado (Chrome DevTools)
- [ ] Contraste WCAG AA verificado (mínimo 4.5:1 para texto normal)
- [ ] Nenhum `console.log` em produção
- [ ] Nenhum valor `!important` excepto no reset de reduced-motion
