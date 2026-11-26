<script lang="ts">
  import { page } from '$app/state';
  import CustomerAccount from '#lib/features/sales-receivables/CustomerAccount.svelte';
  import { permissions } from '#lib/stores/permissions.svelte.ts';

  const customerId = $derived(page.params.customerId ?? '');
  const canRead = $derived(permissions.hasPermission('sales_receivables:read'));
  const canCollect = $derived(permissions.hasPermission('sales_receivables:collect'));
  const canControlCredit = $derived(permissions.hasPermission('sales_credit:authorize'));
</script>

<svelte:head>
  <title>Estado de cuenta | GestionaSV</title>
</svelte:head>

{#if !canRead}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para consultar las cuentas por cobrar.
  </div>
{:else}
  {#key customerId}
    <CustomerAccount {customerId} {canCollect} {canControlCredit} />
  {/key}
{/if}
