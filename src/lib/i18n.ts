/**
 * i18n build-time helper — Blueprint
 *
 * Carrega o pt-BR.json (fonte de verdade) em tempo de build para que os
 * componentes Astro renderizem o texto default DIRETO no HTML.
 *
 * Por quê: o i18n.js runtime preenche [data-i18n-key] via JS após o load.
 * Se o HTML nasce vazio, o layout salta quando o texto entra (CLS alto) e
 * o conteúdo não existe sem JS. Renderizar o pt-BR no build resolve ambos:
 * - CLS ~0 (texto já ocupa o espaço final)
 * - Conteúdo legível sem JS (fallback content-i18n.md)
 * - SEO (crawler vê o conteúdo real)
 *
 * O i18n.js continua sobrescrevendo o textContent ao trocar de idioma.
 */
import ptBR from '../../assets/i18n/pt-BR.json';

type Dict = Record<string, unknown>;

/** Resolve uma chave aninhada tipo "hero.role" no dicionário pt-BR. */
export function t(key: string): string {
  const value = key.split('.').reduce<unknown>(
    (acc, part) => (acc && typeof acc === 'object' ? (acc as Dict)[part] : undefined),
    ptBR as Dict,
  );
  return typeof value === 'string' ? value : '';
}

export const dict = ptBR as Dict;
