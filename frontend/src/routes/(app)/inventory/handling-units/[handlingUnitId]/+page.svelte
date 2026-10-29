<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import { inventoryApi } from '$lib/features/inventory/services';
  import HandlingUnitLotIdentity from '$lib/features/inventory/components/HandlingUnitLotIdentity.svelte';
  import type {
    HandlingUnitTraceEvent,
    HandlingUnitTraceability,
    StockStatus
  } from '$lib/features/inventory/types';
  import { page } from '$app/state';

  let trace = $state<HandlingUnitTraceability | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  onMount(() => {
    void loadTraceability(page.params.handlingUnitId);
  });

  async function loadTraceability(id: string | undefined) {
    if (!id) {
      error = 'El enlace del QR no contiene una unidad logística.';
      loading = false;
      return;
    }
    try {
      trace = await inventoryApi.getHandlingUnitTraceability(id);
    } catch (cause: unknown) {
      error =
        cause instanceof Error
          ? cause.message
          : 'No se pudo cargar la trazabilidad de esta unidad.';
    } finally {
      loading = false;
    }
  }

  const statusLabels: Record<StockStatus, string> = {
    available: 'Disponible',
    quarantine: 'Cuarentena',
    blocked: 'Bloqueado',
    damaged: 'Dañado',
    in_transit: 'En tránsito'
  };

  function movementLabel(type: string): string {
    const labels: Record<string, string> = {
      receipt: 'Recepción',
      putaway: 'Ubicación o liberación',
      transfer: 'Traslado',
      pick: 'Salida para preparación',
      shipment: 'Despacho',
      adjustment_in: 'Ajuste de entrada',
      adjustment_out: 'Ajuste de salida',
      reversal: 'Reversión'
    };
    return labels[type] ?? type.replaceAll('_', ' ');
  }

  function dateTime(value: string | null | undefined): string {
    if (!value) return 'No registrada';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'No registrada';
    return new Intl.DateTimeFormat('es-SV', {
      dateStyle: 'medium',
      timeStyle: 'short'
    }).format(date);
  }

  function dateOnly(value: string | null | undefined): string {
    if (!value) return 'No registrada';
    const date = new Date(value.length === 10 ? `${value}T12:00:00` : value);
    if (Number.isNaN(date.getTime())) return 'No registrada';
    return new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium' }).format(date);
  }

  function statusVariant(status: StockStatus): 'success' | 'warning' | 'danger' | 'neutral' {
    if (status === 'available') return 'success';
    if (status === 'quarantine' || status === 'in_transit') return 'warning';
    if (status === 'damaged' || status === 'blocked') return 'danger';
    return 'neutral';
  }

  function movementPlace(
    warehouseName: string | null,
    warehouseCode: string | null,
    locationCode: string | null
  ): string {
    const warehouse = warehouseName ?? warehouseCode;
    return (
      [warehouse, locationCode].filter((part): part is string => Boolean(part)).join(' · ') ||
      'No registrada'
    );
  }

  function movementStatus(event: HandlingUnitTraceEvent, direction: 'from' | 'to'): string | null {
    const status = direction === 'from' ? event.from_stock_status : event.to_stock_status;
    return status ? statusLabels[status] : null;
  }

  function quantity(value: number, symbol: string | null): string {
    const amount = new Intl.NumberFormat('es-SV', { maximumFractionDigits: 6 }).format(value);
    return `${amount}${symbol ? ` ${symbol}` : ''}`;
  }
</script>

<svelte:head>
  <title>Trazabilidad de unidad logística · GestionaSV</title>
  <meta
    name="description"
    content="Origen, ubicación y movimientos registrados de una unidad logística de inventario."
  />
</svelte:head>

<main class="mx-auto max-w-6xl space-y-6 p-4 sm:p-6 lg:p-8">
  <a
    href={trace
      ? `/warehouses/${encodeURIComponent(trace.handling_unit.warehouse_id)}`
      : '/warehouses'}
    class="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
  >
    <span aria-hidden="true">←</span> Volver a almacenes
  </a>

  {#if loading}
    <section class="rounded-2xl border border-border bg-surface p-6" role="status">
      <div class="skeleton h-7 w-64 rounded-lg"></div>
      <div class="skeleton mt-4 h-28 rounded-xl"></div>
      <p class="mt-4 text-sm text-foreground-muted">Cargando trazabilidad de la unidad…</p>
    </section>
  {:else if error}
    <section class="rounded-2xl border border-danger/30 bg-danger/10 p-6" role="alert">
      <h1 class="text-xl font-semibold text-danger">No se pudo abrir la ficha del QR</h1>
      <p class="mt-2 text-sm text-danger/90">{error}</p>
      <p class="mt-3 text-xs text-foreground-muted">
        Verifique que inició sesión con una cuenta autorizada para consultar el inventario de esta
        bodega.
      </p>
    </section>
  {:else if trace}
    <header class="rounded-2xl border border-border bg-surface p-6">
      <p class="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
        Trazabilidad de inventario
      </p>
      <div class="mt-2 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 class="text-2xl font-semibold text-foreground">{trace.handling_unit.code}</h1>
          <p class="mt-1 text-sm text-foreground-muted">
            {trace.product_sku ? `${trace.product_sku} · ` : ''}{trace.product_name ??
              'Producto sin nombre'}
          </p>
        </div>
        <Badge variant={statusVariant(trace.handling_unit.stock_status)}>
          {statusLabels[trace.handling_unit.stock_status]}
        </Badge>
      </div>
      <div class="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div class="rounded-xl bg-surface-muted/50 p-3">
          <p class="text-xs text-foreground-muted">Cantidad de esta unidad</p>
          <p class="mt-1 font-semibold text-foreground">
            {quantity(trace.handling_unit.quantity_base, trace.base_unit_symbol)}
          </p>
        </div>
        <div class="rounded-xl bg-surface-muted/50 p-3">
          <p class="text-xs text-foreground-muted">Bodega actual</p>
          <p class="mt-1 font-semibold text-foreground">{trace.warehouse_name}</p>
          <p class="text-xs text-foreground-muted">
            {trace.warehouse_code} · {trace.location_code}
          </p>
        </div>
        <div class="rounded-xl bg-surface-muted/50 p-3">
          <p class="text-xs text-foreground-muted">Lote</p>
          <HandlingUnitLotIdentity
            manufacturerLot={trace.handling_unit.lot_code}
            receiptLot={trace.handling_unit.receipt_lot_code}
            receiptLotHeader={trace.handling_unit.receipt_lot_header_code}
          />
        </div>
        <div class="rounded-xl bg-surface-muted/50 p-3">
          <p class="text-xs text-foreground-muted">Vencimiento</p>
          <p class="mt-1 font-semibold text-foreground">
            {dateOnly(trace.handling_unit.expiry_date)}
          </p>
        </div>
      </div>
    </header>

    <section class="rounded-2xl border border-border bg-surface p-6" aria-labelledby="origin-title">
      <div>
        <h2 id="origin-title" class="text-lg font-semibold text-foreground">Origen de compra</h2>
        <p class="mt-1 text-sm text-foreground-muted">
          Información enlazada a la recepción que creó esta unidad logística.
        </p>
      </div>
      <div class="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <p class="text-xs text-foreground-muted">Proveedor</p>
          <p class="mt-1 font-medium text-foreground">
            {trace.origin.supplier_name ?? 'No enlazado'}
          </p>
          {#if trace.origin.supplier_code}<p class="text-xs text-foreground-muted">
              {trace.origin.supplier_code}
            </p>{/if}
        </div>
        <div>
          <p class="text-xs text-foreground-muted">Orden de compra</p>
          <p class="mt-1 font-medium text-foreground">
            {trace.origin.purchase_order_code ?? 'No enlazada'}
          </p>
        </div>
        <div>
          <p class="text-xs text-foreground-muted">Recepción / compra</p>
          <p class="mt-1 font-medium text-foreground">
            {trace.origin.purchase_code ?? 'No enlazada'}
          </p>
          <p class="text-xs text-foreground-muted">
            Recibido: {dateTime(trace.origin.received_at)}
          </p>
        </div>
        <div>
          <p class="text-xs text-foreground-muted">Fecha de compra</p>
          <p class="mt-1 font-medium text-foreground">{dateTime(trace.origin.purchase_date)}</p>
        </div>
        <div>
          <p class="text-xs text-foreground-muted">Consolidado</p>
          <p class="mt-1 font-medium text-foreground">
            {trace.origin.consolidation_code ?? 'No enlazado'}
          </p>
        </div>
      </div>

      <div class="mt-5 border-t border-border pt-4">
        <h3 class="text-sm font-semibold text-foreground">Solicitudes y sucursales de origen</h3>
        {#if trace.origin.requests.length}
          <ul class="mt-3 grid gap-3 md:grid-cols-2">
            {#each trace.origin.requests as request (request.request_code)}
              <li class="rounded-xl border border-border bg-surface-muted/20 p-4">
                <p class="font-mono text-sm font-semibold text-primary">{request.request_code}</p>
                <p class="mt-1 font-medium text-foreground">{request.branch_name}</p>
                <p class="mt-1 text-xs text-foreground-muted">
                  Solicitado: {dateTime(request.requested_at)} · Requerido: {dateOnly(
                    request.required_date
                  )}
                </p>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="mt-2 text-sm text-foreground-muted">
            Esta recepción no tiene una solicitud de sucursal enlazada en los registros disponibles.
          </p>
        {/if}
      </div>
    </section>

    <section
      class="rounded-2xl border border-border bg-surface p-6"
      aria-labelledby="timeline-title"
    >
      <div>
        <h2 id="timeline-title" class="text-lg font-semibold text-foreground">
          Historial de movimientos
        </h2>
        <p class="mt-1 text-sm text-foreground-muted">
          Cada evento se presenta con la fecha y ubicación guardadas en el inventario.
        </p>
      </div>
      {#if trace.movements.length}
        <ol class="mt-5 space-y-0">
          {#each trace.movements as event, index (event.movement_id)}
            <li class="relative flex gap-4 pb-6 last:pb-0">
              <div class="flex w-5 shrink-0 flex-col items-center">
                <span class="mt-1 h-3 w-3 rounded-full border-2 border-primary bg-surface"></span>
                {#if index < trace.movements.length - 1}<span class="mt-1 h-full w-px bg-border"
                  ></span>{/if}
              </div>
              <div class="min-w-0 flex-1 rounded-xl border border-border p-4">
                <div class="flex flex-wrap items-start justify-between gap-2">
                  <h3 class="font-semibold text-foreground">
                    {movementLabel(event.movement_type)}
                  </h3>
                  <time class="text-xs text-foreground-muted">{dateTime(event.posted_at)}</time>
                </div>
                <p class="mt-1 text-xs text-foreground-muted">
                  Registró: {event.operator ?? 'Usuario no disponible'}
                  · Cantidad: {quantity(event.quantity_base, trace.base_unit_symbol)}
                </p>
                {#if event.from_warehouse_name || event.from_warehouse_code}
                  <p class="mt-3 text-sm text-foreground">
                    <span class="text-foreground-muted">Desde:</span>
                    {movementPlace(
                      event.from_warehouse_name,
                      event.from_warehouse_code,
                      event.from_location_code
                    )}
                    {#if movementStatus(event, 'from')}<span class="text-foreground-muted">
                        · {movementStatus(event, 'from')}</span
                      >{/if}
                  </p>
                {/if}
                {#if event.to_warehouse_name || event.to_warehouse_code}
                  <p class="mt-1 text-sm text-foreground">
                    <span class="text-foreground-muted">Hacia:</span>
                    {movementPlace(
                      event.to_warehouse_name,
                      event.to_warehouse_code,
                      event.to_location_code
                    )}
                    {#if movementStatus(event, 'to')}<span class="text-foreground-muted">
                        · {movementStatus(event, 'to')}</span
                      >{/if}
                  </p>
                {/if}
                {#if event.source_reference}
                  <p class="mt-2 break-all font-mono text-[11px] text-foreground-muted">
                    Referencia: {event.source_reference}
                  </p>
                {/if}
              </div>
            </li>
          {/each}
        </ol>
      {:else}
        <p
          class="mt-4 rounded-xl border border-dashed border-border p-4 text-sm text-foreground-muted"
        >
          Esta unidad todavía no tiene movimientos registrados.
        </p>
      {/if}
      <p
        class="mt-5 rounded-lg border border-warning/30 bg-warning/5 px-4 py-3 text-xs text-foreground-muted"
      >
        Los movimientos muestran los estados y ubicaciones registrados. Si el motivo de una pérdida
        o daño no se capturó en el movimiento original, esta ficha no puede recuperarlo.
      </p>
    </section>
  {/if}
</main>
