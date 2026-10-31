<script lang="ts">
  import { page } from '$app/state';
  import PurchaseQuotationResponseEditor from '$lib/features/purchase-quotations/components/PurchaseQuotationResponseEditor.svelte';

  let quotationId = $derived(page.params.id ?? '');
  let consolidationId = $derived(page.url.searchParams.get('consolidation_id'));
</script>

<svelte:head>
  <title>Registrar respuesta | GestionaSV</title>
</svelte:head>

<PurchaseQuotationResponseEditor id={quotationId} {consolidationId} />
