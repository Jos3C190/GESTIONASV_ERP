<script lang="ts">
  import { page } from '$app/state';
  import SalesDocumentEditor from '#lib/features/sales/components/SalesDocumentEditor.svelte';

  let quotationId = $derived(page.params.id);
</script>

{#key quotationId}
  <SalesDocumentEditor documentId={quotationId} />
{/key}
