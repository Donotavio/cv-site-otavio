/**
 * Padrão 4: count-up
 * Números grandes contam de 0 até o valor ao entrar no viewport.
 * Fonte: .claude/skills/web-motion.md (Blueprint)
 *
 * Usar em: métricas de impacto, números-chave.
 * O elemento alvo deve ter data-count-to="42" (valor final numérico).
 * Sufixos/prefixos (+, %, M) preservados via data-count-suffix / data-count-prefix.
 */

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { DURATIONS, EASINGS, motionOk } from './constants';

gsap.registerPlugin(ScrollTrigger);

export function countUp(el: HTMLElement) {
  const target = parseFloat(el.dataset.countTo ?? '0');
  const prefix = el.dataset.countPrefix ?? '';
  const suffix = el.dataset.countSuffix ?? '';
  const decimals = parseInt(el.dataset.countDecimals ?? '0', 10);

  const format = (v: number) =>
    `${prefix}${v.toFixed(decimals)}${suffix}`;

  // Sem motion: mostra valor final direto
  if (!motionOk) {
    el.textContent = format(target);
    return;
  }

  const obj = { val: 0 };
  gsap.to(obj, {
    val: target,
    duration: DURATIONS.entrance,
    ease: EASINGS.outStrong,
    onUpdate: () => { el.textContent = format(obj.val); },
    scrollTrigger: {
      trigger: el,
      start: 'top 85%',
      once: true,
    },
  });
}

/** Aplica count-up a todos os [data-count-to] dentro de um container. */
export function countUpAll(container: ParentNode = document) {
  container.querySelectorAll<HTMLElement>('[data-count-to]').forEach(countUp);
}
