# KB de Gosto — Redesign cv-site-otavio

> Âncora de POV para a direção de arte. Referências reais (2024–2026), verificadas.
> Gênero: site pessoal de um **Data Engineering Manager** — público de hiring
> managers, CTOs e pares. Objetivo: **memorável e crível**, não "template".
> O que estamos deixando para trás: o look "dashboard SaaS dark" (navy quase-preto +
> glow azul/ciano + canvas de partículas + badge soup).

---

## Referências

### 1. Brittany Chiang — brittanychiang.com
- **Por que funciona:** o site canônico de "engenheiro que sabe design" — ganha
  credibilidade por **restrição**, não por efeitos; lê como um README calmo e bem
  documentado.
- **Paleta:** dark slate + texto cinza-claro + **um único acento ciano**, aplicado
  com disciplina (só links/destaques).
- **Tipografia:** uma só família (**Inter**); hierarquia por escala e peso, sem
  segunda face de display.
- **Motion:** muito contido — nav fixa na esquerda, fade/translate suave no scroll.
- **Roubar:** o **split "bio fixa à esquerda / conteúdo rola à direita"** — mantém
  nome, cargo e a tese de uma linha ancorados enquanto a experiência rola.
- ⚠️ É o look mais clonado do gênero. Roubar a *estrutura e a restrição*, **não** a
  paleta navy+ciano (é exatamente a armadilha "dark SaaS genérico").

### 2. Stefan Vitasović — stefanvitasovic.dev (Codrops, mar/2025)
- **Por que funciona:** um motivo de motion **conceitual**, amarrado ao ofício —
  rigidez do print suíço + uma camada digital "crua".
- **Paleta:** base monocromática com grão/textura (não-chapado, mas sem cor).
- **Tipografia:** **inspirada em print suíço** — grids deslocados, whitespace
  generoso, tipografia como protagonista.
- **Motion:** assinatura = **caracteres se montando em palavras**; crossfades de
  0.5s; deslocamento WebGL sutil nas transições.
- **Roubar:** "bits se montam no produto" como **metáfora do próprio trabalho** —
  texto/números resolvendo numa headline limpa = aceno honesto a pipeline
  (raw → modelado), sem clichê.

### 3. Gianluca Gradogna — gianlucagradogna.com (Codrops, jan/2025)
- **Por que funciona:** sofisticação de motion usando **só o básico**; unifica duas
  disciplinas num scroll contínuo.
- **Tipografia:** sans suíço limpo; troca de face **sinaliza mudança de seção**.
- **Motion:** limitado de propósito a **Position, Opacity e Clip Masks** — todo o
  polimento vem do easing/timing.
- **Roubar:** o **orçamento de motion auto-imposto** (três propriedades, ponto).
  Constraint perfeita para um site de engenharia: parece crafted e fica rápido.

### 4. Pell Mell — pellmell.fr (Codrops, mar/2026)
- **Por que funciona:** "a interface tinha que desaparecer" — deletaram UI até sobrar
  só o essencial; o ritmo editorial carrega a experiência. *(É plataforma, não
  portfólio — incluída pelo pensamento de sistema editorial.)*
- **Tipografia:** uma display (Season/Displaay) que **se comporta quase como
  logotipo**, reusada estruturalmente.
- **Motion:** reveals suaves, levemente atrasados e **escalonados** (stagger).
- **Roubar:** uma **gramática de blocos nomeados** (`hero`, `grid`, `highlight`,
  `textBlock`) em vez de liberdade infinita — cada seção lê como uma publicação.
  Aplicação direta a um site movido a JSON.

### 5. Pacôme Pertant — pacomepertant.com (Awwwards SOTD, jun/2026)
- **Por que funciona:** um sistema de **duas cores** + um único marquee hipnótico —
  faz muito com quase nenhuma paleta.
- **Paleta:** **duas cores** (near-black + um tom claro); alto contraste, zero
  gradiente.
- **Motion:** um **marquee contínuo** como dispositivo central + entrada
  som-on/som-off como escolha de design.
- **Roubar:** **um elemento-assinatura em loop** como âncora de personalidade — ex.:
  marquee lento dos sistemas/escala que você domina ("petabyte • streaming •
  lineage •"). Uma ideia de motion, dominada por completo, vence cinco.
- ⚠️ Stack pesado (GSAP/Three/Nuxt). Roubar a *ideia*, não o ferramental.

### 6. "Swiss Grid" — sistema editorial (studio.swiperjs.com/templates/swiss-grid)
- **Por que funciona:** um grid estrito transforma cards soltos numa **publicação
  contínua**. *(É template — incluído como o exemplo mais claro do eixo
  editorial/tipográfico, com specs declaradas.)*
- **Paleta:** monocromático (tinta quase-preta sobre claro) + **um acento vermelho
  suíço**; fotografia monocromática.
- **Tipografia:** **Inter 700** display + **IBM Plex Mono** em labels pequenos
  (números de projeto, locais, anos) — o par grotesk/mono explícito.
- **Roubar:** **labels em mono para metadados** — cargo, datas, tamanho de time,
  escala e tech em IBM Plex Mono sobre um grotesk humanista. É o movimento mais
  barato para o site soar "painel de instrumentos", não "blog".

---

## O eixo "data/sistemas como estética" (com bom gosto)

O clichê a evitar é a rede-de-partículas-ciano-brilhante. A alternativa crível
aparece sob a tendência 2026 **"Micrographics"** (It's Nice That): detalhes técnicos
minúsculos — símbolos de blueprint, métricas mínimas, fragmentos de diagrama —
tratados como **peças deliberadas de design**, não ornamento decorativo. Combinado
com **labels em mono** (ref 6), é o jeito honesto de tornar engenharia de dados
legível como estética: ornamento pequeno, preciso e factual.

---

## Direções 2026 — duráveis (não-modismo)

1. **Layouts editoriais / suíços** (grid estrito, whitespace generoso). *Dura porque*
   grid é estrutura, não moda; envelhece como revista bem diagramada e escala com o
   conteúdo.
2. **Par grotesk + mono** (sans humanista para leitura, mono para metadados).
   *Dura porque* é funcional: mono sinaliza precisão e dados sem ilustração.
3. **Display serifado de alto contraste** para autoridade editorial. *Dura porque*
   serifa refinada sinaliza autoridade — alternativa crível ao sans-geométrico-no-dark
   batido.
4. **Motion contido e proposital** (stagger fade/translate; um dispositivo-assinatura).
   *Dura porque* motion que guia atenção sobrevive; motion que se exibe envelhece em
   um ano. Espelha o "orçamento de 3 propriedades" (ref 3).
5. **Gramática de blocos / bento justificado** (poucos blocos nomeados). *Dura porque*
   constraint preserva coerência conforme o conteúdo cresce — sistema, não layout
   avulso. Combina com site movido a JSON.
6. **Micrographics + handcraft anti-IA** (textura, diagramas reais, detalhe factual).
   *Dura porque* com a IA inundando visuais "tech" genéricos, o detalhe específico e
   humano vira o diferencial que lê como expertise.

---

## Princípios extraídos (entram nas direções e na skill design-system)

1. **Um acento, com disciplina.** Nada de paleta-arco-íris. Cor é evento, não fundo.
2. **Mono carrega os dados.** Metadados (datas, escala, tech, métricas) em mono.
3. **Orçamento de motion ≤ 5 padrões**, três propriedades preferidas (position,
   opacity, clip). Um dispositivo-assinatura.
4. **Grid como espinha.** Tudo alinhado a um ritmo vertical único.
5. **Cortar até doer.** A interface desaparece; sobra o conteúdo.
6. **Honestidade > efeito.** Se um motivo não fala do trabalho (raw → modelado),
   não entra.

> Fontes: Awwwards (Developer SOTD), Codrops (Stefan Vitasović, Gianluca Gradogna,
> Pell Mell), brittanychiang.com, Swiper Studio (Swiss Grid), It's Nice That
> (tendências 2026), Figma Resource Library, Muzli. Hex exatos raramente são
> publicados; onde não verificável, está sinalizado.

---

## Direção escolhida — GATE 1: **A · Instrument Panel**

Editorial claro e preciso. O POV travado para todo o build:

- **Paleta:** paper `#F6F4EF` · ink `#17181B` · muted `#6B6F76` · **um** acento
  vermelhão-sinal `#E1462B`.
- **Tipografia:** Space Grotesk (display) + Inter (corpo) — ambas já carregadas —
  + IBM Plex Mono para **todos os metadados** (datas, escala, tech, métricas).
- **Motion-assinatura:** metadados em mono "resolvem" no lugar (raw → modelado) +
  reveals escalonados (opacity/translate). Um dispositivo-assinatura, ≤ 5 padrões.
- **Intenção:** *"abrir a documentação impecável de um sistema que você confiaria
  em produção."*
- **Layout:** bio fixa à esquerda (nome · cargo · tese · seletor de idioma) +
  conteúdo numerado rolando à direita (01 experiência, 02 projetos, 03 stack…).

Tokens completos em `DESIGN.md` (Phase 2). Refs-âncora desta direção: **6** (Swiss
Grid — labels em mono), **1** (Brittany Chiang — split bio fixa + restrição),
**3** (Gradogna — orçamento de 3 propriedades), **2** (Vitasović — raw→modelado).
