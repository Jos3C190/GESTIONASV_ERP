<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import FleetIcon from './FleetIcon.svelte';
  import VehicleCard from './VehicleCard.svelte';
  import VehicleDetail from './VehicleDetail.svelte';
  import VehicleStatus from './VehicleStatus.svelte';
  import {
    DEMO_VEHICLES,
    VEHICLE_TYPES,
    VEHICLE_KINDS,
    formatFleetNumber,
    type FleetVehicle,
    type VehicleStatus as Status,
    type VehicleKind
  } from './mock-data';

  let query = $state('');
  let status = $state<'Todos' | Status>('Todos');
  let kind = $state<'Todos' | VehicleKind>('Todos');
  let view = $state<'grid' | 'list'>('grid');
  let selected = $state<FleetVehicle | null>(null);
  const tabs = [
    { value: 'Todos', label: 'Todos los vehículos' },
    { value: 'En ruta', label: 'En ruta' },
    { value: 'Disponible', label: 'Disponibles' },
    { value: 'Mantenimiento', label: 'Mantenimiento' }
  ] as const;
  const total = (value: string) =>
    DEMO_VEHICLES.filter((item) => value === 'Todos' || item.status === value).length;
  const metrics = [
    {
      label: 'Vehículos en flota',
      value: DEMO_VEHICLES.length,
      icon: 'truck',
      caption: 'Unidades de distribución',
      tone: 'neutral'
    },
    {
      label: 'En ruta',
      value: total('En ruta'),
      icon: 'route',
      caption: 'En recorridos de entrega',
      tone: 'route'
    },
    {
      label: 'Disponibles',
      value: total('Disponible'),
      icon: 'check',
      caption: 'Listos para una nueva ruta',
      tone: 'available'
    },
    {
      label: 'En mantenimiento',
      value: total('Mantenimiento'),
      icon: 'wrench',
      caption: 'En servicio preventivo',
      tone: 'maintenance'
    }
  ] as const;
  const normalize = (value: string) =>
    value
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
  let filtered = $derived(
    DEMO_VEHICLES.filter(
      (vehicle) =>
        (status === 'Todos' || vehicle.status === status) &&
        (kind === 'Todos' || vehicle.kind === kind) &&
        normalize(
          `${vehicle.id} ${vehicle.plate} ${vehicle.kind} ${vehicle.name} ${vehicle.model} ${vehicle.driver} ${vehicle.destination}`
        ).includes(normalize(query.trim()))
    )
  );

  function clearFilters() {
    query = '';
    status = 'Todos';
    kind = 'Todos';
  }
  function closeDetail() {
    const id = selected?.id;
    selected = null;
    if (id) requestAnimationFrame(() => document.getElementById(`fleet-card-${id}`)?.focus());
  }
</script>

<svelte:window
  onkeydown={(event) => {
    if (event.key === 'Escape' && selected) closeDetail();
  }}
/>

<div class="fleet-workspace" class:detail-open={selected !== null}>
  <header class="page-heading">
    <div>
      <div class="title-line">
        <h1>Flota</h1>
        <span class="prototype"><span></span>Vista de demostración</span>
      </div>
      <p>Un lugar para conocer cada vehículo y el pulso de tu operación.</p>
    </div>
    <div class="heading-actions">
      <span class="snapshot-date"><FleetIcon name="calendar" size={14} />28 oct, 2026</span><span
        title="El registro de vehículos estará disponible en la versión funcional"
        ><Button size="sm" disabled><FleetIcon name="plus" size={15} />Añadir vehículo</Button
        ></span
      >
    </div>
  </header>

  <section class="overview" aria-label="Resumen de la flota">
    <h2 class="sr-only">Estado de la operación</h2>
    <div class="metrics">
      {#each metrics as metric}<div class="metric">
          <div class="metric-label">
            <FleetIcon name={metric.icon} size={15} /><span>{metric.label}</span>
          </div>
          <div class="metric-value">
            <strong>{String(metric.value).padStart(2, '0')}</strong><span
              class="metric-mark {metric.tone}"><FleetIcon name={metric.icon} size={16} /></span
            >
          </div>
          <p>{metric.caption}</p>
        </div>{/each}
    </div>
    <div class="fleet-distribution" aria-hidden="true">
      <span
        class="distribution-route"
        style:width={`${(total('En ruta') / DEMO_VEHICLES.length) * 100}%`}
      ></span><span
        class="distribution-available"
        style:width={`${(total('Disponible') / DEMO_VEHICLES.length) * 100}%`}
      ></span><span
        class="distribution-maintenance"
        style:width={`${(total('Mantenimiento') / DEMO_VEHICLES.length) * 100}%`}
      ></span>
    </div>
  </section>

  <section class="fleet-catalog" aria-labelledby="fleet-catalog-heading">
    <div class="catalog-heading">
      <div>
        <h2 id="fleet-catalog-heading">Directorio de vehículos</h2>
      </div>
      <div class="view-switch" aria-label="Vista del directorio">
        <button
          type="button"
          aria-label="Vista de tarjetas"
          aria-pressed={view === 'grid'}
          class:active={view === 'grid'}
          onclick={() => (view = 'grid')}><FleetIcon name="grid" size={15} /></button
        ><button
          type="button"
          aria-label="Vista de lista"
          aria-pressed={view === 'list'}
          class:active={view === 'list'}
          onclick={() => (view = 'list')}><FleetIcon name="list" size={17} /></button
        >
      </div>
    </div>
    <div class="catalog-toolbar">
      <nav class="status-tabs" aria-label="Filtrar vehículos por estado">
        {#each tabs as tab}<button
            type="button"
            class:active={status === tab.value}
            aria-pressed={status === tab.value}
            onclick={() => (status = tab.value)}>{tab.label}<span>{total(tab.value)}</span></button
          >{/each}
      </nav>
    </div>
    <div class="filter-row">
      <label class="search-field"
        ><FleetIcon name="search" size={16} /><span class="sr-only">Buscar vehículos</span><input
          type="search"
          bind:value={query}
          placeholder="Buscar por vehículo, placa o conductor…"
        /></label
      ><label class="kind-filter"
        ><span class="sr-only">Tipo de vehículo</span><select
          value={kind}
          onchange={(event) => (kind = event.currentTarget.value as typeof kind)}
          ><option value="Todos">Todos los tipos</option>
          {#each VEHICLE_KINDS as vehicleKind}
            <option value={vehicleKind}>{VEHICLE_TYPES[vehicleKind].label}</option>
          {/each}</select
        ></label
      ><span class="result-count" aria-live="polite"
        >{filtered.length} {filtered.length === 1 ? 'vehículo' : 'vehículos'}</span
      >
    </div>

    <div class="workspace" class:has-detail={selected !== null}>
      <div class="catalog-content">
        {#if filtered.length === 0}
          <div class="empty-state">
            <span class="empty-icon"><FleetIcon name="search" size={25} /></span>
            <h3>No encontramos vehículos</h3>
            <p>Prueba con otra placa, nombre o combinación de filtros.</p>
            <Button variant="secondary" size="sm" onclick={clearFilters}>Limpiar filtros</Button>
          </div>
        {:else if view === 'grid'}
          <div class="vehicle-grid">
            {#each filtered as vehicle (vehicle.id)}<VehicleCard
                {vehicle}
                selected={selected?.id === vehicle.id}
                onselect={() => (selected = vehicle)}
              />{/each}
          </div>
        {:else}
          <div class="list-wrap">
            <table>
              <caption class="sr-only">Vehículos de demostración</caption><thead
                ><tr
                  ><th>Vehículo</th><th>Estado</th><th>Conductor</th><th>Ubicación / destino</th><th
                    >Kilometraje</th
                  ><th><span class="sr-only">Acciones</span></th></tr
                ></thead
              ><tbody
                >{#each filtered as vehicle (vehicle.id)}<tr
                    class:selected-row={selected?.id === vehicle.id}
                    ><td
                      ><div class="table-vehicle">
                        <span class="table-icon"><FleetIcon name="truck" size={21} /></span>
                        <div>
                          <strong>{vehicle.id}</strong><span>{vehicle.model} · {vehicle.plate}</span
                          >
                        </div>
                      </div></td
                    ><td><VehicleStatus status={vehicle.status} /></td><td>{vehicle.driver}</td><td
                      >{vehicle.status === 'En ruta' ? vehicle.destination : vehicle.location}</td
                    ><td class="mileage">{formatFleetNumber(vehicle.mileage)} km</td><td
                      ><button
                        id={`fleet-card-${vehicle.id}`}
                        type="button"
                        class="table-action"
                        aria-label={`Ver detalle de ${vehicle.id}`}
                        aria-pressed={selected?.id === vehicle.id}
                        onclick={() => (selected = vehicle)}
                        ><FleetIcon name="chevron" size={16} /></button
                      ></td
                    ></tr
                  >{/each}</tbody
              >
            </table>
          </div>
        {/if}
        <div class="catalog-footer">
          <span>Mostrando {filtered.length} de {DEMO_VEHICLES.length} vehículos</span><span
            ><FleetIcon name="shield" size={13} />Información de ejemplo</span
          >
        </div>
      </div>
      {#if selected}<VehicleDetail vehicle={selected} onclose={closeDetail} />{/if}
    </div>
  </section>
  <div class="prototype-note">
    <FleetIcon name="info" size={14} /><span
      >Maqueta de Flota. Puedes explorar las vistas y los filtros; los datos son ilustrativos y no
      se guardan cambios.</span
    >
  </div>
</div>

<style>
  .fleet-workspace {
    --fleet-route-ink: 0 85 186;
    --fleet-warning-ink: 137 75 0;
    max-width: 1840px;
    margin: 0 auto;
    padding: 22px 30px;
    color: rgb(var(--foreground));
  }
  .page-heading {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 24px;
    margin-bottom: 20px;
  }
  .title-line {
    display: flex;
    align-items: center;
    gap: 13px;
  }
  h1 {
    font-size: 27px;
    line-height: 1.15;
    font-weight: 650;
    letter-spacing: -1px;
  }
  .page-heading p {
    margin-top: 7px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
    line-height: 1.6;
  }
  .prototype {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 7px;
    border: 1px solid rgb(var(--border));
    border-radius: 5px;
    color: rgb(var(--foreground-muted));
    font-size: 11px;
    white-space: nowrap;
  }
  .prototype > span {
    height: 5px;
    width: 5px;
    border-radius: 50%;
    background: rgb(var(--foreground-muted));
  }
  .heading-actions {
    display: flex;
    align-items: center;
    gap: 17px;
    flex-shrink: 0;
  }
  .snapshot-date {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .overview {
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    overflow: hidden;
    background: rgb(var(--surface));
    margin-bottom: 20px;
  }
  .metrics {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    padding: 16px 0;
  }
  .metric {
    padding: 0 21px;
    border-right: 1px solid rgb(var(--border));
  }
  .metric:last-child {
    border: 0;
  }
  .metric-label {
    display: flex;
    align-items: center;
    gap: 7px;
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  .metric-value {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 10px 0 5px;
  }
  .metric-value strong {
    font-size: 28px;
    line-height: 1;
    font-weight: 550;
    letter-spacing: -1.3px;
    font-variant-numeric: tabular-nums;
  }
  .metric-mark {
    display: grid;
    place-items: center;
    height: 29px;
    width: 29px;
    border-radius: 8px;
  }
  .neutral {
    color: rgb(var(--foreground-muted));
    background: rgb(var(--surface-hover));
  }
  .route {
    color: rgb(var(--primary));
    background: rgb(var(--primary) / 0.07);
  }
  .available {
    color: rgb(var(--success));
    background: rgb(var(--success) / 0.07);
  }
  .maintenance {
    color: rgb(var(--warning));
    background: rgb(var(--warning) / 0.08);
  }
  .metric p {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
    line-height: 1.5;
  }
  .fleet-distribution {
    display: flex;
    height: 3px;
    gap: 3px;
    padding: 0 20px;
    margin-bottom: 13px;
    opacity: 0.75;
  }
  .fleet-distribution span {
    border-radius: 2px;
  }
  .distribution-route {
    background: rgb(var(--primary));
  }
  .distribution-available {
    background: rgb(var(--success));
  }
  .distribution-maintenance {
    background: rgb(var(--warning));
  }
  .catalog-heading {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    gap: 16px;
  }
  .catalog-heading h2 {
    font-size: 15px;
    font-weight: 600;
    letter-spacing: -0.3px;
  }
  .view-switch {
    display: flex;
    gap: 3px;
    border: 1px solid rgb(var(--border));
    border-radius: 7px;
    padding: 3px;
    background: rgb(var(--surface-muted));
  }
  .view-switch button {
    display: grid;
    place-items: center;
    height: 27px;
    width: 32px;
    border: 1px solid transparent;
    border-radius: 4px;
    color: rgb(var(--foreground-muted));
  }
  .view-switch button.active {
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    border-color: rgb(var(--border));
    box-shadow: var(--shadow-sm);
  }
  .catalog-toolbar {
    border-bottom: 1px solid rgb(var(--border));
  }
  .status-tabs {
    display: flex;
    gap: 25px;
    overflow-x: auto;
  }
  .status-tabs button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 0 0 13px;
    font-size: 12px;
    white-space: nowrap;
    color: rgb(var(--foreground-muted));
    border-bottom: 2px solid transparent;
  }
  .status-tabs button.active {
    color: rgb(var(--foreground));
    border-bottom-color: rgb(var(--foreground));
    font-weight: 600;
  }
  .status-tabs button > span {
    display: grid;
    place-items: center;
    min-width: 19px;
    height: 17px;
    padding: 0 4px;
    background: rgb(var(--surface-hover));
    border: 1px solid rgb(var(--border));
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
  }
  button:focus-visible,
  select:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 3px;
  }
  .filter-row {
    display: flex;
    gap: 9px;
    align-items: center;
    padding: 10px 0;
  }
  .search-field {
    display: flex;
    align-items: center;
    gap: 8px;
    width: min(340px, 50%);
    border: 1px solid rgb(var(--control-border));
    border-radius: 7px;
    padding: 0 10px;
    height: 35px;
    color: rgb(var(--foreground-muted));
    background: rgb(var(--surface));
  }
  .search-field:focus-within {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 2px;
  }
  .search-field input {
    width: 100%;
    min-width: 0;
    outline: 0;
    background: transparent;
    color: rgb(var(--foreground));
    font-size: 11px;
    height: 100%;
  }
  .search-field input::placeholder {
    color: rgb(var(--foreground-subtle));
  }
  .kind-filter select {
    height: 35px;
    max-width: 180px;
    border: 1px solid rgb(var(--control-border));
    border-radius: 7px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    padding: 0 27px 0 11px;
    font-size: 11px;
  }
  .result-count {
    margin-left: auto;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
    white-space: nowrap;
  }
  .workspace {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 22px;
    align-items: start;
  }
  .workspace.has-detail {
    grid-template-columns: minmax(0, 1fr) 340px;
  }
  .catalog-content {
    min-width: 0;
  }
  .vehicle-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
  }
  .has-detail .vehicle-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .catalog-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 18px 0 0;
    color: rgb(var(--foreground-muted));
    font-size: 11px;
  }
  .catalog-footer > span:last-child {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    min-height: 350px;
    border: 1px dashed rgb(var(--border-strong));
    border-radius: 12px;
    padding: 32px 20px;
    background: rgb(var(--surface-muted));
  }
  .empty-icon {
    display: grid;
    place-items: center;
    height: 54px;
    width: 54px;
    background: rgb(var(--surface));
    border: 1px solid rgb(var(--border));
    border-radius: 50%;
    color: rgb(var(--foreground-muted));
    margin-bottom: 16px;
  }
  .empty-state h3 {
    font-size: 15px;
    font-weight: 600;
  }
  .empty-state p {
    margin: 8px 0 20px;
    color: rgb(var(--foreground-muted));
    font-size: 12px;
    line-height: 1.6;
  }
  .list-wrap {
    width: 100%;
    overflow-x: auto;
    border: 1px solid rgb(var(--border));
    border-radius: 10px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
    white-space: nowrap;
    font-size: 12px;
  }
  th {
    font-size: 11px;
    font-weight: 500;
    color: rgb(var(--foreground-muted));
    background: rgb(var(--surface-muted));
    padding: 12px 15px;
  }
  td {
    padding: 15px;
    border-top: 1px solid rgb(var(--border));
  }
  .table-vehicle {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .table-vehicle strong {
    display: block;
    font-size: 12px;
    font-weight: 600;
  }
  .table-vehicle div > span {
    display: block;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
    margin-top: 4px;
  }
  .table-icon {
    display: grid;
    place-items: center;
    width: 37px;
    height: 37px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: rgb(var(--surface-muted));
    color: rgb(var(--foreground-muted));
  }
  .table-action {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border: 1px solid rgb(var(--border));
    border-radius: 6px;
  }
  .table-action:hover {
    background: rgb(var(--surface-hover));
  }
  .selected-row {
    background: rgb(var(--primary) / 0.04);
  }
  .mileage {
    font-variant-numeric: tabular-nums;
  }
  .prototype-note {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 7px;
    margin-top: 25px;
    color: rgb(var(--foreground-muted));
    font-size: 11px;
    line-height: 1.6;
  }
  :global([data-theme='dark']) .fleet-workspace {
    --fleet-route-ink: 0 168 243;
    --fleet-warning-ink: 255 184 77;
  }
  .has-detail .list-wrap :is(th, td):nth-child(3),
  .has-detail .list-wrap :is(th, td):nth-child(4),
  .has-detail .list-wrap :is(th, td):nth-child(5) {
    display: none;
  }
  @media (min-width: 1700px) {
    .vehicle-grid {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    .has-detail .vehicle-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }
  @media (max-width: 1250px) {
    .vehicle-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .has-detail .vehicle-grid {
      grid-template-columns: minmax(0, 1fr);
    }
    .workspace.has-detail {
      grid-template-columns: minmax(0, 1fr) 320px;
    }
    .snapshot-date {
      display: none;
    }
  }
  @media (max-width: 1000px) {
    .metrics {
      grid-template-columns: 1fr 1fr;
      row-gap: 18px;
    }
    .metric:nth-child(2) {
      border-right: 0;
    }
    .detail-open .overview,
    .detail-open .catalog-heading,
    .detail-open .catalog-toolbar,
    .detail-open .filter-row {
      display: none;
    }
    .workspace.has-detail {
      grid-template-columns: minmax(0, 1fr);
    }
    .has-detail .catalog-content {
      display: none;
    }
    .fleet-workspace {
      padding: 24px;
    }
    .metric {
      padding: 0 15px;
    }
    .metric-label {
      font-size: 11px;
      gap: 5px;
    }
    .metric-mark {
      height: 24px;
      width: 24px;
    }
  }
  @media (max-width: 640px) {
    .fleet-workspace {
      padding: 22px 16px;
    }
    .page-heading {
      display: block;
      margin-bottom: 18px;
    }
    h1 {
      font-size: 26px;
    }
    .heading-actions {
      display: none;
    }
    .page-heading p {
      display: none;
    }
    .metrics {
      grid-template-columns: 1fr 1fr;
      padding: 14px 0;
      row-gap: 14px;
    }
    .metric:nth-child(2) {
      border-right: 0;
    }
    .metric-label {
      font-size: 11px;
    }
    .metric p {
      display: none;
    }
    .metric-value {
      margin: 8px 0 0;
    }
    .metric-value strong {
      font-size: 28px;
    }
    .fleet-distribution {
      padding: 0 15px;
    }
    .overview {
      margin-bottom: 18px;
    }
    .vehicle-grid {
      grid-template-columns: minmax(0, 1fr);
      gap: 16px;
    }
    .status-tabs {
      gap: 20px;
      scrollbar-width: none;
    }
    .status-tabs button {
      padding-top: 7px;
      min-height: 44px;
    }
    .view-switch button {
      min-width: 36px;
      height: 34px;
    }
    .filter-row {
      flex-wrap: wrap;
      padding: 10px 0;
    }
    .search-field {
      width: 100%;
      height: 42px;
    }
    .search-field input {
      font-size: 12px;
    }
    .kind-filter select {
      height: 36px;
      font-size: 12px;
    }
    .catalog-footer {
      font-size: 11px;
    }
    .catalog-footer > span:last-child {
      display: none;
    }
    .prototype-note {
      align-items: flex-start;
      justify-content: flex-start;
    }
    .result-count {
      font-size: 12px;
    }
    .catalog-heading {
      margin-bottom: 12px;
    }
  }
</style>
