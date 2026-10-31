<script lang="ts">
  import { page } from '$app/state';
  import PurchaseOrderDetail from '$lib/features/purchase-orders/components/PurchaseOrderDetail.svelte';

  let orderId = $derived(page.params.id ?? '');
</script>

<svelte:head>
  <title>Detalle de orden de compra | GestionaSV</title>
</svelte:head>

<PurchaseOrderDetail id={orderId} />
