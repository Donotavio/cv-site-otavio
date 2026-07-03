# Brasil Cockpit

Painel executivo com os principais KPIs macroeconômicos do Brasil — "você é o
presidente e quer saber em 30 segundos como o país está indo hoje". Cada
indicador tem status verde/amarelo/vermelho contra metas definidas, delta vs.
período anterior e tendência.

Este é um **sub-projeto embutido no monorepo `cv-site-otavio`**, seguindo o
mesmo padrão dos irmãos **PIX Observatory** e **Data Stack Radar BR**: pipeline
Python Bronze → Silver → Gold (DuckDB + Parquet), JSON exportado para
`assets/data/`, página Astro que consome o JSON em runtime, GitHub Actions que
coletam → transformam → commitam → disparam o deploy. **Zero LLM no runtime.**

> Nota de adaptação: a especificação original descrevia um repo Observable
> Framework separado (`donotavio/brasil-cockpit`) com `.claude/agents/`. A
> decisão foi **embutir como sub-projeto Astro** neste monorepo, usando os
> agentes em `.opencode/agents/` + skills em `.opencode/skills/` +
> `references/taste-kb.md`. Este documento reflete a realidade embutida.

---

## Estrutura

```
ingestion_macro/
  catalog.py            ← fonte única de verdade: séries SGS/SIDRA/market, KPI_META, TARGETS
  collect_sgs.py        ← BACEN SGS (preços, juros, externo, crédito, fiscal)
  collect_caged.py      ← Novo CAGED (start fixo 2020-01-01)
  collect_ptax.py       ← BACEN PTAX: câmbio diário USD e EUR
  collect_ibge.py       ← IBGE SIDRA: PIB, desocupação, PIM, PMC, PMS
  collect_market.py     ← yfinance: Ibovespa (^BVSP)
  requirements.txt
transform_macro/
  silver_macro.py       ← Bronze → Silver (full rebuild, sem argumentos)
  gold_cockpit.py       ← Silver → Gold + assets/data/cockpit.json + historico.json
data/
  bronze/macro_sgs/  macro_caged/  macro_ptax/  macro_ibge/  macro_market/
  silver/{categoria}.parquet
  gold/cockpit.parquet  gold/historico.parquet
assets/data/cockpit.json  assets/data/historico.json   ← consumidos pelo Astro
src/pages/brasil-cockpit.astro
src/components/BrasilCockpitCard.astro   ← card na seção #portfolio
.github/workflows/macro-cockpit-*.yml    ← daily / monthly / caged / quarterly
```

## Comandos

```bash
pip install -r ingestion_macro/requirements.txt
python ingestion_macro/collect_sgs.py
python ingestion_macro/collect_caged.py
python ingestion_macro/collect_ptax.py
python ingestion_macro/collect_ibge.py
python ingestion_macro/collect_market.py
python transform_macro/silver_macro.py    # full rebuild
python transform_macro/gold_cockpit.py    # full rebuild

npm run dev     # Astro — ver a página /brasil-cockpit
npm run build
```

## Contrato de dados (Gold)

**`data/gold/cockpit.parquet` + `assets/data/cockpit.json`** — 1 linha/KPI:

| coluna | descrição |
|---|---|
| `kpi_id` | chave (ex: `ipca_12m`, `selic`, `caged_saldo_12m`) |
| `valor_atual` | último valor |
| `valor_anterior` | valor do período anterior |
| `delta_abs`, `delta_pct` | variação |
| `trend` | `alta` / `baixa` / `estavel` (threshold por KPI em `catalog.TARGETS`) |
| `status` | `verde` / `amarelo` / `vermelho` / `neutro` |
| `meta`, `banda` | meta e banda de tolerância de `catalog.TARGETS` |

**`data/gold/historico.parquet` + `assets/data/historico.json`** — série completa
`(kpi_id, data_referencia, valor)`, limitada aos últimos 5 anos no JSON para
manter o bundle enxuto.

## Convenções (herdadas do monorepo)

- `catalog.py` é importado por todos — **nunca** hardcodar códigos de série ou
  targets fora dele.
- `ibge_territorial_code='1'` para dados nacionais no sidrapy — nunca `'all'`.
- CAGED: `start='2020-01-01'` fixo — Novo CAGED não existe antes desta data.
- SGS API: `start` nunca anterior a 10 anos (`date.today() - timedelta(days=3650)`).
- `silver_macro.py` e `gold_cockpit.py` são **always full rebuild** — sem flags.
- Gold sempre grava **Parquet em `data/gold/` E JSON em `assets/data/`** (o Astro
  consome o JSON em runtime; o Parquet é storage versionado).
- CSS: somente CSS custom properties — nunca hex hardcoded. Tokens de status
  (`--ck-verde/amarelo/vermelho/neutro` + variantes `-ink`) vivem em
  `src/styles/tokens.css`. Variante `-ink` (≥4.5:1 sobre `--paper`) é a única
  permitida em texto.
- Conventional Commits; commits automáticos de dados usam prefixo `data:`.

## CI/CD

Quatro workflows em `.github/workflows/` por cadência de publicação da fonte:

| workflow | cron (UTC) | coleta |
|---|---|---|
| `macro-cockpit-daily.yml` | `0 13 * * 1-5` | ptax + market (após fechamento PTAX 16h BRT) |
| `macro-cockpit-monthly.yml` | `0 6 28 * *` | sgs (preços, juros, comércio, crédito, fiscal) |
| `macro-cockpit-caged.yml` | `0 6 5 * *` | caged (dia 5 garanta publicação do Novo CAGED) |
| `macro-cockpit-quarterly.yml` | `0 6 15 1,4,7,10 *` | ibge (PIB, PNAD, PIM, PMC, PMS) |

Padrão de cada job: `checkout → setup-python 3.12 → pip install → collect →
silver_macro → gold_cockpit → git commit data/ + assets/data/ (prefixo data:) →
createWorkflowDispatch build-and-deploy.yml`. Todos com `workflow_dispatch`.
`GITHUB_TOKEN` padrão basta — todas as fontes são públicas.

## Subagentes (mapeados para `.opencode/agents/`)

A spec original definia 4 agentes em `.claude/agents/`. No monorepo, o trabalho
por domínio é delegado via Task tool aos agentes existentes:

| domínio da spec | agente do monorepo |
|---|---|
| ingestion-engineer | `general` (Python data eng) |
| transform-engineer | `general` (DuckDB) |
| actions-engineer | `general` (GH Actions) |
| observable-engineer | `frontend-builder` + `motion-engineer` + `art-director` + `a11y-perf-auditor` |
