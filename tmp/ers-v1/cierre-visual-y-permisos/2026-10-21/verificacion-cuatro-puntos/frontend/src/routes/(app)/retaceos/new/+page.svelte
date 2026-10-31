<script lang="ts">
  import { page } from '$app/state';
  import RetaceoCreateEditor from '$lib/features/retaceos/components/RetaceoCreateEditor.svelte';

  let purchaseId = $derived(page.url.searchParams.get('purchase_id') ?? '');
</script>

<svelte:head>
  <title>Nuevo retaceo | GestionaSV</title>
</svelte:head>

<RetaceoCreateEditor {purchaseId} />
