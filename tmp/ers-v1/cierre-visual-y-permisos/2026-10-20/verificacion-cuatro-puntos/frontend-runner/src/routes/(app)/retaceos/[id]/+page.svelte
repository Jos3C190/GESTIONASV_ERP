<script lang="ts">
  import { page } from '$app/state';
  import RetaceoDetail from '$lib/features/retaceos/components/RetaceoDetail.svelte';

  let retaceoId = $derived(page.params.id ?? '');
</script>

<svelte:head>
  <title>Detalle de retaceo | GestionaSV</title>
</svelte:head>

<RetaceoDetail id={retaceoId} />
