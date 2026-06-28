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

/** Mapa seção(id) → query. */
export const QUERIES: Record<string, QuerySpec> = {
  hero: {
    lang: 'sql',
    effect: 'type',
    code: [
      'SELECT *',
      'FROM engineers',
      "WHERE name = 'Otávio Ribeiro';",
    ],
    result: '1 row · 0.012s',
  },

  about: {
    lang: 'sql',
    effect: 'fetch',
    code: [
      'SELECT summary, focus, philosophy',
      'FROM profile',
      'LIMIT 1;',
    ],
    result: '1 row fetched · 0.008s',
  },

  impact: {
    lang: 'sql',
    effect: 'aggregate',
    code: [
      'SELECT',
      '  COUNT(DISTINCT year)   AS years,',
      '  COUNT(team_id)         AS teams,',
      '  SUM(data_processed_pb) AS petabytes',
      'FROM career;',
    ],
    /** Números rolam até estes alvos (mesma ordem dos COUNT/SUM acima). */
    counters: [12, 6, 480],
    result: 'aggregated · 0.021s',
  },

  timeline: {
    lang: 'sql',
    effect: 'plan',
    code: [
      'SELECT role, company, period',
      'FROM timeline',
      'ORDER BY start_date DESC;',
    ],
    result: 'query plan · seq scan on timeline',
  },

  skills: {
    lang: 'python',
    effect: 'stream',
    code: [
      'import pandas as pd',
      '',
      'skills = pd.read_parquet("skills.parquet")',
      'skills.sort_values("level", ascending=False)',
    ],
    result: '>>> 8 competencies loaded',
  },

  'tech-stack': {
    lang: 'python',
    effect: 'import',
    code: [
      'from pyspark.sql import SparkSession',
      '',
      'spark = SparkSession.builder.getOrCreate()',
      'spark.catalog.listTables()',
    ],
    result: 'packages loaded · 14 technologies',
  },

  projects: {
    lang: 'sql',
    effect: 'sort',
    code: [
      'SELECT name, language, stars',
      'FROM repositories',
      'ORDER BY stars DESC;',
    ],
    result: 'sorted · 0.014s',
  },

  stats: {
    lang: 'sql',
    effect: 'aggregate',
    code: [
      'SELECT lang, SUM(bytes) AS total',
      'FROM github.languages',
      'GROUP BY lang ORDER BY total DESC;',
    ],
    result: 'aggregated · 6 languages',
  },

  recommendations: {
    lang: 'sql',
    effect: 'scan',
    code: [
      'SELECT author, role, text',
      'FROM recommendations r',
      'JOIN people p ON p.id = r.author_id;',
    ],
    result: 'join scan complete · 6 rows',
  },

  blog: {
    lang: 'python',
    effect: 'paginate',
    code: [
      'import requests',
      '',
      'feed = requests.get("/api/articles?lang=pt")',
      'articles = feed.json()["items"]',
    ],
    result: 'feed loaded · 10 articles',
  },

  contact: {
    lang: 'sql',
    effect: 'insert',
    code: [
      'INSERT INTO opportunities (sender, intent)',
      "VALUES ('you', 'let''s talk');",
    ],
    result: '1 row affected · committed',
  },
};
