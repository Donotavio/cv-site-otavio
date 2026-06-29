# DESIGN.md — Blueprint

**Direction:** Blueprint
**POV:** "A folha de especificação de um engenheiro sênior virou portfólio — preciso, editorial, com a beleza fria de um diagrama técnico bem feito."
**Re-locked:** após feedback visual + estudo de referências (StackGrid, Mattis, Vertical via Chrome DevTools)

---

## Intenção

O site deve sentir como **um blueprint técnico que respira**. Fundo claro de papel, tipografia serif de cartaz, labels em monospace entre colchetes `[ ]`, crop marks emoldurando o que importa, e um retrato em ASCII art — o rosto do Otávio renderizado como dados. Editorial como uma revista de arquitetura, técnico como um schema de pipeline. Um acento elétrico único. Espaço negativo generoso. Escala dramática.

Referência âncora: **StackGrid** (tematicamente perfeito — é literalmente sobre AI agents e data pipelines).

---

## Paleta

```css
:root {
  /* ─── Base (papel claro, editorial) ───────────────── */
  --paper:      #FDFDFD;   /* Fundo principal — branco quase puro */
  --paper-soft: #F4F4F2;   /* Seções alternadas, leve creme */
  --paper-card: #FFFFFF;   /* Cards sobre o papel */

  /* ─── Tinta ────────────────────────────────────────── */
  --ink:        #0A0A0A;   /* Texto principal, quase preto */
  --ink-soft:   #545454;   /* Texto secundário */
  --ink-faint:  #999999;   /* Labels, metadados, captions */

  /* ─── Acento elétrico (único) ──────────────────────── */
  --accent:     #1A1AFF;   /* Azul elétrico — links, highlights, foco */
  --accent-dim: rgba(26, 26, 255, 0.08); /* Fundo de hover sutil */

  /* ─── Glows seletivos (pontuais, raros) ────────────── */
  --glow-blue:    #2B6BFF;
  --glow-magenta: #FF3DCA;

  /* ─── Linhas (blueprint) ───────────────────────────── */
  --line:        rgba(10, 10, 10, 0.12);
  --line-strong: rgba(10, 10, 10, 0.25);
  --line-accent: rgba(26, 26, 255, 0.4);

  /* ─── Sombras (mínimas, papel não flutua muito) ────── */
  --shadow-sm: 0 1px 3px rgba(10, 10, 10, 0.06);
  --shadow-md: 0 8px 32px rgba(10, 10, 10, 0.10);
}
```

**Regras de uso:**
- `--paper` é o fundo dominante. Dark é proibido nesta direção.
- `--accent` (azul elétrico) é o ÚNICO acento de cor. Usado com parcimônia: links, foco, um número-chave, hover de nav.
- Glows (`--glow-*`) aparecem APENAS no ASCII art / visual signature, nunca em texto ou UI.
- Tudo o mais é tinta sobre papel: `--ink`, `--ink-soft`, `--ink-faint`.
- Sem gradientes em backgrounds. Sem dark mode.

---

## Tipografia

### Par tipográfico

| Papel | Família | Peso | Racional |
|-------|---------|------|---------|
| Display / H1 | Instrument Serif | 400 | Serif editorial de cartaz. Elegância fria, contraste alto. A assinatura visual. |
| H2 / H3 | Inter (ou Geist) | 600 | Sans grotesca limpa. Hierarquia clara abaixo do display serif. |
| Corpo | Inter | 400 | Legibilidade máxima sobre papel claro. |
| Labels / Mono | IBM Plex Mono | 400 | Nav, eyebrows, metadados, números. SEMPRE entre colchetes `[ ]`. |

### Carregamento

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### Escala tipográfica fluida

```css
:root {
  --font-display: 'Instrument Serif', Georgia, serif;
  --font-sans:    'Inter', system-ui, sans-serif;
  --font-mono:    'IBM Plex Mono', 'Fragment Mono', monospace;

  /* Escala — note o salto dramático no topo (cartaz) */
  --text-xs:      clamp(0.75rem,  0.72rem + 0.15vw, 0.8125rem);  /* 12–13px mono labels */
  --text-sm:      clamp(0.875rem, 0.84rem + 0.2vw,  0.9375rem);  /* 14–15px */
  --text-base:    clamp(1rem,     0.96rem + 0.25vw, 1.125rem);   /* 16–18px corpo */
  --text-lg:      clamp(1.25rem,  1.1rem  + 0.6vw,  1.5rem);     /* 20–24px */
  --text-xl:      clamp(1.5rem,   1.2rem  + 1.2vw,  2rem);       /* 24–32px */
  --text-2xl:     clamp(2rem,     1.5rem  + 2.2vw,  3rem);       /* 32–48px H2 */
  --text-3xl:     clamp(2.75rem,  1.8rem  + 4vw,    4.5rem);     /* 44–72px */
  --display-1:    clamp(3.5rem,   2rem    + 7vw,    8rem);       /* 56–128px H1 hero */
  --display-2:    clamp(2.75rem,  1.6rem  + 5.5vw,  6rem);       /* 44–96px section display */

  --leading-tight:  1.05;  /* display serif quer leading apertado */
  --leading-snug:   1.2;
  --leading-normal: 1.5;
  --leading-loose:  1.7;

  --tracking-tight: -0.03em;  /* display serif grande */
  --tracking-normal: 0;
  --tracking-wide:   0.04em;
  --tracking-wider:  0.12em;  /* mono labels em maiúscula */
}
```

**Convenções por elemento:**

| Elemento | Font | Size | Weight | Leading | Tracking |
|----------|------|------|--------|---------|----------|
| Hero H1 | display | `--display-1` | 400 | tight | tight |
| Section display | display | `--display-2` | 400 | tight | tight |
| H2 | sans | `--text-2xl` | 600 | snug | normal |
| H3 | sans | `--text-xl` | 600 | snug | normal |
| Corpo | sans | `--text-base` | 400 | loose | normal |
| Nav / label / eyebrow | mono | `--text-xs` | 400/500 | normal | wider, **entre `[ ]`** |
| Número-chave | mono | `--text-3xl` | 500 | tight | tight |
| Tag | mono | `--text-xs` | 400 | tight | wide |

**Regra dos colchetes:** todo label em mono é renderizado entre colchetes — `[ About ]`, `[ 01 ]`, `[ Data Engineering ]`. É a assinatura tipográfica da direção. Pode ser feito via `::before { content: '[ ' }` / `::after { content: ' ]' }` em CSS para não poluir o i18n.

---

## Régua de Espaçamento

Base unit **4px** (mantida da direção anterior — funciona bem).

```css
:root {
  --space-1: 4px;   --space-2: 8px;   --space-3: 12px;  --space-4: 16px;
  --space-5: 20px;  --space-6: 24px;  --space-8: 32px;  --space-10: 40px;
  --space-12: 48px; --space-16: 64px; --space-20: 80px; --space-24: 96px;
  --space-32: 128px; --space-40: 160px; --space-48: 192px;
}
```

Esta direção usa espaço negativo **generoso** — seções respiram com `--space-32` a `--space-48` no desktop.

---

## Elementos de assinatura (signature)

### 1. Crop marks (cantos de blueprint)
Cantos `⌐ ¬ ∟ ⌐` emoldurando o hero e cards-chave. Implementados como `::before`/`::after` ou 4 spans posicionados absolutamente, 1px de linha, `--line-strong`.

```css
.crop-frame { position: relative; }
.crop-frame::before, .crop-frame::after,
.crop-frame > .crop-tl, .crop-frame > .crop-br {
  /* cantos de 16px desenhados com border */
}
```

### 2. ASCII portrait (visual signature do hero)
O rosto do Otávio renderizado em ASCII art (gerado em `assets/data/portrait-ascii.txt`). Exibido em `<pre>` com `--font-mono`, `--text-xs`, `--leading-tight`. Cor `--ink`. Hover/scroll pode revelar um glow azul sutil atrás dele.

### 3. Labels indexados
Seções numeradas: `[ 01 ]`, `[ 02 ]`, em mono, ao lado dos títulos. Linguagem de spec técnica.

### 4. Linhas conectoras com label
Como o "The AI" do StackGrid — uma linha fina apontando para um elemento, com label mono. Usado pontualmente.

---

## Vocabulário de Motion (≤ 5 padrões)

Mantém GSAP + Lenis. Os padrões evoluem para a estética blueprint:

### 1. `resolve` — entrance do hero
Título serif revela com fade + leve y. ASCII art revela linha por linha (efeito "datilografando"/scan). Eyebrow e CTAs em cascata.

### 2. `reveal-up` — scroll reveal
Elementos sobem 24px + fade ao entrar no viewport. `stagger`. `once: true`.

### 3. `hairline-draw` — linhas de blueprint crescem
Linhas divisórias e conectoras crescem de 0→100% (scaleX). Crop marks aparecem desenhando.

### 4. `count-up` — números grandes contam
Métricas e números-chave contam de 0 até o valor ao entrar no viewport. Mono, escala grande. (Novo — substitui o glow hover da direção anterior.)

### 5. `smooth-scroll` — Lenis no root
Smooth scroll, lerp 0.08. `gsap.ticker.lagSmoothing(0)`.

### Durações e easings

```typescript
export const DURATIONS = {
  micro: 0.2, fast: 0.35, normal: 0.6, slow: 0.9, entrance: 1.2,
} as const;
export const EASINGS = {
  out: 'power2.out', outStrong: 'power3.out', inOut: 'power2.inOut',
} as const;
```

`prefers-reduced-motion`: estado final aplicado instantaneamente. ASCII art aparece completo sem scan. Contadores mostram valor final direto.

---

## Outros tokens

```css
:root {
  --radius-sm: 2px;   /* blueprint quer cantos quase retos */
  --radius-md: 4px;
  --radius-lg: 8px;
  --radius-full: 9999px;

  --transition-fast:   0.2s ease;
  --transition-normal: 0.35s cubic-bezier(0.4, 0, 0.2, 1);

  --z-below: -1; --z-base: 0; --z-raised: 10;
  --z-nav: 100; --z-modal: 200; --z-toast: 300;

  --container-xl: 1280px;
  --container-max: 1440px;
}
```

Note: radius **menor** que a direção anterior — blueprint prefere cantos retos/quase retos.

---

## O que muda da direção anterior (The Architect → Blueprint)

| Antes (The Architect) | Agora (Blueprint) |
|------------------------|-------------------|
| Fundo navy `#0A0E27` | Papel claro `#FDFDFD` |
| IBM Plex Mono no H1 | Instrument Serif no H1 (display de cartaz) |
| H1 ~48px | H1 até 128px (escala de cartaz) |
| Cyan `#00D9FF` + coral | Azul elétrico `#1A1AFF` único |
| Cards uniformes | Bento grid assimétrico + crop marks |
| Sem visual signature | ASCII portrait + crop marks + labels indexados |
| Glow hover | count-up de números grandes |
| radius 12px | radius 2–8px (cantos retos) |

---

## O que continua eliminado

- Gradiente roxo (nunca)
- Canvas particles
- Dark mode / toggle
- Badge soup → `.tag` único
- `console.log` em produção
- Custom cursor

---

## Breakpoints

```css
/* Mobile-first, apenas min-width */
@media (min-width: 640px)  { /* tablet */ }
@media (min-width: 1024px) { /* desktop */ }
@media (min-width: 1440px) { /* widescreen */ }
```

---

## Checklist de "pronto" por componente

- [ ] Fundo claro `--paper` — zero dark
- [ ] H1/display em Instrument Serif, escala de cartaz
- [ ] Labels mono entre colchetes `[ ]`
- [ ] Apenas `--accent` como cor; glows só no ASCII
- [ ] Crop marks onde faz sentido (hero, cards-chave)
- [ ] Contraste WCAG AA (ink sobre paper = ~19:1, folgado)
- [ ] Apenas os 5 padrões de motion
- [ ] `prefers-reduced-motion` testado
- [ ] Conteúdo legível sem JS
- [ ] Zero hex hardcoded — só tokens
- [ ] Nenhum `console.log`
