<script lang="ts">
  import { page } from '$app/state';
  import PurchaseQuotationConsolidationEditor from '$lib/features/purchase-quotations/components/PurchaseQuotationConsolidationEditor.svelte';

  let consolidationId = $derived(
    (page.params as Record<string, string | undefined>).consolidationId ?? ''
  );
</script>

<svelte:head>
  <title>Preparar RFQ | GestionaSV</title>
</svelte:head>

<PurchaseQuotationConsolidationEditor {consolidationId} />
