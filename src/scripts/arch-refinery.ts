/**
 * arch-refinery.ts — "PIPELINE.RUN": datamation ao vivo da arquitetura medalhão.
 *
 * Técnica: animated unit visualization (datamation) — cada dado é uma partícula
 * que FLUI da esquerda p/ direita e se REFINA ao cruzar as 5 zonas do medalhão:
 *   Fontes (disperso, azul) → Landing (estratos append-only) → Bronze (linhas
 *   tipadas) → Prata (qualificação + fração desviada p/ quarentena DQ, âmbar) →
 *   Ouro (cristaliza numa grade OBT dourada, brilha e "materializa").
 *
 * Canvas 2D vanilla (sem libs além do permitido). Cores lidas de tokens.css via
 * getComputedStyle → zero hex hardcoded, single source of truth. Gated por
 * motionOk (sob reduced-motion desenha 1 frame estático "assentado" e para).
 * Pausa fora do viewport (IntersectionObserver) e no visibilitychange.
 */
import { motionOk } from './motion/constants';

interface RGB { r: number; g: number; b: number }

function hexToRgb(hex: string): RGB {
  const h = (hex || '').trim().replace('#', '');
  const n = h.length === 3 ? h.split('').map((c) => c + c).join('') : h.slice(0, 6);
  const int = parseInt(n || '000000', 16);
  return { r: (int >> 16) & 255, g: (int >> 8) & 255, b: int & 255 };
}
const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
const clamp01 = (t: number): number => (t < 0 ? 0 : t > 1 ? 1 : t);
function mix(a: RGB, b: RGB, t: number): RGB {
  return { r: lerp(a.r, b.r, t), g: lerp(a.g, b.g, t), b: lerp(a.b, b.b, t) };
}
const css = (c: RGB, a = 1): string => `rgba(${c.r | 0},${c.g | 0},${c.b | 0},${a})`;

// Fronteiras das 5 zonas (fração de W): Fontes|Landing|Bronze|Prata|Ouro
const Z: number[] = [0, 0.2, 0.4, 0.6, 0.8, 1];
const BANDS = 7; // estratos append-only (landing)
const ROWS = 5;  // linhas tipadas (bronze/prata) e linhas da grade (ouro)

interface P {
  x: number; y: number; px: number; py: number; ty: number; vx: number;
  band: number; row: number; shape: number; seed: number;
  rejected: boolean; gcol: number; goldEnter: number;
  life: number; alpha: number; size: number;
}

/** Evento emitido pela simulação → alimenta o log de execução (terminal). */
export interface RefineryEvent {
  kind: 'merge' | 'quarantine';
  domain?: string;
}

export interface RefineryControl {
  destroy: () => void;
  /** Zona em destaque (0..4) — as demais esmaecem. null = tudo aceso. */
  setZone: (zone: number | null) => void;
  /** Frente de processamento 0..1 (scroll-scrub): o rio "enche" até aqui. */
  setProgress: (p: number) => void;
  /** Reroda o pipeline do zero: drena o rio e re-cascateia numa onda rápida. */
  replay: () => void;
}

interface RefineryOpts { onEvent?: (e: RefineryEvent) => void }

const NOOP: RefineryControl = {
  destroy: () => {}, setZone: () => {}, setProgress: () => {}, replay: () => {},
};

export function initRefinery(canvas: HTMLCanvasElement, opts: RefineryOpts = {}): RefineryControl {
  const ctx = canvas.getContext('2d');
  if (!ctx) return NOOP;
  const c2d: CanvasRenderingContext2D = ctx;

  const countEl = canvas.closest('.refinery')?.querySelector('[data-count]') as HTMLElement | null;
  let materialized = 0;
  let shownCount = -1;

  const root = getComputedStyle(document.documentElement);
  const tok = (name: string, fb: string): string => root.getPropertyValue(name).trim() || fb;
  // Metais levemente puxados p/ tinta → legíveis sobre papel branco, mantendo o matiz.
  const rawC = hexToRgb(tok('--accent', '#1A1AFF'));
  const inkC = hexToRgb(tok('--ink', '#0A0A0A'));
  const bronzeC = mix(hexToRgb(tok('--medallion-bronze', '#CD7F32')), inkC, 0.10);
  const silverC = mix(hexToRgb(tok('--medallion-silver', '#8A9BB0')), inkC, 0.32);
  const goldC = mix(hexToRgb(tok('--medallion-gold', '#D4A017')), inkC, 0.14);
  const warnC = mix(hexToRgb(tok('--warning', '#D99700')), inkC, 0.05);

  let W = 0, H = 0;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  let goldCols = 6;
  let colX: number[] = [];
  let goldFill = 0;

  // Controles externos (hover ↔ zona; scroll-scrub ↔ frente de processamento)
  let activeZone: number | null = null;
  let progress = 1;
  const zoneOf = (fx: number): number => Math.min(4, Math.max(0, Math.floor(fx / 0.2)));
  const revealFrac = (): number => lerp(0.14, 1.06, clamp01(progress));

  // Cursor (repel) — o rio desvia do ponteiro; -9999 = fora do canvas.
  let mx = -9999, my = -9999;
  // Replay — onda rápida que re-cascateia o rio (multiplicador de velocidade que decai).
  let speedMul = 1, replayTimer = 0;
  const REPLAY_MS = 1700;
  // Log de execução: emissão throttled de eventos reais da simulação.
  const onEvent = opts.onEvent;
  const DOMAINS = ['receita', 'operacoes', 'clientes'];
  let lastEmit = -9999;
  const emit = (kind: RefineryEvent['kind'], now: number, domain?: string): void => {
    if (!onEvent || now - lastEmit < 380) return;
    lastEmit = now;
    onEvent({ kind, domain });
  };

  const rnd = (a: number, b: number): number => a + Math.random() * (b - a);
  const bandY = (i: number, n: number): number => lerp(H * 0.16, H * 0.84, n === 1 ? 0.5 : i / (n - 1));

  function resize(): void {
    const rect = canvas.getBoundingClientRect();
    W = Math.max(1, rect.width);
    H = Math.max(1, rect.height);
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    c2d.setTransform(dpr, 0, 0, dpr, 0, 0);
    goldCols = W < 560 ? 4 : W < 900 ? 5 : 6;
    colX = [];
    const gx0 = W * Z[4] + W * 0.03;
    const gx1 = W * 0.975;
    for (let i = 0; i < goldCols; i++) {
      colX.push(lerp(gx0, gx1, goldCols === 1 ? 0.5 : i / (goldCols - 1)));
    }
  }

  const parts: P[] = [];
  function reset(p: P): P {
    p.x = rnd(-W * 0.06, -2);
    p.y = rnd(H * 0.12, H * 0.88);
    p.ty = p.y;
    p.vx = rnd(0.62, 1.05);
    p.band = Math.floor(rnd(0, BANDS));
    p.row = Math.floor(rnd(0, ROWS));
    p.shape = Math.floor(rnd(0, 3));
    p.seed = rnd(0, Math.PI * 2);
    p.rejected = false;
    p.gcol = -1;
    p.goldEnter = 0;
    p.life = 0;
    p.alpha = 0;
    p.size = rnd(2.2, 3.4);
    p.px = p.x;
    p.py = p.y;
    return p;
  }

  function build(): void {
    resize();
    const N = Math.max(80, Math.min(460, Math.round(W / 2.7)));
    parts.length = 0;
    for (let i = 0; i < N; i++) {
      const p = reset({} as P);
      p.x = rnd(0, W);
      p.alpha = 1;
      parts.push(p);
    }
  }

  function colorAt(fx: number, rejected: boolean): RGB {
    if (rejected) return warnC;
    if (fx < Z[2]) return rawC;
    if (fx < Z[3]) return mix(rawC, bronzeC, clamp01((fx - Z[2]) / 0.2));
    if (fx < Z[4]) return mix(bronzeC, silverC, clamp01((fx - Z[3]) / 0.2));
    return mix(silverC, goldC, clamp01((fx - Z[4]) / 0.2));
  }

  // Scaffold do esquemático: guias fracas que a "matéria-prima" preenche.
  function drawScaffold(): void {
    // separadores de zona
    for (let i = 1; i < 5; i++) {
      const x = Math.round(W * Z[i]) + 0.5;
      c2d.strokeStyle = css(inkC, 0.07);
      c2d.lineWidth = 1;
      c2d.beginPath();
      c2d.moveTo(x, H * 0.05);
      c2d.lineTo(x, H * 0.95);
      c2d.stroke();
    }
    // Landing: 7 estratos (linhas tracejadas fracas)
    c2d.strokeStyle = css(inkC, 0.05);
    c2d.setLineDash([3, 4]);
    for (let b = 0; b < BANDS; b++) {
      const y = Math.round(bandY(b, BANDS)) + 0.5;
      c2d.beginPath();
      c2d.moveTo(W * Z[1] + 4, y);
      c2d.lineTo(W * Z[2] - 4, y);
      c2d.stroke();
    }
    // Bronze+Prata: 5 linhas tipadas
    for (let r = 0; r < ROWS; r++) {
      const y = Math.round(bandY(r, ROWS)) + 0.5;
      c2d.beginPath();
      c2d.moveTo(W * Z[2] + 4, y);
      c2d.lineTo(W * Z[4] - 4, y);
      c2d.stroke();
    }
    c2d.setLineDash([]);
    // Ouro: pontos-fantasma da grade OBT (slots a preencher)
    c2d.fillStyle = css(inkC, 0.06);
    for (let r = 0; r < ROWS; r++) {
      for (let cix = 0; cix < goldCols; cix++) {
        const gx = colX[cix];
        const gy = bandY(r, ROWS);
        c2d.fillRect(gx - 1, gy - 1, 2, 2);
      }
    }
  }

  function update(p: P, dt: number, now: number, rf: number): void {
    p.px = p.x;
    p.py = p.y;
    // No ouro a partícula é "puxada" p/ a coluna da grade (x deixa de correr livre).
    if (p.gcol < 0) p.x += p.vx * dt * 0.06 * (W / 900 + 0.5) * speedMul;
    p.life += dt;
    const fx = p.x / W;

    if (fx < Z[1]) {
      // Fontes: dispersão que oscila em torno da banda de destino
      p.ty = bandY(p.band, BANDS) + Math.sin(now / 260 + p.seed) * (H * 0.055);
    } else if (fx < Z[2]) {
      // Landing: assenta nos estratos (append-only)
      p.ty = bandY(p.band, BANDS);
    } else if (fx < Z[3]) {
      // Bronze: alinha às linhas tipadas
      p.ty = bandY(p.row, ROWS);
      p.shape = 1;
    } else if (fx < Z[4]) {
      // Prata: qualifica; fração desvia p/ quarentena DQ
      // ~12% ao longo da zona (prob. por-frame baixa, acumulada em ~60 frames)
      if (!p.rejected && p.gcol < 0 && p.life > 500 && Math.random() < 0.0022) {
        p.rejected = true;
        emit('quarantine', now);
      }
      p.ty = p.rejected ? H * 0.965 : bandY(p.row, ROWS);
      p.shape = 1;
    } else {
      // Ouro: cristaliza na grade OBT (coluna fixa + linha), brilha e materializa
      if (!p.rejected && p.gcol < 0) {
        p.gcol = goldFill % goldCols;
        goldFill++;
        p.goldEnter = p.life;
      }
      p.shape = 1;
      p.ty = bandY(p.row, ROWS);
    }

    const ez = fx < Z[1] ? 220 : 95;
    p.y = lerp(p.y, p.ty, clamp01(dt / ez));
    if (p.gcol >= 0) p.x = lerp(p.x, colX[p.gcol], clamp01(dt / 120));

    // Repel do cursor: bolha que se cura sozinha (o ease puxa de volta à banda).
    if (mx > -9000) {
      const dx = p.x - mx, dy = p.y - my;
      const R = 76;
      const d2 = dx * dx + dy * dy;
      if (d2 < R * R) {
        const d = Math.sqrt(d2) || 1;
        const f = 1 - d / R;
        p.x += (dx / d) * f * f * 9;
        p.y += (dy / d) * f * f * 16;
      }
    }

    // alpha: entra suave; rejeitados somem; ouro segura e depois materializa (fade)
    if (p.rejected) {
      p.alpha -= dt / 520;
    } else if (p.gcol >= 0 && p.life - p.goldEnter > 1400) {
      p.alpha -= dt / 900; // "consumida" como OBT → novo dado toma o slot
    } else {
      p.alpha = Math.min(1, p.alpha + dt / 240);
    }

    if (p.x > W * 1.03 || p.alpha <= 0) {
      // conta OBT só quando a frente de processamento já alcançou o ouro
      if (p.gcol >= 0 && !p.rejected && rf >= 0.8) {
        materialized++;
        emit('merge', now, DOMAINS[materialized % DOMAINS.length]);
      }
      reset(p);
    }
  }

  function drawParticle(p: P, col: RGB, glow: number, mult = 1): void {
    const a = clamp01(p.alpha * mult);
    if (a <= 0) return;
    // Trilha cinética: risco fraco da posição anterior → sensação de fluxo.
    const tdx = p.x - p.px, tdy = p.y - p.py;
    if (tdx * tdx + tdy * tdy > 1.2) {
      c2d.strokeStyle = css(col, 0.16 * a);
      c2d.lineWidth = Math.max(1, p.size * 0.6);
      c2d.beginPath();
      c2d.moveTo(p.px, p.py);
      c2d.lineTo(p.x, p.y);
      c2d.stroke();
    }
    const s = p.size;
    if (glow > 0) {
      c2d.save();
      c2d.shadowColor = css(col, 0.75 * a);
      c2d.shadowBlur = glow;
    }
    c2d.fillStyle = css(col, a);
    if (p.shape === 0) {
      c2d.save();
      c2d.translate(p.x, p.y);
      c2d.rotate(Math.PI / 4);
      c2d.fillRect(-s / 2, -s / 2, s, s);
      c2d.restore();
    } else if (p.shape === 1) {
      c2d.fillRect(p.x - s / 2, p.y - s / 2, s, s);
    } else {
      c2d.beginPath();
      c2d.arc(p.x, p.y, s / 2, 0, Math.PI * 2);
      c2d.fill();
    }
    if (glow > 0) c2d.restore();
  }

  let raf = 0;
  let last = performance.now();
  let running = false;

  function frame(now: number): void {
    const dt = Math.min(42, now - last);
    last = now;
    // Replay: velocidade começa ~4× e decai p/ 1× ao longo de REPLAY_MS.
    if (replayTimer > 0) {
      replayTimer = Math.max(0, replayTimer - dt);
      speedMul = 1 + 3 * (replayTimer / REPLAY_MS);
    } else {
      speedMul = 1;
    }
    c2d.clearRect(0, 0, W, H);
    drawScaffold();
    const rf = revealFrac();
    for (const p of parts) {
      update(p, dt, now, rf);
      const fx = p.x / W;
      // frente de processamento: partículas além de rf esmaecem (o rio "enche" c/ scroll)
      let mult = fx > rf ? clamp01(1 - (fx - rf) / 0.07) : 1;
      // hover: só a zona ativa fica acesa; as demais esmaecem
      if (activeZone !== null && zoneOf(fx) !== activeZone) mult *= 0.15;
      // brilha só quando a partícula TRAVOU na coluna da grade → grade nítida
      const locked = p.gcol >= 0 && !p.rejected && Math.abs(p.x - colX[p.gcol]) < 5;
      drawParticle(p, colorAt(fx, p.rejected), locked ? 4 : 0, mult);
    }
    if (countEl && materialized !== shownCount) {
      countEl.textContent = materialized.toLocaleString('pt-BR');
      shownCount = materialized;
    }
    raf = requestAnimationFrame(frame);
  }

  function start(): void {
    if (running) return;
    running = true;
    last = performance.now();
    raf = requestAnimationFrame(frame);
  }
  function stop(): void {
    running = false;
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
  }

  // Frame estático "assentado" p/ reduced-motion: estrutura montada, grade cheia.
  function drawStatic(): void {
    c2d.clearRect(0, 0, W, H);
    drawScaffold();
    let fill = 0;
    for (const p of parts) {
      const fx = clamp01(p.x / W);
      if (fx < Z[2]) { p.y = bandY(p.band, BANDS); p.shape = p.shape === 2 ? 2 : 0; }
      else if (fx < Z[4]) { p.y = bandY(p.row, ROWS); p.shape = 1; }
      else {
        p.shape = 1;
        p.row = fill % ROWS;
        p.y = bandY(p.row, ROWS);
        p.x = colX[Math.floor(fill / ROWS) % goldCols];
        fill++;
      }
      p.alpha = 1;
      p.px = p.x; p.py = p.y; // sem trilha no frame estático
      drawParticle(p, colorAt(fx, false), fx >= Z[4] ? 5 : 0);
    }
  }

  // ── setup ──
  build();

  if (!motionOk) {
    drawStatic();
    const onResizeStatic = (): void => { build(); drawStatic(); };
    window.addEventListener('resize', onResizeStatic);
    return {
      destroy: () => window.removeEventListener('resize', onResizeStatic),
      setZone: () => {},
      setProgress: () => {},
      replay: () => {},
    };
  }

  const onResize = (): void => build();
  window.addEventListener('resize', onResize);

  const io = new IntersectionObserver(
    (entries) => {
      const vis = entries[0].isIntersecting && document.visibilityState === 'visible';
      if (vis) start();
      else stop();
    },
    { threshold: 0.04 },
  );
  io.observe(canvas);

  const onVis = (): void => { if (document.visibilityState !== 'visible') stop(); };
  document.addEventListener('visibilitychange', onVis);

  const onMove = (e: PointerEvent): void => {
    const r = canvas.getBoundingClientRect();
    mx = e.clientX - r.left;
    my = e.clientY - r.top;
  };
  const onLeave = (): void => { mx = -9999; my = -9999; };
  canvas.addEventListener('pointermove', onMove);
  canvas.addEventListener('pointerleave', onLeave);

  return {
    destroy: () => {
      stop();
      io.disconnect();
      window.removeEventListener('resize', onResize);
      document.removeEventListener('visibilitychange', onVis);
      canvas.removeEventListener('pointermove', onMove);
      canvas.removeEventListener('pointerleave', onLeave);
    },
    setZone: (zone) => { activeZone = zone; },
    setProgress: (p) => { progress = clamp01(p); },
    replay: () => {
      materialized = 0;
      shownCount = -1;
      goldFill = 0;
      // drena tudo p/ a esquerda (staggered) → re-cascateia numa onda
      for (const p of parts) {
        reset(p);
        p.x = -rnd(0, W * 0.6);
        p.alpha = 0;
      }
      replayTimer = REPLAY_MS;
      start();
    },
  };
}
