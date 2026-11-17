<script lang="ts">
  import { page } from '$app/state';
  import FiscalDocumentDetail from '#lib/features/sales/components/FiscalDocumentDetail.svelte';

  let id = $derived(page.params.id);
</script>

{#if id}
  {#key id}
    <FiscalDocumentDetail {id} />
  {/key}
{:else}
  <p class="text-sm text-danger">No se encontró el identificador del documento fiscal.</p>
{/if}
