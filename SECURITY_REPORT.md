# Security Report — Pre-Production Audit

**Date:** 2026-06-28
**Scope:** cv-site-otavio (redesign Blueprint, Astro) antes do deploy em produção.
**Status:** ✓ APROVADO — sem vazamentos de credenciais; site seguro para publicação.

---

## 1. Varredura de Secrets / Credenciais

| Verificação | Resultado |
|-------------|-----------|
| Chaves de API reais (OpenAI `sk-`, GitHub `ghp_`/`github_pat_`, AWS `AKIA`, Google `AIza`, JWT) | **Nenhuma** no código ou no histórico |
| Cookies de sessão LinkedIn (`li_at`, `JSESSIONID`) hardcoded | **Nenhum** — lidos via `os.getenv()` |
| Chaves privadas (`-----BEGIN`) | Nenhuma |
| `.env` / dumps / `.pem` / `.key` rastreados | Nenhum |

Os scripts Python (`fetch_github_data.py`, `fetch_linkedin_data_enhanced.py`) obtêm
todos os segredos de variáveis de ambiente (`GITHUB_TOKEN`, `LINKEDIN_SESSION_COOKIE`,
`POLYGLOT_API_KEY`), nunca hardcoded. As GitHub Actions usam `${{ secrets.* }}`.

## 2. `.gitignore`

Cobre: `.env`, `.env.local`, `*.pem`, `*.key`, `*_TOKEN`, `*_SECRET`, `*_PASSWORD`,
`__pycache__/`, `_site/`, `dist/`, `node_modules/`.

## 3. Dados pessoais

O site é um CV público — nome, cargo, links profissionais (LinkedIn/GitHub) e
contato são intencionalmente públicos. Varredura confirmou **ausência** de CPF, RG,
senhas ou dados privados indevidos. (Match de "rg" foi falso positivo: "organização".)

## 4. Histórico do Git — `debug_linkedin.html`

- Existiu no commit inicial (`7226b7d`), removido do working tree em fase anterior.
- **Não está** no site publicado (deploy vem de `dist/`, gerado pelo Astro).
- Análise do conteúdo histórico: é a página **pública/guest** do LinkedIn
  (contém "guest"/"entrar"), **sem valores reais** de csrfToken/JSESSIONID/li_at —
  apenas nomes de campos HTML.
- **Decisão:** não reescrever o histórico (sem credenciais reais; risco baixo;
  reescrita é destrutiva e exige force-push). Documentado para transparência.

## 5. Headers de Segurança (via meta — GitHub Pages não permite headers HTTP)

Adicionados em `BaseLayout.astro`:
- `Content-Security-Policy`: `default-src 'self'`; scripts/styles `'self' 'unsafe-inline'`
  (necessário para scripts inline do Astro e i18n.js); `img-src 'self' data:`;
  `font-src 'self'` (fontes self-hosted); `connect-src 'self'` (fetch dos JSON locais);
  `object-src 'none'`; `base-uri 'self'`; `form-action 'self'`.
- `X-Content-Type-Options: nosniff`
- `referrer: strict-origin-when-cross-origin`

Nota: `frame-ancestors` não é aplicável via meta tag (só header HTTP) — removido.
Para um site estático sem inputs de usuário/backend, a superfície de XSS é mínima.

Validação: com a CSP ativa, i18n, fontes e fetch de dados funcionam (0 violações
de CSP relevantes).

## 6. Recursos Externos

**Zero** recursos externos carregados: fontes self-hosted (woff2 locais), todos os
JSON/imagens/scripts servidos do próprio domínio. Links externos (LinkedIn/GitHub)
são apenas `<a href>` de navegação com `rel="noopener noreferrer"`.

## 7. Legado Jekyll (não atrapalha o deploy)

- Removidos: `_config.yml`, `_layouts/`, `_includes/`, `index.html`, `Gemfile`,
  `.ruby-version` (entrypoints Jekyll que conflitariam com o build Astro).
- `.nojekyll` adicionado em `public/` → presente em `dist/` (impede o GitHub Pages
  de processar a saída como Jekyll).
- `_site/` e `Gemfile.lock` não rastreados (`.gitignore`).
- Deploy via `.github/workflows/build-and-deploy.yml` (Astro build → `dist/` →
  GitHub Pages Actions), independente de qualquer processamento Jekyll.

---

## Veredicto

**✓ SEGURO PARA PRODUÇÃO.** Nenhuma credencial exposta, headers de segurança
aplicados, recursos 100% locais, legado Jekyll neutralizado. O pipeline de dados
Python continua usando secrets via env/Actions, sem hardcode.
