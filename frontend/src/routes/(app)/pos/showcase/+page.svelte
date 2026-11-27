<script lang="ts">
  import ShowcasePage from '#lib/features/pos/ShowcasePage.svelte';
  import { permissions } from '#lib/stores/permissions.svelte.ts';

  const allowed = $derived(
    permissions.hasAnyPermission(['pos:showcase', 'pos:registers_manage', 'pos:supervise'])
  );
</script>

<svelte:head>
  <title>Vitrina | GestionaSV</title>
</svelte:head>

{#if !allowed}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para ver la vitrina.
  </div>
{:else}
  <div class="space-y-5">
    <header>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Punto de venta</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">
        Vitrina
      </h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        La existencia suelta del mostrador: lo que pasa a vitrina se vende por pieza, primero lo que
        vence antes. Al cerrar el día, el conteo registra la merma.
      </p>
    </header>
    <ShowcasePage />
  </div>
{/if}
