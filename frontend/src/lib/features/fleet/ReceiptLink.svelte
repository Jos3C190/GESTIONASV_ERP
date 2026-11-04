<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi } from './api';

  let {
    vehicleId,
    documentId,
    label = 'Ver factura'
  }: { vehicleId: string; documentId: string; label?: string } = $props();

  let error = $state<string | null>(null);

  async function view() {
    error = null;
    // Se abre antes de esperar la URL: después de un await el navegador lo bloquearía.
    const tab = window.open('', '_blank');
    try {
      const { url } = await fleetApi.documents(vehicleId).previewUrl(documentId);
      if (tab) tab.location.href = url;
      else window.location.href = url;
    } catch (err) {
      tab?.close();
      error = err instanceof HttpError ? err.message : 'No se pudo abrir la factura.';
    }
  }
</script>

{#if permissions.hasPermission('fleet_documents:read')}
  <button type="button" onclick={view}>{label}</button>
  {#if error}<small role="alert">{error}</small>{/if}
{/if}

<style>
  button {
    min-height: 44px;
    color: rgb(var(--primary));
    font-size: 12px;
    font-weight: 500;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  small {
    display: block;
    color: rgb(var(--danger));
    font-size: 12px;
  }
</style>
