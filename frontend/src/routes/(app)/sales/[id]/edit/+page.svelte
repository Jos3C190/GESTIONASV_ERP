<script lang="ts">
  import { page } from '$app/state';
  import SalesDocumentEditor from '#lib/features/sales/components/SalesDocumentEditor.svelte';

  let orderId = $derived(page.params.id);
</script>

{#key orderId}
  <SalesDocumentEditor kind="order" documentId={orderId} />
{/key}
