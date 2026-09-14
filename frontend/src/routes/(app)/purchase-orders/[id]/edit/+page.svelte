<script lang="ts">
  import { page } from '$app/state';
  import PurchaseOrderDraftEditor from '$lib/features/purchase-orders/components/PurchaseOrderDraftEditor.svelte';

  let orderId = $derived(page.params.id ?? '');
</script>

<svelte:head><title>Editar orden de compra — GestionaSV</title></svelte:head>

<PurchaseOrderDraftEditor {orderId} />
