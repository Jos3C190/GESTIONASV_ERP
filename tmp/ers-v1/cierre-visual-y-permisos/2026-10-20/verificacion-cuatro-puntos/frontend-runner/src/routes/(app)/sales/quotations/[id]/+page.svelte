<script lang="ts">
  import { page } from '$app/state';
  import SalesQuotationDetail from '$lib/features/sales/components/SalesQuotationDetail.svelte';

  let id = $derived(page.params.id);
</script>

{#if id}
  {#key id}
    <SalesQuotationDetail {id} />
  {/key}
{:else}
  <p class="p-6 text-sm text-danger">No se encontró el identificador de la cotización.</p>
{/if}
