<script lang="ts">
  import Modal from '$lib/components/ui/Modal.svelte';
  import { movementTypeLabel, stockStatusLabel } from '../movement-presentation';
  import type { PhysicalKardexRow } from '../kardex';

  interface Props {
    movement: PhysicalKardexRow | null;
    onclose: () => void;
  }

  let { movement, onclose }: Props = $props();

  function formatDateTime(value: string): string {
    return new Intl.DateTimeFormat('es-SV', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'America/El_Salvador'
    }).format(new Date(value));
  }
</script>

<Modal open={movement !== null} title="Detalle del movimiento físico" {onclose} size="lg">
  {#if movement}
    {@const type = movementTypeLabel(movement.movement_type)}
    <div class="space-y-5">
      <section class="space-y-2">
        <span class="inline-flex rounded-md {type.bg} px-2 py-1 text-xs font-semibold {type.color}">
          {type.label}
        </span>
        <h3 class="text-base font-semibold text-foreground">
          {movement.product_name}
          {#if movement.product_sku}<span class="ml-2 font-mono text-xs text-foreground-muted"
              >{movement.product_sku}</span
            >{/if}
        </h3>
        <p class="text-sm text-foreground-muted">{formatDateTime(movement.posted_at)}</p>
      </section>

      <dl class="grid gap-3 sm:grid-cols-3">
        <div class="rounded-lg border border-border bg-surface-muted/30 p-3">
          <dt class="text-xs text-foreground-muted">Cantidad base</dt>
          <dd class="mt-1 font-semibold tabular-nums text-foreground">
            {movement.quantity_base}
            {movement.base_unit_symbol}
          </dd>
        </div>
        <div class="rounded-lg border border-border bg-surface-muted/30 p-3">
          <dt class="text-xs text-foreground-muted">Entrada / salida</dt>
          <dd class="mt-1 font-semibold tabular-nums text-foreground">
            {movement.incoming_quantity} / {movement.outgoing_quantity}
          </dd>
        </div>
        <div class="rounded-lg border border-border bg-surface-muted/30 p-3">
          <dt class="text-xs text-foreground-muted">Saldo tras este evento</dt>
          <dd class="mt-1 font-semibold tabular-nums text-foreground">
            {movement.balance_after ?? 'No reconstruible'}
          </dd>
        </div>
      </dl>

      <section class="grid gap-3 sm:grid-cols-2" aria-label="Recorrido autorizado">
        <div class="rounded-lg border border-border p-3">
          <h4 class="text-xs font-semibold text-foreground">Origen</h4>
          <p class="mt-2 text-sm text-foreground">
            {movement.from_warehouse_external
              ? 'Origen externo'
              : (movement.from_warehouse_name ?? 'No disponible para este alcance')}
          </p>
          <p class="mt-1 text-xs text-foreground-muted">
            {movement.from_location_code ?? '—'}
            {#if movement.from_stock_status}
              · {stockStatusLabel(movement.from_stock_status)}{/if}
          </p>
        </div>
        <div class="rounded-lg border border-border p-3">
          <h4 class="text-xs font-semibold text-foreground">Destino</h4>
          <p class="mt-2 text-sm text-foreground">
            {movement.to_warehouse_external
              ? 'Destino externo'
              : (movement.to_warehouse_name ?? 'No disponible para este alcance')}
          </p>
          <p class="mt-1 text-xs text-foreground-muted">
            {movement.to_location_code ?? '—'}
            {#if movement.to_stock_status}
              · {stockStatusLabel(movement.to_stock_status)}{/if}
          </p>
        </div>
      </section>

      <dl class="grid gap-x-4 gap-y-2 rounded-lg border border-border p-3 text-sm sm:grid-cols-2">
        <dt class="text-foreground-muted">Lote</dt>
        <dd class="break-all text-foreground">
          Fabricante: {movement.lot_code ?? 'Sin lote'}
          {#if movement.receipt_lot_code}<br />Recepción: {movement.receipt_lot_code}{/if}
          {#if movement.receipt_lot_header_code}<br />Recepción agrupada: {movement.receipt_lot_header_code}{/if}
        </dd>
        <dt class="text-foreground-muted">Unidad logística</dt>
        <dd>
          {#if movement.handling_unit_id}<a
              class="font-mono text-primary underline-offset-4 hover:underline"
              href="/inventory/handling-units/{movement.handling_unit_id}"
              >{movement.handling_unit_code ?? 'Abrir ficha'}</a
            >{:else}<span class="text-foreground">No disponible para este alcance</span>{/if}
        </dd>
        <dt class="text-foreground-muted">Referencia de origen</dt>
        <dd class="break-all font-mono text-xs text-foreground">
          {movement.source_reference ?? 'Sin referencia'}
        </dd>
        <dt class="text-foreground-muted">Identificador persistido</dt>
        <dd class="break-all font-mono text-xs text-foreground">{movement.movement_id}</dd>
      </dl>
    </div>
  {/if}
</Modal>
