# Plan: subir el frontend a SvelteKit 3 (seguridad)

Rama: `fix/sveltekit-3-security`, desde `develop` (incluye V2a, PR #42). La PR de V2b (#43) espera esta.

## Motivo

El CI de seguridad (Trivy, job «Dependencies and runtime images») falla en cualquier PR por la vulnerabilidad CVE-2026-128120 (GHSA-3r8g-jcqq-3p5j, severidad HIGH) en `@sveltejs/kit` 2.70.1, publicada el 13/11/2026.

- Afecta de 2.42.0 a 3.1.0 y solo se corrige en 3.1.1; la rama 2.x (2.70.4) no tiene parche.
- El fallo solo se explota con las funciones remotas experimentales, que el proyecto no usa.

**Decisión del usuario (16/11/2026)**: subir a SvelteKit 3 en lugar de documentar una excepción en Trivy.

## Lo que exige SvelteKit 3 (guía oficial «Migrating to SvelteKit 3»)

- Node 22.17 o superior (la imagen usa `NODE_VERSION=20`), TypeScript 6, Svelte 5.57.1, Vite 8.0.12 y `@sveltejs/vite-plugin-svelte` 7. Los adaptadores pasan a node 6, auto 8 y vercel 7.
- `svelte.config.js` desaparece: sus opciones van al plugin `sveltekit()` en `vite.config.ts`.
- `$lib` pasa a `#lib`, declarado en `imports` de `package.json` y con extensión en los imports. Hay 516 archivos afectados.
- `$app/environment` pasa a `$app/env` (14 archivos).
- `$env/...` queda en desuso a favor de `$app/env/public` y `$app/env/private` (3 archivos).
- `goto`:
  - `keepFocus` + `noScroll` pasan a `reset: false`, y `replaceState` a `replace`;
  - `replaceState()` queda en desuso (8 archivos);
  - `goto` rechaza URL externas.
- Errores: el segundo argumento de `error()` debe ser un texto. `isHttpError`/`isRedirect` en lugar de `instanceof` sobre clases internas (6 archivos importan `@sveltejs/kit`).
- La configuración de tsconfig extiende `$app/tsconfig`.
- Hay un codemod oficial: `npx sv migrate sveltekit-3`.

## Pasos

- [x] **Paso 0: plan.**
- [x] **Paso 1: Node 22 en la imagen.**
  - `frontend/Dockerfile` con `NODE_VERSION=22`.
  - Reconstruir el contenedor `frontend`.
- [x] **Paso 2: codemod y versiones.**
  - Correr `npx sv migrate sveltekit-3` dentro del contenedor.
  - Subir kit, adaptadores, vite, vite-plugin-svelte, svelte, typescript, svelte-check y vitest a versiones compatibles.
  - Revisar el diff del codemod.
- [x] **Paso 3: lo que el codemod no resuelva.**
  - Pasar `pnpm check`, `pnpm lint`, `pnpm test:unit --run` y `SVELTE_ADAPTER=node pnpm build`.
- [ ] **Paso 4: verificación.**
  - Escaneo Trivy local del repositorio sin la CVE.
  - Batería completa.
  - QA en el navegador: inicio de sesión, menú, una pantalla con formulario y una con `goto`.
  - PR a `develop`.
- [ ] **Paso 5: V2b.** Llevar `develop` a la rama de V2b para que su CI pase.

## Estado actual

- **Paso en curso**: 4 (verificación y PR).
- **Resultado de la migración**:
  - kit 3.2.0, Svelte 5.57.3, TypeScript 6.0.3, Vite 8.3.8, vite-plugin-svelte 7, adaptadores node 6, auto 8 y vercel 7, y vitest 4.1.12 (vitest 3 no admite Vite 8);
  - `pnpm check` sin errores, `pnpm lint` limpio, 1,146 pruebas unitarias en verde, build con adapter-node y Trivy del repositorio sin vulnerabilidades.
- **Decisiones**:
  - El codemod (`sv migrate sveltekit-3`) corrió además `pnpm format` sobre todo el frontend: +16 mil líneas de puro formato y cambios de fin de línea. Se descartó ese formato. Los imports `$lib/…` → `#lib/…` con extensión y `$app/environment` → `$app/env` se rehicieron con un script sobre los archivos originales. Solo se conservaron los cambios reales del codemod: la guarda de navegación superficial en 8 manejadores `beforeNavigate`/`afterNavigate`, `tsconfig`, `vite.config.ts` y `package.json`.
  - Variables de entorno en `src/env.ts`: `PUBLIC_API_URL` es dinámica y vale `http://localhost:8000` si falta; las claves de mapas son opcionales y estáticas, como antes.
  - adapter-node 6 ignora `ORIGIN`. No se configuró `paths.origin` porque el frontend no tiene acciones de formulario ni endpoints con escritura (solo `GET /healthz`).
- **Problema encontrado**: con el contenedor `frontend` encendido, Windows bloquea la escritura de archivos del bind mount desde el host (EINVAL). Hay que detenerlo para reescrituras masivas.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop`.
  - Ignorar el check de Vercel.
  - No hacer commits mientras corre la batería completa.
