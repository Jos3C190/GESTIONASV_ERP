<script lang="ts">
  import PortfolioPage from '#lib/features/sales-receivables/PortfolioPage.svelte';
  import { permissions } from '#lib/stores/permissions.svelte.ts';

  const canRead = $derived(permissions.hasPermission('sales_receivables:read'));
</script>

<svelte:head>
  <title>Cuentas por cobrar | GestionaSV</title>
</svelte:head>

{#if !canRead}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para consultar las cuentas por cobrar.
  </div>
{:else}
  <div class="space-y-5">
    <header>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Ventas</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">
        Cuentas por cobrar
      </h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        Lo que deben los clientes por sus facturas, créditos fiscales y notas de débito, con la
        antigüedad de los saldos y los saldos a favor. Los cobros se registran con recibos.
      </p>
    </header>
    <PortfolioPage />
  </div>
{/if}
