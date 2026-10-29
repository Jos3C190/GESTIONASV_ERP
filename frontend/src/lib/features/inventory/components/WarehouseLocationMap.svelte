<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { listLocations } from '$lib/features/locations/services';
  import type { LocationOut } from '$lib/features/locations/types';
  import { inventoryApi } from '../services';
  import type { CapacitySummary } from '../types';
  import { workspaceField } from '../workspace';
  import WarehouseStockPanel from './WarehouseStockPanel.svelte';
  import { formatMovementQuantity as qty } from '../movement-presentation';
  let { warehouseId, initialLocationId = '' }: { warehouseId: string; initialLocationId?: string } =
    $props();
  let query = $state('');
  let applied = $state('');
  let page = $state(1);
  let revision = $state(0);
  let locations = $state<LocationOut[]>([]);
  let pages = $state(1);
  let total = $state(0);
  let selected = $state<LocationOut | null>(null);
  let loading = $state(true);
  let error = $state('');
  let capacity = $state<CapacitySummary | null>(null);
  let capacityError = $state('');
  let capacityLoading = $state(false);
  const groups = $derived([...new Set(locations.map((row) => row.aisle))]);
  $effect(() => {
    const warehouse = warehouseId;
    const number = page;
    const search = applied;
    void revision;
    let active = true;
    loading = true;
    error = '';
    locations = [];
    selected = null;
    listLocations(warehouse, { page: number, size: 48, search, is_active: true })
      .then((data) => {
        if (active) {
          locations = data.items;
          total = data.meta.total;
          pages = data.meta.pages;
          selected = data.items.find((row) => row.id === initialLocationId) ?? null;
        }
      })
      .catch((cause) => {
        if (active)
          error =
            cause instanceof Error ? cause.message : 'No se pudieron consultar las ubicaciones.';
      })
      .finally(() => {
        if (active) loading = false;
      });
    return () => {
      active = false;
    };
  });
  $effect(() => {
    const id = selected?.id;
    const warehouse = warehouseId;
    let active = true;
    capacity = null;
    capacityError = '';
    capacityLoading = Boolean(id);
    if (id)
      inventoryApi
        .getCapacitySummary(warehouse, id)
        .then((data) => {
          if (active) capacity = data;
        })
        .catch(() => {
          if (active) capacityError = 'No se pudo consultar la capacidad de este espacio.';
        })
        .finally(() => {
          if (active) capacityLoading = false;
        });
    return () => {
      active = false;
    };
  });
</script>

<section class="space-y-4" aria-label="Mapa de ubicaciones">
  <div class="rounded-xl border border-border bg-surface p-4 sm:p-5">
    <h3 class="font-semibold">Ubicaciones de la bodega</h3>
    <p class="mt-1 text-sm text-foreground-muted">
      Esquema por pasillo. Selecciona un espacio para consultar su contenido y capacidad; el esquema
      no representa distancias reales.
    </p>
    <form
      class="my-4 flex flex-wrap items-end gap-3"
      onsubmit={(event) => {
        event.preventDefault();
        applied = query.trim();
        page = 1;
        revision += 1;
      }}
    >
      <label class="min-w-0 flex-1 text-sm text-foreground-muted"
        >Código de ubicación<input
          class={workspaceField}
          bind:value={query}
          placeholder="Ej. A02-R01-N01-P01"
        /></label
      ><Button type="submit" disabled={loading}>Buscar ubicación</Button>
    </form>
    {#if loading}<div
        role="status"
        aria-label="Consultando ubicaciones"
        class="skeleton h-40 rounded-lg"
      ></div>
    {:else if error}<div role="alert" class="rounded-lg border border-danger/30 bg-danger/10 p-4">
        <p>{error}</p>
        <Button class="mt-3" variant="secondary" onclick={() => (revision += 1)}>Reintentar</Button>
      </div>
    {:else if !locations.length}<div
        class="rounded-lg border border-dashed border-border p-8 text-center"
      >
        <p class="font-medium">No hay ubicaciones para esta consulta</p>
        <Button
          class="mt-4"
          variant="secondary"
          onclick={() => {
            query = '';
            applied = '';
            page = 1;
            revision += 1;
          }}>Mostrar todas</Button
        >
      </div>
    {:else}<div class="space-y-5">
        {#each groups as aisle (aisle)}<section aria-label={`Pasillo ${aisle}`}>
            <h4 class="mb-2 text-sm font-semibold text-foreground-muted">
              Pasillo {aisle || 'sin asignar'}
            </h4>
            <div
              class="grid grid-cols-1 gap-2 min-[420px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
            >
              {#each locations.filter((row) => row.aisle === aisle) as location (location.id)}<button
                  type="button"
                  aria-pressed={selected?.id === location.id}
                  class="min-w-0 rounded-lg border p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary {selected?.id ===
                  location.id
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:bg-surface-hover'}"
                  onclick={() => (selected = location)}
                  ><span class="block break-all font-mono text-sm font-semibold"
                    >{location.code}</span
                  ><span class="mt-2 grid grid-cols-3 gap-2 text-xs text-foreground-muted"
                    ><span
                      >Estante<br /><strong class="text-foreground">{location.rack}</strong></span
                    ><span
                      >Nivel<br /><strong class="text-foreground">{location.level}</strong></span
                    ><span
                      >Posición<br /><strong class="text-foreground">{location.position}</strong
                      ></span
                    ></span
                  ><span class="mt-2 block text-xs text-foreground-muted"
                    >{location.storage_eligible ? 'Almacenamiento' : 'Zona operativa'} · {location.lifecycle_status ===
                    'active'
                      ? 'Activa'
                      : 'Restringida'}</span
                  ></button
                >{/each}
            </div>
          </section>{/each}
      </div>
      <div
        class="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-foreground-muted"
      >
        <p>{total} espacios · Página {page} de {pages}</p>
        <div class="flex gap-2">
          <Button variant="secondary" disabled={page <= 1} onclick={() => (page -= 1)}
            >Anterior</Button
          ><Button variant="secondary" disabled={page >= pages} onclick={() => (page += 1)}
            >Siguiente</Button
          >
        </div>
      </div>{/if}
  </div>
  {#if selected}<section
      class="rounded-xl border border-primary/30 bg-surface p-4 sm:p-5"
      aria-label="Espacio seleccionado"
    >
      <h3 class="font-semibold">{selected.code}</h3>
      <p class="mt-1 text-sm text-foreground-muted">
        Pasillo {selected.aisle} · Estante {selected.rack} · Nivel {selected.level} · Posición {selected.position}
      </p>
      {#if capacityLoading}<p role="status" class="mt-3 text-sm text-foreground-muted">
          Consultando capacidad…
        </p>{:else if capacityError}<p role="alert" class="mt-3 text-sm">
          {capacityError}
        </p>{:else if capacity}<dl class="mt-4 grid gap-4 sm:grid-cols-2">
          {#each [{ label: 'Peso ocupado / límite operativo', metric: capacity.weight, unit: 'kg' }, { label: 'Volumen ocupado / límite operativo', metric: capacity.volume, unit: 'm³' }] as item}<div
            >
              <dt class="text-sm text-foreground-muted">{item.label}</dt>
              <dd class="mt-1 font-semibold tabular-nums">
                {item.metric.occupied == null ? 'Sin medir' : qty(item.metric.occupied)} / {item
                  .metric.operational == null
                  ? 'Sin configurar'
                  : qty(item.metric.operational)}
                {item.unit}
              </dd>
            </div>{/each}
        </dl>
        {#if capacity.measurementStatus !== 'complete'}<p
            class="mt-3 text-sm text-foreground-muted"
          >
            Hay medidas pendientes; la ocupación no está completamente verificada.
          </p>{/if}{/if}
    </section>
    {#key selected.id}<WarehouseStockPanel {warehouseId} locationId={selected.id} />{/key}
  {:else if !loading && !error && locations.length}<p
      class="rounded-lg border border-dashed border-border p-5 text-sm text-foreground-muted"
    >
      Selecciona un espacio para ver qué contiene.
    </p>{/if}
</section>
