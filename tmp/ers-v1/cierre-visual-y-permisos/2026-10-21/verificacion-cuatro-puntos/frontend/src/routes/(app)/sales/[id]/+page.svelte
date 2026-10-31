<script lang="ts">
  import { page } from '$app/state';
  import SaleDetail from '$lib/features/sales/components/SaleDetail.svelte';

  let id = $derived(page.params.id);
</script>

{#if id}
  {#key id}
    <SaleDetail {id} />
  {/key}
{:else}
  <p class="p-6 text-sm text-danger">No se encontró el identificador de la venta.</p>
{/if}
