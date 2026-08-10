<script lang="ts">
  import { session } from '$lib/stores/session.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { api, type DashboardSummary } from '$lib/api/client';
  import { onMount } from 'svelte';
  import KpiCard from '$lib/features/dashboard/components/KpiCard.svelte';
  import AreaChart from '$lib/features/dashboard/components/AreaChart.svelte';
  import DonutChart from '$lib/features/dashboard/components/DonutChart.svelte';
  import ActivityFeed from '$lib/features/dashboard/components/ActivityFeed.svelte';
  import SummaryTable from '$lib/features/dashboard/components/SummaryTable.svelte';
  import ProgressRing from '$lib/features/dashboard/components/ProgressRing.svelte';
  import AvatarGroup from '$lib/components/ui/AvatarGroup.svelte';
  import Callout from '$lib/components/ui/Callout.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { queryClient } from '$lib/services/query-client';

  // MOCK_DATA = true — KPIs, serie temporal, distribución y tabla son simulados.
  // ActivityFeed es el único componente que consume datos reales (bitácora).
  let loading = $state(true);
  let summary = $state<DashboardSummary | null>(null);
  let summaryError = $state<string | null>(null);
  let range = $state<'7D' | '30D' | '90D'>('30D');

  let series = $derived.by(() => {
    const days = range === '7D' ? 7 : range === '90D' ? 90 : 30;
    return (summary?.activity_series ?? []).slice(-days);
  });

  let team = $derived(summary?.team ?? []);
  let recentUsers = $derived(
    (summary?.recent_users ?? []).map((user) => ({
      name: user.name,
      initials: user.initials,
      dept: user.department,
      status: user.status,
      createdAt: new Date(user.created_at).toLocaleDateString('es-SV', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
      })
    }))
  );

  let kpis = $derived([
    { label: 'Usuarios activos', value: summary?.active_users ?? 0, change: 0, sparkline: [summary?.active_users ?? 0, summary?.active_users ?? 0], icon: 'M17 20h5v-2a4 4 0 0 0-3-3.87M9 20H4v-2a4 4 0 0 1 3-3.87m6-2a4 4 0 1 0-8 0 4 4 0 0 0 8 0z' },
    { label: 'Empleados', value: summary?.employees ?? 0, change: 0, sparkline: [summary?.employees ?? 0, summary?.employees ?? 0], icon: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0zM12 14a7 7 0 0 0-7 7h14a7 7 0 0 0-7-7z' },
    { label: 'Almacenes activos', value: summary?.warehouses ?? 0, change: 0, sparkline: [summary?.warehouses ?? 0, summary?.warehouses ?? 0], icon: 'M3 21h18M5 21V8l7-5 7 5v13M8 12h8M8 16h8' },
    { label: 'Eventos hoy', value: summary?.events_today ?? 0, change: 0, sparkline: [summary?.events_today ?? 0, summary?.events_today ?? 0], icon: 'M13 2L3 14h7l-1 8 10-12h-7l1-8z' }
  ]);

  onMount(() => {
    const queryKey = ['dashboard', company.id ?? 'none', branch.id ?? 'all'] as const;
    void queryClient
      .fetchQuery({
        queryKey,
        staleTime: 15_000,
        queryFn: ({ signal }) => api.dashboard.summary(signal)
      })
      .then((data) => (summary = data))
      .catch((error) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          summaryError =
            error instanceof Error ? error.message : 'No se pudieron cargar las métricas.';
        }
      })
      .finally(() => (loading = false));
    return () => {
      void queryClient.cancelQueries({ queryKey, exact: true });
    };
  });
</script>

<svelte:head><title>Dashboard — GestionaSV</title></svelte:head>

<div class="p-6 md:p-8">
  <!-- Header -->
  <div class="mb-5">
    <h1 class="text-xl font-bold tracking-tight text-foreground">
      Hola, {session.user?.username ?? ''} 👋
    </h1>
    <p class="mt-1 text-sm text-foreground-muted">
      {new Date().toLocaleDateString('es-SV', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
      · {branch.label}
    </p>
  </div>

  {#if summaryError}
    <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">{summaryError}</div>
  {:else}
    <Callout variant="info">
      <span class="font-medium text-foreground">Contexto: {branch.label}.</span>
      <span class="text-foreground-muted"> Las métricas operativas y la actividad reciente respetan este alcance.</span>
    </Callout>
  {/if}

  <!-- KPIs -->
  <div class="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
    {#if loading}
      {#each Array(4) as _}
        <div class="h-28 rounded-xl border border-border skeleton"></div>
      {/each}
    {:else}
      {#each kpis as kpi (kpi.label)}
        <KpiCard {...kpi} />
      {/each}
    {/if}
  </div>

  <!-- Row 2: chart + donut -->
  <div class="mb-6 grid gap-4 lg:grid-cols-3">
    <div class="rounded-xl border border-border bg-surface-elevated p-5 lg:col-span-2">
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h2 class="text-sm font-semibold text-foreground">Actividad del sistema</h2>
          <p class="text-[11px] text-foreground-subtle">Eventos registrados por día</p>
        </div>
        <div class="flex items-center gap-1 rounded-lg border border-border bg-surface-muted p-0.5">
          {#each ['7D', '30D', '90D'] as r (r)}
            <button
              type="button"
              onclick={() => range = r as '7D' | '30D' | '90D'}
              class="rounded-md px-2.5 py-1 text-xs font-medium transition-colors {range === r ? 'bg-surface-elevated text-foreground shadow-soft' : 'text-foreground-subtle hover:text-foreground'}"
            >{r}</button>
          {/each}
        </div>
      </div>
      {#if loading}
        <div class="h-[200px] rounded-lg skeleton"></div>
      {:else}
        <AreaChart data={series} label="Actividad del sistema" height={200} />
      {/if}
    </div>

    <div class="rounded-xl border border-border bg-surface-elevated p-5">
      <h2 class="mb-4 text-sm font-semibold text-foreground">Empleados por departamento</h2>
      {#if loading}
        <div class="flex items-center gap-5">
          <div class="h-[140px] w-[140px] rounded-full skeleton"></div>
          <div class="flex-1 space-y-2">{#each Array(5) as _}<div class="h-3 rounded skeleton"></div>{/each}</div>
        </div>
      {:else}
        {#if (summary?.department_distribution.length ?? 0) > 0}
          <DonutChart data={summary?.department_distribution ?? []} size={140} />
        {:else}
          <div class="flex h-[140px] items-center justify-center text-center text-xs text-foreground-muted">Sin empleados con departamento en este contexto.</div>
        {/if}
      {/if}
    </div>
  </div>

  <!-- Row 3: activity (altura fija con scroll) + progress + team -->
  <div class="mb-6 grid gap-4 lg:grid-cols-3">
    <!-- Activity feed: altura fija con scroll interno + mask inferior -->
    <div class="rounded-xl border border-border bg-surface-elevated p-5 lg:col-span-2">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-sm font-semibold text-foreground">Actividad reciente</h2>
        <a href="/audit-log" class="text-[11px] font-medium text-primary hover:underline">Ver todo →</a>
      </div>
      <div class="max-h-[340px] overflow-y-auto" style="mask-image: linear-gradient(to bottom, black 85%, transparent 100%); -webkit-mask-image: linear-gradient(to bottom, black 85%, transparent 100%);">
        <ActivityFeed />
      </div>
    </div>

    <!-- Progress + team -->
    <div class="flex flex-col gap-4">
      <div class="rounded-xl border border-border bg-surface-elevated p-5">
        <h2 class="mb-3 text-sm font-semibold text-foreground">Onboarding</h2>
        {#if loading}
          <div class="mx-auto h-[120px] w-[120px] rounded-full skeleton"></div>
        {:else}
          <ProgressRing value={summary?.onboarding_progress ?? 0} label="Expedientes completos" size={120} />
        {/if}
      </div>
      <div class="rounded-xl border border-border bg-surface-elevated p-5">
        <h2 class="mb-3 text-sm font-semibold text-foreground">Equipo</h2>
        {#if team.length > 0}
          <AvatarGroup members={team} max={4} size={28} />
          <p class="mt-2 text-[11px] text-foreground-subtle">{team.length} empleados activos</p>
        {:else}
          <p class="text-xs text-foreground-muted">No hay empleados activos en este contexto.</p>
        {/if}
      </div>
    </div>
  </div>

  <!-- Row 4: summary table -->
  <div class="rounded-xl border border-border bg-surface-elevated p-5">
    <div class="mb-4 flex items-center justify-between">
      <h2 class="text-sm font-semibold text-foreground">Usuarios recientes</h2>
      <a href="/users" class="text-[11px] font-medium text-primary hover:underline">Ver todos →</a>
    </div>
    {#if loading}
      <div class="space-y-2">{#each Array(6) as _}<div class="h-10 rounded skeleton"></div>{/each}</div>
    {:else}
      {#if recentUsers.length > 0}
        <SummaryTable rows={recentUsers} />
      {:else}
        <div class="rounded-xl border border-dashed border-border p-8 text-center text-sm text-foreground-muted">No hay usuarios recientes en este contexto.</div>
      {/if}
    {/if}
  </div>
</div>
