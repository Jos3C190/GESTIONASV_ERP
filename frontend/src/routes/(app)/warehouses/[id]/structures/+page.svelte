<script lang="ts">
  import { page } from '$app/state';
  import { getWarehouse } from '$lib/services/warehouses';
  import { permissions } from '$lib/stores/permissions.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import WarehouseCapacityGroupsPanel from '$lib/features/warehouses/components/WarehouseCapacityGroupsPanel.svelte';
  import type { Warehouse } from '$lib/features/warehouses/types';

  let warehouse = $state<Warehouse | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let loadedWarehouseId = $state('');

  let warehouseId = $derived(page.params.id ?? '');

  $effect(() => {
    if (!warehouseId || loadedWarehouseId === warehouseId) return;
    loadedWarehouseId = warehouseId;
    void loadWarehouse(warehouseId);
  });

  async function loadWarehouse(requestedWarehouseId = warehouseId) {
    loading = true;
    error = null;
    try {
      const loaded = await getWarehouse(requestedWarehouseId);
      if (requestedWarehouseId === warehouseId) warehouse = loaded;
    } catch (cause) {
      if (requestedWarehouseId === warehouseId) {
        error = cause instanceof Error ? cause.message : 'No se pudo cargar el almacén.';
      }
    } finally {
      if (requestedWarehouseId === warehouseId) loading = false;
    }
  }
</script>

<svelte:head>
  <title
    >{warehouse ? `Estructuras · ${warehouse.name}` : 'Estructuras y límites compartidos'} — GestionaSV</title
  >
</svelte:head>

<div class="space-y-5 p-6 md:p-8">
  <header class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
    <div class="flex min-w-0 items-start gap-3">
      <a
        href={`/warehouses/${warehouseId}`}
        class="flex h-8 w-8 flex-none items-center justify-center rounded-md text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        aria-label="Volver al detalle del almacén"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"><path d="M19 12H5m7 7-7-7 7-7" /></svg
        >
      </a>
      <div class="min-w-0">
        <h1 class="text-xl font-bold text-foreground">Estructuras y límites compartidos</h1>
        <p class="mt-1 text-sm text-foreground-muted">
          {#if loading}
            Cargando almacén…
          {:else if warehouse}
            {warehouse.name} · {warehouse.code} · {warehouse.branchName}
          {:else}
            Administre la jerarquía física del almacén.
          {/if}
        </p>
      </div>
    </div>
  </header>

  {#if loading}
    <div class="space-y-3" aria-label="Cargando estructuras y límites">
      <div class="h-28 rounded-2xl skeleton"></div>
      <div class="h-64 rounded-2xl skeleton"></div>
    </div>
  {:else if error}
    <div
      class="flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <p class="text-sm text-danger">{error}</p>
      <Button variant="secondary" size="sm" onclick={() => void loadWarehouse()}>Reintentar</Button>
    </div>
  {:else if warehouse}
    <WarehouseCapacityGroupsPanel
      warehouseId={warehouse.id}
      {warehouse}
      canManage={permissions.hasPermission('warehouses.update')}
      canViewLocations={permissions.hasPermission('locations.view')}
    />
  {/if}
</div>
