<script lang="ts">
  import type { GeofenceOut, SiteOut } from '$lib/api/client';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import TrackingMap from './TrackingMap.svelte';
  import { STATUS_LABELS, timeAgo, type TrackedVehicle } from './tracking';
  import { assignPane, initialAssignments, reconcileAssignments } from './split-view';

  type Point = [number, number];
  let {
    count,
    vehicles,
    assignments = $bindable<(string | null)[]>([]),
    preferred = null,
    trails = {},
    simRoutes = {},
    pilots = {},
    sites = [],
    geofences = [],
    logo = null,
    now,
    loading = false
  }: {
    count: 2 | 3 | 4;
    vehicles: TrackedVehicle[];
    assignments?: (string | null)[];
    preferred?: string | null;
    trails?: Record<string, Point[]>;
    simRoutes?: Record<string, Point[]>;
    pilots?: Record<string, { lngLat: Point; course: number }>;
    sites?: SiteOut[];
    geofences?: GeofenceOut[];
    logo?: string | null;
    now: number;
    loading?: boolean;
  } = $props();

  let following = $state([true, true, true, true]);
  let expanded = $state<number | null>(null);
  let expandButtons = $state<(HTMLButtonElement | null)[]>([null, null, null, null]);
  const keys = $derived(vehicles.map((vehicle) => vehicle.key));
  const panes = $derived(
    assignments.map((key) => vehicles.find((vehicle) => vehicle.key === key) ?? null)
  );
  // Stable arrays: the once-per-second text clock must not resync all map markers.
  const mapVehicles = $derived(panes.map((vehicle) => (vehicle ? [vehicle] : [])));
  const visibleIndexes = $derived(Array.from({ length: count }, (_, index) => index));

  $effect(() => {
    if (!assignments.length) {
      if (vehicles.length) assignments = initialAssignments(keys, preferred);
      return;
    }
    if (loading) return;
    const next = reconcileAssignments(assignments, keys);
    if (next.some((key, i) => key !== assignments[i])) assignments = next;
  });

  $effect(() => {
    if (expanded !== null && expanded >= count) expanded = null;
  });

  function choose(index: number, key: string) {
    assignments = assignPane(assignments, index, key || null, keys, count);
    following[index] = true;
  }

  function restoreGrid() {
    const previous = expanded;
    expanded = null;
    if (previous !== null) requestAnimationFrame(() => expandButtons[previous]?.focus());
  }
</script>

<svelte:window
  onkeydown={(event) => {
    if (event.key === 'Escape' && expanded !== null) restoreGrid();
  }}
/>

<div
  class="split-grid"
  class:three={count === 3}
  class:two={count === 2}
  class:expanded={expanded !== null}
  aria-label={`Seguimiento en ${count} vistas`}
>
  {#each visibleIndexes as index (index)}
    {@const vehicle = panes[index] ?? null}
    {@const otherAvailable = vehicles.some(
      (item) => !assignments.slice(0, count).includes(item.key)
    )}
    <section
      class="tracking-pane"
      class:primary={index === 0}
      hidden={expanded !== null && expanded !== index}
      aria-label={`Vista ${index + 1}${vehicle ? `: ${vehicle.name}` : ': sin vehículo'}`}
    >
      <header class="pane-header">
        <div class="pane-controls">
          <span class="pane-number" aria-hidden="true">0{index + 1}</span>
          <select
            aria-label={`Vehículo de la vista ${index + 1}`}
            value={assignments[index] ?? ''}
            disabled={loading || !vehicles.length}
            onchange={(event) => choose(index, event.currentTarget.value)}
          >
            <option value="">Seleccionar vehículo</option>
            {#each vehicles as option (option.key)}
              {@const occupied = assignments.findIndex((key) => key === option.key)}
              <option
                value={option.key}
                disabled={occupied !== -1 && occupied !== index && occupied < count}
              >
                {option.name}{option.vehicle?.plate
                  ? ` · ${option.vehicle.plate}`
                  : ''}{occupied !== -1 && occupied !== index && occupied < count
                  ? ` (vista ${occupied + 1})`
                  : ''}
              </option>
            {/each}
          </select>
          <button
            type="button"
            class="pane-tool"
            class:active={vehicle && following[index]}
            disabled={!vehicle}
            aria-pressed={!!vehicle && following[index]}
            aria-label={`${vehicle && following[index] ? 'Pausar seguimiento' : 'Seguir vehículo'} en vista ${index + 1}`}
            title={vehicle && following[index]
              ? 'Pausar seguimiento para explorar el mapa'
              : 'Seguir vehículo'}
            onclick={() => (following[index] = !following[index])}
            ><FleetIcon name="crosshair" size={16} /></button
          >
          <button
            type="button"
            class="pane-tool"
            bind:this={expandButtons[index]}
            disabled={!vehicle && expanded !== index}
            aria-label={expanded === index ? 'Restaurar cuadrícula' : `Ampliar vista ${index + 1}`}
            aria-pressed={expanded === index}
            title={expanded === index ? 'Restaurar cuadrícula' : 'Ampliar esta vista'}
            onclick={() => {
              if (expanded === index) restoreGrid();
              else expanded = index;
            }}><FleetIcon name={expanded === index ? 'grid' : 'fit'} size={16} /></button
          >
        </div>
        <div class="pane-summary">
          {#if vehicle}
            <span class="unit-status {vehicle.status}"
              ><span></span>{STATUS_LABELS[vehicle.status]}</span
            >
            {#if vehicle.simulated}<span class="simulation">SIM</span>{/if}
            <strong>{Math.round(vehicle.speedKmh)} <span>km/h</span></strong>
            <span class="follow-state"
              >{following[index]
                ? vehicle.status === 'offline'
                  ? 'Última posición'
                  : 'Siguiendo'
                : 'Explorando'}</span
            >
          {:else}
            <span class="muted">{loading ? 'Cargando unidades…' : 'Sin unidad asignada'}</span>
          {/if}
        </div>
      </header>
      <div class="pane-map">
        {#if vehicle}
          {#key vehicle.key}
            <TrackingMap
              vehicles={mapVehicles[index] ?? []}
              selectedKey={vehicle.key}
              follow={following[index]}
              trail={trails[vehicle.key] ?? []}
              simRoutes={simRoutes[vehicle.key] ? { [vehicle.key]: simRoutes[vehicle.key]! } : {}}
              {pilots}
              {sites}
              {geofences}
              {logo}
              compact
              onselect={() => {}}
              oninteract={() => (following[index] = false)}
            />
          {/key}
        {:else}
          <div class="pane-empty">
            <span class="empty-icon"><FleetIcon name="truck" size={24} /></span>
            <h3>
              {loading
                ? 'Buscando posiciones GPS'
                : otherAvailable
                  ? 'Elige un vehículo'
                  : 'Esperando otra unidad'}
            </h3>
            <p>
              {otherAvailable
                ? 'Usa el selector de esta vista para seguir una unidad.'
                : 'Las unidades que reporten posición estarán disponibles aquí.'}
            </p>
          </div>
        {/if}
      </div>
      <footer class="pane-footer">
        {#if vehicle}
          <span class="driver" title={vehicle.vehicle?.driver_name ?? 'Sin conductor asignado'}
            ><FleetIcon name="truck" size={13} />{vehicle.vehicle?.driver_name ??
              'Sin conductor asignado'}</span
          >
          <span title="Última posición recibida">Señal {timeAgo(vehicle.fixTime, now)}</span>
        {:else}
          <span>Vista {index + 1} de {count}</span><span>GPS</span>
        {/if}
      </footer>
    </section>
  {/each}
</div>

<style>
  .split-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-rows: repeat(2, minmax(0, 1fr));
    gap: 10px;
    flex: 1;
    min-height: 0;
    padding: 0 12px 12px;
  }
  .split-grid.two {
    grid-template-rows: minmax(0, 1fr);
  }
  .split-grid.three .primary {
    grid-row: span 2;
  }
  .split-grid.expanded {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(0, 1fr);
  }
  .split-grid.expanded .primary {
    grid-row: auto;
  }
  .tracking-pane {
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    border: 1px solid rgb(var(--border));
    border-radius: 10px;
    background: rgb(var(--surface));
  }
  .tracking-pane[hidden] {
    display: none;
  }
  .pane-header {
    flex-shrink: 0;
    padding: 8px 10px 7px;
    border-bottom: 1px solid rgb(var(--border));
  }
  .pane-controls {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .pane-number {
    flex-shrink: 0;
    color: rgb(var(--foreground-muted));
    font-size: 11px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  select {
    flex: 1;
    min-width: 0;
    height: 36px;
    padding: 0 24px 0 6px;
    overflow: hidden;
    text-overflow: ellipsis;
    border: 1px solid transparent;
    border-radius: 6px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 13px;
    font-weight: 650;
    cursor: pointer;
  }
  select:hover:not(:disabled) {
    border-color: rgb(var(--border));
    background: rgb(var(--surface-hover));
  }
  select:disabled {
    color: rgb(var(--foreground-muted));
    cursor: default;
  }
  .pane-tool {
    display: grid;
    place-items: center;
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    border: 1px solid rgb(var(--border));
    border-radius: 7px;
    color: rgb(var(--foreground-muted));
  }
  .pane-tool:hover:not(:disabled) {
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground));
  }
  .pane-tool.active {
    border-color: rgb(var(--primary) / 0.3);
    color: rgb(var(--primary));
    background: rgb(var(--primary) / 0.08);
  }
  .pane-tool:disabled {
    opacity: 0.4;
    cursor: default;
  }
  button:focus-visible,
  select:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 2px;
  }
  .pane-summary {
    display: flex;
    align-items: center;
    gap: 9px;
    min-height: 23px;
    padding-left: 22px;
    font-size: 11px;
  }
  .pane-summary strong {
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }
  .pane-summary strong span {
    font-size: 10px;
    font-weight: 400;
    color: rgb(var(--foreground-muted));
  }
  .unit-status {
    display: flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
    color: rgb(var(--foreground-muted));
  }
  .unit-status > span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }
  .unit-status.moving {
    color: rgb(var(--success));
  }
  .unit-status.stopped {
    color: rgb(var(--foreground));
  }
  .unit-status.stopped > span {
    background: rgb(var(--warning));
  }
  .simulation {
    padding: 1px 4px;
    border-radius: 3px;
    color: rgb(var(--foreground-muted));
    background: rgb(var(--surface-hover));
    font-size: 9px;
    font-weight: 750;
  }
  .follow-state {
    margin-left: auto;
    color: rgb(var(--foreground-muted));
    font-size: 10px;
  }
  .pane-map {
    position: relative;
    flex: 1;
    min-height: 140px;
    background: rgb(var(--surface-muted));
    overflow: hidden;
  }
  .pane-empty {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
    text-align: center;
  }
  .empty-icon {
    display: grid;
    place-items: center;
    width: 48px;
    height: 48px;
    margin-bottom: 12px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    color: rgb(var(--foreground-muted));
    background: rgb(var(--surface));
  }
  .pane-empty h3 {
    font-size: 13px;
    font-weight: 600;
  }
  .pane-empty p {
    max-width: 240px;
    margin-top: 5px;
    font-size: 12px;
    line-height: 1.5;
    color: rgb(var(--foreground-muted));
  }
  .pane-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-shrink: 0;
    min-height: 30px;
    padding: 5px 10px;
    border-top: 1px solid rgb(var(--border));
    font-size: 10px;
    color: rgb(var(--foreground-muted));
  }
  .driver {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pane-footer > span:last-child {
    flex-shrink: 0;
  }
  .muted {
    color: rgb(var(--foreground-muted));
  }
  @media (max-width: 700px) {
    .split-grid,
    .split-grid.two,
    .split-grid.expanded {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: none;
      grid-auto-rows: minmax(340px, 52dvh);
      flex: none;
    }
    .split-grid.three .primary {
      grid-row: auto;
    }
    .pane-tool {
      width: 40px;
      height: 40px;
    }
  }
</style>
