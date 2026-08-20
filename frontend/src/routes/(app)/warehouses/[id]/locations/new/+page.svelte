<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import LocationFormModal from '$lib/features/locations/components/LocationFormModal.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  let warehouseId = $derived(page.params.id ?? '');
  let canCreate = $derived(permissions.hasPermission('locations.create'));

  function goBack() {
    void goto(`/warehouses/${warehouseId}/locations`);
  }
</script>

<svelte:head><title>Nueva ubicación — GestionaSV</title></svelte:head>

<div class="space-y-5 p-6 md:p-8">
  <header class="flex items-start gap-3">
    <a
      href={`/warehouses/${warehouseId}/locations`}
      class="flex h-8 w-8 flex-none items-center justify-center rounded-md text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
      aria-label="Volver a ubicaciones"
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
    <div>
      <h1 class="text-xl font-bold text-foreground">Nueva ubicación</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Configure la ruta física, la estructura compartida, la capacidad y los datos operativos.
      </p>
    </div>
  </header>

  {#if canCreate}
    <LocationFormModal
      open={true}
      inline={true}
      {warehouseId}
      canRecode={permissions.hasPermission('locations.recode')}
      canCommission={permissions.hasPermission('locations.commission')}
      canActivate={permissions.hasPermission('locations.activate')}
      canDeactivate={permissions.hasPermission('locations.deactivate')}
      canViewCapacity={permissions.hasPermission('inventory:capacity')}
      onclose={goBack}
      onsaved={() => undefined}
    />
  {:else}
    <div role="alert">
      <Card class="p-6">
        <h2 class="text-sm font-semibold text-danger">No tiene permiso para crear ubicaciones</h2>
        <p class="mt-1 text-xs leading-5 text-foreground-muted">
          Solicite el permiso <span class="font-mono">locations.create</span> para continuar.
        </p>
        <div class="mt-4">
          <Button variant="secondary" size="sm" onclick={goBack}>Volver</Button>
        </div>
      </Card>
    </div>
  {/if}
</div>
