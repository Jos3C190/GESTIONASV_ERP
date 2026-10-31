<script lang="ts">
  import { page } from '$app/state';
  import PurchaseQuotationEditor from '$lib/features/purchase-quotations/components/PurchaseQuotationEditor.svelte';

  let initialRequestId = $derived(page.url.searchParams.get('requestId') ?? undefined);
</script>

<svelte:head>
  <title>Nueva cotización de compra | GestionaSV</title>
</svelte:head>

<PurchaseQuotationEditor {initialRequestId} />
