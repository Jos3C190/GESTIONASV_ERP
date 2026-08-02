<script lang="ts">
  import { goto } from '$app/navigation';
  import { session } from '$lib/stores/session.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { api, HttpError } from '$lib/api/client';
  import { z } from 'zod';

  const loginSchema = z.object({
    login: z.string().min(3, 'Mínimo 3 caracteres').max(320),
    password: z.string().min(1, 'Ingrese su contraseña').max(128)
  });

  let loginValue = $state('');
  let passwordValue = $state('');
  let errors = $state<{ login?: string; password?: string; form?: string }>({});
  let submitting = $state(false);
  let showPassword = $state(false);

  function validate(): boolean {
    const result = loginSchema.safeParse({ login: loginValue, password: passwordValue });
    if (result.success) { errors = {}; return true; }
    const fieldErrors: { login?: string; password?: string } = {};
    for (const issue of result.error.issues) {
      const field = issue.path[0] as 'login' | 'password';
      if (!fieldErrors[field]) fieldErrors[field] = issue.message;
    }
    errors = fieldErrors;
    return false;
  }

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault();
    if (submitting) return;
    if (!validate()) return;
    submitting = true; errors = {}; session.setLoading(true);
    try {
      const tokens = await api.auth.login(loginValue, passwordValue);
      session.setToken(tokens.access_token);
      const me = await api.auth.me();
      session.setUser(me);
      const perms = await api.auth.myPermissions();
      permissions.set(perms.permissions, perms.is_superuser);
      await goto('/companies');
    } catch (err) {
      errors.form = err instanceof HttpError ? err.message : 'Error inesperado. Intente nuevamente.';
      session.clear();
    } finally {
      submitting = false; session.setLoading(false);
    }
  }
</script>

<svelte:head><title>Iniciar sesión — ERP System</title></svelte:head>

<div class="flex min-h-screen">
  <!-- Hero side -->
  <div class="relative hidden w-1/2 overflow-hidden lg:flex">
    <div class="hero-gradient absolute inset-0 flex flex-col justify-between p-12">
      <!-- Decorative orbs -->
      <div class="absolute right-10 top-10 h-72 w-72 rounded-full bg-white/10 blur-3xl"></div>
      <div class="absolute bottom-10 left-10 h-56 w-56 rounded-full bg-accent/30 blur-2xl"></div>

      <div class="relative z-10 flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15 backdrop-blur-sm">
          <span class="text-lg font-bold text-white">E</span>
        </div>
        <span class="text-base font-semibold text-white">ERP System</span>
      </div>

      <div class="relative z-10">
        <h1 class="text-4xl font-bold leading-tight text-white">
          Gestiona tu empresa<br />con precisión
        </h1>
        <p class="mt-4 max-w-md text-base text-white/80">
          Sistema modular de planificación de recursos empresariales. 
          Acceso seguro, control granular, datos en tiempo real.
        </p>
        <div class="mt-8 flex gap-6">
          <div><p class="text-2xl font-bold text-white">6</p><p class="text-xs text-white/70">Módulos activos</p></div>
          <div><p class="text-2xl font-bold text-white">17</p><p class="text-xs text-white/70">Próximamente</p></div>
          <div><p class="text-2xl font-bold text-white">21</p><p class="text-xs text-white/70">Permisos</p></div>
        </div>
      </div>

      <p class="relative z-10 text-xs text-white/60">© 2026 ERP System · Todos los derechos reservados</p>
    </div>
  </div>

  <!-- Form side -->
  <div class="flex w-full items-center justify-center bg-surface px-6 lg:w-1/2">
    <div class="w-full max-w-sm">
      <div class="mb-8 text-center lg:hidden">
        <div class="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-foreground text-surface">
          <span class="text-lg font-bold">E</span>
        </div>
        <h1 class="text-xl font-bold text-foreground">ERP System</h1>
      </div>

      <h2 class="text-2xl font-bold tracking-tight text-foreground">Bienvenido</h2>
      <p class="mt-1.5 text-sm text-foreground-muted">Ingrese sus credenciales para continuar</p>

      <form class="mt-8 space-y-5" onsubmit={handleSubmit} novalidate>
        {#if errors.form}
          <div class="animate-fade-scale rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">
            {errors.form}
          </div>
        {/if}

        <div>
          <label for="login" class="mb-1.5 block text-sm font-medium text-foreground">Usuario o correo</label>
          <input id="login" type="text" autocomplete="username" bind:value={loginValue}
            class="w-full rounded-xl border border-border bg-surface px-4 py-2.5 text-sm text-foreground placeholder:text-foreground-subtle transition-all focus:border-primary focus:shadow-glow focus:outline-none"
            placeholder="usuario o correo@ejemplo.com"
            aria-invalid={errors.login ? 'true' : undefined}
            disabled={submitting} />
          {#if errors.login}<p class="mt-1 text-xs text-danger">{errors.login}</p>{/if}
        </div>

        <div>
          <label for="password" class="mb-1.5 block text-sm font-medium text-foreground">Contraseña</label>
          <div class="relative">
            <input id="password" type={showPassword ? 'text' : 'password'} autocomplete="current-password" bind:value={passwordValue}
              class="w-full rounded-xl border border-border bg-surface px-4 py-2.5 pr-11 text-sm text-foreground placeholder:text-foreground-subtle transition-all focus:border-primary focus:shadow-glow focus:outline-none"
              placeholder="••••••••••••" aria-invalid={errors.password ? 'true' : undefined} disabled={submitting} />
            <button type="button" onclick={() => (showPassword = !showPassword)}
              class="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-foreground-subtle transition-colors hover:text-foreground" aria-label={showPassword ? 'Ocultar' : 'Mostrar'} tabindex="-1">
              {#if showPassword}
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61M2 2l22 22" /></svg>
              {:else}
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /></svg>
              {/if}
            </button>
          </div>
          {#if errors.password}<p class="mt-1 text-xs text-danger">{errors.password}</p>{/if}
        </div>

        <button type="submit" disabled={submitting}
          class="flex w-full items-center justify-center gap-2 rounded-lg bg-foreground py-2.5 text-sm font-medium text-surface shadow-soft transition-all duration-150 hover:bg-foreground-muted active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none focus-visible:shadow-glow">
          {#if submitting}
            <svg class="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-dasharray="60" stroke-dashoffset="20" /></svg>
            Ingresando...
          {:else}
            Iniciar sesión
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
          {/if}
        </button>
      </form>

      <p class="mt-8 text-center text-xs text-foreground-subtle">
        Acceso restringido a usuarios autorizados · Fase 6
      </p>
    </div>
  </div>
</div>
