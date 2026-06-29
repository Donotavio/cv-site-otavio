/**
 * query-loader.ts — Query Loader (Blueprint)
 *
 * Mostra um overlay de "terminal SQL/Python" sobre uma seção: digita a query,
 * executa (efeito ÚNICO por seção) e revela o conteúdo real como resultado.
 *
 * Disparado por:
 *  - clique no menu (navegação para a seção) → fireQueryLoader(id)
 *  - primeira vez que a seção entra no viewport via scroll → ScrollTrigger
 *
 * Roda em TODO carregamento solicitado: a cada clique no menu (force) e
 * toda vez que a seção (re)entra no viewport (com cooldown anti-spam).
 * Um guard `running` impede sobreposição na mesma seção.
 *
 * Os 9 effects (um por seção) são visualmente DISTINTOS:
 *   type      (hero)            — typewriter char-by-char + cursor piscando
 *   fetch     (about)           — query instantânea + "fetching… N rows"
 *   aggregate (impact)          — números do COUNT/SUM rolando até o alvo
 *   plan      (timeline)        — query plan tipo EXPLAIN, indentação crescente
 *   stream    (skills)          — stdout Python streaming linha a linha
 *   import    (tech-stack)      — "loading packages" + barra ASCII de progresso
 *   sort      (projects)        — linhas embaralham → reordenam (shuffle→sorted)
 *   scan      (recommendations) — cursor de scan varrendo linha a linha
 *   insert    (contact)         — "1 row affected" + commit
 *
 * Feel premium calmo: easing expo.out, durações ~1.2–2s no total.
 *
 * Acessibilidade: o overlay é decorativo (aria-hidden). O conteúdo real
 * permanece no DOM e legível; sem JS / reduced-motion → overlay nunca aparece.
 * Só transform/opacity nos tweens GSAP. Cursor piscando via CSS animation.
 */

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { QUERIES, type QuerySpec } from './queries';
import { motionOk, EASINGS } from './constants';

gsap.registerPlugin(ScrollTrigger);

// Guard por seção: evita dois loaders sobrepostos na MESMA seção.
const running = new Set<string>();
// Seções já vistas por scroll: o loader por scroll roda só na 1ª vez.
const seenByScroll = new Set<string>();
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Token de syntax highlight simples para SQL/Python. */
function highlight(line: string, lang: 'sql' | 'python'): string {
  const esc = line
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  const sqlKw =
    /\b(SELECT|FROM|WHERE|ORDER BY|GROUP BY|LIMIT|JOIN|ON|INSERT INTO|VALUES|COUNT|SUM|DISTINCT|AS|DESC|ASC)\b/g;
  const pyKw = /\b(import|from|as|def|return|True|False|None|for|in|print)\b/g;
  const str = /(&#39;[^&]*&#39;|'[^']*')/g;
  const num = /\b(\d+(?:\.\d+)?)\b/g;

  let out = esc.replace(str, '<span class="ql-str">$1</span>');
  out = out.replace(num, '<span class="ql-num">$1</span>');
  out = out.replace(lang === 'sql' ? sqlKw : pyKw, '<span class="ql-kw">$&</span>');
  return out;
}

interface Overlay {
  root: HTMLElement;
  pre: HTMLElement;
  status: HTMLElement;
}

function buildOverlay(_section: HTMLElement, spec: QuerySpec): Overlay {
  const root = document.createElement('div');
  root.className = 'ql-overlay';
  root.setAttribute('aria-hidden', 'true');

  root.innerHTML = `
    <div class="ql-terminal">
      <div class="ql-bar">
        <span class="ql-dot"></span>
        <span class="ql-tab">${spec.lang === 'sql' ? 'query.sql' : 'query.py'}</span>
      </div>
      <pre class="ql-code"></pre>
      <div class="ql-status"></div>
    </div>`;

  // Anexa no <body>, não na seção: o overlay é position:fixed e deve centrar
  // na viewport. Dentro da seção, um transform (parallax/reveal) tornaria o
  // fixed relativo à seção, quebrando a centralização.
  document.body.appendChild(root);
  return {
    root,
    pre: root.querySelector('.ql-code') as HTMLElement,
    status: root.querySelector('.ql-status') as HTMLElement,
  };
}

const CURSOR = '<span class="ql-cursor">█</span>';

/** Render helper — junta linhas já tokenizadas. */
function renderLines(pre: HTMLElement, lines: string[], lang: 'sql' | 'python') {
  pre.innerHTML = lines.map((l) => highlight(l, lang)).join('\n');
}

/* ────────────────────────────────────────────────────────────────────────
 * Os 9 efeitos de digitação/execução do CÓDIGO (a fase de "escrever a query")
 * ──────────────────────────────────────────────────────────────────────── */

/** type / insert: typewriter char-by-char com cursor seguindo. */
async function effectType(pre: HTMLElement, spec: QuerySpec, charMs: number) {
  const lines = spec.code;
  const done: string[] = [];
  for (const line of lines) {
    for (let c = 0; c <= line.length; c++) {
      const head = highlight(line.slice(0, c), spec.lang) + CURSOR;
      pre.innerHTML = [...done.map((l) => highlight(l, spec.lang)), head].join('\n');
      // espaços fluem mais rápido → ritmo natural
      await sleep(line[c - 1] === ' ' ? charMs * 0.5 : charMs);
    }
    done.push(line);
  }
  renderLines(pre, done, spec.lang);
}

/** plan: linhas surgem com indentação crescente (estilo EXPLAIN). */
async function effectPlan(pre: HTMLElement, spec: QuerySpec) {
  renderLines(pre, spec.code, spec.lang);
  await sleep(120);
  // depois do SQL, revela um mini "query plan" indentado linha a linha
  const plan = [
    '',
    '-- QUERY PLAN',
    '→ Sort  (start_date DESC)',
    '  → Seq Scan on timeline',
    '    rows=∞  loops=1',
  ];
  const acc = [...spec.code];
  for (const p of plan) {
    acc.push(p);
    pre.innerHTML = acc
      .map((l, i) =>
        i < spec.code.length
          ? highlight(l, spec.lang)
          : `<span class="ql-dim">${l.replace(/</g, '&lt;')}</span>`,
      )
      .join('\n');
    await sleep(160);
  }
}

/** stream: stdout Python — linhas surgem com prompt >>> e leve "digitação". */
async function effectStream(pre: HTMLElement, spec: QuerySpec) {
  const acc: string[] = [];
  for (const line of spec.code) {
    acc.push(line);
    renderLines(pre, acc, spec.lang);
    pre.innerHTML += '\n' + CURSOR;
    await sleep(line === '' ? 90 : 170);
  }
  renderLines(pre, acc, spec.lang);
  await sleep(120);
  // saída de stdout streaming
  const out = [
    '',
    '>>> running pipeline…',
    '>>> [warehouse] 8 competencies',
    '>>> done',
  ];
  for (const o of out) {
    pre.innerHTML =
      acc.map((l) => highlight(l, spec.lang)).join('\n') +
      '\n' +
      `<span class="ql-dim">${o}</span>`;
    acc.push(o);
    await sleep(150);
  }
}

/** import: imports surgem + spinner "loading packages" + barra ASCII. */
async function effectImport(pre: HTMLElement, spec: QuerySpec, status: HTMLElement) {
  const acc: string[] = [];
  for (const line of spec.code) {
    acc.push(line);
    renderLines(pre, acc, spec.lang);
    await sleep(line === '' ? 60 : 130);
  }
  // barra de progresso ASCII no status, com spinner
  const spin = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
  const steps = 16;
  for (let i = 0; i <= steps; i++) {
    const filled = '█'.repeat(i);
    const empty = '·'.repeat(steps - i);
    const pct = Math.round((i / steps) * 100);
    const s = spin[i % spin.length];
    status.innerHTML =
      `<span class="ql-run">${s} loading packages</span>` +
      `<span class="ql-bar-ascii">[${filled}${empty}] ${pct}%</span>`;
    await sleep(55);
  }
}

/** sort: linhas embaralham algumas vezes e depois "assentam" ordenadas. */
async function effectSort(pre: HTMLElement, spec: QuerySpec) {
  renderLines(pre, spec.code, spec.lang);
  await sleep(140);
  // dataset fake de repositórios para "ordenar" visualmente
  const rows = [
    'kafka-bridge      | scala  | ★ 128',
    'spark-lineage     | python | ★ 342',
    'dbt-observability | sql    | ★  87',
    'airflow-operators | python | ★ 201',
  ];
  const sorted = [...rows].sort((a, b) => {
    const sa = parseInt(a.split('★')[1]);
    const sb = parseInt(b.split('★')[1]);
    return sb - sa;
  });
  const base = spec.code.map((l) => highlight(l, spec.lang)).join('\n');
  // 3 frames de shuffle
  for (let f = 0; f < 3; f++) {
    const shuffled = [...rows].sort(() => Math.random() - 0.5);
    pre.innerHTML =
      base +
      '\n\n' +
      shuffled.map((r) => `<span class="ql-dim">${r}</span>`).join('\n');
    await sleep(130);
  }
  // frame final ordenado, com destaque de "settle"
  pre.innerHTML =
    base +
    '\n\n' +
    sorted.map((r) => `<span class="ql-sorted">${r}</span>`).join('\n');
  await sleep(220);
}

/** scan: cursor de scan varre cada linha, destacando-a ao passar. */
async function effectScan(pre: HTMLElement, spec: QuerySpec) {
  renderLines(pre, spec.code, spec.lang);
  await sleep(120);
  const rows = spec.code;
  // passa um "scan" linha a linha — a linha ativa fica realçada
  for (let i = 0; i < rows.length; i++) {
    pre.innerHTML = rows
      .map((l, idx) => {
        const h = highlight(l, spec.lang);
        return idx === i ? `<span class="ql-scan">${h}</span>` : h;
      })
      .join('\n');
    await sleep(180);
  }
  renderLines(pre, rows, spec.lang);
}

/** paginate: feed de artigos carregando lote a lote, como uma API paginada. */
async function effectPaginate(pre: HTMLElement, spec: QuerySpec, status: HTMLElement) {
  const acc: string[] = [];
  for (const line of spec.code) {
    acc.push(line);
    renderLines(pre, acc, spec.lang);
    await sleep(line === '' ? 50 : 120);
  }
  const base = spec.code.map((l) => highlight(l, spec.lang)).join('\n');
  // títulos curtos simulando o feed chegando
  const titles = [
    'every good prompt is a syllogism',
    'building lakehouse governance at scale',
    'delta live tables in production',
    'the cost of bad data contracts',
  ];
  const shown: string[] = [];
  for (let i = 0; i < titles.length; i++) {
    shown.push(`  ↳ "${titles[i]}"`);
    pre.innerHTML = base + '\n\n' +
      shown.map((t) => `<span class="ql-dim">${t}</span>`).join('\n');
    status.innerHTML =
      `<span class="ql-run">▸ paginando feed</span>` +
      `<span class="ql-bar-ascii">page ${i + 1}/4 · ${(i + 1) * 3} items</span>`;
    await sleep(150);
  }
  await sleep(120);
}

/** fetch: query surge instantânea; status faz "fetching… N rows" contando. */
async function effectFetch(pre: HTMLElement, spec: QuerySpec, status: HTMLElement) {
  renderLines(pre, spec.code, spec.lang);
  await sleep(160);
  const target = 1; // about retorna 1 row
  status.innerHTML = `<span class="ql-run">▸ fetching…</span>`;
  await sleep(200);
  // "rows fetched" sobe rápido (mesmo que alvo seja pequeno, dá sensação de IO)
  for (let n = 0; n <= 24; n++) {
    const shown = Math.min(n, target + 23);
    status.innerHTML =
      `<span class="ql-run">▸ fetching…</span>` +
      `<span class="ql-bar-ascii">${shown} rows</span>`;
    await sleep(26);
  }
}

/** aggregate: números do COUNT/SUM "rolando" até o valor final. */
async function effectAggregate(pre: HTMLElement, spec: QuerySpec, status: HTMLElement) {
  const targets = spec.counters ?? [0];
  const labels = ['years', 'teams', 'PB'];
  // proxy animável compartilhado: 0 → 1 (progresso), aplicado a todos os alvos
  const prog = { t: 0 };

  renderLines(pre, spec.code, spec.lang);
  await sleep(140);

  const paint = () => {
    const parts = targets
      .map((target, i) => {
        const v = Math.round(target * prog.t);
        return `${v.toLocaleString('en-US')} ${labels[i] ?? ''}`.trim();
      })
      .join('  ·  ');
    status.innerHTML =
      `<span class="ql-run">▸ aggregating…</span>` +
      `<span class="ql-bar-ascii ql-roll">${parts}</span>`;
  };

  // tween calmo dos contadores (expo.out)
  await new Promise<void>((resolve) => {
    gsap.to(prog, {
      t: 1,
      duration: 1.0,
      ease: EASINGS.out,
      onUpdate: paint,
      onComplete: resolve,
    });
  });
}

/* ────────────────────────────────────────────────────────────────────────
 * Orquestração
 * ──────────────────────────────────────────────────────────────────────── */

/** Executa a sequência completa de loader para uma seção. */
async function run(section: HTMLElement, spec: QuerySpec) {
  const { root, pre, status } = buildOverlay(section, spec);

  // fade-in do overlay (opacity only)
  await gsap.to(root, { opacity: 1, duration: 0.22, ease: EASINGS.out });

  // ── fase de execução: cada effect é único ──
  switch (spec.effect) {
    case 'type':
      await effectType(pre, spec, 24);
      break;
    case 'insert':
      await effectType(pre, spec, 26);
      break;
    case 'plan':
      await effectPlan(pre, spec);
      break;
    case 'stream':
      await effectStream(pre, spec);
      break;
    case 'import':
      await effectImport(pre, spec, status);
      break;
    case 'sort':
      await effectSort(pre, spec);
      break;
    case 'scan':
      await effectScan(pre, spec);
      break;
    case 'fetch':
      await effectFetch(pre, spec, status);
      break;
    case 'aggregate':
      await effectAggregate(pre, spec, status);
      break;
    case 'paginate':
      await effectPaginate(pre, spec, status);
      break;
    default:
      await effectType(pre, spec, 24);
  }

  // ── estado "executando" → só p/ efeitos que não montaram status próprio ──
  const ownsStatus =
    spec.effect === 'import' ||
    spec.effect === 'fetch' ||
    spec.effect === 'aggregate' ||
    spec.effect === 'paginate';
  if (!ownsStatus) {
    status.innerHTML = `<span class="ql-run">▸ executando</span>${CURSOR}`;
    await sleep(320);
  }

  // ── resultado final ──
  status.innerHTML = `<span class="ql-ok">✓</span> ${spec.result}`;
  await sleep(spec.effect === 'insert' ? 320 : 240);

  // ── revela a seção: overlay sai (opacity), conteúdo entra ──
  await gsap.to(root, {
    opacity: 0,
    duration: 0.45,
    ease: EASINGS.inOut,
    onComplete: () => root.remove(),
  });
}

/**
 * Registra o query loader numa seção.
 *  - Scroll: dispara SÓ na primeira vez que a seção entra no viewport.
 *  - Menu (fireQueryLoader): dispara SEMPRE (force).
 * Um guard `running` impede sobrepor dois loaders na mesma seção.
 */
export function registerQueryLoader(section: HTMLElement) {
  if (!motionOk) return; // reduced-motion / SSR → sem overlay, conteúdo direto
  const id = section.id;
  const spec = QUERIES[id];
  if (!spec) return;
  // overlay é position:fixed (centra na viewport) — não precisa ancorar a seção

  const fire = async (opts?: { force?: boolean }) => {
    if (running.has(id)) return;     // já tem um loader rodando nesta seção
    // Scroll dispara SÓ na primeira vez que a seção aparece (não a cada scroll —
    // ficava cansativo). Menu (force:true) dispara sempre.
    if (!opts?.force) {
      if (seenByScroll.has(id)) return;
      seenByScroll.add(id);
    }
    running.add(id);
    try {
      await run(section, spec);
    } finally {
      running.delete(id);
    }
  };

  // Scroll: dispara apenas na primeira entrada (once). Subir de volta não
  // re-dispara — o guard seenByScroll garante "só primeiro carregamento".
  ScrollTrigger.create({
    trigger: section,
    start: 'top 70%',
    once: true,
    onEnter: () => fire(),
  });

  // expõe trigger manual para navegação por menu (force: ignora cooldown)
  (section as HTMLElement & { __qlFire?: (o?: { force?: boolean }) => void })
    .__qlFire = fire;
}

/** Dispara o loader de uma seção imediatamente (navegação por menu).
 *  force: true → ignora o cooldown (clique sempre roda). */
export function fireQueryLoader(id: string) {
  const section = document.getElementById(id) as
    | (HTMLElement & { __qlFire?: (o?: { force?: boolean }) => void })
    | null;
  section?.__qlFire?.({ force: true });
}
