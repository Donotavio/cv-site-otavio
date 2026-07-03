const STATS_KEY = 'or:stats';
const SESSION_KEY = 'or:stats:session';
const API_BASE = 'https://abacus.jasoncameron.dev';
const NAMESPACE = 'otavio-ribeiro-cv-site';
const GLOBAL_KEY = 'visits';

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

async function apiCall(kind: 'hit' | 'get', key: string): Promise<number> {
  try {
    const res = await fetch(`${API_BASE}/${kind}/${NAMESPACE}/${key}`, {
      mode: 'cors',
      credentials: 'omit',
    });
    if (!res.ok) return 0;
    const data = (await res.json()) as { value?: unknown };
    return toInt(data?.value);
  } catch {
    return 0;
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
  const kind: 'hit' | 'get' = firstInSession ? 'hit' : 'get';
  const tasks = [apiCall(kind, GLOBAL_KEY), apiCall(kind, pageKey())];
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
