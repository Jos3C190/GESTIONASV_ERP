<script lang="ts">
  import { page } from '$app/state';
  import WarehouseEditor from '$lib/features/warehouses/components/WarehouseEditor.svelte';
</script>

<WarehouseEditor mode="edit" warehouseId={page.params.id} />
