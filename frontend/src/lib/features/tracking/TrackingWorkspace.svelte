<script lang="ts">
  import { onMount } from 'svelte';
  import { api, type GeofenceOut } from '$lib/api/client';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { demoRoute, demoSnapshot } from './demo';
  import EventsPanel from './EventsPanel.svelte';
  import { demoEvents, demoLiveEvent, fromTraccarEvents, type TrackingEvent } from './events';
  import GeofencePanel from './GeofencePanel.svelte';
  import {
    DEMO_GEOFENCES,
    distanceM,
    draftRing,
    draftShape,
    shapeRing,
    type DraftKind,
    type GeofenceDraft
  } from './geofences';
  import TrackingMap from './TrackingMap.svelte';
  import TransfersPanel from './TransfersPanel.svelte';
  import {
    demoTransferTracks,
    formatClock,
    formatDistance,
    fromApiSummary,
    fromApiTrack,
    type TransferSummary,
    type TransferTrack
  } from './transfers';
  import { page } from '$app/state';
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
  type Tab = 'units' | 'transfers' | 'geofences' | 'events';
  const TRANSFERS_POLL_MS = 30000;
  const TRACK_POLL_MS = 10000;

  const LIVE_POLL_MS = 5000;
  const EVENTS_POLL_MS = 15000;
  const DEMO_TICK_MS = 1000;
  const DEMO_EVENT_EVERY_MS = 45000;
  const TOAST_MS = 7000;
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

  let tab = $state<Tab>('units');
  let liveTransfers = $state<TransferSummary[]>([]);
  let transfersLoading = $state(false);
  let transferError = $state<string | null>(null);
  let selectedTransferId = $state<string | null>(null);
  let liveTrack = $state<TransferTrack | null>(null);

  const transferList = $derived<(TransferSummary | TransferTrack)[]>(
    mode === 'demo' ? demoTransferTracks(vehicles, now) : liveTransfers
  );
  const activeTrack = $derived.by<TransferTrack | null>(() => {
    if (!selectedTransferId) return null;
    if (mode === 'demo')
      return (
        (transferList as TransferTrack[]).find((item) => item.id === selectedTransferId) ?? null
      );
    return liveTrack?.id === selectedTransferId ? liveTrack : null;
  });
  const endpoints = $derived(
    activeTrack
      ? {
          origin: activeTrack.origin.point
            ? { at: activeTrack.origin.point, label: activeTrack.origin.branch }
            : null,
          destination: activeTrack.destination.point
            ? { at: activeTrack.destination.point, label: activeTrack.destination.branch }
            : null
        }
      : null
  );
  let mapView = $state<{ fitRing: (ring: [number, number][]) => void }>();
  let geofences = $state<GeofenceOut[]>([]);
  let geofenceError = $state<string | null>(null);
  let highlightedGeofence = $state<number | null>(null);
  let draft = $state<GeofenceDraft | null>(null);
  let savingGeofence = $state(false);
  let events = $state<TrackingEvent[]>([]);
  let unread = $state(0);
  let focusedEvent = $state<TrackingEvent | null>(null);
  let toasts = $state<TrackingEvent[]>([]);
  let seenEventIds = new Set<string>();
  let eventsPrimed = false;

  const canManageGeofences = $derived(
    mode === 'demo' || permissions.hasPermission('tracking:geofences')
  );
  const draftPreview = $derived(
    draft ? { ring: draftRing(draft), vertices: draft.vertices } : null
  );
  const focusPoint = $derived(
    focusedEvent && focusedEvent.latitude !== null && focusedEvent.longitude !== null
      ? {
          key: focusedEvent.id,
          at: [focusedEvent.longitude, focusedEvent.latitude] as [number, number]
        }
      : null
  );

  const filters: { id: Filter; label: string }[] = [
    { id: 'all', label: 'Todos' },
    { id: 'moving', label: 'En movimiento' },
    { id: 'stopped', label: 'Detenidos' },
    { id: 'offline', label: 'Sin señal' }
  ];

  const counts = $derived(
    vehicles.reduce((acc, vehicle) => ({ ...acc, [vehicle.status]: acc[vehicle.status] + 1 }), {
      all: vehicles.length,
      moving: 0,
      stopped: 0,
      offline: 0
    } as Record<Filter, number>)
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
        if (mode !== 'live') {
          trails = {};
          mode = 'live';
          loadTransfers();
          loadTrack();
          resetEvents();
          loadGeofences();
          pollEvents();
        }
        apply(fromTraccar(snapshot.devices));
      } else if (mode !== 'demo') {
        enterDemo();
      }
    } catch {
      if (signal.aborted) return;
      liveError =
        mode === 'live'
          ? 'Se perdió la conexión con el servidor GPS. Reintentando…'
          : 'No se pudo conectar con el servidor GPS. Mostrando la demostración.';
      if (mode === 'loading') enterDemo();
    } finally {
      polling = false;
    }
  }

  function enterDemo() {
    mode = 'demo';
    trails = {};
    resetEvents();
    geofences = DEMO_GEOFENCES.map((geofence) => ({ ...geofence }));
    receiveEvents(demoEvents(Date.now()));
  }

  function resetEvents() {
    events = [];
    toasts = [];
    unread = 0;
    seenEventIds = new Set();
    eventsPrimed = false;
  }

  /** Agrega eventos nuevos; los que llegan después de la primera carga se notifican. */
  function receiveEvents(incoming: TrackingEvent[]) {
    const initial = !eventsPrimed;
    eventsPrimed = true;
    const fresh = incoming.filter((event) => !seenEventIds.has(event.id));
    if (!fresh.length) return;
    fresh.forEach((event) => seenEventIds.add(event.id));
    events = [...fresh, ...events]
      .sort((a, b) => b.time.getTime() - a.time.getTime())
      .slice(0, 200);
    if (initial) return;
    if (tab !== 'events') unread += fresh.length;
    for (const event of fresh.slice(0, 3)) {
      toasts = [event, ...toasts].slice(0, 3);
      setTimeout(() => (toasts = toasts.filter((toast) => toast.id !== event.id)), TOAST_MS);
    }
  }

  async function pollEvents(signal?: AbortSignal) {
    if (mode !== 'live') return;
    try {
      receiveEvents(fromTraccarEvents(await api.tracking.events(24, signal)));
    } catch {
      // Los eventos son complementarios; el banner de conexión ya avisa si Traccar cae.
    }
  }

  async function loadGeofences() {
    try {
      geofences = await api.tracking.geofences();
      geofenceError = null;
    } catch {
      geofenceError = 'No se pudieron cargar las geocercas.';
    }
  }

  function startDraw(kind: DraftKind) {
    draft = { kind, vertices: [], radiusM: 500 };
    geofenceError = null;
    select(null);
  }

  function addDraftPoint(point: [number, number]) {
    if (!draft) return;
    if (draft.kind === 'circle') {
      if (!draft.vertices.length) draft = { ...draft, vertices: [point] };
      else draft = { ...draft, radiusM: Math.max(20, distanceM(draft.vertices[0]!, point)) };
      return;
    }
    const last = draft.vertices[draft.vertices.length - 1];
    // El doble clic para cerrar también dispara clics sueltos; se ignoran puntos repetidos.
    if (last && distanceM(last, point) < 3) return;
    draft = { ...draft, vertices: [...draft.vertices, point] };
  }

  function undoDraftPoint() {
    if (draft) draft = { ...draft, vertices: draft.vertices.slice(0, -1) };
  }

  async function saveGeofence(data: {
    name: string;
    description: string;
    speedLimit: number | null;
  }) {
    const shape = draft && draftShape(draft);
    if (!shape) return;
    const payload = {
      name: data.name,
      description: data.description || null,
      shape,
      speed_limit_kmh: data.speedLimit
    };
    if (mode === 'demo') {
      geofences = [...geofences, { ...payload, id: -(Date.now() % 1_000_000) - 10 }];
      draft = null;
      return;
    }
    savingGeofence = true;
    try {
      const created = await api.tracking.createGeofence(payload);
      geofences = [...geofences, created];
      draft = null;
      geofenceError = null;
    } catch {
      geofenceError = 'No se pudo guardar la geocerca. Revisa la conexión con el servidor GPS.';
    } finally {
      savingGeofence = false;
    }
  }

  async function deleteGeofence(geofence: GeofenceOut) {
    if (mode === 'live') {
      try {
        await api.tracking.deleteGeofence(geofence.id);
      } catch {
        geofenceError = 'No se pudo eliminar la geocerca.';
        return;
      }
    }
    geofences = geofences.filter((item) => item.id !== geofence.id);
    if (highlightedGeofence === geofence.id) highlightedGeofence = null;
  }

  function focusGeofence(geofence: GeofenceOut) {
    highlightedGeofence = geofence.id;
    mapView?.fitRing(shapeRing(geofence.shape));
  }

  function focusEvent(event: TrackingEvent) {
    // El punto del evento se muestra solo; la tarjeta de la unidad lo taparía.
    select(null);
    focusedEvent = event;
  }

  async function loadTransfers(signal?: AbortSignal) {
    if (mode !== 'live') return;
    transfersLoading = true;
    try {
      liveTransfers = (await api.tracking.transfers(signal)).map(fromApiSummary);
      transferError = null;
    } catch {
      if (!signal?.aborted) transferError = 'No se pudieron consultar los traslados.';
    } finally {
      transfersLoading = false;
    }
  }

  async function loadTrack(signal?: AbortSignal) {
    if (mode !== 'live' || !selectedTransferId) return;
    const id = selectedTransferId;
    try {
      const track = fromApiTrack(await api.tracking.transferTrack(id, signal));
      if (selectedTransferId === id) liveTrack = track;
    } catch {
      if (!signal?.aborted) transferError = 'No se pudo consultar el recorrido del traslado.';
    }
  }

  let fittedTransfer: string | null = null;
  $effect(() => {
    if (!activeTrack || fittedTransfer === activeTrack.id) return;
    const ring = [
      ...activeTrack.route,
      ...[activeTrack.origin.point, activeTrack.destination.point].filter(
        (point): point is [number, number] => point !== null
      )
    ];
    if (!ring.length) return;
    fittedTransfer = activeTrack.id;
    mapView?.fitRing(ring);
  });

  $effect(() => {
    // Resalta y permite seguir la unidad del traslado sin abrir su tarjeta.
    if (!activeTrack?.vehicleCode) return;
    const vehicle = vehicles.find((item) => item.name === activeTrack.vehicleCode);
    if (vehicle && selectedKey !== vehicle.key) selectedKey = vehicle.key;
  });

  $effect(() => {
    // Un traslado pedido por URL no existe en la demostración.
    if (mode === 'demo' && selectedTransferId && !activeTrack) selectTransfer(null);
  });

  function selectTransfer(id: string | null) {
    selectedTransferId = id;
    liveTrack = null;
    fittedTransfer = null;
    transferError = null;
    if (!id) {
      select(null);
      return;
    }
    focusedEvent = null;
    loadTrack();
  }

  function openTab(next: Tab) {
    tab = next;
    if (next === 'transfers') loadTransfers();
    else if (selectedTransferId) selectTransfer(null);
    if (next === 'events') unread = 0;
    if (next !== 'geofences') {
      draft = null;
      highlightedGeofence = null;
    }
    if (next !== 'events') focusedEvent = null;
  }

  onMount(() => {
    const controller = new AbortController();
    pollLive(controller.signal);
    const livePoll = setInterval(() => pollLive(controller.signal), LIVE_POLL_MS);
    const eventsPoll = setInterval(() => pollEvents(controller.signal), EVENTS_POLL_MS);
    let demoSequence = 0;
    const demoEventsTimer = setInterval(() => {
      if (mode === 'demo') receiveEvents([demoLiveEvent(demoSequence++, Date.now())]);
    }, DEMO_EVENT_EVERY_MS);
    const transfersPoll = setInterval(() => {
      if (tab === 'transfers') loadTransfers(controller.signal);
    }, TRANSFERS_POLL_MS);
    const trackPoll = setInterval(() => loadTrack(controller.signal), TRACK_POLL_MS);
    const requested = page.url.searchParams.get('transfer');
    if (requested) {
      tab = 'transfers';
      selectedTransferId = requested;
    }
    const tick = setInterval(() => {
      now = Date.now();
      if (mode === 'demo') apply(demoSnapshot(now));
    }, DEMO_TICK_MS);
    return () => {
      controller.abort();
      clearInterval(livePoll);
      clearInterval(eventsPoll);
      clearInterval(demoEventsTimer);
      clearInterval(tick);
      clearInterval(transfersPoll);
      clearInterval(trackPoll);
    };
  });

  function select(key: string | null) {
    selectedKey = key;
    if (!key) follow = false;
  }
</script>

<svelte:window
  onkeydown={(event) => {
    if (event.key !== 'Escape') return;
    if (draft) draft = null;
    else if (focusedEvent) focusedEvent = null;
    else if (selectedTransferId) selectTransfer(null);
    else if (selectedKey) select(null);
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
        Ubicación en tiempo real de las unidades de {company.active?.commercial_name ??
          'tu empresa'}.
      </p>
    </div>
    <div class="heading-meta">
      {#if lastSync}<span
          ><FleetIcon name="refresh" size={14} /> Actualizado {timeAgo(lastSync, now)}</span
        >{/if}
    </div>
  </header>

  {#if liveError}
    <div class="banner" role="status"><FleetIcon name="alert" size={15} />{liveError}</div>
  {/if}

  <div class="tracking-shell">
    <TrackingMap
      bind:this={mapView}
      vehicles={visible}
      {selectedKey}
      {follow}
      trail={activeTrack ? activeTrack.trail : selectedKey ? (trails[selectedKey] ?? []) : []}
      plannedRoute={activeTrack ? activeTrack.route : plannedRoute}
      {endpoints}
      {geofences}
      {highlightedGeofence}
      draft={draftPreview}
      drawing={draft !== null}
      {focusPoint}
      onselect={(key) => {
        if (activeTrack && key === null) return;
        if (activeTrack) selectTransfer(null);
        select(key);
        focusedEvent = null;
      }}
      ondrawpoint={addDraftPoint}
    />

    {#if toasts.length}
      <div class="toasts" aria-live="polite">
        {#each toasts as toast (toast.id)}
          <button
            type="button"
            class="toast {toast.tone}"
            onclick={() => {
              openTab('events');
              focusEvent(toast);
              toasts = toasts.filter((item) => item.id !== toast.id);
            }}
          >
            <FleetIcon name="alert" size={15} />
            <span
              ><strong>{toast.title}</strong>{toast.vehicleName}{toast.detail
                ? ` · ${toast.detail}`
                : ''}</span
            >
          </button>
        {/each}
      </div>
    {/if}

    <aside class="device-panel" aria-label="Seguimiento de unidades">
      <div class="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'units'}
          class:active={tab === 'units'}
          onclick={() => openTab('units')}>Unidades</button
        >
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'transfers'}
          class:active={tab === 'transfers'}
          onclick={() => openTab('transfers')}>Traslados</button
        >
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'geofences'}
          class:active={tab === 'geofences'}
          onclick={() => openTab('geofences')}>Geocercas</button
        >
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'events'}
          class:active={tab === 'events'}
          onclick={() => openTab('events')}
          >Eventos{#if unread}<span class="unread">{unread > 99 ? '99+' : unread}</span
            >{/if}</button
        >
      </div>
      {#if tab === 'geofences'}
        <GeofencePanel
          {geofences}
          canManage={canManageGeofences}
          {draft}
          saving={savingGeofence}
          error={geofenceError}
          highlighted={highlightedGeofence}
          onstartdraw={startDraw}
          onundo={undoDraftPoint}
          onradius={(radiusM) => draft && (draft = { ...draft, radiusM })}
          oncancel={() => (draft = null)}
          onsave={saveGeofence}
          ondelete={deleteGeofence}
          onfocus={focusGeofence}
        />
      {:else if tab === 'transfers'}
        <TransfersPanel
          transfers={transferList}
          selectedId={selectedTransferId}
          loading={transfersLoading}
          error={transferError}
          {now}
          onselect={(id) => selectTransfer(id === selectedTransferId ? null : id)}
        />
      {:else if tab === 'events'}
        <EventsPanel {events} {now} focusedId={focusedEvent?.id ?? null} onfocus={focusEvent} />
      {:else}
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
              onclick={() => (filter = item.id)}>{item.label}<span>{counts[item.id]}</span></button
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
                <span class="device-avatar {vehicle.status}"
                  ><FleetIcon name="truck" size={17} /></span
                >
                <span class="device-main">
                  <strong>{vehicle.name}</strong>
                  <span
                    >{vehicle.vehicle
                      ? `${vehicle.vehicle.plate} · ${vehicle.vehicle.driver}`
                      : 'Dispositivo GPS'}</span
                  >
                </span>
                <span class="device-side">
                  <span class="status-text {vehicle.status}">{STATUS_LABELS[vehicle.status]}</span>
                  <span
                    >{vehicle.status === 'moving'
                      ? `${Math.round(vehicle.speedKmh)} km/h`
                      : timeAgo(vehicle.fixTime, now)}</span
                  >
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
      {/if}
      {#if mode === 'demo'}
        <p class="panel-note">
          <FleetIcon name="info" size={13} />Posiciones simuladas. Configura Traccar para ver tus
          unidades reales.
        </p>
      {/if}
    </aside>

    {#if selectedTransferId}
      {@const track = activeTrack}
      <section class="vehicle-card transfer-card" aria-label="Recorrido del traslado">
        <header>
          <div>
            <h2>{track?.code ?? 'Cargando traslado…'}</h2>
            {#if track}<p>
                {track.vehicleCode ?? 'Sin vehículo asignado'}{track.vehicleName
                  ? ` · ${track.vehicleName}`
                  : ''}
              </p>{/if}
          </div>
          <button
            type="button"
            class="icon-button"
            aria-label="Cerrar recorrido"
            onclick={() => selectTransfer(null)}><FleetIcon name="close" size={16} /></button
          >
        </header>
        {#if track}
          <ol class="legs">
            <li><span class="leg-pin">A</span>{track.origin.branch}</li>
            <li><span class="leg-pin destination">B</span>{track.destination.branch}</li>
          </ol>
          {#if track.arrived}
            <p class="flag success">
              <FleetIcon name="check" size={14} />Llegó a la sucursal de destino
            </p>
          {:else if track.offRoute}
            <p class="flag danger"><FleetIcon name="alert" size={14} />Fuera de la ruta planeada</p>
          {/if}
          <div class="progress-line">
            <span>Avance</span><strong>{Math.round(track.progress * 100)}%</strong>
          </div>
          <div class="progress-track"><span style:width="{track.progress * 100}%"></span></div>
          <dl class="stats">
            <div>
              <dt>Restante</dt>
              <dd>{formatDistance(track.remainingM)}</dd>
            </div>
            <div>
              <dt>Llegada est.</dt>
              <dd>{track.arrived ? 'Llegó' : formatClock(track.eta)}</dd>
            </div>
            <div>
              <dt>Velocidad</dt>
              <dd>{track.position ? `${Math.round(track.position.speedKmh)} km/h` : '—'}</dd>
            </div>
            <div>
              <dt>Salida</dt>
              <dd>{formatClock(track.dispatchedAt)}</dd>
            </div>
            <div>
              <dt>Distancia</dt>
              <dd>{formatDistance(track.distanceM)}</dd>
            </div>
            <div>
              <dt>Última señal</dt>
              <dd>{timeAgo(track.position?.fixTime ?? null, now)}</dd>
            </div>
          </dl>
          {#if !track.origin.point || !track.destination.point}
            <p class="note">
              Una de las sucursales no tiene coordenadas; regístralas para ver la ruta.
            </p>
          {:else if mode === 'live' && !track.gpsConfigured}
            <p class="note">
              El servidor GPS no está configurado; solo se muestra la ruta planeada.
            </p>
          {:else if mode === 'live' && !track.deviceFound}
            <p class="note">
              {track.vehicleCode
                ? `Ningún dispositivo de Traccar se llama “${track.vehicleCode}”. Usa el código del vehículo como nombre o identificador del GPS.`
                : 'El traslado no tiene vehículo asignado.'}
            </p>
          {:else if track.routeSource === 'straight'}
            <p class="note">Ruta aproximada en línea recta; el servicio de rutas no respondió.</p>
          {/if}
          <div class="card-actions">
            <button
              type="button"
              class:active={follow}
              aria-pressed={follow}
              disabled={!track.position}
              onclick={() => (follow = !follow)}
              ><FleetIcon name="crosshair" size={15} />{follow
                ? 'Siguiendo'
                : 'Seguir unidad'}</button
            >
            <a href="/transfers"><FleetIcon name="route" size={15} />Ver traslados</a>
          </div>
        {/if}
      </section>
    {:else if selected}
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
          <button
            type="button"
            class="icon-button"
            aria-label="Cerrar detalle"
            onclick={() => select(null)}><FleetIcon name="close" size={16} /></button
          >
        </header>
        <div class="card-status">
          <span class="status-pill {selected.status}"
            ><span></span>{STATUS_LABELS[selected.status]}</span
          >
          {#if selected.vehicle?.status === 'En ruta'}
            <span class="route-to"
              ><FleetIcon name="route" size={14} />{selected.vehicle.destination}</span
            >
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
            <dd>
              {selected.ignition === null ? '—' : selected.ignition ? 'Encendido' : 'Apagado'}
            </dd>
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
            ><FleetIcon name="crosshair" size={15} />{follow
              ? 'Siguiendo'
              : 'Seguir unidad'}</button
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
  .tabs {
    display: flex;
    gap: 2px;
    padding: 6px 6px 0;
    border-bottom: 1px solid rgb(var(--border));
  }
  .tabs button {
    display: inline-flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    gap: 5px;
    padding: 9px 4px 8px;
    border-bottom: 2px solid transparent;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .tabs button.active {
    border-bottom-color: rgb(var(--foreground));
    color: rgb(var(--foreground));
    font-weight: 600;
  }
  .unread {
    min-width: 18px;
    padding: 1px 5px;
    border-radius: 999px;
    background: rgb(var(--danger));
    color: #fff;
    font-size: 10px;
    font-weight: 700;
  }
  .toasts {
    position: absolute;
    top: 12px;
    left: 50%;
    z-index: 3;
    display: grid;
    gap: 8px;
    width: min(360px, calc(100% - 24px));
    transform: translateX(-50%);
  }
  .toast {
    display: flex;
    align-items: flex-start;
    gap: 9px;
    padding: 10px 12px;
    border: 1px solid rgb(var(--border));
    border-left: 4px solid rgb(var(--primary));
    border-radius: 10px;
    background: rgb(var(--surface));
    box-shadow: 0 10px 28px rgb(0 0 0 / 0.22);
    text-align: left;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
    animation: rise 160ms ease-out;
  }
  .toast strong {
    display: block;
    margin-bottom: 2px;
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  .toast.danger {
    border-left-color: rgb(var(--danger));
  }
  .toast.warning {
    border-left-color: rgb(var(--warning));
  }
  .toast.success {
    border-left-color: rgb(var(--success));
  }
  .toast.danger > :global(svg) {
    color: rgb(var(--danger));
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
  .transfer-card .legs {
    display: grid;
    gap: 6px;
    margin: 12px 0 0;
    padding: 0;
    list-style: none;
    font-size: 12px;
    font-weight: 550;
  }
  .transfer-card .legs li {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .leg-pin {
    display: grid;
    place-items: center;
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #0f172a;
    color: #fff;
    font-size: 10px;
    font-weight: 700;
  }
  .leg-pin.destination {
    background: #16a34a;
  }
  .flag {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 10px;
    padding: 7px 9px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
  }
  .flag.success {
    background: rgb(var(--success) / 0.12);
    color: rgb(var(--success));
  }
  .flag.danger {
    background: rgb(var(--danger) / 0.1);
    color: rgb(var(--danger));
  }
  .progress-line {
    display: flex;
    justify-content: space-between;
    margin-top: 12px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .progress-line strong {
    color: rgb(var(--foreground));
  }
  .progress-track {
    height: 6px;
    margin-top: 6px;
    overflow: hidden;
    border-radius: 6px;
    background: rgb(var(--border));
  }
  .progress-track span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: rgb(var(--primary));
    transition: width 600ms ease-out;
  }
  .note {
    margin-top: 10px;
    font-size: 11px;
    line-height: 1.5;
    color: rgb(var(--foreground-muted));
  }
  .card-actions button:disabled {
    opacity: 0.45;
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
