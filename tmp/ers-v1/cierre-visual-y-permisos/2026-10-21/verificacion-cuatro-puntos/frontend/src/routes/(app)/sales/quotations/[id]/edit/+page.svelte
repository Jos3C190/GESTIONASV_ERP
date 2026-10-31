<script lang="ts">
  import { page } from '$app/state';
  import SalesQuotationEditor from '$lib/features/sales/components/SalesQuotationEditor.svelte';

  let quotationId = $derived(page.params.id);
</script>

{#key quotationId}
  <SalesQuotationEditor {quotationId} />
{/key}
