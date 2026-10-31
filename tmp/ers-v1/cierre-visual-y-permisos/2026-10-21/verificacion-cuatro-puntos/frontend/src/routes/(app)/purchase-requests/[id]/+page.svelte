<script lang="ts">
  import { page } from '$app/state';
  import PurchaseRequestDetail from '$lib/features/purchase-requests/components/PurchaseRequestDetail.svelte';

  let requestId = $derived(page.params.id ?? '');
</script>

<svelte:head><title>Detalle de solicitud de compra — GestionaSV</title></svelte:head>

<PurchaseRequestDetail {requestId} />
