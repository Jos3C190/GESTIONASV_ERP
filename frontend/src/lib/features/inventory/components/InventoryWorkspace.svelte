<script lang="ts">
  import { onDestroy, tick, untrack } from 'svelte';
  import { page } from '$app/state';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { getWarehouse, getWarehouses } from '$lib/services/warehouses';
  import type { Warehouse } from '$lib/features/warehouses/types';
  import Button from '$lib/components/ui/Button.svelte';
  import InventoryConsultation from './InventoryConsultation.svelte';
  import WarehouseReceiptQueue from './WarehouseReceiptQueue.svelte';
  import WarehousePreparationQueue from './WarehousePreparationQueue.svelte';
  import WarehouseMovementsPanel from './WarehouseMovementsPanel.svelte';

  let warehouses = $state<Warehouse[]>([]);
  let selected = $state<Warehouse | null>(null);
  let choosing = $state(true);
  let selectionError = $state<string | null>(null);
  let selectionLoading = $state(false);
  let search = $state('');
  let offsetPage = $state(1);
  let total = $state(0);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let revision = $state(0);
  let inventoryRevision = $state(0);
  let activeSection = $state<'receipts' | 'preparation' | 'stock' | 'movements'>('preparation');
  let sequence = 0;
  let urlSelectionSequence = 0;
  const size = 12;
  const fieldClass =
    'h-10 w-full rounded-lg border border-border-control bg-surface px-3 text-sm text-foreground placeholder:text-foreground-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary';
  let allowed = $derived(
    permissions.hasPermission('inventory:read') && permissions.hasPermission('warehouses.view')
  );
  let contextKey = $derived(
    [
      company.id,
      branch.id,
      permissions.isSuperuser,
      ...permissions.permissions.slice().sort()
    ].join('|')
  );
  let canVerify = $derived(permissions.hasPermission('inventory:receive'));
  let canRelease = $derived(permissions.hasPermission('inventory:move'));
  let pageCount = $derived(Math.max(1, Math.ceil(total / size)));

  $effect(() => {
    void contextKey;
    untrack(() => {
      selected = null;
      choosing = true;
      search = '';
      offsetPage = 1;
    });
  });

  $effect(() => {
    const requested = page.url.searchParams.get('warehouse_id');
    void contextKey;
    const canRead = allowed;
    let active = true;
    const selectionRequest = ++urlSelectionSequence;
    selectionError = null;
    selectionLoading = false;
    if (requested && canRead) {
      selected = null;
      choosing = true;
      selectionLoading = true;
      void getWarehouse(requested)
        .then((warehouse) => {
          if (!active || selectionRequest !== urlSelectionSequence) return;
          selected = warehouse;
          choosing = false;
        })
        .catch((cause) => {
          if (active && selectionRequest === urlSelectionSequence)
            selectionError =
              cause instanceof Error
                ? cause.message
                : 'La bodega solicitada no está disponible en tu contexto.';
        })
        .finally(() => {
          if (active && selectionRequest === urlSelectionSequence) selectionLoading = false;
        });
    }
    return () => {
      active = false;
    };
  });

  $effect(() => {
    const currentContext = contextKey;
    const query = search.trim();
    const currentPage = offsetPage;
    const canRead = allowed;
    void revision;
    const request = ++sequence;
    const controller = new AbortController();
    warehouses = [];
    total = 0;
    error = null;
    loading = canRead;
    const timer = setTimeout(
      () => {
        if (!canRead || !company.id) {
          loading = false;
          return;
        }
        void getWarehouses({
          search: query,
          page: currentPage,
          size,
          sort: 'name',
          branchId: branch.id ?? undefined,
          signal: controller.signal
        })
          .then((result) => {
            if (request !== sequence || currentContext !== contextKey) return;
            warehouses = result.items;
            total = result.meta.total;
            if (
              !selected &&
              !query &&
              currentPage === 1 &&
              !page.url.searchParams.has('warehouse_id') &&
              result.meta.total === 1
            ) {
              selected = result.items[0] ?? null;
              choosing = false;
            }
          })
          .catch((cause) => {
            if (request !== sequence || controller.signal.aborted) return;
            error =
              cause instanceof Error ? cause.message : 'No se pudieron consultar las bodegas.';
          })
          .finally(() => {
            if (request === sequence) loading = false;
          });
      },
      query ? 250 : 0
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
      sequence += 1;
    };
  });

  onDestroy(() => {
    sequence += 1;
  });

  async function changeWarehouse() {
    urlSelectionSequence += 1;
    selectionLoading = false;
    choosing = true;
    await tick();
    document.getElementById('inventory-warehouse-search')?.focus();
  }
</script>

<svelte:head><title>Inventario | GestionaSV</title></svelte:head>

<div class="mx-auto max-w-[1600px] space-y-6 p-4 md:p-6 lg:p-8">
  <header class="flex flex-wrap items-start justify-between gap-4">
    <div>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Operación de bodega</p>
      <h1 class="mt-2 text-2xl font-semibold tracking-tight text-foreground">Inventario</h1>
      <p class="mt-2 max-w-2xl text-sm leading-6 text-foreground-muted">
        Consulta existencias, revisa las unidades recibidas y prepara su ubicación en bodega.
      </p>
    </div>
    {#if permissions.hasPermission('inventory:valuation')}
      <a
        href="/inventory/valuation"
        class="rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >Valoración y conciliación →</a
      >
    {/if}
  </header>

  {#if !allowed}
    <section class="rounded-xl border border-border bg-surface-muted p-6" role="status">
      <h2 class="font-semibold text-foreground">Acceso a inventario requerido</h2>
      <p class="mt-2 text-sm text-foreground-muted">
        Tu usuario necesita permiso para consultar inventario y bodegas. Solicita que te asignen el
        acceso correspondiente.
      </p>
    </section>
  {:else}
    <p class="sr-only" role="status" aria-live="polite">
      {loading
        ? 'Buscando bodegas…'
        : error
          ? 'No se pudo completar la búsqueda.'
          : `${total} bodegas encontradas. Página ${offsetPage} de ${pageCount}.`}
    </p>
    {#if selectionError}<div
        class="rounded-lg border border-danger/30 bg-danger/10 p-4 text-sm text-foreground"
        role="alert"
      >
        No se pudo abrir la bodega solicitada. {selectionError}
      </div>{/if}
    {#if selectionLoading}<p class="text-sm text-foreground-muted" role="status">
        Abriendo la bodega solicitada…
      </p>{/if}
    <div hidden={!choosing}>
      <section
        class="rounded-xl border border-border bg-surface"
        aria-labelledby="warehouse-heading"
      >
        <div class="flex flex-wrap items-end justify-between gap-4 border-b border-border p-5">
          <div>
            <h2 id="warehouse-heading" class="font-semibold text-foreground">
              Selecciona la bodega
            </h2>
            <p class="mt-1 text-xs text-foreground-muted">
              {branch.label} · Solo se muestran las bodegas autorizadas.
            </p>
          </div>
          <label class="w-full sm:w-80">
            <span class="mb-1.5 block text-xs font-medium text-foreground-muted"
              >Buscar por nombre o código</span
            >
            <input
              id="inventory-warehouse-search"
              type="search"
              class={fieldClass}
              value={search}
              placeholder="Ej. Matriz o BM-001"
              oninput={(event) => {
                search = event.currentTarget.value;
                offsetPage = 1;
              }}
            />
          </label>
        </div>
        <div class="p-5" aria-busy={loading}>
          {#if loading}
            <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Cargando bodegas">
              {#each [1, 2, 3] as item (item)}<div class="skeleton h-24 rounded-lg"></div>{/each}
            </div>
          {:else if error}
            <div class="rounded-lg border border-danger/30 bg-danger/10 p-4" role="alert">
              <p class="text-sm text-foreground">{error}</p>
              <Button class="mt-3" variant="secondary" size="sm" onclick={() => (revision += 1)}
                >Reintentar</Button
              >
            </div>
          {:else if !warehouses.length}
            <div class="py-8 text-center">
              <span
                class="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-surface-muted text-foreground-muted"
                aria-hidden="true">⌕</span
              >
              <h3 class="mt-3 text-sm font-semibold text-foreground">
                {search ? 'Sin coincidencias' : 'Sin bodegas para consultar'}
              </h3>
              <p class="mt-1 text-sm text-foreground-muted">
                {search
                  ? 'Prueba otro nombre o código.'
                  : 'Revisa la sucursal seleccionada o solicita acceso a tu bodega.'}
              </p>
              {#if search}<Button
                  class="mt-4"
                  variant="secondary"
                  size="sm"
                  onclick={() => {
                    urlSelectionSequence += 1;
                    search = '';
                    offsetPage = 1;
                  }}>Limpiar búsqueda</Button
                >{/if}
            </div>
          {:else}
            <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {#each warehouses as warehouse (warehouse.id)}
                <button
                  type="button"
                  aria-pressed={selected?.id === warehouse.id}
                  onclick={() => {
                    urlSelectionSequence += 1;
                    selectionLoading = false;
                    selectionError = null;
                    selected = warehouse;
                    choosing = false;
                    requestAnimationFrame(() =>
                      document.getElementById('selected-heading')?.focus()
                    );
                  }}
                  class="min-w-0 rounded-lg border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary {selected?.id ===
                  warehouse.id
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:bg-surface-hover'}"
                >
                  <span
                    class="flex items-center justify-between gap-3 text-xs text-foreground-muted"
                    ><span class="font-mono">{warehouse.code}</span><span
                      >{selected?.id === warehouse.id
                        ? 'Seleccionada ✓'
                        : warehouse.isCentral
                          ? 'Bodega matriz'
                          : 'Bodega de sucursal'}</span
                    ></span
                  >
                  <span class="mt-2 block break-words text-sm font-semibold text-foreground"
                    >{warehouse.name}</span
                  >
                </button>
              {/each}
            </div>
          {/if}
          <div
            class="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-foreground-muted"
          >
            <p>{total} bodega{total === 1 ? '' : 's'} · Página {offsetPage} de {pageCount}</p>
            <div class="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={loading || offsetPage <= 1}
                onclick={() => (offsetPage -= 1)}>Anterior</Button
              >
              <Button
                variant="secondary"
                size="sm"
                disabled={loading || offsetPage >= pageCount}
                onclick={() => (offsetPage += 1)}>Siguiente</Button
              >
            </div>
          </div>
        </div>
      </section>
    </div>

    {#if selected}
      <section aria-labelledby="selected-heading" class="space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p class="text-xs font-mono text-foreground-muted">{selected.code}</p>
            <h2
              id="selected-heading"
              tabindex="-1"
              class="mt-1 text-lg font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              {selected.name}
            </h2>
          </div>
          <Button variant="secondary" size="sm" onclick={() => void changeWarehouse()}
            >Cambiar bodega</Button
          >
          {#if permissions.hasPermission('locations.view')}
            <a
              class="rounded-lg border border-border px-4 py-2 text-sm text-foreground hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              href={`/warehouses/${selected.id}/locations`}>Ubicaciones y etiquetas →</a
            >
          {/if}
        </div>
        {#if permissions.hasPermission('inventory:warehouse_receipts')}
          <nav
            class="grid grid-cols-2 gap-1 rounded-lg border border-border bg-surface p-1 sm:flex"
            aria-label="Tareas de bodega"
          >
            {#each [{ id: 'receipts', label: 'Recepciones' }, { id: 'preparation', label: 'Preparar y ubicar' }, { id: 'stock', label: 'Existencias' }, { id: 'movements', label: 'Movimientos' }] as section (section.id)}
              <button
                type="button"
                aria-current={activeSection === section.id ? 'page' : undefined}
                class="min-h-11 min-w-0 rounded-md px-2 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary sm:px-4 {activeSection ===
                section.id
                  ? 'bg-foreground text-surface'
                  : 'text-foreground-muted hover:bg-surface-hover'}"
                onclick={() => (activeSection = section.id as typeof activeSection)}
                >{section.label}</button
              >
            {/each}
          </nav>
        {/if}
        {#if permissions.hasPermission('inventory:warehouse_receipts') && activeSection === 'receipts'}
          {#key `${contextKey}:${selected.id}`}<WarehouseReceiptQueue
              warehouseId={selected.id}
              {contextKey}
              onregistered={() => {
                inventoryRevision += 1;
                activeSection = 'preparation';
              }}
            />{/key}
        {/if}
        {#if permissions.hasPermission('inventory:warehouse_receipts') && activeSection === 'preparation'}
          {#key `${contextKey}:${selected.id}`}<WarehousePreparationQueue
              warehouseId={selected.id}
              {contextKey}
              canOperate={canVerify && canRelease}
              onplaced={() => (inventoryRevision += 1)}
            />{/key}
        {/if}
        {#if permissions.hasPermission('inventory:warehouse_receipts') && activeSection === 'movements'}
          {#key `${contextKey}:${selected.id}`}<WarehouseMovementsPanel
              warehouseId={selected.id}
              {contextKey}
            />{/key}
        {/if}
        {#if !permissions.hasPermission('inventory:warehouse_receipts') || activeSection === 'stock'}
          {#key `${contextKey}:${selected.id}:${inventoryRevision}`}
            <InventoryConsultation
              warehouseId={selected.id}
              warehouseName={selected.name}
              {contextKey}
              canOpen={permissions.hasPermission('inventory:valuation') && canVerify}
              canReadPurchases={permissions.hasPermission('purchases:read')}
              {canVerify}
              {canRelease}
              canReadRetaceos={permissions.hasPermission('retaceos:read')}
              canVerifyRetaceos={permissions.hasPermission('retaceos:verify')}
              canTransfer={permissions.hasPermission('inventory:move')}
            />
          {/key}
        {/if}
      </section>
    {:else if !loading && !error && total > 0}
      <div
        class="rounded-xl border border-dashed border-border p-8 text-center text-sm text-foreground-muted"
      >
        Selecciona una bodega para consultar sus productos y unidades logísticas.
      </div>
    {/if}
  {/if}
</div>
