/** @type {import('@sveltejs/kit').Config} */
import autoAdapter from '@sveltejs/adapter-auto';
import nodeAdapter from '@sveltejs/adapter-node';
import vercelAdapter from '@sveltejs/adapter-vercel';
import { env } from 'node:process';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

const useNodeAdapter = env.SVELTE_ADAPTER === 'node';
const useVercelAdapter =
  env.SVELTE_ADAPTER === 'vercel' || env.VERCEL === '1' || env.VERCEL === 'true';
const adapter = useNodeAdapter
  ? nodeAdapter()
  : useVercelAdapter
    ? vercelAdapter()
    : autoAdapter();

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
