<script lang="ts">
  import FleetIcon from './FleetIcon.svelte';
  import VehicleImage from './VehicleImage.svelte';
  import VehicleStatus from './VehicleStatus.svelte';
  import { formatFleetNumber, type FleetVehicle } from './mock-data';

  let { vehicle, onclose }: { vehicle: FleetVehicle; onclose: () => void } = $props();
  let section = $state('Resumen');
  let closeButton = $state<HTMLButtonElement>();
  let panel = $state<HTMLElement>();
  $effect(() => {
    if (vehicle.id) {
      section = 'Resumen';
      closeButton?.focus();
      panel?.scrollIntoView?.({ block: 'start', behavior: 'instant' });
    }
  });
  const sections = ['Resumen', 'Mantenimiento', 'Documentos'];
</script>

<aside bind:this={panel} class="detail" aria-label={`Detalle de ${vehicle.id}`}>
  <div class="detail-heading">
    <span>Detalle del vehículo</span><button
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
        <h2>{vehicle.id}</h2>
        <p>{vehicle.model} <span> / </span> {vehicle.year}</p>
      </div>
      <VehicleStatus status={vehicle.status} />
    </div>
    <VehicleImage {vehicle} large />
    <div class="hero-footer">
      <span class="plate">{vehicle.plate}</span><span
        ><FleetIcon name="shield" size={13} /> Documentación vigente</span
      >
    </div>
  </div>
  <nav class="detail-nav" aria-label="Secciones del vehículo">
    {#each sections as item}<button
        type="button"
        class:active={section === item}
        aria-pressed={section === item}
        onclick={() => (section = item)}>{item}</button
      >{/each}
  </nav>
  <div class="detail-content">
    {#if section === 'Resumen'}
      <section class="detail-section">
        <h3>Información general</h3>
        <dl class="specs">
          <div>
            <dt>Tipo de vehículo</dt>
            <dd>{vehicle.kind}</dd>
          </div>
          <div>
            <dt>Capacidad máxima</dt>
            <dd>{formatFleetNumber(vehicle.capacity)} kg</dd>
          </div>
          <div>
            <dt>Kilometraje</dt>
            <dd>{formatFleetNumber(vehicle.mileage)} km</dd>
          </div>
          <div>
            <dt>Combustible</dt>
            <dd>Diésel</dd>
          </div>
        </dl>
      </section>
      <section class="detail-section">
        <h3>Conductor asignado</h3>
        <div class="driver-profile">
          <span class="avatar">{vehicle.initials}</span>
          <div><strong>{vehicle.driver}</strong><span>Conductor de distribución</span></div>
          <span class="driver-check"><FleetIcon name="check" size={15} /></span>
        </div>
      </section>
      <section class="detail-section">
        <div class="section-heading">
          <h3>{vehicle.status === 'En ruta' ? 'Recorrido de hoy' : 'Ubicación actual'}</h3>
          <span class="demo-label">Simulado</span>
        </div>
        <div class="route-box">
          <div class="route-stop">
            <span class="stop-dot origin"></span>
            <div>
              <span>{vehicle.status === 'En ruta' ? 'Origen' : 'Vehículo en'}</span><strong
                >{vehicle.location}</strong
              >
            </div>
          </div>
          <div class="route-connector"></div>
          <div class="route-stop">
            <span class="stop-dot"></span>
            <div>
              <span>{vehicle.status === 'En ruta' ? 'Destino' : 'Estado operativo'}</span><strong
                >{vehicle.destination}</strong
              >
            </div>
          </div>
          {#if vehicle.status === 'En ruta'}<div class="route-progress-label">
              <span>Avance del recorrido</span><strong>{vehicle.progress}%</strong>
            </div>
            <div class="route-progress"><span style:width={`${vehicle.progress}%`}></span></div>
            <div class="eta">
              <FleetIcon name="clock" size={13} /> Llegada estimada
              <strong>{vehicle.arrival}</strong>
            </div>{/if}
        </div>
      </section>
      <section class="detail-section">
        <div class="section-heading">
          <h3>Nivel de combustible</h3>
          <strong class="fuel-number">{vehicle.fuel}%</strong>
        </div>
        <div class="fuel-track"><span style:width={`${vehicle.fuel}%`}></span></div>
        <p class="muted-note">Lectura de ejemplo para esta maqueta.</p>
      </section>
    {:else if section === 'Mantenimiento'}
      <section class="detail-section">
        <h3>Próximo servicio</h3>
        <div class="service-callout">
          <FleetIcon name="wrench" size={22} />
          <div>
            <strong>{vehicle.nextService}</strong><span
              >{vehicle.status === 'Mantenimiento'
                ? 'Servicio preventivo en taller central'
                : 'Mantenimiento preventivo programado'}</span
            >
          </div>
        </div>
        <dl class="specs">
          <div>
            <dt>Odómetro actual</dt>
            <dd>{formatFleetNumber(vehicle.mileage)} km</dd>
          </div>
          <div>
            <dt>Frecuencia</dt>
            <dd>Cada 5,000 km</dd>
          </div>
        </dl>
      </section>
      <section class="detail-section">
        <h3>Historial de servicios</h3>
        <ol class="timeline">
          <li>
            <span class="timeline-check"><FleetIcon name="check" size={12} /></span>
            <div>
              <strong>Cambio de aceite y filtros</strong>
              <p>20 sep 2026 · Taller central</p>
              <span>Servicio completado</span>
            </div>
          </li>
          <li>
            <span class="timeline-check"><FleetIcon name="check" size={12} /></span>
            <div>
              <strong>Revisión de frenos</strong>
              <p>16 ago 2026 · Taller central</p>
              <span>Servicio completado</span>
            </div>
          </li>
          <li>
            <span class="timeline-check"><FleetIcon name="check" size={12} /></span>
            <div>
              <strong>Rotación de neumáticos</strong>
              <p>12 jul 2026 · Taller central</p>
              <span>Servicio completado</span>
            </div>
          </li>
        </ol>
        <p class="muted-note">Historial ilustrativo. No corresponde a servicios reales.</p>
      </section>
    {:else}
      <section class="detail-section">
        <h3>Documentos del vehículo</h3>
        <p class="document-intro">Una vista organizada de los documentos de cada unidad.</p>
        <div class="document-list">
          {#each ['Tarjeta de circulación', 'Seguro del vehículo', 'Revisión técnica'] as document}<div
              class="document-row"
            >
              <span class="document-icon"><FleetIcon name="file" size={19} /></span>
              <div><strong>{document}</strong><span>PDF · Documento de muestra</span></div>
              <span class="document-status">Vigente</span>
            </div>{/each}
        </div>
        <div class="document-notice">
          <FleetIcon name="info" size={16} />
          <p>Los documentos son ilustrativos y no contienen archivos descargables.</p>
        </div>
      </section>
    {/if}
  </div>
  <div class="detail-footer">
    <FleetIcon name="info" size={14} /><span>Vista de demostración. Datos sin conexión.</span>
  </div>
</aside>

<style>
  .detail {
    align-self: start;
    position: sticky;
    top: 20px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
    max-height: calc(100dvh - 96px);
    overflow-y: auto;
    overscroll-behavior: contain;
    scrollbar-width: thin;
    scroll-margin-top: 20px;
    min-width: 0;
  }
  .detail-heading {
    position: sticky;
    top: 0;
    z-index: 2;
    min-height: 59px;
    background: rgb(var(--surface));
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-bottom: 1px solid rgb(var(--border));
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
  button:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 3px;
  }
  .close-button:hover {
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground));
  }
  .detail-hero {
    background: rgb(var(--surface-muted));
    padding: 20px 18px 15px;
  }
  .hero-title,
  .hero-footer,
  .section-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  h2 {
    font-size: 21px;
    line-height: 1.2;
    font-weight: 650;
    letter-spacing: -0.8px;
  }
  .hero-title p {
    color: rgb(var(--foreground-muted));
    font-size: 12px;
    margin-top: 5px;
  }
  .hero-title p span {
    color: rgb(var(--border-strong));
    padding: 0 3px;
  }
  .hero-footer > span:last-child {
    display: flex;
    gap: 5px;
    align-items: center;
    color: rgb(var(--success));
    font-size: 11px;
  }
  .plate {
    display: inline-flex;
    padding: 4px 7px;
    background: rgb(var(--surface));
    border: 1px solid rgb(var(--border-strong));
    border-radius: 4px;
    font:
      10px 'Geist Mono',
      monospace;
  }
  .detail-nav {
    position: sticky;
    top: 59px;
    z-index: 1;
    background: rgb(var(--surface));
    display: flex;
    gap: 16px;
    padding: 0 18px;
    border-top: 1px solid rgb(var(--border));
    border-bottom: 1px solid rgb(var(--border));
  }
  .detail-nav button {
    padding: 14px 0 12px;
    border-bottom: 2px solid transparent;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .detail-nav .active {
    color: rgb(var(--foreground));
    border-bottom-color: rgb(var(--foreground));
    font-weight: 600;
  }
  .detail-content {
    padding: 0 18px;
  }
  .detail-section {
    padding: 19px 0;
    border-bottom: 1px solid rgb(var(--border));
  }
  .detail-section:last-child {
    border-bottom: 0;
  }
  h3 {
    font-size: 12px;
    font-weight: 600;
  }
  .specs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 17px 12px;
    margin-top: 16px;
  }
  dt {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
    margin-bottom: 4px;
  }
  dd {
    font-size: 12px;
    font-weight: 550;
  }
  .driver-profile {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 14px;
  }
  .avatar {
    display: grid;
    place-items: center;
    width: 36px;
    height: 36px;
    border: 1px solid rgb(var(--border));
    border-radius: 50%;
    background: rgb(var(--surface-hover));
    font-size: 12px;
    font-weight: 600;
  }
  .driver-profile strong,
  .driver-profile div span {
    display: block;
    font-size: 12px;
  }
  .driver-profile div span {
    color: rgb(var(--foreground-muted));
    font-size: 11px;
    margin-top: 4px;
  }
  .driver-check {
    margin-left: auto;
    color: rgb(var(--success));
  }
  .demo-label {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
    padding: 3px 5px;
    background: rgb(var(--surface-muted));
    border: 1px solid rgb(var(--border));
    border-radius: 4px;
  }
  .route-box {
    background: rgb(var(--surface-muted));
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    padding: 16px 13px 12px;
    margin-top: 12px;
  }
  .route-stop {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  .route-stop div {
    display: grid;
    gap: 3px;
  }
  .route-stop div > span {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .route-stop strong {
    font-size: 12px;
    font-weight: 550;
  }
  .stop-dot {
    height: 8px;
    width: 8px;
    flex-shrink: 0;
    border-radius: 50%;
    background: rgb(var(--primary));
    outline: 3px solid rgb(var(--primary) / 0.1);
  }
  .stop-dot.origin {
    background: rgb(var(--surface));
    border: 1px solid rgb(var(--foreground-muted));
    outline: none;
  }
  .route-connector {
    height: 18px;
    border-left: 1px dashed rgb(var(--border-strong));
    margin: 4px 0 4px 3px;
  }
  .route-progress-label {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
    margin-top: 18px;
  }
  .route-progress-label strong {
    color: rgb(var(--foreground));
    font-weight: 550;
  }
  .route-progress,
  .fuel-track {
    height: 4px;
    background: rgb(var(--border));
    border-radius: 4px;
    margin-top: 7px;
    overflow: hidden;
  }
  .route-progress span,
  .fuel-track span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: rgb(var(--primary));
  }
  .fuel-track {
    margin-top: 12px;
  }
  .fuel-track span {
    background: rgb(var(--success));
  }
  .fuel-number {
    font-size: 12px;
    font-weight: 550;
  }
  .eta {
    display: flex;
    align-items: center;
    gap: 5px;
    margin-top: 12px;
    padding-top: 11px;
    border-top: 1px solid rgb(var(--border));
    color: rgb(var(--foreground-muted));
    font-size: 11px;
  }
  .eta strong {
    margin-left: auto;
    font-weight: 550;
    color: rgb(var(--foreground));
  }
  .muted-note {
    margin-top: 9px;
    color: rgb(var(--foreground-muted));
    font-size: 11px;
    line-height: 1.6;
  }
  .detail-footer {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgb(var(--surface-muted));
    border-top: 1px solid rgb(var(--border));
    padding: 13px 18px;
    color: rgb(var(--foreground-muted));
    font-size: 11px;
  }
  .service-callout {
    display: flex;
    gap: 11px;
    align-items: center;
    background: rgb(var(--warning) / 0.07);
    border: 1px solid rgb(var(--warning) / 0.2);
    color: rgb(var(--fleet-warning-ink, var(--warning)));
    border-radius: 8px;
    padding: 15px 12px;
    margin-top: 12px;
  }
  .service-callout strong,
  .service-callout span {
    display: block;
  }
  .service-callout strong {
    font-size: 12px;
    font-weight: 600;
  }
  .service-callout span {
    margin-top: 4px;
    font-size: 11px;
  }
  .timeline {
    list-style: none;
    margin: 18px 0 0;
    padding: 0;
  }
  .timeline li {
    display: flex;
    gap: 12px;
    padding-bottom: 25px;
    position: relative;
  }
  .timeline li:not(:last-child)::after {
    content: '';
    position: absolute;
    left: 10px;
    top: 24px;
    bottom: 3px;
    border-left: 1px solid rgb(var(--border));
  }
  .timeline li:last-child {
    padding-bottom: 10px;
  }
  .timeline-check {
    display: grid;
    place-items: center;
    height: 22px;
    width: 22px;
    border: 1px solid rgb(var(--border));
    border-radius: 50%;
    color: rgb(var(--success));
    flex-shrink: 0;
  }
  .timeline strong {
    font-size: 12px;
    font-weight: 550;
  }
  .timeline p,
  .timeline div > span {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
    margin-top: 5px;
  }
  .timeline div > span {
    display: block;
    color: rgb(var(--success));
    font-size: 11px;
  }
  .document-intro {
    font-size: 12px;
    line-height: 1.6;
    color: rgb(var(--foreground-muted));
    margin: 10px 0 18px;
  }
  .document-row {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 15px 0;
    border-bottom: 1px solid rgb(var(--border));
  }
  .document-icon {
    background: rgb(var(--surface-muted));
    border: 1px solid rgb(var(--border));
    padding: 8px;
    border-radius: 7px;
  }
  .document-row strong,
  .document-row div > span {
    display: block;
    font-size: 11px;
    font-weight: 550;
  }
  .document-row div > span {
    color: rgb(var(--foreground-muted));
    font-size: 11px;
    margin-top: 4px;
    font-weight: 400;
  }
  .document-status {
    margin-left: auto;
    color: rgb(var(--success));
    font-size: 11px;
  }
  .document-notice {
    display: flex;
    gap: 8px;
    align-items: start;
    margin-top: 20px;
    color: rgb(var(--foreground-muted));
  }
  .document-notice p {
    font-size: 11px;
    line-height: 1.6;
  }
  @media (max-width: 1000px) {
    .detail {
      position: static;
      max-height: none;
      overflow: visible;
      overscroll-behavior: auto;
    }
  }
  @media (max-width: 640px) {
    .detail-heading {
      min-height: 65px;
    }
    .detail-nav {
      top: 65px;
      gap: 20px;
    }
    .detail-nav button {
      font-size: 12px;
      min-height: 44px;
    }
    .close-button {
      height: 36px;
      width: 36px;
    }
  }
</style>
