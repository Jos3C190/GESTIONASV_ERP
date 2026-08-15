<script lang="ts">
  import { page as routePage } from '$app/state';
  import { onMount } from 'svelte';
  import { api, HttpError, type PageMeta } from '$lib/api/client';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { queryClient } from '$lib/services/query-client';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Callout from '$lib/components/ui/Callout.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import type { KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import LocationTable from '$lib/features/locations/components/LocationTable.svelte';
  import LocationFormModal from '$lib/features/locations/components/LocationFormModal.svelte';
  import BatchGeneratorModal from '$lib/features/locations/components/BatchGeneratorModal.svelte';
  import LocationImportModal from '$lib/features/locations/components/LocationImportModal.svelte';
  import LocationCodeSchemeModal from '$lib/features/locations/components/LocationCodeSchemeModal.svelte';
  import {
    getLocationCodeScheme,
    getLocationSummary,
    listLocations
  } from '$lib/features/locations/services';
  import {
    LOCATION_STATUS_OPTIONS,
    LOCATION_TYPE_OPTIONS,
    type LocationBatchJob,
    type LocationCodeScheme,
    type LocationOut,
    type LocationSummary
  } from '$lib/features/locations/types';

  const PAGE_SIZE = 25;
  const NO_AREA_FILTER = '__none__';
  const warehouseId = $derived(routePage.params.id ?? '');
  let warehouseName = $state('');
  let items = $state<LocationOut[]>([]);
  let summary = $state<LocationSummary | null>(null);
  let scheme = $state<LocationCodeScheme | null>(null);
  let meta = $state<PageMeta | null>(null);
  let loading = $state(true);
  let contextLoading = $state(true);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let currentPage = $state(1);
  let search = $state('');
  let areaFilter = $state('');
  let typeFilter = $state('');
  let statusFilter = $state('');
  let activityFilter = $state('');
  let formOpen = $state(false);
  let editing = $state<LocationOut | null>(null);
  let generatorOpen = $state(false);
  let importOpen = $state(false);
  let schemeOpen = $state(false);
  let actionLoading = $state<string | null>(null);
  let loadGeneration = 0;
  let searchTimer: ReturnType<typeof setTimeout> | null = null;

  let canCreate = $derived(permissions.hasPermission('locations.create'));
  let canGenerate = $derived(permissions.hasPermission('locations.bulk'));
  let canImport = $derived(permissions.hasPermission('locations.import'));
  let canManageScheme = $derived(permissions.hasPermission('locations.scheme'));
  let hasFilters = $derived(
    Boolean(search.trim() || areaFilter || typeFilter || statusFilter || activityFilter)
  );
  let blockedCount = $derived(
    (summary?.by_status.blocked ?? 0) +
      (summary?.by_status.blocked_in ?? 0) +
      (summary?.by_status.blocked_out ?? 0)
  );
  let areaOptions = $derived(
    (() => {
      const areas = summary?.areas ?? {};
      const explicitlyUnassigned = areas[NO_AREA_FILTER];
      const assigned = Object.entries(areas).reduce(
        (total, [area, count]) => (area === NO_AREA_FILTER ? total : total + count),
        0
      );
      const unassigned = explicitlyUnassigned ?? Math.max(0, (summary?.total ?? 0) - assigned);
      return [
        {
          value: NO_AREA_FILTER,
          label: 'Sin área',
          description: `${unassigned} ubicación(es)`
        },
        ...Object.keys(areas)
          .filter((area) => area !== NO_AREA_FILTER)
          .sort((left, right) => left.localeCompare(right, 'es', { numeric: true }))
          .map((area) => ({
            value: area,
            label: area,
            description: `${areas[area] ?? 0} ubicación(es)`
          }))
      ];
    })()
  );

  const queryPrefix = () =>
    ['locations', company.id ?? 'none', branch.id ?? 'all', warehouseId] as const;

  async function initialize() {
    contextLoading = true;
    error = null;
    try {
      const [warehouse, activeScheme] = await Promise.all([
        api.warehouses.get(warehouseId),
        getLocationCodeScheme(warehouseId).catch((cause) => {
          if (cause instanceof HttpError && cause.status === 404) return null;
          throw cause;
        })
      ]);
      warehouseName = warehouse.name;
      scheme = activeScheme;
      await loadData();
    } catch (cause) {
      error =
        cause instanceof HttpError ? cause.message : 'No se pudo abrir la estructura del almacén.';
      loading = false;
    } finally {
      contextLoading = false;
    }
  }

  async function loadData(force = false) {
    const generation = ++loadGeneration;
    loading = true;
    error = null;
    const prefix = queryPrefix();
    try {
      await queryClient.cancelQueries({ queryKey: prefix, exact: false });
      if (force) await queryClient.invalidateQueries({ queryKey: prefix, exact: false });
      const listKey = [
        ...prefix,
        'list',
        currentPage,
        PAGE_SIZE,
        search.trim(),
        areaFilter,
        typeFilter,
        statusFilter,
        activityFilter
      ] as const;
      const summaryKey = [...prefix, 'summary'] as const;
      const [pageResult, summaryResult] = await Promise.all([
        queryClient.fetchQuery({
          queryKey: listKey,
          staleTime: force ? 0 : 30_000,
          queryFn: ({ signal }) =>
            listLocations(warehouseId, {
              page: currentPage,
              size: PAGE_SIZE,
              search: search.trim() || undefined,
              area: areaFilter || undefined,
              location_type: typeFilter || undefined,
              lifecycle_status: statusFilter || undefined,
              is_active:
                activityFilter === 'active'
                  ? true
                  : activityFilter === 'inactive'
                    ? false
                    : undefined,
              signal
            })
        }),
        queryClient.fetchQuery({
          queryKey: summaryKey,
          staleTime: force ? 0 : 60_000,
          queryFn: ({ signal }) => getLocationSummary(warehouseId, signal)
        })
      ]);
      if (generation !== loadGeneration) return;
      items = pageResult.items;
      meta = pageResult.meta;
      summary = summaryResult;
      if (currentPage > pageResult.meta.pages) {
        currentPage = pageResult.meta.pages;
        await loadData(force);
      }
    } catch (cause) {
      if (
        generation !== loadGeneration ||
        (cause instanceof DOMException && cause.name === 'AbortError')
      )
        return;
      error = cause instanceof HttpError ? cause.message : 'No se pudieron cargar las ubicaciones.';
    } finally {
      if (generation === loadGeneration) loading = false;
    }
  }

  function applyFilters() {
    currentPage = 1;
    void loadData();
  }

  function updateSearch(value: string) {
    search = value;
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(applyFilters, 350);
  }

  function clearFilters() {
    search = '';
    areaFilter = '';
    typeFilter = '';
    statusFilter = '';
    activityFilter = '';
    applyFilters();
  }

  function openCreate() {
    editing = null;
    formOpen = true;
  }

  function openEdit(location: LocationOut) {
    editing = location;
    formOpen = true;
  }

  async function activate(location: LocationOut) {
    actionLoading = location.id;
    error = null;
    try {
      await api.locations.activate(location.id);
      success = `${location.code} está disponible nuevamente.`;
      await loadData(true);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo activar la ubicación.';
    } finally {
      actionLoading = null;
    }
  }

  function deactivate(location: LocationOut) {
    confirmation.request({
      kind: 'deactivate',
      title: 'Desactivar ubicación',
      description:
        'Dejará de estar disponible para nuevas operaciones. El historial y la trazabilidad se conservarán.',
      resourceName: location.code,
      confirmLabel: 'Desactivar ubicación',
      execute: async () => {
        await api.locations.deactivate(location.id);
        success = `${location.code} fue desactivada.`;
        await loadData(true);
      }
    });
  }

  function remove(location: LocationOut) {
    confirmation.request({
      kind: 'delete',
      title: 'Enviar ubicación a la Papelera',
      description:
        'El sistema comprobará que no tenga inventario ni tareas activas. La ruta histórica no se perderá.',
      resourceName: location.code,
      confirmLabel: 'Enviar a la Papelera',
      requireReason: true,
      reasonLabel: 'Motivo de eliminación',
      execute: async (reason) => {
        if (!reason) return;
        await api.lifecycle.delete('locations', location.id, reason);
        success = `${location.code} fue enviada a la Papelera.`;
        await loadData(true);
      }
    });
  }

  function actionsFor(location: LocationOut): KebabItem[] {
    const actions: KebabItem[] = [];
    if (permissions.hasPermission('locations.update')) {
      actions.push({
        id: 'edit',
        label: 'Editar',
        icon: 'edit',
        onClick: () => openEdit(location)
      });
    }
    if (location.is_active && permissions.hasPermission('locations.deactivate')) {
      actions.push({
        id: 'deactivate',
        label: actionLoading === location.id ? 'Desactivando…' : 'Desactivar',
        icon: 'power',
        variant: 'danger',
        onClick: () => deactivate(location)
      });
    }
    if (!location.is_active && permissions.hasPermission('locations.activate')) {
      actions.push({
        id: 'activate',
        label: actionLoading === location.id ? 'Activando…' : 'Activar',
        icon: 'power',
        onClick: () => void activate(location)
      });
    }
    if (permissions.hasPermission('locations.delete')) {
      actions.push({
        id: 'delete',
        label: 'Enviar a la Papelera',
        icon: 'delete',
        variant: 'danger',
        onClick: () => remove(location)
      });
    }
    return actions;
  }

  function handleSaved(location: LocationOut, createAnother: boolean) {
    success = createAnother
      ? `${location.code} creada. Puede registrar la siguiente ubicación.`
      : `${location.code} guardada correctamente.`;
    void loadData(true);
  }

  function handlePublished(job: LocationBatchJob) {
    success = `${job.total_rows.toLocaleString('es-SV')} filas procesadas en el lote.`;
    void loadData(true);
  }

  function goToPage(nextPage: number) {
    if (!meta || nextPage < 1 || nextPage > meta.pages || nextPage === currentPage) return;
    currentPage = nextPage;
    void loadData();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  onMount(() => {
    void initialize();
    return () => {
      if (searchTimer) clearTimeout(searchTimer);
      loadGeneration += 1;
      void queryClient.cancelQueries({ queryKey: queryPrefix(), exact: false });
    };
  });
</script>

<svelte:head><title>Ubicaciones de almacenamiento — GestionaSV</title></svelte:head>

<div class="p-6 md:p-8">
  <div class="w-full">
    <header class="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:gap-3">
      <a
        href="/warehouses/{warehouseId}"
        class="flex h-8 w-8 flex-none items-center justify-center rounded-md text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground"
        aria-label="Volver al almacén"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"><path d="M19 12H5m7 7-7-7 7-7" /></svg
        >
      </a>
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="text-xl font-bold text-foreground">Ubicaciones de almacenamiento</h1>
          {#if scheme}<span
              class="rounded-md border border-border bg-surface-muted px-2 py-0.5 font-mono text-xs text-foreground-muted"
              >Esquema v{scheme.version}</span
            >{/if}
        </div>
        <p class="text-sm text-foreground-muted">
          {contextLoading
            ? 'Cargando estructura…'
            : `Rutas operativas, capacidad y estados de ${warehouseName}.`}
        </p>
      </div>
      <div class="flex flex-wrap gap-2 lg:shrink-0">
        {#if canManageScheme && scheme}
          <Button variant="ghost" size="sm" onclick={() => (schemeOpen = true)}>
            Configurar códigos
          </Button>
        {/if}
        {#if canImport}<Button variant="secondary" size="sm" onclick={() => (importOpen = true)}>
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"><path d="M12 3v12m0 0 4-4m-4 4-4-4" /><path d="M4 19h16" /></svg
            >
            Importar
          </Button>{/if}
        {#if canGenerate}<Button
            variant="secondary"
            size="sm"
            onclick={() => (generatorOpen = true)}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg
            >
            Generar por rangos
          </Button>{/if}
        {#if canCreate}<Button size="sm" onclick={openCreate}>
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
              aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg
            >
            Nueva ubicación
          </Button>{/if}
      </div>
    </header>

    {#if success}
      {#key success}<Callout variant="success"
          ><span class="font-medium text-foreground">{success}</span></Callout
        >{/key}
    {/if}
    {#if error}
      <div
        class="mb-5 flex flex-col gap-3 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
        role="alert"
      >
        <span>{error}</span>
        <Button variant="secondary" size="sm" onclick={() => void loadData(true)}>Reintentar</Button
        >
      </div>
    {/if}

    <section
      class="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
      aria-label="Resumen de ubicaciones"
    >
      {#if contextLoading || (!summary && loading)}
        {#each Array(4) as _}<div class="h-24 rounded-xl skeleton"></div>{/each}
      {:else}
        {#each [['Ubicaciones', summary?.total ?? 0, 'Total registrado'], ['Activas', summary?.active ?? 0, `${summary?.inactive ?? 0} inactivas`], ['Capacidad', summary?.total_capacity ?? 0, 'Capacidad configurada'], ['Bloqueadas', blockedCount, 'Requieren atención']] as metric (metric[0])}
          <Card class="p-4">
            <p class="text-xs font-medium text-foreground-muted">{metric[0]}</p>
            <p class="mt-2 font-mono text-2xl font-semibold text-foreground">
              {Number(metric[1]).toLocaleString('es-SV')}
            </p>
            <p class="mt-1 text-xs text-foreground-subtle">{metric[2]}</p>
          </Card>
        {/each}
      {/if}
    </section>

    <Card class="mb-4 p-4">
      <div
        class="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(260px,2fr)_repeat(4,minmax(150px,1fr))_auto]"
      >
        <div class="relative">
          <label for="location-search" class="sr-only">Buscar ubicaciones</label>
          <svg
            class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg
          >
          <input
            id="location-search"
            value={search}
            oninput={(event) => updateSearch(event.currentTarget.value)}
            placeholder="Buscar por código, alias o referencia…"
            autocomplete="off"
            class="h-[42px] w-full rounded-lg border border-border bg-surface pl-10 pr-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <SmartSelect
          id="location-area-filter"
          ariaLabel="Filtrar por área"
          bind:value={areaFilter}
          options={areaOptions}
          placeholder="Todas las áreas"
          compact
          onselect={applyFilters}
        />
        <SmartSelect
          id="location-type-filter"
          ariaLabel="Filtrar por tipo"
          bind:value={typeFilter}
          options={LOCATION_TYPE_OPTIONS.map((item) => ({ ...item }))}
          placeholder="Todos los tipos"
          compact
          onselect={applyFilters}
        />
        <SmartSelect
          id="location-status-filter"
          ariaLabel="Filtrar por estado"
          bind:value={statusFilter}
          options={LOCATION_STATUS_OPTIONS.map((item) => ({ ...item }))}
          placeholder="Todos los estados"
          compact
          onselect={applyFilters}
        />
        <SmartSelect
          id="location-active-filter"
          ariaLabel="Filtrar por vigencia"
          bind:value={activityFilter}
          options={[
            { value: 'active', label: 'Activas' },
            { value: 'inactive', label: 'Inactivas' }
          ]}
          placeholder="Toda vigencia"
          compact
          onselect={applyFilters}
        />
        {#if hasFilters}<Button variant="ghost" size="sm" onclick={clearFilters}>Limpiar</Button
          >{/if}
      </div>
    </Card>

    <Card class="overflow-hidden p-0">
      {#if loading}
        <div class="space-y-3 p-4" aria-label="Cargando ubicaciones">
          {#each Array(8) as _}<div class="h-14 rounded-lg skeleton"></div>{/each}
        </div>
      {:else if items.length === 0}
        <div class="flex flex-col items-center px-6 py-16 text-center">
          <div
            class="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-surface-muted text-foreground-muted"
          >
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              aria-hidden="true"
              ><path d="M3 21h18M5 21V8l7-4 7 4v13M8 12h2m4 0h2M8 16h2m4 0h2" /></svg
            >
          </div>
          <h2 class="mt-4 text-base font-semibold text-foreground">
            {hasFilters ? 'No hay coincidencias' : 'Aún no hay ubicaciones'}
          </h2>
          <p class="mt-2 max-w-md text-sm text-foreground-muted">
            {hasFilters
              ? 'Ajuste los filtros o busque otro identificador.'
              : 'Cree una ruta individual, genere la matriz del almacén o importe la estructura existente.'}
          </p>
          <div class="mt-5 flex flex-col gap-2 sm:flex-row">
            {#if hasFilters}<Button variant="secondary" size="sm" onclick={clearFilters}
                >Limpiar filtros</Button
              >{/if}
            {#if !hasFilters && canGenerate}<Button
                variant="secondary"
                size="sm"
                onclick={() => (generatorOpen = true)}>Generar por rangos</Button
              >{/if}
            {#if !hasFilters && canCreate}<Button size="sm" onclick={openCreate}
                >Crear primera ubicación</Button
              >{/if}
          </div>
        </div>
      {:else}
        <LocationTable {items} {actionsFor} />
      {/if}
    </Card>

    {#if meta}
      <div class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p class="text-xs text-foreground-muted">
          {meta.total.toLocaleString('es-SV')} ubicaciones · Página {meta.page} de {meta.pages}
        </p>
        {#if meta.pages > 1}<div class="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onclick={() => goToPage(meta!.page - 1)}
              disabled={loading || meta.page <= 1}>Anterior</Button
            >
            <Button
              variant="secondary"
              size="sm"
              onclick={() => goToPage(meta!.page + 1)}
              disabled={loading || meta.page >= meta.pages}>Siguiente</Button
            >
          </div>{/if}
      </div>
    {/if}
  </div>
</div>

<LocationFormModal
  open={formOpen}
  {warehouseId}
  location={editing}
  canRecode={permissions.hasPermission('locations.recode')}
  canCommission={permissions.hasPermission('locations.commission')}
  canActivate={permissions.hasPermission('locations.activate')}
  canDeactivate={permissions.hasPermission('locations.deactivate')}
  onclose={() => {
    formOpen = false;
    editing = null;
  }}
  onsaved={handleSaved}
/>
<BatchGeneratorModal
  open={generatorOpen}
  {warehouseId}
  {scheme}
  hasPermission={(code) => permissions.hasPermission(code)}
  onclose={() => (generatorOpen = false)}
  onpublished={handlePublished}
/>
<LocationImportModal
  open={importOpen}
  {warehouseId}
  {scheme}
  hasPermission={(code) => permissions.hasPermission(code)}
  onclose={() => (importOpen = false)}
  onpublished={handlePublished}
/>
{#if scheme}
  <LocationCodeSchemeModal
    open={schemeOpen}
    {warehouseId}
    {scheme}
    onclose={() => (schemeOpen = false)}
    onsaved={(nextScheme) => {
      scheme = nextScheme;
      success = `Esquema de códigos actualizado a la versión ${nextScheme.version}.`;
    }}
  />
{/if}
