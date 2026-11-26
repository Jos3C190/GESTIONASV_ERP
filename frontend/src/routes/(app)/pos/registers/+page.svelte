<script lang="ts">
  import RegistersPage from '#lib/features/pos/RegistersPage.svelte';
  import { permissions } from '#lib/stores/permissions.svelte.ts';

  const allowed = $derived(permissions.hasPermission('pos:registers_manage'));
</script>

<svelte:head>
  <title>Cajas | GestionaSV</title>
</svelte:head>

{#if !allowed}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para configurar cajas.
  </div>
{:else}
  <div class="space-y-5">
    <header>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Punto de venta</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">Cajas</h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        Cada caja usa un punto de venta de la configuración fiscal y define su fondo y sus topes de
        efectivo.
      </p>
    </header>
    <RegistersPage />
  </div>
{/if}
