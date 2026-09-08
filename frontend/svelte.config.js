/** @type {import('@sveltejs/kit').Config} */
import autoAdapter from '@sveltejs/adapter-auto';
import nodeAdapter from '@sveltejs/adapter-node';
import { env } from 'node:process';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

const useNodeAdapter = env.SVELTE_ADAPTER === 'node' || env.NODE_ENV === 'production';
const adapter = useNodeAdapter ? nodeAdapter() : autoAdapter();

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
