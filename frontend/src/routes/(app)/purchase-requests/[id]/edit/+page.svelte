<script lang="ts">
  import { page } from '$app/state';
  import PurchaseRequestDraftEditor from '$lib/features/purchase-requests/components/PurchaseRequestDraftEditor.svelte';

  let requestId = $derived(page.params.id ?? '');
</script>

<svelte:head><title>Editar solicitud de compra — GestionaSV</title></svelte:head>

<PurchaseRequestDraftEditor {requestId} />
