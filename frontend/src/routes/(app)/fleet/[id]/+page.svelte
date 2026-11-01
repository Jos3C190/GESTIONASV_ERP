<script lang="ts">
  import { page } from '$app/state';
  import VehicleFile from '$lib/features/fleet/VehicleFile.svelte';
</script>

<svelte:head><title>Vehículo — GestionaSV</title></svelte:head>

{#key page.params.id}
  <VehicleFile vehicleId={page.params.id ?? ''} />
{/key}
