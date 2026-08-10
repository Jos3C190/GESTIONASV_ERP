/** @type {import('@sveltejs/kit').Config} */
import adapter from '@sveltejs/adapter-auto';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter(),
    alias: {
      $lib: './src/lib',
      '$lib/*': './src/lib/*'
    }
  },
  compilerOptions: {
    runes: true
  }
};

export default config;
