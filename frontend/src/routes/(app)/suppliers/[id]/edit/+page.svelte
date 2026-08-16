<script lang="ts">
  import { page } from '$app/state';
  import SupplierEditor from '$lib/features/suppliers/components/SupplierEditor.svelte';

  const supplierId = $derived(Number(page.params.id));
</script>

<SupplierEditor mode="edit" {supplierId} />
