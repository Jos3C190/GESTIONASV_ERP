<script lang="ts">
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import {
    movementTypeLabel,
    stockStatusLabel
  } from '$lib/features/inventory/movement-presentation';
  import { formatKardexDateTime, kardexNumber } from '$lib/features/inventory/kardex-format';
  import type { PhysicalKardex, PhysicalKardexRow } from '$lib/features/inventory/kardex';

  let {
    data,
    page,
    loading,
    onPageChange,
    onOpenDetail
  }: {
    data: PhysicalKardex;
    page: number;
    loading: boolean;
    onPageChange: (page: number) => void;
    onOpenDetail: (row: PhysicalKardexRow) => void;
  } = $props();

  const endpoint = (external: boolean, name: string | null) =>
    external ? 'Punto externo' : (name ?? 'Bodega no disponible para este alcance');

  const location = (code: string | null, status: string | null) =>
    `${code ?? 'Sin ubicación'}${status ? ` · ${stockStatusLabel(status)}` : ''}`;
</script>

<div class="space-y-3 xl:hidden">
  {#each data.items as row (row.id)}
    <article class="space-y-3 rounded-lg border border-border bg-surface p-4">
      <header class="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p class="text-sm font-medium text-foreground">{formatKardexDateTime(row.posted_at)}</p>
          <p class="mt-1 break-all font-mono text-xs text-foreground-muted">
            {row.document_reference ?? row.source_reference ?? 'Sin documento de origen'}
          </p>
        </div>
        <Badge>{movementTypeLabel(row.movement_type).label}</Badge>
        {#if row.operator}<p class="mt-1 text-xs text-foreground-muted">
            Registró: {row.operator}
          </p>{/if}
      </header>

      <div class="grid grid-cols-2 gap-3 rounded-lg bg-surface-muted/50 p-3 text-sm">
        <div>
          <p class="text-xs text-foreground-muted">Entrada</p>
          <p class="mt-1 font-semibold tabular-nums text-success">
            {kardexNumber(row.incoming_quantity)}
          </p>
        </div>
        <div>
          <p class="text-xs text-foreground-muted">Salida</p>
          <p class="mt-1 font-semibold tabular-nums text-danger">
            {kardexNumber(row.outgoing_quantity)}
          </p>
        </div>
        <div class="col-span-2 border-t border-border pt-2">
          <p class="text-xs text-foreground-muted">Saldo después del movimiento</p>
          <p class="mt-1 font-semibold tabular-nums text-foreground">
            {row.balance_after == null
              ? 'Saldo no reconstruible'
              : `${kardexNumber(row.balance_after)} ${row.base_unit_symbol}`}
          </p>
        </div>
      </div>

      <div class="space-y-1 text-sm">
        <p class="font-medium text-foreground">
          {row.is_internal
            ? 'Cambio dentro de la bodega'
            : `${endpoint(row.from_warehouse_external, row.from_warehouse_name)} → ${endpoint(row.to_warehouse_external, row.to_warehouse_name)}`}
        </p>
        <p class="break-words text-xs text-foreground-muted">
          {location(row.from_location_code, row.from_stock_status)} → {location(
            row.to_location_code,
            row.to_stock_status
          )}
        </p>
        {#if row.is_internal}
          <p class="text-xs text-foreground-muted">
            Cambio de ubicación/estado: {kardexNumber(row.quantity_base)}
            {row.base_unit_symbol}; efecto neto cero.
          </p>
        {/if}
      </div>

      <footer class="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-foreground-muted">
          {#if row.lot_code}<span>Lote fabricante {row.lot_code}</span>{/if}
          {#if row.receipt_lot_code}<span>Lote de recepción {row.receipt_lot_code}</span>{/if}
          {#if row.handling_unit_id}
            <a
              class="font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              href="/inventory/handling-units/{row.handling_unit_id}"
              >{row.handling_unit_code ?? 'Ver unidad logística'}</a
            >
          {/if}
        </div>
        <Button variant="secondary" onclick={() => onOpenDetail(row)}>Ver detalle</Button>
      </footer>
    </article>
  {/each}
</div>

<div class="hidden overflow-x-auto rounded-lg border border-border xl:block">
  <table class="w-full min-w-[1050px] text-left text-sm">
    <caption class="sr-only">Movimientos físicos del artículo seleccionado</caption>
    <thead class="bg-surface-muted/60 text-xs text-foreground-muted">
      <tr>
        <th scope="col" class="px-3 py-3">Fecha</th>
        <th scope="col" class="px-3 py-3">Movimiento y origen</th>
        <th scope="col" class="px-3 py-3">Recorrido</th>
        <th scope="col" class="px-3 py-3 text-right">Entradas</th>
        <th scope="col" class="px-3 py-3 text-right">Salidas</th>
        <th scope="col" class="px-3 py-3 text-right">Saldo</th>
        <th scope="col" class="px-3 py-3">Detalle</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-border">
      {#each data.items as row (row.id)}
        <tr class="align-top">
          <td class="whitespace-nowrap px-3 py-3 text-foreground-muted"
            >{formatKardexDateTime(row.posted_at)}</td
          >
          <td class="px-3 py-3">
            <Badge>{movementTypeLabel(row.movement_type).label}</Badge>
            {#if row.operator}<p class="mt-1 text-xs text-foreground-muted">
                Registró: {row.operator}
              </p>{/if}
            <p class="mt-2 break-all font-mono text-xs text-foreground-muted">
              {row.document_reference ?? row.source_reference ?? 'Sin documento de origen'}
            </p>
            {#if row.lot_code}<p class="mt-1 text-xs text-foreground-muted">
                Lote fabricante {row.lot_code}
              </p>{/if}
            {#if row.receipt_lot_code}<p class="mt-1 text-xs text-foreground-muted">
                Lote de recepción {row.receipt_lot_code}
              </p>{/if}
            {#if row.handling_unit_id}
              <a
                class="mt-1 inline-block text-xs text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                href="/inventory/handling-units/{row.handling_unit_id}"
                >{row.handling_unit_code ?? 'Ver unidad logística'}</a
              >
            {/if}
          </td>
          <td class="px-3 py-3">
            <p class="font-medium text-foreground">
              {row.is_internal
                ? 'Cambio dentro de la bodega'
                : `${endpoint(row.from_warehouse_external, row.from_warehouse_name)} → ${endpoint(row.to_warehouse_external, row.to_warehouse_name)}`}
            </p>
            <p class="mt-1 text-xs text-foreground-muted">
              {location(row.from_location_code, row.from_stock_status)} → {location(
                row.to_location_code,
                row.to_stock_status
              )}
            </p>
            {#if row.is_internal}
              <p class="mt-1 text-xs text-foreground-muted">
                Cambio de ubicación/estado: {kardexNumber(row.quantity_base)}
                {row.base_unit_symbol}; efecto neto cero.
              </p>
            {/if}
          </td>
          <td class="px-3 py-3 text-right tabular-nums text-success"
            >{kardexNumber(row.incoming_quantity)}</td
          >
          <td class="px-3 py-3 text-right tabular-nums text-danger"
            >{kardexNumber(row.outgoing_quantity)}</td
          >
          <td class="px-3 py-3 text-right font-medium tabular-nums text-foreground"
            >{row.balance_after == null ? 'No reconstruible' : kardexNumber(row.balance_after)}</td
          >
          <td class="px-3 py-3"
            ><Button variant="secondary" onclick={() => onOpenDetail(row)}>Ver detalle</Button></td
          >
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
  <p class="text-sm text-foreground-muted">
    {data.total} movimiento(s) · Página {data.page} de {Math.max(
      1,
      Math.ceil(data.total / data.page_size)
    )}
  </p>
  <div class="flex gap-2">
    <Button
      variant="secondary"
      disabled={page <= 1 || loading}
      onclick={() => onPageChange(page - 1)}>Anterior</Button
    >
    <Button
      variant="secondary"
      disabled={page * data.page_size >= data.total || loading}
      onclick={() => onPageChange(page + 1)}>Siguiente</Button
    >
  </div>
</div>
