<script lang="ts">
  import { vehicleAlerts } from './alerts';
  import FleetIcon from './FleetIcon.svelte';
  import VehicleImage from './VehicleImage.svelte';
  import VehicleStatus from './VehicleStatus.svelte';
  import { formatFleetNumber, type FleetVehicle } from './mock-data';
  let {
    vehicle,
    selected = false,
    onselect
  }: { vehicle: FleetVehicle; selected?: boolean; onselect: () => void } = $props();
  const load = $derived(Math.round((vehicle.load / vehicle.capacity) * 100));
  const alerts = $derived(vehicleAlerts(vehicle));
  const topAlert = $derived(alerts[0]);
</script>

<button
  id={`fleet-card-${vehicle.id}`}
  type="button"
  class="vehicle-card"
  class:selected
  aria-label={`Ver detalle de ${vehicle.id}`}
  aria-describedby={`fleet-summary-${vehicle.id}`}
  aria-pressed={selected}
  onclick={onselect}
>
  <span id={`fleet-summary-${vehicle.id}`} class="sr-only"
    >{vehicle.model}. {vehicle.status}. {vehicle.status === 'En ruta'
      ? vehicle.destination
      : vehicle.location}.{alerts.length
      ? ` Alertas: ${alerts.map((alert) => alert.label).join(', ')}.`
      : ''}</span
  >
  <div class="vehicle-stage">
    <div class="stage-top">
      <VehicleStatus status={vehicle.status} /><span class="vehicle-kind">{vehicle.kind}</span>
    </div>
    <VehicleImage {vehicle} />
    <div class="stage-bottom">
      <span class="vehicle-code">{vehicle.id}</span><span class="plate">{vehicle.plate}</span>
    </div>
  </div>
  <div class="card-body">
    <div class="model-line"><span>{vehicle.model}</span><span>{vehicle.year}</span></div>
    <div class="destination">
      <FleetIcon name={vehicle.status === 'En ruta' ? 'route' : 'pin'} size={15} /><span
        >{vehicle.status === 'En ruta' ? vehicle.destination : vehicle.location}</span
      ><FleetIcon name="chevron" size={14} />
    </div>
    <div class="driver">
      <span class="avatar">{vehicle.initials}</span><span>{vehicle.driver}</span><span
        class="arrival">{vehicle.arrival}</span
      >
    </div>
    {#if topAlert}
      <div
        class="alert-row {topAlert.tone}"
        title={alerts.map((alert) => alert.label).join(' · ')}
      >
        <FleetIcon name="alert" size={13} /><span>{topAlert.label}</span>{#if alerts.length > 1}<span
            class="alert-more">+{alerts.length - 1}</span
          >{/if}
      </div>
    {:else}
      <div class="alert-row ok">
        <FleetIcon name="shield" size={13} /><span>Documentos y servicio al día</span>
      </div>
    {/if}
    <div class="load-label">
      <span>Capacidad de carga</span><span
        ><strong>{formatFleetNumber(vehicle.load)}</strong> / {formatFleetNumber(vehicle.capacity)} kg</span
      >
    </div>
    <div
      class="load-track"
      role="progressbar"
      aria-label={`Carga de ${vehicle.id}`}
      aria-valuenow={load}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div style:width={`${load}%`}></div>
    </div>
  </div>
</button>

<style>
  .vehicle-card {
    width: 100%;
    min-width: 0;
    overflow: hidden;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
    text-align: left;
    color: rgb(var(--foreground));
    transition:
      border-color 150ms,
      box-shadow 150ms;
  }
  .vehicle-card:hover {
    border-color: rgb(var(--border-strong));
    box-shadow: var(--shadow-md);
  }
  .vehicle-card.selected {
    border-color: rgb(var(--primary));
    box-shadow: 0 0 0 1px rgb(var(--primary));
  }
  .vehicle-card:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 4px;
  }
  .vehicle-stage {
    background: rgb(var(--surface-muted));
    padding: 13px 14px 12px;
    border-bottom: 1px solid rgb(var(--border));
  }
  .stage-top,
  .stage-bottom,
  .model-line,
  .destination,
  .driver,
  .load-label {
    display: flex;
    align-items: center;
  }
  .stage-top,
  .stage-bottom,
  .model-line,
  .load-label {
    justify-content: space-between;
    gap: 8px;
  }
  .vehicle-kind {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .vehicle-code {
    font-size: 15px;
    font-weight: 650;
    letter-spacing: -0.4px;
  }
  .plate {
    border: 1px solid rgb(var(--border-strong));
    border-radius: 4px;
    background: rgb(var(--surface));
    padding: 3px 5px;
    font:
      11px 'Geist Mono',
      monospace;
    letter-spacing: 0.35px;
  }
  .card-body {
    padding: 12px 14px;
  }
  .model-line {
    margin-bottom: 8px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .destination {
    gap: 7px;
    margin-bottom: 10px;
    font-size: 12px;
    font-weight: 550;
  }
  .destination > :last-child {
    margin-left: auto;
    color: rgb(var(--foreground-muted));
  }
  .destination span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .driver {
    gap: 6px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
    margin-bottom: 12px;
  }
  .avatar {
    display: grid;
    place-items: center;
    width: 23px;
    height: 23px;
    flex-shrink: 0;
    border-radius: 50%;
    background: rgb(var(--surface-hover));
    border: 1px solid rgb(var(--border));
    color: rgb(var(--foreground));
    font-size: 8px;
    font-weight: 600;
  }
  .arrival {
    margin-left: auto;
    font-size: 11px;
    white-space: nowrap;
  }
  .alert-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 12px;
    padding: 6px 8px;
    border: 1px solid transparent;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 550;
  }
  .alert-row span:first-of-type {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .alert-row.danger {
    color: rgb(var(--danger));
    background: rgb(var(--danger) / 0.08);
    border-color: rgb(var(--danger) / 0.22);
  }
  .alert-row.warning {
    color: rgb(var(--fleet-warning-ink, var(--warning)));
    background: rgb(var(--warning) / 0.08);
    border-color: rgb(var(--warning) / 0.22);
  }
  .alert-row.ok {
    color: rgb(var(--foreground-muted));
    background: rgb(var(--surface-muted));
    font-weight: 450;
  }
  .alert-row.ok :global(svg) {
    color: rgb(var(--success));
  }
  .alert-more {
    margin-left: auto;
    padding: 1px 5px;
    border: 1px solid currentColor;
    border-radius: 999px;
    background: rgb(var(--surface));
    font-size: 10px;
  }
  .load-label {
    margin-bottom: 7px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .load-label strong {
    font-weight: 550;
    color: rgb(var(--foreground));
  }
  .load-track {
    height: 4px;
    overflow: hidden;
    border-radius: 5px;
    background: rgb(var(--border));
  }
  .load-track div {
    height: 100%;
    border-radius: inherit;
    background: rgb(var(--success));
  }
  @media (prefers-reduced-motion: reduce) {
    .vehicle-card {
      transition: none;
    }
  }
</style>
