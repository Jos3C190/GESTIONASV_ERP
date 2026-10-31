<script lang="ts">
  import { onDestroy } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { inventoryApi } from '../services';
  import type { InventoryMovementHistory, WarehouseMovementFilters } from '../types';
  import { localMovementDate, localMovementPeriod, movementDirection } from '../movement-history';
  import { formatMovementQuantity, movementTypeLabel } from '../movement-presentation';
  import MovementDetailsModal from './MovementDetailsModal.svelte';

  let { warehouseId, contextKey = '' }: { warehouseId: string; contextKey?: string } = $props();
  const initial = localMovementPeriod(30);
  const size = 25;
  const field =
    'mt-1 min-h-11 w-full rounded-lg border border-border-control bg-surface px-3 py-2 text-sm text-foreground placeholder:text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary';
  const movementTypes = [
    'opening',
    'receipt',
    'putaway',
    'transfer',
    'pick',
    'shipment',
    'adjustment_in',
    'adjustment_out',
    'reversal'
  ];
  let from = $state(initial.period_from);
  let to = $state(initial.period_to);
  let search = $state('');
  let lot = $state('');
  let reference = $state('');
  let type = $state('');
  let direction = $state<WarehouseMovementFilters['direction']>('');
  let applied = $state<WarehouseMovementFilters & { movement_type?: string }>({ ...initial });
  let offset = $state(0);
  let revision = $state(0);
  let rows = $state<InventoryMovementHistory[]>([]);
  let hasNext = $state(false);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let formError = $state<string | null>(null);
  let selected = $state<InventoryMovementHistory | null>(null);
  let sequence = 0;
  const appliedLabels = $derived(
    [
      applied.q ? `Producto: ${applied.q}` : '',
      applied.movement_type ? `Tipo: ${movementTypeLabel(applied.movement_type).label}` : '',
      applied.direction
        ? `Sentido: ${{ incoming: 'Entradas', outgoing: 'Salidas', internal: 'Dentro de esta bodega' }[applied.direction]}`
        : '',
      applied.lot_code ? `Lote: ${applied.lot_code}` : '',
      applied.source_reference ? `Referencia: ${applied.source_reference}` : ''
    ].filter(Boolean)
  );

  function isPreset(days: number) {
    const period = localMovementPeriod(days);
    return applied.period_from === period.period_from && applied.period_to === period.period_to;
  }

  function apply() {
    if (from && to && from > to) {
      formError = 'La fecha Desde debe ser anterior o igual a Hasta.';
      document.getElementById('movement-from')?.focus();
      return;
    }
    formError = null;
    offset = 0;
    applied = {
      period_from: from,
      period_to: to,
      q: search.trim(),
      lot_code: lot.trim(),
      source_reference: reference.trim(),
      direction,
      movement_type: type || undefined
    };
    revision += 1;
  }
  function preset(days: number) {
    const period = localMovementPeriod(days);
    from = period.period_from;
    to = period.period_to;
    apply();
  }
  function clear() {
    from = '';
    to = '';
    search = '';
    lot = '';
    reference = '';
    type = '';
    direction = '';
    apply();
  }
  $effect(() => {
    const warehouse = warehouseId;
    void contextKey;
    const { movement_type, ...filters } = applied;
    const pageOffset = offset;
    void revision;
    const request = ++sequence;
    const controller = new AbortController();
    rows = [];
    selected = null;
    error = null;
    hasNext = false;
    loading = true;
    void inventoryApi
      .listWarehouseMovements(
        warehouse,
        size + 1,
        movement_type,
        pageOffset,
        filters,
        controller.signal
      )
      .then((result) => {
        if (request !== sequence) return;
        rows = result.slice(0, size);
        hasNext = result.length > size;
      })
      .catch((cause) => {
        if (request === sequence && !controller.signal.aborted)
          error =
            cause instanceof Error ? cause.message : 'No se pudieron consultar los movimientos.';
      })
      .finally(() => {
        if (request === sequence) loading = false;
      });
    return () => {
      sequence += 1;
      controller.abort();
    };
  });
  onDestroy(() => {
    sequence += 1;
  });

  function pageTo(next: number) {
    offset = next;
    document.getElementById('warehouse-movements-heading')?.focus();
  }
</script>

<section
  class="overflow-hidden rounded-xl border border-border bg-surface"
  aria-labelledby="warehouse-movements-heading"
>
  <header class="border-b border-border p-4 sm:p-5">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3
          id="warehouse-movements-heading"
          tabindex="-1"
          class="rounded text-base font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          Movimientos de esta bodega
        </h3>
        <p class="mt-1 max-w-2xl text-sm leading-6 text-foreground-muted">
          Consulta entradas, salidas y cambios de ubicación. El historial es de solo lectura.
        </p>
      </div>
      <span class="rounded-md border border-border px-2 py-1 text-xs text-foreground-muted"
        >Hora de El Salvador</span
      >
    </div>
    <form
      class="mt-5 space-y-3"
      onsubmit={(event) => {
        event.preventDefault();
        apply();
      }}
    >
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label class="text-sm font-medium text-foreground sm:col-span-2"
          >Producto, SKU o unidad
          <input
            class={field}
            type="search"
            placeholder="Ej. Chocolate, PRD-CHO-006 o HU-…"
            maxlength="120"
            bind:value={search}
          />
        </label>
        <label class="text-sm font-medium text-foreground" for="movement-from"
          >Desde
          <input
            id="movement-from"
            class={field}
            type="date"
            bind:value={from}
            aria-invalid={Boolean(formError)}
            aria-describedby={formError ? 'movement-period-error' : undefined}
          />
        </label>
        <label class="text-sm font-medium text-foreground"
          >Hasta
          <input class={field} type="date" bind:value={to} />
        </label>
      </div>
      <details class="rounded-lg border border-border">
        <summary
          class="cursor-pointer rounded-lg px-3 py-3 text-sm font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >Más filtros: tipo, sentido, lote y referencia</summary
        >
        <div class="grid gap-3 border-t border-border p-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label for="movement-type" class="text-sm font-medium text-foreground"
              >Tipo de movimiento</label
            >
            <select
              id="movement-type"
              class={field}
              value={type}
              onchange={(event) => (type = event.currentTarget.value)}
              ><option value="">Todos los tipos</option>{#each movementTypes as value}<option
                  {value}>{movementTypeLabel(value).label}</option
                >{/each}</select
            >
          </div>
          <div>
            <label for="movement-direction" class="text-sm font-medium text-foreground"
              >Sentido</label
            >
            <select
              id="movement-direction"
              class={field}
              value={direction}
              onchange={(event) =>
                (direction = event.currentTarget.value as WarehouseMovementFilters['direction'])}
              ><option value="">Todos</option><option value="incoming">Entradas</option><option
                value="outgoing">Salidas</option
              ><option value="internal">Dentro de esta bodega</option></select
            >
          </div>
          <label class="text-sm font-medium text-foreground"
            >Lote de recepción o fabricante
            <input
              class={field}
              placeholder="Código o parte del lote"
              maxlength="120"
              bind:value={lot}
            />
          </label>
          <label class="text-sm font-medium text-foreground"
            >Referencia del movimiento
            <input
              class={field}
              placeholder="Código o parte de la referencia"
              maxlength="160"
              bind:value={reference}
            />
          </label>
        </div>
      </details>
      {#if formError}<p id="movement-period-error" class="text-sm text-danger" role="alert">
          {formError}
        </p>{/if}
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap gap-1" aria-label="Períodos rápidos">
          {#each [{ days: 1, label: 'Hoy' }, { days: 7, label: '7 días' }, { days: 30, label: '30 días' }] as period}
            <button
              type="button"
              aria-pressed={isPreset(period.days)}
              class="min-h-11 rounded-lg border px-3 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary {isPreset(
                period.days
              )
                ? 'border-border bg-surface-muted text-foreground'
                : 'border-transparent text-foreground-muted hover:bg-surface-hover'}"
              onclick={() => preset(period.days)}>{period.label}</button
            >
          {/each}
        </div>
        <div class="flex gap-2">
          <Button variant="secondary" class="min-h-11" onclick={clear}>Limpiar filtros</Button
          ><Button type="submit" class="min-h-11" disabled={loading}>Consultar</Button>
        </div>
      </div>
    </form>
  </header>
  <div aria-busy={loading}>
    {#if loading}
      <div class="space-y-3 p-5" role="status">
        <p class="text-sm text-foreground-muted">Consultando movimientos…</p>
        {#each [1, 2, 3] as item (item)}<div class="skeleton h-20 rounded-lg"></div>{/each}
      </div>
    {:else if error}
      <div class="m-4 rounded-lg border border-danger/30 bg-danger/10 p-4">
        <p role="alert" class="text-sm text-foreground">{error}</p>
        <Button variant="secondary" class="mt-3 min-h-11" onclick={() => (revision += 1)}
          >Reintentar consulta</Button
        >
      </div>
    {:else}
      <div
        class="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3 text-xs text-foreground-muted sm:px-5"
        role="status"
      >
        <span
          >{applied.period_from
            ? `Desde ${applied.period_from.split('-').reverse().join('/')}`
            : 'Desde el primer registro'}{applied.period_to
            ? ` hasta ${applied.period_to.split('-').reverse().join('/')}`
            : ' · Sin fecha final'}</span
        >
        <span
          >{rows.length ? `${offset + 1}–${offset + rows.length} resultados` : '0 resultados'} · Más recientes
          primero</span
        >
      </div>
      {#if appliedLabels.length > 0}
        <ul
          class="flex flex-wrap gap-2 border-b border-border px-4 py-3 sm:px-5"
          aria-label="Filtros aplicados"
        >
          {#each appliedLabels as label}<li
              class="max-w-full break-words rounded-md border border-border bg-surface-muted px-2 py-1 text-xs text-foreground"
            >
              {label}
            </li>{/each}
        </ul>
      {/if}
      {#if rows.length === 0}
        <div class="px-5 py-10 text-center">
          <div
            class="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-surface-muted text-xl text-foreground-muted"
            aria-hidden="true"
          >
            ↔
          </div>
          <p class="mt-3 font-semibold text-foreground">No hay movimientos con estos filtros</p>
          <p class="mx-auto mt-1 max-w-md text-sm leading-6 text-foreground-muted">
            Amplía el período o limpia los filtros para consultar otros registros de esta bodega.
          </p>
          <Button variant="secondary" class="mt-4 min-h-11" onclick={clear}
            >Ver todo el historial</Button
          >
        </div>
      {:else}
        <div
          class="hidden grid-cols-[1fr_2fr_2fr_1fr_6rem] gap-4 border-b border-border bg-surface-muted px-5 py-3 text-xs font-medium text-foreground-muted lg:grid"
          aria-hidden="true"
        >
          <span>Fecha y responsable</span><span>Producto y movimiento</span><span>Recorrido</span
          ><span>Cantidad</span><span class="text-right">Detalle</span>
        </div>
        <ol class="divide-y divide-border">
          {#each rows as row (row.id)}
            {@const flow = movementDirection(row, warehouseId)}
            {@const kind = movementTypeLabel(row.movement_type)}
            <li>
              <article
                class="grid min-w-0 gap-3 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-[1fr_2fr_2fr_1fr_6rem] lg:gap-4"
                aria-label={`${flow.label}: ${row.product_name ?? row.product_sku ?? 'Producto histórico'}`}
              >
                <div
                  class="flex min-w-0 flex-wrap items-baseline gap-x-2 text-xs leading-5 text-foreground-muted sm:col-span-2 lg:col-span-1 lg:block"
                >
                  <time datetime={row.posted_at} class="text-foreground"
                    >{localMovementDate(row.posted_at)}</time
                  >
                  <p class="break-words">{row.operator ?? 'Responsable no registrado'}</p>
                </div>
                <div class="min-w-0">
                  <span
                    class="inline-flex rounded px-2 py-0.5 text-xs font-medium {kind.color} {kind.bg}"
                    >{kind.label}</span
                  >
                  <p class="mt-2 break-words text-sm font-semibold text-foreground">
                    {row.product_name ?? row.product_sku ?? 'Producto histórico sin nombre'}
                  </p>
                  <p class="mt-1 break-all font-mono text-xs text-foreground-muted">
                    {row.product_sku ?? row.handling_unit_code ?? 'Sin código de producto'}
                  </p>
                  {#if row.receipt_lot_code || row.lot_code}<p
                      class="mt-1 break-all text-xs text-foreground-muted"
                    >
                      Lote: {row.receipt_lot_header_code ?? row.receipt_lot_code ?? row.lot_code}
                    </p>{/if}
                </div>
                <div class="min-w-0 text-xs leading-5 text-foreground-muted">
                  <p class="break-words">
                    <span class="font-medium text-foreground">Desde:</span>
                    {row.from_warehouse_id === warehouseId
                      ? (row.from_location_code ?? 'Esta bodega')
                      : (row.from_warehouse_name ?? 'Origen externo')}
                  </p>
                  <p class="break-words">
                    <span class="font-medium text-foreground">Hacia:</span>
                    {row.to_warehouse_id === warehouseId
                      ? (row.to_location_code ?? 'Esta bodega')
                      : (row.to_warehouse_name ?? 'Salida de inventario')}
                  </p>
                  <details class="mt-1">
                    <summary
                      class="min-h-11 cursor-pointer rounded py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                      >Referencia</summary
                    >
                    <p class="mt-1 break-all font-mono">
                      {row.source_reference ?? 'Sin referencia registrada'}
                    </p>
                  </details>
                </div>
                <div
                  class="flex min-w-0 items-center justify-between gap-3 border-t border-border pt-3 sm:col-span-2 lg:contents"
                >
                  <div class="min-w-0">
                    <p class="text-xs font-medium {flow.className}">{flow.label}</p>
                    <p class="mt-1 break-words font-mono text-sm font-semibold text-foreground">
                      {flow.sign}
                      {formatMovementQuantity(row.quantity_base)}
                      {row.base_unit_symbol ?? row.base_unit_name ?? 'u'}
                    </p>
                  </div>
                  <div class="lg:text-right">
                    <button
                      type="button"
                      class="min-h-11 rounded-lg border border-border px-3 text-xs font-medium text-foreground hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                      aria-label={`Ver detalle de ${row.product_name ?? row.product_sku ?? 'movimiento'} del ${localMovementDate(row.posted_at)}`}
                      onclick={() => (selected = row)}>Ver detalle</button
                    >
                  </div>
                </div>
              </article>
            </li>
          {/each}
        </ol>
      {/if}
      <footer
        class="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3 sm:px-5"
      >
        <p class="text-xs text-foreground-muted">
          Página {Math.floor(offset / size) + 1} · Hasta {size} registros por página
        </p>
        <div class="flex gap-2">
          <Button
            variant="secondary"
            class="min-h-11"
            disabled={offset === 0}
            onclick={() => pageTo(Math.max(0, offset - size))}>Anterior</Button
          ><Button
            variant="secondary"
            class="min-h-11"
            disabled={!hasNext}
            onclick={() => pageTo(offset + size)}>Siguiente</Button
          >
        </div>
      </footer>
    {/if}
  </div>
</section>
<MovementDetailsModal movement={selected} onclose={() => (selected = null)} />
