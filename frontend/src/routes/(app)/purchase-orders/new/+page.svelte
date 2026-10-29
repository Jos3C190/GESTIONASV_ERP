<script lang="ts">
  import { page } from '$app/state';
  import PurchaseOrderEditor from '$lib/features/purchase-orders/components/PurchaseOrderEditor.svelte';

  let quotationId = $derived(page.url.searchParams.get('quotation_id') ?? '');
  let consolidationId = $derived(page.url.searchParams.get('consolidation_id') ?? '');
</script>

<svelte:head>
  <title>Nueva orden de compra | GestionaSV</title>
</svelte:head>

<PurchaseOrderEditor {quotationId} {consolidationId} />
