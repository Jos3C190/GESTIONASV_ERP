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
  /** Último día de vigencia de la tarjeta actual, si hay una. */
  let cardExpires = $state<string | null>(null);
  /** Hasta saberlo, no se afirma que falte: se evita un botón principal que luego cambia. */
  let cardKnown = $state(false);
  const today = new Date().toLocaleDateString('en-CA');
  const expired = $derived(cardExpires !== null && cardExpires < today);
  const registered = $derived(cardExpires !== null && !expired);
  // La tarjeta imprime MM-AAAA: se muestra igual para compararla de un vistazo.
  const printedExpiry = $derived(
    cardExpires ? `${cardExpires.slice(5, 7)}-${cardExpires.slice(0, 4)}` : ''
  );

  $effect(() => {
    if (!allowed) return;
    fleetApi
      .circulationCaptureCapabilities()
      .then((result) => (available = result.enabled))
      .catch(() => (available = false));
  });

  async function loadCard() {
    const id = vehicle.id;
    if (!permissions.hasPermission('fleet_documents:read')) {
      cardKnown = true;
      return;
    }
    const page = await fleetApi
      .documents(id)
      .list({ size: 100 })
      .catch(() => null);
    // La respuesta de un vehículo anterior no debe pintar este.
    if (id !== vehicle.id) return;
    const card = page?.items.find((item) => item.category_code === 'circulation_card');
    cardExpires = card?.expires_on ?? null;
    cardKnown = page !== null;
  }

  $effect(() => {
    void vehicle.id;
    void loadCard();
  });

  function confirmed(result: CirculationConfirmed) {
    notice = confirmationNotice(result);
    void loadCard();
    onconfirmed(result.vehicle);
  }
</script>

{#if allowed && available && vehicle.plate}
  <section class="entry">
    <div>
      <h3>Tarjeta de circulación</h3>
      {#if registered}
        <p>Registrada. Vence {printedExpiry}.</p>
      {:else if expired}
        <p class="expired">Venció en {printedExpiry}. Fotografía la tarjeta nueva.</p>
      {:else}
        <p>Fotografía el frente y el reverso; propondremos los datos para que los revises.</p>
      {/if}
    </div>
    <Button
      size="lg"
      variant={registered || !cardKnown ? 'secondary' : 'primary'}
      onclick={() => {
        notice = null;
        open = true;
      }}
    >
      <FleetIcon name="camera" size={16} />{registered ? 'Capturar de nuevo' : 'Capturar con fotos'}
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
  .expired {
    padding-left: 8px;
    border-left: 3px solid rgb(var(--danger));
    color: rgb(var(--foreground));
    font-weight: 500;
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
