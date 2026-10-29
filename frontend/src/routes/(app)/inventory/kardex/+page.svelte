<script lang="ts">
  import { page as appPage } from '$app/state';
  import { onDestroy } from 'svelte';
  import { untrack } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import KardexProductPicker from '$lib/features/inventory/components/KardexProductPicker.svelte';
  import KardexMovementDetails from '$lib/features/inventory/components/KardexMovementDetails.svelte';
  import PhysicalKardexList from '$lib/features/inventory/components/PhysicalKardexList.svelte';
  import KardexReconciliationList from '$lib/features/inventory/components/KardexReconciliationList.svelte';
  import ValuedKardexList from '$lib/features/inventory/components/ValuedKardexList.svelte';
  import KardexStatementTools from '$lib/features/inventory/components/KardexStatementTools.svelte';
  import KardexReconciliationControls from '$lib/features/inventory/components/KardexReconciliationControls.svelte';
  import { getWarehouses } from '$lib/services/warehouses';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { displayDecimal } from '$lib/features/inventory/valuation';
  import { kardexMoney } from '$lib/features/inventory/kardex-format';
  import {
    kardexApi,
    kardexErrorMessage,
    kardexReportPath,
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
    'h-11 w-full rounded-lg border border-foreground/50 bg-surface px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary';
  const tabClass = (active: boolean) =>
    `rounded-lg px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${active ? 'bg-foreground text-surface' : 'text-foreground-muted hover:bg-surface-muted hover:text-foreground'}`;

  let view = $state<View>('physical');
  let warehouses = $state<Warehouse[]>([]);
  let selectedWarehouse = $state('');
  let warehousesLoading = $state(false);
  let warehousesError = $state<string | null>(null);
  let selectedItem = $state<KardexItemOption | null>(null);
  let itemSearchError = $state<string | null>(null);
  let selectedItemId = $derived(selectedItem?.inventory_item_id ?? '');
  let itemSearchLoading = $state(false);
  let physicalRequestSequence = 0;
  let reconciliationRequestSequence = 0;
  let valuationRequestSequence = 0;
  let physicalData = $state<PhysicalKardex | null>(null);
  let selectedMovement = $state<PhysicalKardex['items'][number] | null>(null);
  let physicalLoading = $state(false);
  let physicalError = $state<string | null>(null);
  let reconciliation = $state<Reconciliation | null>(null);
  let reconciliationLoading = $state(false);
  let reconciliationError = $state<string | null>(null);
  let reconciliationPage = $state(1);
  let reconciliationFilters = $state({ as_of: dateToday(), q: '', difference_only: false });
  let valuationData = $state<ValuedKardex | null>(null);
  let valuationLoading = $state(false);
  let valuationError = $state<string | null>(null);
  let valuationItemId = $state('');
  let valuationItemName = $state('');
  let valuationPage = $state(1);
  let page = $state(1);
  let failedPhysicalPage = 1;
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
  let loadedHref = '';
  let advancedFiltersOpen = $state(false);
  let advancedFilterCount = $derived(
    [movementType, lotCode.trim(), sourceReference.trim()].filter(Boolean).length
  );
  let periodError = $derived(
    !validDate(periodFrom) || !validDate(periodTo)
      ? 'Completa Desde y Hasta con fechas válidas.'
      : periodFrom > periodTo
        ? 'La fecha inicial debe ser anterior o igual a la final.'
        : null
  );

  function validDate(value: string): boolean {
    if (!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value) || value.startsWith('0000')) return false;
    const date = new Date(`${value}T12:00:00Z`);
    return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }

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
    return kardexErrorMessage(cause, fallback);
  }

  function focusResultsHeading(id: string) {
    if (typeof document === 'undefined') return;
    const heading = document.getElementById(id);
    heading?.focus({ preventScroll: true });
    heading?.scrollIntoView({ block: 'start', behavior: 'instant' });
  }

  function invalidatePhysical() {
    physicalRequestSequence++;
    physicalLoading = false;
    physicalData = null;
    selectedMovement = null;
    physicalError = null;
    page = 1;
    failedPhysicalPage = 1;
  }

  function invalidateValuation() {
    valuationRequestSequence++;
    valuationLoading = false;
    valuationData = null;
    valuationError = null;
    valuationPage = 1;
  }

  function clearItemSearch() {
    itemSearchLoading = false;
    itemSearchError = null;
    selectedItem = null;
  }

  function invalidateReconciliation() {
    reconciliationRequestSequence++;
    reconciliationLoading = false;
    reconciliation = null;
    reconciliationError = null;
    reconciliationPage = 1;
  }

  function physicalIdentity(requestedPage = page): string {
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
      requestedPage,
      25
    ]);
  }

  async function loadWarehouses(restoreFocus = false) {
    if (restoreFocus) focusResultsHeading('physical-title');
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
      if (
        requestedWarehouse &&
        !warehouses.some((warehouse) => warehouse.id === requestedWarehouse)
      ) {
        selectedWarehouse = '';
        clearItemSearch();
        warehousesError = 'La bodega del enlace no está disponible dentro de tu alcance actual.';
        return;
      }
      if (
        requestedWarehouse &&
        warehouses.some((warehouse) => warehouse.id === requestedWarehouse)
      ) {
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

  async function restoreUrlContext(
    sequence: number,
    companyId: string | null,
    branchId: string | null
  ) {
    const href = appPage.url.href;
    const contextKey = `${companyId ?? ''}:${branchId ?? ''}:${href}`;
    const params = new URL(href).searchParams;
    const requestedItemId = params.get('inventory_item_id');
    if (!requestedItemId || contextKey === restoredUrlContext || !selectedWarehouse) return;

    const periodStart = params.get('period_from');
    const periodEnd = params.get('period_to');
    if (periodStart && /^\d{4}-\d{2}-\d{2}$/.test(periodStart)) periodFrom = periodStart;
    if (periodEnd && /^\d{4}-\d{2}-\d{2}$/.test(periodEnd)) periodTo = periodEnd;
    movementType = params.get('movement_type') ?? '';
    lotCode = params.get('lot_code') ?? '';
    sourceReference = params.get('source_reference') ?? '';
    advancedFiltersOpen = Boolean(movementType || lotCode || sourceReference);
    itemSearchLoading = true;
    itemSearchError = null;
    try {
      const results = await kardexApi.searchItems(selectedWarehouse, requestedItemId);
      if (
        sequence !== loadedWarehouseSequence ||
        companyId !== company.id ||
        branchId !== branch.id ||
        href !== appPage.url.href
      )
        return;
      const match = results.find((item) => item.inventory_item_id === requestedItemId);
      if (!match) {
        itemSearchError =
          'El artículo del movimiento no aparece dentro de la bodega y el alcance seleccionados.';
        return;
      }
      restoredUrlContext = contextKey;
      selectedItem = match;
      await loadPhysical(1);
    } catch (cause) {
      if (
        sequence === loadedWarehouseSequence &&
        companyId === company.id &&
        branchId === branch.id &&
        href === appPage.url.href
      )
        itemSearchError = errorMessage(cause, 'No se pudo abrir el movimiento enlazado.');
    } finally {
      if (
        sequence === loadedWarehouseSequence &&
        companyId === company.id &&
        branchId === branch.id &&
        href === appPage.url.href
      )
        itemSearchLoading = false;
    }
  }

  function chooseItem(item: KardexItemOption) {
    invalidatePhysical();
    selectedItem = item;
    itemSearchError = null;
    void loadPhysical(1);
  }

  function setPeriod(days: number) {
    periodTo = dateToday();
    periodFrom = dateDaysAgo(days - 1);
    invalidatePhysical();
    invalidateValuation();
    if (selectedItemId) void loadPhysical(1);
  }

  function clearAdvancedFilters() {
    if (selectedItemId) focusResultsHeading('kardex-results-heading');
    else if (typeof document !== 'undefined')
      document.getElementById('kardex-extra-filters')?.focus();
    movementType = '';
    lotCode = '';
    sourceReference = '';
    invalidatePhysical();
    if (selectedItemId) void loadPhysical(1);
  }

  async function loadPhysical(nextPage = 1, focusResults = false) {
    if (!selectedWarehouse || !selectedItemId || periodError) return;
    if (focusResults) focusResultsHeading('kardex-results-heading');
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
    failedPhysicalPage = nextPage;
    const identity = physicalIdentity(nextPage);
    physicalLoading = true;
    physicalError = null;
    physicalData = null;
    selectedMovement = null;
    try {
      const result = await kardexApi.physical(filters);
      if (sequence === physicalRequestSequence && identity === physicalIdentity(nextPage)) {
        physicalData = result;
        page = result.page;
      }
    } catch (cause) {
      if (sequence === physicalRequestSequence && identity === physicalIdentity(nextPage))
        physicalError = errorMessage(cause, 'No se pudo consultar el historial de la bodega.');
    } finally {
      if (sequence === physicalRequestSequence && identity === physicalIdentity(nextPage))
        physicalLoading = false;
    }
  }

  async function loadReconciliation(nextPage = 1) {
    if (!canValue) return;
    if (nextPage !== reconciliationPage || reconciliationError)
      focusResultsHeading('reconciliation-title');
    const sequence = ++reconciliationRequestSequence;
    const identity = JSON.stringify([
      company.id,
      branch.id,
      canValue,
      nextPage,
      50,
      reconciliationFilters
    ]);
    reconciliationPage = nextPage;
    reconciliationLoading = true;
    reconciliationError = null;
    reconciliation = null;
    try {
      const result = await kardexApi.reconciliation(reconciliationPage, 50, reconciliationFilters);
      if (
        sequence === reconciliationRequestSequence &&
        identity ===
          JSON.stringify([
            company.id,
            branch.id,
            canValue,
            reconciliationPage,
            50,
            reconciliationFilters
          ])
      )
        reconciliation = result;
    } catch (cause) {
      if (
        sequence === reconciliationRequestSequence &&
        identity ===
          JSON.stringify([
            company.id,
            branch.id,
            canValue,
            reconciliationPage,
            50,
            reconciliationFilters
          ])
      )
        reconciliationError = errorMessage(cause, 'No se pudo conciliar el inventario.');
    } finally {
      if (
        sequence === reconciliationRequestSequence &&
        identity ===
          JSON.stringify([
            company.id,
            branch.id,
            canValue,
            reconciliationPage,
            50,
            reconciliationFilters
          ])
      )
        reconciliationLoading = false;
    }
  }

  async function showValued(itemId: string, name: string, nextPage = 1) {
    if (periodError) return;
    if (nextPage !== valuationPage || valuationError) focusResultsHeading('valuation-title');
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
    const href = appPage.url.href;
    const contextChanged =
      companyId !== loadedCompany ||
      branchId !== loadedBranch ||
      valuationAllowed !== loadedCanValue ||
      href !== loadedHref;
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
      loadedHref = href;
      restoredUrlContext = '';
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
      loadedHref = '';
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
    }
  });

  onDestroy(() => {
    loadedWarehouseSequence++;
    physicalRequestSequence++;
    reconciliationRequestSequence++;
    valuationRequestSequence++;
  });
</script>

<svelte:head><title>Kardex | GestionaSV</title></svelte:head>

<main class="kardex-workspace mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
  <header class="flex flex-wrap items-start justify-between gap-4">
    <div class="max-w-3xl">
      <p class="text-sm text-foreground-muted">Inventario</p>
      <h1 class="mt-2 text-2xl font-semibold tracking-tight text-foreground">Kardex</h1>
      <p class="mt-2 text-sm leading-6 text-foreground-muted">
        {canValue
          ? 'Consulta cada movimiento físico por bodega y revisa los costos desde el registro de valoración de la empresa.'
          : 'Consulta las entradas, salidas y cambios de ubicación de tus bodegas autorizadas.'}
      </p>
    </div>
    {#if view === 'physical' && physicalData}
      <Button
        variant="secondary"
        disabled={physicalLoading}
        onclick={() => void loadPhysical(page, true)}
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
          <h2
            id="physical-title"
            tabindex="-1"
            class="scroll-mt-24 text-lg font-semibold text-foreground"
          >
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
            <p role="alert" class="mb-3 text-sm text-foreground">{warehousesError}</p>
            <Button variant="secondary" onclick={() => void loadWarehouses(true)}>Reintentar</Button
            >
            {#if appPage.url.searchParams.has('warehouse_id')}
              <a
                class="ml-3 inline-flex min-h-11 items-center text-sm font-medium text-foreground underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                href="/inventory/kardex">Elegir otra bodega</a
              >
            {/if}
          </div>
        {:else if warehouses.length === 0}
          <p
            class="rounded-lg border border-dashed border-border p-5 text-sm text-foreground-muted"
          >
            No hay bodegas activas dentro de tu alcance actual.
          </p>
        {:else}
          <div class="grid gap-4 md:grid-cols-3">
            <label class="text-sm font-medium text-foreground" for="kardex-warehouse"
              >Bodega
              <select
                id="kardex-warehouse"
                class={`${inputClass} mt-1 min-h-14`}
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
            <div class="min-w-0 md:col-span-2">
              {#key `${company.id}:${branch.id}:${selectedWarehouse}`}
                <KardexProductPicker
                  warehouseId={selectedWarehouse}
                  warehouseName={warehouses.find((entry) => entry.id === selectedWarehouse)?.name ??
                    'Bodega seleccionada'}
                  selected={selectedItem}
                  disabled={itemSearchLoading}
                  onselect={chooseItem}
                />
              {/key}
            </div>
          </div>
          <div
            class="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4"
          >
            <p class="text-sm font-medium text-foreground">Período de consulta</p>
            <div class="flex flex-wrap gap-1" role="group" aria-label="Períodos rápidos">
              {#each [{ days: 1, label: 'Hoy' }, { days: 7, label: '7 días' }, { days: 30, label: '30 días' }] as period}
                <button
                  type="button"
                  class={`min-h-11 rounded-lg border border-border px-3 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${periodFrom === dateDaysAgo(period.days - 1) && periodTo === dateToday() ? 'bg-foreground text-surface' : 'text-foreground hover:bg-surface-hover'}`}
                  aria-pressed={periodFrom === dateDaysAgo(period.days - 1) &&
                    periodTo === dateToday()}
                  onclick={() => setPeriod(period.days)}>{period.label}</button
                >
              {/each}
            </div>
          </div>
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_auto]">
            <label class="text-sm font-medium text-foreground" for="kardex-from"
              >Desde
              <input
                id="kardex-from"
                type="date"
                required
                aria-invalid={!validDate(periodFrom) || periodFrom > periodTo}
                aria-describedby={periodError ? 'kardex-period-error' : undefined}
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
                required
                aria-invalid={!validDate(periodTo) || periodFrom > periodTo}
                aria-describedby={periodError ? 'kardex-period-error' : undefined}
                class={`${inputClass} mt-1`}
                bind:value={periodTo}
                oninput={() => {
                  invalidatePhysical();
                  invalidateValuation();
                }}
              />
            </label>
            <div class="flex items-end sm:col-span-2 lg:col-span-1">
              <Button
                class="min-h-11 w-full"
                disabled={physicalLoading || !selectedItemId || Boolean(periodError)}
                onclick={() => void loadPhysical(1)}
                >{physicalLoading ? 'Consultando…' : 'Consultar movimientos'}</Button
              >
            </div>
          </div>
          <details class="rounded-lg border border-border" bind:open={advancedFiltersOpen}>
            <summary
              id="kardex-extra-filters"
              class="cursor-pointer rounded-lg px-4 py-3 text-sm font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Más filtros{advancedFilterCount ? ` · ${advancedFilterCount} activos` : ''}
            </summary>
            <div class="grid gap-4 border-t border-border p-4 md:grid-cols-3">
              <label class="text-sm font-medium text-foreground" for="kardex-type"
                >Tipo de movimiento
                <select
                  id="kardex-type"
                  class={`${inputClass} mt-1`}
                  bind:value={movementType}
                  onchange={invalidatePhysical}
                >
                  <option value="">Todos los tipos</option><option value="opening"
                    >Saldo inicial</option
                  ><option value="receipt">Recepción</option><option value="putaway"
                    >Ubicación</option
                  ><option value="transfer">Traslado</option><option value="pick"
                    >Preparación de salida</option
                  ><option value="shipment">Despacho</option><option value="adjustment_in"
                    >Ajuste de entrada</option
                  ><option value="adjustment_out">Ajuste de salida</option><option value="reversal"
                    >Reversión</option
                  >
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
                  placeholder="Referencia exacta del movimiento"
                />
                <span class="mt-1 block text-xs text-foreground-muted"
                  >Es una referencia de documento, no el SKU del producto.</span
                >
              </label>
              {#if advancedFilterCount > 0}
                <div class="md:col-span-3">
                  <Button variant="secondary" onclick={clearAdvancedFilters}
                    >Limpiar filtros adicionales</Button
                  >
                </div>
              {/if}
            </div>
          </details>
          {#if itemSearchError}<div class="rounded-lg border border-danger/30 bg-danger/10 p-4">
              <p role="alert" class="mb-3 text-sm text-foreground">{itemSearchError}</p>
              <Button variant="secondary" onclick={() => void loadWarehouses(true)}
                >Reintentar enlace</Button
              >
            </div>{/if}
          {#if !physicalData && !physicalLoading && !physicalError && !itemSearchError}
            <p
              class="rounded-lg border border-dashed border-border bg-surface-muted/30 p-4 text-sm text-foreground-muted"
            >
              {selectedItemId
                ? 'Producto seleccionado. Ajusta el período y los filtros; luego pulsa “Consultar movimientos”.'
                : 'Elige un producto para ver sus movimientos. Al abrir el selector encontrarás los productos con actividad más reciente en esta bodega.'}
            </p>
          {/if}
          {#if periodError}<p id="kardex-period-error" class="text-sm text-foreground" role="alert">
              {periodError}
            </p>{/if}
          {#if selectedItem}
            <h3
              id="kardex-results-heading"
              tabindex="-1"
              class="scroll-mt-24 break-words text-base font-semibold text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-foreground"
            >
              Movimientos de {selectedItem.product_name}
            </h3>
          {/if}
          {#if physicalError}<div class="rounded-lg border border-danger/30 bg-danger/10 p-4">
              <p role="alert" class="mb-3 text-sm text-foreground">{physicalError}</p>
              <Button
                variant="secondary"
                onclick={() => void loadPhysical(failedPhysicalPage, true)}
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
                    ? `${number(physicalData.opening_quantity)} ${selectedItem?.base_unit_symbol ?? 'unidades base'}`
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
                    ? `${number(physicalData.closing_quantity)} ${selectedItem?.base_unit_symbol ?? 'unidades base'}`
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
            <KardexStatementTools
              context={physicalData.context}
              path={kardexReportPath('physical', {
                warehouse_id: physicalData.warehouse_id,
                inventory_item_id: physicalData.inventory_item_id,
                period_from: physicalData.period_from,
                period_to: physicalData.period_to,
                movement_type: movementType,
                lot_code: lotCode.trim(),
                source_reference: sourceReference.trim()
              })}
              code={`Kardex-fisico-${selectedItem?.sku ?? 'producto'}-${physicalData.period_to}`}
              scope={`Bodega: ${physicalData.context?.warehouse_name ?? warehouses.find((row) => row.id === selectedWarehouse)?.name ?? ''} · Historial físico sin costos.`}
            />
            {#if physicalData.items.length === 0}<div
                class="rounded-lg border border-dashed border-border p-8 text-center"
              >
                <h3 class="font-medium text-foreground">
                  {advancedFilterCount > 0
                    ? 'Sin movimientos con estos filtros'
                    : 'Sin movimientos en estas fechas'}
                </h3>
                <p class="mt-2 text-sm text-foreground-muted">
                  {advancedFilterCount > 0
                    ? 'Prueba sin filtros de tipo, lote o documento. También puedes ampliar el período.'
                    : 'Prueba un período más amplio. Los saldos solo se muestran cuando existe un corte físico que permite reconstruirlos.'}
                </p>
                {#if advancedFilterCount > 0}<Button
                    class="mt-4"
                    variant="secondary"
                    onclick={clearAdvancedFilters}>Quitar filtros adicionales</Button
                  >{/if}
              </div>
            {:else}
              <PhysicalKardexList
                data={physicalData}
                {page}
                loading={physicalLoading}
                onPageChange={(nextPage) => void loadPhysical(nextPage, true)}
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
          <h2
            id="reconciliation-title"
            tabindex="-1"
            class="scroll-mt-24 text-lg font-semibold text-foreground"
          >
            Cantidad física y valorada
          </h2>
          <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
            Compara los saldos de todas las bodegas de la empresa. El promedio de costo es
            compartido; los traslados internos no lo cambian.
          </p>
        </div>
        <KardexReconciliationControls
          asOf={reconciliationFilters.as_of}
          query={reconciliationFilters.q}
          differenceOnly={reconciliationFilters.difference_only}
          loading={reconciliationLoading}
          onquery={(filters) => {
            reconciliationFilters = filters;
            void loadReconciliation(1);
          }}
        />
        {#if reconciliationLoading}<div role="status" class="space-y-3">
            <p class="text-sm text-foreground-muted">
              Tomando una lectura consistente de las existencias…
            </p>
            <div class="skeleton h-48 rounded-lg"></div>
          </div>
        {:else if reconciliationError}<div
            class="rounded-lg border border-danger/30 bg-danger/10 p-4"
          >
            <p role="alert" class="mb-3 text-sm text-foreground">{reconciliationError}</p>
            <Button variant="secondary" onclick={() => void loadReconciliation(reconciliationPage)}
              >Reintentar</Button
            >
          </div>
        {:else if reconciliation}
          {#if reconciliation.balance_known === false}<p
              role="status"
              class="rounded-lg border border-warning/30 bg-warning/10 p-4 text-sm"
            >
              El corte solicitado es anterior a la base de valoración. Los saldos no se pueden
              reconstruir para esa fecha.
            </p>{/if}
          <dl class="grid grid-cols-2 gap-3 border-y border-border py-4 sm:grid-cols-4">
            <div>
              <dt class="text-xs text-foreground-muted">Valor del resultado</dt>
              <dd class="mt-1 font-semibold tabular-nums">
                {money(reconciliation.inventory_value, reconciliation.currency ?? undefined)}
              </dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Productos conciliados</dt>
              <dd class="mt-1 font-semibold tabular-nums">
                {reconciliation.reconciled_items ?? '—'}
              </dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Con diferencia</dt>
              <dd class="mt-1 font-semibold tabular-nums">
                {reconciliation.discrepant_items ?? '—'}
              </dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Sin base verificable</dt>
              <dd class="mt-1 font-semibold tabular-nums">
                {reconciliation.unvalued_items ?? '—'}
              </dd>
            </div>
          </dl>
          {#if reconciliation.valuation_enabled && reconciliation.balance_known !== false && (reconciliation.unvalued_items ?? 0) > 0}
            <p
              class="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-foreground"
            >
              Hay productos sin valoración verificable. El importe del resultado suma únicamente los
              valores registrados.
            </p>
          {/if}
          <KardexStatementTools
            context={reconciliation.context}
            path={kardexReportPath('reconciliation', reconciliationFilters)}
            code={`Conciliacion-${reconciliation.as_of ?? 'actual'}`}
            scope={`Toda la empresa · Corte por fecha de registro: ${(reconciliation.as_of ?? reconciliationFilters.as_of).split('-').reverse().join('/')}`}
          />
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
          {#if reconciliation.items.length === 0}<div
              class="rounded-lg border border-dashed border-border p-6 text-center"
            >
              <p class="font-medium text-foreground">
                {reconciliationFilters.q || reconciliationFilters.difference_only
                  ? 'Sin coincidencias con estos filtros'
                  : 'No hay artículos de inventario para mostrar'}
              </p>
              {#if reconciliationFilters.q || reconciliationFilters.difference_only}
                <p class="mt-2 text-sm text-foreground-muted">
                  Prueba otro producto o consulta todos los estados de conciliación.
                </p>
                <Button
                  class="mt-4"
                  variant="secondary"
                  onclick={() => {
                    reconciliationFilters = {
                      ...reconciliationFilters,
                      q: '',
                      difference_only: false
                    };
                    void loadReconciliation(1);
                  }}>Quitar filtros de producto y estado</Button
                >
              {/if}
            </div>{:else}
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
            <h2
              id="valuation-title"
              tabindex="-1"
              class="scroll-mt-24 text-lg font-semibold text-foreground"
            >
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
        <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-[1fr_1fr_auto]">
          <label class="text-sm font-medium text-foreground" for="value-from"
            >Desde<input
              id="value-from"
              type="date"
              required
              aria-invalid={!validDate(periodFrom) || periodFrom > periodTo}
              aria-describedby={periodError ? 'kardex-value-period-error' : undefined}
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
              required
              aria-invalid={!validDate(periodTo) || periodFrom > periodTo}
              aria-describedby={periodError ? 'kardex-value-period-error' : undefined}
              class={`${inputClass} mt-1`}
              bind:value={periodTo}
              oninput={() => {
                invalidatePhysical();
                invalidateValuation();
              }}
            /></label
          >
          <div class="flex items-end sm:col-span-2 xl:col-span-1">
            <Button
              class="whitespace-nowrap"
              disabled={!valuationItemId || valuationLoading || Boolean(periodError)}
              onclick={() => void showValued(valuationItemId, valuationItemName)}
              >{valuationLoading ? 'Consultando…' : 'Actualizar período'}</Button
            >
          </div>
        </div>
        {#if periodError}<p
            id="kardex-value-period-error"
            class="text-sm text-foreground"
            role="alert"
          >
            {periodError}
          </p>{/if}
        {#if valuationItemId}<h3 class="text-base font-semibold text-foreground">
            {valuationItemName}
          </h3>{:else}<p
            class="rounded-lg border border-dashed border-border p-5 text-sm text-foreground-muted"
          >
            Selecciona “Ver Kardex” en una fila de conciliación.
          </p>{/if}
        {#if valuationError}
          <div class="rounded-lg border border-danger/30 bg-danger/10 p-4">
            <p role="alert" class="mb-3 text-sm text-foreground">{valuationError}</p>
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
          <KardexStatementTools
            context={valuationData.context}
            path={kardexReportPath('valuation', {
              inventory_item_id: valuationData.inventory_item_id,
              period_from: valuationData.period_from,
              period_to: valuationData.period_to
            })}
            code={`Kardex-valorado-${valuationData.context?.sku ?? 'producto'}-${valuationData.period_to}`}
            scope="Toda la empresa · Los costos de cada movimiento son históricos. La bodega seleccionada no modifica el promedio global."
          />
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

<style>
  .kardex-workspace :global(button) {
    min-height: 2.75rem;
  }

  .kardex-workspace :global(button:focus-visible) {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 2px;
  }
</style>
