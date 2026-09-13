<script lang="ts">
  import { page } from '$app/state';
  import PurchaseQuotationDetail from '$lib/features/purchase-quotations/components/PurchaseQuotationDetail.svelte';

  let quotationId = $derived(page.params.id ?? '');
</script>

<svelte:head>
  <title>Detalle de cotización | GestionaSV</title>
</svelte:head>

<PurchaseQuotationDetail id={quotationId} />
