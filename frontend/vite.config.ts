import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig, type ViteDevServer } from 'vite';

function normalizeSvelteRouteModulePath() {
  return {
    name: 'normalize-svelte-route-module-path',
    enforce: 'pre' as const,
    configureServer(server: ViteDevServer) {
      server.middlewares.use((request, _response, next) => {
        const url = request.url;
        if (!url?.startsWith('/src/routes/')) {
          next();
          return;
        }

        const queryStart = url.indexOf('?');
        const pathname = queryStart === -1 ? url : url.slice(0, queryStart);
        if (!pathname.includes('%2B')) {
          next();
          return;
        }

        request.url =
          pathname.replace(/%2B/gi, '+') + (queryStart === -1 ? '' : url.slice(queryStart));
        next();
      });
    }
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [
    normalizeSvelteRouteModulePath(),
    sveltekit(),
    ...(mode === 'test' ? [svelteTesting()] : [])
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // Let SvelteKit initialize SSR on demand. Speculative app-route warmup can
    // race its server module runner and cache a 500 response until restart.
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
