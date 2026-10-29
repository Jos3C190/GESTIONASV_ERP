<script lang="ts">
  import { untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import PurchaseFlowRibbon from './PurchaseFlowRibbon.svelte';
  import { HttpError, api } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchaseConsolidationsApi } from '$lib/api/purchase-consolidations';
  import { branch } from '$lib/stores/branch.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Category } from '$lib/types/catalog';
  import type { PurchaseWorkItem, PurchaseWorkItemType } from '$lib/types/purchase-consolidation';
  import type { PurchaseRequestStatus } from '$lib/types/purchase-request';
  import type { WarehouseOut } from '$lib/api/client';

  const statusOptions: { value: string; label: string }[] = [
    { value: '', label: 'Todos los estados' },
    { value: 'draft', label: 'Borrador' },
    { value: 'submitted', label: 'Enviada' },
    { value: 'approved', label: 'Aprobada' },
    { value: 'rejected', label: 'Rechazada' },
    { value: 'partially_quoted', label: 'Parcialmente cotizada' },
    { value: 'quoted', label: 'Cotizada' },
    { value: 'partially_ordered', label: 'Parcialmente ordenada' },
    { value: 'completed', label: 'Completada' },
    { value: 'frozen', label: 'Enviada a cotización' },
    { value: 'closed', label: 'Consolidado cerrado' },
    { value: 'cancelled', label: 'Cancelada' }
  ];

  const statusLabels: Record<string, string> = Object.fromEntries(
    statusOptions.filter((option) => option.value).map((option) => [option.value, option.label])
  );
  const periodPresets = [
    { value: '7', label: '7 días' },
    { value: '15', label: '15 días' },
    { value: '30', label: '30 días' },
    { value: '90', label: '90 días' },
    { value: 'custom', label: 'Personalizado' }
  ] as const;
  const asDateInput = (date: Date) => {
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
    return local.toISOString().slice(0, 10);
  };
  const defaultDateTo = asDateInput(new Date());
  const dateOffset = new Date();
  dateOffset.setDate(dateOffset.getDate() - 29);
  const defaultDateFrom = asDateInput(dateOffset);

  let items = $state<PurchaseWorkItem[]>([]);
  let consolidationOptions = $state<PurchaseWorkItem[]>([]);
  let categories = $state<Category[]>([]);
  let categoriesLoading = $state(false);
  let categoriesError = $state<string | null>(null);
  let warehouses = $state<WarehouseOut[]>([]);
  let warehousesLoading = $state(false);
  let warehousesError = $state<string | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let query = $state('');
  let typeFilter = $state<'' | PurchaseWorkItemType>('');
  let statusFilter = $state('');
  let categoryFilter = $state('');
  let branchFilter = $state(branch.id ?? '');
  let warehouseFilter = $state('');
  let consolidationFilter = $state('');
  let dateFrom = $state(defaultDateFrom);
  let dateTo = $state(defaultDateTo);
  let datePreset = $state<(typeof periodPresets)[number]['value']>('30');
  let pageNumber = $state(1);
  let pageSize = $state(20);
  let totalPages = $state(0);
  let totalItems = $state(0);
  let selectedIds = $state<string[]>([]);
  let requestGeneration = 0;
  let warehouseGeneration = 0;
  let categoryGeneration = 0;
  let loadedCategoriesCompanyId: string | null = null;
  let lastOperationalBranchId: string | null | undefined;
  let canCreateRequest = $derived(
    permissions.hasAnyPermission(['purchase_requests:create', 'purchase_requests:manage'])
  );
  let canManageRequests = $derived(permissions.hasPermission('purchase_requests:manage'));

  function displayError(err: unknown) {
    return err instanceof HttpError
      ? err.message
      : err instanceof Error
        ? err.message
        : 'No se pudieron cargar las solicitudes y consolidados.';
  }

  async function loadWarehouses() {
    const generation = ++warehouseGeneration;
    warehousesLoading = true;
    warehousesError = null;
    try {
      const result = await api.warehouses.catalogue({ branch_id: branchFilter });
      if (generation === warehouseGeneration) warehouses = result;
    } catch (err: unknown) {
      if (generation === warehouseGeneration) {
        warehouses = [];
        warehousesError = displayError(err);
      }
    } finally {
      if (generation === warehouseGeneration) warehousesLoading = false;
    }
  }

  async function loadCategories() {
    const generation = ++categoryGeneration;
    const companyId = company.id;
    categoriesLoading = true;
    categoriesError = null;
    try {
      const result = await catalogApi.listCategories();
      if (generation !== categoryGeneration || company.id !== companyId) return;
      categories = result.filter((item) => item.is_active);
    } catch (err: unknown) {
      if (generation !== categoryGeneration) return;
      categories = [];
      categoriesError = displayError(err);
    } finally {
      if (generation === categoryGeneration) categoriesLoading = false;
    }
  }

  async function loadData(nextPage = pageNumber) {
    const generation = ++requestGeneration;
    loading = true;
    error = null;
    try {
      const filters = {
        q: query.trim() || undefined,
        type: typeFilter || undefined,
        status: (statusFilter || undefined) as PurchaseRequestStatus | 'frozen' | 'closed' | undefined,
        branch_id: branchFilter || undefined,
        warehouse_id: warehouseFilter || undefined,
        category_id: categoryFilter ? Number(categoryFilter) : undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        consolidation_id: consolidationFilter || undefined,
        page: nextPage,
        size: pageSize
      };
      const [response, consolidations] = await Promise.all([
        purchaseConsolidationsApi.listWorkItems(filters),
        purchaseConsolidationsApi.listWorkItems({
          type: 'consolidated',
          branch_id: branchFilter || undefined,
          category_id: categoryFilter ? Number(categoryFilter) : undefined,
          size: 100
        })
      ]);
      if (generation !== requestGeneration) return;
      items = response.items;
      consolidationOptions = consolidations.items;
      totalPages = response.meta.pages;
      totalItems = response.meta.total;
      pageNumber = nextPage;
    } catch (err: unknown) {
      if (generation !== requestGeneration) return;
      error = displayError(err);
      items = [];
      totalPages = 0;
      totalItems = 0;
    } finally {
      if (generation === requestGeneration) loading = false;
    }
  }

  function applyFilters() {
    pageNumber = 1;
    void loadData(1);
  }

  function clearFilters() {
    query = '';
    typeFilter = '';
    statusFilter = '';
    categoryFilter = '';
    consolidationFilter = '';
    branchFilter = branch.id ?? '';
    warehouseFilter = '';
    dateFrom = defaultDateFrom;
    dateTo = defaultDateTo;
    datePreset = '30';
    void loadWarehouses();
    applyFilters();
  }

  function selectPeriod(value: (typeof periodPresets)[number]['value']) {
    datePreset = value;
    if (value !== 'custom') {
      const end = new Date();
      const start = new Date(end);
      start.setDate(start.getDate() - Number(value) + 1);
      dateTo = asDateInput(end);
      dateFrom = asDateInput(start);
    }
    applyFilters();
  }

  function updateBranch(event: Event) {
    branchFilter = (event.currentTarget as HTMLSelectElement).value;
    warehouseFilter = '';
    void loadWarehouses();
    applyFilters();
  }

  function updateType(event: Event) {
    typeFilter = (event.currentTarget as HTMLSelectElement).value as '' | PurchaseWorkItemType;
    applyFilters();
  }

  function updateStatus(event: Event) {
    statusFilter = (event.currentTarget as HTMLSelectElement).value;
    applyFilters();
  }

  function updateCategory(event: Event) {
    categoryFilter = (event.currentTarget as HTMLSelectElement).value;
    applyFilters();
  }

  function updateWarehouse(event: Event) {
    warehouseFilter = (event.currentTarget as HTMLSelectElement).value;
    applyFilters();
  }

  function updateConsolidation(event: Event) {
    consolidationFilter = (event.currentTarget as HTMLSelectElement).value;
    applyFilters();
  }

  function toggleSelection(item: PurchaseWorkItem, checked: boolean) {
    if (checked) selectedIds = [...new Set([...selectedIds, item.id])];
    else selectedIds = selectedIds.filter((id) => id !== item.id);
  }

  function createConsolidation() {
    const params = new URLSearchParams({
      request_ids: selectedIds.join(','),
      date_from: dateFrom,
      date_to: dateTo
    });
    void goto(`/purchase-consolidations/new?${params}`);
  }

  function formatDate(value: string | null) {
    if (!value) return '—';
    return new Intl.DateTimeFormat('es-SV', {
      timeZone: 'America/El_Salvador',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    }).format(new Date(value));
  }

  function formatInputDate(value: string) {
    if (!value) return '—';
    const [year = 0, month = 0, day = 0] = value.split('-').map(Number);
    if (!year || !month || !day) return '—';
    return new Intl.DateTimeFormat('es-SV', { day: '2-digit', month: '2-digit', year: 'numeric' })
      .format(new Date(year, month - 1, day, 12));
  }

  function periodDescription() {
    if (datePreset === 'custom') {
      return `Rango personalizado: ${formatInputDate(dateFrom)} a ${formatInputDate(dateTo)}. Las fechas solo filtran; no cierran el consolidado.`;
    }
    return `Últimos ${datePreset} días: ${formatInputDate(dateFrom)} a ${formatInputDate(dateTo)}. Las fechas solo filtran; no cierran el consolidado.`;
  }

  function itemHref(item: PurchaseWorkItem) {
    return item.item_type === 'consolidated'
      ? `/purchase-consolidations/${item.id}`
      : `/purchase-requests/${item.id}`;
  }

  $effect(() => {
    const companyId = company.id;
    const selectedBranch = branch.id;
    const branchReady = branch.ready;
    const previousCategoriesCompanyId = untrack(() => loadedCategoriesCompanyId);

    if (companyId && companyId !== previousCategoriesCompanyId) {
      untrack(() => {
        loadedCategoriesCompanyId = companyId;
        void loadCategories();
      });
    }

    if (branchReady) {
      untrack(() => {
        if (lastOperationalBranchId !== selectedBranch) {
          lastOperationalBranchId = selectedBranch;
          branchFilter = selectedBranch ?? '';
        }
        void loadWarehouses();
        void loadData(1);
      });
    }
  });
</script>

<div class="purchase-work-queue min-h-full bg-background px-4 pb-8 pt-4 sm:px-6 sm:pt-6 md:px-8 md:pt-8">
  <header class="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
    <div>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Compras</p>
      <h1 class="mt-1 text-xl font-semibold text-foreground">Solicitudes y consolidados</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        {totalItems} registros · La demanda original se conserva en cada consolidado.
      </p>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      {#if canCreateRequest}
        <Button size="sm" onclick={() => goto('/purchase-requests/new')}>
          Nueva solicitud
        </Button>
      {:else}
        <p class="max-w-xs text-right text-xs text-foreground-muted">
          Para crear una solicitud, pide a un administrador que habilite la creación en tu rol.
        </p>
      {/if}
      {#if canManageRequests}
        <Button size="sm" variant="secondary" disabled={selectedIds.length === 0} onclick={createConsolidation}>
          Consolidar seleccionadas ({selectedIds.length})
        </Button>
      {/if}
    </div>
  </header>

  <PurchaseFlowRibbon currentStep={1} />

  <Card class="mb-4 p-4">
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <label class="space-y-1 text-xs text-foreground-muted">
        <span>Código o justificación</span>
        <div class="flex gap-2">
          <input
            aria-label="Buscar código o justificación"
            bind:value={query}
            onkeydown={(event) => event.key === 'Enter' && applyFilters()}
            placeholder="Ej. SCR-00012"
            class="h-9 min-w-0 flex-1 rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
          <Button size="sm" variant="secondary" onclick={applyFilters}>Buscar</Button>
        </div>
      </label>
      <label class="space-y-1 text-xs text-foreground-muted">
        <span>Tipo</span>
        <select bind:value={typeFilter} onchange={updateType} class="filter-control" aria-label="Filtrar por tipo">
          <option value="">Todos los tipos</option>
          <option value="individual">Individual</option>
          <option value="consolidated">Consolidada</option>
        </select>
      </label>
      <label class="space-y-1 text-xs text-foreground-muted">
        <span>Categoría de producto</span>
        <select
          bind:value={categoryFilter}
          onchange={updateCategory}
          class="filter-control"
          aria-label="Filtrar por categoría de producto"
          disabled={categoriesLoading || categories.length === 0}
        >
          <option value="">Todas las categorías</option>
          {#each categories as category (category.id_category)}
            <option value={category.id_category}>{category.name}</option>
          {/each}
        </select>
        {#if categoriesError}
          <span class="mt-1 block text-xs text-danger" role="alert">No se cargaron las categorías.</span>
          <button
            type="button"
            class="mt-1 text-xs text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            onclick={loadCategories}
          >Reintentar</button>
        {/if}
      </label>
      <label class="space-y-1 text-xs text-foreground-muted">
        <span>Estado</span>
        <select bind:value={statusFilter} onchange={updateStatus} class="filter-control" aria-label="Filtrar por estado">
          {#each statusOptions as option}
            <option value={option.value}>{option.label}</option>
          {/each}
        </select>
      </label>
      <label class="space-y-1 text-xs text-foreground-muted">
        <span>Consolidado</span>
        <select bind:value={consolidationFilter} onchange={updateConsolidation} class="filter-control" aria-label="Filtrar por consolidado">
          <option value="">Todos los consolidados</option>
          {#each consolidationOptions as item (item.id)}
            <option value={item.id}>{item.code} · {statusLabels[item.status] ?? item.status}</option>
          {/each}
        </select>
      </label>
      <label class="space-y-1 text-xs text-foreground-muted">
        <span>Sucursal</span>
        <select value={branchFilter} onchange={updateBranch} class="filter-control" aria-label="Filtrar por sucursal">
          {#if branch.accessAllBranches}<option value="">Todas las sucursales</option>{/if}
          {#each branch.branches as item (item.id)}
            <option value={item.id}>{item.name}</option>
          {/each}
        </select>
      </label>
      <label class="space-y-1 text-xs text-foreground-muted">
        <span>Almacén</span>
        <select bind:value={warehouseFilter} onchange={updateWarehouse} class="filter-control" aria-label="Filtrar por almacén">
          <option value="">{warehousesLoading ? 'Cargando almacenes…' : 'Todos los almacenes'}</option>
          {#each warehouses as item (item.id)}
            <option value={item.id}>{item.name}{item.branch_name ? ` · ${item.branch_name}` : ''}</option>
          {/each}
        </select>
        {#if warehousesError}
          <span class="mt-1 block text-xs text-danger" role="alert">No se cargó la lista de almacenes.</span>
          <button type="button" class="mt-1 text-xs text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" onclick={loadWarehouses}>Reintentar</button>
        {:else if !warehousesLoading && warehouses.length === 0}
          <span class="mt-1 block text-xs text-foreground-muted">No hay almacenes disponibles para esta sucursal.</span>
        {/if}
      </label>
      <label class="space-y-1 text-xs text-foreground-muted">
        <span>Desde</span>
        <input type="date" bind:value={dateFrom} onchange={() => { datePreset = 'custom'; applyFilters(); }} class="filter-control" />
      </label>
      <label class="space-y-1 text-xs text-foreground-muted">
        <span>Hasta</span>
        <input type="date" bind:value={dateTo} onchange={() => { datePreset = 'custom'; applyFilters(); }} class="filter-control" />
      </label>
    </div>
    <div class="mt-3 flex flex-wrap items-center gap-2" role="group" aria-label="Período de búsqueda">
      <span class="mr-1 text-xs text-foreground-muted">Período:</span>
      {#each periodPresets as preset (preset.value)}
        <button type="button" aria-pressed={datePreset === preset.value} onclick={() => selectPeriod(preset.value)} class={`min-h-9 rounded-full border px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${datePreset === preset.value ? 'border-primary bg-primary/10 text-primary' : 'border-border text-foreground-muted hover:bg-surface-muted'}`}>
          {preset.label}
        </button>
      {/each}
    </div>
    <div class="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
      <p class="text-xs text-foreground-muted">{periodDescription()}</p>
      <label class="flex items-center gap-2 text-xs text-foreground-muted">
        Filas
        <select bind:value={pageSize} onchange={applyFilters} class="filter-control !h-8 !w-auto">
          <option value={10}>10</option><option value={20}>20</option><option value={25}>25</option>
          <option value={30}>30</option><option value={100}>100</option>
        </select>
      </label>
    </div>
  </Card>

  {#if error}
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">
      <span>{error}</span><Button size="sm" variant="secondary" onclick={() => void loadData()}>Reintentar</Button>
    </div>
  {/if}

  {#if selectedIds.length > 0}
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary/25 bg-primary/5 px-4 py-3 text-sm" role="status">
      <span class="text-foreground">{selectedIds.length} solicitud(es) seleccionada(s). La selección se conserva aunque cambies filtros o páginas.</span>
      <Button size="sm" variant="secondary" onclick={() => selectedIds = []}>Limpiar selección</Button>
    </div>
  {/if}

  <Card class="overflow-hidden p-0">
    {#if loading}
      <div class="space-y-3 p-4" role="status" aria-label="Cargando solicitudes y consolidados">
        {#each Array(5) as _}<div class="skeleton h-12 w-full rounded-md"></div>{/each}
      </div>
    {:else if items.length === 0}
      <div class="px-6 py-16 text-center">
        <p class="text-sm font-medium text-foreground">No hay registros para esos filtros</p>
        <p class="mt-1 text-xs text-foreground-muted">Prueba otra categoría, estado, período, sucursal o código.</p>
        <Button class="mt-4" size="sm" variant="secondary" onclick={clearFilters}>Restablecer filtros</Button>
      </div>
    {:else}
      <div class="hidden overflow-x-auto xl:block">
        <table class="w-full min-w-[1140px] text-sm">
          <thead class="border-b border-border bg-surface-muted">
            <tr>
              {#if canManageRequests}<th scope="col" class="w-10 px-3 py-3"><span class="sr-only">Seleccionar</span></th>{/if}
              <th scope="col" class="px-4 py-3 text-left font-semibold text-foreground">Código</th>
              <th scope="col" class="px-4 py-3 text-left font-semibold text-foreground">Tipo</th>
              <th scope="col" class="px-4 py-3 text-left font-semibold text-foreground">Sucursal</th>
              <th scope="col" class="px-4 py-3 text-left font-semibold text-foreground">Almacén</th>
              <th scope="col" class="px-4 py-3 text-left font-semibold text-foreground">Solicitante</th>
              <th scope="col" class="px-4 py-3 text-left font-semibold text-foreground">Requerida</th>
              <th scope="col" class="px-4 py-3 text-left font-semibold text-foreground">Fecha</th>
              <th scope="col" class="px-4 py-3 text-right font-semibold text-foreground">Líneas / fuentes</th>
              <th scope="col" class="px-4 py-3 text-left font-semibold text-foreground">Estado</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each items as item (item.item_type + item.id)}
              <tr class="hover:bg-surface-muted">
                {#if canManageRequests}
                  <td class="px-3 py-3">
                    {#if item.item_type === 'individual' && item.status === 'approved'}
                      <input type="checkbox" aria-label={`Seleccionar ${item.code}`} checked={selectedIds.includes(item.id)} onchange={(event) => toggleSelection(item, (event.currentTarget as HTMLInputElement).checked)} class="h-4 w-4 rounded border-border accent-primary" />
                    {/if}
                  </td>
                {/if}
                <td class="px-4 py-3 font-mono text-xs font-medium text-foreground"><a href={itemHref(item)} class="hover:text-primary hover:underline">{item.code}</a></td>
                <td class="px-4 py-3"><span class:badge-blue={item.item_type === 'consolidated'} class="rounded-full border border-border px-2 py-1 text-xs text-foreground-muted">{item.item_type === 'consolidated' ? 'Consolidada' : 'Individual'}</span></td>
                <td class="px-4 py-3 text-foreground-muted">{item.branch_name ?? (item.item_type === 'consolidated' ? 'Demanda de varias sucursales' : '—')}</td>
                <td class="px-4 py-3 text-foreground-muted">{item.warehouse_name ?? (item.item_type === 'consolidated' ? 'Bodega central sin definir' : '—')}</td>
                <td class="px-4 py-3 text-foreground-muted">{item.requester_name ?? '—'}</td>
                <td class="px-4 py-3 text-foreground-muted">{formatDate(item.required_date)}</td>
                <td class="px-4 py-3 text-foreground-muted">{formatDate(item.request_date)}</td>
                <td class="px-4 py-3 text-right font-mono text-xs text-foreground">{item.line_count}{item.item_type === 'consolidated' ? ` / ${item.source_count}` : ''}</td>
                <td class="px-4 py-3 text-foreground-muted">{statusLabels[item.status] ?? item.status}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <ul class="divide-y divide-border xl:hidden">
        {#each items as item (item.item_type + item.id)}
          <li class="p-4">
            <div class="flex items-start gap-3">
              {#if canManageRequests && item.item_type === 'individual' && item.status === 'approved'}
                <input type="checkbox" aria-label={`Seleccionar ${item.code}`} checked={selectedIds.includes(item.id)} onchange={(event) => toggleSelection(item, (event.currentTarget as HTMLInputElement).checked)} class="mt-1 h-5 w-5 rounded border-border accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" />
              {/if}
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <a href={itemHref(item)} class="font-mono text-sm font-semibold text-primary hover:underline">{item.code}</a>
                  <span class:badge-blue={item.item_type === 'consolidated'} class="rounded-full border border-border px-2 py-0.5 text-xs text-foreground-muted">{item.item_type === 'consolidated' ? 'Consolidada' : 'Individual'}</span>
                  <span class="rounded-full border border-border px-2 py-0.5 text-xs text-foreground-muted">{statusLabels[item.status] ?? item.status}</span>
                </div>
                <dl class="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                  <div><dt class="text-foreground-muted">Sucursal</dt><dd class="mt-0.5 break-words text-foreground">{item.branch_name ?? (item.item_type === 'consolidated' ? 'Demanda de varias sucursales' : '—')}</dd></div>
                  <div><dt class="text-foreground-muted">Almacén</dt><dd class="mt-0.5 break-words text-foreground">{item.warehouse_name ?? (item.item_type === 'consolidated' ? 'Bodega central sin definir' : '—')}</dd></div>
                  <div><dt class="text-foreground-muted">Solicitante</dt><dd class="mt-0.5 break-words text-foreground">{item.requester_name ?? '—'}</dd></div>
                  <div><dt class="text-foreground-muted">Fecha requerida</dt><dd class="mt-0.5 text-foreground">{formatDate(item.required_date)}</dd></div>
                  <div><dt class="text-foreground-muted">Fecha</dt><dd class="mt-0.5 text-foreground">{formatDate(item.request_date)}</dd></div>
                  <div><dt class="text-foreground-muted">Líneas / fuentes</dt><dd class="mt-0.5 font-mono text-foreground">{item.line_count}{item.item_type === 'consolidated' ? ` / ${item.source_count}` : ''}</dd></div>
                </dl>
              </div>
            </div>
          </li>
        {/each}
      </ul>
      <div class="flex flex-col gap-3 border-t border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <p class="text-xs text-foreground-muted">Página {pageNumber} de {totalPages || 1} · {totalItems} registros</p>
        <div class="flex gap-2">
          <Button size="sm" variant="secondary" disabled={pageNumber <= 1} onclick={() => void loadData(pageNumber - 1)}>Anterior</Button>
          <Button size="sm" variant="secondary" disabled={pageNumber >= totalPages} onclick={() => void loadData(pageNumber + 1)}>Siguiente</Button>
        </div>
      </div>
    {/if}
  </Card>
</div>

<style>
  :global(.purchase-work-queue .hover-lift) { transition: none; }
  :global(.purchase-work-queue .hover-lift:hover) { transform: none; box-shadow: var(--shadow-md); }
  .filter-control {
    height: 2.25rem;
    width: 100%;
    border: 1px solid rgb(var(--border));
    border-radius: 0.375rem;
    background: rgb(var(--surface));
    padding: 0 0.75rem;
    color: rgb(var(--foreground));
    font-size: 0.875rem;
  }
  .filter-control:focus-visible { border-color: rgb(var(--primary)); outline: 2px solid rgb(var(--primary)); outline-offset: 2px; }
  .badge-blue { border-color: rgb(var(--primary) / 0.4); background: rgb(var(--primary) / 0.1); color: rgb(var(--primary)); }
</style>
