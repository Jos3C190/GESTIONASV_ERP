<script lang="ts">
  /** Detalle de almacén — hero persistente + tabs (Vercel/Geist + HIG Apple). */

  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { getWarehouse } from '$lib/services/warehouses';
  import { inventoryApi } from '$lib/features/inventory/services';
  import type { CapacitySummary } from '$lib/features/inventory/types';
  import CapacitySummaryPanel from '$lib/features/inventory/components/CapacitySummaryPanel.svelte';
  import HandlingUnitsPanel from '$lib/features/inventory/components/HandlingUnitsPanel.svelte';
  import WarehouseCapacityGroupsSummary from '$lib/features/warehouses/components/WarehouseCapacityGroupsSummary.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import {
    CAPACITY_ENFORCEMENT_LABEL,
    CAPACITY_PROFILE_LABEL,
    CAPACITY_STATUS_LABEL,
    STATUS_MAP,
    TYPE_LABEL,
    type CapacityStatus,
    type Warehouse,
    type WarehouseMovement
  } from '$lib/features/warehouses/types';
  import Avatar from '$lib/components/ui/Avatar.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Tabs from '$lib/components/ui/Tabs.svelte';

  let warehouse = $state<Warehouse | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let capacitySummary = $state<CapacitySummary | null>(null);
  let capacityLoading = $state(false);
  let capacityError = $state<string | null>(null);

  let warehouseId = $derived(page.params.id ?? '');

  async function loadData() {
    if (!warehouseId) return;
    const canLoadCapacity = permissions.hasPermission('inventory:capacity');
    loading = true;
    error = null;
    capacitySummary = null;
    capacityError = null;
    try {
      warehouse = await getWarehouse(warehouseId);
      if (canLoadCapacity) {
        capacityLoading = true;
        try {
          capacitySummary = await inventoryApi.getCapacitySummary(warehouseId);
        } catch (err) {
          capacityError =
            err instanceof Error ? err.message : 'No se pudo cargar la ocupación física.';
        } finally {
          capacityLoading = false;
        }
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Error al cargar el almacén.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void permissions.hasPermission('inventory:capacity');
    if (warehouseId) void loadData();
  });

  // === Métricas calculadas ===
  let shelvesOccupiedPct = $derived(
    warehouse && warehouse.shelvesTotal > 0 && warehouse.shelvesOccupied != null
      ? Math.round((warehouse.shelvesOccupied / warehouse.shelvesTotal) * 100)
      : null
  );

  // === Tabs ===
  const TABS = [
    { id: 'resumen', label: 'Resumen', icon: 'overview' },
    { id: 'inventario', label: 'Inventario', icon: 'inventory' },
    { id: 'operaciones', label: 'Operaciones', icon: 'operations' },
    { id: 'seguridad', label: 'Seguridad y cumplimiento', icon: 'security' }
  ];
  let activeTab = $state('resumen');

  // === Helpers ===
  function fmt(value: string | number | null | undefined, suffix = ''): string {
    if (value === null || value === undefined || value === '' || value === 0) return '—';
    return typeof value === 'number' ? value.toLocaleString() + suffix : value;
  }
  function fmtMoney(value: number): string {
    if (!value) return '—';
    return `$${value.toLocaleString()}`;
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

  function physicalMetric(value: number | null, unit: string): string {
    if (value == null) return 'No registrado';
    return `${Number(value).toLocaleString('es-SV', { maximumFractionDigits: 3 })} ${unit}`;
  }

  function movementTypeLabel(t: WarehouseMovement['type']): {
    label: string;
    color: string;
    bg: string;
  } {
    const m: Record<WarehouseMovement['type'], { label: string; color: string; bg: string }> = {
      inbound: { label: 'Entrada', color: 'text-success', bg: 'bg-success/10' },
      outbound: { label: 'Salida', color: 'text-primary', bg: 'bg-primary/10' },
      transfer: { label: 'Transferencia', color: 'text-warning', bg: 'bg-warning/10' },
      adjustment: { label: 'Ajuste', color: 'text-foreground-muted', bg: 'bg-surface-muted/60' }
    };
    return m[t];
  }

  function movementIcon(t: WarehouseMovement['type']): string {
    return t === 'inbound' ? '↓' : t === 'outbound' ? '↑' : t === 'transfer' ? '↔' : '⚙';
  }

  function stockStatus(
    qty: number,
    min: number,
    max: number
  ): { label: string; color: string; bg: string } {
    if (qty <= min) return { label: 'Bajo', color: 'text-danger', bg: 'bg-danger/10' };
    if (qty >= max * 0.9) return { label: 'Alto', color: 'text-warning', bg: 'bg-warning/10' };
    return { label: 'Normal', color: 'text-success', bg: 'bg-success/10' };
  }
</script>

<svelte:head
  ><title>{warehouse ? `${warehouse.name} — Almacenes` : 'Almacén — GestionaSV'}</title
  ></svelte:head
>

<div class="p-6 md:p-8">
  <!-- Header con back -->
  <div class="mb-6 flex items-center gap-3">
    <a
      href="/warehouses"
      class="flex h-8 w-8 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground"
      aria-label="Volver"
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
        aria-hidden="true"
        ><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg
      >
    </a>
    <div class="flex-1">
      <h1 class="text-xl font-bold text-foreground">Detalle del almacén</h1>
      <p class="text-sm text-foreground-muted">Información completa del almacén.</p>
    </div>
    {#if warehouse}
      <div class="flex items-center gap-2">
        {#if permissions.hasPermission('locations.view')}<Button
            variant="secondary"
            size="sm"
            onclick={() => goto(`/warehouses/${warehouseId}/locations`)}
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
              ><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path
                d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"
              /></svg
            >
            Ubicaciones
          </Button>{/if}
        {#if permissions.hasPermission('warehouses.update')}<Button
            size="sm"
            onclick={() => goto(`/warehouses/${warehouseId}/edit`)}
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
              ><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg
            >
            Editar
          </Button>{/if}
      </div>
    {/if}
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-16">
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
        <p class="text-xs text-foreground-subtle">Cargando almacén...</p>
      </div>
    </div>
  {:else if error}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {:else if warehouse}
    <!-- ========================================== -->
    <!-- HERO PERSISTENTE                           -->
    <!-- ========================================== -->
    <div class="space-y-5">
      <!-- Tarjeta de identidad -->
      <Card class="p-6">
        <div class="flex flex-col sm:flex-row items-start sm:items-center gap-5">
          <div
            class="flex h-16 w-16 flex-none items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-xs"
          >
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M20 7l-8-4-8 4m16 0v10l-8 4m8-14L12 11M4 7v10l8 4m0-14L4 7m8 4v10" />
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex flex-wrap items-center gap-3">
              <h2 class="text-lg font-bold text-foreground">{warehouse.name}</h2>
              <Badge variant={STATUS_MAP[warehouse.status]?.variant || 'neutral'}>
                {STATUS_MAP[warehouse.status]?.label || warehouse.status}
              </Badge>
            </div>
            <div
              class="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-foreground-muted"
            >
              <span class="font-mono text-xs">{warehouse.code}</span>
              <span class="flex items-center gap-1.5">
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="text-foreground-subtle"
                  ><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" /><circle
                    cx="12"
                    cy="10"
                    r="3"
                  /></svg
                >
                <button
                  onclick={() => warehouse && goto(`/branches/${warehouse.branchId}`)}
                  class="hover:text-primary transition-colors underline-offset-2 hover:underline"
                  >{warehouse.branchName}</button
                >
              </span>
              <span class="flex items-center gap-1.5">
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="text-foreground-subtle"
                  ><rect x="3" y="3" width="18" height="18" rx="2" /><path
                    d="M3 9h18M9 3v18"
                  /></svg
                >
                {warehouse.location}
              </span>
              <span
                class="inline-flex items-center gap-1 rounded-md border border-border bg-surface-muted/40 px-1.5 py-0.5 text-[10.5px] font-medium text-foreground-muted"
              >
                {TYPE_LABEL[warehouse.type]}
              </span>
            </div>
          </div>
          <div class="flex flex-none flex-col items-start gap-1.5 sm:items-end">
            <p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
              Estado de capacidad
            </p>
            <Badge variant={capacityVariant(capacitySummary?.status ?? warehouse.capacityStatus)}>
              {CAPACITY_STATUS_LABEL[capacitySummary?.status ?? warehouse.capacityStatus]}
            </Badge>
            <p class="text-[10px] text-foreground-muted">
              {capacityLoading
                ? 'Calculando ocupación…'
                : capacitySummary?.effectiveUtilizationPct == null
                  ? capacitySummary?.measurementStatus === 'incomplete'
                    ? 'Hay mercancía pendiente de medir'
                    : 'Ocupación no calculable'
                  : `${capacitySummary.effectiveUtilizationPct.toLocaleString('es-SV', { maximumFractionDigits: 1 })}% proyectado`}
            </p>
          </div>
        </div>
      </Card>

      {#if warehouse.images.length > 0}
        <section aria-labelledby="warehouse-gallery-title">
          <h3 id="warehouse-gallery-title" class="mb-3 text-sm font-semibold text-foreground">
            Galería del almacén
          </h3>
          <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {#each warehouse.images as image, index (image.public_id ?? image.url)}
              <figure class={index === 0 ? 'col-span-2 row-span-2' : ''}>
                <img
                  src={image.url}
                  alt={image.caption || `${warehouse.name}, imagen ${index + 1}`}
                  class="aspect-video h-full w-full rounded-xl border border-border object-cover shadow-soft"
                />
                {#if image.caption}<figcaption class="mt-1 text-xs text-foreground-muted">
                    {image.caption}
                  </figcaption>{/if}
              </figure>
            {/each}
          </div>
        </section>
      {/if}

      <!-- Métricas clave + Encargado (grid horizontal siempre visible) -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Encargado -->
        <Card class="p-5">
          <p
            class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-3 flex items-center gap-1.5"
          >
            <svg
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle
                cx="12"
                cy="7"
                r="4"
              /></svg
            >
            Encargado
          </p>
          <div class="flex items-center gap-2.5">
            <Avatar initials={warehouse.managerInitials || '??'} size={36} />
            <div class="min-w-0 flex-1">
              <p class="text-sm font-semibold text-foreground truncate">
                {warehouse.manager || 'Sin asignar'}
              </p>
              <p class="text-[11px] text-foreground-subtle">Encargado de almacén</p>
            </div>
          </div>
        </Card>

        <!-- Dimensiones y capacidad física -->
        <Card class="p-5">
          <p
            class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-3 flex items-center gap-1.5"
          >
            <svg
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M9 3v18" /></svg
            >
            Capacidad física
          </p>
          <dl class="space-y-1 text-[11.5px]">
            <div class="flex items-center justify-between gap-2">
              <dt class="text-foreground-muted">Área</dt>
              <dd class="font-mono text-foreground">{fmt(warehouse.area)} m²</dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-foreground-muted">Dimensiones generales</dt>
              <dd class="font-mono text-foreground text-[10.5px]">
                {fmt(warehouse.length)} × {fmt(warehouse.width)} × {fmt(warehouse.height)} m
              </dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-foreground-muted">Dimensiones útiles</dt>
              <dd class="font-mono text-foreground text-[10.5px]">
                {warehouse.usableLengthM == null ? '—' : warehouse.usableLengthM} ×
                {warehouse.usableWidthM == null ? '—' : warehouse.usableWidthM} ×
                {warehouse.usableHeightM == null ? '—' : warehouse.usableHeightM} m
              </dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-foreground-muted">Peso operativo</dt>
              <dd class="font-mono text-foreground">
                {physicalMetric(warehouse.operationalMaxWeightKg, 'kg')}
              </dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-foreground-muted">Peso certificado</dt>
              <dd class="font-mono text-foreground">
                {physicalMetric(warehouse.certifiedMaxWeightKg, 'kg')}
              </dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-foreground-muted">Volumen operativo</dt>
              <dd class="font-mono text-foreground">
                {physicalMetric(warehouse.operationalUsableVolumeM3, 'm³')}
              </dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-foreground-muted">Volumen certificado</dt>
              <dd class="font-mono text-foreground">
                {physicalMetric(warehouse.certifiedUsableVolumeM3, 'm³')}
              </dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-foreground-muted">Perfil</dt>
              <dd class="text-right text-foreground">
                {CAPACITY_PROFILE_LABEL[warehouse.capacityProfile]}
              </dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-foreground-muted">Control</dt>
              <dd class="text-right text-foreground">
                {CAPACITY_ENFORCEMENT_LABEL[warehouse.capacityEnforcementMode]}
              </dd>
            </div>
            <div class="flex items-center justify-between gap-2">
              <dt class="text-foreground-muted">Elegible</dt>
              <dd class="text-foreground">{warehouse.storageEligible ? 'Sí' : 'No'}</dd>
            </div>
          </dl>
        </Card>

        <!-- Capacidad y movimiento -->
        <Card class="p-5">
          <p
            class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-3 flex items-center gap-1.5"
          >
            <svg
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"><path d="M3 3v18h18" /><path d="m7 14 4-4 4 4 6-6" /></svg
            >
            Movimiento reciente
          </p>
          {#if warehouse.dailyMovementsAvg > 0}
            <div class="grid grid-cols-2 gap-2 mb-2">
              <div class="rounded-md border border-border bg-surface-muted/40 px-2 py-1.5">
                <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                  Entradas mes
                </p>
                <p class="font-mono text-sm font-bold tabular-nums text-success">
                  {fmt(warehouse.inboundThisMonth)}
                </p>
              </div>
              <div class="rounded-md border border-border bg-surface-muted/40 px-2 py-1.5">
                <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                  Salidas mes
                </p>
                <p class="font-mono text-sm font-bold tabular-nums text-primary">
                  {fmt(warehouse.outboundThisMonth)}
                </p>
              </div>
            </div>
            <p class="text-[10.5px] text-foreground-subtle">
              Últ. movimiento: <span class="font-medium text-foreground"
                >{warehouse.lastMovement}</span
              >
            </p>
          {:else}
            <p class="text-xs text-foreground-subtle">Sin movimientos recientes</p>
          {/if}
        </Card>

        <!-- Inventario valorizado -->
        <Card class="p-5">
          <p
            class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-3 flex items-center gap-1.5"
          >
            <svg
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><line x1="12" y1="1" x2="12" y2="23" /><path
                d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"
              /></svg
            >
            Valor inventario
          </p>
          <p class="font-mono text-2xl font-bold tabular-nums text-foreground leading-none">
            {fmtMoney(warehouse.inventoryValue)}
          </p>
          <p class="mt-1 text-[10.5px] text-foreground-subtle">
            {fmt(warehouse.totalSKUs)} SKUs · rotación
            {warehouse.inventoryTurnover > 0
              ? `${warehouse.inventoryTurnover.toFixed(1)}x/año`
              : 'no calculada'}
          </p>
        </Card>
      </div>
    </div>

    <!-- ========================================== -->
    <!-- TABS STICKY                                 -->
    <!-- ========================================== -->
    <Tabs items={TABS} bind:active={activeTab} sticky={true} />

    <div class="mt-5">
      <!-- TAB: Resumen -->
      {#if activeTab === 'resumen'}
        <div id="tab-panel-resumen" role="tabpanel" aria-labelledby="tab-resumen" class="space-y-5">
          <CapacitySummaryPanel
            summary={capacitySummary}
            loading={capacityLoading}
            error={capacityError}
          />

          <WarehouseCapacityGroupsSummary
            warehouseId={warehouse.id}
            canViewLocations={permissions.hasPermission('locations.view')}
          />

          <!-- Ocupación de estantes -->
          {#if warehouse.shelvesTotal > 0 && warehouse.shelvesOccupied != null}
            <Card class="p-6">
              <h3 class="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="text-foreground-subtle"
                  ><line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line
                    x1="8"
                    y1="18"
                    x2="21"
                    y2="18"
                  /><line x1="3" y1="6" x2="3.01" y2="6" /><line
                    x1="3"
                    y1="12"
                    x2="3.01"
                    y2="12"
                  /><line x1="3" y1="18" x2="3.01" y2="18" /></svg
                >
                Ocupación de estantes
              </h3>
              <div
                class="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-2"
              >
                <span>{warehouse.shelvesOccupied} ocupados de {warehouse.shelvesTotal} totales</span
                >
                <span class="font-mono text-foreground">{shelvesOccupiedPct ?? '—'}%</span>
              </div>
              <div class="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  style="width: {shelvesOccupiedPct ?? 0}%; background: {(shelvesOccupiedPct ??
                    0) >= 90
                    ? 'rgb(var(--danger))'
                    : (shelvesOccupiedPct ?? 0) >= 70
                      ? 'rgb(var(--warning))'
                      : 'rgb(var(--success))'};"
                ></div>
              </div>
              <p class="mt-2 text-[11px] text-foreground-muted">
                {warehouse.shelvesTotal - warehouse.shelvesOccupied} estantes disponibles para asignación
              </p>
            </Card>
          {/if}

          <!-- Resumen ejecutivo: alertas e indicadores -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
            <Card class="p-6">
              <h3 class="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="text-foreground-subtle"
                  ><path
                    d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
                  /><line x1="12" y1="9" x2="12" y2="13" /><line
                    x1="12"
                    y1="17"
                    x2="12.01"
                    y2="17"
                  /></svg
                >
                Alertas operativas
              </h3>
              <ul class="space-y-2.5 text-[12.5px]">
                {#if warehouse.lowStockItems > 0}
                  <li class="flex items-start gap-2.5">
                    <span
                      class="mt-0.5 inline-flex h-5 w-5 flex-none items-center justify-center rounded-full bg-warning/15 text-warning text-[10px] font-bold"
                      >!</span
                    >
                    <div>
                      <p class="font-medium text-foreground">
                        {warehouse.lowStockItems} producto(s) bajo stock mínimo
                      </p>
                      <p class="text-[11px] text-foreground-muted">
                        Revisar reposición en panel de inventario
                      </p>
                    </div>
                  </li>
                {/if}
                {#if warehouse.expiringItems > 0}
                  <li class="flex items-start gap-2.5">
                    <span
                      class="mt-0.5 inline-flex h-5 w-5 flex-none items-center justify-center rounded-full bg-warning/15 text-warning text-[10px] font-bold"
                      >!</span
                    >
                    <div>
                      <p class="font-medium text-foreground">
                        {warehouse.expiringItems} producto(s) próximos a vencer
                      </p>
                      <p class="text-[11px] text-foreground-muted">Revisar fechas de caducidad</p>
                    </div>
                  </li>
                {/if}
                <li class="flex items-start gap-2.5">
                  <span
                    class="mt-0.5 inline-flex h-5 w-5 flex-none items-center justify-center rounded-full bg-primary/15 text-primary text-[10px] font-bold"
                    >i</span
                  >
                  <div>
                    <p class="font-medium text-foreground">
                      {capacityLoading
                        ? 'Calculando ocupación física'
                        : capacityError
                          ? 'Ocupación física no disponible'
                          : capacitySummary?.measurementStatus === 'incomplete'
                            ? 'Mercancía pendiente de medir'
                            : capacitySummary
                              ? 'Ocupación física actualizada'
                              : 'Ocupación física no cargada'}
                    </p>
                    <p class="text-[11px] text-foreground-muted">
                      {capacityError
                        ? capacityError
                        : capacitySummary?.measurementStatus === 'incomplete'
                          ? 'Los porcentajes desconocidos no se sustituyen por cero.'
                          : capacitySummary
                            ? 'Incluye existencias y reservas vigentes por peso y volumen.'
                            : 'Consulte el resumen de capacidad con permiso de inventario.'}
                    </p>
                  </div>
                </li>
                {#if shelvesOccupiedPct != null && warehouse.shelvesTotal > 0 && shelvesOccupiedPct < 30 && warehouse.status === 'active'}
                  <li class="flex items-start gap-2.5">
                    <span
                      class="mt-0.5 inline-flex h-5 w-5 flex-none items-center justify-center rounded-full bg-primary/15 text-primary text-[10px] font-bold"
                      >i</span
                    >
                    <div>
                      <p class="font-medium text-foreground">
                        Baja utilización de estantes ({shelvesOccupiedPct}%)
                      </p>
                      <p class="text-[11px] text-foreground-muted">
                        Oportunidad de consolidación con otro almacén
                      </p>
                    </div>
                  </li>
                {/if}
                {#if warehouse.lowStockItems === 0 && warehouse.expiringItems === 0 && !(shelvesOccupiedPct != null && warehouse.shelvesTotal > 0 && shelvesOccupiedPct < 30 && warehouse.status === 'active')}
                  <li class="flex items-center gap-2.5 text-foreground-muted">
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      class="text-success flex-none"><polyline points="20 6 9 17 4 12" /></svg
                    >
                    Sin alertas de existencias registradas.
                  </li>
                {/if}
              </ul>
            </Card>

            <Card class="p-6">
              <h3 class="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="text-foreground-subtle"
                  ><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path
                    d="m9 12 2 2 4-4"
                  /></svg
                >
                Estado del sistema
              </h3>
              <ul class="space-y-2.5 text-[12.5px]">
                <li class="flex items-center justify-between">
                  <span class="text-foreground-muted">Alarma</span>
                  {#if warehouse.hasAlarm}
                    <span class="inline-flex items-center gap-1 text-success font-semibold">
                      <svg
                        width="12"
                        height="12"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="3"
                        stroke-linecap="round"
                        stroke-linejoin="round"><polyline points="20 6 9 17 4 12" /></svg
                      >
                      Activa
                    </span>
                  {:else}
                    <span class="text-foreground-muted">Inactiva</span>
                  {/if}
                </li>
                <li class="flex items-center justify-between">
                  <span class="text-foreground-muted">Cámaras CCTV</span>
                  <span class="font-mono text-foreground">{warehouse.cameras} activas</span>
                </li>
                <li class="flex items-center justify-between">
                  <span class="text-foreground-muted">Control de acceso</span>
                  <span class="text-foreground capitalize"
                    >{warehouse.accessControl.replace('_', ' ')}</span
                  >
                </li>
                <li class="flex items-center justify-between">
                  <span class="text-foreground-muted">Personal</span>
                  <span class="font-mono text-foreground"
                    >{warehouse.operators} operarios ({warehouse.shifts.length} turnos)</span
                  >
                </li>
                <li class="flex items-center justify-between">
                  <span class="text-foreground-muted">Certificaciones</span>
                  <span class="text-foreground">{warehouse.certifications.length} vigentes</span>
                </li>
              </ul>
            </Card>
          </div>
        </div>

        <!-- TAB: Inventario -->
      {:else if activeTab === 'inventario'}
        <div
          id="tab-panel-inventario"
          role="tabpanel"
          aria-labelledby="tab-inventario"
          class="space-y-5"
        >
          <!-- Resumen inventario: KPIs -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="rounded-lg border border-border bg-surface-muted/40 p-3 text-center">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Total SKUs
              </p>
              <p class="font-mono text-xl font-bold tabular-nums text-foreground mt-1">
                {fmt(warehouse.totalSKUs)}
              </p>
            </div>
            <div class="rounded-lg border border-border bg-warning/10 p-3 text-center">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Bajo stock
              </p>
              <p class="font-mono text-xl font-bold tabular-nums text-warning mt-1">
                {fmt(warehouse.lowStockItems)}
              </p>
            </div>
            <div class="rounded-lg border border-border bg-primary/10 p-3 text-center">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Por vencer
              </p>
              <p class="font-mono text-xl font-bold tabular-nums text-primary mt-1">
                {fmt(warehouse.expiringItems)}
              </p>
            </div>
            <div class="rounded-lg border border-border bg-success/10 p-3 text-center">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Rotación
              </p>
              <p class="font-mono text-xl font-bold tabular-nums text-success mt-1">
                {warehouse.inventoryTurnover > 0
                  ? `${warehouse.inventoryTurnover.toFixed(1)}x/año`
                  : '—'}
              </p>
            </div>
          </div>

          {#if permissions.hasPermission('inventory:read')}
            <HandlingUnitsPanel
              warehouseId={warehouse.id}
              canVerify={permissions.hasPermission('inventory:receive')}
            />
          {:else}
            <Card class="p-5">
              <p class="text-sm font-semibold text-foreground">Inventario físico restringido</p>
              <p class="mt-1 text-xs text-foreground-muted">
                Su rol no permite consultar las unidades logísticas de este almacén.
              </p>
            </Card>
          {/if}

          <!-- Top categorías -->
          {#if warehouse.topCategories.length > 0}
            <Card class="p-6">
              <h3 class="mb-3 text-sm font-semibold text-foreground flex items-center gap-2">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="text-foreground-subtle"
                  ><path
                    d="M20 7l-8-4-8 4m16 0v10l-8 4m8-14L12 11M4 7v10l8 4m0-14L4 7m8 4v10"
                  /></svg
                >
                Top categorías
              </h3>
              <div class="flex flex-wrap gap-1.5">
                {#each warehouse.topCategories as cat, i (cat)}
                  <span
                    class="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface-muted/40 px-2.5 py-1 text-[12px] font-medium text-foreground"
                  >
                    <span
                      class="flex h-4 w-4 flex-none items-center justify-center rounded-full bg-primary/15 text-[10px] font-bold text-primary"
                      >{i + 1}</span
                    >
                    {cat}
                  </span>
                {/each}
              </div>
            </Card>
          {/if}

          <!-- Top productos -->
          {#if warehouse.topProducts.length > 0}
            <Card class="p-6">
              <h3 class="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="text-foreground-subtle"
                  ><polyline points="3 6 5 6 21 6" /><path
                    d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
                  /></svg
                >
                Top productos
              </h3>
              <div class="overflow-x-auto rounded-lg border border-border">
                <table class="w-full text-xs">
                  <thead class="bg-surface-muted/50 border-b border-border">
                    <tr>
                      <th class="px-3 py-2 text-left font-semibold text-foreground">SKU</th>
                      <th class="px-3 py-2 text-left font-semibold text-foreground">Producto</th>
                      <th class="px-3 py-2 text-left font-semibold text-foreground">Categoría</th>
                      <th class="px-3 py-2 text-right font-semibold text-foreground">Cantidad</th>
                      <th class="px-3 py-2 text-center font-semibold text-foreground">Estado</th>
                      <th class="px-3 py-2 text-right font-semibold text-foreground">Vence</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-border">
                    {#each warehouse.topProducts as p (p.sku)}
                      {@const status = stockStatus(p.quantity, p.minStock, p.maxStock)}
                      <tr class="hover:bg-surface-muted/30">
                        <td class="px-3 py-2 font-mono text-foreground">{p.sku}</td>
                        <td class="px-3 py-2 text-foreground">{p.name}</td>
                        <td class="px-3 py-2 text-foreground-muted">{p.category}</td>
                        <td class="px-3 py-2 text-right font-mono tabular-nums text-foreground">
                          {p.quantity.toLocaleString()}
                          <span class="text-foreground-muted">{p.unit}</span>
                        </td>
                        <td class="px-3 py-2 text-center">
                          <span
                            class="inline-flex items-center rounded-md {status.bg} px-1.5 py-0.5 text-[10.5px] font-semibold {status.color}"
                            >{status.label}</span
                          >
                        </td>
                        <td class="px-3 py-2 text-right font-mono text-foreground-muted"
                          >{p.expiryDate ?? '—'}</td
                        >
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            </Card>
          {/if}

          <!-- Movimientos recientes -->
          {#if warehouse.recentMovements.length > 0}
            <Card class="p-6">
              <h3 class="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="text-foreground-subtle"
                  ><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg
                >
                Movimientos recientes
              </h3>
              <ul class="space-y-2">
                {#each warehouse.recentMovements as m (m.id)}
                  {@const mt = movementTypeLabel(m.type)}
                  <li
                    class="flex items-center gap-3 rounded-lg border border-border bg-surface-muted/20 p-3 hover:bg-surface-muted/40 transition-colors"
                  >
                    <span
                      class="flex h-8 w-8 flex-none items-center justify-center rounded-full {mt.bg} {mt.color} text-base font-bold"
                    >
                      {movementIcon(m.type)}
                    </span>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2">
                        <span
                          class="inline-flex items-center rounded-md {mt.bg} px-1.5 py-0.5 text-[10.5px] font-semibold {mt.color}"
                          >{mt.label}</span
                        >
                        <span class="font-mono text-[11px] text-foreground-muted"
                          >{m.reference}</span
                        >
                      </div>
                      <p class="mt-0.5 text-sm text-foreground">
                        <span class="font-medium">{m.quantity.toLocaleString()} ×</span>
                        <span class="font-mono text-foreground-muted text-[11.5px]"
                          >{m.productSku}</span
                        >
                        {m.productName}
                      </p>
                    </div>
                    <div class="hidden sm:block text-right flex-none">
                      <p class="text-[11px] text-foreground-muted">{m.date}</p>
                      <p class="text-[11px] text-foreground">{m.operator}</p>
                    </div>
                  </li>
                {/each}
              </ul>
            </Card>
          {/if}
        </div>

        <!-- TAB: Operaciones -->
      {:else if activeTab === 'operaciones'}
        <div
          id="tab-panel-operaciones"
          role="tabpanel"
          aria-labelledby="tab-operaciones"
          class="space-y-5"
        >
          <!-- Personal y turnos -->
          <Card class="p-6">
            <h3 class="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="text-foreground-subtle"
                ><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle
                  cx="9"
                  cy="7"
                  r="4"
                /><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></svg
              >
              Personal y turnos
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <div class="flex items-baseline gap-2 mb-3">
                  <span class="font-mono text-3xl font-bold tabular-nums text-foreground"
                    >{warehouse.operators}</span
                  >
                  <span class="text-sm text-foreground-muted">operarios asignados</span>
                </div>
                <p class="text-xs text-foreground-muted">
                  Cobertura de {warehouse.shifts.length}
                  {warehouse.shifts.length === 1 ? 'turno' : 'turnos'}
                </p>
              </div>
              <div class="space-y-2">
                <p
                  class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-2"
                >
                  Turnos operativos
                </p>
                {#if warehouse.shifts.length > 0}
                  <div class="flex flex-wrap gap-2">
                    {#each warehouse.shifts as s (s)}
                      <span
                        class="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface-muted/40 px-2.5 py-1 text-xs font-medium text-foreground"
                      >
                        {#if s === 'mañana'}
                          <svg
                            width="12"
                            height="12"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            class="text-warning"
                            ><circle cx="12" cy="12" r="5" /><path
                              d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"
                            /></svg
                          >
                        {:else if s === 'tarde'}
                          <svg
                            width="12"
                            height="12"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            class="text-primary"
                            ><path d="M17 18a5 5 0 0 0-10 0" /><line
                              x1="12"
                              y1="2"
                              x2="12"
                              y2="9"
                            /><line x1="4.22" y1="10.22" x2="5.64" y2="11.64" /><line
                              x1="1"
                              y1="18"
                              x2="3"
                              y2="18"
                            /><line x1="21" y1="18" x2="23" y2="18" /><line
                              x1="18.36"
                              y1="5.64"
                              x2="19.78"
                              y2="6.78"
                            /><line x1="23" y1="22" x2="1" y2="22" /><polyline
                              points="8 6 12 10 16 6"
                            /></svg
                          >
                        {:else}
                          <svg
                            width="12"
                            height="12"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            class="text-foreground-muted"
                            ><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg
                          >
                        {/if}
                        {s.charAt(0).toUpperCase() + s.slice(1)}
                      </span>
                    {/each}
                  </div>
                {:else}
                  <p class="text-xs text-foreground-muted">Sin turnos asignados</p>
                {/if}
              </div>
            </div>
          </Card>

          <!-- Condiciones ambientales + Mantenimiento -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Card class="p-6">
              <h3 class="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="text-foreground-subtle"
                  ><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z" /></svg
                >
                Condiciones ambientales
              </h3>
              <dl class="space-y-3 text-sm">
                <div class="flex items-center justify-between gap-2">
                  <dt class="text-foreground-muted">Temperatura</dt>
                  <dd class="font-mono text-foreground text-right">
                    {fmt(warehouse.temperatureRange)}
                  </dd>
                </div>
                <div class="flex items-center justify-between gap-2">
                  <dt class="text-foreground-muted">Humedad relativa</dt>
                  <dd class="font-mono text-foreground text-right">
                    {fmt(warehouse.humidityRange)}
                  </dd>
                </div>
                <div class="flex items-center justify-between gap-2">
                  <dt class="text-foreground-muted">Sistema de climatización</dt>
                  <dd class="text-foreground text-right capitalize">
                    {fmt(warehouse.cooling.replace('_', ' '))}
                  </dd>
                </div>
                <div class="flex items-center justify-between gap-2">
                  <dt class="text-foreground-muted">Ventilación</dt>
                  <dd class="text-foreground text-right">
                    {#if warehouse.hasVentilation}
                      <span class="inline-flex items-center gap-1 text-success font-semibold">
                        <svg
                          width="12"
                          height="12"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="3"
                          stroke-linecap="round"
                          stroke-linejoin="round"><polyline points="20 6 9 17 4 12" /></svg
                        >
                        Activa
                      </span>
                    {:else}
                      <span class="text-foreground-muted">Inactiva</span>
                    {/if}
                  </dd>
                </div>
              </dl>
            </Card>

            <Card class="p-6">
              <h3 class="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="text-foreground-subtle"
                  ><path
                    d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"
                  /></svg
                >
                Mantenimiento
              </h3>
              <dl class="space-y-3 text-sm">
                <div class="flex items-center justify-between gap-2">
                  <dt class="text-foreground-muted">Último mantenimiento</dt>
                  <dd class="text-foreground text-right">{fmt(warehouse.lastMaintenance)}</dd>
                </div>
                <div class="flex items-center justify-between gap-2">
                  <dt class="text-foreground-muted">Próximo mantenimiento</dt>
                  <dd class="font-mono text-foreground text-right">
                    {fmt(warehouse.nextMaintenance)}
                  </dd>
                </div>
                {#if warehouse.maintenanceNotes}
                  <div class="pt-3 mt-1 border-t border-border/60">
                    <dt
                      class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-1.5"
                    >
                      Notas
                    </dt>
                    <dd class="text-foreground-muted text-[12px] leading-relaxed">
                      {warehouse.maintenanceNotes}
                    </dd>
                  </div>
                {/if}
              </dl>
            </Card>
          </div>
        </div>

        <!-- TAB: Seguridad y cumplimiento -->
      {:else if activeTab === 'seguridad'}
        <div
          id="tab-panel-seguridad"
          role="tabpanel"
          aria-labelledby="tab-seguridad"
          class="space-y-5"
        >
          <!-- Seguridad -->
          <Card class="p-6">
            <h3 class="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="text-foreground-subtle"
                ><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg
              >
              Seguridad y vigilancia
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
              <div class="space-y-3">
                <p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
                  Control de acceso
                </p>
                <div class="flex items-center gap-2.5">
                  <div
                    class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary"
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
                      ><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path
                        d="M7 11V7a5 5 0 0 1 10 0v4"
                      /></svg
                    >
                  </div>
                  <div>
                    <p class="text-sm font-semibold text-foreground capitalize">
                      {warehouse.accessControl.replace('_', ' ')}
                    </p>
                    <p class="text-[10.5px] text-foreground-muted">Sistema principal de acceso</p>
                  </div>
                </div>
              </div>

              <div class="space-y-3">
                <p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
                  Vigilancia
                </p>
                <div class="flex items-center gap-2.5">
                  <div
                    class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary"
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
                      ><path d="M23 7l-7 5 7 5V7z" /><rect
                        x="1"
                        y="5"
                        width="15"
                        height="14"
                        rx="2"
                        ry="2"
                      /></svg
                    >
                  </div>
                  <div>
                    <p class="text-sm font-semibold text-foreground">
                      {warehouse.cameras} cámaras CCTV
                    </p>
                    <p class="text-[10.5px] text-foreground-muted">Cobertura 24/7 con grabación</p>
                  </div>
                </div>
              </div>

              <div class="space-y-3">
                <p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
                  Alarma
                </p>
                <div class="flex items-center gap-2.5">
                  <div
                    class="flex h-10 w-10 items-center justify-center rounded-lg {warehouse.hasAlarm
                      ? 'bg-success/10 text-success'
                      : 'bg-surface-muted text-foreground-muted'}"
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
                      ><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path
                        d="M13.73 21a2 2 0 0 1-3.46 0"
                      /></svg
                    >
                  </div>
                  <div>
                    <p class="text-sm font-semibold text-foreground">
                      {warehouse.hasAlarm ? 'Sistema activo' : 'Sin sistema de alarma'}
                    </p>
                    <p class="text-[10.5px] text-foreground-muted">
                      Última auditoría: {fmt(warehouse.lastSecurityAudit)}
                    </p>
                  </div>
                </div>
              </div>

              <div class="space-y-3">
                <p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
                  Sistema contra incendio
                </p>
                <div class="flex flex-wrap gap-1.5">
                  {#if warehouse.fireSystem.length > 0}
                    {#each warehouse.fireSystem as f (f)}
                      <span
                        class="inline-flex items-center gap-1 rounded-md border border-primary/20 bg-primary/5 px-2 py-1 text-[11px] font-medium text-primary"
                      >
                        <svg
                          width="10"
                          height="10"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="3"
                          stroke-linecap="round"
                          stroke-linejoin="round"><polyline points="20 6 9 17 4 12" /></svg
                        >
                        {f}
                      </span>
                    {/each}
                  {:else}
                    <p class="text-xs text-foreground-muted">
                      Sin sistema contra incendio registrado
                    </p>
                  {/if}
                </div>
              </div>
            </div>
          </Card>

          <!-- Cumplimiento -->
          <Card class="p-6">
            <h3 class="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="text-foreground-subtle"
                ><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline
                  points="14 2 14 8 20 8"
                /><line x1="9" y1="13" x2="15" y2="13" /><line
                  x1="9"
                  y1="17"
                  x2="15"
                  y2="17"
                /></svg
              >
              Cumplimiento y certificaciones
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
              <div class="space-y-3">
                <p
                  class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-2"
                >
                  Permiso sanitario
                </p>
                {#if warehouse.sanitaryPermit}
                  <div class="rounded-lg border border-border bg-surface-muted/30 p-3">
                    <p class="font-mono text-xs font-semibold text-foreground">
                      {warehouse.sanitaryPermit}
                    </p>
                    <p class="mt-1 text-[11px] text-foreground-muted">
                      Vence: <span class="font-mono">{fmt(warehouse.sanitaryPermitExpiry)}</span>
                    </p>
                  </div>
                {:else}
                  <p class="text-xs text-foreground-muted">Sin permiso sanitario registrado</p>
                {/if}
              </div>

              <div class="space-y-3">
                <p
                  class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-2"
                >
                  Última inspección
                </p>
                <div class="rounded-lg border border-border bg-surface-muted/30 p-3">
                  <p class="text-sm font-semibold text-foreground">
                    {fmt(warehouse.lastInspection)}
                  </p>
                  <p class="mt-1 text-[11px] text-foreground-muted">
                    Inspección física y documental
                  </p>
                </div>
              </div>

              <div class="md:col-span-2">
                <p
                  class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-2"
                >
                  Certificaciones
                </p>
                {#if warehouse.certifications.length > 0}
                  <div class="flex flex-wrap gap-1.5">
                    {#each warehouse.certifications as c (c)}
                      <span
                        class="inline-flex items-center gap-1.5 rounded-md border border-success/20 bg-success/5 px-2.5 py-1 text-[12px] font-medium text-success"
                      >
                        <svg
                          width="11"
                          height="11"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="2"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          ><circle cx="12" cy="8" r="6" /><polyline
                            points="9 14.5 11 16.5 15 13"
                          /></svg
                        >
                        {c}
                      </span>
                    {/each}
                  </div>
                {:else}
                  <p class="text-xs text-foreground-muted">Sin certificaciones registradas</p>
                {/if}
              </div>
            </div>
          </Card>

          <!-- Información del sistema -->
          <Card class="p-6">
            <h3 class="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="text-foreground-subtle"
                ><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg
              >
              Información del sistema
            </h3>
            <dl class="grid grid-cols-1 md:grid-cols-3 gap-x-8 gap-y-3 text-sm">
              <div class="flex items-center justify-between gap-2">
                <dt class="text-foreground-muted">ID interno</dt>
                <dd class="font-mono text-foreground text-right">{warehouse.id}</dd>
              </div>
              <div class="flex items-center justify-between gap-2">
                <dt class="text-foreground-muted">Creado</dt>
                <dd class="text-foreground text-right">{fmt(warehouse.createdAt)}</dd>
              </div>
              <div class="flex items-center justify-between gap-2">
                <dt class="text-foreground-muted">Última actualización</dt>
                <dd class="text-foreground text-right">{fmt(warehouse.updatedAt)}</dd>
              </div>
            </dl>
          </Card>
        </div>
      {/if}
    </div>
  {/if}
</div>
