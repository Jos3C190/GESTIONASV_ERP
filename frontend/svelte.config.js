/** @type {import('@sveltejs/kit').Config} */
import adapter from '@sveltejs/adapter-auto';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter(),
    // Use a dedicated development output folder so Vite treats generated
    // SvelteKit artifacts as its own output instead of watched source files.
    outDir: process.env.SVELTEKIT_OUT_DIR ?? '.svelte-kit',
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
