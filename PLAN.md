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
- [ ] **Paso 2: codemod y versiones.**
  - Correr `npx sv migrate sveltekit-3` dentro del contenedor.
  - Subir kit, adaptadores, vite, vite-plugin-svelte, svelte, typescript, svelte-check y vitest a versiones compatibles.
  - Revisar el diff del codemod.
- [ ] **Paso 3: lo que el codemod no resuelva.**
  - Pasar `pnpm check`, `pnpm lint`, `pnpm test:unit --run` y `SVELTE_ADAPTER=node pnpm build`.
- [ ] **Paso 4: verificación.**
  - Escaneo Trivy local del repositorio sin la CVE.
  - Batería completa.
  - QA en el navegador: inicio de sesión, menú, una pantalla con formulario y una con `goto`.
  - PR a `develop`.
- [ ] **Paso 5: V2b.** Llevar `develop` a la rama de V2b para que su CI pase.

## Estado actual

- **Paso en curso**: 2. La imagen `frontend` ya está en Node 22.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop`.
  - Ignorar el check de Vercel.
  - No hacer commits mientras corre la batería completa.
