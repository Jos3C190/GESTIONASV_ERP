<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { workspaceApi, workspaceField, type StockPage } from '../workspace';
  import { formatMovementQuantity as quantity, stockStatusLabel } from '../movement-presentation';
  import { physicalKardexHref } from '../kardex';
  let {
    warehouseId,
    locationId = '',
    onlocation
  }: { warehouseId: string; locationId?: string; onlocation?: (id: string) => void } = $props();
  let query = $state('');
  let status = $state('');
  let applied = $state({ q: '', stock_status: '' });
  let page = $state(1);
  let revision = $state(0);
  let result = $state<StockPage | null>(null);
  let loading = $state(true);
  let error = $state('');
  $effect(() => {
    const controller = new AbortController();
    let active = true;
    const warehouse = warehouseId;
    const location = locationId;
    const filters = applied;
    const number = page;
    void revision;
    loading = true;
    error = '';
    result = null;
    workspaceApi
      .stock(warehouse, { ...filters, page: number, location_id: location }, controller.signal)
      .then((data) => {
        if (active) result = data;
      })
      .catch((cause) => {
        if (active)
          error =
            cause instanceof Error ? cause.message : 'No se pudieron consultar las existencias.';
      })
      .finally(() => {
        if (active) loading = false;
      });
    return () => {
      active = false;
      controller.abort();
    };
  });
</script>

<section
  class="overflow-hidden rounded-xl border border-border bg-surface"
  aria-label="Existencias por ubicación"
>
  <div class="border-b border-border p-4 sm:p-5">
    <h3 class="font-semibold text-foreground">
      {locationId ? 'Contenido del espacio' : 'Existencias por ubicación'}
    </h3>
    <p class="mt-1 text-sm text-foreground-muted">
      Cantidades registradas en inventario. Cada fila conserva su unidad; las unidades en
      preparación se consultan aparte.
    </p>
    <form
      class="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_180px_auto]"
      onsubmit={(event) => {
        event.preventDefault();
        page = 1;
        applied = { q: query.trim(), stock_status: status };
        revision += 1;
      }}
    >
      <label class="text-sm text-foreground-muted"
        >Producto, código o lote<input
          class={workspaceField}
          bind:value={query}
          maxlength="120"
          placeholder="Ej. Azúcar o PRD-AZU-004"
        /></label
      >
      <label class="text-sm text-foreground-muted"
        >Estado<select class={workspaceField} bind:value={status}
          ><option value="">Todos</option
          >{#each ['available', 'quarantine', 'blocked', 'damaged', 'in_transit'] as value}<option
              {value}>{stockStatusLabel(value)}</option
            >{/each}</select
        ></label
      >
      <Button type="submit" class="self-end" disabled={loading}>Consultar</Button>
    </form>
  </div>
  {#if loading}<div role="status" aria-label="Consultando existencias" class="space-y-3 p-5">
      <div class="skeleton h-12 rounded-lg"></div>
      <div class="skeleton h-12 rounded-lg"></div>
    </div>
  {:else if error}<div role="alert" class="m-4 rounded-lg border border-danger/30 bg-danger/10 p-4">
      <p>{error}</p>
      <Button class="mt-3" variant="secondary" onclick={() => (revision += 1)}>Reintentar</Button>
    </div>
  {:else if !result?.items.length}<div class="p-8 text-center">
      <p class="font-medium text-foreground">Sin existencias para esta consulta</p>
      <p class="mt-2 text-sm text-foreground-muted">
        Prueba con otro producto o estado. No se incluyen cantidades cero.
      </p>
      <Button
        class="mt-4"
        variant="secondary"
        onclick={() => {
          query = '';
          status = '';
          applied = { q: '', stock_status: '' };
          page = 1;
          revision += 1;
        }}>Limpiar filtros</Button
      >
    </div>
  {:else}
    <ul class="divide-y divide-border">
      {#each result.items as row, index (`${row.inventory_item_id}:${row.location_id}:${row.stock_status}:${index}`)}
        <li class="grid gap-3 p-4 sm:p-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_auto]">
          <div class="min-w-0">
            <p class="font-semibold text-foreground">{row.product_name}</p>
            <p class="mt-1 font-mono text-xs text-foreground-muted">
              {row.sku ?? 'Código no disponible'}
            </p>
            <p class="mt-2 text-sm text-foreground-muted break-all">
              Lote: {row.lot_code ?? 'Sin lote de fabricante'}
            </p>
            {#if row.expiry_date}<p class="text-sm text-foreground-muted">
                Vencimiento: {row.expiry_date.split('-').reverse().join('/')}
              </p>{/if}
          </div>
          <div>
            <p class="text-lg font-semibold tabular-nums text-foreground">
              {quantity(row.quantity_base)}
              <span class="text-sm font-normal">{row.base_unit_symbol}</span>
            </p>
            <p class="mt-1 text-sm text-foreground-muted">{stockStatusLabel(row.stock_status)}</p>
            {#if onlocation}<button
                type="button"
                class="mt-2 rounded text-sm text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                onclick={() => onlocation?.(row.location_id)}>{row.location_code}</button
              >{:else}<p class="mt-2 font-mono text-sm text-foreground">{row.location_code}</p>{/if}
          </div>
          <a
            class="self-center justify-self-start rounded-lg border border-border px-4 py-2.5 text-sm text-foreground hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            href={physicalKardexHref(warehouseId, row.inventory_item_id)}>Ver movimientos</a
          >
        </li>
      {/each}
    </ul>
    <div
      class="flex flex-wrap items-center justify-between gap-3 border-t border-border p-4 text-sm text-foreground-muted"
    >
      <p>{result.total} registros · Página {page} de {Math.max(1, Math.ceil(result.total / 25))}</p>
      <div class="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onclick={() => (page -= 1)}
          >Anterior</Button
        ><Button
          variant="secondary"
          disabled={page * 25 >= result!.total}
          onclick={() => (page += 1)}>Siguiente</Button
        >
      </div>
    </div>
  {/if}
</section>
