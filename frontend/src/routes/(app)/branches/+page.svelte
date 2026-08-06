<script lang="ts">
  /**
   * Módulo de Sucursales — ERP System (Vercel / Geist Design System).
   *
   * Rediseño Maestro-Detalle de 2 Columnas con 4 KPIs Superiores,
   * Tabla con acento primario y micro-sparklines, Menú de 3 puntos antirecorte,
   * Panel de Detalle Horizontal de 3 Secciones (debajo de la tabla) y Mapa
   * interactivo estirado al 100% de la altura combinada mostrando todas las sucursales.
   */

  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { goto } from '$app/navigation';
  import { type Branch } from '$lib/features/branches/types';
  import { getBranches } from '$lib/services/branches';
  import { api, HttpError } from '$lib/api/client';
  import { permissions } from '$lib/stores/permissions.svelte';
  import BranchTable from '$lib/features/branches/components/BranchTable.svelte';
  import BranchMap from '$lib/features/branches/components/BranchMap.svelte';
  import BranchDetail from '$lib/features/branches/components/BranchDetail.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { onMount } from 'svelte';
  import { company } from '$lib/stores/company.svelte';
  import { branch as operationalBranch } from '$lib/stores/branch.svelte';
  import { queryClient } from '$lib/services/query-client';

  let showMap = $state(true);
  let selectedId = $state<string | null>(null);
  let branches = $state<Branch[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let cityFilter = $state('');
  let statusFilter = $state<'all' | 'active' | 'inactive' | 'maintenance'>('all');

  const branchesQueryKey = $derived([
    'branches',
    company.id ?? 'none',
    operationalBranch.id ?? 'all'
  ] as const);

  async function loadBranches(force = false) {
    loading = true;
    try {
      if (force) await queryClient.invalidateQueries({ queryKey: branchesQueryKey });
      branches = await queryClient.fetchQuery({
        queryKey: branchesQueryKey,
        staleTime: force ? 0 : 30_000,
        queryFn: ({ signal }) => getBranches(signal)
      });
      if (selectedId && !branches.some((b) => b.id === selectedId)) {
        selectedId = null;
      }
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudieron cargar las sucursales.';
    } finally {
      loading = false;
    }
  }
  onMount(() => {
    void loadBranches();
    return () => {
      void queryClient.cancelQueries({ queryKey: branchesQueryKey, exact: true });
    };
  });
  async function toggleBranch(branch: Branch) {
    const activate = branch.status === 'inactive';
    if (!activate) {
      confirmation.request({
        kind: 'deactivate',
        title: 'Desactivar sucursal',
        description:
          'La sucursal dejará de estar disponible para nuevas operaciones. Primero deberán resolverse sus almacenes y asignaciones activas.',
        resourceName: branch.name,
        confirmLabel: 'Desactivar sucursal',
        execute: async () => {
          await api.branches.deactivate(branch.id);
          await loadBranches(true);
        }
      });
      return;
    }
    try {
      await api.branches.activate(branch.id);
      await loadBranches(true);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cambiar el estado.';
    }
  }

  let cities = $derived(Array.from(new Set(branches.map((b) => b.city))).sort());

  let filteredBranches = $derived.by(() => {
    let result = branches;

    if (cityFilter) {
      result = result.filter((b) => b.city === cityFilter);
    }

    if (statusFilter !== 'all') {
      result = result.filter((b) => b.status === statusFilter);
    }

    const q = globalSearch.query.toLowerCase().trim();
    if (q) {
      result = result.filter(
        (b) =>
          b.name.toLowerCase().includes(q) ||
          b.code.toLowerCase().includes(q) ||
          b.city.toLowerCase().includes(q) ||
          b.manager.toLowerCase().includes(q)
      );
    }

    return result;
  });

  let selectedBranch = $derived(
    selectedId ? (branches.find((b) => b.id === selectedId) ?? null) : null
  );

  function onSelect(id: string) {
    selectedId = selectedId === id ? null : id;
  }

  // --- Métricas calculadas dinámicamente ---
  let totalEmployees = $derived(branches.reduce((sum, b) => sum + b.employees, 0));
  let totalWarehouses = $derived(branches.reduce((sum, b) => sum + b.warehouses, 0));

  let activeCount = $derived(branches.filter((b) => b.status === 'active').length);
  let maintenanceCount = $derived(branches.filter((b) => b.status === 'maintenance').length);
  let inactiveCount = $derived(branches.filter((b) => b.status === 'inactive').length);
  let totalBranches = $derived(branches.length);

  // Perímetro y offset para el anillo SVG de sucursales activas
  const ringR = 16;
  const ringC = 2 * Math.PI * ringR; // ~100.53
  let ringOffset = $derived(
    totalBranches > 0 ? ringC - (activeCount / totalBranches) * ringC : ringC
  );
</script>

<svelte:head><title>Sucursales — ERP System</title></svelte:head>

<div
  class="p-4 sm:p-6 md:p-8 flex flex-col lg:h-[calc(100vh-3.5rem)] space-y-4 sm:space-y-5 overflow-auto lg:overflow-hidden"
>
  <!-- Header de la página -->
  <div
    class="flex flex-col sm:flex-row flex-none items-start sm:items-center justify-between gap-3 sm:gap-4"
  >
    <p class="text-sm text-foreground-muted">
      {filteredBranches.length} sucursal(es) registradas · Red de operaciones nacional
    </p>
    <div class="flex flex-wrap items-center gap-2 w-full sm:w-auto">
      <!-- Filtros -->
      <select
        bind:value={cityFilter}
        class="h-9 rounded-md border border-border bg-surface px-3 text-xs font-medium text-foreground focus:border-primary focus:outline-none"
      >
        <option value="">Todas las ciudades</option>
        {#each cities as city}<option value={city}>{city}</option>{/each}
      </select>

      <select
        bind:value={statusFilter}
        class="h-9 rounded-md border border-border bg-surface px-3 text-xs font-medium text-foreground focus:border-primary focus:outline-none hidden sm:block"
      >
        <option value="all">Todos los estados</option>
        <option value="active">Activas</option>
        <option value="maintenance">Mantenimiento</option>
        <option value="inactive">Inactivas</option>
      </select>

      <!-- Toggle mapa -->
      <button
        type="button"
        onclick={() => (showMap = !showMap)}
        class="flex h-9 items-center gap-2 rounded-lg border border-border bg-surface px-3 text-xs font-medium text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:shadow-glow"
        aria-label="Mostrar u ocultar el mapa"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
          class={showMap ? 'text-primary' : 'text-foreground-subtle'}
        >
          <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" /><line
            x1="8"
            y1="2"
            x2="8"
            y2="18"
          /><line x1="16" y1="6" x2="16" y2="22" />
        </svg>
        {showMap ? 'Ocultar mapa' : 'Mostrar mapa'}
      </button>

      {#if permissions.hasPermission('branches.create')}<Button
          size="sm"
          onclick={() => goto('/branches/new')}
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
          Crear sucursal
        </Button>{/if}
    </div>
  </div>
  <!-- FILA DE 4 KPI CARDS SUPERIORES -->
  <div class="grid flex-none grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
    <!-- KPI 1: Empleados -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Empleados</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            ><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle
              cx="9"
              cy="7"
              r="4"
            /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {totalEmployees}
        </div>
        <p class="text-[11px] text-foreground-subtle mt-1 truncate">
          En {totalBranches} sucursales
        </p>
      </div>
    </div>

    <!-- KPI 2: Almacenes -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Almacenes</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-success/10 text-success">
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
          {totalWarehouses}
        </div>
        <p class="text-[11px] text-foreground-subtle mt-1 truncate">Distribuidos en la red</p>
      </div>
    </div>

    <!-- KPI 3: Ventas del mes -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Ventas</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-warning/10 text-warning">
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            ><line x1="12" y1="1" x2="12" y2="23" /><path
              d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"
            /></svg
          >
        </div>
      </div>
      <div>
        <div class="text-sm font-bold text-foreground">Integración pendiente</div>
        <p class="text-[11px] text-foreground-subtle mt-1 truncate">
          Disponible al implementar Ventas
        </p>
      </div>
    </div>

    <!-- KPI 4: Sucursales activas con Mini Ring -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Sucursales activas</span
        >
        <div class="font-mono text-lg font-bold text-foreground">
          {activeCount}
          <span class="text-xs font-normal text-foreground-subtle">/ {totalBranches}</span>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <!-- Mini Anillo SVG -->
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
            r={ringR}
            fill="none"
            stroke="rgb(var(--border))"
            stroke-width="4.5"
          />
          <circle
            cx="20"
            cy="20"
            r={ringR}
            fill="none"
            stroke="rgb(var(--success))"
            stroke-width="4.5"
            stroke-dasharray={ringC.toFixed(1)}
            stroke-dashoffset={ringOffset.toFixed(1)}
            stroke-linecap="round"
            class="transition-all duration-700 ease-out"
          />
        </svg>
        <div class="text-[11px] space-y-0.5 text-foreground-muted">
          <p>
            <strong class="font-semibold text-warning">{maintenanceCount}</strong> en mantenimiento
          </p>
          <p>
            <strong class="font-semibold text-foreground-subtle">{inactiveCount}</strong> inactiva
          </p>
        </div>
      </div>
    </div>
  </div>

  <!-- GRID PRINCIPAL DE 2 COLUMNAS (MAESTRO-DETALLE + MAPA COMPLETO) -->
  {#if error}<div class="rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
      {error}
    </div>{/if}
  {#if loading}
    <div
      class="flex-1 flex items-center justify-center border border-border rounded-xl bg-surface-elevated shadow-sm"
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
        <p class="text-xs text-foreground-subtle font-medium">Cargando sucursales...</p>
      </div>
    </div>
  {:else}
    <div
      class="flex-1 min-h-0 grid grid-cols-1 {showMap
        ? 'lg:grid-cols-12'
        : 'grid-cols-1'} gap-5 items-stretch"
    >
      <!-- COLUMNA IZQUIERDA: Tabla de sucursales + Panel de detalle horizontal abajo -->
      <div
        class="{showMap
          ? 'lg:col-span-7 xl:col-span-7'
          : 'lg:col-span-12'} flex flex-col gap-5 flex-1 min-h-0"
      >
        <!-- Tabla Maestro -->
        <Card
          class="flex-1 min-h-0 flex flex-col overflow-hidden p-0 border border-border shadow-sm"
        >
          <BranchTable
            branches={filteredBranches}
            {selectedId}
            {onSelect}
            onEdit={permissions.hasPermission('branches.update')
              ? (item) => goto(`/branches/${item.id}/edit`)
              : undefined}
            onDelete={permissions.hasAnyPermission(['branches.activate', 'branches.deactivate'])
              ? (item) => void toggleBranch(item)
              : undefined}
          />
        </Card>

        <!-- Panel de Detalle Horizontal (Debajo de la tabla) -->
        <Card class="flex-none overflow-hidden p-0 border border-border shadow-sm">
          <BranchDetail branch={selectedBranch} />
        </Card>
      </div>

      <!-- COLUMNA DERECHA: Mapa a Alto Completo (Estirado al 100% del sobrante) -->
      {#if showMap}
        <div
          class="lg:col-span-5 xl:col-span-5 flex flex-col flex-1 min-h-[350px] lg:min-h-0 mt-4 lg:mt-0"
        >
          <div class="flex-1 h-full min-h-0 w-full">
            <BranchMap branches={filteredBranches} {selectedId} {onSelect} />
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>
