<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { HttpError } from '$lib/api/client';
  import LocationFormModal from '$lib/features/locations/components/LocationFormModal.svelte';
  import { getLocation } from '$lib/features/locations/services';
  import type { LocationOut } from '$lib/features/locations/types';
  import { permissions } from '$lib/stores/permissions.svelte';

  let warehouseId = $derived(page.params.id ?? '');
  let locationId = $derived(page.params.locationId ?? '');
  let location = $state<LocationOut | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let loadedKey = $state('');
  let canUpdate = $derived(permissions.hasPermission('locations.update'));

  $effect(() => {
    const key = `${warehouseId}:${locationId}`;
    if (!warehouseId || !locationId || !canUpdate || loadedKey === key) return;
    loadedKey = key;
    void loadLocation(warehouseId, locationId);
  });

  async function loadLocation(requestedWarehouseId: string, requestedLocationId: string) {
    loading = true;
    error = null;
    try {
      const loaded = await getLocation(requestedWarehouseId, requestedLocationId);
      if (`${requestedWarehouseId}:${requestedLocationId}` === `${warehouseId}:${locationId}`) {
        location = loaded;
      }
    } catch (cause) {
      if (cause instanceof HttpError) error = cause.message;
      else error = 'No se pudo cargar la ubicación.';
    } finally {
      if (`${requestedWarehouseId}:${requestedLocationId}` === `${warehouseId}:${locationId}`) {
        loading = false;
      }
    }
  }

  function goBack() {
    void goto(`/warehouses/${warehouseId}/locations`);
  }
</script>

<svelte:head><title>Editar ubicación — GestionaSV</title></svelte:head>

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
      <h1 class="text-xl font-bold text-foreground">Editar ubicación</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Actualice la configuración sin perder la trazabilidad de la ubicación.
      </p>
    </div>
  </header>

  {#if !canUpdate}
    <div role="alert">
      <Card class="p-6">
        <h2 class="text-sm font-semibold text-danger">No tiene permiso para editar ubicaciones</h2>
        <p class="mt-1 text-xs leading-5 text-foreground-muted">
          Solicite el permiso <span class="font-mono">locations.update</span> para continuar.
        </p>
        <div class="mt-4">
          <Button variant="secondary" size="sm" onclick={goBack}>Volver</Button>
        </div>
      </Card>
    </div>
  {:else if loading}
    <div class="h-96 rounded-2xl skeleton" aria-label="Cargando ubicación"></div>
  {:else if error}
    <div role="alert">
      <Card class="p-6">
        <h2 class="text-sm font-semibold text-danger">No se pudo abrir la ubicación</h2>
        <p class="mt-1 text-xs leading-5 text-danger/90">{error}</p>
        <div class="mt-4 flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onclick={() => void loadLocation(warehouseId, locationId)}
          >
            Reintentar
          </Button>
          <Button variant="ghost" size="sm" onclick={goBack}>Volver</Button>
        </div>
      </Card>
    </div>
  {:else if location}
    <LocationFormModal
      open={true}
      inline={true}
      {warehouseId}
      {location}
      canRecode={permissions.hasPermission('locations.recode')}
      canCommission={permissions.hasPermission('locations.commission')}
      canActivate={permissions.hasPermission('locations.activate')}
      canDeactivate={permissions.hasPermission('locations.deactivate')}
      canViewCapacity={permissions.hasPermission('inventory:capacity')}
      onclose={goBack}
      onsaved={() => undefined}
    />
  {/if}
</div>
