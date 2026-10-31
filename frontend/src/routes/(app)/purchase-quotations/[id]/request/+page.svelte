<script lang="ts">
  import { page } from '$app/state';
  import PurchaseQuotationRequestDocument from '$lib/features/purchase-quotations/components/PurchaseQuotationRequestDocument.svelte';

  let quotationId = $derived(page.params.id ?? '');
  let consolidationId = $derived(page.url.searchParams.get('consolidation_id'));
</script>

<svelte:head>
  <title>Documento de solicitud de cotización | GestionaSV</title>
</svelte:head>

<PurchaseQuotationRequestDocument id={quotationId} {consolidationId} />
