<script lang="ts">
  import { page } from '$app/state';
  import RetaceoDraftEditor from '$lib/features/retaceos/components/RetaceoDraftEditor.svelte';

  let retaceoId = $derived(page.params.id ?? '');
</script>

<svelte:head>
  <title>Editar retaceo | GestionaSV</title>
</svelte:head>

<RetaceoDraftEditor {retaceoId} />
