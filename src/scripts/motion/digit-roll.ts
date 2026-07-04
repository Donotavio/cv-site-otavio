/**
 * Padrão (extensão de count-up): digit-roll — "telemetria de dados"
 * Fonte: .opencode/skills/web-motion.md (Blueprint)
 *
 * Efeito slot-machine / odômetro: cada dígito de um número rola verticalmente
 * de 0 até o seu valor final quando entra no viewport. Premiado no Awwwards
 * para "big numbers". Aqui mantemos o feel premium calmo (expo.out, durações
 * longas) e o vocabulário blueprint.
 *
 * Como funciona:
 *  - Para um valor numérico ("10", "15", "3"), cada caractere de dígito vira
 *    uma "coluna" (.digit-col) contendo a sequência 0..9 empilhada
 *    verticalmente dentro de uma janela com overflow:hidden (.digit-roll).
 *  - A coluna é deslocada via translateY (transform → GPU) para revelar o
 *    dígito final. Stagger entre colunas (esquerda→direita) cria a sensação
 *    de telemetria assentando.
 *  - Sufixos textuais ("+", " Clouds") e prefixos são preservados como texto
 *    estático ao lado das colunas.
 *  - Valores puramente textuais ("Petabytes") recebem um fade/scramble curto
 *    (scrambleText) — sem rolagem de dígitos.
 *
 * Acessibilidade & SSG:
 *  - Sem motion (prefers-reduced-motion): o valor final é escrito direto como
 *    texto simples, sem montar colunas.
 *  - O HTML SSG já nasce com o valor final visível (textContent). Só montamos
 *    as colunas quando vamos animar; portanto sem JS o número permanece legível.
 *  - Só transform/opacity nos tweens.
 */

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { DURATIONS, EASINGS, STAGGER, motionOk } from './constants';
import { registerCleaner } from './cleanup';

gsap.registerPlugin(ScrollTrigger);

/** Caracteres do scramble para valores textuais (estética telemetria). */
const SCRAMBLE_CHARS = '0123456789#@%&▚▞▙▟░▒';

/** Escreve o valor final como texto simples (fallback / reduced-motion). */
function setStatic(el: HTMLElement, value: string): void {
  el.textContent = value;
}

/**
 * Monta a estrutura de colunas para um valor com dígitos.
 * Retorna a lista de colunas roláveis (na ordem do markup) para animar depois.
 */
function buildDigitMarkup(el: HTMLElement, value: string): HTMLElement[] {
  el.textContent = '';
  el.classList.add('digit-roll-host');

  const cols: HTMLElement[] = [];

  for (const ch of value) {
    if (ch >= '0' && ch <= '9') {
      const roll = document.createElement('span');
      roll.className = 'digit-roll';
      roll.setAttribute('aria-hidden', 'true');

      const col = document.createElement('span');
      col.className = 'digit-col';
      // empilha 0..9 e repete o dígito final no topo? Não — sequência simples
      // 0..9, deslocamos para o índice do dígito-alvo.
      for (let n = 0; n <= 9; n++) {
        const cell = document.createElement('span');
        cell.className = 'digit-cell';
        cell.textContent = String(n);
        col.appendChild(cell);
      }
      col.dataset.target = ch;
      roll.appendChild(col);
      el.appendChild(roll);
      cols.push(col);
    } else {
      // sufixo/prefixo/espaço/símbolo — estático
      const fixed = document.createElement('span');
      fixed.className = 'digit-fixed';
      fixed.textContent = ch;
      el.appendChild(fixed);
    }
  }

  // valor acessível para leitores de tela (as colunas são aria-hidden)
  el.setAttribute('aria-label', value);

  return cols;
}

/**
 * Anima as colunas rolando do 0 até o dígito-alvo, com stagger L→R.
 *
 * ⚠️ COUPLING CSS ↔ JS (NÃO QUEBRAR): o offset `yPercent: -target * 10`
 * depende diretamente do CSS do componente (Impact.astro):
 *   `.digit-cell { height: 1em; }`  e  `.digit-col { will-change: transform; }`
 *
 * Como cada coluna empilha EXATAMENTE 10 células (0..9) e cada uma mede 1em,
 * o deslocamento por dígito é exatamente 10% da altura total da coluna — daí
 * o `* 10`. `yPercent` é relativo à altura do próprio elemento (a coluna),
 * NÃO da célula; por isso funciona com qualquer `font-size` (a coluna cresce
 * proporcionalmente às células de 1em).
 *
 * Casos que QUEBRAM o offset (exigem revisão aqui E no CSS):
 *  - Mudar o número de células por coluna (ex.: prefixar 0..9 com um "0" extra
 *    para loop infinito) → `* 10` deixa de ser 1/N.
 *  - Altura variável entre células (ex.: `height: auto`) → o `1/N` deixa de
 *    ser uniforme e `yPercent` aponta para o dígito errado.
 *  - Trocar `yPercent` por `y` em px/em fixo sem recalcular contra o CSS.
 *
 * Sempre que tocar no markup/CSS das células, validar visualmente TODOS os
 * dígitos (0..9) na seção Impact e atualizar este comentário + o fator abaixo.
 *
 * will-change cleanup: `.digit-col { will-change: transform }` é permanente no
 * CSS (promove a composited layer para evitar jank no roll). Após o tween,
 * resetamos para `auto` no `onComplete` — libera a layer e reduz o footprint
 * de GPU memory (web-motion.md guardrail). Sem este reset, cada métrica do
 * Impact mantém uma layer alocada para sempre, mesmo depois de assentada.
 */
function rollColumns(cols: HTMLElement[]): void {
  cols.forEach((col, i) => {
    const target = parseInt(col.dataset.target ?? '0', 10);
    // cada célula ocupa 1em de altura (line-height controlado no CSS host).
    // translateY negativo em "em" desloca para o dígito-alvo.
    gsap.fromTo(
      col,
      { yPercent: 0 },
      {
        yPercent: -target * 10, // 10 células → cada dígito = 10% da coluna
        duration: DURATIONS.entrance,
        ease: EASINGS.outStrong,
        delay: i * STAGGER.tight,
        // Libera a composited layer após o roll. `.digit-col` tem
        // will-change:transform permanente no CSS (Impact.astro); sem este
        // reset, a layer GPU persiste indefinidamente após a animação.
        onComplete: () => {
          col.style.willChange = 'auto';
        },
      },
    );
  });
}

/**
 * Scramble curto para valores textuais ("Petabytes"): embaralha caracteres
 * e resolve para o valor final. Fade-in no contêiner.
 */
function scrambleText(el: HTMLElement, value: string): void {
  el.textContent = value;
  const chars = value.split('');
  const proxy = { p: 0 };

  gsap.fromTo(
    el,
    { opacity: 0 },
    { opacity: 1, duration: DURATIONS.normal, ease: EASINGS.out },
  );

  gsap.to(proxy, {
    p: 1,
    duration: DURATIONS.slow,
    ease: EASINGS.inOut,
    onUpdate: () => {
      const settled = Math.floor(proxy.p * chars.length);
      const out = chars
        .map((c, i) => {
          if (c === ' ' || i < settled) return c;
          return SCRAMBLE_CHARS[Math.floor(Math.random() * SCRAMBLE_CHARS.length)];
        })
        .join('');
      el.textContent = out;
    },
    onComplete: () => {
      el.textContent = value;
    },
  });
}

/**
 * Aplica o efeito a um elemento.
 * @param el     elemento alvo (deve conter o valor final em data-roll-value
 *               ou no próprio textContent)
 * @param trigger elemento que dispara o ScrollTrigger (default: el)
 */
export function digitRoll(el: HTMLElement, trigger?: Element): void {
  const value = (el.dataset.rollValue ?? el.textContent ?? '').trim();
  if (!value) return;

  const hasDigit = /\d/.test(value);

  // Sem motion: valor final direto, sem montar colunas.
  if (!motionOk) {
    setStatic(el, value);
    return;
  }

  // gsap.context() rastreia tweens + ScrollTrigger para teardown limpo.
  const ctx = gsap.context(() => {
    const run = () => {
      if (hasDigit) {
        const cols = buildDigitMarkup(el, value);
        rollColumns(cols);
      } else {
        scrambleText(el, value);
      }
    };

    const triggerEl = trigger ?? el;
    const rect = triggerEl.getBoundingClientRect();
    const alreadyVisible =
      rect.top < window.innerHeight * 0.85 && rect.bottom > 0;

    if (alreadyVisible) {
      run();
      return;
    }

    ScrollTrigger.create({
      trigger: triggerEl,
      start: 'top 85%',
      once: true,
      onEnter: run,
    });
  });
  registerCleaner(() => ctx.revert());
}
