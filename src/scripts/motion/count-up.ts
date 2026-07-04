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
import { registerCleaner } from './cleanup';

gsap.registerPlugin(ScrollTrigger);

export function countUp(el: HTMLElement, trigger?: Element): void {
  const target = parseFloat(el.dataset.countTo ?? '0');
  const prefix = el.dataset.countPrefix ?? '';
  const suffix = el.dataset.countSuffix ?? '';
  const decimals = parseInt(el.dataset.countDecimals ?? '0', 10);

  // pt-BR usa vírgula como separador decimal (única localidade do site —
  // ver AGENTS.md/i18n). toFixed() sempre usa ponto; troca só quando há
  // casas decimais para não afetar contadores inteiros já existentes.
  const format = (v: number) => {
    const num = v.toFixed(decimals);
    return `${prefix}${decimals > 0 ? num.replace('.', ',') : num}${suffix}`;
  };

  // Sem motion: mostra valor final direto
  if (!motionOk) {
    el.textContent = format(target);
    return;
  }

  // gsap.context() rastreia tweens + ScrollTrigger criados dentro, permitindo
  // teardown limpo em SPA / view transitions via registerCleaner.
  const ctx = gsap.context(() => {
    const run = () => {
      const obj = { val: 0 };
      gsap.to(obj, {
        val: target,
        duration: DURATIONS.entrance,
        ease: EASINGS.outStrong,
        onUpdate: () => { el.textContent = format(obj.val); },
      });
    };

    const triggerEl = trigger ?? el;

    // Se o elemento já está visível no load, conta imediatamente.
    // (ScrollTrigger com start 'top 85%' não dispara de forma confiável
    //  para elementos que já passaram do ponto de start no carregamento.)
    const rect = triggerEl.getBoundingClientRect();
    const alreadyVisible = rect.top < window.innerHeight * 0.85 && rect.bottom > 0;

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

/** Aplica count-up a todos os [data-count-to] dentro de um container. */
export function countUpAll(container: ParentNode = document): void {
  // Wrapper em arrow fn: forEach passa (value, key, parent); countUp espera
  // (el, trigger?). Passar countUp direto quebrava a tipagem.
  container.querySelectorAll<HTMLElement>('[data-count-to]').forEach((el) => countUp(el));
}
