<script lang="ts">
  import { page } from '$app/state';
  import PurchaseReceivingEditor from '$lib/features/purchases/components/PurchaseReceivingEditor.svelte';

  let orderId = $derived(page.url.searchParams.get('order_id') ?? '');
</script>

<svelte:head>
  <title>Nueva recepción de compra | GestionaSV</title>
</svelte:head>

<PurchaseReceivingEditor {orderId} />
