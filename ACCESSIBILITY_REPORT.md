# Accessibility & Performance Report — PIX Observatory

**Página auditada:** `http://localhost:4321/cv-site-otavio/pix-observatory/`
**Metodologia:** Lighthouse v13 (headless Chrome) rodado 2x — (1) contra o dev server Astro, (2) contra o build de produção (`astro build` → `dist/`, servido estático) — combinado com leitura estática de código (`pix-observatory.astro`, `PixAgent.astro`, `tokens.css`) e cálculo manual de contraste WCAG (fórmula de luminância relativa) para validar/complementar o que os scanners automáticos não capturam.

> **Nota metodológica importante:** o dev server Astro (não-minificado, com client HMR) infla os números de performance (LCP ~20s, FCP ~11s) e **não deve ser usado como referência**. Os números de performance abaixo usam o build de produção. A auditoria de acessibilidade, no entanto, é válida em ambos, pois independe de minificação.

---

## Executive Summary

- **Lighthouse (prod build, desktop):** Performance 81 · Accessibility 96 · Best Practices 100 · SEO 100
- **Lighthouse (prod build, mobile, simulado):** Performance 82 · Accessibility 96 · Best Practices 100 · SEO 100
- **Blockers:** 2 críticos, 4 médios, 5 baixos
- **WCAG 2.1 AA Compliance:** **Fail** — falha sistêmica de contraste no token `--pix-green` usado como cor de texto
- **Recomendação:** ⚠ **Precisa de remediação antes do launch** (o item crítico de contraste é rápido de corrigir — 1 novo token de cor + find/replace)

---

## Lighthouse Scores (v13, build de produção)

| Métrica | Desktop | Mobile (simulado) | Target | Status |
|---|---|---|---|---|
| Performance | 81 | 82 | ≥90 | ⚠ Abaixo |
| Accessibility | 96 | 96 | ≥90 | ✓ (mas ver ressalva abaixo) |
| Best Practices | 100 | 100 | ≥90 | ✓ |
| SEO | 100 | 100 | ≥90 | ✓ |
| FCP | 2.2s | 2.2s | <2.5s | ✓ (na margem) |
| **LCP** | **4.6s** | **4.4s** | <2.5s | ✗ **Falha** |
| CLS | 0 | 0 | <0.1 | ✓ Excelente |
| TBT | 0ms | 0ms | — | ✓ Excelente |
| Total byte weight | 567 KiB | 567 KiB | — | Aceitável |

⚠ **Ressalva sobre Accessibility=96:** o axe/Lighthouse só varre elementos com `opacity > 0` no momento do scan. Como quase todo o conteúdo da página usa `gsap.from({opacity:0, y:32}, {scrollTrigger:{start:'top 88%'}})` (padrão `revealUp`), **a maior parte do conteúdo abaixo da dobra está com `opacity:0` durante o scan automatizado** e é silenciosamente ignorada pelo auditor de contraste. O score real de acessibilidade da página, considerando todos os elementos, é **mais baixo que 96** — a auditoria manual abaixo encontrou ~10 elementos adicionais com o mesmo problema de contraste que o scanner não viu.

---

## 🔴 Achado Crítico #1 — Falha sistêmica de contraste no token `--pix-green`

**Severidade: CRÍTICO — bloqueia WCAG 2.1 AA (1.4.3 Contrast Minimum)**

`--pix-green: #00A651` (`src/styles/tokens.css:90`) tem contraste de **apenas 3.19:1** contra fundos claros (`--paper`, `--paper-soft`, `--paper-card`, todos ~branco). O mínimo exigido para texto normal é **4.5:1**. Isso não é um problema pontual — é o token de cor de destaque de toda a página, usado como **cor de texto** (não só de fundo/borda) em pelo menos 9 lugares:

| Elemento | Arquivo:linha | Contraste medido | Texto real ou decorativo? |
|---|---|---|---|
| `.pix-agent__fab-label` ("Pergunte ao PIX") — cor `--paper` sobre fundo `--pix-green` | `PixAgent.astro:114` + estilo `:142-155` | **3.14:1** | **Real — CTA principal, sempre visível** |
| `.pix-metric__value--green` (KPI "258M+", métrica hero) | `pix-observatory.astro:118` + `:1075-1077` | **3.19:1** | **Real — o número mais importante da página** |
| `.pix-growth-chart__unit` ("tx/dia · M") | `pix-observatory.astro:304` + `:1127-1129` | **3.19:1** | Real (mesmo com `aria-hidden`, contraste visual ainda se aplica) |
| `.pix-growth-chart__bars` (gráfico ASCII) | `pix-observatory.astro:307-312` + `:1136-1143` | **3.19:1** | Decorativo, mas ainda perceptível |
| `.pix-news__source` (badge "Fonte") texto sobre `--pix-green-dim` | `pix-observatory.astro:1314-1327` | **2.67:1** | **Real — nome da fonte da notícia** |
| `.pix-news__index` (numeração "01", "02"...) | `pix-observatory.astro:1266-1276` | **2.90:1** | Decorativo (`aria-hidden`) |
| `.pix-pipeline-strip__badge--gh` ("AI") | `pix-observatory.astro:290` + `:1411-1415` | **2.67:1** | **Real — label do badge** |
| `.pix-agent__author--ai` ("pix-ai") | `PixAgent.astro:58,345` | **2.67:1** (sobre `--pix-green-dim`) | Decorativo (`aria-hidden`) |
| `.hero-sparkline` / `.hero-spark-label` | `pix-observatory.astro:888-899` | **3.19:1** | Decorativo (`aria-hidden`) |

Os badges de camada Bronze/Silver/Gold também falham, com o mesmo padrão (cor da camada como texto sobre `*-dim` do próprio tom):

| Badge | Contraste medido |
|---|---|
| `.pix-pipeline-strip__badge--bronze` / `.arch-card__badge--bronze` | **2.96:1** |
| `.pix-pipeline-strip__badge--silver` / `.arch-card__badge--silver` | **2.69:1** |
| `.pix-pipeline-strip__badge--gold` / `.arch-card__badge--gold` | **2.26:1** — o pior de todos |

**Confirmado por scanner automático:** o Lighthouse (mesmo só vendo os elementos com opacity>0 no momento do scan) já pegou 2 desses (`.pix-growth-chart__unit` e `.pix-growth-chart__bars`) com score 0 no audit `color-contrast`.

### Remediação recomendada

Criar um segundo token, **mais escuro**, para uso exclusivo em texto (mantendo `--pix-green` para fundos/acentos onde ele já funciona bem):

```css
/* tokens.css — adicionar próximo à linha 90 */
--pix-green:      #00A651;  /* uso: fundos, bordas, ícones grandes — NÃO usar como cor de texto em fundo claro */
--pix-green-ink:  #007C3C;  /* uso: texto sobre --paper/--paper-soft/--paper-card — 5.28:1, passa AA */
```

Depois, trocar `color: var(--pix-green)` → `color: var(--pix-green-ink)` em todos os seletores de **texto** listados na tabela acima (não nos usos de fundo/borda/ícone puramente decorativo onde o fundo é escuro, como `.pix-agent__fab` background). Para os badges Bronze/Silver/Gold, mesma lógica: escurecer ~20-25% cada cor de camada para uso como texto, mantendo os tons originais em `border`/`background`.

**Efeito colateral a testar:** o FAB (`.pix-agent__fab`) tem fundo `--pix-green` com texto `--paper` — como o fundo aqui é a cor sólida (não diluída), a correção correta é trocar a cor do **texto** para algo com contraste suficiente contra `#00A651` (ex: `--ink` #0A0A0A dá 6.2:1) ou escurecer o fundo do botão em vez do texto.

---

## 🔴 Achado Crítico #2 — LCP de 4.4-4.6s (falha do target <2.5s)

**Severidade: CRÍTICO — Lighthouse Performance**

Mesmo no build de produção, LCP fica em **4.4-4.6s**, quase 2x o target. Causas identificadas pelo Lighthouse Insights:

1. **CSS bloqueando render:** `pix-observatory.css` (27KB) e `Footer.css` (17KB) são carregados de forma síncrona/bloqueante — juntos custam ~754ms + 304ms de delay antes do primeiro paint (`render-blocking-insight`).
2. **`unused-css-rules`:** ~12KB de CSS não utilizado nesta página (provavelmente CSS de outras páginas compartilhado via bundle).
3. **`unused-javascript`:** ~50KB de JS estimado como não utilizado — o candidato mais provável é o chunk `constants.COqmzvmr.js` (113KB não comprimido / 44KB gzip) que empacota **GSAP + ScrollTrigger inteiros** só para os efeitos `revealUp`/`countUp`/`hairlineDraw`.
4. **`cache-insight`:** fontes (`inter-var.woff2` 230KB!, `ibmplexmono-*.woff2`) e o bundle GSAP não têm headers de cache de longa duração configurados no ambiente de teste (isso é esperado no `http-server` local — **validar no GitHub Pages real**, que geralmente já aplica cache/CDN, mas vale confirmar).

### Remediação recomendada

- Considerar `astro:assets` ou inlining de CSS crítico específico da seção hero (above-the-fold) e carregar o resto do CSS da página de forma não bloqueante.
- Avaliar code-splitting do GSAP: `revealUp`/`hairlineDraw` já são "nice-to-have" motion — usar `IntersectionObserver` nativo para o count-up simples (`pix-metric__value`) evitaria carregar ScrollTrigger só para 3 números, deixando GSAP só onde realmente precisa de easing customizado.
- **`inter-var.woff2` de 230KB é pesado** para uma fonte variável — considerar subsetting (remover pesos/estilos não usados) ou trocar por uma fonte estática de 2-3 pesos fixos.
- Font `woff2` já usa `preload` (bom, visto no `<head>` gerado) — mantém.

---

## WCAG 2.1 AA Compliance

| Princípio | Status | Observações |
|---|---|---|
| **Perceivable** | ✗ Fail | Ver Achado Crítico #1 (contraste sistêmico) |
| **Operable** | ✓ Pass | Teclado, foco, Escape — tudo implementado corretamente (ver seção abaixo) |
| **Understandable** | ✓ Pass | `lang="pt-BR"`, labels associados, mensagens de erro claras no widget de notícias |
| **Robust** | ✓ Pass | `heading-order`, `landmark-one-main`, `button-name`, `link-name`, `aria-allowed-attr` — todos passam no Lighthouse |

---

## Auditoria do Agente Flutuante (`PixAgent.astro`)

### Pontos fortes (implementação correta) ✓

- `aria-expanded` / `aria-controls` / `aria-label` dinâmico no FAB, sincronizados corretamente em `openPanel()`/`closePanel()` (`PixAgent.astro:526-551`).
- `role="dialog"` + `aria-modal="false"` é coerente com o fato de **não** haver focus-trap — design intencional de painel não-modal, documentado no comentário do componente.
- **Escape fecha o painel** e retorna o foco ao FAB (`PixAgent.astro:606-608, 550`) — comportamento correto de "restore focus".
- Foco move para o `<input>` ~120ms após abrir (`PixAgent.astro:535`) — pequeno delay para esperar a animação de abertura, boa prática.
- `prefers-reduced-motion` respeitado tanto no CSS (`@media (prefers-reduced-motion: reduce)` em `:181-184, :197-199, :252-255, :320-322, :368-370`) quanto no JS (`closePanel()` verifica `matchMedia` antes de esperar `animationend`, `PixAgent.astro:548-549`) — **excelente**, evita o bug clássico de "painel nunca fecha porque a animação nunca dispara o evento".
- Chips de sugestão são `<button>` nativos — funcionam com Tab/Enter/Espaço de graça, sem JS extra.
- `role="log"` + `aria-live="polite"` nas mensagens (`PixAgent.astro:52-55`) — leitor de tela anuncia novas respostas sem interromper o usuário.
- Label do input associado corretamente via `<label for="pix-agent-input" class="sr-only">` (`PixAgent.astro:80`) — a classe `sr-only` está bem implementada (`clip: rect(0,0,0,0)`, não `display:none`), então o texto continua acessível a leitores de tela.
- Botão de enviar desabilitado (`disabled`) durante o processamento evita duplo-envio, com `:disabled` tendo contraste/opacidade adequados.

### Bugs encontrados

**🟡 MÉDIO — Foco pode escapar do painel para conteúdo visualmente obstruído**
Como `aria-modal="false"` e não há focus-trap, ao pressionar Tab a partir do último elemento focável do painel (`#pix-agent-send`), o foco avança para o próximo elemento do DOM — o próprio FAB, depois o `<Footer>`. Isso é *semanticamente* aceitável para um diálogo não-modal, mas como o painel é `position: fixed` (`PixAgent.astro:127-137`) e cobre até 560px de altura no canto inferior direito, em viewports baixos (ex.: notebook com zoom, ou mobile em paisagem) **elementos do footer podem estar visualmente atrás do painel** enquanto ainda são alcançáveis via Tab — o indicador de foco fica escondido sob o card do chat.
*Remediação:* ou (a) implementar focus-trap simples enquanto `isOpen === true` (Tab no último elemento volta ao primeiro), ou (b) adicionar `inert` / `aria-hidden` temporário no `<Footer>` enquanto o painel está aberto.

**🟢 BAIXO — Toque em mobile: FAB colapsa para ícone puro (~480px)**
Em `@media (max-width: 480px)` (`PixAgent.astro:214-217`), o label "Pergunte ao PIX" é ocultado (`display:none`) e o botão vira `padding: var(--space-4)` (16px). Isso funciona, mas o alvo de toque resultante fica em torno de **~56×56px** (ícone 24px + 16px×2 padding) — dentro do recomendado (WCAG 2.5.5 AAA pede 44px, 2.5.8 AA pede 24px na versão 2.2) então está OK, mas vale confirmar visualmente que o ícone sozinho comunica a função sem o label (dependência total do `aria-label` para usuários de leitor de tela, que já está presente e correto).

**🟢 BAIXO — Painel pode ficar com o input atrás do teclado virtual no iOS Safari**
O painel usa `height: min(560px, calc(100dvh - var(--space-24)))` (`PixAgent.astro:224`) — o uso de `dvh` é a escolha correta e moderna (se ajusta ao viewport visual quando o teclado abre). Porém, `position: fixed` em iOS Safari tem um bug histórico onde elementos fixos podem ficar posicionados incorretamente em relação ao *visual viewport* quando o teclado on-screen está ativo (o elemento é calculado contra o *layout viewport*). **Não foi possível confirmar em dispositivo real** neste ambiente — recomenda-se teste manual em iPhone real (Safari) com o teclado aberto, observando se `#pix-agent-input` permanece visível e clicável.

**🟢 BAIXO — Sem `Arrow keys`/navegação por seta entre chips de sugestão**
Os 3 chips de sugestão (`PixAgent.astro:68-70`) são `<button>` soltos, sem `role="group"` com navegação por setas (não é uma violação — WCAG não exige — mas o checklist do agente auditor pede teste de Arrow keys; aqui Tab sequencial funciona normalmente, então é apenas uma oportunidade de UX, não um bug).

---

## Auditoria do Widget de Notícias

### Pontos fortes ✓

- `<ol id="pix-news-list" role="list" aria-live="polite">` (`pix-observatory.astro:341`) — atualização de conteúdo assíncrono é anunciada a leitores de tela.
- Cada link tem `aria-label` completo combinando título + fonte + tempo relativo (`pix-observatory.astro:1887`) — evita o anti-padrão "leia mais" sem contexto.
- Erro de fetch tratado com fallback textual visível (`pix-observatory.astro:1906-1909`) — "feed indisponível — tente recarregar".
- `escapeHtml()` aplicado em todos os campos vindos do JSON externo (`pix-observatory.astro:1854-1858, 1879, 1885, 1887, 1890`) — protege contra XSS via feed RSS malicioso/comprometido. Boa prática de segurança que também beneficia a robustez de acessibilidade (evita HTML quebrado sendo injetado no DOM).

### Bugs encontrados

**🟡 MÉDIO — Sem timeout no `fetch()`, loading infinito possível**
`renderNews()` (`pix-observatory.astro:1860-1910`) faz `fetch(...)` sem `AbortController`/timeout algum. Se a rede estiver lenta ou o servidor não responder (sem erro explícito, apenas travado), a Promise nunca resolve/rejeita e o texto `"carregando feed…"` (`pix-observatory.astro:343`) **fica exibido indefinidamente**, sem fallback.
*Remediação:*
```js
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 6000);
const res = await fetch(url, { cache: 'no-cache', signal: controller.signal });
clearTimeout(timeoutId);
```

**🟡 MÉDIO — CLS potencial: placeholder de loading não reserva altura do grid final**
O estado de loading é um único `<li>` (`pix-observatory.astro:343`) sem grid — ocupa a altura de uma linha de texto. Quando os dados chegam, `list.innerHTML` é substituído por um grid de N cards (2 colunas × várias linhas no desktop) — a altura do container **salta** de ~1 linha para várias centenas de pixels, empurrando todo o conteúdo abaixo (seção de arquitetura, insights etc.) para baixo repentinamente. O Lighthouse não capturou isso porque o fetch local é instantâneo (<50ms), mas em conexões 3G/4G reais (request de `pix_news.json`, ~3.4KB) o delta de tempo é suficiente para o usuário perceber o salto — **CLS real, não medido pelo teste local**.
*Remediação:* reservar `min-height` no `.pix-news__list` (ex.: `min-height: 280px` no mobile / `420px` no desktop via media query) igual à altura média esperada de N cards, ou usar 2-3 skeleton cards cinza no lugar do texto "carregando feed…".

**🟢 BAIXO — `title="${source}"` duplica informação já presente no `aria-label` do link pai**
`pix-observatory.astro:1892` — o atributo `title` no badge de fonte é redundante com o `aria-label` do `<a>` pai (que já inclui a fonte). Não é um erro, mas pode gerar leitura duplicada em alguns leitores de tela que também expõem `title` como tooltip acessível. Baixo impacto, mas pode ser removido com segurança.

**🟢 BAIXO — `.pix-news__index::before` usa CSS `counter()` — texto não selecionável/copiável**
Os números "01", "02"... são gerados via `content: counter(news, decimal-leading-zero)` (`pix-observatory.astro:1274-1276`) e marcados `aria-hidden="true"` — comportamento correto para leitores de tela (é puramente decorativo, a ordem real já está no DOM/`<ol>`). Nenhuma ação necessária, apenas confirmando que está correto.

---

## Heading Hierarchy

**Status: ✓ Pass** (confirmado pelo audit `heading-order` do Lighthouse, score 1)

```
h1  "O maior sistema de pagamentos do mundo, em tempo real."     (linha 54)
 h2 "Telemetria do PIX"                                           (linha 91)
 h2 "Arquitetura do Pipeline"                                      (linha 357)
  h3 "BACEN API → Parquet Raw" (Bronze)                            (linha 379)
  h3 "Limpeza e Tipagem" (Silver)                                  (linha 403)
  h3 "Agregações Analíticas" (Gold)                                (linha 427)
  h3 "Orquestração automatizada"                                   (linha 452)
 h2 "Insights dos Dados"                                           (linha 486)
  h3 × 3 (insight cards)                                           (linhas 503, 523, 543)
 h2 "Anatomia dos Dados"                                           (linha 568)
  h3 × 3 (analysis cards)                                          (linhas 584, 608, 649)
 h2 "Stack Técnico"                                                (linha 677)
```

Nenhum nível pulado, um único `h1`, estrutura sequencial correta. **Sem problemas de acessibilidade aqui.**

**🟢 BAIXO — Rótulos numéricos (`mono-label`) fora de ordem, confuso para usuários que enxergam**
Os rótulos decorativos `<span class="mono-label">01</span>` / `02` / `05` / `05b` / `04` que precedem cada `<h2>` (linhas 90, 356, 485, 567, 676) **não seguem a ordem visual real da página**: Dashboard=`01`, Pipeline=`02`, Insights=`05`, Anatomia=`05b`, Stack=`04`. Isso não é um problema de WCAG (os spans têm `aria-hidden`? — **checar**: não têm `aria-hidden`, então leitores de tela também anunciam "05 Insights dos Dados", "05 b Anatomia dos Dados", "04 Stack Técnico" fora de ordem, o que é uma pequena inconsistência semântica). Recomenda-se renumerar sequencialmente (01→05) ou remover os números se as seções foram reordenadas ao longo do desenvolvimento.

---

## Color Contrast — Resumo Consolidado

| Elemento | Medido | Requisito | Status |
|---|---|---|---|
| Corpo de texto (`--ink-soft` #545454 sobre `--paper`) | ~7.5:1 | 4.5:1 | ✓ Pass |
| `--ink-faint` #6F6F6F sobre `--paper`/`--paper-soft`/`--paper-card` | 4.94 / 4.56 / 5.02:1 | 4.5:1 | ✓ Pass (documentado no próprio token, `tokens.css:16`) |
| **`--pix-green` como texto sobre fundos claros** | **3.19:1** | 4.5:1 | **✗ Fail (sistêmico, ver Crítico #1)** |
| Badge `pix-news__source` (verde s/ verde-dim) | 2.67:1 | 4.5:1 | ✗ Fail |
| Badge bronze (s/ bronze-dim) | 2.96:1 | 4.5:1 | ✗ Fail |
| Badge silver (s/ silver-dim) | 2.69:1 | 4.5:1 | ✗ Fail |
| Badge gold (s/ gold-dim) | 2.26:1 | 4.5:1 | ✗ Fail (pior caso) |
| FAB label (`--paper` s/ `--pix-green`) | 3.14:1 | 4.5:1 | ✗ Fail |
| `--accent` #1A1AFF (links/CTAs azuis) sobre `--paper` | ~8.6:1 (estimado) | 4.5:1 | ✓ Pass |

---

## Focus Visible & Keyboard Navigation

| Elemento | `:focus-visible` definido? | Arquivo:linha |
|---|---|---|
| FAB (`.pix-agent__fab`) | ✓ outline verde 2px | `PixAgent.astro:169-172` |
| Botão fechar (`.pix-agent__close`) | ✓ outline verde 2px | `PixAgent.astro:292` |
| Chips de sugestão (`.pix-agent__chip`) | ✓ outline verde 2px | `PixAgent.astro:397` |
| Botão enviar (`.pix-agent__send`) | ✓ outline verde 2px | `PixAgent.astro:449` |
| Input (`.pix-agent__input`) | Parcial — usa `:focus` (não `:focus-visible`) mudando só `border-color`, sem outline | `PixAgent.astro:432` |
| Links de notícia (`.pix-news__link`) | ✓ outline verde 2px | `pix-observatory.astro:1260-1263` |
| Links do hero (`.btn-primary`/`.btn-secondary`) | Depende do estilo global — não verificado neste escopo | — |

**🟢 BAIXO — Input do chat não tem outline de foco visível, só troca de borda**
`.pix-agent__input:focus { border-color: var(--pix-green); }` (`PixAgent.astro:432`) muda a cor da borda de 1px, mas não adiciona `outline`/`box-shadow`. É uma indicação de foco *mais sutil* que os outros elementos do mesmo painel (que usam outline 2px + offset). Não é uma falha de WCAG 2.4.7 (existe *alguma* indicação visível), mas é inconsistente com o padrão usado em todos os outros controles do mesmo componente, e pode ser insuficiente para usuários com baixa visão.
*Remediação:* alinhar com o padrão dos outros elementos: `outline: 2px solid var(--pix-green); outline-offset: 2px;` também no `:focus-visible` do input.

**Keyboard navigation — teste de fluxo lógico (análise estática):**
1. Skip-link "Ir para o conteúdo principal" presente no topo (`dist/index.html` gerado) — ✓ boa prática.
2. Header → nav → lang switcher → main content (hero → CTAs → KPIs → notícias → arquitetura → insights → análise → stack) → **PixAgent panel (se aberto) → FAB** → Footer.
3. Todo o agente é operável 100% via teclado: `Tab` até o FAB → `Enter`/`Espaço` abre → foco vai para o input → digitar → `Enter` envia → `Escape` fecha e retorna foco ao FAB. **Fluxo correto e completo, sem mouse.**
4. Único ponto de atenção: como não há focus-trap (ver Médio, seção do agente), `Tab` repetido dentro do painel aberto eventualmente sai dele e segue para o restante da página — comportamento intencional pelo design (`aria-modal="false"`), mas requer o ajuste de "conteúdo obstruído" mencionado acima.

---

## Reduced-Motion Testing

| Verificação | Status |
|---|---|
| `prefers-reduced-motion` detectado via `matchMedia`/CSS media query | ✓ |
| Animação do FAB (`fab-attention`, `fab-icon-bob`) desabilitada | ✓ (`PixAgent.astro:181-199`) |
| Animação de abrir/fechar painel desabilitada, com fallback JS correto (sem esperar `animationend` que nunca disparia) | ✓ (`PixAgent.astro:252-255, 548-549`) |
| Animação de mensagens (`msg-in`) desabilitada | ✓ (`PixAgent.astro:320-322`) |
| Animação de "digitando..." (`agent-typing`) desabilitada, mas mantém `content: '...'` estático | ✓ (`PixAgent.astro:368-370`) |
| Pulso do "live dot" das notícias desabilitado | ✓ (`pix-observatory.astro:1209-1211`) |
| GSAP `revealUp`/`countUp`/`hairlineDraw` respeitam `motionOk` (flag central) | ✓ (`count-up.ts:27-30`, uso de `motionOk` em todos os scripts de motion) |

**Excelente cobertura de `prefers-reduced-motion`** — todas as animações CSS têm override, e o `motionOk` central do sistema de motion garante que o JS (GSAP) também respeita a preferência, incluindo o fallback correto de "mostrar valor final direto" no `countUp` (`count-up.ts:27-30`) em vez de pular a animação e deixar o número em 0.

---

## Performance Profiling (build de produção)

| Métrica | Valor | Target | Status |
|---|---|---|---|
| FCP | 2.2s | <2.5s | ✓ |
| LCP | 4.4–4.6s | <2.5s | ✗ Fail |
| CLS (medido) | 0 | <0.1 | ✓ (mas ver ressalva de CLS do widget de notícias em rede real) |
| TBT | 0ms | — | ✓ Excelente |
| Total byte weight | 567 KiB | — | Aceitável |
| HTML renderizado (prod, minificado) | 50.5 KB (~9.2 KB gzip) | — | ✓ Bom |
| HTML (dev server, não minificado) | 111 KB | — | N/A (não é o número de produção) |
| CSS da página (`pix-observatory.*.css`) | 27 KB (~4 KB gzip) | — | Aceitável |
| Bundle GSAP+ScrollTrigger (`constants.*.js`) | 113 KB (~44 KB gzip) | — | ⚠ Pesado para o uso (reveal + counter) |
| Scripts inline vs. módulos | 0 scripts síncronos bloqueantes — todos `type="module"` (deferred nativamente) ou com `defer` explícito (`i18n.js`) | — | ✓ Ótima prática, confirmado no HTML gerado |

### Scripts e bloqueio de render
Nenhum script bloqueia o parsing do HTML — todos os `<script>` da página (`pix-observatory.astro:1764, 1824`) e do componente (`PixAgent.astro:454`) são compilados pelo Astro para `<script type="module" src="...">`, que é deferido nativamente pelo browser. **Sem problema aqui.**

### CountUp / GSAP — thrashing?
`countUp()` (`count-up.ts:32-40`) atualiza `el.textContent` a cada tick do `gsap.to()` (~60fps durante a duração da animação). Como são poucos elementos (6 KPIs com `data-count-to`) e a alteração é apenas de texto dentro de um `<span>` inline sem afetar layout de elementos vizinhos de forma significativa, **não há layout thrashing real** — o custo é де reflow local pequeno, não em cascata. Nenhuma leitura de `getBoundingClientRect()`/`offsetWidth` é feita dentro do loop `onUpdate`, então não há o padrão clássico de "force synchronous layout" alternando leitura/escrita. **Aprovado.**

### Fetch de `pix_news.json`
- ✓ Tratamento de erro com `try/catch` e mensagem de fallback visível.
- ✗ Sem timeout/`AbortController` (ver Médio, seção de notícias).
- ✗ Placeholder de loading não reserva espaço equivalente ao grid final (ver Médio, CLS, seção de notícias).
- ✓ Usa `cache: 'no-cache'` para sempre pegar dados atualizados — correto para um feed de notícias.

---

## Mobile Testing (análise estática de CSS + emulação Lighthouse mobile)

| Item | Resultado |
|---|---|
| FAB em <480px | Label ocultado, ícone-somente, `aria-label` mantém acessibilidade; alvo de toque ~56×56px — adequado |
| Painel de chat cabe na tela | ✓ `width: min(400px, 100vw - 32px)`, `height: min(560px, 100dvh - 96px)` — usa `dvh`, se adapta corretamente à altura disponível |
| Teclado virtual x painel fixo | ⚠ Não testável neste ambiente (sem device real) — risco conhecido de `position:fixed` + iOS Safari + teclado; recomenda-se teste manual |
| Grid de notícias em mobile | ✓ 1 coluna abaixo de 768px (`pix-observatory.astro:1224-1229`), correto |
| **Cards de "Anatomia dos Dados" em mobile** | **Ver Bug Funcional abaixo — CSS ausente afeta todos os breakpoints, incluindo mobile** |

---

## 🟠 Bug Funcional (fora do escopo estrito de a11y/perf, mas encontrado durante a auditoria)

**Severidade: ALTO (visual/funcional) — não é uma falha de acessibilidade ou performance per se, mas quebra a experiência da seção "Anatomia dos Dados" em todos os viewports, incluindo mobile**

A seção `#analysis` ("Anatomia dos Dados", `pix-observatory.astro:564-667`) usa as classes `.analysis-grid`, `.analysis-card`, `.analysis-card__head/__title/__desc/__foot`, `.analysis-chart`, `.analysis-bars`/`.analysis-bar__track`/`.analysis-bar__fill`, e `.analysis-donut` — **nenhuma dessas classes tem definição de CSS em nenhum lugar do projeto** (confirmado via `grep` no código-fonte e no CSS compilado em `dist/_astro/pix-observatory.*.css` — zero ocorrências).

Impacto real por elemento:
- `.analysis-grid`: sem `display:grid`, os 3 `<article class="card analysis-card">` empilham em coluna única em **todos os breakpoints** (não é responsivo por acidente, mas nunca fica em 3 colunas no desktop como as outras seções da página).
- `.analysis-bars`/`.analysis-bar__track`/`.analysis-bar__fill` (cards "Composição de chaves"): são `<span>`/`<div>` sem `display:block`, `height`, ou `background` no track — o `width: 32%` inline no `__fill` não tem efeito visível porque o elemento não tem altura. **As barras de progresso ficam invisíveis** — o card mostra só os rótulos ("Celular", "32%") sem nenhuma representação visual da porcentagem.
- `.analysis-chart__bars` / `.analysis-donut__ascii`: são `<pre>`, então herdam `font-family: monospace` do user-agent stylesheet por padrão — a arte ASCII permanece legível "por acidente", mas sem o espaçamento/tamanho customizados que o resto do site usa (`--font-mono`, `--text-sm`, `--leading-loose` etc.).
- Cards ficam com apenas o estilo genérico de `.card` (borda, padding, sombra no hover) — sem os `gap`/`flex-direction` esperados, o espaçamento interno entre título/descrição/gráfico/rodapé fica com o `margin` default do browser (inconsistente entre navegadores).

**Remediação:** adicionar o bloco de CSS faltante para `.analysis-*` (provavelmente foi removido acidentalmente durante uma refatoração, já que os outros grids da página — `.insights-grid`, `.arch-grid` — seguem exatamente o mesmo padrão de `display:grid` responsivo que falta aqui). Sugestão de ponto de inserção: após a regra `.insight-card__stat-label` (`pix-observatory.astro:1657-1662`), replicando o padrão de `.insights-grid`/`.insight-card` já existente, mais estilos específicos para `.analysis-bar__track` (`height`, `background: var(--paper-soft)`, `border-radius`) e `.analysis-bar__fill` (`height: 100%`, `background: var(--pix-green-ink)` — usando o token corrigido do Achado Crítico #1, já que é uma barra sólida e não precisa do tom claro).

---

## Issues & Remediation — Sumário Priorizado

### 🔴 Críticos (bloqueiam launch)
1. **Contraste sistêmico de `--pix-green` como texto** (WCAG 1.4.3) — Impacto: usuários com baixa visão não conseguem ler o KPI principal (258M+), o CTA do agente, os badges de fonte/camada. Esforço: **baixo** (1 token novo + find/replace em ~9 seletores).
2. **LCP 4.4-4.6s** (Lighthouse Performance) — Impacto: usuários em rede móvel percebem a página como lenta para carregar visualmente. Esforço: **médio** (code-splitting do GSAP, CSS crítico inline, subset de fonte).

### 🟡 Médios (deveriam ser corrigidos)
3. **Foco pode ficar visualmente obstruído** atrás do painel do agente ao tabular além do último campo. Esforço: baixo (focus-trap simples ou `inert` no footer).
4. **Fetch de notícias sem timeout** — loading infinito em rede instável. Esforço: baixo (`AbortController`).
5. **CLS potencial no widget de notícias** em rede lenta (placeholder não reserva altura). Esforço: baixo (`min-height` no container).
6. **Bug funcional: CSS ausente para toda a seção "Anatomia dos Dados"** — barras de progresso invisíveis, grid não responsivo. Esforço: médio (recriar bloco de CSS ~60 linhas seguindo padrão de `.insights-grid`).

### 🟢 Baixos (nice-to-have)
7. Input do chat sem `outline` de foco (só muda borda) — inconsistente com os outros controles do mesmo painel.
8. Rótulos numéricos de seção (`01`, `02`, `05`, `05b`, `04`) fora de ordem sequencial, incluindo para leitores de tela (sem `aria-hidden`).
9. Atributo `title` redundante no badge de fonte das notícias.
10. Teste manual pendente: painel do chat + teclado virtual no iOS Safari real (`position:fixed` é historicamente problemático).
11. Fonte variável `inter-var.woff2` (230KB) é candidata a subsetting/otimização.

---

## Browser & Device Compatibility

Não testado neste ambiente (sem acesso a browsers reais além do Chrome headless via Lighthouse). Todo o CSS usado é sintaxe padrão moderna (`clamp()`, custom properties, `dvh`, `:focus-visible`, `mask`) — compatível com Chrome/Firefox/Safari/Edge nas últimas 2 versões majors. `dvh` tem suporte a partir de iOS Safari 15.4+/Chrome 108+ — **confirmar browser support mínimo do projeto** antes do launch se precisar suportar iOS mais antigo (fallback seria usar `vh` com JS de correção).

## Assistive Technology Compatibility

Não testado com VoiceOver/NVDA reais neste ambiente (ausência de acesso a hardware/OS com AT instalado). A análise de código sugere boa compatibilidade esperada (landmarks corretos, `aria-live`, `role="log"`, `role="dialog"`, labels associados), mas **recomenda-se validação manual com VoiceOver antes do launch**, especialmente para:
- Anúncio da resposta do agente após envio de pergunta (`aria-live="polite"` no container de mensagens).
- Anúncio de atualização do feed de notícias (`aria-live="polite"` na lista).

---

## Recommendations for Maintenance

1. Adicionar teste automatizado de contraste (axe-core em CI) para pegar regressões do Achado Crítico #1 antes do merge.
2. Revisar todo uso de `var(--pix-green)`/`var(--medallion-*)` como `color` (não `background`/`border`) no restante do site (Header, Footer, outras páginas) — o mesmo padrão de token "só funciona como fundo" pode se repetir em outras páginas do site.
3. Considerar mover o audit de contraste para rodar **após** todas as animações `revealUp` completarem (ex.: `--motion-ok: false` via flag de teste, ou forçar `opacity:1` via CSS de override no ambiente de CI) para evitar falso-negativo de cobertura no scanner automático.
4. Re-rodar Lighthouse no domínio real do GitHub Pages (não local) após deploy, para validar compressão/cache reais da CDN.

---

## Sign-Off

- **Auditor:** A11y & Performance Auditor Agent
- **Data:** 2026-06-30
- **Status:** ⚠ **Needs fixes** — 2 itens críticos e 1 bug funcional alto identificados; nenhum é estruturalmente complexo de corrigir (estimativa total: 1-2 dias de trabalho de frontend). Recomenda-se nova rodada de auditoria após as correções, com foco em revalidar contraste e re-medir LCP no build de produção.
