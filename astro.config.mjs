// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
  site: 'https://donotavio.github.io',
  base: '/cv-site-otavio/',
  output: 'static',
  build: {
    // _astro evita conflito com public/assets/ (dados, imagens, i18n)
    assets: '_astro',
  },
  vite: {
    build: {
      // Keep SVGs as separate files (not inlined as base64)
      assetsInlineLimit: 0,
    },
  },
});
