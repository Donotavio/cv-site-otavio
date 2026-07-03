const STATS_KEY = 'or:stats';
const SESSION_KEY = 'or:stats:session';
const GLOBAL_COUNTED_KEY = 'or:stats:session:global';
const API_BASE = 'https://abacus.jasoncameron.dev';
const NAMESPACE = 'otavio-ribeiro-cv-site';
const GLOBAL_KEY = 'visits';

// Deadline máxima para cada chamada à API. Evita que as células fiquem
// "presas em 0" indefinidamente se o abacus estiver lento/indisponível;
// ao estourar, cai suavemente no valor em cache (localStorage).
const API_DEADLINE_MS = 2500;

interface Stats {
  clicks: number;
  global: number;
  page: number;
}

function toInt(v: unknown): number {
  const n = parseInt(typeof v === 'string' ? v : String(v ?? ''), 10);
  return Number.isFinite(n) ? Math.max(0, n) : 0;
}

function read(): Stats {
  try {
    const raw = localStorage.getItem(STATS_KEY);
    if (!raw) return { clicks: 0, global: 0, page: 0 };
    const p = JSON.parse(raw) as Partial<Stats>;
    return { clicks: toInt(p.clicks), global: toInt(p.global), page: toInt(p.page) };
  } catch {
    return { clicks: 0, global: 0, page: 0 };
  }
}

function write(s: Stats): void {
  try {
    localStorage.setItem(STATS_KEY, JSON.stringify(s));
  } catch {
    /* swallow (modo privado / quota) */
  }
}

function currentPath(): string {
  return location.pathname.replace(/\/+$/, '') || '/';
}

function pageKey(): string {
  const slug = currentPath()
    .replace(/^\/+|\/+$/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return `page-${slug || 'home'}`.slice(0, 60);
}

let cache: Stats | null = null;

function get(): Stats {
  if (!cache) cache = read();
  return cache;
}

let writeScheduled = false;

function scheduleWrite(): void {
  if (writeScheduled) return;
  writeScheduled = true;
  const run = () => {
    writeScheduled = false;
    write(get());
  };
  const w = window as unknown as {
    requestIdleCallback?: (cb: () => void, opts: { timeout: number }) => void;
  };
  if ('requestIdleCallback' in window && typeof w.requestIdleCallback === 'function') {
    w.requestIdleCallback(run, { timeout: 2000 });
  } else {
    window.setTimeout(run, 1000);
  }
}

function readSession(): string[] {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((p) => typeof p === 'string') : [];
  } catch {
    return [];
  }
}

function writeSession(arr: string[]): void {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(arr));
  } catch {
    /* swallow */
  }
}

// "Visitas" (chave global) deve refletir o número de SESSÕES reais, não
// "1ª view de cada página por sessão" somado. Sem isto, uma sessão que
// visita 5 páginas inflava o total em +5. Marcamos um flag booleano por
// sessão para que o hit global dispare uma única vez.
function hasCountedGlobal(): boolean {
  try {
    return sessionStorage.getItem(GLOBAL_COUNTED_KEY) === '1';
  } catch {
    return false;
  }
}

function markCountedGlobal(): void {
  try {
    sessionStorage.setItem(GLOBAL_COUNTED_KEY, '1');
  } catch {
    /* swallow */
  }
}

async function apiCall(kind: 'hit' | 'get', key: string): Promise<number> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), API_DEADLINE_MS);
  try {
    const res = await fetch(`${API_BASE}/${kind}/${NAMESPACE}/${key}`, {
      mode: 'cors',
      credentials: 'omit',
      signal: controller.signal,
    });
    if (!res.ok) return 0;
    const data = (await res.json()) as { value?: unknown };
    return toInt(data?.value);
  } catch {
    return 0;
  } finally {
    window.clearTimeout(timer);
  }
}

export function getCachedClicks(): number {
  return get().clicks;
}

export function getCachedViews(): { global: number; page: number } {
  const s = get();
  return { global: s.global, page: s.page };
}

export async function syncViews(): Promise<{ global: number; page: number }> {
  const path = currentPath();
  const seen = readSession();
  const firstInSession = seen.indexOf(path) === -1;
  // Global: hit UMA vez por sessão (conta sessões = "Visitas" honesto).
  // Página: hit UMA vez por (sessão, página) ("Nesta página").
  const globalCounted = hasCountedGlobal();
  const globalKind: 'hit' | 'get' = globalCounted ? 'get' : 'hit';
  const pageKind: 'hit' | 'get' = firstInSession ? 'hit' : 'get';
  const tasks = [apiCall(globalKind, GLOBAL_KEY), apiCall(pageKind, pageKey())];
  if (!globalCounted) markCountedGlobal();
  if (firstInSession) {
    seen.push(path);
    writeSession(seen);
  }
  const [global, page] = await Promise.all(tasks);
  const s = get();
  if (global > 0) s.global = global;
  if (page > 0) s.page = page;
  write(s);
  return { global: s.global, page: s.page };
}

export function trackClick(): number {
  const s = get();
  s.clicks += 1;
  scheduleWrite();
  return s.clicks;
}
