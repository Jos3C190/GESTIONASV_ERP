import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
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
});
