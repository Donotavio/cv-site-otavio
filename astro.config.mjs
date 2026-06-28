// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
  site: 'https://donotavio.github.io',
  base: '/cv-site-otavio/',
  output: 'static',
  build: {
    // Keep assets folder name consistent with existing pipeline paths
    assets: 'assets',
  },
  vite: {
    build: {
      // Keep SVGs as separate files (not inlined as base64)
      assetsInlineLimit: 0,
    },
  },
});
