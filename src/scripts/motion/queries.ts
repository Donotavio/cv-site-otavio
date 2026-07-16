/**
 * queries.ts — Query Loader (Blueprint)
 *
 * Cada seção carrega como o resultado de uma query SQL ou Python sendo
 * digitada e executada — tematicamente coerente com Engenharia de Dados.
 * Cada seção tem sua própria query E seu próprio efeito de carregamento.
 *
 * effect: define a "personalidade" da execução (ver query-loader.ts):
 *   'type'      — typewriter char-by-char + cursor piscando
 *   'fetch'     — query instantânea + "N rows fetched" contando
 *   'plan'      — query plan / EXPLAIN revelando linha a linha
 *   'stream'    — Python print() com output incremental
 *   'aggregate' — COUNT/SUM com números rolando
 *   'import'    — import + spinner "loading packages"
 *   'sort'      — ORDER BY com linhas reordenando
 *   'scan'      — JOIN com cursor de scan varrendo
 *   'insert'    — INSERT com "1 row affected"
 */

export type QueryEffect =
  | 'type' | 'fetch' | 'plan' | 'stream'
  | 'aggregate' | 'import' | 'sort' | 'scan' | 'insert' | 'paginate';

export interface QuerySpec {
  lang: 'sql' | 'python';
  effect: QueryEffect;
  /** Linhas do código exibido (com indentação). */
  code: string[];
  /** Linha de status pós-execução (ex "8 rows in 0.04s"). */
  result: string;
  /** effect 'aggregate': alvos numéricos que "rolam" até o valor. */
  counters?: number[];
}

/**
 * Queries por PÁGINA — usadas pelo page-loader (transição de página).
 * Mesmo efeito de "código digitando" (type) em todas para coesão visual;
 * o conteúdo é temático de cada página. Chaveado por slug do pathname.
 * Fallback → 'home'.
 */
export const PAGE_QUERIES: Record<string, QuerySpec> = {
  home: {
    lang: 'sql',
    effect: 'type',
    code: [
      'SELECT *',
      'FROM engineers',
      "WHERE name = 'Otávio Ribeiro';",
    ],
    result: '1 row · 0.012s',
  },
  eleicoes: {
    lang: 'sql',
    effect: 'type',
    code: [
      'SELECT instituto, uf, contratante',
      'FROM tse.pesquisas_2026',
      'ORDER BY registro_dt DESC;',
    ],
    result: 'observatório carregado · TSE',
  },
  cockpit: {
    lang: 'sql',
    effect: 'type',
    code: [
      'SELECT kpi, valor, status',
      'FROM macro.cockpit_brasil',
      'WHERE vigente = TRUE;',
    ],
    result: 'cockpit carregado · BACEN · IBGE',
  },
  pix: {
    lang: 'sql',
    effect: 'type',
    code: [
      'SELECT mes, volume, valor',
      'FROM bacen.pix',
      'ORDER BY mes DESC;',
    ],
    result: 'observatório carregado · BACEN',
  },
  radar: {
    lang: 'python',
    effect: 'type',
    code: [
      'import radar',
      '',
      'radar.load("data_stack_radar_br")',
    ],
    result: 'radar carregado · stack BR',
  },
};
