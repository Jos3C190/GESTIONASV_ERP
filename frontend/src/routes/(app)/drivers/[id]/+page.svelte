<script lang="ts">
  import { page } from '$app/state';
  import DriverProfile from '$lib/features/drivers/DriverProfile.svelte';
</script>

<svelte:head><title>Conductor — GestionaSV</title></svelte:head>

{#key page.params.id}
  <DriverProfile driverId={page.params.id ?? ''} />
{/key}
