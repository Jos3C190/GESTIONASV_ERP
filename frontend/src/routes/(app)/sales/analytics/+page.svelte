<script lang="ts">
  import AnalyticsPage from '#lib/features/sales-analytics/AnalyticsPage.svelte';
  import { permissions } from '#lib/stores/permissions.svelte.ts';

  const canRead = $derived(permissions.hasPermission('sales_analytics:read'));
</script>

<svelte:head>
  <title>Análisis comercial | GestionaSV</title>
</svelte:head>

{#if !canRead}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para ver las cifras de venta.
  </div>
{:else}
  <div class="space-y-5">
    <header>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Ventas</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">
        Análisis comercial
      </h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        Venta sin IVA de las facturas y los créditos fiscales vigentes, devoluciones, avance de las
        metas por sucursal y, si puedes ver costos, el margen bruto sobre el costo de salida.
      </p>
    </header>
    <AnalyticsPage />
  </div>
{/if}
