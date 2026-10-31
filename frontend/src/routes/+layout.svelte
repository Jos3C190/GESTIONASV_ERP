<script lang="ts">
  import '../app.css';
  import type { Snippet } from 'svelte';
  import type { LayoutData } from './$types';
  import { dev } from '$app/environment';
  import ConfirmActionDialog from '$lib/components/ui/ConfirmActionDialog.svelte';

  interface Props {
    children: Snippet;
    data: LayoutData;
  }

  let { children }: Props = $props();

  /**
   * En desarrollo, una página restaurada desde la caché atrás/adelante (bfcache) trae congelado
   * el código de cuando se dejó y pierde la conexión de recarga de Vite: se veían versiones
   * viejas aunque el servidor ya sirviera la nueva. Al restaurarse, se recarga con el código
   * actual. En producción la caché se conserva porque acelera la navegación.
   */
  function reloadRestoredPage(event: PageTransitionEvent) {
    if (dev && event.persisted) location.reload();
  }
</script>

<svelte:window onpageshow={reloadRestoredPage} />

<svelte:head>
  <title>GestionaSV</title>
  <meta name="description" content="GestionaSV — panel de gestión empresarial." />
</svelte:head>

{@render children()}
<ConfirmActionDialog />
