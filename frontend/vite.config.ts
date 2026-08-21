import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vite';

export default defineConfig(({ mode }) => ({
  plugins: [sveltekit(), ...(mode === 'test' ? [svelteTesting()] : [])],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    warmup: {
      // Transform the product screens during startup to avoid a long SSR
      // transform waterfall on the first navigation in slower environments.
      ssrFiles: [
        './src/routes/(app)/+layout.svelte',
        './src/routes/(app)/products/[id]/+page.svelte',
        './src/routes/(app)/products/[id]/variants/[variantId]/+page.svelte'
      ]
    },
    watch: {
      ignored: ['**/.svelte-kit/**']
    },
    fs: {
      strict: false
    }
  },
  preview: {
    host: '0.0.0.0',
    port: 3000
  },
  test: {
    include: ['src/**/*.test.{ts,js}', 'tests/unit/**/*.test.{ts,js}'],
    environment: 'happy-dom',
    setupFiles: ['./tests/unit/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/lib/**/*.{ts,svelte}']
    }
  }
}));
