<script lang="ts">
  import { page } from '$app/state';
  import PurchaseDetail from '$lib/features/purchases/components/PurchaseDetail.svelte';

  let purchaseId = $derived(page.params.id ?? '');
</script>

<svelte:head>
  <title>Detalle de compra | GestionaSV</title>
</svelte:head>

<PurchaseDetail id={purchaseId} />
