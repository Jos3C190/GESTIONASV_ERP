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

/** Rutas que se cargan al arrancar, en orden: el runtime de SvelteKit y la pantalla de entrada. */
const STARTUP_ROUTES = ['/healthz', '/login'];
const WARMUP_HEADER = 'x-vite-startup-warmup';

/**
 * Arranque en frío ordenado del servidor de desarrollo.
 *
 * La primera carga de SvelteKit compila su runtime y puede tardar más de un minuto con el
 * código montado desde Windows. Si en ese lapso llegan varias solicitudes a la vez (el
 * chequeo de salud cada 10 s y el navegador), compiten por el mismo arranque y Vite corta la
 * carga a los 60 s ("transport invoke timed out"). Aquí el propio servidor visita las rutas de
 * arranque una tras otra, por el mismo camino que un usuario (no es la precarga especulativa de
 * Vite, que compite con SvelteKit), y retiene las demás solicitudes hasta que termina.
 * En modo middleware (Vitest) no hay servidor HTTP y no hace nada.
 */
function warmUpOnStart() {
  return {
    name: 'warm-up-on-start',
    configureServer(server: ViteDevServer) {
      let warming: Promise<void> | null = null;
      server.httpServer?.once('listening', () => {
        const address = server.httpServer?.address();
        if (!address || typeof address === 'string') return;
        const started = Date.now();
        warming = (async () => {
          for (const route of STARTUP_ROUTES) {
            try {
              await fetch(`http://127.0.0.1:${address.port}${route}`, {
                headers: { [WARMUP_HEADER]: '1' },
                redirect: 'manual'
              });
            } catch {
              // Si una ruta falla, la siguiente solicitud real la vuelve a intentar.
            }
          }
        })().finally(() => {
          warming = null;
          server.config.logger.info(
            `  ➜  Rutas de arranque listas en ${((Date.now() - started) / 1000).toFixed(1)} s`
          );
        });
      });
      server.middlewares.use((request, _response, next) => {
        const pending = warming;
        if (!pending || request.headers[WARMUP_HEADER] === '1') {
          next();
          return;
        }
        pending.then(() => next(), next);
      });
    }
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [
    warmUpOnStart(),
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
      // Carpetas que no son código de la app. Montadas desde Windows cada archivo cuesta ~1 ms
      // de consultar: recorrer la caché de pnpm (15 000 archivos) y las salidas de compilación
      // retrasaba más de un minuto la primera carga de SvelteKit y Vite la cortaba a los 60 s.
      ignored: [
        '**/.svelte-kit/**',
        '**/.pnpm-store/**',
        '**/build/**',
        '**/.vercel/**',
        '**/playwright-report/**',
        '**/test-results/**',
        '**/coverage/**'
      ]
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
