<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import type { InventoryMovementHistory } from '../types';
  import {
    formatMovementDate,
    formatMovementQuantity,
    formatPhysicalMeasure,
    movementTypeLabel,
    stockStatusLabel
  } from '../movement-presentation';

  interface Props {
    movement: InventoryMovementHistory | null;
    onclose: () => void;
  }

  let { movement, onclose }: Props = $props();

  function warehouseTitle(name: string | null, code: string | null, fallback: string): string {
    if (!name && !code) return fallback;
    return name ? `${name}${code ? ` (${code})` : ''}` : (code ?? '—');
  }
</script>

<Modal open={movement !== null} title="Detalle del movimiento" {onclose} size="lg">
  {#if movement}
    {@const typeStyle = movementTypeLabel(movement.movement_type)}
    <div class="space-y-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <span
            class="inline-flex items-center rounded-md {typeStyle.bg} px-2 py-1 text-xs font-semibold {typeStyle.color}"
            >{typeStyle.label}</span
          >
          <h3 class="mt-3 break-words text-base font-semibold text-foreground">
            {movement.product_name ?? 'Producto sin nombre'}
          </h3>
          {#if movement.product_sku}
            <p class="mt-1 font-mono text-xs text-foreground-muted">{movement.product_sku}</p>
          {/if}
        </div>
        <div class="text-left sm:text-right">
          <p class="text-xs text-foreground-muted">Fecha y hora</p>
          <p class="mt-1 text-sm font-medium text-foreground">
            {formatMovementDate(movement.posted_at)}
          </p>
          <p class="mt-1 text-xs text-foreground-muted">
            Registrado por {movement.operator ?? 'usuario no disponible'}
          </p>
        </div>
      </div>

      {#if movement.purchase_order_code || movement.purchase_code}
        <section class="rounded-lg border border-primary/20 bg-primary/5 p-3">
          <h4 class="text-xs font-semibold text-foreground">Compra de origen</h4>
          <p class="mt-1 text-sm text-foreground">
            {movement.purchase_code ?? 'Compra vinculada'}
            {#if movement.purchase_order_code}
              <span class="ml-1 text-foreground-muted">· Orden {movement.purchase_order_code}</span>
            {/if}
          </p>
        </section>
      {/if}

      <section class="rounded-lg border border-border bg-surface-muted/20 p-3">
        <h4 class="mb-3 text-xs font-semibold text-foreground">Recorrido del producto</h4>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div class="rounded-md border border-border bg-surface p-3">
            <p class="text-xs text-foreground-muted">Desde</p>
            <p class="mt-1 text-sm font-medium text-foreground">
              {warehouseTitle(
                movement.from_warehouse_name,
                movement.from_warehouse_code,
                'Origen externo'
              )}
            </p>
            <p class="mt-1 text-xs text-foreground-muted">
              {movement.from_location_code ?? 'Sin ubicación de origen'}
              {#if movement.from_stock_status}
                · {stockStatusLabel(movement.from_stock_status)}
              {/if}
            </p>
          </div>
          <div class="rounded-md border border-border bg-surface p-3">
            <p class="text-xs text-foreground-muted">Hacia</p>
            <p class="mt-1 text-sm font-medium text-foreground">
              {warehouseTitle(
                movement.to_warehouse_name,
                movement.to_warehouse_code,
                'Sin almacén de destino'
              )}
            </p>
            <p class="mt-1 text-xs text-foreground-muted">
              {movement.to_location_code ?? 'Sin ubicación de destino'}
              {#if movement.to_stock_status}
                · {stockStatusLabel(movement.to_stock_status)}
              {/if}
            </p>
          </div>
        </div>
      </section>

      <dl class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div class="rounded-lg border border-border bg-surface-muted/30 p-3">
          <dt class="text-xs text-foreground-muted">Cantidad y unidad base</dt>
          <dd class="mt-1 text-sm font-semibold text-foreground">
            {formatMovementQuantity(movement.quantity_base)}
            {movement.base_unit_symbol ?? movement.base_unit_name ?? 'unidades'}
          </dd>
        </div>
        <div class="rounded-lg border border-border bg-surface-muted/30 p-3">
          <dt class="text-xs text-foreground-muted">Unidad logística</dt>
          <dd class="mt-1 min-w-0 break-all text-sm font-medium text-foreground">
            {movement.handling_unit_code ?? 'Sin unidad logística'}
          </dd>
        </div>
        <div class="rounded-lg border border-border bg-surface-muted/30 p-3">
          <dt class="text-xs text-foreground-muted">Lote</dt>
          <dd class="mt-1 min-w-0 break-all text-sm font-medium text-foreground">
            Fabricante: {movement.lot_code ?? 'Sin lote'}
            {#if movement.receipt_lot_code}<br />Recepción: {movement.receipt_lot_code}{/if}
            {#if movement.receipt_lot_header_code}<br />Recepción original: {movement.receipt_lot_header_code}{/if}
          </dd>
        </div>
        <div class="rounded-lg border border-border bg-surface-muted/30 p-3">
          <dt class="text-xs text-foreground-muted">Vencimiento</dt>
          <dd class="mt-1 text-sm font-medium text-foreground">
            {movement.expiry_date ?? 'Sin vencimiento registrado'}
          </dd>
        </div>
        <div class="rounded-lg border border-border bg-surface-muted/30 p-3">
          <dt class="text-xs text-foreground-muted">Peso ocupado</dt>
          <dd class="mt-1 text-sm font-medium text-foreground">
            {formatPhysicalMeasure(movement.occupied_weight_kg, 'kg')}
          </dd>
        </div>
        <div class="rounded-lg border border-border bg-surface-muted/30 p-3">
          <dt class="text-xs text-foreground-muted">Volumen ocupado</dt>
          <dd class="mt-1 text-sm font-medium text-foreground">
            {formatPhysicalMeasure(movement.occupied_volume_m3, 'm³')}
          </dd>
        </div>
      </dl>

      <details class="rounded-lg border border-border bg-surface-muted/20 p-3">
        <summary
          class="cursor-pointer text-sm font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          Datos de trazabilidad
        </summary>
        <dl class="mt-3 grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2">
          <div>
            <dt class="text-xs text-foreground-muted">Referencia de origen</dt>
            <dd class="mt-1 break-all font-mono text-xs text-foreground">
              {movement.source_reference ?? 'Sin referencia'}
            </dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">ID del movimiento</dt>
            <dd class="mt-1 break-all font-mono text-xs text-foreground">{movement.movement_id}</dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">ID de la línea</dt>
            <dd class="mt-1 break-all font-mono text-xs text-foreground">{movement.id}</dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">ID del artículo de inventario</dt>
            <dd class="mt-1 break-all font-mono text-xs text-foreground">
              {movement.inventory_item_id}
            </dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">ID de la unidad base</dt>
            <dd class="mt-1 font-mono text-xs text-foreground">{movement.base_unit_id}</dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">Estado de medición</dt>
            <dd class="mt-1 text-xs text-foreground">
              {movement.measurement_status === 'incomplete'
                ? 'Incompleta'
                : movement.measurement_status === 'verified'
                  ? 'Verificada'
                  : 'Completa'}
            </dd>
          </div>
          {#if movement.packaging_snapshot}
            <div class="sm:col-span-2">
              <dt class="text-xs text-foreground-muted">Presentación utilizada</dt>
              <dd
                class="mt-1 overflow-x-auto rounded-md bg-surface p-2 font-mono text-xs text-foreground-muted"
              >
                <pre>{JSON.stringify(movement.packaging_snapshot, null, 2)}</pre>
              </dd>
            </div>
          {/if}
        </dl>
      </details>

      <div class="flex justify-end">
        <Button variant="secondary" onclick={onclose}>Cerrar</Button>
      </div>
    </div>
  {/if}
</Modal>
