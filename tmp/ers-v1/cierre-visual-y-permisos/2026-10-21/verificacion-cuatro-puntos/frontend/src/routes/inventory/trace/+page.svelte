<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import { inventoryApi } from '$lib/features/inventory/services';
  import type { PublicHandlingUnitTrace, StockStatus } from '$lib/features/inventory/types';

  let trace = $state<PublicHandlingUnitTrace | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  onMount(() => {
    const token = window.location.hash.slice(1);
    window.history.replaceState(
      window.history.state,
      '',
      `${window.location.pathname}${window.location.search}`
    );
    if (!token) {
      error = 'Este enlace no contiene el permiso QR. Vuelva a escanear la etiqueta.';
      loading = false;
      return;
    }
    void loadTrace(token);
  });

  async function loadTrace(token: string) {
    try {
      trace = await inventoryApi.getPublicTraceability(token);
    } catch (cause: unknown) {
      error =
        cause instanceof Error
          ? cause.message
          : 'No se pudo consultar el origen y los movimientos de esta unidad.';
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

  function statusVariant(status: StockStatus): 'success' | 'warning' | 'danger' | 'neutral' {
    if (status === 'available') return 'success';
    if (status === 'quarantine' || status === 'in_transit') return 'warning';
    if (status === 'damaged' || status === 'blocked') return 'danger';
    return 'neutral';
  }

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
    return new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium', timeStyle: 'short' }).format(
      date
    );
  }

  function dateOnly(value: string | null | undefined): string {
    if (!value) return 'Sin vencimiento registrado';
    const date = new Date(value.length === 10 ? `${value}T12:00:00` : value);
    if (Number.isNaN(date.getTime())) return 'Sin vencimiento registrado';
    return new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium' }).format(date);
  }

  function quantity(value: string, symbol: string | null): string {
    const amount = Number(value);
    const formatted = new Intl.NumberFormat('es-SV', { maximumFractionDigits: 6 }).format(
      Number.isFinite(amount) ? amount : 0
    );
    return `${formatted}${symbol ? ` ${symbol}` : ''}`;
  }

  function place(
    warehouseName: string | null,
    warehouseCode: string | null,
    locationCode: string | null
  ): string {
    return (
      [warehouseName ?? warehouseCode, locationCode]
        .filter((part): part is string => Boolean(part))
        .join(' · ') || 'No registrada'
    );
  }
</script>

<svelte:head>
  <title>Ficha QR de inventario · GestionaSV</title>
  <meta
    name="description"
    content="Consulta limitada del origen, ubicación y movimientos de una unidad logística."
  />
  <meta name="referrer" content="no-referrer" />
</svelte:head>

<main class="mx-auto max-w-5xl space-y-5 p-4 sm:p-6 lg:p-8">
  <header class="rounded-2xl border border-border bg-surface p-5 sm:p-7">
    <p class="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
      Ficha de trazabilidad
    </p>
    <h1 class="mt-2 text-2xl font-semibold text-foreground">Consulta de inventario</h1>
    <p class="mt-2 max-w-3xl text-sm text-foreground-muted">
      Esta ficha muestra información limitada de la unidad identificada por la etiqueta QR. No
      requiere iniciar sesión.
    </p>
  </header>

  {#if loading}
    <section class="rounded-2xl border border-border bg-surface p-6" role="status">
      <div class="skeleton h-7 w-64 rounded-lg"></div>
      <div class="skeleton mt-4 h-28 rounded-xl"></div>
      <p class="mt-4 text-sm text-foreground-muted">Consultando el historial de la unidad…</p>
    </section>
  {:else if error}
    <section class="rounded-2xl border border-danger/30 bg-danger/10 p-6" role="alert">
      <h2 class="text-lg font-semibold text-danger">No se pudo abrir la ficha</h2>
      <p class="mt-2 text-sm text-danger/90">{error}</p>
      <p class="mt-3 text-xs text-foreground-muted">
        Si el enlace fue revocado, solicite una etiqueta QR nueva al encargado de inventario.
      </p>
    </section>
  {:else if trace}
    <section class="rounded-2xl border border-border bg-surface p-5 sm:p-7">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p class="text-xs font-medium text-foreground-muted">Unidad logística</p>
          <h2 class="mt-1 font-mono text-xl font-semibold text-foreground">
            {trace.handling_unit_code}
          </h2>
          <p class="mt-2 text-sm text-foreground-muted">
            {trace.product_sku ? `${trace.product_sku} · ` : ''}{trace.product_name ??
              'Producto sin nombre'}
          </p>
        </div>
        <Badge variant={statusVariant(trace.stock_status)}>{statusLabels[trace.stock_status]}</Badge
        >
      </div>

      <dl class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div class="rounded-xl bg-surface-muted/40 p-4">
          <dt class="text-xs text-foreground-muted">Cantidad de esta unidad</dt>
          <dd class="mt-1 font-semibold text-foreground">
            {quantity(trace.quantity_base, trace.base_unit_symbol)}
          </dd>
        </div>
        <div class="rounded-xl bg-surface-muted/40 p-4">
          <dt class="text-xs text-foreground-muted">Ubicación actual</dt>
          <dd class="mt-1 font-semibold text-foreground">
            {trace.warehouse_name || trace.warehouse_code || 'Bodega no registrada'} · {trace.location_code ||
              'Sin ubicación asignada'}
          </dd>
          {#if trace.warehouse_code && trace.warehouse_code !== trace.warehouse_name}
            <dd class="text-xs text-foreground-muted">{trace.warehouse_code}</dd>
          {/if}
        </div>
        <div class="rounded-xl bg-surface-muted/40 p-4">
          <dt class="text-xs text-foreground-muted">Lote / vencimiento</dt>
          <dd class="mt-1 font-semibold text-foreground">
            {trace.receipt_lot_code ?? trace.lot_code ?? 'Sin lote registrado'}
          </dd>
          <dd class="text-xs text-foreground-muted">{dateOnly(trace.expiry_date)}</dd>
        </div>
      </dl>
    </section>

    <section class="rounded-2xl border border-primary/30 bg-primary/5 p-5 sm:p-7">
      <h2 class="text-lg font-semibold text-foreground">Origen de compra</h2>
      {#if !trace.origin.supplier_name && !trace.origin.purchase_code && !trace.origin.purchase_order_code}
        <p
          class="mt-3 rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-foreground-muted"
        >
          Esta unidad está registrada en inventario, pero no tiene una recepción o lote de compra
          enlazado. El origen no está disponible.
        </p>
      {/if}
      <dl class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <dt class="text-xs text-foreground-muted">Proveedor</dt>
          <dd class="mt-1 font-medium text-foreground">
            {trace.origin.supplier_name ?? 'No enlazado'}
          </dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Orden de compra</dt>
          <dd class="mt-1 font-medium text-foreground">
            {trace.origin.purchase_order_code ?? 'No enlazada'}
          </dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Compra / recepción</dt>
          <dd class="mt-1 font-medium text-foreground">
            {trace.origin.purchase_code ?? 'No enlazada'}
          </dd>
          <dd class="text-xs text-foreground-muted">
            Recibido: {dateTime(trace.origin.received_at)}
          </dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Consolidado</dt>
          <dd class="mt-1 font-medium text-foreground">
            {trace.origin.consolidation_code ?? 'No enlazado'}
          </dd>
        </div>
      </dl>
    </section>

    <section class="rounded-2xl border border-border bg-surface p-5 sm:p-7">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 class="text-lg font-semibold text-foreground">Movimientos</h2>
          <p class="mt-1 text-sm text-foreground-muted">
            Historial registrado para esta unidad y sus divisiones.
          </p>
        </div>
        <Badge variant="neutral">{trace.movements.length} movimiento(s)</Badge>
      </div>

      {#if trace.movements.length}
        <ol class="mt-5 space-y-3">
          {#each trace.movements as movement, index (`${movement.posted_at}-${index}`)}
            <li class="rounded-xl border border-border bg-surface-muted/20 p-4">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p class="font-semibold text-foreground">
                    {movementLabel(movement.movement_type)}
                  </p>
                  <p class="mt-1 text-xs text-foreground-muted">{dateTime(movement.posted_at)}</p>
                </div>
                <p class="font-mono text-sm font-semibold text-primary">
                  {quantity(movement.quantity_base, trace.base_unit_symbol)}
                </p>
              </div>
              <dl class="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt class="text-xs text-foreground-muted">Origen</dt>
                  <dd class="mt-1 text-foreground">
                    {place(
                      movement.from_warehouse_name,
                      movement.from_warehouse_code,
                      movement.from_location_code
                    )}
                  </dd>
                  {#if movement.from_stock_status}
                    <dd class="text-xs text-foreground-muted">
                      {statusLabels[movement.from_stock_status]}
                    </dd>
                  {/if}
                </div>
                <div>
                  <dt class="text-xs text-foreground-muted">Destino</dt>
                  <dd class="mt-1 text-foreground">
                    {place(
                      movement.to_warehouse_name,
                      movement.to_warehouse_code,
                      movement.to_location_code
                    )}
                  </dd>
                  {#if movement.to_stock_status}
                    <dd class="text-xs text-foreground-muted">
                      {statusLabels[movement.to_stock_status]}
                    </dd>
                  {/if}
                </div>
              </dl>
            </li>
          {/each}
        </ol>
      {:else}
        <p class="mt-5 rounded-xl bg-surface-muted/30 p-4 text-sm text-foreground-muted">
          Aún no hay movimientos registrados para esta unidad.
        </p>
      {/if}
    </section>
  {/if}

  <footer class="px-1 pb-4 text-xs text-foreground-muted">
    El acceso de esta ficha depende del QR. El encargado puede revocar los enlaces de una unidad si
    la etiqueta se pierde o se comparte por error.
  </footer>
</main>
