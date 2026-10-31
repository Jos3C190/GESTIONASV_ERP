<script lang="ts">
  import { page } from '$app/state';
  import ProductEditor from '$lib/features/products/components/ProductEditor.svelte';

  let productId = $derived(Number(page.params.id));
</script>

<ProductEditor mode="edit" {productId} />
