<script lang="ts">
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesAnalyticsApi } from '#lib/api/sales-analytics.ts';
  import AreaChart from '#lib/features/dashboard/components/AreaChart.svelte';
  import BucketTable from '#lib/features/sales-analytics/BucketTable.svelte';
  import GoalsEditor from '#lib/features/sales-analytics/GoalsEditor.svelte';
  import {
    formatMoney,
    formatPercent,
    localDay,
    monthStart
  } from '#lib/features/sales-analytics/format.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type { SalesAnalysis } from '#lib/types/sales-analytics.ts';

  const canSetGoals = $derived(permissions.hasPermission('sales_goals:manage'));
  const inputClass =
    'h-10 rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  const today = localDay();
  let from = $state(monthStart(today));
  let to = $state(today);
  let analysis = $state<SalesAnalysis | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let editingGoals = $state(false);
  let generation = 0;

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try {
      const result = await salesAnalyticsApi.analysis(from, to, branch.id ?? null);
      if (current === generation) analysis = result;
    } catch (cause) {
      if (current === generation) {
        analysis = null;
        error = cause instanceof HttpError ? cause.message : 'No se pudo cargar el análisis.';
      }
    } finally {
      if (current === generation) loading = false;
    }
  }

  $effect(() => {
    void branch.id;
    void load();
  });

  const series = $derived(
    // «AAAA-MM-DD» solo se lee como medianoche UTC (el día anterior en El Salvador): mediodía local.
    (analysis?.by_day ?? []).map((item) => ({
      date: `${item.key}T12:00:00`,
      value: Number(item.net_sales)
    }))
  );
  const peak = $derived(
    Math.max(1, ...(analysis?.by_hour ?? []).map((item) => Number(item.net_sales)))
  );
  const cards = $derived.by(() => {
    if (!analysis) return [];
    const totals = analysis.totals;
    const list = [
      {
        label: 'Venta sin IVA',
        value: formatMoney(totals.net_sales),
        hint: 'Facturas y créditos fiscales'
      },
      {
        label: 'Documentos',
        value: String(totals.documents),
        hint: 'Facturas y créditos fiscales vigentes'
      },
      {
        label: 'Tiquete promedio',
        value: totals.average_ticket ? formatMoney(totals.average_ticket) : '—',
        hint: 'Venta entre documentos'
      },
      {
        label: 'Devoluciones',
        value: formatPercent(totals.returns_percent),
        hint: `${formatMoney(totals.returns)} en notas y retornos`
      }
    ];
    if (analysis.costs_visible) {
      list.push({
        label: 'Margen bruto',
        value: formatPercent(totals.margin_percent),
        hint: `${formatMoney(totals.margin)} sobre costo de salida`
      });
    }
    return list;
  });
</script>

<div class="space-y-5">
  <form
    class="flex flex-wrap items-end gap-3"
    onsubmit={(event) => {
      event.preventDefault();
      void load();
    }}
  >
    <label class="space-y-1 text-sm text-foreground-muted"
      >Desde
      <input class={inputClass} type="date" max={to} bind:value={from} required />
    </label>
    <label class="space-y-1 text-sm text-foreground-muted"
      >Hasta
      <input class={inputClass} type="date" min={from} max={today} bind:value={to} required />
    </label>
    <Button type="submit" variant="secondary" disabled={loading}>Consultar</Button>
    {#if canSetGoals && !editingGoals}
      <Button variant="ghost" onclick={() => (editingGoals = true)}>Metas del mes</Button>
    {/if}
    <span class="text-xs text-foreground-muted">Alcance: {branch.label} · montos sin IVA</span>
  </form>

  {#if editingGoals}
    <GoalsEditor
      period={from.slice(0, 7)}
      branchId={branch.id ?? null}
      onSaved={() => {
        editingGoals = false;
        void load();
      }}
      onCancel={() => (editingGoals = false)}
    />
  {/if}

  {#if loading && !analysis}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-hidden="true">
      {#each [1, 2, 3, 4] as item (item)}
        <div class="skeleton h-24 rounded-xl"></div>
      {/each}
    </div>
    <div class="skeleton h-64 rounded-xl" aria-hidden="true"></div>
  {:else if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {:else if analysis}
    <dl class="grid gap-3 sm:grid-cols-2 {cards.length > 4 ? 'lg:grid-cols-5' : 'lg:grid-cols-4'}">
      {#each cards as card (card.label)}
        <div class="rounded-xl border border-border bg-surface p-4">
          <dt class="text-sm text-foreground-muted">{card.label}</dt>
          <dd class="mt-1 text-xl font-semibold tabular-nums text-foreground">{card.value}</dd>
          <dd class="mt-1 text-xs text-foreground-muted">{card.hint}</dd>
        </div>
      {/each}
    </dl>

    {#if analysis.totals.documents === 0}
      <div
        class="rounded-xl border border-border bg-surface p-8 text-center text-sm text-foreground-muted"
      >
        <p class="font-medium text-foreground">Sin ventas facturadas en el rango</p>
        <p class="mt-1">
          El análisis cuenta las facturas y los créditos fiscales vigentes del período.
        </p>
      </div>
    {:else}
      <section class="rounded-xl border border-border bg-surface p-4" aria-label="Venta por día">
        <h2 class="mb-3 text-sm font-semibold text-foreground">Venta sin IVA por día</h2>
        <AreaChart data={series} label="Venta sin IVA por día" height={200} />
      </section>

      <BucketTable
        title="Por sucursal"
        rows={analysis.by_branch}
        costs={analysis.costs_visible}
        goals
      />

      <div class="grid gap-4 lg:grid-cols-2">
        <BucketTable
          title="Por categoría"
          rows={analysis.by_category}
          costs={analysis.costs_visible}
        />
        <BucketTable
          title="Clientes principales"
          rows={analysis.top_customers}
          costs={analysis.costs_visible}
        />
        <BucketTable
          title="Productos más vendidos"
          rows={analysis.top_products}
          costs={analysis.costs_visible}
          quantity
        />
        <BucketTable
          title="Productos menos vendidos"
          rows={analysis.bottom_products}
          costs={analysis.costs_visible}
          quantity
          empty="Con diez productos o menos no hay lista de menos vendidos."
        />
      </div>

      <section class="rounded-xl border border-border bg-surface p-4" aria-label="Venta por hora">
        <h2 class="mb-3 text-sm font-semibold text-foreground">Venta por hora de emisión</h2>
        <ul class="space-y-1.5 text-sm">
          {#each analysis.by_hour as item (item.key)}
            <li class="flex items-center gap-3">
              <span class="w-12 tabular-nums text-foreground-muted">{item.label}</span>
              <div class="h-2 flex-1 rounded-full bg-surface-muted">
                <div
                  class="h-2 rounded-full bg-primary"
                  style="width: {(Number(item.net_sales) / peak) * 100}%"
                ></div>
              </div>
              <span class="w-28 text-right tabular-nums text-foreground"
                >{formatMoney(item.net_sales)}</span
              >
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</div>
