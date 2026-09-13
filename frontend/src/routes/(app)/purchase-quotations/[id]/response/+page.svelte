<script lang="ts">
  import { page } from '$app/state';
  import PurchaseQuotationResponseEditor from '$lib/features/purchase-quotations/components/PurchaseQuotationResponseEditor.svelte';

  let quotationId = $derived(page.params.id ?? '');
</script>

<svelte:head>
  <title>Registrar respuesta | GestionaSV</title>
</svelte:head>

<PurchaseQuotationResponseEditor id={quotationId} />
