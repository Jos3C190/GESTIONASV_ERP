<script lang="ts">
  import { page } from '$app/state';
  import { HttpError } from '$lib/api/client';
  import { fleetApi, type FleetVehicle } from '$lib/features/fleet/api';
  import VehicleForm from '$lib/features/fleet/VehicleForm.svelte';

  let vehicle = $state<FleetVehicle | null>(null);
  let error = $state<string | null>(null);

  $effect(() => {
    const id = page.params.id ?? '';
    fleetApi
      .get(id)
      .then((result) => (vehicle = result))
      .catch((err) => {
        error = err instanceof HttpError ? err.message : 'No se pudo cargar el vehículo.';
      });
  });
</script>

<svelte:head><title>Editar vehículo — GestionaSV</title></svelte:head>

<div class="page">
  <a class="back" href={`/fleet/${page.params.id}`}>← Ficha del vehículo</a>
  <h1>Editar {vehicle?.code ?? 'vehículo'}</h1>
  {#if error}
    <p class="error" role="alert">{error}</p>
  {:else if vehicle}
    <VehicleForm mode="edit" {vehicle} />
  {:else}
    <p class="muted">Cargando…</p>
  {/if}
</div>

<style>
  .page {
    max-width: 1200px;
    margin: 0 auto;
  }
  .back,
  .muted {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  h1 {
    margin: 8px 0 18px;
    font-size: 26px;
    font-weight: 650;
    letter-spacing: -0.8px;
  }
  .error {
    color: rgb(var(--danger));
    font-size: 13px;
  }
</style>
