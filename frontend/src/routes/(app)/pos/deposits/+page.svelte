<script lang="ts">
  import DepositsPage from '#lib/features/pos/DepositsPage.svelte';
  import { permissions } from '#lib/stores/permissions.svelte.ts';

  const allowed = $derived(permissions.hasPermission('pos:deposits'));
</script>

<svelte:head>
  <title>Depósitos | GestionaSV</title>
</svelte:head>

{#if !allowed}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para registrar depósitos.
  </div>
{:else}
  <div class="space-y-5">
    <header>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Punto de venta</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">
        Depósitos
      </h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        Registra el depósito bancario del efectivo de los turnos cerrados, con su boleta.
      </p>
    </header>
    <DepositsPage />
  </div>
{/if}
