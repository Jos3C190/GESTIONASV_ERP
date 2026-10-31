<script lang="ts">
  import { page } from '$app/state';
  import PurchaseQuotationComparison from '$lib/features/purchase-quotations/components/PurchaseQuotationComparison.svelte';

  let requestId = $derived(page.params.requestId ?? '');
</script>

<svelte:head>
  <title>Comparación de cotizaciones | GestionaSV</title>
</svelte:head>

<PurchaseQuotationComparison {requestId} />
