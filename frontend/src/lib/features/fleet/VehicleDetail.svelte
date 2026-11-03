<script lang="ts">
  import type { FleetVehicle } from './api';
  import {
    formatDateTime,
    formatNumber,
    FUEL_LABELS,
    meterName,
    meterShort,
    plateLabel,
    LICENSE_LABELS
  } from './catalog';
  import ComplianceList from './ComplianceList.svelte';
  import FleetIcon from './FleetIcon.svelte';
  import VehicleImage from './VehicleImage.svelte';
  import VehicleStatus from './VehicleStatus.svelte';

  let { vehicle, onclose }: { vehicle: FleetVehicle; onclose: () => void } = $props();
  let closeButton = $state<HTMLButtonElement>();
  let panel = $state<HTMLElement>();
  $effect(() => {
    if (vehicle.id) {
      closeButton?.focus();
      panel?.scrollIntoView?.({ block: 'start', behavior: 'instant' });
    }
  });
</script>

<aside bind:this={panel} class="detail" aria-label={`Detalle de ${vehicle.code}`}>
  <div class="detail-heading">
    <span>Resumen del vehículo</span><button
      bind:this={closeButton}
      type="button"
      onclick={onclose}
      class="close-button"
      aria-label="Cerrar detalle"><FleetIcon name="close" size={17} /></button
    >
  </div>
  <div class="detail-hero">
    <div class="hero-title">
      <div>
        <h2>{vehicle.code}</h2>
        <p>{vehicle.brand} {vehicle.model} <span>/</span> {vehicle.year}</p>
      </div>
      <VehicleStatus status={vehicle.operational_status} />
    </div>
    <VehicleImage
      image={vehicle.type.base_image}
      typeName={vehicle.type.name}
      label={`${vehicle.brand} ${vehicle.model}`}
      large
    />
    <div class="hero-footer">
      <span class="plate">{plateLabel(vehicle.plate)}</span>
      <span class="branch"
        ><FleetIcon name="pin" size={13} />{vehicle.branch_name}{vehicle.loan
          ? ` · Prestado a ${vehicle.loan.to_branch_name}`
          : ''}</span
      >
    </div>
  </div>
  <div class="detail-content">
    <section class="detail-section">
      <h3>Aptitud para operar</h3>
      <ComplianceList compliance={vehicle.compliance} />
    </section>
    {#if vehicle.current_transfer}
      <section class="detail-section">
        <h3>Traslado en curso</h3>
        <a class="trip" href={`/tracking?transfer=${vehicle.current_transfer.id}`}>
          <FleetIcon name="route" size={16} />
          <span>
            <strong>{vehicle.current_transfer.code}</strong>
            <small
              >Hacia {vehicle.current_transfer.destination_branch} · salió {formatDateTime(
                vehicle.current_transfer.dispatched_at
              )}</small
            >
          </span>
          <FleetIcon name="chevron" size={14} />
        </a>
      </section>
    {/if}
    <section class="detail-section">
      <h3>Conductor asignado</h3>
      {#if vehicle.driver}
        <a class="driver" href={`/drivers/${vehicle.driver.driver_id}`}>
          <span class="avatar">{vehicle.driver.initials}</span>
          <span>
            <strong>{vehicle.driver.name}</strong>
            <small>Licencia {LICENSE_LABELS[vehicle.driver.license_class]}</small>
          </span>
          <FleetIcon name="chevron" size={14} />
        </a>
      {:else}
        <p class="muted">Sin conductor asignado.</p>
      {/if}
    </section>
    <section class="detail-section">
      <h3>Información general</h3>
      <dl class="specs">
        <div>
          <dt>Tipo</dt>
          <dd>{vehicle.type.name}</dd>
        </div>
        <div>
          <dt>Capacidad</dt>
          <dd>{formatNumber(vehicle.capacity_kg)} kg</dd>
        </div>
        <div>
          <dt>{meterName(vehicle.type.meter_unit)}</dt>
          <dd>{formatNumber(vehicle.odometer_km)} {meterShort(vehicle.type.meter_unit)}</dd>
        </div>
        <div>
          <dt>Combustible</dt>
          <dd>{FUEL_LABELS[vehicle.fuel_type]}</dd>
        </div>
        <div>
          <dt>GPS</dt>
          <dd>{vehicle.gps_linked ? 'Vinculado' : 'Sin GPS'}</dd>
        </div>
        <div>
          <dt>Color</dt>
          <dd>{vehicle.color ?? '—'}</dd>
        </div>
      </dl>
    </section>
  </div>
  <div class="detail-footer">
    <a class="open-file" href={`/fleet/${vehicle.id}`}
      >Abrir ficha completa <FleetIcon name="arrow" size={15} /></a
    >
  </div>
</aside>

<style>
  .detail {
    align-self: start;
    position: sticky;
    top: 20px;
    min-width: 0;
    max-height: calc(100dvh - 96px);
    overflow-y: auto;
    overscroll-behavior: contain;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
    scrollbar-width: thin;
  }
  .detail-heading {
    position: sticky;
    top: 0;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-bottom: 1px solid rgb(var(--border));
    background: rgb(var(--surface));
    font-size: 12px;
    font-weight: 550;
  }
  .close-button {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border: 1px solid rgb(var(--border));
    border-radius: 50%;
    color: rgb(var(--foreground-muted));
  }
  .close-button:hover {
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground));
  }
  .detail-hero {
    padding: 20px 18px 15px;
    background: rgb(var(--surface-muted));
  }
  .hero-title,
  .hero-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  h2 {
    font-size: 21px;
    font-weight: 650;
    letter-spacing: -0.8px;
  }
  .hero-title p {
    margin-top: 5px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .hero-title p span {
    padding: 0 3px;
    color: rgb(var(--border-strong));
  }
  .plate {
    padding: 4px 7px;
    border: 1px solid rgb(var(--border-strong));
    border-radius: 4px;
    background: rgb(var(--surface));
    font:
      10px 'Geist Mono',
      monospace;
  }
  .branch {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .detail-content {
    padding: 0 18px;
  }
  .detail-section {
    padding: 17px 0;
    border-bottom: 1px solid rgb(var(--border));
  }
  .detail-section:last-child {
    border-bottom: 0;
  }
  h3 {
    margin-bottom: 11px;
    font-size: 12px;
    font-weight: 600;
  }
  .trip,
  .driver {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 9px;
  }
  .trip:hover,
  .driver:hover {
    background: rgb(var(--surface-hover));
  }
  .trip span,
  .driver span:not(.avatar) {
    display: grid;
    flex: 1;
    gap: 2px;
    min-width: 0;
  }
  strong {
    font-size: 12px;
    font-weight: 600;
  }
  small {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .avatar {
    display: grid;
    place-items: center;
    flex-shrink: 0;
    width: 34px;
    height: 34px;
    border: 1px solid rgb(var(--border));
    border-radius: 50%;
    background: rgb(var(--surface-hover));
    font-size: 11px;
    font-weight: 600;
  }
  .muted {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .specs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px 12px;
  }
  dt {
    margin-bottom: 3px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  dd {
    font-size: 12px;
    font-weight: 550;
  }
  .detail-footer {
    padding: 13px 18px;
    border-top: 1px solid rgb(var(--border));
    background: rgb(var(--surface-muted));
  }
  .open-file {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    height: 36px;
    border-radius: 8px;
    background: rgb(var(--foreground));
    color: rgb(var(--surface));
    font-size: 12px;
    font-weight: 600;
  }
  button:focus-visible,
  a:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 2px;
  }
  @media (max-width: 1000px) {
    .detail {
      position: static;
      max-height: none;
      overflow: visible;
    }
  }
</style>
