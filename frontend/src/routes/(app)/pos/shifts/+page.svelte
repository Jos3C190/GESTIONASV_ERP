<script lang="ts">
  import ShiftsPage from '#lib/features/pos/ShiftsPage.svelte';
  import { permissions } from '#lib/stores/permissions.svelte.ts';

  const allowed = $derived(permissions.hasAnyPermission(['pos:supervise', 'pos:reports']));
</script>

<svelte:head>
  <title>Turnos de caja | GestionaSV</title>
</svelte:head>

{#if !allowed}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para revisar turnos de caja.
  </div>
{:else}
  <div class="space-y-5">
    <header>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Punto de venta</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">
        Turnos de caja
      </h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        Revisa los conteos que entregan los cajeros: compara lo esperado con lo contado, aprueba el
        cierre o pide recontar.
      </p>
    </header>
    <ShiftsPage />
  </div>
{/if}
