<script lang="ts">
  /**
   * Módulo de Almacenes — ERP System (Vercel / Geist Design System).
   *
   * Reestructurado en Bento Grid (4x2 en Desktop) con la Comparativa de Capacidad
   * integrada en la celda principal 2x2. Utiliza una jerarquía semántica equilibrada
   * (Verde = Óptimo, Ámbar = Advertencia, Rojo = Lleno/Crítico, Gris = Mantenimiento)
   * sobre una base neutra Geist.
   */

  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { goto } from '$app/navigation';
  import {
    STATUS_MAP,
    utilizationPct,
    getShortWarehouseName,
    type Warehouse
  } from '$lib/features/warehouses/types';
  import { getWarehouses } from '$lib/services/warehouses';
  import {
    api,
    HttpError,
    type PageMeta,
    type WarehouseListSummary
  } from '$lib/api/client';
  import { permissions } from '$lib/stores/permissions.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import KebabMenu from '$lib/components/ui/KebabMenu.svelte';
  import { onDestroy } from 'svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { branch as operationalBranch } from '$lib/stores/branch.svelte';
  import { queryClient } from '$lib/services/query-client';

  let warehouses = $state<Warehouse[]>([]);
  let meta = $state<PageMeta | null>(null);
  let page = $state(1);
  const pageSize = 9;
  let summary = $state<WarehouseListSummary>({
    total_capacity: 0,
    total_used: 0,
    total_products: 0,
    active: 0,
    full: 0,
    maintenance: 0,
    inactive: 0,
    status_counts: {},
    branches: []
  });
  let loading = $state(true);
  let error = $state<string | null>(null);

  let branchFilter = $state('');
  let statusFilter = $state<'all' | 'active' | 'full' | 'maintenance'>('all');
  let viewMode = $state<'grid' | 'list'>('grid');
  let sortBy = $state<'capacity' | 'name' | 'movement'>('capacity');

  // Estado para el degradado inferior condicional en la celda de comparativa
  let scrollContainer: HTMLDivElement | null = $state(null);
  let showBottomFade = $state(false);

  function checkScrollFade() {
    if (!scrollContainer) return;
    const { scrollTop, clientHeight, scrollHeight } = scrollContainer;
    showBottomFade = scrollHeight > clientHeight && scrollTop + clientHeight < scrollHeight - 8;
  }

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

  async function loadWarehouses(force = false) {
    loading = true;
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
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudieron cargar los almacenes.';
    } finally {
      loading = false;
    }
  }
  async function toggleWarehouse(wh: Warehouse) {
    const activate = wh.status === 'inactive';
    if (!activate) {
      confirmation.request({
        kind: 'deactivate',
        title: 'Desactivar almacén',
        description:
          'El almacén dejará de aceptar nuevas operaciones. La acción puede estar bloqueada si mantiene ubicaciones físicas activas.',
        resourceName: wh.name,
        confirmLabel: 'Desactivar almacén',
        execute: async () => {
          await api.warehouses.deactivate(wh.id);
          await loadWarehouses(true);
        }
      });
      return;
    }
    try {
      await api.warehouses.activate(wh.id);
      await loadWarehouses(true);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cambiar el estado.';
    }
  }

  $effect(() => {
    if (scrollContainer) {
      checkScrollFade();
    }
  });

  // Sucursales disponibles para el selector
  let branches = $derived(summary.branches);

  // Filtrado y ordenamiento dinámico
  let filtered = $derived(warehouses);

  // Conteo global de almacenes por estado (usado en los chips de filtro)
  let statusCounts = $derived({
    all: summary.status_counts.all ?? 0,
    active: summary.status_counts.active ?? 0,
    full: summary.status_counts.full ?? 0,
    maintenance: summary.status_counts.maintenance ?? 0
  });

  // Métricas acumuladas para KPIs basadas en los almacenes filtrados
  let totalCapacity = $derived(summary.total_capacity);
  let totalUsed = $derived(summary.total_used);
  let totalProducts = $derived(summary.total_products);
  let overallPct = $derived(totalCapacity > 0 ? Math.round((totalUsed / totalCapacity) * 100) : 0);

  // Conteos específicos de la vista filtrada (para KPI 5)
  let fActiveCount = $derived(summary.active);
  let fFullCount = $derived(summary.full);
  let fMaintCount = $derived(summary.maintenance);
  let fTotalCount = $derived(meta?.total ?? 0);

  // Almacenes ordenados por ocupación para la sección de comparativa (Bento Cell 1)
  let rankedWarehouses = $derived(
    [...filtered].sort((a, b) => utilizationPct(b) - utilizationPct(a))
  );

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

  onDestroy(() => {
    void queryClient.cancelQueries({ queryKey: ['warehouses'] });
  });

  // Color semántico funcional según nivel de ocupación
  function getStrokeColor(pct: number, status: string): string {
    if (status === 'maintenance') return 'rgb(var(--foreground-subtle))';
    if (pct >= 90) return 'rgb(var(--danger))';
    if (pct >= 70) return 'rgb(var(--warning))';
    return 'rgb(var(--success))';
  }
</script>

<svelte:head><title>Almacenes — ERP System</title></svelte:head>

<div class="p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
  <!-- Header de página (Sin título redundante) -->
  <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4">
    <p class="text-sm text-foreground-muted">
      {meta?.total ?? 0} almacenes registrados en {branches.length} sucursales
    </p>
    {#if permissions.hasPermission('warehouses.create')}<Button
        size="sm"
        onclick={() => goto('/warehouses/new')}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg
        >
        Crear almacén
      </Button>{/if}
  </div>

  <!-- BENTO GRID (4 Columnas x 2 Filas en Desktop) -->
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
    <!-- Celda Bento 1 (Grande 2x2): Comparativa de Capacidad -->
    <div
      class="lg:col-span-2 lg:row-span-2 relative flex flex-col h-[336px] rounded-xl border border-border bg-surface-elevated p-5 shadow-sm overflow-hidden"
    >
      <!-- Header Celda Comparativa -->
      <div class="flex items-start justify-between gap-3 border-b border-border/60 pb-3 flex-none">
        <div>
          <h3 class="text-sm font-bold text-foreground">Comparativa de capacidad</h3>
          <p class="text-[11.5px] text-foreground-muted">Ranking de ocupación por almacén</p>
        </div>
        <!-- Leyenda compacta semántica -->
        <div class="flex flex-col items-end text-[10px] text-foreground-muted space-y-0.5">
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center gap-1"
              ><i class="h-1.5 w-1.5 rounded-full bg-success"></i> &lt;70%</span
            >
            <span class="inline-flex items-center gap-1"
              ><i class="h-1.5 w-1.5 rounded-full bg-warning"></i> 70–89%</span
            >
            <span class="inline-flex items-center gap-1"
              ><i class="h-1.5 w-1.5 rounded-full bg-danger"></i> ≥90%</span
            >
          </div>
          <div>
            <span class="inline-flex items-center gap-1"
              ><i class="h-1.5 w-1.5 rounded-full bg-foreground-subtle"></i> Offline</span
            >
          </div>
        </div>
      </div>

      <!-- Ranking con Scroll Interno -->
      <div
        bind:this={scrollContainer}
        onscroll={checkScrollFade}
        class="flex-1 overflow-y-auto pt-3 pr-1.5 space-y-2.5 custom-scrollbar"
      >
        {#each rankedWarehouses as wh (wh.id)}
          {@const pct = utilizationPct(wh)}
          {@const color = getStrokeColor(pct, wh.status)}
          {@const shortName = getShortWarehouseName(wh.name)}

          <div
            class="flex items-center gap-3 text-xs group cursor-default"
            title="{wh.name} · {wh.branchName}"
          >
            <!-- Nombre corto -->
            <span
              class="w-24 flex-none font-medium text-foreground truncate group-hover:text-primary transition-colors"
            >
              {shortName}
            </span>
            <!-- Barra de progreso horizontal -->
            <div class="flex-1 h-2 rounded-full bg-surface-muted overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-500"
                style="width: {wh.status === 'maintenance' ? 0 : pct}%; background: {color};"
              ></div>
            </div>
            <!-- Porcentaje -->
            <span
              class="w-9 flex-none text-right font-mono font-bold text-[11px] tabular-nums"
              style="color: {color};"
            >
              {wh.status === 'maintenance' ? '—' : `${pct}%`}
            </span>
          </div>
        {/each}
      </div>

      <!-- Degradado / Fade Out Inferior Condicional -->
      {#if showBottomFade}
        <div
          class="pointer-events-none absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-surface-elevated via-surface-elevated/80 to-transparent transition-opacity duration-300 z-10"
        ></div>
      {/if}
    </div>

    <!-- Celda Bento 2 (1x1): KPI Capacidad Total -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-5 h-[160px] flex flex-col justify-between"
    >
      <div class="flex items-center justify-between">
        <span class="text-[11px] font-semibold uppercase tracking-wider text-foreground-subtle"
          >Capacidad total</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            ><path
              d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"
            /><path d="m3.3 7 8.7 5 8.7-5" /><path d="M12 22V12" /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {totalCapacity.toLocaleString()}
          <span class="text-xs font-normal text-foreground-muted">u</span>
        </div>
        <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
          <div class="h-full rounded-full bg-primary" style="width: 100%;"></div>
        </div>
      </div>
      <p class="text-[11px] text-foreground-subtle truncate">
        Distribuida en {fTotalCount} almacenes
      </p>
    </div>

    <!-- Celda Bento 3 (1x1): KPI Ocupado -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-5 h-[160px] flex flex-col justify-between"
    >
      <div class="flex items-center justify-between">
        <span class="text-[11px] font-semibold uppercase tracking-wider text-foreground-subtle"
          >Ocupado</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-success/10 text-success">
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            ><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line
              x1="6"
              y1="20"
              x2="6"
              y2="14"
            /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {totalUsed.toLocaleString()}
          <span class="text-xs font-normal text-foreground-muted">u</span>
        </div>
        <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
          <div class="h-full rounded-full bg-success" style="width: {overallPct}%;"></div>
        </div>
      </div>
      <p class="text-[11px] text-foreground-muted truncate">
        <strong class="text-success font-semibold">{overallPct}%</strong> de la capacidad total en uso
      </p>
    </div>

    <!-- Celda Bento 4 (1x1): KPI Productos -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-5 h-[160px] flex flex-col justify-between"
    >
      <div class="flex items-center justify-between">
        <span class="text-[11px] font-semibold uppercase tracking-wider text-foreground-subtle"
          >Productos</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-warning/10 text-warning">
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            ><path
              d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"
            /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {totalProducts.toLocaleString()}
        </div>
        <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
          <div class="h-full rounded-full bg-warning" style="width: 65%;"></div>
        </div>
      </div>
      <p class="text-[11px] text-foreground-subtle truncate">SKUs únicos distribuidos</p>
    </div>

    <!-- Celda Bento 5 (1x1): KPI Almacenes Activos -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-5 h-[160px] flex flex-col justify-between"
    >
      <div class="flex items-center justify-between">
        <span class="text-[11px] font-semibold uppercase tracking-wider text-foreground-subtle"
          >Almacenes activos</span
        >
        <div class="font-mono text-lg font-bold text-foreground">
          {fActiveCount}
          <span class="text-xs font-normal text-foreground-subtle">/ {fTotalCount}</span>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <!-- Mini Anillo SVG Verde -->
        <svg
          width="40"
          height="40"
          viewBox="0 0 40 40"
          class="-rotate-90 flex-none"
          aria-hidden="true"
        >
          <circle
            cx="20"
            cy="20"
            r="15"
            fill="none"
            stroke="rgb(var(--border))"
            stroke-width="4.5"
          />
          <circle
            cx="20"
            cy="20"
            r="15"
            fill="none"
            stroke="rgb(var(--success))"
            stroke-width="4.5"
            stroke-dasharray="94.2"
            stroke-dashoffset={fTotalCount > 0 ? 94.2 - (fActiveCount / fTotalCount) * 94.2 : 94.2}
            stroke-linecap="round"
          />
        </svg>
        <div class="text-[11px] space-y-0.5">
          <p class="font-semibold text-danger">{fFullCount} llenos</p>
          <p class="font-medium text-warning">{fMaintCount} en mantenimiento</p>
        </div>
      </div>
      <p class="text-[10.5px] text-foreground-subtle truncate">
        {fActiveCount} operando normalmente
      </p>
    </div>
  </div>

  <!-- Barra de Herramientas (Toolbar: Chips por estado + Filtros + Toggle Grid/Lista) -->
  <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 sm:gap-6 pt-2">
    <!-- Chips de Filtro por Estado -->
    <div class="flex flex-wrap items-center gap-2" role="tablist" aria-label="Filtrar por estado">
      <button
        onclick={() => (statusFilter = 'all')}
        class="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary {statusFilter ===
        'all'
          ? 'bg-foreground text-surface border-foreground'
          : 'bg-surface border-border text-foreground-muted hover:bg-surface-hover'}"
      >
        Todos <span
          class="rounded-full bg-surface-muted px-1.5 py-0.5 text-[10px] font-semibold text-foreground"
          >{statusCounts.all}</span
        >
      </button>

      <button
        onclick={() => (statusFilter = 'active')}
        class="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-success {statusFilter ===
        'active'
          ? 'badge-success font-semibold border-success/30'
          : 'bg-surface border-border text-foreground-muted hover:bg-surface-hover'}"
      >
        Activo <span
          class="rounded-full bg-success/10 px-1.5 py-0.5 text-[10px] font-semibold text-success"
          >{statusCounts.active}</span
        >
      </button>

      <button
        onclick={() => (statusFilter = 'full')}
        class="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger {statusFilter ===
        'full'
          ? 'badge-danger font-semibold border-danger/30'
          : 'bg-surface border-border text-foreground-muted hover:bg-surface-hover'}"
      >
        Lleno <span
          class="rounded-full bg-danger/10 px-1.5 py-0.5 text-[10px] font-semibold text-danger"
          >{statusCounts.full}</span
        >
      </button>

      <button
        onclick={() => (statusFilter = 'maintenance')}
        class="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warning {statusFilter ===
        'maintenance'
          ? 'badge-warning font-semibold border-warning/30'
          : 'bg-surface border-border text-foreground-muted hover:bg-surface-hover'}"
      >
        Mantenimiento <span
          class="rounded-full bg-warning/10 px-1.5 py-0.5 text-[10px] font-semibold text-warning"
          >{statusCounts.maintenance}</span
        >
      </button>
    </div>

    <!-- Controles derechos (Sucursal, Ordenamiento, Toggle Grid/Lista) -->
    <div
      class="flex flex-wrap items-center justify-end gap-2 self-end md:self-auto w-full sm:w-auto"
    >
      <select
        bind:value={branchFilter}
        class="h-9 rounded-md border border-border bg-surface px-3 text-xs font-medium text-foreground focus:border-primary focus:outline-none"
      >
        <option value="">Todas las sucursales</option>
        {#each branches as b (b.id)}<option value={b.id}>{b.name}</option>{/each}
      </select>

      <select
        bind:value={sortBy}
        class="h-9 rounded-md border border-border bg-surface px-3 text-xs font-medium text-foreground focus:border-primary focus:outline-none"
      >
        <option value="capacity">Ordenar: % Capacidad</option>
        <option value="name">Ordenar: Nombre</option>
        <option value="movement">Ordenar: Últ. movimiento</option>
      </select>

      <!-- Toggle Segmented Control (Grid vs Lista) -->
      <div
        class="flex items-center rounded-md border border-border bg-surface p-0.5"
        role="group"
        aria-label="Modo de vista"
      >
        <button
          onclick={() => (viewMode = 'grid')}
          title="Vista de cuadrícula"
          aria-label="Vista de cuadrícula"
          class="flex h-8 w-8 items-center justify-center rounded-md text-xs transition-colors {viewMode ===
          'grid'
            ? 'bg-primary/10 text-primary font-semibold'
            : 'text-foreground-subtle hover:text-foreground'}"
        >
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            ><rect x="3" y="3" width="7" height="7" rx="1" /><rect
              x="14"
              y="3"
              width="7"
              height="7"
              rx="1"
            /><rect x="14" y="14" width="7" height="7" rx="1" /><rect
              x="3"
              y="14"
              width="7"
              height="7"
              rx="1"
            /></svg
          >
        </button>
        <button
          onclick={() => (viewMode = 'list')}
          title="Vista de lista compacta"
          aria-label="Vista de lista compacta"
          class="flex h-8 w-8 items-center justify-center rounded-md text-xs transition-colors {viewMode ===
          'list'
            ? 'bg-primary/10 text-primary font-semibold'
            : 'text-foreground-subtle hover:text-foreground'}"
        >
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            ><line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line
              x1="8"
              y1="18"
              x2="21"
              y2="18"
            /><line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line
              x1="3"
              y1="18"
              x2="3.01"
              y2="18"
            /></svg
          >
        </button>
      </div>
    </div>
  </div>

  <!-- Vista Principal: Grid o Lista de Tarjetas de Almacén -->
  {#if error}<div class="rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
      {error}
    </div>{/if}
  {#if loading}
    <div
      class="flex items-center justify-center py-24 border border-border rounded-xl bg-surface-elevated shadow-sm"
    >
      <div class="flex flex-col items-center gap-3">
        <svg class="animate-spin h-5 w-5 text-primary" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"
          ></circle>
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          ></path>
        </svg>
        <p class="text-xs text-foreground-subtle font-medium">Cargando almacenes...</p>
      </div>
    </div>
  {:else if filtered.length === 0}
    <!-- Estado Vacío -->
    <Card class="flex flex-col items-center justify-center py-12 text-center">
      <div
        class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-foreground-subtle"
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          ><path
            d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"
          /><circle cx="12" cy="12" r="3" /></svg
        >
      </div>
      <h3 class="mt-4 text-base font-semibold text-foreground">Sin almacenes encontrados</h3>
      <p class="mt-1 text-xs text-foreground-muted max-w-sm">
        No se encontraron almacenes que coincidan con los criterios de búsqueda o filtro
        seleccionados.
      </p>
      <div class="mt-5">
        <Button variant="secondary" size="sm" onclick={resetFilters}>Limpiar filtros</Button>
      </div>
    </Card>
  {:else if viewMode === 'grid'}
    <!-- Vista Grid (3 cols desktop, 2 cols tablet, 1 col mobile) -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {#each filtered as wh (wh.id)}
        {@render WarehouseCard(wh, false)}
      {/each}
    </div>
  {:else}
    <!-- Vista Lista Compacta -->
    <div class="flex flex-col gap-3">
      {#each filtered as wh (wh.id)}
        {@render WarehouseCard(wh, true)}
      {/each}
    </div>
  {/if}

  {#if meta && meta.pages > 1}
    <div class="flex items-center justify-between gap-4 pt-1">
      <p class="text-xs text-foreground-muted">
        Página {meta.page} de {meta.pages} · {meta.total} almacenes
      </p>
      <div class="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          onclick={() => (page = Math.max(1, page - 1))}
          disabled={loading || meta.page <= 1}>Anterior</Button
        >
        <Button
          variant="secondary"
          size="sm"
          onclick={() => (page = Math.min(meta!.pages, page + 1))}
          disabled={loading || meta.page >= meta.pages}>Siguiente</Button
        >
      </div>
    </div>
  {/if}
</div>

<!-- Snippet de Tarjeta de Almacén (Grid y Lista Compacta) -->
{#snippet WarehouseCard(wh: Warehouse, isList: boolean)}
  {@const pct = utilizationPct(wh)}
  {@const color = getStrokeColor(pct, wh.status)}
  {@const isMaint = wh.status === 'maintenance'}
  {@const strokeDash = 2 * Math.PI * (isList ? 20 : 36)}
  {@const strokeOffset = strokeDash - (pct / 100) * strokeDash}

  <div
    class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 transition-all duration-200 hover:border-primary/40 hover:shadow-md flex {isList
      ? 'flex-col sm:flex-row sm:items-center justify-between gap-4'
      : 'flex-col gap-4'}"
  >
    <!-- Header de la tarjeta: Icono + Nombre + Código + Badge -->
    <div class="flex items-start justify-between gap-3 {isList ? 'sm:w-1/3 flex-none' : ''}">
      <div class="flex items-start gap-3 min-w-0">
        <div
          class="flex h-10 w-10 flex-none items-center justify-center rounded-lg bg-primary/10 text-primary"
        >
          {#if isMaint}
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              ><path
                d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"
              /></svg
            >
          {:else}
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              ><path
                d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"
              /><path d="m3.3 7 8.7 5 8.7-5" /><path d="M12 22V12" /></svg
            >
          {/if}
        </div>
        <div class="min-w-0">
          <h4 class="font-bold text-sm text-foreground truncate">{wh.name}</h4>
          <p class="font-mono text-[11px] text-foreground-subtle tracking-wide">{wh.code}</p>
        </div>
      </div>
      <Badge variant={STATUS_MAP[wh.status]?.variant || 'neutral'}>
        {STATUS_MAP[wh.status]?.label || wh.status}
      </Badge>
    </div>

    <!-- Cuerpo de la tarjeta: Medidor circular SVG de capacidad + Meta info -->
    <div class="flex items-center gap-4 {isList ? 'flex-1 justify-between' : ''}">
      <!-- Medidor Circular de Capacidad -->
      <div
        class="relative flex-none flex items-center justify-center"
        aria-label={isMaint
          ? 'Almacén fuera de servicio por mantenimiento'
          : `${pct}% de capacidad ocupada`}
        role="img"
      >
        <svg
          width={isList ? 52 : 88}
          height={isList ? 52 : 88}
          viewBox="0 0 {isList ? 52 : 88} {isList ? 52 : 88}"
          class="-rotate-90"
        >
          <circle
            cx={isList ? 26 : 44}
            cy={isList ? 26 : 44}
            r={isList ? 20 : 36}
            fill="none"
            stroke="rgb(var(--border))"
            stroke-width={isList ? 5 : 7}
          />
          <circle
            cx={isList ? 26 : 44}
            cy={isList ? 26 : 44}
            r={isList ? 20 : 36}
            fill="none"
            stroke={color}
            stroke-width={isList ? 5 : 7}
            stroke-dasharray={strokeDash}
            stroke-dashoffset={isMaint ? strokeDash : strokeOffset}
            stroke-linecap="round"
            class="transition-all duration-700 ease-out"
          />
        </svg>
        <div class="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span
            class="font-mono font-bold {isList ? 'text-xs' : 'text-base'} tabular-nums"
            style="color: {color};"
          >
            {isMaint ? '—' : `${pct}%`}
          </span>
          {#if !isList}
            <span class="text-[9px] font-semibold text-foreground-subtle uppercase tracking-wider">
              {isMaint ? 'OFFLINE' : 'USADO'}
            </span>
          {/if}
        </div>
      </div>

      <!-- Meta Info (Sucursal, Ubicación, Unidades y Productos) -->
      <div class="flex-1 space-y-1.5 text-xs">
        <p class="text-[11.5px] text-foreground-muted flex items-center gap-1.5 truncate">
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            class="flex-none text-foreground-subtle"
            ><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" /><circle
              cx="12"
              cy="10"
              r="3"
            /></svg
          >
          <span class="truncate">{wh.branchName} · {wh.location}</span>
        </p>
        <div class="flex items-center justify-between text-xs">
          <span class="text-foreground-subtle">Capacidad:</span>
          <span class="font-mono font-medium text-foreground"
            >{wh.used.toLocaleString()} / {wh.capacity.toLocaleString()} u</span
          >
        </div>
        <div class="flex items-center justify-between text-xs">
          <span class="text-foreground-subtle">Productos:</span>
          <span class="font-semibold text-foreground">{wh.products.toLocaleString()}</span>
        </div>
      </div>
    </div>

    <!-- Footer de la tarjeta: Último movimiento + Enlace ver detalle -->
    <div
      class="flex items-center justify-between border-t border-border/60 pt-3 text-xs text-foreground-subtle {isList
        ? 'sm:w-auto sm:border-t-0 sm:pt-0 gap-4'
        : ''}"
    >
      <span class="flex items-center gap-1">
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          ><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg
        >
        Últ. movimiento: {wh.lastMovement}
      </span>
      <div class="-mr-1.5 flex items-center">
        <KebabMenu
          orientation={isList ? 'vertical' : 'horizontal'}
          items={[
            {
              id: 'detail',
              label: 'Ver detalle',
              icon: 'detail',
              onClick: () => goto(`/warehouses/${wh.id}`)
            },
            ...(permissions.hasPermission('warehouses.update')
              ? [
                  {
                    id: 'edit',
                    label: 'Editar',
                    icon: 'edit' as const,
                    onClick: () => goto(`/warehouses/${wh.id}/edit`)
                  }
                ]
              : []),
            ...(permissions.hasAnyPermission(['warehouses.activate', 'warehouses.deactivate'])
              ? [
                  {
                    id: 'state',
                    label: wh.status === 'inactive' ? 'Activar' : 'Desactivar',
                    icon: 'power' as const,
                    variant: 'danger' as const,
                    onClick: () => toggleWarehouse(wh)
                  }
                ]
              : [])
          ]}
        />
      </div>
    </div>
  </div>
{/snippet}

<style>
  /* Scrollbar fina de Geist */
  .custom-scrollbar::-webkit-scrollbar {
    width: 4px;
  }
  .custom-scrollbar::-webkit-scrollbar-track {
    background: transparent;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb {
    background: rgb(var(--border-strong));
    border-radius: 9999px;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background: rgb(var(--foreground-subtle));
  }
</style>
