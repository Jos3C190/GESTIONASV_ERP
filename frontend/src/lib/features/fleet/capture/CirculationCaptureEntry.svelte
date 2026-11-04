<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import CaptureDialog from '$lib/features/document-capture/CaptureDialog.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type CirculationConfirmed, type FleetVehicle } from '../api';
  import { formatDate } from '../catalog';
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
  let cardIssued = $state<string | null>(null);
  const canCapture = $derived(allowed && available);
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
    cardIssued = card?.issued_on ?? null;
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

{#if vehicle.plate && (canCapture || cardExpires)}
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
    {#if canCapture}
      <Button
        size="lg"
        variant={registered || !cardKnown ? 'secondary' : 'primary'}
        onclick={() => {
          notice = null;
          open = true;
        }}
      >
        <FleetIcon name="camera" size={16} />{registered
          ? 'Capturar de nuevo'
          : 'Capturar con fotos'}
      </Button>
    {/if}
    {#if cardExpires}
      <dl>
        <div>
          <dt>Placa</dt>
          <dd>{vehicle.plate}</dd>
        </div>
        <div>
          <dt>Emisión</dt>
          <dd>{formatDate(cardIssued)}</dd>
        </div>
        <div>
          <dt>Vence</dt>
          <dd>{printedExpiry}</dd>
        </div>
        <div>
          <dt>VIN</dt>
          <dd>{vehicle.vin ?? '—'}</dd>
        </div>
        <div>
          <dt>Chasis</dt>
          <dd>{vehicle.chassis_number ?? '—'}</dd>
        </div>
        <div>
          <dt>Motor</dt>
          <dd>{vehicle.engine_number ?? '—'}</dd>
        </div>
      </dl>
    {/if}
    {#if notice}<p class="notice" role="status">{notice}</p>{/if}
  </section>
  {#if canCapture}<CaptureDialog bind:open {config} onconfirmed={confirmed} />{/if}
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
  dl {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    margin: 0;
    padding-top: 12px;
    border-top: 1px solid rgb(var(--border));
  }
  dt {
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  dd {
    margin: 2px 0 0;
    color: rgb(var(--foreground));
    font-size: 14px;
    overflow-wrap: anywhere;
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
    .notice,
    dl {
      grid-column: 1 / -1;
    }
    dl {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }
</style>
