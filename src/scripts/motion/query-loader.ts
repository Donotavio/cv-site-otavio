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
 *
 * Robustez:
 * - gsap.context() por execução → ctx.revert() mata tweens/ScrollTriggers.
 * - Token de cancelamento: cadeias async param de escrever no DOM removido.
 * - finally GARANTE remoção do overlay (mesmo em throw/cancelamento).
 * - Timings centralizados em constants.ts (LOADER), sem números ad-hoc.
 * - Null-checks em todo querySelector do overlay.
 * - queryLoaderDone é seguido de ScrollTrigger.refresh() debounced (conteúdo
 *   dinâmico injetado depois pelo consumidor pode mudar alturas).
 */

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { QUERIES, type QuerySpec } from './queries';
import { motionOk, EASINGS, LOADER } from './constants';
import { registerCleaner } from './cleanup';

gsap.registerPlugin(ScrollTrigger);

// Guard por seção: evita dois loaders sobrepostos na MESMA seção.
const running = new Set<string>();
// Seções já vistas por scroll: o loader por scroll roda só na 1ª vez.
const seenByScroll = new Set<string>();

interface CancelToken { cancelled: boolean }
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Token de cancelamento: sleep que resolve, mas permite checagem pós-await. */
function makeToken(): CancelToken {
  return { cancelled: false };
}
/** Cancela o token e retorna true se estava ativo (para early-return). */
function cancel(token: CancelToken): boolean {
  if (token.cancelled) return false;
  token.cancelled = true;
  return true;
}

/** Token de cancelamento shared por seção (acessível ao teardown). */
const sectionTokens = new Map<string, CancelToken>();

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

function buildOverlay(spec: QuerySpec): Overlay | null {
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

  const pre = root.querySelector<HTMLElement>('.ql-code');
  const status = root.querySelector<HTMLElement>('.ql-status');
  // Null-guard: se o markup interno mudar, aborta limpo (sem throw solto).
  if (!pre || !status) {
    root.remove();
    return null;
  }
  return { root, pre, status };
}

const CURSOR = '<span class="ql-cursor">█</span>';

/** Render helper — junta linhas já tokenizadas. */
function renderLines(pre: HTMLElement, lines: string[], lang: 'sql' | 'python') {
  pre.innerHTML = lines.map((l) => highlight(l, lang)).join('\n');
}

/* ────────────────────────────────────────────────────────────────────────
 * Os 9 efeitos de digitação/execução do CÓDIGO (a fase de "escrever a query")
 * Todos recebem o token para bail-out entre iterações longas.
 * ──────────────────────────────────────────────────────────────────────── */

/** type / insert: typewriter char-by-char com cursor seguindo. */
async function effectType(pre: HTMLElement, spec: QuerySpec, charMs: number, token: CancelToken) {
  const lines = spec.code;
  const done: string[] = [];
  for (const line of lines) {
    for (let c = 0; c <= line.length; c++) {
      if (token.cancelled) return;
      const head = highlight(line.slice(0, c), spec.lang) + CURSOR;
      pre.innerHTML = [...done.map((l) => highlight(l, spec.lang)), head].join('\n');
      // espaços fluem mais rápido → ritmo natural
      await sleep(line[c - 1] === ' ' ? charMs * LOADER.spaceFactor : charMs);
    }
    done.push(line);
  }
  renderLines(pre, done, spec.lang);
}

/** plan: linhas surgem com indentação crescente (estilo EXPLAIN). */
async function effectPlan(pre: HTMLElement, spec: QuerySpec, token: CancelToken) {
  renderLines(pre, spec.code, spec.lang);
  await sleep(LOADER.preEffectPlanMs);
  if (token.cancelled) return;
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
    if (token.cancelled) return;
    acc.push(p);
    pre.innerHTML = acc
      .map((l, i) =>
        i < spec.code.length
          ? highlight(l, spec.lang)
          : `<span class="ql-dim">${l.replace(/</g, '&lt;')}</span>`,
      )
      .join('\n');
    await sleep(LOADER.planMs);
  }
}

/** stream: stdout Python — linhas surgem com prompt >>> e leve "digitação". */
async function effectStream(pre: HTMLElement, spec: QuerySpec, token: CancelToken) {
  const acc: string[] = [];
  for (const line of spec.code) {
    if (token.cancelled) return;
    acc.push(line);
    renderLines(pre, acc, spec.lang);
    pre.innerHTML += '\n' + CURSOR;
    await sleep(line === '' ? LOADER.lineMsBlankStream : LOADER.lineMsStream);
  }
  renderLines(pre, acc, spec.lang);
  await sleep(LOADER.preEffectMs);
  if (token.cancelled) return;
  // saída de stdout streaming
  const out = [
    '',
    '>>> running pipeline…',
    '>>> [warehouse] 8 competencies',
    '>>> done',
  ];
  for (const o of out) {
    if (token.cancelled) return;
    pre.innerHTML =
      acc.map((l) => highlight(l, spec.lang)).join('\n') +
      '\n' +
      `<span class="ql-dim">${o}</span>`;
    acc.push(o);
    await sleep(LOADER.lineMsStream);
  }
}

/** import: imports surgem + spinner "loading packages" + barra ASCII. */
async function effectImport(pre: HTMLElement, spec: QuerySpec, status: HTMLElement, token: CancelToken) {
  const acc: string[] = [];
  for (const line of spec.code) {
    if (token.cancelled) return;
    acc.push(line);
    renderLines(pre, acc, spec.lang);
    await sleep(line === '' ? LOADER.lineMsBlank : LOADER.lineMs);
  }
  // barra de progresso ASCII no status, com spinner
  const spin = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
  const steps = 16;
  for (let i = 0; i <= steps; i++) {
    if (token.cancelled) return;
    const filled = '█'.repeat(i);
    const empty = '·'.repeat(steps - i);
    const pct = Math.round((i / steps) * 100);
    const s = spin[i % spin.length];
    status.innerHTML =
      `<span class="ql-run">${s} loading packages</span>` +
      `<span class="ql-bar-ascii">[${filled}${empty}] ${pct}%</span>`;
    await sleep(LOADER.progressMs);
  }
}

/** sort: linhas embaralham algumas vezes e depois "assentam" ordenadas. */
async function effectSort(pre: HTMLElement, spec: QuerySpec, token: CancelToken) {
  renderLines(pre, spec.code, spec.lang);
  await sleep(LOADER.preEffectMs);
  if (token.cancelled) return;
  // dataset fake de repositórios para "ordenar" visualmente
  const rows = [
    'kafka-bridge      | scala  | ★ 128',
    'spark-lineage     | python | ★ 342',
    'dbt-observability | sql    | ★  87',
    'airflow-operators | python | ★ 201',
  ];
  const sorted = [...rows].sort((a, b) => {
    // parseInt(undefined) → NaN; `?? 0` previne comparator NaN (sort instável)
    // caso o separador '★' mude no futuro.
    const sa = parseInt(a.split('★')[1] ?? '0', 10) || 0;
    const sb = parseInt(b.split('★')[1] ?? '0', 10) || 0;
    return sb - sa;
  });
  const base = spec.code.map((l) => highlight(l, spec.lang)).join('\n');
  // 3 frames de shuffle
  for (let f = 0; f < 3; f++) {
    if (token.cancelled) return;
    const shuffled = [...rows].sort(() => Math.random() - 0.5);
    pre.innerHTML =
      base +
      '\n\n' +
      shuffled.map((r) => `<span class="ql-dim">${r}</span>`).join('\n');
    await sleep(LOADER.sortFrameMs);
  }
  if (token.cancelled) return;
  // frame final ordenado, com destaque de "settle"
  pre.innerHTML =
    base +
    '\n\n' +
    sorted.map((r) => `<span class="ql-sorted">${r}</span>`).join('\n');
  await sleep(LOADER.sortSettleMs);
}

/** scan: cursor de scan varre cada linha, destacando-a ao passar. */
async function effectScan(pre: HTMLElement, spec: QuerySpec, token: CancelToken) {
  renderLines(pre, spec.code, spec.lang);
  await sleep(LOADER.preEffectMs);
  if (token.cancelled) return;
  const rows = spec.code;
  // passa um "scan" linha a linha — a linha ativa fica realçada
  for (let i = 0; i < rows.length; i++) {
    if (token.cancelled) return;
    pre.innerHTML = rows
      .map((l, idx) => {
        const h = highlight(l, spec.lang);
        return idx === i ? `<span class="ql-scan">${h}</span>` : h;
      })
      .join('\n');
    await sleep(LOADER.scanMs);
  }
  renderLines(pre, rows, spec.lang);
}

/** paginate: feed de artigos carregando lote a lote, como uma API paginada. */
async function effectPaginate(pre: HTMLElement, spec: QuerySpec, status: HTMLElement, token: CancelToken) {
  const acc: string[] = [];
  for (const line of spec.code) {
    if (token.cancelled) return;
    acc.push(line);
    renderLines(pre, acc, spec.lang);
    await sleep(line === '' ? LOADER.lineMsBlank : LOADER.lineMs);
  }
  if (token.cancelled) return;
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
    if (token.cancelled) return;
    shown.push(`  ↳ "${titles[i]}"`);
    pre.innerHTML = base + '\n\n' +
      shown.map((t) => `<span class="ql-dim">${t}</span>`).join('\n');
    status.innerHTML =
      `<span class="ql-run">▸ paginando feed</span>` +
      `<span class="ql-bar-ascii">page ${i + 1}/4 · ${(i + 1) * 3} items</span>`;
    await sleep(LOADER.paginateMs);
  }
  await sleep(LOADER.preEffectMs);
}

/** fetch: query surge instantânea; status faz "fetching… N rows" contando. */
async function effectFetch(pre: HTMLElement, spec: QuerySpec, status: HTMLElement, token: CancelToken) {
  renderLines(pre, spec.code, spec.lang);
  await sleep(LOADER.preEffectMs);
  if (token.cancelled) return;
  const target = 1; // about retorna 1 row
  status.innerHTML = `<span class="ql-run">▸ fetching…</span>`;
  await sleep(LOADER.fetchHoldMs);
  if (token.cancelled) return;
  // "rows fetched" sobe rápido (mesmo que alvo seja pequeno, dá sensação de IO)
  for (let n = 0; n <= 24; n++) {
    if (token.cancelled) return;
    const shown = Math.min(n, target + 23);
    status.innerHTML =
      `<span class="ql-run">▸ fetching…</span>` +
      `<span class="ql-bar-ascii">${shown} rows</span>`;
    await sleep(LOADER.fetchTickMs);
  }
}

/** aggregate: números do COUNT/SUM "rolando" até o valor final. */
async function effectAggregate(pre: HTMLElement, spec: QuerySpec, status: HTMLElement, token: CancelToken, ctx: gsap.Context) {
  const targets = spec.counters ?? [0];
  const labels = ['years', 'teams', 'PB'];
  // proxy animável compartilhado: 0 → 1 (progresso), aplicado a todos os alvos
  const prog = { t: 0 };

  renderLines(pre, spec.code, spec.lang);
  await sleep(LOADER.preEffectMs);
  if (token.cancelled) return;

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

  // tween calmo dos contadores (expo.out). Criado dentro do contexto GSAP
  // para ctx.revert() matá-lo no teardown. NÃO usamos onComplete para resolver
  // (o tween pode ser morto antes, hangando o await); em vez disso, dormimos
  // pela duração e checamos cancelamento — à prova de hang.
  ctx.add(() =>
    gsap.to(prog, {
      t: 1,
      duration: LOADER.aggregateDur,
      ease: EASINGS.out,
      onUpdate: paint,
    }),
  );
  await sleep(LOADER.aggregateDur * 1000);
}

/* ────────────────────────────────────────────────────────────────────────
 * Orquestração
 * ──────────────────────────────────────────────────────────────────────── */

/** Executa a sequência completa de loader para uma seção. */
async function run(section: HTMLElement, spec: QuerySpec) {
  const token = makeToken();
  sectionTokens.set(section.id, token);

  const overlay = buildOverlay(spec);
  // buildOverlay retorna null só em falha de markup — remove token e sai.
  if (!overlay) {
    sectionTokens.delete(section.id);
    return;
  }
  const { root, pre, status } = overlay;

  // Contexto GSAP: rastreia os tweens de fade e o tween do aggregate para
  // ctx.revert() no teardown (cancelamento instantâneo). Contexto vazio no
  // init — tweens são adicionados via ctx.add() ao longo da execução.
  const ctx = gsap.context(() => {});

  try {
    // fade-in do overlay (opacity only). Disparamos o tween e dormimos pela
    // duração — NÃO usamos onComplete (se o tween for morto no teardown antes
    // do complete, o await hangaria). Cancelamento é checado após o sleep.
    ctx.add(() =>
      gsap.to(root, { opacity: 1, duration: LOADER.fadeIn, ease: EASINGS.out }),
    );
    await sleep(LOADER.fadeIn * 1000);
    if (token.cancelled) return;

    // ── fase de execução: cada effect é único ──
    switch (spec.effect) {
      case 'type':
        await effectType(pre, spec, LOADER.charMs, token);
        break;
      case 'insert':
        await effectType(pre, spec, LOADER.charMsInsert, token);
        break;
      case 'plan':
        await effectPlan(pre, spec, token);
        break;
      case 'stream':
        await effectStream(pre, spec, token);
        break;
      case 'import':
        await effectImport(pre, spec, status, token);
        break;
      case 'sort':
        await effectSort(pre, spec, token);
        break;
      case 'scan':
        await effectScan(pre, spec, token);
        break;
      case 'fetch':
        await effectFetch(pre, spec, status, token);
        break;
      case 'aggregate':
        await effectAggregate(pre, spec, status, token, ctx);
        break;
      case 'paginate':
        await effectPaginate(pre, spec, status, token);
        break;
      default:
        await effectType(pre, spec, LOADER.charMs, token);
    }
    if (token.cancelled) return;

    // ── estado "executando" → só p/ efeitos que não montaram status próprio ──
    const ownsStatus =
      spec.effect === 'import' ||
      spec.effect === 'fetch' ||
      spec.effect === 'aggregate' ||
      spec.effect === 'paginate';
    if (!ownsStatus) {
      status.innerHTML = `<span class="ql-run">▸ executando</span>${CURSOR}`;
      await sleep(LOADER.runMs);
    }
    if (token.cancelled) return;

    // ── resultado final ──
    status.innerHTML = `<span class="ql-ok">✓</span> ${spec.result}`;
    await sleep(spec.effect === 'insert' ? LOADER.resultMsInsert : LOADER.resultMs);
    if (token.cancelled) return;

    // ── revela a seção: overlay sai (opacity), conteúdo entra ──
    ctx.add(() =>
      gsap.to(root, {
        opacity: 0,
        duration: LOADER.fadeOut,
        ease: EASINGS.inOut,
        onComplete: () => { if (root.parentNode) root.remove(); },
      }),
    );
    await sleep(LOADER.fadeOut * 1000);
  } finally {
    // Garantia: overlay sempre removido e tweens mortos, mesmo em
    // throw/cancelamento. Idempotente (parentNode check + ctx.revert safe).
    ctx.revert();
    if (root.parentNode) root.remove();
    sectionTokens.delete(section.id);
  }

  if (token.cancelled) return;

  // Sinaliza que o loader terminou de revelar esta seção. Seções com motion
  // de conteúdo (ex.: GitHubStats count-up / heatmap) devem disparar SUA
  // animação aqui — caso contrário o motion roda escondido sob o overlay e o
  // usuário nunca o vê ("seção sem animação").
  window.dispatchEvent(
    new CustomEvent('queryLoaderDone', { detail: { id: section.id } }),
  );

  // Conteúdo dinâmico injetado depois do reveal (count-ups, heatmaps, barras)
  // pode mudar a altura da página e desincronizar ScrollTriggers. Refresh
  // debounced: se várias seções revelarem em sequência, roda uma vez só.
  scheduleScrollRefresh();
}

/** Debounce simples para ScrollTrigger.refresh() após reveals. */
let refreshTimer = 0;
function scheduleScrollRefresh() {
  window.clearTimeout(refreshTimer);
  refreshTimer = window.setTimeout(() => {
    try { ScrollTrigger.refresh(); } catch { /* noop */ }
  }, LOADER.refreshMs);
}

/**
 * Registra o query loader numa seção.
 *  - Scroll: dispara SÓ na primeira vez que a seção entra no viewport.
 *  - Menu (fireQueryLoader): dispara SEMPRE (force).
 * Um guard `running` impede sobrepor dois loaders na mesma seção.
 * Idempotente: se já registrado (re-init / troca de idioma), no-op.
 */
export function registerQueryLoader(section: HTMLElement): void {
  if (!motionOk) return; // reduced-motion / SSR → sem overlay, conteúdo direto
  const id = section.id;
  const spec = QUERIES[id];
  if (!spec) return;
  // Idempotência: não re-registra ScrollTrigger nem __qlFire em re-init.
  const flagged = section as HTMLElement & { __qlRegistered?: boolean };
  if (flagged.__qlRegistered) return;
  flagged.__qlRegistered = true;

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

  // Teardown: cancela um loader em curso (para de escrever no overlay) e mata
  // o ScrollTrigger de entrada. O overlay em si é removido pelo finally do run.
  registerCleaner(() => {
    const token = sectionTokens.get(id);
    if (token) cancel(token);
    ScrollTrigger.getAll()
      .filter((st) => st.trigger === section && st.vars.once)
      .forEach((st) => st.kill());
  });
}

/** Dispara o loader de uma seção imediatamente (navegação por menu).
 *  force: true → ignora o cooldown (clique sempre roda). */
export function fireQueryLoader(id: string): void {
  const section = document.getElementById(id) as
    | (HTMLElement & { __qlFire?: (o?: { force?: boolean }) => void })
    | null;
  section?.__qlFire?.({ force: true });
}
