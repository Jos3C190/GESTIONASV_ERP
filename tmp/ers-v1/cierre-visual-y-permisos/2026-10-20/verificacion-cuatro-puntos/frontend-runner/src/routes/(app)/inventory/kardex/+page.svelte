<script lang="ts">
  import { page as appPage } from '$app/state';
  import { onDestroy } from 'svelte';
  import { untrack } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import KardexMovementDetails from '$lib/features/inventory/components/KardexMovementDetails.svelte';
  import PhysicalKardexList from '$lib/features/inventory/components/PhysicalKardexList.svelte';
  import KardexReconciliationList from '$lib/features/inventory/components/KardexReconciliationList.svelte';
  import ValuedKardexList from '$lib/features/inventory/components/ValuedKardexList.svelte';
  import { getWarehouses } from '$lib/services/warehouses';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { displayDecimal } from '$lib/features/inventory/valuation';
  import { kardexMoney } from '$lib/features/inventory/kardex-format';
  import {
    kardexApi,
    type KardexItemOption,
    type PhysicalKardex,
    type Reconciliation,
    type ValuedKardex
  } from '$lib/features/inventory/kardex';
  import type { Warehouse } from '$lib/features/warehouses/types';

  type View = 'physical' | 'valuation' | 'reconciliation';
  const canRead = $derived(permissions.hasPermission('inventory:read'));
  const canValue = $derived(
    permissions.hasPermission('inventory:valuation') && branch.accessAllBranches
  );
  const inputClass =
    'h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary';
  const tabClass = (active: boolean) =>
    `rounded-lg px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${active ? 'bg-primary/10 text-primary' : 'text-foreground-muted hover:bg-surface-muted hover:text-foreground'}`;

  let view = $state<View>('physical');
  let warehouses = $state<Warehouse[]>([]);
  let selectedWarehouse = $state('');
  let warehousesLoading = $state(false);
  let warehousesError = $state<string | null>(null);
  let itemQuery = $state('');
  let itemOptions = $state<KardexItemOption[]>([]);
  let itemSearchError = $state<string | null>(null);
  let selectedItemId = $state('');
  let selectedItemName = $state('');
  let itemSearchLoading = $state(false);
  let searchSequence = 0;
  let physicalRequestSequence = 0;
  let reconciliationRequestSequence = 0;
  let valuationRequestSequence = 0;
  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  let physicalData = $state<PhysicalKardex | null>(null);
  let selectedMovement = $state<PhysicalKardex['items'][number] | null>(null);
  let physicalLoading = $state(false);
  let physicalError = $state<string | null>(null);
  let reconciliation = $state<Reconciliation | null>(null);
  let reconciliationLoading = $state(false);
  let reconciliationError = $state<string | null>(null);
  let reconciliationPage = $state(1);
  let valuationData = $state<ValuedKardex | null>(null);
  let valuationLoading = $state(false);
  let valuationError = $state<string | null>(null);
  let valuationItemId = $state('');
  let valuationItemName = $state('');
  let valuationPage = $state(1);
  let page = $state(1);
  let periodFrom = $state(dateDaysAgo(29));
  let periodTo = $state(dateToday());
  let movementType = $state('');
  let lotCode = $state('');
  let sourceReference = $state('');
  let loadedCompany = '';
  let loadedBranch: string | null = null;
  let loadedCanValue = false;
  let loadedWarehouseSequence = 0;
  let restoredUrlContext = '';

  function dateToday(): string {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/El_Salvador',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).format(new Date());
  }

  function dateDaysAgo(days: number): string {
    const date = new Date(`${dateToday()}T12:00:00-06:00`);
    date.setDate(date.getDate() - days);
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/El_Salvador',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).format(date);
  }

  function number(value: string | null | undefined): string {
    return value == null ? '—' : displayDecimal(value, 3);
  }

  const money = kardexMoney;

  function errorMessage(cause: unknown, fallback: string): string {
    return cause instanceof Error ? cause.message : fallback;
  }

  function invalidatePhysical() {
    physicalRequestSequence++;
    physicalLoading = false;
    physicalData = null;
    selectedMovement = null;
    physicalError = null;
    page = 1;
  }

  function invalidateValuation() {
    valuationRequestSequence++;
    valuationLoading = false;
    valuationData = null;
    valuationError = null;
    valuationPage = 1;
  }

  function clearItemSearch() {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = null;
    searchSequence++;
    itemSearchLoading = false;
    itemQuery = '';
    itemOptions = [];
    itemSearchError = null;
    selectedItemId = '';
    selectedItemName = '';
  }

  function invalidateReconciliation() {
    reconciliationRequestSequence++;
    reconciliationLoading = false;
    reconciliation = null;
    reconciliationError = null;
    reconciliationPage = 1;
  }

  function physicalIdentity(): string {
    return JSON.stringify([
      company.id,
      branch.id,
      selectedWarehouse,
      selectedItemId,
      periodFrom,
      periodTo,
      movementType,
      lotCode.trim(),
      sourceReference.trim(),
      page,
      25
    ]);
  }

  async function loadWarehouses() {
    const sequence = ++loadedWarehouseSequence;
    const companyId = company.id;
    const branchId = branch.id;
    warehousesLoading = true;
    warehousesError = null;
    try {
      const all: Warehouse[] = [];
      let pageNumber = 1;
      let pages = 1;
      do {
        const result = await getWarehouses({
          branchId: branchId ?? undefined,
          page: pageNumber,
          size: 100,
          status: 'active'
        });
        if (
          sequence !== loadedWarehouseSequence ||
          companyId !== company.id ||
          branchId !== branch.id
        )
          return;
        all.push(...result.items);
        pages = Math.max(1, result.meta.pages);
        pageNumber += 1;
      } while (pageNumber <= pages);
      if (
        sequence !== loadedWarehouseSequence ||
        companyId !== company.id ||
        branchId !== branch.id
      )
        return;
      warehouses = all.filter((warehouse) => warehouse.status === 'active');
      const requestedWarehouse = new URL(appPage.url).searchParams.get('warehouse_id');
      if (requestedWarehouse && warehouses.some((warehouse) => warehouse.id === requestedWarehouse)) {
        selectedWarehouse = requestedWarehouse;
      }
      if (!warehouses.some((warehouse) => warehouse.id === selectedWarehouse)) {
        selectedWarehouse = warehouses[0]?.id ?? '';
        clearItemSearch();
        invalidatePhysical();
        invalidateValuation();
        valuationItemId = '';
        valuationItemName = '';
      }
      await restoreUrlContext(sequence, companyId, branchId);
    } catch (cause) {
      if (
        sequence === loadedWarehouseSequence &&
        companyId === company.id &&
        branchId === branch.id
      )
        warehousesError = errorMessage(cause, 'No se pudieron consultar las bodegas autorizadas.');
    } finally {
      if (
        sequence === loadedWarehouseSequence &&
        companyId === company.id &&
        branchId === branch.id
      )
        warehousesLoading = false;
    }
  }

  async function restoreUrlContext(sequence: number, companyId: string | null, branchId: string | null) {
    const href = appPage.url.href;
    const contextKey = `${companyId ?? ''}:${branchId ?? ''}:${href}`;
    const params = new URL(href).searchParams;
    const requestedItemId = params.get('inventory_item_id');
    if (!requestedItemId || contextKey === restoredUrlContext || !selectedWarehouse) return;
    restoredUrlContext = contextKey;

    const periodStart = params.get('period_from');
    const periodEnd = params.get('period_to');
    if (periodStart && /^\d{4}-\d{2}-\d{2}$/.test(periodStart)) periodFrom = periodStart;
    if (periodEnd && /^\d{4}-\d{2}-\d{2}$/.test(periodEnd)) periodTo = periodEnd;
    movementType = params.get('movement_type') ?? '';
    lotCode = params.get('lot_code') ?? '';
    sourceReference = params.get('source_reference') ?? '';
    const searchTerm = params.get('product_name')?.trim() || params.get('sku')?.trim() || requestedItemId;
    itemSearchLoading = true;
    itemSearchError = null;
    try {
      const results = await kardexApi.searchItems(selectedWarehouse, searchTerm);
      if (sequence !== loadedWarehouseSequence || companyId !== company.id || branchId !== branch.id || href !== appPage.url.href) return;
      const match = results.find((item) => item.inventory_item_id === requestedItemId);
      if (!match) {
        itemSearchError = 'El artículo del movimiento no aparece dentro de la bodega y el alcance seleccionados.';
        return;
      }
      itemOptions = results;
      selectedItemId = match.inventory_item_id;
      selectedItemName = match.product_name;
      itemQuery = match.sku ? `${match.product_name} · ${match.sku}` : match.product_name;
      await loadPhysical(1);
    } catch (cause) {
      if (sequence === loadedWarehouseSequence && companyId === company.id && branchId === branch.id)
        itemSearchError = errorMessage(cause, 'No se pudo abrir el movimiento enlazado.');
    } finally {
      if (sequence === loadedWarehouseSequence && companyId === company.id && branchId === branch.id)
        itemSearchLoading = false;
    }
  }

  function searchItems(query: string) {
    invalidatePhysical();
    itemQuery = query;
    selectedItemId = '';
    selectedItemName = '';
    physicalData = null;
    selectedMovement = null;
    itemOptions = [];
    itemSearchError = null;
    if (searchTimer) clearTimeout(searchTimer);
    const sequence = ++searchSequence;
    const identity = JSON.stringify([
      company.id,
      branch.id,
      selectedWarehouse,
      searchTermFor(query)
    ]);
    if (!selectedWarehouse || query.trim().length < 2) {
      itemOptions = [];
      itemSearchLoading = false;
      return;
    }
    itemSearchLoading = true;
    const warehouseId = selectedWarehouse;
    const searchTerm = query.trim();
    searchTimer = setTimeout(async () => {
      try {
        const results = await kardexApi.searchItems(warehouseId, searchTerm);
        if (
          sequence === searchSequence &&
          identity ===
            JSON.stringify([company.id, branch.id, selectedWarehouse, searchTermFor(itemQuery)])
        ) {
          itemOptions = results;
          itemSearchError = null;
        }
      } catch (cause) {
        if (
          sequence === searchSequence &&
          identity ===
            JSON.stringify([company.id, branch.id, selectedWarehouse, searchTermFor(itemQuery)])
        )
          itemSearchError = errorMessage(cause, 'No se pudieron buscar artículos de esta bodega.');
      } finally {
        if (
          sequence === searchSequence &&
          identity ===
            JSON.stringify([company.id, branch.id, selectedWarehouse, searchTermFor(itemQuery)])
        )
          itemSearchLoading = false;
      }
    }, 250);
  }

  function searchTermFor(value: string): string {
    return value.trim();
  }

  function chooseItemFromQuery(query: string): boolean {
    const option = itemOptions.find(
      (entry) => (entry.sku ? `${entry.product_name} · ${entry.sku}` : entry.product_name) === query
    );
    if (!option) return false;
    chooseItem(option.inventory_item_id);
    return true;
  }

  function chooseItem(id: string) {
    const item = itemOptions.find((option) => option.inventory_item_id === id);
    if (!item) return;
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = null;
    searchSequence++;
    itemSearchLoading = false;
    selectedItemId = item.inventory_item_id;
    selectedItemName = item.product_name;
    itemSearchError = null;
    itemQuery = item.sku ? `${item.product_name} · ${item.sku}` : item.product_name;
    physicalData = null;
    page = 1;
  }

  async function loadPhysical(nextPage = 1) {
    if (!selectedWarehouse || !selectedItemId || periodFrom > periodTo) return;
    const sequence = ++physicalRequestSequence;
    const filters = {
      warehouse_id: selectedWarehouse,
      inventory_item_id: selectedItemId,
      period_from: periodFrom,
      period_to: periodTo,
      movement_type: movementType || undefined,
      lot_code: lotCode.trim() || undefined,
      source_reference: sourceReference.trim() || undefined,
      page: nextPage,
      page_size: 25
    };
    page = nextPage;
    const identity = physicalIdentity();
    physicalLoading = true;
    physicalError = null;
    try {
      const result = await kardexApi.physical(filters);
      if (sequence === physicalRequestSequence && identity === physicalIdentity())
        physicalData = result;
    } catch (cause) {
      if (sequence === physicalRequestSequence && identity === physicalIdentity())
        physicalError = errorMessage(cause, 'No se pudo consultar el historial de la bodega.');
    } finally {
      if (sequence === physicalRequestSequence && identity === physicalIdentity())
        physicalLoading = false;
    }
  }

  async function loadReconciliation(nextPage = 1) {
    const sequence = ++reconciliationRequestSequence;
    const identity = JSON.stringify([company.id, branch.id, canValue, nextPage, 50]);
    reconciliationPage = nextPage;
    reconciliationLoading = true;
    reconciliationError = null;
    try {
      const result = await kardexApi.reconciliation(reconciliationPage, 50);
      if (
        sequence === reconciliationRequestSequence &&
        identity === JSON.stringify([company.id, branch.id, canValue, reconciliationPage, 50])
      )
        reconciliation = result;
    } catch (cause) {
      if (
        sequence === reconciliationRequestSequence &&
        identity === JSON.stringify([company.id, branch.id, canValue, reconciliationPage, 50])
      )
        reconciliationError = errorMessage(cause, 'No se pudo conciliar el inventario.');
    } finally {
      if (
        sequence === reconciliationRequestSequence &&
        identity === JSON.stringify([company.id, branch.id, canValue, reconciliationPage, 50])
      )
        reconciliationLoading = false;
    }
  }

  async function showValued(itemId: string, name: string, nextPage = 1) {
    const sequence = ++valuationRequestSequence;
    valuationItemId = itemId;
    valuationItemName = name;
    valuationPage = nextPage;
    valuationData = null;
    const identity = valuationIdentity(itemId, nextPage);
    valuationLoading = true;
    valuationError = null;
    try {
      const result = await kardexApi.valued(itemId, {
        period_from: periodFrom,
        period_to: periodTo,
        page: nextPage,
        page_size: 25
      });
      if (sequence === valuationRequestSequence && identity === valuationIdentity(itemId, nextPage))
        valuationData = result;
    } catch (cause) {
      if (sequence === valuationRequestSequence && identity === valuationIdentity(itemId, nextPage))
        valuationError = errorMessage(cause, 'No se pudo consultar el Kardex valorado.');
    } finally {
      if (sequence === valuationRequestSequence && identity === valuationIdentity(itemId, nextPage))
        valuationLoading = false;
    }
  }

  function valuationIdentity(itemId: string, nextPage: number): string {
    return JSON.stringify([
      company.id,
      branch.id,
      canValue,
      itemId,
      periodFrom,
      periodTo,
      nextPage,
      25
    ]);
  }

  function changeView(next: View) {
    view = next;
    if (next === 'reconciliation' && canValue && !reconciliation) void loadReconciliation();
  }

  function handleTabKeydown(event: KeyboardEvent, current: View) {
    const views: View[] = canValue ? ['physical', 'valuation', 'reconciliation'] : ['physical'];
    const currentIndex = views.indexOf(current);
    let nextIndex: number | null = null;
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % views.length;
    if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + views.length) % views.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = views.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const nextView = views[nextIndex]!;
    changeView(nextView);
    requestAnimationFrame(() => document.getElementById(`kardex-tab-${nextView}`)?.focus());
  }

  $effect(() => {
    const companyId = company.id;
    const branchId = branch.id;
    const readAllowed = canRead;
    const valuationAllowed = canValue;
    const contextChanged =
      companyId !== loadedCompany ||
      branchId !== loadedBranch ||
      valuationAllowed !== loadedCanValue;
    if (companyId && readAllowed && contextChanged) {
      invalidatePhysical();
      invalidateValuation();
      invalidateReconciliation();
      clearItemSearch();
      selectedMovement = null;
      valuationItemId = '';
      valuationItemName = '';
      loadedCompany = companyId;
      loadedBranch = branchId;
      loadedCanValue = valuationAllowed;
      warehouses = [];
      physicalData = null;
      reconciliation = null;
      valuationData = null;
      if (!valuationAllowed) view = 'physical';
      untrack(() => void loadWarehouses());
    }
    if (!readAllowed) {
      loadedWarehouseSequence++;
      loadedCompany = '';
      loadedBranch = null;
      loadedCanValue = false;
      invalidatePhysical();
      invalidateValuation();
      invalidateReconciliation();
      clearItemSearch();
      selectedMovement = null;
      valuationItemId = '';
      valuationItemName = '';
      warehouses = [];
      physicalData = null;
      valuationData = null;
      if (searchTimer) clearTimeout(searchTimer);
    }
  });

  onDestroy(() => {
    loadedWarehouseSequence++;
    searchSequence++;
    physicalRequestSequence++;
    reconciliationRequestSequence++;
    valuationRequestSequence++;
    if (searchTimer) clearTimeout(searchTimer);
  });
</script>

<svelte:head><title>Kardex | GestionaSV</title></svelte:head>

<main class="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
  <header class="flex flex-wrap items-start justify-between gap-4">
    <div class="max-w-3xl">
      <p class="text-xs font-semibold uppercase tracking-[0.14em] text-primary">Inventario</p>
      <h1 class="mt-2 text-2xl font-semibold tracking-tight text-foreground">Kardex</h1>
      <p class="mt-2 text-sm leading-6 text-foreground-muted">
        Consulta cada movimiento físico por bodega y revisa los costos desde el registro de
        valoración de la empresa.
      </p>
    </div>
    {#if view === 'physical' && physicalData}
      <Button
        variant="secondary"
        disabled={physicalLoading}
        onclick={() => void loadPhysical(page)}
      >
        Actualizar consulta
      </Button>
    {:else if view === 'reconciliation' && canValue}
      <Button
        variant="secondary"
        disabled={reconciliationLoading}
        onclick={() => void loadReconciliation(reconciliationPage)}>Actualizar conciliación</Button
      >
    {/if}
  </header>

  {#if !canRead}
    <section class="rounded-xl border border-border bg-surface p-6">
      <h2 class="font-semibold text-foreground">Permiso de inventario requerido</h2>
      <p class="mt-2 text-sm text-foreground-muted">
        Solicita el permiso de consulta de inventario para ver movimientos de tus bodegas.
      </p>
    </section>
  {:else}
    <div
      class="flex flex-wrap gap-2 border-b border-border pb-3"
      role="tablist"
      aria-label="Vistas del Kardex"
      aria-orientation="horizontal"
    >
      <button
        id="kardex-tab-physical"
        class={tabClass(view === 'physical')}
        type="button"
        role="tab"
        aria-selected={view === 'physical'}
        aria-controls="kardex-panel"
        tabindex={view === 'physical' ? 0 : -1}
        onkeydown={(event) => handleTabKeydown(event, 'physical')}
        onclick={() => changeView('physical')}>Movimientos físicos</button
      >
      {#if canValue}
        <button
          id="kardex-tab-valuation"
          class={tabClass(view === 'valuation')}
          type="button"
          role="tab"
          aria-selected={view === 'valuation'}
          aria-controls="kardex-panel"
          tabindex={view === 'valuation' ? 0 : -1}
          onkeydown={(event) => handleTabKeydown(event, 'valuation')}
          onclick={() => changeView('valuation')}>Valoración</button
        >
        <button
          id="kardex-tab-reconciliation"
          class={tabClass(view === 'reconciliation')}
          type="button"
          role="tab"
          aria-selected={view === 'reconciliation'}
          aria-controls="kardex-panel"
          tabindex={view === 'reconciliation' ? 0 : -1}
          onkeydown={(event) => handleTabKeydown(event, 'reconciliation')}
          onclick={() => changeView('reconciliation')}>Conciliación</button
        >
      {/if}
    </div>

    {#if view === 'physical'}
      <!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role -->
      <section
        id="kardex-panel"
        role="tabpanel"
        tabindex="0"
        aria-labelledby="kardex-tab-physical"
        class="space-y-5 rounded-xl border border-border bg-surface p-4 sm:p-6"
      >
        <div>
          <h2 id="physical-title" class="text-lg font-semibold text-foreground">
            Movimientos de una bodega
          </h2>
          <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
            El saldo incluye todos los estados físicos. Cambiar una unidad de ubicación dentro de la
            misma bodega no aumenta sus existencias.
          </p>
        </div>
        {#if warehousesLoading}
          <div role="status" class="space-y-3">
            <p class="text-sm text-foreground-muted">Cargando bodegas autorizadas…</p>
            <div class="skeleton h-12 rounded-lg"></div>
          </div>
        {:else if warehousesError}
          <div class="rounded-lg border border-danger/30 bg-danger/10 p-4">
            <p role="alert" class="mb-3 text-sm text-danger">{warehousesError}</p>
            <Button variant="secondary" onclick={() => void loadWarehouses()}>Reintentar</Button>
          </div>
        {:else if warehouses.length === 0}
          <p
            class="rounded-lg border border-dashed border-border p-5 text-sm text-foreground-muted"
          >
            No hay bodegas activas dentro de tu alcance actual.
          </p>
        {:else}
          <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <label class="text-sm font-medium text-foreground" for="kardex-warehouse"
              >Bodega
              <select
                id="kardex-warehouse"
                class={`${inputClass} mt-1`}
                bind:value={selectedWarehouse}
                onchange={() => {
                  invalidatePhysical();
                  clearItemSearch();
                }}
              >
                {#each warehouses as warehouse (warehouse.id)}<option value={warehouse.id}
                    >{warehouse.code} · {warehouse.name}</option
                  >{/each}
              </select>
            </label>
            <label class="text-sm font-medium text-foreground" for="kardex-item"
              >Producto o SKU
              <input
                id="kardex-item"
                class={`${inputClass} mt-1`}
                list="kardex-item-options"
                autocomplete="off"
                value={itemQuery}
                oninput={(event) => {
                  const query = event.currentTarget.value;
                  if (!chooseItemFromQuery(query)) searchItems(query);
                }}
                onchange={() => chooseItemFromQuery(itemQuery)}
                placeholder="Escribe al menos dos caracteres"
              />
              <datalist id="kardex-item-options"
                >{#each itemOptions as option (option.inventory_item_id)}<option
                    value={option.sku
                      ? `${option.product_name} · ${option.sku}`
                      : option.product_name}
                  ></option>{/each}</datalist
              >
              {#if itemSearchLoading}<span
                  class="mt-1 block text-xs text-foreground-muted"
                  role="status">Buscando artículos…</span
                >{/if}
              {#if itemOptions.length === 0 && itemQuery.trim().length >= 2 && !itemSearchLoading && !itemSearchError}
                <span class="mt-1 block text-xs text-foreground-muted"
                  >No se encontraron artículos.</span
                >
              {/if}
              {#if selectedItemId}<span class="mt-1 block text-xs text-foreground-muted"
                  >{selectedItemName}</span
                >{/if}
            </label>
            <label class="text-sm font-medium text-foreground" for="kardex-from"
              >Desde
              <input
                id="kardex-from"
                type="date"
                class={`${inputClass} mt-1`}
                bind:value={periodFrom}
                oninput={() => {
                  invalidatePhysical();
                  invalidateValuation();
                }}
              />
            </label>
            <label class="text-sm font-medium text-foreground" for="kardex-to"
              >Hasta
              <input
                id="kardex-to"
                type="date"
                class={`${inputClass} mt-1`}
                bind:value={periodTo}
                oninput={() => {
                  invalidatePhysical();
                  invalidateValuation();
                }}
              />
            </label>
            <label class="text-sm font-medium text-foreground" for="kardex-type"
              >Tipo de movimiento
              <select
                id="kardex-type"
                class={`${inputClass} mt-1`}
                bind:value={movementType}
                onchange={invalidatePhysical}
              >
                <option value="">Todos los tipos</option><option value="receipt">Recepción</option
                ><option value="putaway">Ubicación</option><option value="transfer">Traslado</option
                ><option value="pick">Preparación de salida</option><option value="shipment"
                  >Despacho</option
                ><option value="adjustment_in">Ajuste de entrada</option><option
                  value="adjustment_out">Ajuste de salida</option
                ><option value="reversal">Reversión</option>
              </select>
            </label>
            <label class="text-sm font-medium text-foreground" for="kardex-lot"
              >Lote fabricante, recepción o cabecera (opcional)
              <input
                id="kardex-lot"
                class={`${inputClass} mt-1`}
                bind:value={lotCode}
                oninput={invalidatePhysical}
                maxlength="120"
                placeholder="Código de lote exacto"
              />
            </label>
            <label class="text-sm font-medium text-foreground" for="kardex-reference"
              >Documento de origen (opcional)
              <input
                id="kardex-reference"
                class={`${inputClass} mt-1`}
                bind:value={sourceReference}
                oninput={invalidatePhysical}
                maxlength="160"
                placeholder="Ej. adjustment:AJU-00001:1"
              />
            </label>
            <div class="flex items-end">
              <Button
                disabled={physicalLoading || !selectedItemId || periodFrom > periodTo}
                onclick={() => void loadPhysical(1)}
                >{physicalLoading ? 'Consultando…' : 'Consultar movimientos'}</Button
              >
            </div>
          </div>
          {#if itemSearchError}<div class="rounded-lg border border-danger/30 bg-danger/10 p-4">
              <p role="alert" class="mb-3 text-sm text-danger">{itemSearchError}</p>
              <Button variant="secondary" onclick={() => searchItems(itemQuery)}
                >Reintentar búsqueda</Button
              >
            </div>{/if}
          {#if !physicalData && !physicalLoading && !physicalError && !itemSearchError}
            <p
              class="rounded-lg border border-dashed border-border bg-surface-muted/30 p-4 text-sm text-foreground-muted"
            >
              {selectedItemId
                ? 'Producto seleccionado. Ajusta el período y los filtros; luego pulsa “Consultar movimientos”.'
                : 'Para comenzar, elige una bodega, busca un producto o SKU con al menos dos caracteres, selecciona el artículo y consulta sus movimientos.'}
            </p>
          {/if}
          {#if periodFrom > periodTo}<p class="text-sm text-danger" role="alert">
              La fecha inicial debe ser anterior o igual a la final.
            </p>{/if}
          {#if physicalError}<div class="rounded-lg border border-danger/30 bg-danger/10 p-4">
              <p role="alert" class="mb-3 text-sm text-danger">{physicalError}</p>
              <Button variant="secondary" onclick={() => void loadPhysical(page)}
                >Reintentar consulta</Button
              >
            </div>{/if}
          {#if physicalLoading}<div role="status" class="space-y-3">
              <p class="text-sm text-foreground-muted">
                Leyendo movimientos y saldos de la bodega…
              </p>
              <div class="skeleton h-20 rounded-lg"></div>
              <div class="skeleton h-52 rounded-lg"></div>
            </div>{/if}
          {#if physicalData && !physicalLoading}
            <section
              aria-label="Resumen de existencias físicas"
              class="grid gap-3 border-y border-border py-4 sm:grid-cols-3"
            >
              <div>
                <p class="text-xs text-foreground-muted">Saldo al inicio</p>
                <p class="mt-1 text-xl font-semibold tabular-nums text-foreground">
                  {physicalData.opening_known
                    ? `${number(physicalData.opening_quantity)} ${itemOptions.find((item) => item.inventory_item_id === selectedItemId)?.base_unit_symbol ?? 'unidades base'}`
                    : 'No reconstruible'}
                </p>
              </div>
              <div>
                <p class="text-xs text-foreground-muted">Entradas / salidas del período</p>
                <p class="mt-1 text-xl font-semibold tabular-nums text-foreground">
                  {number(physicalData.incoming_quantity)}
                  <span class="text-sm font-normal text-foreground-muted"
                    >/ {number(physicalData.outgoing_quantity)}</span
                  >
                </p>
              </div>
              <div>
                <p class="text-xs text-foreground-muted">Saldo al cierre</p>
                <p class="mt-1 text-xl font-semibold tabular-nums text-primary">
                  {physicalData.closing_known
                    ? `${number(physicalData.closing_quantity)} ${itemOptions.find((item) => item.inventory_item_id === selectedItemId)?.base_unit_symbol ?? 'unidades base'}`
                    : 'No reconstruible'}
                </p>
              </div>
              <p class="sm:col-span-3 text-xs leading-5 text-foreground-muted">
                {physicalData.balance_basis}
              {movementType || lotCode || sourceReference
                  ? 'Los saldos reconstruidos incluyen todos los movimientos del artículo; las entradas, salidas y filas respetan los filtros aplicados.'
                  : ''}
              </p>
            </section>
            {#if physicalData.items.length === 0}<div
                class="rounded-lg border border-dashed border-border p-8 text-center"
              >
                <h3 class="font-medium text-foreground">Sin movimientos en estas fechas</h3>
                <p class="mt-2 text-sm text-foreground-muted">
                  Prueba un período más amplio. Los saldos solo se muestran cuando existe un corte
                  físico que permite reconstruirlos.
                </p>
              </div>
            {:else}
              <PhysicalKardexList
                data={physicalData}
                {page}
                loading={physicalLoading}
                onPageChange={(nextPage) => void loadPhysical(nextPage)}
                onOpenDetail={(row) => (selectedMovement = row)}
              />{/if}
          {/if}
          <KardexMovementDetails
            movement={selectedMovement}
            onclose={() => (selectedMovement = null)}
          />
        {/if}
      </section>
    {:else if view === 'reconciliation' && canValue}
      <!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role -->
      <section
        id="kardex-panel"
        role="tabpanel"
        tabindex="0"
        aria-labelledby="kardex-tab-reconciliation reconciliation-title"
        class="space-y-5 rounded-xl border border-border bg-surface p-4 sm:p-6"
      >
        <div>
          <h2 id="reconciliation-title" class="text-lg font-semibold text-foreground">
            Cantidad física y valorada
          </h2>
          <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
            Compara los saldos de todas las bodegas de la empresa. El promedio de costo es
            compartido; los traslados internos no lo cambian.
          </p>
        </div>
        {#if reconciliationLoading}<div role="status" class="space-y-3">
            <p class="text-sm text-foreground-muted">
              Tomando una lectura consistente de las existencias…
            </p>
            <div class="skeleton h-48 rounded-lg"></div>
          </div>
        {:else if reconciliationError}<div
            class="rounded-lg border border-danger/30 bg-danger/10 p-4"
          >
            <p role="alert" class="mb-3 text-sm text-danger">{reconciliationError}</p>
            <Button variant="secondary" onclick={() => void loadReconciliation(reconciliationPage)}
              >Reintentar</Button
            >
          </div>
        {:else if reconciliation}
          {#if !reconciliation.valuation_enabled}<div
              class="rounded-lg border border-warning/30 bg-warning/10 p-4"
            >
              <h3 class="font-medium text-foreground">La valoración aún no está activada</h3>
              <p class="mt-1 text-sm text-foreground-muted">
                Puedes consultar los movimientos físicos. Para comparar cantidades y costos, revisa
                y aprueba el corte inicial.
              </p>
              <a
                class="mt-3 inline-block text-sm font-medium text-primary underline-offset-4 hover:underline"
                href="/inventory/valuation">Abrir valoración de inventario</a
              >
            </div>{/if}
          {#if reconciliation.items.length === 0}<p
              class="rounded-lg border border-dashed border-border p-8 text-center text-sm text-foreground-muted"
            >
              No hay artículos de inventario para mostrar.
            </p>{:else}
            <KardexReconciliationList
              data={reconciliation}
              page={reconciliationPage}
              onPageChange={(nextPage) => void loadReconciliation(nextPage)}
              onOpenKardex={(row) => {
                valuationItemId = row.inventory_item_id;
                valuationItemName = row.product_name;
                changeView('valuation');
                void showValued(row.inventory_item_id, row.product_name);
              }}
            />{/if}
        {/if}
      </section>
    {:else if view === 'valuation' && canValue}
      <!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role -->
      <section
        id="kardex-panel"
        role="tabpanel"
        tabindex="0"
        aria-labelledby="kardex-tab-valuation valuation-title"
        class="space-y-5 rounded-xl border border-border bg-surface p-4 sm:p-6"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id="valuation-title" class="text-lg font-semibold text-foreground">
              Kardex valorado
            </h2>
            <p class="mt-1 text-sm text-foreground-muted">
              Promedio por producto para toda la empresa. Los filtros de bodega no cambian este
              costo.
            </p>
          </div>
          <a
            class="text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            href="/inventory/valuation">Abrir configuración y saldos</a
          >
        </div>
        <div class="grid gap-4 sm:grid-cols-3">
          <label class="text-sm font-medium text-foreground" for="value-from"
            >Desde<input
              id="value-from"
              type="date"
              class={`${inputClass} mt-1`}
              bind:value={periodFrom}
              oninput={() => {
                invalidatePhysical();
                invalidateValuation();
              }}
            /></label
          ><label class="text-sm font-medium text-foreground" for="value-to"
            >Hasta<input
              id="value-to"
              type="date"
              class={`${inputClass} mt-1`}
              bind:value={periodTo}
              oninput={() => {
                invalidatePhysical();
                invalidateValuation();
              }}
            /></label
          >
          <div class="flex items-end">
            <Button
              disabled={!valuationItemId || valuationLoading || periodFrom > periodTo}
              onclick={() => void showValued(valuationItemId, valuationItemName)}
              >{valuationLoading ? 'Consultando…' : 'Actualizar período'}</Button
            >
          </div>
        </div>
        {#if valuationItemId}<h3 class="text-base font-semibold text-foreground">
            {valuationItemName}
          </h3>{:else}<p
            class="rounded-lg border border-dashed border-border p-5 text-sm text-foreground-muted"
          >
            Selecciona “Ver Kardex” en una fila de conciliación.
          </p>{/if}
        {#if valuationError}
          <div class="rounded-lg border border-danger/30 bg-danger/10 p-4">
            <p role="alert" class="mb-3 text-sm text-danger">{valuationError}</p>
            <Button
              variant="secondary"
              onclick={() => void showValued(valuationItemId, valuationItemName, valuationPage)}
              >Reintentar</Button
            >
          </div>
        {:else if valuationLoading}<div role="status" class="space-y-3">
            <p class="text-sm text-foreground-muted">Consultando movimientos de costo…</p>
            <div class="skeleton h-20 rounded-lg"></div>
            <div class="skeleton h-52 rounded-lg"></div>
          </div>
        {:else if valuationData?.setting}
          <div class="grid gap-3 border-y border-border py-4 sm:grid-cols-3">
            <div>
              <p class="text-xs text-foreground-muted">Saldo anterior</p>
              <p class="mt-1 font-semibold tabular-nums">
                {valuationData.opening_known
                  ? `${number(valuationData.opening_quantity)} · ${money(valuationData.opening_value, valuationData.setting.currency)}`
                  : 'Saldo anterior no reconstruible desde el corte'}
              </p>
            </div>
            <div>
              <p class="text-xs text-foreground-muted">Variación de valor</p>
              <p class="mt-1 font-semibold tabular-nums">
                {money(valuationData.period_value_change, valuationData.setting.currency)}
              </p>
            </div>
            <div>
              <p class="text-xs text-foreground-muted">Saldo a la fecha final</p>
              <p class="mt-1 font-semibold tabular-nums text-primary">
                {valuationData.closing_known
                  ? `${number(valuationData.closing_quantity)} · ${money(valuationData.closing_value, valuationData.setting.currency)}`
                  : 'Antes de activar la valoración'}
              </p>
            </div>
          </div>
          {#if valuationData.entries.length === 0}<p
              class="rounded-lg border border-dashed border-border p-8 text-center text-sm text-foreground-muted"
            >
              No hay movimientos de costo registrados en ese período.
            </p>{:else}
            <ValuedKardexList
              data={valuationData}
              loading={valuationLoading}
              canReadRetaceos={permissions.hasPermission('retaceos:read')}
              onPageChange={(nextPage) =>
                void showValued(valuationItemId, valuationItemName, nextPage)}
            />{/if}
        {:else if valuationData && !valuationData.setting}<div
            class="rounded-lg border border-warning/30 bg-warning/10 p-4"
          >
            <p class="font-medium text-foreground">La valoración no está activa.</p>
            <p class="mt-1 text-sm text-foreground-muted">
              Los importes no se pueden consultar hasta aprobar el corte inicial.
            </p>
            <a
              class="mt-3 inline-block text-sm font-medium text-primary underline-offset-4 hover:underline"
              href="/inventory/valuation">Abrir valoración de inventario</a
            >
          </div>{/if}
      </section>
    {/if}
  {/if}
</main>
