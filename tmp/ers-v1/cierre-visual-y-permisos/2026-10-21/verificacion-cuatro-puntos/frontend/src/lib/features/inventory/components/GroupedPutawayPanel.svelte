<script lang="ts">
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { listLocations } from '$lib/features/locations/services';
  import type { LocationOut } from '$lib/features/locations/types';
  import { inventoryApi } from '../services';
  import type { InventoryReceiptLot, LegacyInventoryStock, ReceiptLotLine } from '../types';
  import {
    buildPutawayAllocations,
    subtractBaseQuantities,
    sumBaseQuantities,
    type PutawayDestinationPlan
  } from '../putaway-group';

  interface Props {
    warehouseId: string;
    onconfirmed?: () => void;
  }

  let { warehouseId, onconfirmed }: Props = $props();

  const inputClass =
    'mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  let lots = $state<InventoryReceiptLot[]>([]);
  let legacyStock = $state<LegacyInventoryStock[]>([]);
  let selectedLotId = $state('');
  let selectedItemId = $state('');
  let productScan = $state('');
  let locationScan = $state('');
  let selectedLocationId = $state('');
  let quantityToPlace = $state('');
  let destinationPlan = $state<PutawayDestinationPlan[]>([]);
  let locations = $state<LocationOut[]>([]);
  let page = $state(1);
  let pages = $state(1);
  let sequence = 0;
  let locationSequence = 0;
  let idempotencyKey: string | null = null;
  let loading = $state(true);
  let locationsLoading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let locationError = $state<string | null>(null);
  let planError = $state<string | null>(null);
  let success = $state<string | null>(null);
  let quarantinedUnits = $state<Array<{ id: string; code: string }>>([]);
  let productScanInput = $state<HTMLInputElement | null>(null);
  let locationScanInput = $state<HTMLInputElement | null>(null);

  let selectedLot = $derived(lots.find((lot) => lot.id === selectedLotId) ?? null);
  let pendingLines = $derived(
    (selectedLot?.lines ?? []).filter((line) =>
      hasPositiveQuantity(line.pending_placement_quantity_base)
    )
  );
  let selectedLine = $derived(
    pendingLines.find((line) => line.inventory_lot_detail_id === selectedItemId) ?? null
  );
  let pendingTotal = $derived(
    selectedLine ? sumBaseQuantities([selectedLine.pending_placement_quantity_base]) : '0'
  );
  let plannedTotal = $derived(
    sumBaseQuantities(destinationPlan.map((destination) => destination.quantity_base)) ?? '0'
  );
  let locationOptions = $derived(
    locations
      .filter(
        (location) =>
          location.is_active && location.storage_eligible && location.lifecycle_status === 'active'
      )
      .sort((left, right) => left.code.localeCompare(right.code, 'es-SV'))
  );

  function hasPositiveQuantity(value: string | number | null | undefined): boolean {
    if (value == null) return false;
    const quantity = Number(value);
    return Number.isFinite(quantity) && quantity > 0;
  }

  function formatQuantity(value: string | number | null | undefined): string {
    if (value == null) return '—';
    const exact = sumBaseQuantities([value]);
    if (exact == null) return '—';
    const [whole = '0', fraction = ''] = exact.split('.');
    const formattedWhole = new Intl.NumberFormat('es-SV', { maximumFractionDigits: 0 }).format(
      BigInt(whole)
    );
    return fraction ? `${formattedWhole}.${fraction}` : formattedWhole;
  }

  function receiptDate(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Fecha no disponible';
    return new Intl.DateTimeFormat('es-SV', {
      dateStyle: 'short',
      timeZone: 'America/El_Salvador'
    }).format(date);
  }

  function receiptDateTime(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Fecha no disponible';
    return new Intl.DateTimeFormat('es-SV', {
      dateStyle: 'short',
      timeStyle: 'short',
      timeZone: 'America/El_Salvador'
    }).format(date);
  }

  function normalizeScan(value: string): string {
    return value.trim().toLocaleUpperCase('es-SV');
  }

  function resetPlan() {
    destinationPlan = [];
    quantityToPlace = '';
    planError = null;
    success = null;
    quarantinedUnits = [];
    idempotencyKey = null;
  }

  function selectReceiptLot(lotId: string) {
    selectedLotId = lotId;
    selectedItemId = '';
    productScan = '';
    locationScan = '';
    selectedLocationId = '';
    resetPlan();
  }

  function selectReceiptProduct(itemId: string) {
    selectedItemId = itemId;
    productScan = '';
    resetPlan();
    if (itemId) queueMicrotask(() => locationScanInput?.focus());
  }

  function acceptProductScan() {
    const scanned = normalizeScan(productScan);
    if (!scanned) return;
    const matches = pendingLines.filter(
      (line) =>
        normalizeScan(line.receipt_lot_detail_code) === scanned ||
        normalizeScan(line.product_sku ?? '') === scanned
    );
    if (matches.length > 1) {
      planError = 'Este producto tiene varias líneas de recepción. Escanee el código de lote de recepción o seleccione la línea exacta.';
      return;
    }
    const match = matches[0];
    if (!match) {
      planError = `El código ${productScan.trim()} no pertenece a los productos pendientes de esta recepción.`;
      return;
    }
    selectedItemId = match.inventory_lot_detail_id;
    productScan = '';
    resetPlan();
    queueMicrotask(() => locationScanInput?.focus());
  }

  function acceptLocationScan() {
    const scanned = normalizeScan(locationScan);
    if (!scanned) return;
    const match = locationOptions.find(
      (location) =>
        normalizeScan(location.code) === scanned ||
        normalizeScan(location.barcode ?? '') === scanned
    );
    if (!match) {
      locationError = `La ubicación ${locationScan.trim()} no está activa y habilitada para almacenamiento en esta bodega.`;
      return;
    }
    selectedLocationId = match.id;
    locationScan = '';
    locationError = null;
    idempotencyKey = null;
    queueMicrotask(() => document.getElementById('group-putaway-quantity')?.focus());
  }

  function destinationLabel(locationId: string): string {
    const location = locationOptions.find((candidate) => candidate.id === locationId);
    return location?.code ?? 'Ubicación retirada';
  }

  function sourceUnits(line: ReceiptLotLine) {
    return line.handling_units
      .filter((unit) => hasPositiveQuantity(unit.pending_placement_quantity_base))
      .map((unit) => ({
        id: unit.id,
        code: unit.code,
        pending_quantity_base: unit.pending_placement_quantity_base
      }));
  }

  function addDestination() {
    planError = null;
    success = null;
    if (!selectedLine) {
      planError = 'Escanee o seleccione primero el producto recibido.';
      return;
    }
    if (
      !selectedLocationId ||
      !locationOptions.some((location) => location.id === selectedLocationId)
    ) {
      planError = 'Seleccione o escanee una ubicación activa apta para almacenamiento.';
      return;
    }
    const quantity = quantityToPlace.trim();
    const proposed = [
      ...destinationPlan,
      {
        destination_location_id: selectedLocationId,
        quantity_base: quantity
      }
    ];
    const allocationCheck = buildPutawayAllocations(sourceUnits(selectedLine), proposed);
    if (allocationCheck.error) {
      planError = allocationCheck.error;
      return;
    }
    const existingIndex = destinationPlan.findIndex(
      (destination) => destination.destination_location_id === selectedLocationId
    );
    destinationPlan =
      existingIndex < 0
        ? proposed
        : destinationPlan.map((destination, index) =>
            index === existingIndex
              ? {
                  ...destination,
                  quantity_base:
                    sumBaseQuantities([destination.quantity_base, quantity]) ?? quantity
                }
              : destination
          );
    quantityToPlace = '';
    locationScan = '';
    idempotencyKey = null;
  }

  function removeDestination(index: number) {
    destinationPlan = destinationPlan.filter((_, itemIndex) => itemIndex !== index);
    idempotencyKey = null;
    planError = null;
    success = null;
  }

  async function loadLots(requestedWarehouseId: string, requestedPage: number, request: number) {
    loading = true;
    error = null;
    try {
      let result = await inventoryApi.listReceiptLots({
        warehouseId: requestedWarehouseId,
        status: 'pending_placement',
        page: requestedPage,
        size: 20
      });
      let lastPage = Math.max(1, Math.ceil(result.total / result.size));
      let pageToShow = requestedPage;
      if (requestedPage > lastPage) {
        pageToShow = lastPage;
        result = await inventoryApi.listReceiptLots({
          warehouseId: requestedWarehouseId,
          status: 'pending_placement',
          page: pageToShow,
          size: 20
        });
        lastPage = Math.max(1, Math.ceil(result.total / result.size));
      }
      if (request !== sequence) return;
      lots = result.items;
      legacyStock = result.legacy_stock ?? [];
      pages = lastPage;
      page = pageToShow;
      if (!result.items.some((lot) => lot.id === selectedLotId)) {
        selectedLotId = result.items[0]?.id ?? '';
        selectedItemId = '';
        resetPlan();
      }
    } catch (cause) {
      if (request !== sequence) return;
      lots = [];
      legacyStock = [];
      error =
        cause instanceof Error
          ? cause.message
          : 'No se pudieron cargar las recepciones pendientes.';
    } finally {
      if (request === sequence) loading = false;
    }
  }

  async function loadLocations(requestedWarehouseId: string, request: number) {
    locationsLoading = true;
    locationError = null;
    try {
      const all: LocationOut[] = [];
      let currentPage = 1;
      let totalPages = 1;
      do {
        const response = await listLocations(requestedWarehouseId, {
          page: currentPage,
          size: 100
        });
        all.push(...response.items);
        totalPages = Math.max(1, response.meta.pages);
        currentPage += 1;
      } while (currentPage <= totalPages);
      if (request === locationSequence) locations = all;
    } catch (cause) {
      if (request === locationSequence) {
        locations = [];
        locationError =
          cause instanceof Error ? cause.message : 'No se pudieron cargar las ubicaciones.';
      }
    } finally {
      if (request === locationSequence) locationsLoading = false;
    }
  }

  $effect(() => {
    const currentWarehouseId = warehouseId;
    const request = ++sequence;
    const locationsRequest = ++locationSequence;
    page = 1;
    selectedLotId = '';
    selectedItemId = '';
    productScan = '';
    locationScan = '';
    selectedLocationId = '';
    resetPlan();
    void loadLots(currentWarehouseId, 1, request);
    void loadLocations(currentWarehouseId, locationsRequest);
  });

  async function confirmGroup() {
    if (!selectedLot || !selectedLine || saving) return;
    const plan = buildPutawayAllocations(sourceUnits(selectedLine), destinationPlan);
    if (plan.allocations === null) {
      planError = plan.error;
      return;
    }

    planError = null;
    error = null;
    success = null;
    saving = true;
    const attemptKey = idempotencyKey ?? crypto.randomUUID();
    idempotencyKey = attemptKey;
    try {
      const result = await inventoryApi.confirmPutawayGroup({
        idempotency_key: attemptKey,
        receipt_lot_id: selectedLot.id,
        inventory_lot_detail_id: selectedLine.inventory_lot_detail_id,
        inventory_item_id: selectedLine.inventory_item_id,
        allocations: plan.allocations
      });
      const total = formatQuantity(result.total_quantity_base);
      const quarantineCount = result.allocations.filter(
        (allocation) => allocation.stock_status === 'quarantine'
      ).length;
      const successMessage =
        quarantineCount > 0
          ? `${total} unidades base ubicadas. ${quarantineCount} unidad(es) quedan en cuarentena hasta completar sus revisiones de medidas, etiqueta y costo.`
          : `${total} unidades base ubicadas y disponibles.`;
      const unitsNeedingReview = result.allocations
        .filter((allocation) => allocation.stock_status === 'quarantine')
        .map((allocation) => ({
          id: allocation.handling_unit_id,
          code: allocation.handling_unit_code
        }));
      selectedItemId = '';
      productScan = '';
      resetPlan();
      const refreshRequest = ++sequence;
      await loadLots(warehouseId, page, refreshRequest);
      success = successMessage;
      quarantinedUnits = unitsNeedingReview;
      onconfirmed?.();
    } catch (cause) {
      error =
        cause instanceof Error ? cause.message : 'No se pudo confirmar la ubicación del grupo.';
    } finally {
      saving = false;
    }
  }

  function goToPage(nextPage: number) {
    if (nextPage < 1 || nextPage > pages || loading) return;
    selectedItemId = '';
    resetPlan();
    const request = ++sequence;
    void loadLots(warehouseId, nextPage, request);
  }
</script>

<section
  class="rounded-xl border border-border bg-surface p-4 sm:p-5"
  aria-labelledby="group-putaway-title"
>
  <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
    <div>
      <div class="flex flex-wrap items-center gap-2">
        <h3 id="group-putaway-title" class="text-base font-semibold text-foreground">
          Colocación por grupo
        </h3>
        {#if !loading}<Badge variant="neutral">{lots.length} recepción(es) pendientes</Badge>{/if}
      </div>
      <p class="mt-1 max-w-3xl text-sm leading-5 text-foreground-muted">
        Seleccione una recepción, escanee el producto y reparta su cantidad entre ubicaciones. La
        colocación no vuelve a recibir ni suma mercancía.
      </p>
    </div>
    <Button
      type="button"
      variant="secondary"
      size="sm"
      onclick={() => {
        const request = ++sequence;
        void loadLots(warehouseId, page, request);
      }}
      disabled={loading || saving}
    >
      {loading ? 'Actualizando…' : 'Actualizar pendientes'}
    </Button>
  </div>

  {#if success}
    <div class="mt-4 space-y-2 rounded-lg border border-success/30 bg-success/10 p-3">
      <p class="text-sm text-success" role="status">{success}</p>
      {#if quarantinedUnits.length > 0}
        <ul class="space-y-1 text-sm" aria-label="Unidades pendientes de revisión">
          {#each quarantinedUnits as unit (unit.id)}
            <li>
              <a
                class="font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                href="/warehouses/{encodeURIComponent(
                  warehouseId
                )}?tab=inventario&handling_unit={encodeURIComponent(unit.id)}"
              >
                Revisar unidad {unit.code}
              </a>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}

  {#if !loading && legacyStock.length > 0}
    <aside class="mt-4 rounded-lg border border-warning/30 bg-warning/5 p-3" aria-labelledby="legacy-stock-title">
      <h4 id="legacy-stock-title" class="text-sm font-semibold text-foreground">
        Existencia histórica sin lote de recepción atribuible
      </h4>
      <p class="mt-1 text-xs text-foreground-muted">
        El saldo total se toma de inventario y se concilia con las unidades que sí tienen una línea de recepción. No se asigna un origen a los registros antiguos.
      </p>
      <ul class="mt-3 space-y-2">
        {#each legacyStock as row (`${row.location_id}-${row.inventory_item_id}-${row.stock_status}`)}
          <li class="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-surface px-3 py-2 text-xs">
            <span class="font-medium text-foreground">{row.product_name}{row.product_sku ? ` · ${row.product_sku}` : ''} · {row.location_code ?? 'Ubicación no disponible'} · {row.stock_status}</span>
            <span class="tabular-nums text-foreground-muted">
              Legado {row.legacy_quantity_base} {row.base_unit_symbol} / total {row.total_quantity_base}
              {#if row.legacy_handling_unit_count > 0} · {row.legacy_handling_unit_count} HU sin línea{/if}
              {#if !row.reconciled} · diferencia {row.reconciliation_difference}{/if}
            </span>
          </li>
        {/each}
      </ul>
    </aside>
  {/if}

  {#if error}
    <p
      class="mt-4 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
      role="alert"
    >
      {error}
    </p>
    <Button
      class="mt-3"
      type="button"
      variant="secondary"
      size="sm"
      onclick={() => {
        const request = ++sequence;
        void loadLots(warehouseId, page, request);
      }}>Reintentar</Button
    >
  {:else if loading}
    <div class="mt-4 space-y-3" aria-label="Cargando recepciones" role="status">
      <div class="h-10 animate-pulse rounded-lg bg-surface-hover"></div>
      <div class="h-24 animate-pulse rounded-lg bg-surface-hover"></div>
    </div>
  {:else if lots.length === 0}
    <div class="mt-4 rounded-lg border border-dashed border-border px-4 py-8 text-center">
      <p class="text-sm font-medium text-foreground">No hay recepciones pendientes de ubicación</p>
      <p class="mt-1 text-xs text-foreground-muted">
        Las ubicaciones confirmadas aparecerán en el inventario de esta bodega.
      </p>
    </div>
  {:else}
    <div class="mt-4 grid gap-4 xl:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.6fr)]">
      <div class="space-y-4">
        <label class="block text-xs font-medium text-foreground-muted" for="group-putaway-lot">
          Recepción
          <select
            id="group-putaway-lot"
            class={inputClass}
            value={selectedLotId}
            disabled={saving}
            onchange={(event) => selectReceiptLot((event.currentTarget as HTMLSelectElement).value)}
          >
            <option value="">Seleccione una recepción</option>
            {#each lots as lot (lot.id)}
              <option value={lot.id}
                >{lot.code} · {lot.purchase_code} · {receiptDate(lot.received_at)}</option
              >
            {/each}
          </select>
        </label>

        {#if selectedLot}
          <div class="rounded-lg border border-border bg-surface-subtle p-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p class="font-mono text-sm font-semibold text-primary">{selectedLot.code}</p>
                <p class="mt-1 text-xs text-foreground-muted">
                  Compra {selectedLot.purchase_code} · {receiptDateTime(selectedLot.received_at)}
                </p>
              </div>
              <Badge
                variant={selectedLot.placement_status === 'partially_placed'
                  ? 'warning'
                  : 'neutral'}
              >
                {selectedLot.placement_status === 'partially_placed' ? 'Parcial' : 'Pendiente'}
              </Badge>
            </div>
            <p class="mt-3 text-xs font-medium text-foreground-muted">
              Productos en esta recepción
            </p>
            <ul class="mt-2 space-y-2">
              {#each selectedLot.lines as line (line.inventory_item_id)}
                <li class="rounded-md border border-border px-3 py-2">
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                      <p class="truncate text-sm font-medium text-foreground">
                        {line.product_name}
                      </p>
                      <p class="mt-0.5 font-mono text-[11px] text-foreground-muted">
                        {line.product_sku ?? 'Sin código interno'}
                      </p>
                    </div>
                    <p class="shrink-0 text-right font-mono text-xs tabular-nums text-foreground">
                      {formatQuantity(line.pending_placement_quantity_base)}
                      <span class="text-foreground-muted">pend.</span>
                    </p>
                  </div>
                  <div
                    class="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-foreground-muted"
                  >
                    <span
                      >Recibido {formatQuantity(line.accepted_quantity_base)}
                      {line.base_unit_symbol ?? 'unid.'}</span
                    >
                    <span>Ubicado {formatQuantity(line.placed_quantity_base)}</span>
                    <span>Pendiente {formatQuantity(line.pending_placement_quantity_base)}</span>
                  </div>
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if pages > 1}
          <nav
            class="flex items-center justify-between gap-3"
            aria-label="Páginas de recepciones pendientes"
          >
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={page <= 1 || loading}
              onclick={() => goToPage(page - 1)}>Anterior</Button
            >
            <span class="text-xs text-foreground-muted">Página {page} de {pages}</span>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={page >= pages || loading}
              onclick={() => goToPage(page + 1)}>Siguiente</Button
            >
          </nav>
        {/if}
      </div>

      <div class="space-y-4">
        <div class="grid gap-3 md:grid-cols-2">
          <label
            class="block text-xs font-medium text-foreground-muted"
            for="group-putaway-product-scan"
          >
            Escanear código del producto
            <input
              bind:this={productScanInput}
              id="group-putaway-product-scan"
              class={inputClass}
              value={productScan}
              placeholder="Escanee el SKU y presione Enter"
              autocomplete="off"
              disabled={!selectedLot || saving || pendingLines.length === 0}
              oninput={(event) => (productScan = (event.currentTarget as HTMLInputElement).value)}
              onkeydown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  acceptProductScan();
                }
              }}
            />
          </label>
          <label
            class="block text-xs font-medium text-foreground-muted"
            for="group-putaway-product"
          >
            Producto pendiente
            <select
              id="group-putaway-product"
              class={inputClass}
              value={selectedItemId}
              disabled={!selectedLot || saving || pendingLines.length === 0}
              onchange={(event) =>
                selectReceiptProduct((event.currentTarget as HTMLSelectElement).value)}
            >
              <option value="">Seleccione producto</option>
              {#each pendingLines as line (line.inventory_lot_detail_id)}
                <option value={line.inventory_lot_detail_id}
                  >{line.product_sku ?? 'Sin código'} · {line.product_name} · {line.receipt_lot_detail_code}</option
                >
              {/each}
            </select>
          </label>
        </div>

        {#if selectedLine}
          <div class="rounded-lg border border-primary/30 bg-primary/5 p-3">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p class="text-sm font-semibold text-foreground">{selectedLine.product_name}</p>
                <p class="mt-0.5 font-mono text-xs text-primary">
                  {selectedLine.product_sku ?? 'Sin código interno'} · {selectedLine.receipt_lot_detail_code}
                </p>
              </div>
              <Badge variant="primary"
                >{formatQuantity(selectedLine.pending_placement_quantity_base)}
                {selectedLine.base_unit_symbol ?? 'unid.'} pendientes</Badge
              >
            </div>
            <div class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <div class="rounded-md bg-surface px-2.5 py-2">
                <p class="text-[10px] uppercase text-foreground-muted">Recibido</p>
                <p class="mt-1 font-mono text-sm tabular-nums">
                  {formatQuantity(selectedLine.accepted_quantity_base)}
                </p>
              </div>
              <div class="rounded-md bg-surface px-2.5 py-2">
                <p class="text-[10px] uppercase text-foreground-muted">Ya ubicado</p>
                <p class="mt-1 font-mono text-sm tabular-nums">
                  {formatQuantity(selectedLine.placed_quantity_base)}
                </p>
              </div>
              <div class="rounded-md bg-surface px-2.5 py-2">
                <p class="text-[10px] uppercase text-foreground-muted">En este plan</p>
                <p class="mt-1 font-mono text-sm tabular-nums">{formatQuantity(plannedTotal)}</p>
              </div>
              <div class="rounded-md bg-surface px-2.5 py-2">
                <p class="text-[10px] uppercase text-foreground-muted">Quedará pendiente</p>
                <p class="mt-1 font-mono text-sm tabular-nums">
                  {formatQuantity(subtractBaseQuantities(pendingTotal ?? '0', plannedTotal) ?? '0')}
                </p>
              </div>
            </div>
          </div>

          {#if destinationPlan.length > 0}
            <section
              class="overflow-hidden rounded-xl border border-primary/40 bg-primary/5 shadow-sm"
              aria-label="Reparto que se confirmará"
              aria-live="polite"
            >
              <div
                class="flex flex-wrap items-center justify-between gap-3 border-b border-primary/20 bg-primary/10 px-4 py-3"
              >
                <div>
                  <h3 class="text-sm font-semibold text-foreground">Revisa el reparto</h3>
                  <p class="mt-0.5 text-xs text-foreground-muted">
                    Confirma que cada destino y cantidad sean correctos.
                  </p>
                </div>
                <Badge variant="primary"
                  >{destinationPlan.length} destinos · {formatQuantity(plannedTotal)}
                  {selectedLine.base_unit_symbol ?? 'unid.'}</Badge
                >
              </div>
              <ul class="divide-y divide-primary/15">
                {#each destinationPlan as destination, index (destination.destination_location_id)}
                  <li class="flex items-center justify-between gap-3 px-4 py-3">
                    <div class="min-w-0">
                      <p class="text-sm font-semibold text-foreground">
                        {destinationLabel(destination.destination_location_id)}
                      </p>
                      <p class="mt-0.5 font-mono text-sm font-medium tabular-nums text-primary">
                        {formatQuantity(destination.quantity_base)}
                        {selectedLine.base_unit_symbol ?? 'unid.'}
                      </p>
                    </div>
                    <button
                      type="button"
                      class="rounded-md px-2 py-1 text-xs text-danger hover:bg-danger/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-danger"
                      disabled={saving}
                      aria-label={`Quitar ${destinationLabel(destination.destination_location_id)} del plan`}
                      onclick={() => removeDestination(index)}>Quitar</button
                    >
                  </li>
                {/each}
              </ul>
            </section>
          {/if}

          <div
            class="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(180px,0.7fr)_140px_auto] md:items-end"
          >
            <label
              class="block text-xs font-medium text-foreground-muted"
              for="group-putaway-location-scan"
            >
              Escanear ubicación
              <input
                bind:this={locationScanInput}
                id="group-putaway-location-scan"
                class={inputClass}
                value={locationScan}
                placeholder="Código de ubicación"
                autocomplete="off"
                disabled={saving || locationOptions.length === 0}
                oninput={(event) => {
                  locationScan = (event.currentTarget as HTMLInputElement).value;
                  locationError = null;
                }}
                onkeydown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    acceptLocationScan();
                  }
                }}
              />
            </label>
            <label
              class="block text-xs font-medium text-foreground-muted"
              for="group-putaway-location"
            >
              Destino habilitado
              <select
                id="group-putaway-location"
                class={inputClass}
                value={selectedLocationId}
                disabled={saving || locationsLoading || locationOptions.length === 0}
                onchange={(event) => {
                  selectedLocationId = (event.currentTarget as HTMLSelectElement).value;
                  locationError = null;
                  idempotencyKey = null;
                }}
              >
                <option value="">{locationsLoading ? 'Cargando…' : 'Seleccione destino'}</option>
                {#each locationOptions as location (location.id)}
                  <option value={location.id}>{location.code} · {location.location_type}</option>
                {/each}
              </select>
            </label>
            <label
              class="block text-xs font-medium text-foreground-muted"
              for="group-putaway-quantity"
            >
              Cantidad base
              <input
                id="group-putaway-quantity"
                class={inputClass}
                type="number"
                min="0.000001"
                step="0.000001"
                max={pendingTotal ?? undefined}
                value={quantityToPlace}
                disabled={!selectedLocationId || saving}
                oninput={(event) =>
                  (quantityToPlace = (event.currentTarget as HTMLInputElement).value)}
                onkeydown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    addDestination();
                  }
                }}
              />
            </label>
            <Button
              type="button"
              variant="secondary"
              disabled={!selectedLocationId || !quantityToPlace || saving}
              onclick={addDestination}>Agregar destino</Button
            >
          </div>

          {#if locationError}
            <p class="text-sm text-danger" role="alert">{locationError}</p>
          {:else if locationOptions.length === 0 && !locationsLoading}
            <p class="text-sm text-warning">
              Esta bodega no tiene ubicaciones activas aptas para almacenamiento.
            </p>
          {/if}

          {#if destinationPlan.length > 0}
            <div
              class="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3"
            >
              <p class="max-w-xl text-xs leading-5 text-foreground-muted">
                La ubicación no vuelve a sumar cantidad al inventario. Si falta una revisión, la
                unidad queda en cuarentena y no se puede despachar como disponible.
              </p>
              <Button
                type="button"
                disabled={saving || destinationPlan.length === 0}
                onclick={() => void confirmGroup()}
              >
                {saving ? 'Confirmando ubicación…' : 'Confirmar ubicación del grupo'}
              </Button>
            </div>
          {/if}
        {:else if selectedLot}
          <div class="rounded-lg border border-dashed border-border px-4 py-8 text-center">
            <p class="text-sm font-medium text-foreground">Escanee o seleccione un producto</p>
            <p class="mt-1 text-xs text-foreground-muted">
              El sistema solo aceptará productos de esta recepción con cantidad pendiente.
            </p>
          </div>
        {/if}

        {#if planError}
          <p
            class="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
            role="alert"
          >
            {planError}
          </p>
        {/if}
      </div>
    </div>
  {/if}
</section>
