#!/usr/bin/env node
/**
 * Translate LinkedIn articles using polyglot-ai core.
 *
 * Reads assets/data/blog_articles.json (pt-BR base) and produces
 * translated versions for en-US and es-ES.
 *
 * Usage:
 *   POLYGLOT_AI_PATH=/path/to/polyglot-ai POLYGLOT_API_KEY=sk-... node scripts/translate_articles.js
 */

import { readFile, writeFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, '..');
const DATA_DIR = resolve(PROJECT_ROOT, 'assets', 'data');

const POLYGLOT_PATH = process.env.POLYGLOT_AI_PATH || resolve(PROJECT_ROOT, '..', 'polyglot-ai');
const SOURCE_LOCALE = 'pt-BR';
const TARGET_LOCALES = ['en-US', 'es-ES'];

async function loadTranslator() {
  const translatorPath = resolve(POLYGLOT_PATH, 'src', 'core', 'translator.js');
  try {
    return await import(translatorPath);
  } catch (err) {
    console.error(`Failed to load polyglot-ai from ${translatorPath}`);
    console.error('Set POLYGLOT_AI_PATH to the polyglot-ai repo root.');
    throw err;
  }
}

async function main() {
  console.log('=== Article Translator ===\n');

  // Load articles
  const articlesPath = resolve(DATA_DIR, 'blog_articles.json');
  const articlesData = JSON.parse(await readFile(articlesPath, 'utf-8'));
  const articles = articlesData.articles || [];

  if (!articles.length) {
    console.log('No articles to translate.');
    return;
  }

  console.log(`Found ${articles.length} article(s) to translate.`);

  const { translateKeys, createProvider } = await loadTranslator();

  const config = {
    provider: process.env.POLYGLOT_PROVIDER || 'openai',
    apiKey: process.env.POLYGLOT_API_KEY || process.env.LLM_API_KEY,
    model: process.env.POLYGLOT_MODEL || 'gpt-4o-mini',
    batchSize: 10,
    contextPrompt: 'These are LinkedIn Pulse article texts by a Data Engineering Manager. Translate naturally, preserving technical terms, markdown formatting (## headers, > blockquotes, - lists), and the professional tone.',
  };

  if (!config.apiKey) {
    console.error('Error: POLYGLOT_API_KEY or LLM_API_KEY env var required.');
    process.exit(1);
  }

  for (const targetLocale of TARGET_LOCALES) {
    console.log(`\n--- Translating to ${targetLocale} ---`);

    const translatedArticles = [];

    for (let i = 0; i < articles.length; i++) {
      const article = articles[i];
      console.log(`  [${i + 1}/${articles.length}] ${article.title.slice(0, 50)}...`);

      // Build a flat object of translatable fields
      const keysToTranslate = {
        title: article.title,
        excerpt: article.excerpt || '',
      };

      // Translate body in a separate call (can be large)
      const bodyKeys = {};
      if (article.body) {
        // Split body into chunks if very large (> 3000 chars)
        const bodyChunks = splitBody(article.body, 3000);
        bodyChunks.forEach((chunk, idx) => {
          bodyKeys[`body_${idx}`] = chunk;
        });
      }

      // Translate metadata (title + excerpt)
      const translatedMeta = await translateKeys({
        keysToTranslate,
        sourceLocale: SOURCE_LOCALE,
        targetLocale,
        config,
      });

      // Translate body chunks
      let translatedBody = '';
      if (Object.keys(bodyKeys).length > 0) {
        const translatedBodyChunks = await translateKeys({
          keysToTranslate: bodyKeys,
          sourceLocale: SOURCE_LOCALE,
          targetLocale,
          config: { ...config, contextPrompt: config.contextPrompt + ' Preserve paragraph breaks and markdown formatting exactly.' },
        });

        // Reassemble body
        const chunkCount = Object.keys(bodyKeys).length;
        const chunks = [];
        for (let c = 0; c < chunkCount; c++) {
          chunks.push(translatedBodyChunks[`body_${c}`] || '');
        }
        translatedBody = chunks.join('\n\n');
      }

      // Translate tags
      let translatedTags = article.tags || [];
      if (translatedTags.length > 0) {
        const tagKeys = {};
        translatedTags.forEach((tag, idx) => {
          tagKeys[`tag_${idx}`] = tag;
        });
        const translatedTagResult = await translateKeys({
          keysToTranslate: tagKeys,
          sourceLocale: SOURCE_LOCALE,
          targetLocale,
          config,
        });
        translatedTags = translatedTags.map((_, idx) => translatedTagResult[`tag_${idx}`] || translatedTags[idx]);
      }

      translatedArticles.push({
        ...article,
        title: translatedMeta.title || article.title,
        excerpt: translatedMeta.excerpt || article.excerpt,
        body: translatedBody || article.body,
        tags: translatedTags,
      });
    }

    // Write translated file
    const output = {
      ...articlesData,
      articles: translatedArticles,
    };

    const outputPath = resolve(DATA_DIR, `blog_articles_${targetLocale}.json`);
    await writeFile(outputPath, JSON.stringify(output, null, 2) + '\n', 'utf-8');
    console.log(`  ✓ Saved ${outputPath}`);
  }

  console.log('\n✓ All translations complete.');
}

/**
 * Split body text into chunks at paragraph boundaries.
 */
function splitBody(text, maxChars) {
  if (text.length <= maxChars) return [text];

  const paragraphs = text.split('\n\n');
  const chunks = [];
  let current = '';

  for (const para of paragraphs) {
    if (current.length + para.length + 2 > maxChars && current.length > 0) {
      chunks.push(current.trim());
      current = para;
    } else {
      current += (current ? '\n\n' : '') + para;
    }
  }

  if (current.trim()) {
    chunks.push(current.trim());
  }

  return chunks.length > 0 ? chunks : [text];
}

main().catch((err) => {
  console.error('Fatal error:', err.message);
  process.exit(1);
});
