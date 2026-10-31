<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { HttpError } from '$lib/api/client';
  import BatchGeneratorModal from '$lib/features/locations/components/BatchGeneratorModal.svelte';
  import { getLocationCodeScheme } from '$lib/features/locations/services';
  import type { LocationCodeScheme } from '$lib/features/locations/types';
  import { permissions } from '$lib/stores/permissions.svelte';

  let warehouseId = $derived(page.params.id ?? '');
  let canGenerate = $derived(permissions.hasPermission('locations.bulk'));
  let scheme = $state<LocationCodeScheme | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let loadedWarehouseId = $state('');

  $effect(() => {
    if (!warehouseId || !canGenerate || loadedWarehouseId === warehouseId) return;
    loadedWarehouseId = warehouseId;
    void loadScheme(warehouseId);
  });

  async function loadScheme(requestedWarehouseId = warehouseId) {
    loading = true;
    error = null;
    try {
      scheme = await getLocationCodeScheme(requestedWarehouseId);
    } catch (cause) {
      if (cause instanceof HttpError && cause.status === 404) scheme = null;
      else
        error =
          cause instanceof HttpError ? cause.message : 'No se pudo cargar el esquema de códigos.';
    } finally {
      loading = false;
    }
  }

  function goBack() {
    void goto(`/warehouses/${warehouseId}/locations`);
  }
</script>

<svelte:head><title>Generar ubicaciones por rangos — GestionaSV</title></svelte:head>

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
      <h1 class="text-xl font-bold text-foreground">Generar ubicaciones por rangos</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Diseñe la matriz, revise el impacto y publique el lote en pasos separados.
      </p>
    </div>
  </header>

  {#if !canGenerate}
    <div role="alert">
      <Card class="p-6">
        <h2 class="text-sm font-semibold text-danger">No tiene permiso para generar ubicaciones</h2>
        <p class="mt-1 text-xs leading-5 text-foreground-muted">
          Solicite el permiso <span class="font-mono">locations.bulk</span> para continuar.
        </p>
        <div class="mt-4">
          <Button variant="secondary" size="sm" onclick={goBack}>Volver</Button>
        </div>
      </Card>
    </div>
  {:else if loading}
    <div class="h-96 rounded-2xl skeleton" aria-label="Cargando generador"></div>
  {:else if error}
    <div role="alert">
      <Card class="p-6">
        <h2 class="text-sm font-semibold text-danger">No se pudo preparar el generador</h2>
        <p class="mt-1 text-xs leading-5 text-danger/90">{error}</p>
        <div class="mt-4 flex gap-2">
          <Button variant="secondary" size="sm" onclick={() => void loadScheme()}>Reintentar</Button
          >
          <Button variant="ghost" size="sm" onclick={goBack}>Volver</Button>
        </div>
      </Card>
    </div>
  {:else}
    <BatchGeneratorModal
      open={true}
      inline={true}
      {warehouseId}
      {scheme}
      hasPermission={(code) => permissions.hasPermission(code)}
      onclose={goBack}
      onpublished={() => undefined}
    />
  {/if}
</div>
