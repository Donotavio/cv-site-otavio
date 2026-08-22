/**
 * Smoke test de render das páginas de dashboard, SEM browser.
 *
 * Por que existe: as páginas de sub-projeto (eleicoes-2026, pix-observatory,
 * brasil-cockpit, ...) montam quase tudo em runtime via `innerHTML` a partir
 * dos JSONs de `assets/data/`. O `astro build` passa mesmo quando a seção
 * renderiza vazia ou sem estilo, então build verde != página correta. Em
 * ambiente headless (CI, agente de background) não há Chrome para conferir —
 * este script carrega o HTML buildado + o bundle JS real em jsdom, serve os
 * JSONs por fetch mockado e imprime o que o usuário efetivamente veria.
 *
 * Caso real que motivou: as seções [13]/[14] do eleicoes-2026 foram ao ar
 * exibindo dezenas de cards vazios porque o TSE passou a bloquear a coleta —
 * build e type-check estavam verdes o tempo todo.
 *
 * Pré-requisito (jsdom NÃO é dependência do projeto, para não pesar o build):
 *     npm install jsdom --no-save
 *
 * Uso:
 *     npm run build && node scripts/render_check.mjs
 *     node scripts/render_check.mjs --page eleicoes-2026
 *
 * Saída: relatório por seção; exit != 0 se houver erro de console ou se
 * nenhuma seção renderizar conteúdo (sinal de quebra geral).
 */
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const pageArg = process.argv.indexOf("--page");
const PAGE = pageArg > -1 ? process.argv[pageArg + 1] : "eleicoes-2026";

let JSDOM, VirtualConsole;
try {
  ({ JSDOM, VirtualConsole } = await import("jsdom"));
} catch {
  console.error("✗ jsdom não encontrado. Rode: npm install jsdom --no-save");
  process.exit(2);
}

const htmlPath = join(ROOT, "dist", PAGE, "index.html");
if (!existsSync(htmlPath)) {
  console.error(`✗ ${htmlPath} não existe — rode 'npm run build' antes.`);
  process.exit(2);
}

const astroDir = join(ROOT, "dist/_astro");
const bundles = readdirSync(astroDir).filter(
  (f) => f.startsWith(`${PAGE}.astro_astro_type_script_index_`) && f.endsWith(".js")
);
if (!bundles.length) {
  console.error(`✗ bundle JS de ${PAGE} não encontrado em dist/_astro.`);
  process.exit(2);
}

// Serve qualquer asset pedido pela página (JSON de dados, SVG de mapa, ...)
// resolvendo o caminho da URL contra a raiz do repo — servir só assets/data
// fazia as seções de mapa acusarem erro que não existe em produção.
const BASE_PREFIX = "/cv-site-otavio/";
const resolveAsset = (url) => {
  const path = String(url).split("?")[0];
  const rel = path.startsWith(BASE_PREFIX) ? path.slice(BASE_PREFIX.length) : path.replace(/^\//, "");
  return join(ROOT, rel);
};
const virtualConsole = new VirtualConsole();
const consoleErrors = [];
virtualConsole.on("jsdomError", (e) => consoleErrors.push(`jsdomError: ${e.message}`));
virtualConsole.on("error", (...a) => consoleErrors.push(`console.error: ${a.join(" ")}`));

const dom = new JSDOM(readFileSync(htmlPath, "utf8"), {
  runScripts: "outside-only",
  url: `https://donotavio.github.io/cv-site-otavio/${PAGE}/`,
  pretendToBeVisual: true,
  virtualConsole,
});
const { window } = dom;

const served = [];
const missing = [];
window.fetch = async (url) => {
  const name = String(url).split("/").pop().split("?")[0];
  const file = resolveAsset(url);
  if (!existsSync(file)) {
    missing.push(name);
    return { ok: false, status: 404, json: async () => ({}), text: async () => "" };
  }
  served.push(name);
  const body = readFileSync(file, "utf8");
  return { ok: true, status: 200, json: async () => JSON.parse(body), text: async () => body };
};
window.matchMedia = window.matchMedia || (() => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
window.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0);
window.scrollTo = () => {};
// jsdom não implementa IntersectionObserver (usado por jumpnav/scrollspy).
window.IntersectionObserver = class {
  observe() {} unobserve() {} disconnect() {} takeRecords() { return []; }
};

// Bundles de motion (GSAP/Lenis) usam `import` ES e não rodam sob window.eval;
// são irrelevantes para o conteúdo renderizado, então basta pular e avisar.
const pulados = [];
let executados = 0;
for (const b of bundles) {
  const code = readFileSync(join(astroDir, b), "utf8");
  if (/^\s*import[\s{*'"]/m.test(code)) { pulados.push(b.split(".")[0] + "…(módulo ES)"); continue; }
  // IIFE: bundles minificados declaram os mesmos nomes curtos (`e`, `t`, ...)
  // em escopo de módulo. Avaliados juntos no escopo global do jsdom eles se
  // sobrescrevem e produzem erros fantasma (ex.: "e.format is not a function").
  try { window.eval(`(function(){${code}\n})()`); executados++; } catch (e) { consoleErrors.push(`eval ${b}: ${e.message}`); }
}
if (executados === 0) {
  // Nenhum script da página rodou (todos são módulos ES com import). Qualquer
  // veredito aqui seria falso — as seções ficariam "presas em loading" só
  // porque nada as populou. Melhor declarar inconclusivo que dar OK vazio.
  console.log(`\n📄 ${PAGE} — smoke test de render (jsdom)\n`);
  console.log(`  ⚠ INCONCLUSIVO: nenhum bundle executável (${bundles.length} são módulos ES).`);
  console.log(`    Esta página monta o conteúdo via import de módulos, que window.eval não suporta.`);
  console.log(`    Validar com browser real ou 'npm run preview'.\n`);
  process.exit(3);
}
window.document.dispatchEvent(new window.Event("astro:page-load"));
await new Promise((r) => setTimeout(r, 1500));

const d = window.document;
console.log(`\n📄 ${PAGE} — smoke test de render (jsdom)\n`);
console.log(`  assets servidos: ${served.length}${missing.length ? ` · ausentes: ${[...new Set(missing)].join(", ")}` : ""}`);
if (pulados.length) console.log(`  bundles pulados: ${pulados.length} (módulos ES de motion — não afetam conteúdo)`);

let comConteudo = 0;
const linhas = [];
for (const sec of d.querySelectorAll("section[id]")) {
  const num = sec.querySelector(".mono-label")?.textContent?.trim() ?? "--";
  // "Conteúdo" = o que o JS injetou/manteve, ignorando placeholders de loading.
  const vazioPlaceholder = sec.querySelectorAll(".el-loading, .ck-loading").length;
  const erro = sec.querySelectorAll(".el-error").length;
  const espera = sec.querySelectorAll(".el-await, .el-prest-pending").length;
  const texto = (sec.textContent ?? "").replace(/\s+/g, " ").trim();
  const ok = texto.length > 120 && !vazioPlaceholder;
  if (ok) comConteudo++;
  const flag = erro ? "✗ erro" : espera ? "⏳ aguardando dado" : vazioPlaceholder ? "✗ preso em loading" : ok ? "✓" : "· vazio";
  linhas.push(`  [${num}] ${sec.id.padEnd(20)} ${flag}`);
}
console.log(linhas.join("\n"));
console.log(`\n  seções com conteúdo: ${comConteudo}/${d.querySelectorAll("section[id]").length}`);
console.log(`  erros de console   : ${consoleErrors.length ? "\n    " + consoleErrors.slice(0, 8).join("\n    ") : "nenhum"}`);

const falhou = consoleErrors.length > 0 || comConteudo === 0;
console.log(falhou ? "\n✗ smoke test FALHOU\n" : "\n✓ smoke test OK\n");
process.exit(falhou ? 1 : 0);
