<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { company } from '$lib/stores/company.svelte';
  import { session } from '$lib/stores/session.svelte';

  onMount(() => {
    const destination = !session.isAuthenticated
      ? '/login'
      : company.id
        ? '/dashboard'
        : '/companies';

    void goto(destination, { replaceState: true });
  });
</script>

<svelte:head>
  <title>GestionaSV</title>
</svelte:head>

<main class="grid min-h-screen place-items-center bg-surface" role="status" aria-label="Redirigiendo">
  <span class="h-5 w-5 animate-spin rounded-full border-2 border-primary/25 border-t-primary"></span>
</main>
