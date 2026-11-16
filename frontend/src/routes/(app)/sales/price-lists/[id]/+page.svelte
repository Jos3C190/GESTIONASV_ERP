<script lang="ts">
  import { page } from '$app/state';
  import PriceListDetail from '#lib/features/price-lists/components/PriceListDetail.svelte';
</script>

{#key page.params.id}
  <PriceListDetail listId={page.params.id ?? ''} />
{/key}
