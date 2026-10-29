<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { demoRoute, demoSnapshot } from './demo';
  import TrackingMap from './TrackingMap.svelte';
  import {
    compassPoint,
    fromTraccar,
    STATUS_LABELS,
    timeAgo,
    type TrackedVehicle,
    type TrackingStatus
  } from './tracking';

  type Mode = 'loading' | 'live' | 'demo';
  type Filter = 'all' | TrackingStatus;

  const LIVE_POLL_MS = 5000;
  const DEMO_TICK_MS = 1000;
  const TRAIL_POINTS = 60;

  let mode = $state<Mode>('loading');
  let liveError = $state<string | null>(null);
  let vehicles = $state<TrackedVehicle[]>([]);
  let trails = $state<Record<string, [number, number][]>>({});
  let selectedKey = $state<string | null>(null);
  let follow = $state(false);
  let query = $state('');
  let filter = $state<Filter>('all');
  let now = $state(Date.now());
  let lastSync = $state<Date | null>(null);

  const filters: { id: Filter; label: string }[] = [
    { id: 'all', label: 'Todos' },
    { id: 'moving', label: 'En movimiento' },
    { id: 'stopped', label: 'Detenidos' },
    { id: 'offline', label: 'Sin señal' }
  ];

  const counts = $derived(
    vehicles.reduce(
      (acc, vehicle) => ({ ...acc, [vehicle.status]: acc[vehicle.status] + 1 }),
      { all: vehicles.length, moving: 0, stopped: 0, offline: 0 } as Record<Filter, number>
    )
  );

  const visible = $derived(
    vehicles.filter((vehicle) => {
      if (filter !== 'all' && vehicle.status !== filter) return false;
      const term = query.trim().toLowerCase();
      if (!term) return true;
      return [vehicle.name, vehicle.vehicle?.plate, vehicle.vehicle?.driver, vehicle.vehicle?.model]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(term));
    })
  );

  const selected = $derived(vehicles.find((vehicle) => vehicle.key === selectedKey) ?? null);
  const plannedRoute = $derived(
    mode === 'demo' && selected?.vehicle?.status === 'En ruta'
      ? demoRoute(selected.vehicle.destination)
      : null
  );

  function apply(next: TrackedVehicle[]) {
    vehicles = next;
    lastSync = new Date();
    const nextTrails: Record<string, [number, number][]> = {};
    for (const vehicle of next) {
      const previous = trails[vehicle.key] ?? [];
      const point: [number, number] = [vehicle.longitude, vehicle.latitude];
      const last = previous[previous.length - 1];
      nextTrails[vehicle.key] =
        last && last[0] === point[0] && last[1] === point[1]
          ? previous
          : [...previous, point].slice(-TRAIL_POINTS);
    }
    trails = nextTrails;
    if (selectedKey && !next.some((vehicle) => vehicle.key === selectedKey)) selectedKey = null;
  }

  let polling = false;

  // Consulta Traccar a través del backend. Sin configuración se usa la demostración;
  // si falla, se conservan los últimos datos en vivo o se muestra la demostración.
  async function pollLive(signal: AbortSignal) {
    if (polling) return;
    polling = true;
    try {
      const snapshot = await api.tracking.positions(signal);
      liveError = null;
      if (snapshot.configured) {
        if (mode !== 'live') trails = {};
        mode = 'live';
        apply(fromTraccar(snapshot.devices));
      } else if (mode !== 'demo') {
        mode = 'demo';
        trails = {};
      }
    } catch {
      if (signal.aborted) return;
      liveError =
        mode === 'live'
          ? 'Se perdió la conexión con el servidor GPS. Reintentando…'
          : 'No se pudo conectar con el servidor GPS. Mostrando la demostración.';
      if (mode === 'loading') mode = 'demo';
    } finally {
      polling = false;
    }
  }

  onMount(() => {
    const controller = new AbortController();
    pollLive(controller.signal);
    const livePoll = setInterval(() => pollLive(controller.signal), LIVE_POLL_MS);
    const tick = setInterval(() => {
      now = Date.now();
      if (mode === 'demo') apply(demoSnapshot(now));
    }, DEMO_TICK_MS);
    return () => {
      controller.abort();
      clearInterval(livePoll);
      clearInterval(tick);
    };
  });

  function select(key: string | null) {
    selectedKey = key;
    if (!key) follow = false;
  }
</script>

<svelte:window
  onkeydown={(event) => {
    if (event.key === 'Escape' && selectedKey) select(null);
  }}
/>

<div class="tracking-workspace">
  <header class="page-heading">
    <div>
      <div class="title-line">
        <h1>Seguimiento</h1>
        {#if mode === 'live'}
          <span class="mode-badge live"><span></span>En vivo · Traccar</span>
        {:else if mode === 'demo'}
          <span class="mode-badge"><span></span>Vista de demostración</span>
        {/if}
      </div>
      <p>
        Ubicación en tiempo real de las unidades de {company.active?.commercial_name ?? 'tu empresa'}.
      </p>
    </div>
    <div class="heading-meta">
      {#if lastSync}<span><FleetIcon name="refresh" size={14} /> Actualizado {timeAgo(lastSync, now)}</span>{/if}
    </div>
  </header>

  {#if liveError}
    <div class="banner" role="status"><FleetIcon name="alert" size={15} />{liveError}</div>
  {/if}

  <div class="tracking-shell">
    <TrackingMap
      vehicles={visible}
      {selectedKey}
      {follow}
      trail={selectedKey ? (trails[selectedKey] ?? []) : []}
      {plannedRoute}
      onselect={select}
    />

    <aside class="device-panel" aria-label="Unidades rastreadas">
      <div class="panel-search">
        <FleetIcon name="search" size={16} />
        <input
          bind:value={query}
          type="search"
          placeholder="Buscar unidad, placa o conductor"
          aria-label="Buscar unidades"
        />
      </div>
      <div class="filters" role="group" aria-label="Filtrar por estado">
        {#each filters as item (item.id)}
          <button
            type="button"
            class:active={filter === item.id}
            aria-pressed={filter === item.id}
            onclick={() => (filter = item.id)}
            >{item.label}<span>{counts[item.id]}</span></button
          >
        {/each}
      </div>
      <ul class="device-list">
        {#each visible as vehicle (vehicle.key)}
          <li>
            <button
              type="button"
              class="device-row"
              class:selected={vehicle.key === selectedKey}
              aria-pressed={vehicle.key === selectedKey}
              onclick={() => select(vehicle.key)}
            >
              <span class="device-avatar {vehicle.status}"><FleetIcon name="truck" size={17} /></span>
              <span class="device-main">
                <strong>{vehicle.name}</strong>
                <span>{vehicle.vehicle ? `${vehicle.vehicle.plate} · ${vehicle.vehicle.driver}` : 'Dispositivo GPS'}</span>
              </span>
              <span class="device-side">
                <span class="status-text {vehicle.status}">{STATUS_LABELS[vehicle.status]}</span>
                <span>{vehicle.status === 'moving' ? `${Math.round(vehicle.speedKmh)} km/h` : timeAgo(vehicle.fixTime, now)}</span>
              </span>
            </button>
          </li>
        {:else}
          <li class="empty">
            {mode === 'loading'
              ? 'Conectando con el servidor GPS…'
              : vehicles.length
                ? 'Ninguna unidad coincide con la búsqueda.'
                : 'Aún no hay unidades reportando posición.'}
          </li>
        {/each}
      </ul>
      {#if mode === 'demo'}
        <p class="panel-note">
          <FleetIcon name="info" size={13} />Posiciones simuladas. Configura Traccar para ver tus unidades
          reales.
        </p>
      {/if}
    </aside>

    {#if selected}
      <section class="vehicle-card" aria-label={`Detalle de ${selected.name}`}>
        <header>
          <div>
            <h2>{selected.name}</h2>
            <p>
              {selected.vehicle
                ? `${selected.vehicle.model} · ${selected.vehicle.plate}`
                : 'Dispositivo sin vehículo asociado'}
            </p>
          </div>
          <button type="button" class="icon-button" aria-label="Cerrar detalle" onclick={() => select(null)}
            ><FleetIcon name="close" size={16} /></button
          >
        </header>
        <div class="card-status">
          <span class="status-pill {selected.status}"><span></span>{STATUS_LABELS[selected.status]}</span>
          {#if selected.vehicle?.status === 'En ruta'}
            <span class="route-to"><FleetIcon name="route" size={14} />{selected.vehicle.destination}</span>
          {/if}
        </div>
        <dl class="stats">
          <div>
            <dt>Velocidad</dt>
            <dd>{Math.round(selected.speedKmh)} km/h</dd>
          </div>
          <div>
            <dt>Rumbo</dt>
            <dd>
              <FleetIcon name="navigation" size={13} class="course-icon" />
              {selected.status === 'moving' ? compassPoint(selected.course) : '—'}
            </dd>
          </div>
          <div>
            <dt>Última señal</dt>
            <dd>{timeAgo(selected.fixTime, now)}</dd>
          </div>
          <div>
            <dt>Motor</dt>
            <dd>{selected.ignition === null ? '—' : selected.ignition ? 'Encendido' : 'Apagado'}</dd>
          </div>
          {#if selected.vehicle}
            <div>
              <dt>Conductor</dt>
              <dd>{selected.vehicle.driver}</dd>
            </div>
          {/if}
          {#if selected.battery !== null}
            <div>
              <dt>Batería GPS</dt>
              <dd>{Math.round(selected.battery)}%</dd>
            </div>
          {/if}
        </dl>
        <p class="coords">
          <FleetIcon name="pin" size={13} />{selected.address ??
            `${selected.latitude.toFixed(5)}, ${selected.longitude.toFixed(5)}`}
        </p>
        <div class="card-actions">
          <button
            type="button"
            class:active={follow}
            aria-pressed={follow}
            onclick={() => (follow = !follow)}
            ><FleetIcon name="crosshair" size={15} />{follow ? 'Siguiendo' : 'Seguir unidad'}</button
          >
          {#if selected.vehicle}
            <a href="/fleet"><FleetIcon name="truck" size={15} />Ver en Flota</a>
          {/if}
        </div>
      </section>
    {/if}
  </div>
</div>

<style>
  .tracking-workspace {
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
    margin-bottom: 16px;
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
  }
  .mode-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    border: 1px solid rgb(var(--border));
    border-radius: 6px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .mode-badge > span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: rgb(var(--foreground-muted));
  }
  .mode-badge.live {
    color: rgb(var(--success));
    border-color: rgb(var(--success) / 0.3);
  }
  .mode-badge.live > span {
    background: rgb(var(--success));
    animation: pulse 1.6s ease-in-out infinite;
  }
  .heading-meta span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .banner {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    padding: 9px 12px;
    border: 1px solid rgb(var(--warning) / 0.3);
    border-radius: 8px;
    background: rgb(var(--warning) / 0.08);
    font-size: 12px;
  }
  .tracking-shell {
    position: relative;
    height: max(560px, calc(100dvh - 190px));
    overflow: hidden;
    border: 1px solid rgb(var(--border));
    border-radius: 14px;
  }
  .device-panel {
    position: absolute;
    top: 12px;
    left: 12px;
    bottom: 12px;
    z-index: 2;
    display: flex;
    flex-direction: column;
    width: 330px;
    overflow: hidden;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface) / 0.97);
    box-shadow: 0 8px 28px rgb(0 0 0 / 0.18);
    backdrop-filter: blur(6px);
  }
  .panel-search {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 12px 12px 8px;
    padding: 0 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 9px;
    color: rgb(var(--foreground-muted));
  }
  .panel-search input {
    flex: 1;
    min-width: 0;
    height: 36px;
    border: 0;
    background: transparent;
    color: rgb(var(--foreground));
    font-size: 12px;
    outline: none;
  }
  .panel-search:focus-within {
    border-color: rgb(var(--primary));
  }
  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 0 12px 10px;
    border-bottom: 1px solid rgb(var(--border));
  }
  .filters button {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 8px;
    border: 1px solid rgb(var(--border));
    border-radius: 999px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .filters button span {
    font-variant-numeric: tabular-nums;
    opacity: 0.8;
  }
  .filters button.active {
    border-color: rgb(var(--foreground));
    background: rgb(var(--foreground));
    color: rgb(var(--surface));
  }
  .device-list {
    flex: 1;
    overflow-y: auto;
    margin: 0;
    padding: 6px;
    list-style: none;
    scrollbar-width: thin;
  }
  .device-row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 9px 8px;
    border-radius: 9px;
    text-align: left;
  }
  .device-row:hover {
    background: rgb(var(--surface-hover));
  }
  .device-row.selected {
    background: rgb(var(--primary) / 0.1);
  }
  .device-avatar {
    display: grid;
    place-items: center;
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    color: #fff;
    background: rgb(22 163 74);
  }
  .device-avatar.stopped {
    background: rgb(217 119 6);
  }
  .device-avatar.offline {
    background: rgb(113 113 122);
  }
  .device-main {
    display: grid;
    gap: 3px;
    min-width: 0;
    flex: 1;
  }
  .device-main strong {
    font-size: 13px;
    font-weight: 600;
  }
  .device-main span,
  .device-side span:last-child {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .device-side {
    display: grid;
    gap: 3px;
    justify-items: end;
    flex-shrink: 0;
  }
  .status-text {
    font-size: 11px;
    font-weight: 550;
  }
  .status-text.moving {
    color: rgb(var(--success));
  }
  .status-text.stopped {
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
  .status-text.offline {
    color: rgb(var(--foreground-muted));
  }
  .empty {
    padding: 28px 12px;
    text-align: center;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .panel-note {
    display: flex;
    gap: 6px;
    align-items: flex-start;
    padding: 10px 12px;
    border-top: 1px solid rgb(var(--border));
    font-size: 11px;
    line-height: 1.5;
    color: rgb(var(--foreground-muted));
  }
  .vehicle-card {
    position: absolute;
    left: 354px;
    bottom: 16px;
    z-index: 2;
    width: 340px;
    padding: 16px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
    box-shadow: 0 10px 32px rgb(0 0 0 / 0.22);
    animation: rise 160ms ease-out;
  }
  .vehicle-card header {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }
  .vehicle-card h2 {
    font-size: 18px;
    font-weight: 650;
    letter-spacing: -0.5px;
  }
  .vehicle-card header p {
    margin-top: 3px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .icon-button {
    display: grid;
    place-items: center;
    flex-shrink: 0;
    width: 30px;
    height: 30px;
    border: 1px solid rgb(var(--border));
    border-radius: 50%;
    color: rgb(var(--foreground-muted));
  }
  .icon-button:hover {
    background: rgb(var(--surface-hover));
  }
  .card-status {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 12px;
    font-size: 12px;
  }
  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    background: rgb(var(--success) / 0.12);
    color: rgb(var(--success));
  }
  .status-pill > span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }
  .status-pill.stopped {
    background: rgb(var(--warning) / 0.12);
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
  .status-pill.offline {
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground-muted));
  }
  .route-to {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-weight: 550;
  }
  .stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px 10px;
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid rgb(var(--border));
  }
  dt {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  dd {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 3px;
    font-size: 13px;
    font-weight: 600;
  }
  .coords {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 12px;
    font:
      11px 'Geist Mono',
      monospace;
    color: rgb(var(--foreground-muted));
  }
  .card-actions {
    display: flex;
    gap: 8px;
    margin-top: 14px;
  }
  .card-actions > * {
    display: inline-flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    gap: 6px;
    height: 34px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    font-size: 12px;
    font-weight: 550;
  }
  .card-actions > *:hover {
    background: rgb(var(--surface-hover));
  }
  .card-actions button.active {
    border-color: rgb(var(--primary));
    background: rgb(var(--primary) / 0.1);
    color: rgb(var(--primary));
  }
  button:focus-visible,
  a:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 2px;
  }
  @keyframes pulse {
    50% {
      opacity: 0.35;
    }
  }
  @keyframes rise {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
  }
  @media (max-width: 900px) {
    .tracking-workspace {
      padding: 16px;
    }
    .tracking-shell {
      height: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
      overflow: visible;
      border: 0;
    }
    .tracking-shell > :global(.tracking-map) {
      position: relative;
      height: 420px;
      border: 1px solid rgb(var(--border));
      border-radius: 14px;
      overflow: hidden;
    }
    .vehicle-card {
      position: static;
      order: 1;
      width: auto;
      box-shadow: none;
    }
    .device-panel {
      position: static;
      order: 2;
      width: auto;
      max-height: 360px;
      box-shadow: none;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .mode-badge.live > span,
    .vehicle-card {
      animation: none;
    }
  }
</style>
