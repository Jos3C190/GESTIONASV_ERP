<script lang="ts">
  import ContingencyPanel from '#lib/features/sales/components/ContingencyPanel.svelte';
  import { permissions } from '#lib/stores/permissions.svelte.ts';

  const canRead = $derived(permissions.hasPermission('sales_invoices:read'));
  const canOperate = $derived(permissions.hasPermission('sales_invoices:contingency'));
</script>

<svelte:head>
  <title>Contingencia | GestionaSV</title>
</svelte:head>

{#if !canRead}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para consultar la contingencia de facturación.
  </div>
{:else}
  <div class="space-y-5">
    <header>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Ventas</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">
        Contingencia
      </h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        Facturación sin conexión con Hacienda por establecimiento: qué tiendas están en
        contingencia, qué falta informar y los plazos de 24 horas para el evento y de 72 horas para
        transmitir los documentos.
      </p>
    </header>
    <ContingencyPanel {canOperate} />
  </div>
{/if}
