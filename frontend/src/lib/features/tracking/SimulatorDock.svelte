<script lang="ts">
  import { onMount } from 'svelte';
  import {
    api,
    type SimulationAction,
    type SimulationMode,
    type SimulationOut,
    type SimulatorOut
  } from '$lib/api/client';
  import {
    DRIVE_KEYS,
    DRIVE_SEND_MS,
    SIGNAL_PRESETS,
    SPEED_PRESETS,
    STOP_PRESETS,
    countdown,
    driveStep,
    formatDistance,
    inputFromKeys,
    progressOf,
    sessionKey,
    sessionStatus,
    typingTarget,
    type DriveInput,
    type DriveState
  } from './simulator';
  import type { TrackedVehicle } from './tracking';

  type LngLat = [number, number];

  let {
    vehicles = [],
    picking = $bindable(false),
    waypoints = $bindable<LngLat[]>([]),
    pilot = $bindable<{ key: string; lngLat: LngLat; course: number } | null>(null),
    routes = $bindable<Record<string, LngLat[]>>({}),
    onfocus
  }: {
    /** Unidades visibles en el mapa: el joystick parte de la posición mostrada. */
    vehicles?: TrackedVehicle[];
    /** El mapa está marcando puntos del recorrido. */
    picking?: boolean;
    waypoints?: LngLat[];
    /** Unidad manejada con el joystick: el mapa la dibuja sin esperar al servidor. */
    pilot?: { key: string; lngLat: LngLat; course: number } | null;
    /** Recorridos de las sesiones automáticas por unidad del mapa: se dibujan y la unidad los sigue. */
    routes?: Record<string, LngLat[]>;
    onfocus?: (key: string) => void;
  } = $props();

  const OPEN_KEY = 'tracking.simulator.open';
  const POLL_OPEN_MS = 2500;
  const POLL_CLOSED_MS = 15000;

  let info = $state<SimulatorOut | null>(null);
  let open = $state(false);
  let activeId = $state<string | null>(null);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let now = $state(Date.now());
  let confirmEnd = $state(false);

  // Formulario de una nueva sesión.
  let vehicleId = $state('');
  let mode = $state<SimulationMode>('route');
  let source = $state<'transfer' | 'points'>('points');
  let speed = $state(60);
  let snap = $state(true);

  const sessions = $derived(info?.sessions ?? []);
  const active = $derived(sessions.find((item) => item.id === activeId) ?? null);
  const busyVehicles = $derived(new Set(sessions.map((item) => item.vehicle_id)));
  const candidates = $derived(info?.vehicles ?? []);
  const chosen = $derived(candidates.find((item) => item.id === vehicleId) ?? null);
  const visible = $derived(!!info?.enabled && (info.can_simulate || sessions.length > 0));
  const canStart = $derived(
    !!chosen &&
      !busyVehicles.has(chosen.id) &&
      (mode === 'joystick' ||
        (source === 'transfer' ? !!chosen.transfer_id : waypoints.length >= 2))
  );

  $effect(() => {
    // Sin traslado en curso, el trayecto se marca en el mapa.
    if (chosen && !chosen.transfer_id && source === 'transfer') source = 'points';
  });

  $effect(() => {
    routes = Object.fromEntries(
      sessions.filter((item) => item.mode === 'route').map((item) => [sessionKey(item), item.route])
    );
  });

  $effect(() => {
    if (mode !== 'route' || source !== 'points' || active) picking = false;
  });

  function remember(value: boolean) {
    try {
      localStorage.setItem(OPEN_KEY, value ? '1' : '0');
    } catch {
      // Sin almacenamiento (modo privado): el panel simplemente no recuerda su estado.
    }
  }

  function toggle(value = !open) {
    open = value;
    remember(value);
    if (!value) {
      picking = false;
      stopDriving();
      return;
    }
    refresh();
    if (active?.mode === 'joystick' && active.can_control && !driving) startDriving(active);
  }

  function message(failure: unknown): string {
    return failure instanceof Error ? failure.message : 'No se pudo completar la acción.';
  }

  let loading = false;
  async function refresh(signal?: AbortSignal) {
    if (loading) return;
    loading = true;
    try {
      info = await api.tracking.simulator.state(signal);
      if (activeId && !info.sessions.some((item) => item.id === activeId)) {
        // La sesión terminó (por el usuario, por inactividad o al desactivar el simulador).
        activeId = null;
        stopDriving();
      }
      if (!vehicleId && info.vehicles.length) vehicleId = info.vehicles[0]!.id;
    } catch {
      // Se conservan los últimos datos; el siguiente ciclo vuelve a intentarlo.
    } finally {
      loading = false;
    }
  }

  async function start() {
    if (!chosen || busy) return;
    busy = true;
    error = null;
    try {
      const shown = vehicles.find((item) => item.vehicle?.id === chosen.id);
      const created = await api.tracking.simulator.start({
        vehicle_id: chosen.id,
        mode,
        speed_kmh: speed,
        ...(mode === 'joystick'
          ? { start: shown ? [shown.longitude, shown.latitude] : chosen.start }
          : source === 'transfer'
            ? { transfer_id: chosen.transfer_id }
            : { waypoints })
      });
      waypoints = [];
      picking = false;
      info = info ? { ...info, sessions: [...info.sessions, created] } : info;
      activate(created);
      onfocus?.(sessionKey(created));
    } catch (failure) {
      error = message(failure);
    } finally {
      busy = false;
    }
  }

  function activate(session: SimulationOut | null) {
    stopDriving();
    confirmEnd = false;
    error = null;
    activeId = session?.id ?? null;
    if (session) speed = Math.round(session.speed_kmh);
    if (session?.mode === 'joystick' && session.can_control) startDriving(session);
  }

  function replace(updated: SimulationOut) {
    if (!info) return;
    info = {
      ...info,
      sessions: info.sessions.map((item) => (item.id === updated.id ? updated : item))
    };
  }

  async function control(
    action: SimulationAction,
    extra: { minutes?: number; speed_kmh?: number } = {}
  ) {
    if (!active || busy) return;
    busy = true;
    error = null;
    try {
      replace(await api.tracking.simulator.control(active.id, action, extra));
    } catch (failure) {
      error = message(failure);
    } finally {
      busy = false;
    }
  }

  let speedTimer: ReturnType<typeof setTimeout> | undefined;
  function changeSpeed(value: number) {
    speed = value;
    if (!active || active.mode !== 'route') return;
    clearTimeout(speedTimer);
    speedTimer = setTimeout(() => control('speed', { speed_kmh: value }), 350);
  }

  async function end() {
    if (!active) return;
    if (!confirmEnd) {
      confirmEnd = true;
      return;
    }
    busy = true;
    try {
      await api.tracking.simulator.end(active.id);
      stopDriving();
      if (info) info = { ...info, sessions: info.sessions.filter((item) => item.id !== active.id) };
      activeId = null;
    } catch (failure) {
      error = message(failure);
    } finally {
      busy = false;
      confirmEnd = false;
    }
  }

  // ------------------------------------------------------------ joystick

  let drive: DriveState | null = null;
  let driving = $state<SimulationOut | null>(null);
  let shownSpeed = $state(0);
  let frame = 0;
  let lastFrame = 0;
  let lastSent = 0;
  let sentMoving = false;
  let sending = false;
  const pressed = new Set<string>();
  let pad = $state<DriveInput>({ throttle: 0, steer: 0 });
  let knob = $state({ x: 0, y: 0 });

  function startDriving(session: SimulationOut) {
    driving = session;
    drive = { lngLat: [session.longitude, session.latitude], course: session.course, speedKmh: 0 };
    lastFrame = performance.now();
    lastSent = 0;
    frame = requestAnimationFrame(loop);
  }

  function stopDriving() {
    cancelAnimationFrame(frame);
    if (driving && drive && drive.speedKmh > 0) {
      // Al soltar el control la unidad queda detenida donde está.
      drive.speedKmh = 0;
      void send(true);
    }
    driving = null;
    drive = null;
    pilot = null;
    pressed.clear();
    pad = { throttle: 0, steer: 0 };
    knob = { x: 0, y: 0 };
  }

  function currentInput(): DriveInput {
    const keys = inputFromKeys(pressed);
    return {
      throttle: keys.throttle !== 0 ? keys.throttle : pad.throttle,
      steer: keys.steer !== 0 ? keys.steer : pad.steer
    };
  }

  function loop(time: number) {
    if (!driving || !drive) return;
    const dt = Math.min(0.1, (time - lastFrame) / 1000);
    lastFrame = time;
    drive = driveStep(drive, currentInput(), dt, speed);
    shownSpeed = drive.speedKmh;
    pilot = { key: sessionKey(driving), lngLat: drive.lngLat, course: drive.course };
    const moving = drive.speedKmh > 0.5;
    if (time - lastSent >= DRIVE_SEND_MS && (moving || sentMoving)) {
      lastSent = time;
      void send(false);
    }
    frame = requestAnimationFrame(loop);
  }

  async function send(final: boolean) {
    if (!driving || !drive || (sending && !final)) return;
    sending = true;
    const state = drive;
    sentMoving = state.speedKmh > 0.5;
    try {
      const result = await api.tracking.simulator.drive(driving.id, {
        latitude: state.lngLat[1],
        longitude: state.lngLat[0],
        course: Math.round(state.course * 10) / 10 >= 360 ? 0 : Math.round(state.course * 10) / 10,
        speed_kmh: Math.round(state.speedKmh * 10) / 10,
        snap
      });
      if (result.snapped && drive)
        drive = { ...drive, lngLat: [result.longitude, result.latitude] };
      error = null;
    } catch (failure) {
      error = message(failure);
      // Si el servidor rechaza el salto, la unidad vuelve a la última posición aceptada.
      const server = sessions.find((item) => item.id === driving?.id);
      if (server && drive)
        drive = { ...drive, lngLat: [server.longitude, server.latitude], speedKmh: 0 };
    } finally {
      sending = false;
    }
  }

  function padPointer(event: PointerEvent, element: HTMLElement) {
    const rect = element.getBoundingClientRect();
    const radius = rect.width / 2;
    let x = event.clientX - rect.left - radius;
    let y = event.clientY - rect.top - radius;
    const length = Math.hypot(x, y);
    if (length > radius) {
      x = (x / length) * radius;
      y = (y / length) * radius;
    }
    knob = { x, y };
    pad = { throttle: -y / radius, steer: x / radius };
  }

  function releasePad() {
    knob = { x: 0, y: 0 };
    pad = { throttle: 0, steer: 0 };
  }

  function onkeydown(event: KeyboardEvent) {
    if (event.altKey && event.shiftKey && event.key.toLowerCase() === 's') {
      if (!visible) return;
      event.preventDefault();
      toggle();
      return;
    }
    if (!driving || !open || typingTarget(event.target)) return;
    const key = event.key.toLowerCase();
    if (!DRIVE_KEYS.has(key)) return;
    event.preventDefault();
    event.stopPropagation();
    pressed.add(key);
  }

  function onkeyup(event: KeyboardEvent) {
    pressed.delete(event.key.toLowerCase());
  }

  onMount(() => {
    try {
      open = localStorage.getItem(OPEN_KEY) === '1';
    } catch {
      open = false;
    }
    const controller = new AbortController();
    refresh(controller.signal);
    let timer: ReturnType<typeof setTimeout>;
    const schedule = () => {
      timer = setTimeout(
        async () => {
          if (info?.enabled !== false || open) await refresh(controller.signal);
          schedule();
        },
        open ? POLL_OPEN_MS : POLL_CLOSED_MS
      );
    };
    schedule();
    const tick = setInterval(() => (now = Date.now()), 1000);
    const blur = () => pressed.clear();
    window.addEventListener('blur', blur);
    return () => {
      controller.abort();
      clearTimeout(timer);
      clearInterval(tick);
      clearTimeout(speedTimer);
      window.removeEventListener('blur', blur);
      stopDriving();
    };
  });
</script>

<svelte:window {onkeydown} {onkeyup} />

{#if visible}
  <div class="sim-dock" class:open>
    {#if open}
      <section class="sim-panel" aria-label="Simulación de seguimiento">
        <header>
          <div class="title">
            <span class="badge">SIM</span>
            <strong>Simulación</strong>
          </div>
          <span class="env">Entorno de desarrollo</span>
          <button
            type="button"
            class="icon"
            aria-label="Ocultar simulación"
            onclick={() => toggle(false)}
          >
            <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"
              ><path
                d="M6 6l12 12M18 6L6 18"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
              /></svg
            >
          </button>
        </header>

        {#if !info?.ready}
          <p class="note warn">
            El servidor GPS no está configurado: no hay dónde reportar posiciones.
          </p>
        {/if}

        {#if sessions.length}
          <div class="chips" role="tablist" aria-label="Sesiones activas">
            {#each sessions as session (session.id)}
              {@const status = sessionStatus(session, now)}
              <button
                type="button"
                role="tab"
                aria-selected={session.id === activeId}
                class="chip {status.tone}"
                class:active={session.id === activeId}
                onclick={() => activate(session.id === activeId ? null : session)}
              >
                <span class="dot"></span>{session.vehicle_code}
              </button>
            {/each}
            {#if info?.can_simulate}
              <button
                type="button"
                class="chip new"
                class:active={!activeId}
                onclick={() => activate(null)}>+ Nueva</button
              >
            {/if}
          </div>
        {/if}

        {#if active}
          {@const status = sessionStatus(active, now)}
          <div class="session">
            <div class="session-head">
              <div>
                <strong>{active.vehicle_code}</strong>
                <span class="muted">{active.vehicle_plate}</span>
              </div>
              <span class="state {status.tone}"><span class="dot"></span>{status.label}</span>
            </div>
            <p class="muted small">
              {active.mode === 'joystick'
                ? 'Joystick'
                : active.transfer_code
                  ? `Traslado ${active.transfer_code}`
                  : 'Recorrido marcado'}
              {#if active.started_by_name}· {active.started_by_name}{/if}
            </p>

            {#if active.mode === 'route'}
              <div class="progress" aria-label="Avance del recorrido">
                <span style:width="{progressOf(active) * 100}%"></span>
              </div>
              <p class="muted small row">
                <span
                  >{formatDistance(active.progress_m)} de {formatDistance(
                    active.route_length_m
                  )}</span
                >
                <span>{Math.round(active.current_speed_kmh)} km/h</span>
              </p>
            {/if}

            {#if active.can_control}
              <label class="field">
                <span class="row"
                  ><span>Velocidad {active.mode === 'joystick' ? 'máxima' : 'objetivo'}</span><b
                    >{speed} km/h</b
                  ></span
                >
                <input
                  type="range"
                  min="5"
                  max="200"
                  step="5"
                  value={speed}
                  oninput={(event) => changeSpeed(Number(event.currentTarget.value))}
                />
              </label>

              {#if active.mode === 'joystick'}
                <div class="drive">
                  <div
                    class="pad"
                    role="slider"
                    tabindex="0"
                    aria-label="Joystick: arriba acelera, abajo frena, a los lados gira"
                    aria-valuenow={Math.round(shownSpeed)}
                    onpointerdown={(event) => {
                      event.currentTarget.setPointerCapture(event.pointerId);
                      padPointer(event, event.currentTarget);
                    }}
                    onpointermove={(event) => {
                      if (event.currentTarget.hasPointerCapture(event.pointerId))
                        padPointer(event, event.currentTarget);
                    }}
                    onpointerup={releasePad}
                    onpointercancel={releasePad}
                  >
                    <span class="knob" style:transform="translate({knob.x}px, {knob.y}px)"></span>
                  </div>
                  <div class="gauge">
                    <b>{Math.round(shownSpeed)}</b><span>km/h</span>
                    <label class="toggle">
                      <input type="checkbox" bind:checked={snap} /> Ajustar a calles
                    </label>
                    <span class="keys">WASD / flechas · Espacio frena</span>
                  </div>
                </div>
              {:else}
                <div class="actions">
                  {#if active.state === 'paused'}
                    <button type="button" disabled={busy} onclick={() => control('resume')}
                      >Reanudar</button
                    >
                  {:else if active.state === 'arrived'}
                    <button type="button" disabled={busy} onclick={() => control('restart')}
                      >Repetir</button
                    >
                  {:else}
                    <button type="button" disabled={busy} onclick={() => control('pause')}
                      >Pausar</button
                    >
                  {/if}
                  <button
                    type="button"
                    disabled={busy || active.state === 'arrived'}
                    title="Sale de la ruta planeada para probar la alerta de desvío"
                    onclick={() => control('detour')}>Desvío</button
                  >
                  {#if active.stop_until && new Date(active.stop_until).getTime() > now}
                    <button type="button" disabled={busy} onclick={() => control('resume')}
                      >Arrancar</button
                    >
                  {/if}
                </div>
              {/if}

              <div class="group">
                <span class="label">Detener</span>
                {#each STOP_PRESETS as minutes (minutes)}
                  <button
                    type="button"
                    disabled={busy}
                    title={minutes >= 20
                      ? 'Fuera de una sucursal genera la alerta de parada larga (20 min)'
                      : undefined}
                    onclick={() => control('stop', { minutes })}>{minutes} min</button
                  >
                {/each}
              </div>
              <div class="group">
                <span class="label">Señal</span>
                {#if active.signal_lost_until && new Date(active.signal_lost_until).getTime() > now}
                  <button type="button" disabled={busy} onclick={() => control('signal_restore')}
                    >Restaurar · {countdown(
                      new Date(active.signal_lost_until).getTime() - now
                    )}</button
                  >
                {:else}
                  {#each SIGNAL_PRESETS as minutes (minutes)}
                    <button
                      type="button"
                      disabled={busy}
                      title={minutes >= 10
                        ? 'Más de 10 min sin señal genera la alerta de GPS perdido'
                        : undefined}
                      onclick={() => control('signal_loss', { minutes })}
                      >Cortar {minutes} min</button
                    >
                  {/each}
                {/if}
              </div>
            {:else}
              <p class="note">
                Solo puede verla: la maneja otra persona o no tiene permiso para simular.
              </p>
            {/if}

            <div class="footer">
              <button type="button" class="ghost" onclick={() => onfocus?.(sessionKey(active))}
                >Ver en el mapa</button
              >
              {#if active.can_control}
                <button
                  type="button"
                  class="danger"
                  class:confirm={confirmEnd}
                  disabled={busy}
                  onclick={end}>{confirmEnd ? '¿Finalizar? Confirmar' : 'Finalizar'}</button
                >
              {/if}
            </div>
          </div>
        {:else if info?.can_simulate}
          <form
            class="form"
            onsubmit={(event) => {
              event.preventDefault();
              start();
            }}
          >
            <label class="field">
              <span>Vehículo</span>
              <select bind:value={vehicleId}>
                {#each candidates as vehicle (vehicle.id)}
                  <option value={vehicle.id} disabled={busyVehicles.has(vehicle.id)}>
                    {vehicle.code} · {vehicle.plate} — {vehicle.branch_name}{busyVehicles.has(
                      vehicle.id
                    )
                      ? ' (en simulación)'
                      : vehicle.has_gps
                        ? ' · GPS real'
                        : ''}
                  </option>
                {/each}
              </select>
            </label>
            {#if chosen?.has_gps}
              <p class="muted small">
                Su GPS real sigue reportando; el mapa mostrará el virtual hasta finalizar.
              </p>
            {/if}

            <div class="segmented" role="radiogroup" aria-label="Modo">
              <button
                type="button"
                role="radio"
                aria-checked={mode === 'route'}
                class:on={mode === 'route'}
                onclick={() => (mode = 'route')}>Trayecto automático</button
              >
              <button
                type="button"
                role="radio"
                aria-checked={mode === 'joystick'}
                class:on={mode === 'joystick'}
                onclick={() => (mode = 'joystick')}>Joystick</button
              >
            </div>

            {#if mode === 'route'}
              <div class="segmented small" role="radiogroup" aria-label="Recorrido">
                <button
                  type="button"
                  role="radio"
                  aria-checked={source === 'transfer'}
                  class:on={source === 'transfer'}
                  disabled={!chosen?.transfer_id}
                  title={chosen?.transfer_id
                    ? undefined
                    : 'El vehículo no tiene un traslado en tránsito'}
                  onclick={() => (source = 'transfer')}
                  >{chosen?.transfer_code
                    ? `Traslado ${chosen.transfer_code}`
                    : 'Traslado en curso'}</button
                >
                <button
                  type="button"
                  role="radio"
                  aria-checked={source === 'points'}
                  class:on={source === 'points'}
                  onclick={() => (source = 'points')}>Puntos en el mapa</button
                >
              </div>
              {#if source === 'points'}
                <div class="picker" class:active={picking}>
                  <button type="button" class:on={picking} onclick={() => (picking = !picking)}>
                    {picking ? 'Marcando… (clic en el mapa)' : 'Marcar en el mapa'}
                  </button>
                  <span class="muted small"
                    >{waypoints.length} punto{waypoints.length === 1 ? '' : 's'}</span
                  >
                  {#if waypoints.length}
                    <button
                      type="button"
                      class="ghost"
                      onclick={() => (waypoints = waypoints.slice(0, -1))}>Deshacer</button
                    >
                    <button type="button" class="ghost" onclick={() => (waypoints = [])}
                      >Limpiar</button
                    >
                  {/if}
                </div>
              {/if}
            {:else}
              <p class="muted small">
                Aparece donde se ve la unidad (o en su sucursal) y la maneja con el joystick o el
                teclado.
              </p>
            {/if}

            <label class="field">
              <span class="row"><span>Velocidad</span><b>{speed} km/h</b></span>
              <input type="range" min="5" max="200" step="5" bind:value={speed} />
              <span class="presets">
                {#each SPEED_PRESETS as preset (preset)}
                  <button type="button" class:on={speed === preset} onclick={() => (speed = preset)}
                    >{preset}</button
                  >
                {/each}
              </span>
            </label>

            <button type="submit" class="primary" disabled={!canStart || busy || !info?.ready}>
              {busy ? 'Iniciando…' : 'Iniciar simulación'}
            </button>
          </form>
        {/if}

        {#if error}<p class="note error" role="alert">{error}</p>{/if}
        <p class="hint">Alt + Shift + S muestra u oculta este panel</p>
      </section>
    {/if}

    <button
      type="button"
      class="sim-pill"
      class:on={open}
      aria-expanded={open}
      title="Simulación (Alt + Shift + S)"
      onclick={() => toggle()}
    >
      <span class="badge">SIM</span>
      {#if sessions.length}<span class="count">{sessions.length}</span>{/if}
    </button>
  </div>
{/if}

<style>
  .sim-dock {
    --sim: 124 58 237;
    position: absolute;
    right: 12px;
    bottom: 40px;
    z-index: 3;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
    max-height: calc(100% - 120px);
    pointer-events: none;
  }
  .sim-dock > * {
    pointer-events: auto;
  }
  .sim-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 7px;
    border: 1px solid rgb(var(--border));
    border-radius: 999px;
    background: rgb(var(--surface) / 0.9);
    box-shadow: 0 4px 14px rgb(0 0 0 / 0.14);
    color: rgb(var(--foreground));
    backdrop-filter: blur(6px);
    cursor: pointer;
    opacity: 0.78;
    transition:
      opacity 150ms ease,
      border-color 150ms ease;
  }
  .sim-pill:hover,
  .sim-pill.on,
  .sim-pill:focus-visible {
    opacity: 1;
    border-color: rgb(var(--sim) / 0.5);
  }
  .badge {
    padding: 1px 6px;
    border-radius: 6px;
    background: rgb(var(--sim));
    color: #fff;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.08em;
  }
  .count {
    min-width: 18px;
    padding: 0 5px;
    border-radius: 999px;
    background: rgb(var(--sim) / 0.14);
    color: rgb(var(--sim));
    font-size: 11px;
    font-weight: 700;
    text-align: center;
  }
  .sim-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 312px;
    max-height: 100%;
    overflow-y: auto;
    padding: 12px;
    border: 1px solid rgb(var(--sim) / 0.28);
    border-radius: 14px;
    background: rgb(var(--surface) / 0.94);
    box-shadow: 0 14px 38px rgb(0 0 0 / 0.22);
    color: rgb(var(--foreground));
    font-size: 12.5px;
    backdrop-filter: blur(10px);
    animation: sim-rise 160ms ease-out;
  }
  header {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13.5px;
  }
  .env {
    margin-left: auto;
    color: rgb(var(--foreground-muted));
    font-size: 11px;
  }
  .icon {
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: rgb(var(--foreground-muted));
    cursor: pointer;
  }
  .icon:hover {
    background: rgb(var(--foreground) / 0.06);
  }
  .muted {
    color: rgb(var(--foreground-muted));
  }
  .small {
    margin: 0;
    font-size: 11.5px;
    line-height: 1.4;
  }
  .row {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 9px;
    border: 1px solid rgb(var(--border));
    border-radius: 999px;
    background: transparent;
    color: inherit;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
  }
  .chip.active {
    border-color: rgb(var(--sim) / 0.6);
    background: rgb(var(--sim) / 0.1);
  }
  .chip.new {
    color: rgb(var(--sim));
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: rgb(var(--foreground-muted));
  }
  .live .dot {
    background: rgb(var(--success));
    animation: sim-pulse 1.6s ease-in-out infinite;
  }
  .hold .dot {
    background: rgb(var(--warning));
  }
  .lost .dot {
    background: rgb(var(--danger));
  }
  .done .dot {
    background: rgb(var(--sim));
  }
  .session,
  .form {
    display: grid;
    gap: 10px;
  }
  .session-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .session-head strong {
    margin-right: 6px;
  }
  .state {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11.5px;
    font-weight: 600;
  }
  .progress {
    height: 6px;
    overflow: hidden;
    border-radius: 999px;
    background: rgb(var(--foreground) / 0.08);
  }
  .progress span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: rgb(var(--sim));
    transition: width 600ms linear;
  }
  .field {
    display: grid;
    gap: 6px;
  }
  .field > span:first-child {
    color: rgb(var(--foreground-muted));
    font-size: 11.5px;
  }
  .field b {
    color: rgb(var(--foreground));
  }
  select {
    width: 100%;
    padding: 7px 8px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: inherit;
    font: inherit;
  }
  input[type='range'] {
    width: 100%;
    accent-color: rgb(var(--sim));
  }
  button {
    font: inherit;
  }
  .segmented {
    display: grid;
    grid-template-columns: 1fr 1fr;
    padding: 3px;
    border-radius: 9px;
    background: rgb(var(--foreground) / 0.06);
  }
  .segmented button {
    padding: 6px 8px;
    border: 0;
    border-radius: 7px;
    background: transparent;
    color: rgb(var(--foreground-muted));
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  }
  .segmented button.on {
    background: rgb(var(--surface));
    box-shadow: 0 1px 3px rgb(0 0 0 / 0.12);
    color: rgb(var(--foreground));
  }
  .segmented button:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
  .segmented.small button {
    font-size: 11.5px;
  }
  .picker,
  .actions,
  .group,
  .presets,
  .footer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
  }
  .picker.active {
    padding: 6px;
    border-radius: 9px;
    background: rgb(var(--sim) / 0.08);
  }
  .label {
    min-width: 54px;
    color: rgb(var(--foreground-muted));
    font-size: 11.5px;
  }
  .picker button,
  .actions button,
  .group button,
  .presets button,
  .footer button {
    padding: 5px 9px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: inherit;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  }
  .actions button {
    flex: 1;
  }
  .presets button {
    padding: 3px 8px;
    font-size: 11px;
  }
  button.on,
  .presets button.on {
    border-color: rgb(var(--sim) / 0.55);
    background: rgb(var(--sim) / 0.1);
    color: rgb(var(--sim));
  }
  button:disabled {
    cursor: not-allowed;
    opacity: 0.55;
  }
  .ghost {
    border-color: transparent !important;
    background: transparent !important;
    color: rgb(var(--foreground-muted)) !important;
  }
  .footer {
    justify-content: space-between;
    padding-top: 4px;
    border-top: 1px solid rgb(var(--border));
  }
  .danger {
    border-color: rgb(var(--danger) / 0.35) !important;
    color: rgb(var(--danger)) !important;
  }
  .danger.confirm {
    background: rgb(var(--danger)) !important;
    color: #fff !important;
  }
  .primary {
    padding: 9px 12px;
    border: 0;
    border-radius: 9px;
    background: rgb(var(--sim));
    color: #fff;
    font-size: 12.5px;
    font-weight: 700;
    cursor: pointer;
  }
  .primary:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }
  .drive {
    display: grid;
    grid-template-columns: 112px 1fr;
    align-items: center;
    gap: 14px;
  }
  .pad {
    position: relative;
    display: grid;
    place-items: center;
    width: 112px;
    height: 112px;
    border: 1px solid rgb(var(--sim) / 0.3);
    border-radius: 50%;
    background:
      radial-gradient(circle, rgb(var(--sim) / 0.12) 0 30%, transparent 31%),
      rgb(var(--foreground) / 0.04);
    touch-action: none;
    cursor: grab;
  }
  .pad:active {
    cursor: grabbing;
  }
  .knob {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: rgb(var(--sim));
    box-shadow: 0 4px 12px rgb(var(--sim) / 0.45);
    transition: transform 60ms linear;
  }
  .gauge {
    display: grid;
    gap: 2px;
  }
  .gauge b {
    font-size: 30px;
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }
  .gauge > span {
    color: rgb(var(--foreground-muted));
    font-size: 11px;
  }
  .toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 8px;
    font-size: 11.5px;
  }
  .toggle input {
    accent-color: rgb(var(--sim));
  }
  .keys {
    margin-top: 2px;
  }
  .note {
    margin: 0;
    padding: 7px 9px;
    border-radius: 8px;
    background: rgb(var(--foreground) / 0.05);
    font-size: 11.5px;
    line-height: 1.4;
  }
  .note.warn {
    background: rgb(var(--warning) / 0.12);
  }
  .note.error {
    background: rgb(var(--danger) / 0.1);
    color: rgb(var(--danger));
  }
  .hint {
    margin: 0;
    color: rgb(var(--foreground-muted));
    font-size: 10.5px;
    text-align: center;
  }
  @keyframes sim-rise {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
  }
  @keyframes sim-pulse {
    50% {
      opacity: 0.4;
    }
  }
  @media (max-width: 900px) {
    /* En móvil el mapa ocupa la parte superior: el panel flota sobre él, arriba a la izquierda. */
    .sim-dock {
      top: 12px;
      right: auto;
      bottom: auto;
      left: 12px;
      align-items: flex-start;
      flex-direction: column-reverse;
      max-height: calc(55dvh - 24px);
    }
    .sim-panel {
      width: min(312px, calc(100vw - 24px));
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .sim-panel {
      animation: none;
    }
    .live .dot {
      animation: none;
    }
  }
</style>
