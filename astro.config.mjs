import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://hsbrxlb.github.io',
  base: '/opportunity-gazette',
  output: 'static',
  integrations: [sitemap()],
  build: {
    format: 'directory',
  },
});
