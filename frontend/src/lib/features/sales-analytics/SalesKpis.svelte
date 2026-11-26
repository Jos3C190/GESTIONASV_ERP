<script lang="ts">
  import { salesAnalyticsApi } from '#lib/api/sales-analytics.ts';
  import {
    formatMoney,
    formatPercent,
    localDay,
    monthStart
  } from '#lib/features/sales-analytics/format.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type { SalesAnalysis } from '#lib/types/sales-analytics.ts';

  /** Ventas del mes en el Dashboard: solo para quien puede ver las cifras de venta. */
  const canSee = $derived(permissions.hasPermission('sales_analytics:read'));

  let analysis = $state<SalesAnalysis | null>(null);
  let failed = $state(false);
  let generation = 0;

  $effect(() => {
    if (!canSee) return;
    const scope = branch.id ?? null;
    const current = ++generation;
    const today = localDay();
    failed = false;
    salesAnalyticsApi
      .analysis(monthStart(today), today, scope)
      .then((result) => {
        if (current === generation) analysis = result;
      })
      .catch(() => {
        if (current === generation) failed = true;
      });
  });

  const goal = $derived.by(() => {
    const rows = (analysis?.by_branch ?? []).filter((row) => row.goal);
    if (!rows.length) return null;
    const target = rows.reduce((sum, row) => sum + Number(row.goal), 0);
    const sold = rows.reduce((sum, row) => sum + Number(row.net_sales), 0);
    return target > 0 ? ((sold / target) * 100).toFixed(2) : null;
  });
</script>

{#if canSee && !failed}
  <section class="mb-6" aria-label="Ventas del mes">
    <div class="mb-2 flex items-center justify-between">
      <h2 class="text-sm font-semibold text-foreground">Ventas del mes · sin IVA</h2>
      <a class="text-sm text-primary hover:underline" href="/sales/analytics">Ver análisis</a>
    </div>
    {#if !analysis}
      <div class="grid grid-cols-2 gap-4 lg:grid-cols-4" aria-hidden="true">
        {#each [1, 2, 3, 4] as item (item)}
          <div class="skeleton h-20 rounded-xl"></div>
        {/each}
      </div>
    {:else}
      <dl class="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {#each [['Venta', formatMoney(analysis.totals.net_sales)], ['Documentos', String(analysis.totals.documents)], ['Tiquete promedio', analysis.totals.average_ticket ? formatMoney(analysis.totals.average_ticket) : '—'], ['Avance de metas', goal === null ? 'Sin metas' : formatPercent(goal)]] as [label, value] (label)}
          <a
            class="rounded-xl border border-border bg-surface-elevated p-4 hover:border-primary/40"
            href="/sales/analytics"
          >
            <dt class="text-xs text-foreground-muted">{label}</dt>
            <dd class="mt-1 text-lg font-semibold tabular-nums text-foreground">{value}</dd>
          </a>
        {/each}
      </dl>
    {/if}
  </section>
{/if}
