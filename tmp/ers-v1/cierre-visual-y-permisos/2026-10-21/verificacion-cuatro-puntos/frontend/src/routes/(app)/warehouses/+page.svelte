<script lang="ts">
  import { goto } from '$app/navigation';
  import { onDestroy } from 'svelte';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import {
    CAPACITY_ENFORCEMENT_LABEL,
    CAPACITY_PROFILE_LABEL,
    CAPACITY_STATUS_LABEL,
    STATUS_MAP,
    type CapacityStatus,
    type Warehouse
  } from '$lib/features/warehouses/types';
  import { getWarehouses } from '$lib/services/warehouses';
  import { api, HttpError, type PageMeta, type WarehouseListSummary } from '$lib/api/client';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { branch as operationalBranch } from '$lib/stores/branch.svelte';
  import { queryClient } from '$lib/services/query-client';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';

  const EMPTY_SUMMARY: WarehouseListSummary = {
    total_certified_max_weight_kg: 0,
    total_operational_max_weight_kg: 0,
    total_certified_usable_volume_m3: 0,
    total_operational_usable_volume_m3: 0,
    storage_eligible: 0,
    capacity_configured: 0,
    capacity_incomplete: 0,
    total_products: 0,
    active: 0,
    maintenance: 0,
    inactive: 0,
    status_counts: {},
    branches: []
  };

  let warehouses = $state<Warehouse[]>([]);
  let meta = $state<PageMeta | null>(null);
  let summary = $state<WarehouseListSummary>({ ...EMPTY_SUMMARY });
  let page = $state(1);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let branchFilter = $state('');
  let statusFilter = $state<'all' | 'active' | 'maintenance' | 'inactive'>('all');
  let viewMode = $state<'grid' | 'list'>('grid');
  let sortBy = $state<'name' | 'movement'>('name');
  const pageSize = 9;

  const warehousesQueryKey = $derived([
    'warehouses',
    company.id ?? 'none',
    operationalBranch.id ?? 'all',
    page,
    globalSearch.query.trim(),
    branchFilter || 'all',
    statusFilter,
    sortBy
  ] as const);

  let branches = $derived(summary.branches);
  let statusCounts = $derived({
    all: summary.status_counts.all ?? meta?.total ?? 0,
    active: summary.status_counts.active ?? summary.active,
    maintenance: summary.status_counts.maintenance ?? summary.maintenance,
    inactive: summary.status_counts.inactive ?? summary.inactive
  });

  function formatNumber(value: number | null | undefined, unit = ''): string {
    if (value == null || !Number.isFinite(Number(value))) return 'No registrado';
    return `${Number(value).toLocaleString('es-SV', { maximumFractionDigits: 3 })}${unit}`;
  }

  function formatUsableDimensions(warehouse: Warehouse): string {
    const values = [warehouse.usableLengthM, warehouse.usableWidthM, warehouse.usableHeightM];
    if (values.every((value) => value == null)) return 'No registradas';
    return `${values
      .map((value) => (value == null ? '—' : Number(value).toLocaleString('es-SV')))
      .join(' × ')} m`;
  }

  function capacityVariant(status: CapacityStatus): 'success' | 'warning' | 'danger' | 'neutral' {
    if (status === 'available') return 'success';
    if (status === 'warning' || status === 'incomplete') return 'warning';
    if (
      status === 'critical' ||
      status === 'full' ||
      status === 'over_operational' ||
      status === 'over_certified'
    )
      return 'danger';
    return 'neutral';
  }

  async function loadWarehouses(force = false) {
    loading = true;
    error = null;
    try {
      if (force) await queryClient.invalidateQueries({ queryKey: warehousesQueryKey });
      const response = await queryClient.fetchQuery({
        queryKey: warehousesQueryKey,
        staleTime: force ? 0 : 30_000,
        queryFn: ({ signal }) =>
          getWarehouses({
            page,
            size: pageSize,
            search: globalSearch.query.trim() || undefined,
            branchId: branchFilter || undefined,
            status: statusFilter === 'all' ? undefined : statusFilter,
            sort: sortBy,
            signal
          })
      });
      warehouses = response.items;
      meta = response.meta;
      summary = response.summary;
      if (page > response.meta.pages) page = response.meta.pages;
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudieron cargar los almacenes.';
    } finally {
      loading = false;
    }
  }

  function toggleWarehouse(warehouse: Warehouse) {
    if (warehouse.status === 'inactive') {
      void api.warehouses
        .activate(warehouse.id)
        .then(() => loadWarehouses(true))
        .catch((cause) => {
          error = cause instanceof HttpError ? cause.message : 'No se pudo activar el almacén.';
        });
      return;
    }
    confirmation.request({
      kind: 'deactivate',
      title: 'Desactivar almacén',
      description:
        'El almacén dejará de aceptar nuevas operaciones. La acción puede bloquearse si mantiene ubicaciones físicas activas.',
      resourceName: warehouse.name,
      confirmLabel: 'Desactivar almacén',
      execute: async () => {
        await api.warehouses.deactivate(warehouse.id);
        await loadWarehouses(true);
      }
    });
  }

  function deleteWarehouse(warehouse: Warehouse) {
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar almacén',
      description:
        'El almacén se ocultará de la operación diaria. La eliminación se bloqueará mientras conserve dependencias activas.',
      resourceName: warehouse.name,
      confirmLabel: 'Eliminar almacén',
      requireReason: true,
      reasonLabel: 'Motivo de eliminación',
      execute: async (reason) => {
        if (!reason) return;
        await api.lifecycle.delete('warehouses', warehouse.id, reason);
        await loadWarehouses(true);
      }
    });
  }

  function actionsFor(warehouse: Warehouse): KebabItem[] {
    const items: KebabItem[] = [
      {
        id: 'detail',
        label: 'Ver detalle',
        icon: 'detail',
        onClick: () => void goto(`/warehouses/${warehouse.id}`)
      }
    ];
    if (permissions.hasPermission('locations.view')) {
      items.push({
        id: 'locations',
        label: 'Ver ubicaciones',
        icon: 'locations',
        onClick: () => void goto(`/warehouses/${warehouse.id}/locations`)
      });
    }
    if (permissions.hasPermission('warehouses.view')) {
      items.push({
        id: 'structures',
        label: 'Ver estructuras y límites',
        icon: 'link',
        onClick: () => void goto(`/warehouses/${warehouse.id}/structures`)
      });
    }
    if (permissions.hasPermission('warehouses.update')) {
      items.push(
        {
          id: 'edit',
          label: 'Editar',
          icon: 'edit',
          onClick: () => void goto(`/warehouses/${warehouse.id}/edit`)
        },
        {
          id: 'toggle',
          label: warehouse.status === 'inactive' ? 'Activar' : 'Desactivar',
          icon: 'power',
          onClick: () => toggleWarehouse(warehouse)
        }
      );
    }
    if (permissions.hasPermission('warehouses.delete')) {
      items.push({
        id: 'delete',
        label: 'Eliminar',
        icon: 'delete',
        variant: 'danger',
        onClick: () => deleteWarehouse(warehouse)
      });
    }
    return items;
  }

  function resetFilters() {
    branchFilter = '';
    statusFilter = 'all';
    globalSearch.clear();
  }

  let previousFilterKey = '';
  $effect(() => {
    const filterKey = `${globalSearch.query.trim()}|${branchFilter}|${statusFilter}|${sortBy}`;
    if (filterKey !== previousFilterKey) {
      previousFilterKey = filterKey;
      page = 1;
    }
    const timer = window.setTimeout(() => void loadWarehouses(), 250);
    return () => window.clearTimeout(timer);
  });

  onDestroy(() => void queryClient.cancelQueries({ queryKey: ['warehouses'] }));
</script>

<svelte:head><title>Almacenes — GestionaSV</title></svelte:head>

<div class="space-y-5 p-4 sm:p-6 md:p-8">
  <header class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div>
      <h1 class="text-xl font-bold text-foreground">Almacenes</h1>
      <p class="text-sm text-foreground-muted">
        {meta?.total ?? 0} registrados en {branches.length} sucursal(es)
      </p>
    </div>
    {#if permissions.hasPermission('warehouses.create')}
      <Button size="sm" onclick={() => goto('/warehouses/new')}>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M12 5v14M5 12h14" />
        </svg>
        Crear almacén
      </Button>
    {/if}
  </header>

  <section
    class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"
    aria-label="Resumen de capacidad física"
  >
    <Card class="p-4">
      <p class="text-xs font-medium text-foreground-muted">Configuración física</p>
      <p class="mt-2 font-mono text-2xl font-semibold text-foreground">
        {summary.capacity_configured.toLocaleString('es-SV')}
      </p>
      <p class="mt-1 text-xs text-foreground-subtle">
        {summary.capacity_incomplete} incompleta(s)
      </p>
    </Card>
    <Card class="p-4">
      <p class="text-xs font-medium text-foreground-muted">Almacenamiento elegible</p>
      <p class="mt-2 font-mono text-2xl font-semibold text-foreground">
        {summary.storage_eligible.toLocaleString('es-SV')}
      </p>
      <p class="mt-1 text-xs text-foreground-subtle">Almacenes habilitados</p>
    </Card>
    <Card class="p-4">
      <p class="text-xs font-medium text-foreground-muted">Peso de la red</p>
      <p class="mt-2 font-mono text-lg font-semibold text-foreground">
        {formatNumber(summary.total_operational_max_weight_kg, ' kg')}
      </p>
      <p class="mt-1 text-xs text-foreground-subtle">
        Certificado: {formatNumber(summary.total_certified_max_weight_kg, ' kg')}
      </p>
    </Card>
    <Card class="p-4">
      <p class="text-xs font-medium text-foreground-muted">Volumen útil de la red</p>
      <p class="mt-2 font-mono text-lg font-semibold text-foreground">
        {formatNumber(summary.total_operational_usable_volume_m3, ' m³')}
      </p>
      <p class="mt-1 text-xs text-foreground-subtle">
        Certificado: {formatNumber(summary.total_certified_usable_volume_m3, ' m³')}
      </p>
    </Card>
    <Card class="p-4">
      <p class="text-xs font-medium text-foreground-muted">Ocupación real</p>
      <p class="mt-2 font-mono text-2xl font-semibold text-foreground">—</p>
      <p class="mt-1 text-xs text-foreground-subtle">Desconocida hasta medir inventario</p>
    </Card>
  </section>

  <Card class="p-4">
    <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
      <div class="flex flex-wrap gap-2" role="group" aria-label="Filtrar por estado operativo">
        {#each [['all', 'Todos', statusCounts.all], ['active', 'Activos', statusCounts.active], ['maintenance', 'Mantenimiento', statusCounts.maintenance], ['inactive', 'Inactivos', statusCounts.inactive]] as option (option[0])}
          <button
            type="button"
            onclick={() => (statusFilter = option[0] as typeof statusFilter)}
            class="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors {statusFilter ===
            option[0]
              ? 'border-primary bg-primary/10 text-primary'
              : 'border-border bg-surface text-foreground-muted hover:bg-surface-hover'}"
          >
            {option[1]} <span class="font-mono">{option[2]}</span>
          </button>
        {/each}
      </div>
      <div class="flex flex-wrap gap-2">
        <select
          bind:value={branchFilter}
          aria-label="Filtrar por sucursal"
          class="h-9 min-w-44 rounded-md border border-border bg-surface px-3 text-xs font-medium text-foreground focus:border-primary focus:outline-none"
        >
          <option value="">Todas las sucursales</option>
          {#each branches as item (item.id)}<option value={item.id}>{item.name}</option>{/each}
        </select>
        <select
          bind:value={sortBy}
          aria-label="Ordenar almacenes"
          class="h-9 min-w-44 rounded-md border border-border bg-surface px-3 text-xs font-medium text-foreground focus:border-primary focus:outline-none"
        >
          <option value="name">Ordenar por nombre</option>
          <option value="movement">Último movimiento</option>
        </select>
        <div class="flex rounded-lg border border-border p-0.5">
          <button
            type="button"
            class="rounded-md px-2.5 py-1.5 text-xs {viewMode === 'grid'
              ? 'bg-primary/10 text-primary'
              : 'text-foreground-muted'}"
            onclick={() => (viewMode = 'grid')}>Cuadrícula</button
          >
          <button
            type="button"
            class="rounded-md px-2.5 py-1.5 text-xs {viewMode === 'list'
              ? 'bg-primary/10 text-primary'
              : 'text-foreground-muted'}"
            onclick={() => (viewMode = 'list')}>Lista</button
          >
        </div>
      </div>
    </div>
  </Card>

  {#if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {/if}

  {#if loading}
    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {#each Array(6) as _}<div class="h-72 rounded-xl skeleton"></div>{/each}
    </div>
  {:else if warehouses.length === 0}
    <Card class="flex flex-col items-center py-12 text-center">
      <h2 class="text-base font-semibold text-foreground">Sin almacenes encontrados</h2>
      <p class="mt-1 max-w-md text-sm text-foreground-muted">
        No hay registros que coincidan con los filtros seleccionados.
      </p>
      <div class="mt-4">
        <Button variant="secondary" size="sm" onclick={resetFilters}>Limpiar filtros</Button>
      </div>
    </Card>
  {:else}
    <div
      class={viewMode === 'grid'
        ? 'grid gap-4 md:grid-cols-2 xl:grid-cols-3'
        : 'flex flex-col gap-3'}
    >
      {#each warehouses as warehouse (warehouse.id)}
        <article
          class="rounded-xl border border-border bg-surface-elevated p-5 shadow-sm {viewMode ===
          'list'
            ? 'xl:grid xl:grid-cols-[minmax(220px,1fr)_2fr_auto] xl:items-center xl:gap-5'
            : ''}"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 class="truncate text-sm font-semibold text-foreground">{warehouse.name}</h2>
              <p class="mt-0.5 font-mono text-xs text-foreground-subtle">{warehouse.code}</p>
              <p class="mt-2 truncate text-xs text-foreground-muted">
                {warehouse.branchName} · {warehouse.location}
              </p>
            </div>
            <KebabMenu items={actionsFor(warehouse)} ariaLabel={`Acciones de ${warehouse.name}`} />
          </div>

          <div class="mt-4 space-y-3 {viewMode === 'list' ? 'xl:mt-0' : ''}">
            <div class="flex flex-wrap gap-2">
              <Badge variant={STATUS_MAP[warehouse.status]?.variant ?? 'neutral'}>
                {STATUS_MAP[warehouse.status]?.label ?? warehouse.status}
              </Badge>
              <Badge variant={capacityVariant(warehouse.capacityStatus)}>
                {CAPACITY_STATUS_LABEL[warehouse.capacityStatus]}
              </Badge>
            </div>
            <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              <div>
                <dt class="text-foreground-subtle">Peso operativo</dt>
                <dd class="mt-0.5 font-mono text-foreground">
                  {formatNumber(warehouse.operationalMaxWeightKg, ' kg')}
                </dd>
              </div>
              <div>
                <dt class="text-foreground-subtle">Peso certificado</dt>
                <dd class="mt-0.5 font-mono text-foreground">
                  {formatNumber(warehouse.certifiedMaxWeightKg, ' kg')}
                </dd>
              </div>
              <div>
                <dt class="text-foreground-subtle">Volumen operativo</dt>
                <dd class="mt-0.5 font-mono text-foreground">
                  {formatNumber(warehouse.operationalUsableVolumeM3, ' m³')}
                </dd>
              </div>
              <div>
                <dt class="text-foreground-subtle">Volumen certificado</dt>
                <dd class="mt-0.5 font-mono text-foreground">
                  {formatNumber(warehouse.certifiedUsableVolumeM3, ' m³')}
                </dd>
              </div>
              <div>
                <dt class="text-foreground-subtle">Perfil</dt>
                <dd class="mt-0.5 text-foreground">
                  {CAPACITY_PROFILE_LABEL[warehouse.capacityProfile]}
                </dd>
              </div>
              <div>
                <dt class="text-foreground-subtle">Control</dt>
                <dd class="mt-0.5 text-foreground">
                  {CAPACITY_ENFORCEMENT_LABEL[warehouse.capacityEnforcementMode]}
                </dd>
              </div>
              <div>
                <dt class="text-foreground-subtle">Dimensiones útiles</dt>
                <dd class="mt-0.5 font-mono text-foreground">
                  {formatUsableDimensions(warehouse)}
                </dd>
              </div>
              <div>
                <dt class="text-foreground-subtle">Almacenamiento</dt>
                <dd class="mt-0.5 text-foreground">
                  {warehouse.storageEligible ? 'Elegible' : 'No elegible'}
                </dd>
              </div>
            </dl>
          </div>

          <div
            class="mt-4 rounded-lg border border-border bg-surface-muted/30 p-3 text-xs {viewMode ===
            'list'
              ? 'xl:mt-0 xl:w-48'
              : ''}"
          >
            <p class="font-medium text-foreground">Ocupación desconocida</p>
            <p class="mt-1 text-foreground-muted">
              Se calculará con existencias medidas y reservadas.
            </p>
          </div>
        </article>
      {/each}
    </div>
  {/if}

  {#if meta && meta.pages > 1}
    <footer class="flex items-center justify-between gap-4">
      <p class="text-xs text-foreground-muted">
        Página {meta.page} de {meta.pages} · {meta.total} almacenes
      </p>
      <div class="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={loading || meta.page <= 1}
          onclick={() => (page = Math.max(1, page - 1))}>Anterior</Button
        >
        <Button
          variant="secondary"
          size="sm"
          disabled={loading || meta.page >= meta.pages}
          onclick={() => (page = Math.min(meta!.pages, page + 1))}>Siguiente</Button
        >
      </div>
    </footer>
  {/if}
</div>
