<script lang="ts">
  import type { TransferVehicle } from '$lib/features/inventory/transfer-documents';

  type CollectionState = 'loading' | 'loaded' | 'empty' | 'error';
  interface Props {
    vehicles: TransferVehicle[];
    state: CollectionState;
    error: string | null;
    canManageFleet: boolean;
  }

  let { vehicles, state, error, canManageFleet }: Props = $props();
</script>

<section class="space-y-5" aria-labelledby="vehicles-heading">
  <header class="flex flex-wrap items-start justify-between gap-3">
    <div>
      <h2 id="vehicles-heading" class="text-lg font-semibold text-foreground">
        Vehículos de traslado
      </h2>
      <p class="mt-1 text-sm text-foreground-muted">
        Los vehículos se registran y administran en Flota. Cada uno tiene una ubicación móvil para
        el inventario en tránsito.
      </p>
    </div>
    {#if canManageFleet}
      <a
        class="inline-flex items-center rounded-xl border border-border bg-surface px-3 py-2 text-sm font-medium text-primary hover:bg-surface-hover"
        href="/fleet">Administrar en Flota</a
      >
    {/if}
  </header>

  {#if error}<p
      class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </p>{/if}

  {#if state === 'loading'}
    <p
      class="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted"
      role="status"
    >
      Consultando vehículos…
    </p>
  {:else if state === 'error'}
    <p
      class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      No se pudo consultar el catálogo. La recepción en sucursal sigue disponible desde Documentos.
    </p>
  {:else if state === 'empty'}
    <p
      class="rounded-xl border border-dashed border-border bg-surface p-7 text-sm text-foreground-muted"
    >
      No hay vehículos de traslado en tus sucursales. Regístralos en Flota.
    </p>
  {:else}
    <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {#each vehicles as vehicle (vehicle.id)}
        <article class="rounded-2xl border border-border bg-surface p-4">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="font-mono text-sm font-semibold text-primary">{vehicle.code}</p>
              <h3 class="mt-1 font-medium text-foreground">
                {vehicle.plate ? `${vehicle.plate} · ` : ''}{vehicle.name}
              </h3>
            </div>
            <span
              class="inline-flex rounded-full border px-2.5 py-1 text-xs font-medium {vehicle.status ===
              'active'
                ? 'border-success/30 bg-success/10 text-success'
                : 'border-border bg-surface-muted text-foreground-muted'}"
              data-status={vehicle.status}
              >{vehicle.status === 'active' ? 'Activo' : 'Inactivo'}</span
            >
          </div>
          <p class="mt-3 text-xs text-foreground-muted">
            {vehicle.branch_name ? `${vehicle.branch_name} · ` : ''}Ubicación móvil: {vehicle.transit_warehouse_name}
          </p>
          {#if vehicle.fleet_vehicle_id}
            <a
              class="mt-3 inline-block text-xs font-medium text-primary"
              href={`/fleet/${vehicle.fleet_vehicle_id}`}>Ver ficha del vehículo</a
            >
          {/if}
        </article>
      {/each}
    </div>
  {/if}
</section>
