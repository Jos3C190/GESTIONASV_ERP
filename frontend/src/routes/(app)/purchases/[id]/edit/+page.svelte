<script lang="ts">
  import { page } from '$app/state';
  import PurchaseDraftEditor from '$lib/features/purchases/components/PurchaseDraftEditor.svelte';

  let purchaseId = $derived(page.params.id ?? '');
</script>

<svelte:head>
  <title>Editar recepción de compra | GestionaSV</title>
</svelte:head>

<PurchaseDraftEditor {purchaseId} />
