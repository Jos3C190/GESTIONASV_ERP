<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import CaptureDialog from '$lib/features/document-capture/CaptureDialog.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type CirculationConfirmed, type FleetVehicle } from '../api';
  import FleetIcon from '../FleetIcon.svelte';
  import { circulationCaptureConfig, confirmationNotice } from './circulation-config';

  let {
    vehicle,
    onconfirmed
  }: { vehicle: FleetVehicle; onconfirmed: (vehicle: FleetVehicle) => void } = $props();

  const allowed = $derived(permissions.hasPermission('fleet_documents:upload'));
  const config = $derived(circulationCaptureConfig(vehicle.id));
  let available = $state(false);
  let open = $state(false);
  let notice = $state<string | null>(null);

  $effect(() => {
    if (!allowed) return;
    fleetApi
      .circulationCaptureCapabilities()
      .then((result) => (available = result.enabled))
      .catch(() => (available = false));
  });

  function confirmed(result: CirculationConfirmed) {
    notice = confirmationNotice(result);
    onconfirmed(result.vehicle);
  }
</script>

{#if allowed && available && vehicle.plate}
  <section class="entry">
    <div>
      <h3>Tarjeta de circulación</h3>
      <p>Fotografía el frente y el reverso; propondremos los datos para que los revises.</p>
    </div>
    <Button
      size="lg"
      onclick={() => {
        notice = null;
        open = true;
      }}
    >
      <FleetIcon name="camera" size={16} />Capturar con fotos
    </Button>
    {#if notice}<p class="notice" role="status">{notice}</p>{/if}
  </section>
  <CaptureDialog bind:open {config} onconfirmed={confirmed} />
{/if}

<style>
  .entry {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 12px;
    margin-bottom: 16px;
    padding: 16px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface-elevated));
  }
  h3 {
    margin: 0;
    color: rgb(var(--foreground));
    font-size: 14px;
    font-weight: 600;
  }
  p {
    margin: 4px 0 0;
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  .notice {
    margin: 0;
    padding: 8px 12px;
    border-left: 3px solid rgb(var(--success));
    border-radius: 8px;
    color: rgb(var(--foreground));
    background: rgb(var(--success) / 10%);
  }
  @media (min-width: 640px) {
    .entry {
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
    }
    .notice {
      grid-column: 1 / -1;
    }
  }
</style>
