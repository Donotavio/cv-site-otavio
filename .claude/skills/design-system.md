# Skill: design-system

Tokens de design, regras de aplicação e convenções CSS para o cv-site-otavio. Direção "The Architect". Fonte de verdade: `DESIGN.md` na raiz do repo.

---

## Princípio

Tokens são lei. Nenhum valor de cor, fonte, espaçamento ou radius hardcoded no código — tudo via CSS custom properties definidas no `DESIGN.md`. Se um token não existe, pergunte antes de inventar.

---

## Onde os tokens vivem

```
DESIGN.md                  ← Fonte de verdade (legível por humanos)
src/styles/tokens.css      ← :root com todas as custom properties
src/styles/reset.css       ← Normalize + base styles
src/styles/typography.css  ← Classes utilitárias de tipo
src/styles/layout.css      ← Grid, container, breakpoints
```

Todos os outros arquivos CSS importam de `tokens.css`. Nunca redefinir um token em um componente — apenas usá-lo.

---

## Tokens de cor

```css
/* src/styles/tokens.css */
:root {
  --bg:          #0A0E27;
  --bg-soft:     #141830;
  --bg-card:     rgba(20, 24, 48, 0.7);

  --text:        #F5F7FA;
  --muted:       #94A3B8;

  --primary:     #00D9FF;
  --primary-dim: rgba(0, 217, 255, 0.15);

  --cta:         #FF6B6B;
  --cta-hover:   #FF4F4F;

  --line:        rgba(148, 163, 184, 0.12);
  --line-accent: rgba(0, 217, 255, 0.25);

  --shadow-sm:   0 2px 8px rgba(0, 0, 0, 0.3);
  --shadow-md:   0 8px 32px rgba(0, 0, 0, 0.4);
  --shadow-glow: 0 0 24px rgba(0, 217, 255, 0.12);
}
```

**Uso semântico obrigatório:**

| Token | Usar em |
|-------|---------|
| `--bg` | Background da página, `<body>` |
| `--bg-soft` | Seções alternadas, fundos de destaques |
| `--bg-card` | Cards, modais, nav sticky |
| `--text` | Todo texto primário |
| `--muted` | Labels, datas, texto secundário, placeholders |
| `--primary` | Links ativos, underlines, ícones em destaque, badges de tech |
| `--primary-dim` | Background de hover, highlight sutil |
| `--cta` | Botão primário, download CV, link de contato principal |
| `--cta-hover` | Estado `:hover` do CTA |
| `--line` | Bordas de cards, divisores, `hr` |
| `--line-accent` | Bordas de cards em hover ou focus |
| `--shadow-sm` | Elevação sutil (tags, badges) |
| `--shadow-md` | Cards em hover, modais |
| `--shadow-glow` | Efeito glow em cards de destaque |

---

## Tokens de tipografia

```css
:root {
  --font-mono: 'IBM Plex Mono', 'Fira Code', monospace;
  --font-sans: 'Inter', system-ui, sans-serif;

  --text-xs:   clamp(0.75rem,  0.7rem   + 0.25vw, 0.875rem);
  --text-sm:   clamp(0.875rem, 0.825rem + 0.25vw, 1rem);
  --text-base: clamp(1rem,     0.95rem  + 0.25vw, 1.125rem);
  --text-lg:   clamp(1.125rem, 1rem     + 0.5vw,  1.375rem);
  --text-xl:   clamp(1.375rem, 1.125rem + 1vw,    1.75rem);
  --text-2xl:  clamp(1.75rem,  1.375rem + 1.5vw,  2.5rem);
  --text-3xl:  clamp(2.25rem,  1.5rem   + 2.5vw,  3.5rem);
  --text-4xl:  clamp(3rem,     2rem     + 3.5vw,  5rem);

  --leading-tight:  1.2;
  --leading-snug:   1.4;
  --leading-normal: 1.6;
  --leading-loose:  1.8;

  --tracking-tight:  -0.02em;
  --tracking-normal: 0em;
  --tracking-wide:   0.05em;
  --tracking-wider:  0.1em;
}
```

**Convenções por elemento:**

| Elemento | Font | Size | Weight | Leading | Tracking |
|----------|------|------|--------|---------|----------|
| H1 / hero title | mono | `4xl` | 700 | tight | tight |
| H2 | sans | `2xl` | 700 | snug | normal |
| H3 | sans | `xl` | 700 | snug | normal |
| H4 | sans | `lg` | 600 | snug | normal |
| Body | sans | `base` | 400 | normal | normal |
| Body small | sans | `sm` | 400 | normal | normal |
| Eyebrow / overline | mono | `xs` | 400 | normal | wider |
| Label / data | mono | `sm` | 400 | normal | wide |
| Button | sans | `sm` | 600 | tight | wide |
| Tag / badge | mono | `xs` | 400 | tight | wide |

---

## Tokens de espaçamento

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

| Contexto | Token |
|----------|-------|
| Gap entre ícone e label | `--space-2` |
| Padding interno de button | `--space-3` vertical / `--space-6` horizontal |
| Gap entre tags | `--space-2` |
| Padding interno de card | `--space-6` a `--space-8` |
| Espaço entre H2 e parágrafo | `--space-4` |
| Margem entre seções (mobile) | `--space-12` a `--space-16` |
| Margem entre seções (desktop) | `--space-20` a `--space-32` |
| Padding lateral de página (mobile) | `--space-4` a `--space-6` |
| Padding lateral de página (desktop) | `--space-8` a `--space-12` |

---

## Outros tokens

```css
:root {
  --radius-sm:   4px;
  --radius-md:   8px;
  --radius-lg:   12px;
  --radius-xl:   20px;
  --radius-full: 9999px;

  --transition-fast:   0.2s ease;
  --transition-normal: 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow:   0.6s cubic-bezier(0.16, 1, 0.3, 1);

  --z-below:  -1;
  --z-base:    0;
  --z-raised: 10;
  --z-nav:    100;
  --z-modal:  200;
  --z-toast:  300;
}
```

---

## Breakpoints

```css
/* Mobile-first. Apenas min-width. */

/* 0–639px: mobile (default — nenhuma media query) */

@media (min-width: 640px) {
  /* tablet */
}

@media (min-width: 1024px) {
  /* desktop */
}

@media (min-width: 1440px) {
  /* widescreen */
}
```

**Variáveis de container:**

```css
:root {
  --container-sm:  640px;
  --container-md:  768px;
  --container-lg:  1024px;
  --container-xl:  1280px;
  --container-max: 1440px;
}

.container {
  width: 100%;
  max-width: var(--container-xl);
  margin-inline: auto;
  padding-inline: var(--space-4);
}

@media (min-width: 640px)  { .container { padding-inline: var(--space-6);  } }
@media (min-width: 1024px) { .container { padding-inline: var(--space-8);  } }
@media (min-width: 1440px) { .container { padding-inline: var(--space-12); } }
```

---

## Componentes de base

### Tag / Badge

```css
.tag {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: transparent;
  white-space: nowrap;
}

.tag--accent {
  color: var(--primary);
  border-color: var(--line-accent);
  background: var(--primary-dim);
}
```

### Botão primário (CTA)

```css
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-6);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  font-weight: 600;
  letter-spacing: var(--tracking-wide);
  color: var(--bg);
  background: var(--cta);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast), transform var(--transition-fast);
}
.btn-primary:hover {
  background: var(--cta-hover);
  transform: translateY(-1px);
}
.btn-primary:active {
  transform: translateY(0);
}
.btn-primary:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 3px;
}
```

### Botão secundário (outline)

```css
.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-6);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  font-weight: 600;
  letter-spacing: var(--tracking-wide);
  color: var(--text);
  background: transparent;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast),
              transform var(--transition-fast);
}
.btn-secondary:hover {
  border-color: var(--primary);
  color: var(--primary);
  transform: translateY(-1px);
}
.btn-secondary:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 3px;
}
```

### Card base

```css
.card {
  background: var(--bg-card);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: border-color var(--transition-normal),
              box-shadow var(--transition-normal),
              transform var(--transition-normal);
}
.card:hover {
  border-color: var(--line-accent);
  box-shadow: var(--shadow-glow);
  transform: translateY(-2px);
}
```

---

## Regras de CSS nos componentes Astro

```astro
<!-- Correto: CSS scoped por componente -->
<style>
  .hero-title {
    font-family: var(--font-mono);
    font-size: var(--text-4xl);
    color: var(--text);
  }
</style>

<!-- Errado: hex hardcoded -->
<style>
  .hero-title {
    color: #F5F7FA; /* ← nunca fazer isso */
  }
</style>
```

**Regras:**
1. Só CSS scoped (`<style>` sem `is:global`) em componentes Astro
2. `is:global` permitido apenas em `tokens.css`, `reset.css`, `typography.css`, `layout.css`
3. Nenhum `!important` — exceto no reset de `prefers-reduced-motion`
4. Nenhum `z-index` sem usar a escala `--z-*`
5. Nenhuma propriedade de animação/transition fora dos tokens — usar `var(--transition-*)`

---

## Checklist de conformidade

Antes de entregar qualquer componente:

- [ ] Nenhum hex hardcoded (grep por `#[0-9a-fA-F]` no componente)
- [ ] Nenhum `px` de espaçamento sem token (usar `var(--space-*)`)
- [ ] Nenhuma font-family inline — usar `var(--font-mono)` / `var(--font-sans)`
- [ ] Nenhum font-size sem token — usar `var(--text-*)`
- [ ] Botões com `:focus-visible` estilizado
- [ ] Cards com `:hover` e `:focus` via tokens
- [ ] Contraste WCAG AA verificado (4.5:1 texto normal, 3:1 texto grande)
- [ ] Breakpoints mobile-first, apenas `min-width`
- [ ] Nenhum `scroll-behavior: smooth` (conflita com Lenis)
