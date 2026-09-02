/** @type {import('@sveltejs/kit').Config} */
import autoAdapter from '@sveltejs/adapter-auto';
import nodeAdapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

const adapter = process.env.SVELTE_ADAPTER === 'node' ? nodeAdapter() : autoAdapter();

const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter,
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
