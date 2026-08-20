<script lang="ts">
  /** Detalle de sucursal — hero persistente + tabs de detalle (Vercel/Geist + HIG Apple). */

  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { getBranch } from '$lib/services/branches';
  import { STATUS_MAP, type Branch } from '$lib/features/branches/types';
  import ImageGallery from '$lib/features/branches/components/ImageGallery.svelte';
  import BranchMiniMap from '$lib/features/branches/components/BranchMiniMap.svelte';
  import Avatar from '$lib/components/ui/Avatar.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Tabs from '$lib/components/ui/Tabs.svelte';

  let branch = $state<Branch | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let branchId = $derived(page.params.id);

  async function loadData() {
    if (!branchId) return;
    loading = true;
    error = null;
    try {
      branch = await getBranch(branchId);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Error al cargar la sucursal.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (branchId) loadData();
  });

  let salesGrowth = $derived(
    branch && branch.salesLastMonth > 0
      ? ((branch.salesThisMonth - branch.salesLastMonth) / branch.salesLastMonth) * 100
      : 0
  );

  let fullStars = $derived(branch ? Math.floor(branch.customerRating) : 0);
  let hasHalfStar = $derived(branch ? branch.customerRating % 1 >= 0.5 : false);

  // === Tab state (con hash sync) ===
  const TABS = [
    { id: 'infraestructura', label: 'Infraestructura', icon: 'building' },
    { id: 'ubicacion', label: 'Ubicación y contacto', icon: 'map' },
    { id: 'galeria', label: 'Galería', icon: 'gallery' },
    { id: 'descripcion', label: 'Descripción', icon: 'description' }
  ];
  let activeTab = $state('infraestructura');

  // === Helpers ===
  function fmt(value: string | number | null | undefined, suffix = ''): string {
    if (value === null || value === undefined || value === '' || value === 0) return '—';
    return typeof value === 'number' ? value.toLocaleString() + suffix : value;
  }
  function fmtMoney(value: number): string {
    if (!value) return '—';
    return `$${value.toLocaleString()}`;
  }
</script>

<svelte:head
  ><title>{branch ? `${branch.name} — Sucursales` : 'Sucursal — GestionaSV'}</title></svelte:head
>

<div class="p-6 md:p-8">
  <!-- Header con back (siempre visible) -->
  <div class="mb-6 flex items-center gap-3">
    <a
      href="/branches"
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
      <h1 class="text-xl font-bold text-foreground">Detalle de la sucursal</h1>
      <p class="text-sm text-foreground-muted">Información completa de la sucursal.</p>
    </div>
    {#if branch}
      <div class="flex items-center gap-2">
        <Button variant="secondary" size="sm" onclick={() => goto(`/branches/${branchId}/edit`)}>
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
          Editar
        </Button>
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
        <p class="text-xs text-foreground-subtle">Cargando sucursal...</p>
      </div>
    </div>
  {:else if error}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {:else if branch}
    <!-- ========================================== -->
    <!-- HERO PERSISTENTE (siempre visible)         -->
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
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle
                cx="12"
                cy="10"
                r="3"
              />
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex flex-wrap items-center gap-3">
              <h2 class="text-lg font-bold text-foreground">{branch.name}</h2>
              <Badge variant={STATUS_MAP[branch.status]?.variant || 'neutral'}>
                {STATUS_MAP[branch.status]?.label || branch.status}
              </Badge>
            </div>
            <div
              class="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-foreground-muted"
            >
              <span class="font-mono text-xs">{branch.code}</span>
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
                {branch.city}
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
                  ><circle cx="12" cy="12" r="10" /><path
                    d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
                  /></svg
                >
                Zona {branch.zone}
              </span>
            </div>
            {#if branch.customerRating > 0}
              <div class="mt-2 flex items-center gap-2">
                <div class="flex items-center gap-0.5">
                  {#each Array(fullStars) as _}
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="#F59E0B"
                      aria-hidden="true"
                      ><polygon
                        points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
                      /></svg
                    >
                  {/each}
                  {#if hasHalfStar}
                    <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true"
                      ><defs
                        ><linearGradient id="half-star"
                          ><stop offset="50%" stop-color="#F59E0B" /><stop
                            offset="50%"
                            stop-color="transparent"
                          /></linearGradient
                        ></defs
                      ><polygon
                        points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
                        fill="url(#half-star)"
                        stroke="#F59E0B"
                        stroke-width="1"
                      /></svg
                    >
                  {/if}
                  {#each Array(5 - fullStars - (hasHalfStar ? 1 : 0)) as _}
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="rgb(var(--border-strong))"
                      stroke-width="1.5"
                      aria-hidden="true"
                      ><polygon
                        points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
                      /></svg
                    >
                  {/each}
                </div>
                <span class="font-mono text-xs font-bold text-foreground"
                  >{branch.customerRating.toFixed(1)}</span
                >
                <span class="text-xs text-foreground-subtle"
                  >· {branch.monthlyVisitors.toLocaleString()} visitas/mes</span
                >
              </div>
            {/if}
          </div>
          <div class="hidden sm:flex flex-col gap-2 flex-none">
            <div class="text-right">
              <p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
                Ventas del mes
              </p>
              <p class="font-mono text-lg font-bold tabular-nums text-foreground">
                ${branch.salesThisMonth.toLocaleString()}
              </p>
              {#if salesGrowth !== 0}
                <p
                  class="text-[10px] font-semibold {salesGrowth > 0
                    ? 'text-success'
                    : 'text-danger'}"
                >
                  {salesGrowth > 0 ? '↑' : '↓'}
                  {Math.abs(salesGrowth).toFixed(1)}% vs mes anterior
                </p>
              {/if}
            </div>
          </div>
        </div>
      </Card>

      <!-- Métricas clave + Encargado + Infraestructura básica (grid horizontal siempre visible) -->
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
          <div class="flex items-center gap-2.5 mb-3">
            <Avatar initials={branch.managerInitials} size={36} />
            <div class="min-w-0 flex-1">
              <p class="text-sm font-semibold text-foreground truncate">{branch.manager}</p>
              <p class="text-[11px] text-foreground-subtle">Encargado de sucursal</p>
            </div>
          </div>
          <div class="space-y-1 text-[11.5px]">
            <div class="flex items-center gap-1.5 text-foreground-muted">
              <svg
                width="11"
                height="11"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="text-foreground-subtle flex-none"
                ><path
                  d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"
                /></svg
              >
              <span class="font-mono truncate">{branch.phone}</span>
            </div>
            <div class="flex items-center gap-1.5 text-foreground-muted">
              <svg
                width="11"
                height="11"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="text-foreground-subtle flex-none"
                ><rect x="2" y="4" width="20" height="16" rx="2" /><path
                  d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"
                /></svg
              >
              <span class="truncate">{branch.email}</span>
            </div>
          </div>
        </Card>

        <!-- Métricas rápidas -->
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
            KPIs operativos
          </p>
          <div class="grid grid-cols-2 gap-2">
            <div class="rounded-md border border-border bg-surface-muted/40 px-2.5 py-2">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Empleados
              </p>
              <p class="font-mono text-base font-bold tabular-nums text-foreground">
                {branch.employees}
              </p>
            </div>
            <div class="rounded-md border border-border bg-surface-muted/40 px-2.5 py-2">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Almacenes
              </p>
              <p class="font-mono text-base font-bold tabular-nums text-foreground">
                {branch.warehouses}
              </p>
            </div>
            <div class="rounded-md border border-border bg-surface-muted/40 px-2.5 py-2">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Ticket
              </p>
              <p class="font-mono text-base font-bold tabular-nums text-foreground">
                ${branch.avgTicket.toFixed(2)}
              </p>
            </div>
            <div class="rounded-md border border-border bg-surface-muted/40 px-2.5 py-2">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                YTD
              </p>
              <p class="font-mono text-base font-bold tabular-nums text-foreground">
                ${(branch.salesYTD / 1000).toFixed(0)}k
              </p>
            </div>
          </div>
        </Card>

        <!-- Infraestructura básica (versión compacta) -->
        <Card class="p-5 lg:col-span-2">
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
              stroke-linejoin="round"><path d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4" /></svg
            >
            Infraestructura
          </p>
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div class="rounded-md border border-border bg-surface-muted/40 px-2.5 py-2">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Terreno
              </p>
              <p class="font-mono text-sm font-bold tabular-nums text-foreground">
                {branch.area}<span class="text-[10px] font-normal text-foreground-muted"> m²</span>
              </p>
            </div>
            <div class="rounded-md border border-border bg-surface-muted/40 px-2.5 py-2">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Construido
              </p>
              <p class="font-mono text-sm font-bold tabular-nums text-foreground">
                {branch.areaBuilt}<span class="text-[10px] font-normal text-foreground-muted">
                  m²</span
                >
              </p>
            </div>
            <div class="rounded-md border border-border bg-surface-muted/40 px-2.5 py-2">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Niveles
              </p>
              <p class="font-mono text-sm font-bold tabular-nums text-foreground">
                {branch.floors}
              </p>
            </div>
            <div class="rounded-md border border-border bg-surface-muted/40 px-2.5 py-2">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Estac.
              </p>
              <p class="font-mono text-sm font-bold tabular-nums text-foreground">
                {branch.parking}<span class="text-[10px] font-normal text-foreground-muted">
                  esp.</span
                >
              </p>
            </div>
            <div class="rounded-md border border-border bg-surface-muted/40 px-2.5 py-2">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Aforo
              </p>
              <p class="font-mono text-sm font-bold tabular-nums text-foreground">
                {branch.capacity}
              </p>
            </div>
            <div class="rounded-md border border-border bg-surface-muted/40 px-2.5 py-2">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Antigüedad
              </p>
              <p class="font-mono text-sm font-bold tabular-nums text-foreground">
                {branch.buildingAge}<span class="text-[10px] font-normal text-foreground-muted">
                  a</span
                >
              </p>
            </div>
            <div class="rounded-md border border-border bg-surface-muted/40 px-2.5 py-2">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Tipo
              </p>
              <p class="text-xs font-bold capitalize text-foreground">{branch.propertyType}</p>
            </div>
            <div class="rounded-md border border-warning/20 bg-warning/5 px-2.5 py-2">
              <p class="text-[9px] font-bold uppercase tracking-wider text-foreground-subtle">
                Sin edificar
              </p>
              <p class="font-mono text-sm font-bold tabular-nums text-foreground">
                {branch.areaUnbuilt}<span class="text-[10px] font-normal text-foreground-muted">
                  m²</span
                >
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>

    <!-- ========================================== -->
    <!-- TABS STICKY CON DETALLES                   -->
    <!-- ========================================== -->
    <Tabs items={TABS} bind:active={activeTab} sticky={true} />

    <div class="mt-5">
      <!-- TAB: Infraestructura -->
      {#if activeTab === 'infraestructura'}
        <div
          id="tab-panel-infraestructura"
          role="tabpanel"
          aria-labelledby="tab-infraestructura"
          class="space-y-5"
        >
          <!-- Infraestructura física detallada -->
          <Card class="p-6">
            <h3 class="mb-5 text-sm font-semibold text-foreground flex items-center gap-2">
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
                ><path d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4" /><path
                  d="M9 9v.01M9 12v.01M9 15v.01M9 18v.01"
                /></svg
              >
              Infraestructura física detallada
            </h3>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-x-8 gap-y-5">
              <!-- SUB-GRUPO 1: Construcción y conservación -->
              <div>
                <p
                  class="mb-3 text-[10px] font-bold uppercase tracking-wider text-foreground-subtle flex items-center gap-1.5"
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
                    class="text-foreground-subtle"
                    ><path d="M2 22h20M4 22V8l8-6 8 6v14M9 22V12h6v10" /></svg
                  >
                  Construcción y conservación
                </p>
                <dl class="space-y-2.5 text-[12.5px]">
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Tipo de construcción</dt>
                    <dd class="text-foreground text-right capitalize font-medium">
                      {fmt(branch.constructionType)}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Año de construcción</dt>
                    <dd class="font-mono text-foreground text-right">
                      {fmt(branch.constructionYear)}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Estado de conservación</dt>
                    {#if branch.condition === 'excelente'}
                      <dd class="text-success text-right font-semibold">Excelente</dd>
                    {:else if branch.condition === 'bueno'}
                      <dd class="text-primary text-right font-semibold">Bueno</dd>
                    {:else if branch.condition === 'regular'}
                      <dd class="text-warning text-right font-semibold">Regular</dd>
                    {:else if branch.condition === 'malo'}
                      <dd class="text-danger text-right font-semibold">Malo</dd>
                    {:else}
                      <dd class="text-foreground-muted text-right">—</dd>
                    {/if}
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Última renovación</dt>
                    <dd class="text-foreground text-right">{fmt(branch.lastRenovation)}</dd>
                  </div>
                  <div
                    class="flex items-center justify-between gap-2 pt-2 border-t border-border/40"
                  >
                    <dt class="text-foreground-muted">Material de fachada</dt>
                    <dd class="text-foreground text-right capitalize font-medium">
                      {fmt(branch.exteriorMaterial)}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Material de piso</dt>
                    <dd class="text-foreground text-right capitalize font-medium">
                      {fmt(branch.floorMaterial)}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Cap. de techo</dt>
                    <dd class="font-mono text-foreground text-right">
                      {fmt(branch.roofCapacityKgM2, ' kg/m²')}
                    </dd>
                  </div>
                </dl>
              </div>

              <!-- SUB-GRUPO 2: Servicios básicos -->
              <div>
                <p
                  class="mb-3 text-[10px] font-bold uppercase tracking-wider text-foreground-subtle flex items-center gap-1.5"
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
                    class="text-foreground-subtle"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" /></svg
                  >
                  Servicios básicos
                </p>
                <dl class="space-y-2.5 text-[12.5px]">
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Cap. eléctrica</dt>
                    <dd class="font-mono text-foreground text-right">
                      {fmt(branch.electricalCapacityKVA, ' kVA')}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Proveedor de internet</dt>
                    <dd class="text-foreground text-right font-medium">
                      {fmt(branch.internetProvider)}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Tipo de conexión</dt>
                    <dd class="text-foreground text-right capitalize font-medium">
                      {fmt(branch.internetType)}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Abastecimiento de agua</dt>
                    <dd class="text-foreground text-right capitalize font-medium">
                      {fmt(branch.waterSource.replace('_', ' '))}
                    </dd>
                  </div>
                  <div
                    class="flex items-center justify-between gap-2 pt-2 border-t border-border/40"
                  >
                    <dt class="text-foreground-muted">Climatización</dt>
                    <dd class="text-foreground text-right capitalize font-medium">
                      {fmt(branch.acSystem.replace('_', ' '))}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Tipo de iluminación</dt>
                    <dd class="text-foreground text-right capitalize font-medium">
                      {fmt(branch.lighting)}
                    </dd>
                  </div>
                </dl>
              </div>

              <!-- SUB-GRUPO 3: Seguridad y vigilancia -->
              <div>
                <p
                  class="mb-3 text-[10px] font-bold uppercase tracking-wider text-foreground-subtle flex items-center gap-1.5"
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
                    class="text-foreground-subtle"
                    ><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg
                  >
                  Seguridad y vigilancia
                </p>
                <dl class="space-y-2.5 text-[12.5px]">
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Cámaras CCTV</dt>
                    <dd class="font-mono text-foreground text-right">{fmt(branch.cctvCameras)}</dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Control de acceso</dt>
                    <dd class="text-foreground text-right capitalize font-medium">
                      {fmt(branch.accessControl)}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Sistema de alarma</dt>
                    <dd class="text-foreground text-right">
                      {#if branch.hasAlarm}
                        <span
                          class="inline-flex items-center gap-1 rounded-md bg-success/10 px-1.5 py-0.5 text-[10.5px] font-semibold text-success"
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
                          Activa
                        </span>
                      {:else}
                        <span
                          class="inline-flex items-center gap-1 rounded-md bg-surface-muted px-1.5 py-0.5 text-[10.5px] font-medium text-foreground-muted"
                          >— No</span
                        >
                      {/if}
                    </dd>
                  </div>
                  <div class="flex items-start justify-between gap-2">
                    <dt class="text-foreground-muted flex-none">Sistema contra incendio</dt>
                    <dd class="text-right">
                      {#if branch.fireSystem.length > 0}
                        <div class="flex flex-wrap gap-1 justify-end">
                          {#each branch.fireSystem as f (f)}
                            <span
                              class="inline-flex items-center gap-1 rounded-md bg-primary/5 px-1.5 py-0.5 text-[10.5px] font-medium text-primary"
                            >
                              <svg
                                width="9"
                                height="9"
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
                        </div>
                      {:else}
                        <span class="text-foreground-subtle">—</span>
                      {/if}
                    </dd>
                  </div>
                  <div
                    class="flex items-center justify-between gap-2 pt-2 border-t border-border/40"
                  >
                    <dt class="text-foreground-muted">Planta eléctrica de emergencia</dt>
                    <dd class="text-foreground text-right">
                      {#if branch.hasBackupGenerator}
                        <span
                          class="inline-flex items-center gap-1 rounded-md bg-success/10 px-1.5 py-0.5 text-[10.5px] font-semibold text-success"
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
                          Sí
                        </span>
                      {:else}
                        <span
                          class="inline-flex items-center gap-1 rounded-md bg-surface-muted px-1.5 py-0.5 text-[10.5px] font-medium text-foreground-muted"
                          >— No</span
                        >
                      {/if}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Sistema UPS</dt>
                    <dd class="text-foreground text-right">
                      {#if branch.hasUPS}
                        <span
                          class="inline-flex items-center gap-1 rounded-md bg-success/10 px-1.5 py-0.5 text-[10.5px] font-semibold text-success"
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
                          Sí
                        </span>
                      {:else}
                        <span
                          class="inline-flex items-center gap-1 rounded-md bg-surface-muted px-1.5 py-0.5 text-[10.5px] font-medium text-foreground-muted"
                          >— No</span
                        >
                      {/if}
                    </dd>
                  </div>
                </dl>
              </div>

              <!-- SUB-GRUPO 4: Información legal y administrativa -->
              <div>
                <p
                  class="mb-3 text-[10px] font-bold uppercase tracking-wider text-foreground-subtle flex items-center gap-1.5"
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
                    class="text-foreground-subtle"
                    ><path
                      d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                    /><polyline points="14 2 14 8 20 8" /><line
                      x1="9"
                      y1="13"
                      x2="15"
                      y2="13"
                    /><line x1="9" y1="17" x2="15" y2="17" /></svg
                  >
                  Información legal y administrativa
                </p>
                <dl class="space-y-2.5 text-[12.5px]">
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Valor catastral</dt>
                    <dd class="font-mono text-foreground text-right font-semibold">
                      {fmtMoney(branch.appraisedValue)}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Mantenimiento mensual</dt>
                    <dd class="font-mono text-foreground text-right">
                      {fmtMoney(branch.monthlyMaintenance)}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Código catastral</dt>
                    <dd class="font-mono text-foreground text-right text-[11.5px]">
                      {fmt(branch.cadastralCode)}
                    </dd>
                  </div>
                  <div class="flex items-center justify-between gap-2">
                    <dt class="text-foreground-muted">Venc. permiso municipal</dt>
                    <dd class="text-foreground text-right">{fmt(branch.permitExpiry)}</dd>
                  </div>
                  <div
                    class="flex items-center justify-between gap-2 pt-2 border-t border-border/40"
                  >
                    <dt class="text-foreground-muted">Proveedor de limpieza</dt>
                    <dd class="text-foreground text-right font-medium">
                      {fmt(branch.cleaningProvider)}
                    </dd>
                  </div>
                  {#if branch.leaseExpiry}
                    <div class="flex items-center justify-between gap-2">
                      <dt class="text-foreground-muted">Venc. contrato</dt>
                      <dd class="font-mono text-warning text-right font-semibold">
                        {fmt(branch.leaseExpiry)}
                      </dd>
                    </div>
                    <div class="flex items-center justify-between gap-2">
                      <dt class="text-foreground-muted">Propietario</dt>
                      <dd class="text-foreground text-right text-[11px]">{fmt(branch.landlord)}</dd>
                    </div>
                  {:else}
                    <div class="flex items-center justify-between gap-2">
                      <dt class="text-foreground-muted">Régimen</dt>
                      <dd
                        class="inline-flex items-center gap-1 rounded-md bg-primary/5 px-2 py-0.5 text-[10.5px] font-semibold text-primary"
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
                        Inmueble propio
                      </dd>
                    </div>
                  {/if}
                </dl>
              </div>
            </div>

            {#if branch.accessibility.length > 0}
              <div class="mt-5 pt-4 border-t border-border/60">
                <p
                  class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-2 flex items-center gap-1.5"
                >
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
                    ><circle cx="12" cy="4" r="2" /><path
                      d="M19 13v-2c0-1.1-.9-2-2-2H7c-1.1 0-2 .9-2 2v2"
                    /><circle cx="12" cy="17" r="5" /></svg
                  >
                  Accesibilidad
                </p>
                <div class="flex flex-wrap gap-1.5">
                  {#each branch.accessibility as a (a)}
                    <span
                      class="inline-flex items-center gap-1 rounded-md border border-primary/20 bg-primary/5 px-2.5 py-1 text-[11.5px] font-medium text-primary"
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
                      {a}
                    </span>
                  {/each}
                </div>
              </div>
            {/if}
          </Card>

          <!-- Capacidad de almacenamiento -->
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
                  d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"
                /><path d="m3.3 7 8.7 5 8.7-5" /><path d="M12 22V12" /></svg
              >
              Capacidad de almacenamiento
            </h3>

            {#if branch.warehousesDetail.length > 0}
              <p class="mb-4 text-xs text-foreground-muted">
                Los límites se presentan por almacén. La ocupación permanece desconocida hasta
                medir el peso y volumen de las existencias y reservas.
              </p>

              <div class="overflow-x-auto rounded-lg border border-border">
                <table class="w-full text-xs">
                  <thead class="bg-surface-muted/50 border-b border-border">
                    <tr>
                      <th class="px-3 py-2 text-left font-semibold text-foreground">Almacén</th>
                      <th class="px-3 py-2 text-right font-semibold text-foreground">Peso operativo</th>
                      <th class="px-3 py-2 text-right font-semibold text-foreground">Peso certificado</th>
                      <th class="px-3 py-2 text-right font-semibold text-foreground">Volumen operativo</th>
                      <th class="px-3 py-2 text-right font-semibold text-foreground">Volumen certificado</th>
                      <th class="px-3 py-2 text-center font-semibold text-foreground">Ocupación</th>
                      <th class="px-3 py-2 text-center font-semibold text-foreground">Estado</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-border">
                    {#each branch.warehousesDetail as w (w.code)}
                      <tr class="hover:bg-surface-muted/30">
                        <td class="px-3 py-2">
                          <p class="font-medium text-foreground">{w.name}</p>
                          <p class="font-mono text-[10px] text-foreground-subtle">
                            {w.code} · {w.location}
                          </p>
                        </td>
                        <td class="px-3 py-2 text-right font-mono tabular-nums text-foreground"
                          >{w.operationalMaxWeightKg == null ? '—' : `${w.operationalMaxWeightKg.toLocaleString('es-SV')} kg`}</td
                        >
                        <td class="px-3 py-2 text-right font-mono tabular-nums text-foreground"
                          >{w.certifiedMaxWeightKg == null ? '—' : `${w.certifiedMaxWeightKg.toLocaleString('es-SV')} kg`}</td
                        >
                        <td class="px-3 py-2 text-right font-mono tabular-nums text-foreground"
                          >{w.operationalUsableVolumeM3 == null ? '—' : `${w.operationalUsableVolumeM3.toLocaleString('es-SV')} m³`}</td
                        >
                        <td class="px-3 py-2 text-right font-mono tabular-nums text-foreground"
                          >{w.certifiedUsableVolumeM3 == null ? '—' : `${w.certifiedUsableVolumeM3.toLocaleString('es-SV')} m³`}</td
                        >
                        <td class="px-3 py-2 text-center text-foreground-muted">
                          Desconocida
                        </td>
                        <td class="px-3 py-2 text-center">
                          {#if w.status === 'active'}
                            <span
                              class="inline-flex items-center gap-1 rounded-md bg-success/10 px-1.5 py-0.5 text-[10px] font-medium text-success"
                              ><span class="h-1.5 w-1.5 rounded-full bg-success"></span> Activo</span
                            >
                          {:else if w.status === 'inactive'}
                            <span
                              class="inline-flex items-center gap-1 rounded-md bg-surface-muted px-1.5 py-0.5 text-[10px] font-medium text-foreground-muted"
                              ><span class="h-1.5 w-1.5 rounded-full bg-foreground-subtle"></span> Inactivo</span
                            >
                          {:else}
                            <span
                              class="inline-flex items-center gap-1 rounded-md bg-warning/10 px-1.5 py-0.5 text-[10px] font-medium text-warning"
                              ><span class="h-1.5 w-1.5 rounded-full bg-warning"></span> Mant.</span
                            >
                          {/if}
                        </td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {:else}
              <div
                class="flex h-20 items-center justify-center rounded-lg bg-surface-muted/20 text-xs text-foreground-subtle"
              >
                Sin almacenes asignados a esta sucursal
              </div>
            {/if}
          </Card>
        </div>

        <!-- TAB: Ubicación y contacto -->
      {:else if activeTab === 'ubicacion'}
        <div
          id="tab-panel-ubicacion"
          role="tabpanel"
          aria-labelledby="tab-ubicacion"
          class="grid grid-cols-1 lg:grid-cols-5 gap-5"
        >
          <!-- Mapa (3 cols) -->
          <Card class="lg:col-span-3 p-6 flex flex-col">
            <h3
              class="mb-4 text-sm font-semibold text-foreground flex items-center gap-2 flex-none"
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
                class="text-foreground-subtle"
                ><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle
                  cx="12"
                  cy="10"
                  r="3"
                /></svg
              >
              Ubicación
            </h3>
            <BranchMiniMap {branch} fillHeight={true} />
          </Card>

          <!-- Contacto (2 cols) -->
          <div class="lg:col-span-2 space-y-5">
            <Card class="p-6">
              <h3 class="mb-4 text-sm font-semibold text-foreground">Contacto</h3>
              <dl class="space-y-3 text-sm">
                <div>
                  <dt
                    class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-0.5 flex items-center gap-1.5"
                  >
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
                    Dirección
                  </dt>
                  <dd class="text-foreground text-[12.5px]">{branch.address}</dd>
                  <dd class="text-foreground-muted text-xs">{branch.city}</dd>
                </div>
                <div class="pt-2 border-t border-border/60">
                  <dt
                    class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-0.5 flex items-center gap-1.5"
                  >
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
                      ><rect x="3" y="4" width="18" height="18" rx="2" /><line
                        x1="16"
                        y1="2"
                        x2="16"
                        y2="6"
                      /><line x1="8" y1="2" x2="8" y2="6" /><line
                        x1="3"
                        y1="10"
                        x2="21"
                        y2="10"
                      /></svg
                    >
                    Inaugurada
                  </dt>
                  <dd class="text-foreground text-[12.5px]">{branch.openedAt}</dd>
                </div>
                <div class="pt-2 border-t border-border/60">
                  <dt
                    class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-0.5 flex items-center gap-1.5"
                  >
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
                      ><circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" /><path
                        d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
                      /></svg
                    >
                    Coordenadas
                  </dt>
                  <dd class="font-mono text-foreground text-[12.5px]">
                    {branch.lat.toFixed(4)}, {branch.lng.toFixed(4)}
                  </dd>
                </div>
                {#if branch.website}
                  <div class="pt-2 border-t border-border/60">
                    <dt
                      class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle mb-0.5 flex items-center gap-1.5"
                    >
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
                        ><circle cx="12" cy="12" r="10" /><path
                          d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
                        /></svg
                      >
                      Web
                    </dt>
                    <dd class="font-mono text-primary text-xs truncate">{branch.website}</dd>
                  </div>
                {/if}
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
                  ><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg
                >
                Horario de atención
              </h3>
              <dl class="space-y-1.5 text-sm">
                {#each branch.scheduleDetail as d (d.day)}
                  <div class="flex items-center justify-between gap-2 py-1">
                    <dt class="text-foreground-muted text-[12.5px]">{d.day}</dt>
                    <dd class="font-mono text-[12px] text-foreground">
                      {#if d.open && d.close}
                        {d.open}–{d.close}
                      {:else}
                        <span class="text-foreground-subtle">Cerrado</span>
                      {/if}
                    </dd>
                  </div>
                {/each}
              </dl>
            </Card>
          </div>
        </div>

        <!-- TAB: Galería -->
      {:else if activeTab === 'galeria'}
        <div id="tab-panel-galeria" role="tabpanel" aria-labelledby="tab-galeria">
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
                ><rect x="3" y="3" width="18" height="18" rx="2" /><circle
                  cx="8.5"
                  cy="8.5"
                  r="1.5"
                /><path d="m21 15-5-5L5 21" /></svg
              >
              Galería
            </h3>
            <ImageGallery images={branch.images} />
          </Card>
        </div>

        <!-- TAB: Descripción -->
      {:else if activeTab === 'descripcion'}
        <div id="tab-panel-descripcion" role="tabpanel" aria-labelledby="tab-descripcion">
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
                ><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline
                  points="14 2 14 8 20 8"
                /><line x1="9" y1="13" x2="15" y2="13" /><line
                  x1="9"
                  y1="17"
                  x2="15"
                  y2="17"
                /></svg
              >
              Descripción
            </h3>
            <p class="text-sm leading-relaxed text-foreground-muted">{branch.description}</p>
            <div class="mt-6 pt-5 border-t border-border/60 grid grid-cols-1 sm:grid-cols-3 gap-5">
              <div>
                <p
                  class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle flex items-center gap-1.5"
                >
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
                    ><path d="M9 11l3 3L22 4" /><path
                      d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"
                    /></svg
                  >
                  Última inspección
                </p>
                <p class="mt-1 text-sm text-foreground">{branch.lastInspection}</p>
              </div>
              <div>
                <p
                  class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle flex items-center gap-1.5"
                >
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
                    ><path d="M21 12a9 9 0 1 1-6.219-8.56" /><polyline
                      points="21 4 21 10 15 10"
                    /></svg
                  >
                  Rotación inventario
                </p>
                <p class="mt-1 font-mono text-sm text-foreground">
                  {branch.inventoryTurnover > 0
                    ? `${branch.inventoryTurnover.toFixed(1)}x/año`
                    : '—'}
                </p>
              </div>
              <div>
                <p
                  class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle flex items-center gap-1.5"
                >
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
                    ><circle cx="12" cy="12" r="10" /><path
                      d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
                    /></svg
                  >
                  Inaugurada
                </p>
                <p class="mt-1 text-sm text-foreground">{branch.openedAt}</p>
              </div>
            </div>
          </Card>
        </div>
      {/if}
    </div>
  {/if}
</div>
