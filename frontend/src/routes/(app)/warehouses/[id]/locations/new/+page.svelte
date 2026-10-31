<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Callout from '$lib/components/ui/Callout.svelte';
  import LocationFormModal from '$lib/features/locations/components/LocationFormModal.svelte';
  import LocationCodeSchemeModal from '$lib/features/locations/components/LocationCodeSchemeModal.svelte';
  import { HttpError } from '$lib/api/client';
  import { getOptionalLocationCodeScheme } from '$lib/features/locations/services';
  import type { LocationCodeScheme, LocationOut } from '$lib/features/locations/types';
  import { permissions } from '$lib/stores/permissions.svelte';

  let warehouseId = $derived(page.params.id ?? '');
  let canCreate = $derived(permissions.hasPermission('locations.create'));
  let canManageScheme = $derived(permissions.hasPermission('locations.scheme'));
  let scheme = $state<LocationCodeScheme | null>(null);
  let schemeLoading = $state(true);
  let schemeError = $state<string | null>(null);
  let schemeOpen = $state(false);
  let savedLocation = $state<LocationOut | null>(null);

  async function loadScheme() {
    schemeLoading = true;
    schemeError = null;
    try {
      scheme = await getOptionalLocationCodeScheme(warehouseId);
    } catch (cause) {
      schemeError =
        cause instanceof HttpError
          ? cause.message
          : 'No se pudo comprobar el formato de códigos de este almacén.';
    } finally {
      schemeLoading = false;
    }
  }

  function goBack() {
    void goto(`/warehouses/${warehouseId}`);
  }

  function closeForm() {
    if (!savedLocation) goBack();
  }

  onMount(() => {
    void loadScheme();
  });
</script>

<svelte:head><title>Nueva ubicación — GestionaSV</title></svelte:head>

<div class="space-y-5 p-6 md:p-8">
  <header class="flex items-start gap-3">
    <a
      href={`/warehouses/${warehouseId}`}
      class="flex h-8 w-8 flex-none items-center justify-center rounded-md text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
      aria-label="Volver al almacén"
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
        Configure el punto de recepción, la ruta y sus datos operativos.
      </p>
    </div>
  </header>

  {#if savedLocation}
    <Callout variant="success" dismissible={false}>
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p class="font-semibold text-foreground">Ubicación creada en BM-001</p>
          <p class="mt-1 text-sm text-foreground-muted">
            {savedLocation.code} · {savedLocation.area ?? 'Sin área'} · activa
          </p>
          <p class="mt-1 text-xs text-foreground-muted">
            Puedes verla en la ficha del almacén. La creación no registra existencias ni
            movimientos.
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onclick={goBack}>Ver BM-001</Button>
          <Button
            size="sm"
            onclick={() => {
              savedLocation = null;
            }}>Crear otra ubicación</Button
          >
        </div>
      </div>
    </Callout>
  {:else if canCreate && schemeLoading}
    <div role="status" aria-label="Comprobando esquema de códigos">
      <Card class="p-6 text-sm text-foreground-muted">
        Comprobando el esquema de códigos del almacén…
      </Card>
    </div>
  {:else if canCreate && schemeError}
    <div
      class="flex flex-col gap-3 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{schemeError} No abriré la configuración hasta confirmar el estado.</span>
      <Button variant="secondary" size="sm" onclick={() => void loadScheme()}>Reintentar</Button>
    </div>
  {:else if canCreate && !scheme}
    <Card class="space-y-4 p-6">
      <div>
        <h2 class="text-base font-semibold text-foreground">Falta el formato de códigos</h2>
        <p class="mt-1 text-sm text-foreground-muted">
          Este almacén todavía no tiene un esquema para generar la ruta de la ubicación. Configúralo
          una sola vez y luego registra la recepción.
        </p>
      </div>
      {#if canManageScheme}
        <Button onclick={() => (schemeOpen = true)}>Configurar códigos del almacén</Button>
      {:else}
        <p class="text-sm text-warning">
          Solicita el permiso para configurar códigos de ubicación.
        </p>
      {/if}
    </Card>
  {:else if canCreate}
    <LocationFormModal
      open={true}
      inline={true}
      {warehouseId}
      canRecode={permissions.hasPermission('locations.recode')}
      canCommission={permissions.hasPermission('locations.commission')}
      canActivate={permissions.hasPermission('locations.activate')}
      canDeactivate={permissions.hasPermission('locations.deactivate')}
      canViewCapacity={permissions.hasPermission('inventory:capacity')}
      onclose={closeForm}
      onsaved={(location) => {
        savedLocation = location;
      }}
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

{#if canManageScheme && !scheme && !schemeLoading && !schemeError}
  <LocationCodeSchemeModal
    open={schemeOpen}
    {warehouseId}
    {scheme}
    onclose={() => (schemeOpen = false)}
    onsaved={(nextScheme) => {
      scheme = nextScheme;
    }}
  />
{/if}
