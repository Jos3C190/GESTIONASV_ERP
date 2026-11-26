<script lang="ts">
  import PosWorkspace from '#lib/features/pos/PosWorkspace.svelte';
  import { permissions } from '#lib/stores/permissions.svelte.ts';

  const allowed = $derived(permissions.hasAnyPermission(['pos:sell', 'pos:shift_open']));
</script>

<svelte:head>
  <title>Caja | GestionaSV</title>
</svelte:head>

{#if !allowed}
  <div class="app-page">
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      No tienes permiso para trabajar en la caja.
    </div>
  </div>
{:else}
  <PosWorkspace />
{/if}
