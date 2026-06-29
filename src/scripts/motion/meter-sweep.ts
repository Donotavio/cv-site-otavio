/**
 * Padrão derivado: meter-sweep
 * "Carregando dados" — o medidor mono [████··] varre da esquerda p/ direita,
 * revelando os blocos em sequência como um terminal carregando uma barra.
 * Fonte: vocabulário blueprint (.opencode/skills/web-motion.md)
 *
 * Técnica: clip-path inset (right → 0). Só anima clip-path (composited, sem
 * recalcular layout). O texto final do medidor JÁ está no HTML (visível sem JS
 * e com reduced-motion). Coeso com o feel premium calmo: easing expo.out,
 * duração normal, desaceleração longa — NÃO snappy.
 *
 * O elemento alvo é o .skill-meter (mono [████··]). O sweep usa o início
 * apertado (clip 100%) só quando motion está ok; default CSS = revelado.
 *
 * Detecção de já-visível replica count-up.ts: se o grupo já está no viewport
 * no load, dispara imediatamente em vez de criar ScrollTrigger (que não dispara
 * de forma confiável para elementos já passados do start).
 */

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { DURATIONS, EASINGS, motionOk, STAGGER } from './constants';

gsap.registerPlugin(ScrollTrigger);

/**
 * Anima os medidores de um grupo varrendo da esquerda p/ direita.
 * @param meters  - NodeList/array dos .skill-meter do grupo
 * @param trigger - container do grupo (ScrollTrigger)
 * @param stagger - delay entre medidores (default STAGGER.tight)
 */
export function meterSweep(
  meters: Element[] | NodeListOf<Element>,
  trigger: Element,
  stagger: number = STAGGER.tight,
) {
  const list = Array.from(meters);
  if (!list.length) return;

  // Sem motion: medidor cheio já está no HTML, nada a fazer.
  if (!motionOk) return;

  const run = () => {
    gsap.fromTo(
      list,
      { clipPath: 'inset(0 100% 0 0)' },
      {
        clipPath: 'inset(0 0% 0 0)',
        duration: DURATIONS.normal,
        ease: EASINGS.out, // expo.out — varredura premium, desacelera no fim
        stagger,
        // garante estado final limpo (sem clip residual)
        onComplete: () => {
          list.forEach((el) => {
            (el as HTMLElement).style.clipPath = '';
          });
        },
      },
    );
  };

  // Já visível no load → dispara já (mesma lógica de count-up.ts)
  const rect = trigger.getBoundingClientRect();
  const alreadyVisible =
    rect.top < window.innerHeight * 0.85 && rect.bottom > 0;

  if (alreadyVisible) {
    run();
    return;
  }

  ScrollTrigger.create({
    trigger,
    start: 'top 85%',
    once: true,
    onEnter: run,
  });
}
