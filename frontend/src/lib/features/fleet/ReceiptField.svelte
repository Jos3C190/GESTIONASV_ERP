<script lang="ts">
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi } from './api';

  let {
    id,
    vehicleId,
    label = 'Factura',
    noun = 'factura',
    value = $bindable('')
  }: { id: string; vehicleId: string; label?: string; noun?: string; value?: string } = $props();

  let documents = $state<{ id: string; title: string }[]>([]);
  let status = $state<'loading' | 'ready' | 'failed'>('loading');
  const canRead = $derived(permissions.hasPermission('fleet_documents:read'));

  $effect(() => {
    if (canRead) void load(vehicleId);
  });

  async function load(owner: string) {
    status = 'loading';
    try {
      documents = (await fleetApi.documents(owner).list({ size: 100 })).items;
      status = 'ready';
    } catch {
      documents = [];
      status = 'failed';
    }
  }
</script>

{#if canRead}
  <div class="field">
    {#if status === 'failed'}
      <span>{label}</span>
      <small class="failed" role="alert">
        No se pudieron cargar los documentos. Puedes registrar sin adjuntarlo.
      </small>
    {:else if status === 'ready' && documents.length === 0}
      <span>{label}</span>
      <small>
        Este vehículo no tiene documentos. Para ligarlo, súbelo primero en la pestaña Documentos.
      </small>
    {:else}
      <label for={id}>{label}</label>
      <select {id} bind:value disabled={status === 'loading'}>
        <option value="">Sin {noun}</option>
        {#each documents as document (document.id)}
          <option value={document.id}>{document.title}</option>
        {/each}
      </select>
    {/if}
  </div>
{/if}

<style>
  .field {
    display: grid;
    align-content: start;
    gap: 6px;
    font-size: 14px;
    font-weight: 500;
  }
  select {
    width: 100%;
    min-height: 44px;
    padding: 0 12px;
    border: 1px solid rgb(var(--control-border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 16px;
    font-weight: 400;
  }
  small {
    color: rgb(var(--foreground-muted));
    font-size: 12px;
    font-weight: 400;
  }
  .failed {
    color: rgb(var(--danger));
  }
  @media (min-width: 768px) {
    select {
      min-height: 38px;
      font-size: 13px;
    }
  }
</style>
