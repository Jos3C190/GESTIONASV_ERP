<script lang="ts">
  import { onMount, tick, untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type FleetVehicle, type GpsSetup } from '../api';
  import FleetIcon from '../FleetIcon.svelte';
  import Notice from './Notice.svelte';
  import PhoneSteps from './PhoneSteps.svelte';
  import {
    cleanIdentifier,
    isPhoneIdentifier,
    nextStep,
    OTHER_MODEL,
    previousStep,
    resumeStep,
    stepNumber,
    TOTAL_STEPS,
    validIdentifier,
    type DeviceKind,
    type SetupStep
  } from './setup-flow';
  import SignalCheckStep from './SignalCheckStep.svelte';
  import TrackerSteps from './TrackerSteps.svelte';

  let {
    open = $bindable(),
    vehicle,
    startKind = null,
    startStep = 'kind',
    onchanged
  }: {
    open: boolean;
    vehicle: FleetVehicle;
    startKind?: DeviceKind | null;
    startStep?: SetupStep;
    onchanged: (next: FleetVehicle) => void;
  } = $props();

  const COPY: Record<SetupStep, { title: string; intro: string }> = {
    kind: { title: '¿Qué vas a conectar?', intro: 'Elige una opción; te guiamos paso a paso.' },
    install: {
      title: 'Instala la app en el teléfono',
      intro: 'Hazlo en el teléfono que va a viajar en el vehículo.'
    },
    scan: {
      title: 'Configura la app',
      intro: 'Con esto la app sabe a qué vehículo pertenece.'
    },
    permissions: {
      title: 'Revisa los permisos',
      intro: 'Hazlo en el teléfono. Sin esto, la ubicación se corta con la pantalla apagada.'
    },
    model: { title: '¿Qué GPS tienes?', intro: 'La marca aparece en el GPS o en su caja.' },
    identifier: {
      title: 'Escribe su identificador',
      intro: 'Es el número que identifica al GPS.'
    },
    configure: {
      title: 'Configura el GPS',
      intro: 'Debe enviar su ubicación a este servidor.'
    },
    signal: { title: 'Comprobando la señal', intro: 'Vemos si ya llega su ubicación.' }
  };

  // Solo valores iniciales: el asistente lleva su propio avance desde aquí.
  const initial = untrack(() => {
    const replacing = vehicle.gps_linked && startStep === 'kind';
    const current = vehicle.gps_device_unique_id;
    return {
      vehicleId: vehicle.id,
      kind: startKind,
      step: startStep,
      replacing,
      previous: current,
      // Al reemplazar se pide el número nuevo: el del equipo actual no reemplaza nada.
      identifier: replacing || isPhoneIdentifier(current) ? '' : (current ?? '')
    };
  });

  let kind = $state<DeviceKind | null>(initial.kind);
  let step = $state<SetupStep>(initial.step);
  let setup = $state<GpsSetup | null>(null);
  let loadError = $state(false);
  let busy = $state(false);
  let stepError = $state<string | null>(null);
  let fieldError = $state<string | null>(null);
  let modelKey = $state('');
  let identifier = $state(initial.identifier);
  let checks = $state([false, false, false]);
  let reporting = $state(false);
  // Solo el primer enlace reemplaza: repetirlo invalidaría un código ya escaneado.
  let replacePending = $state(initial.replacing);
  let heading = $state<HTMLHeadingElement | null>(null);

  // Se llega directo a la señal desde "Ver cómo resolverlo": ahí la ayuda va de entrada.
  const showHelpNow = initial.step === 'signal';
  const canTrack = $derived(permissions.hasPermission('tracking:read'));
  const number = $derived(stepNumber(kind, step));
  const usable = $derived(!loadError && (!setup || setup.configured));
  const copy = $derived.by(() => {
    if (step !== 'signal') return COPY[step];
    if (reporting) {
      return {
        title: kind === 'phone' ? 'Teléfono conectado' : 'GPS conectado',
        intro: 'El vehículo ya aparece en Seguimiento.'
      };
    }
    return showHelpNow
      ? { title: 'Revisemos la señal', intro: 'Comprueba estos puntos uno por uno.' }
      : COPY.signal;
  });
  const tracker = $derived(setup?.trackers.find((item) => item.key === modelKey) ?? null);
  // Al retomar una configuración también se puede cambiar de tipo y perder el equipo actual.
  const changesKind = $derived(
    vehicle.gps_linked &&
      kind !== null &&
      (kind === 'phone') !== isPhoneIdentifier(vehicle.gps_device_unique_id)
  );
  const replaceWarning = $derived(
    (replacePending || changesKind) &&
      (step === 'kind' || step === 'install' || step === 'identifier')
  );

  const blocked = $derived.by(() => {
    if (step === 'kind') return kind === null;
    if (step === 'model') return !tracker;
    return false;
  });

  const primaryLabel = $derived.by(() => {
    if (step === 'install') return 'Ya la instalé';
    if (step === 'scan') return 'Ya la configuré';
    if (step === 'permissions') return 'Comprobar señal';
    if (step === 'configure') return 'Ya lo configuré';
    return 'Continuar';
  });

  async function loadSetup() {
    if (loadError) {
      // "Reintentar" desaparece al pulsarlo: el foco pasa al título.
      loadError = false;
      await tick();
      heading?.focus();
    }
    try {
      setup = await fleetApi.gpsSetup(initial.vehicleId);
    } catch {
      loadError = true;
    }
  }

  onMount(() => {
    void loadSetup();
    // El Modal enfoca "Cerrar" en el siguiente cuadro; el foco debe quedar en el paso.
    const frame = requestAnimationFrame(() => requestAnimationFrame(() => heading?.focus()));
    return () => cancelAnimationFrame(frame);
  });

  async function goTo(next: SetupStep) {
    step = next;
    stepError = null;
    fieldError = null;
    await tick();
    // Quien usa lector de pantalla oye el título nuevo al cambiar de paso.
    heading?.focus();
  }

  function messageOf(error: unknown): string {
    return error instanceof HttpError
      ? error.message
      : 'No se pudo conectar con el servidor. Inténtalo de nuevo.';
  }

  async function linkThen(action: () => Promise<FleetVehicle>, next: SetupStep, inField: boolean) {
    busy = true;
    stepError = null;
    fieldError = null;
    try {
      onchanged(await action());
      replacePending = false;
      setup = await fleetApi.gpsSetup(initial.vehicleId);
      await goTo(next);
    } catch (error) {
      if (inField) fieldError = messageOf(error);
      else stepError = messageOf(error);
    } finally {
      busy = false;
    }
  }

  async function advance() {
    if (!kind || blocked || busy) return;
    const next = nextStep(kind, step);
    if (step === 'install') {
      const replace = replacePending;
      await linkThen(() => fleetApi.linkPhone(initial.vehicleId, replace), next, false);
    } else if (step === 'identifier') {
      const value = cleanIdentifier(identifier);
      if (!validIdentifier(value)) {
        fieldError = 'Revisa el identificador: solo letras y números, de 3 a 64.';
      } else if (initial.replacing && value === initial.previous) {
        fieldError = 'Ese es el GPS actual; escribe el del equipo nuevo.';
      } else {
        identifier = value;
        await linkThen(() => fleetApi.linkGps(initial.vehicleId, value), next, true);
      }
    } else {
      await goTo(next);
    }
  }

  function back() {
    if (kind) void goTo(previousStep(kind, step));
  }

  function close() {
    open = false;
  }
</script>

<Modal
  {open}
  title="Conectar GPS"
  size="md"
  mobileFullScreen
  flush
  preventClose={busy}
  onclose={close}
>
  <div class="wizard">
    {#if usable}
      <div class="progress">
        <span class="count">Paso {number} de {TOTAL_STEPS}</span>
        <div
          class="bar"
          role="progressbar"
          aria-label="Avance de la configuración"
          aria-valuemin="1"
          aria-valuemax={TOTAL_STEPS}
          aria-valuenow={number}
          aria-valuetext={`Paso ${number} de ${TOTAL_STEPS}`}
        >
          <span style:width={`${(number / TOTAL_STEPS) * 100}%`}></span>
        </div>
      </div>
    {/if}

    <div class="body">
      <!-- Siempre montado: si el paso se vuelve un error, el foco no se pierde. -->
      <header>
        <h3 tabindex="-1" bind:this={heading}>{usable ? copy.title : 'No se puede continuar'}</h3>
        {#if usable}<p>{copy.intro}</p>{/if}
      </header>

      {#if loadError}
        <div class="alert" role="alert">
          <p>No pudimos cargar los datos de conexión.</p>
          <Button variant="secondary" size="lg" onclick={() => void loadSetup()}>Reintentar</Button>
        </div>
      {:else if !setup}
        <p class="loading" role="status">Cargando…</p>
      {:else if !setup.configured}
        <div class="alert" role="alert">
          <p>
            Falta configurar la dirección del servidor GPS. Pídeselo al administrador; sin ella los
            equipos no saben a dónde enviar su ubicación.
          </p>
        </div>
      {:else}
        {#if step === 'kind'}
          <div class="kinds" role="radiogroup" aria-label="Tipo de equipo">
            <label class="kind" class:selected={kind === 'phone'}>
              <input type="radio" name="gps-kind" value="phone" bind:group={kind} />
              <span class="kind-icon"><FleetIcon name="phone" size={22} /></span>
              <span class="kind-text">
                <strong>Teléfono del conductor</strong>
                <small>Sin comprar nada; usa una app gratuita.</small>
              </span>
            </label>
            <label class="kind" class:selected={kind === 'tracker'}>
              <input type="radio" name="gps-kind" value="tracker" bind:group={kind} />
              <span class="kind-icon"><FleetIcon name="truck" size={22} /></span>
              <span class="kind-text">
                <strong>GPS instalado en el vehículo</strong>
                <small>Un equipo fijo con su propio chip de datos.</small>
              </span>
            </label>
          </div>
          {#if setup.private_network}
            <Notice>
              Por ahora el servidor solo funciona dentro de la red de la empresa. Fuera de ella, con
              datos móviles, no llegará la ubicación.
            </Notice>
          {/if}
        {:else if step === 'signal' && kind}
          <SignalCheckStep
            vehicleId={vehicle.id}
            {kind}
            privateNetwork={setup.private_network}
            {showHelpNow}
            onsignal={(value) => (reporting = value)}
          />
        {:else if kind === 'phone'}
          <PhoneSteps
            {step}
            configUri={setup.phone_config_uri}
            serverUrl={setup.server_url}
            identifier={vehicle.gps_device_unique_id}
            bind:permissions={checks}
          />
        {:else if kind === 'tracker'}
          <TrackerSteps
            {step}
            models={setup.trackers}
            host={setup.host}
            {fieldError}
            onsubmit={() => void advance()}
            onedit={() => (fieldError = null)}
            bind:modelKey
            bind:identifier
          />
        {/if}
        {#if replaceWarning}
          <Notice warn>
            Este vehículo ya tiene un GPS. Al continuar con el nuevo, el actual dejará de aparecer
            en Seguimiento.
          </Notice>
        {/if}
        {#if stepError}<p class="error" role="alert">{stepError}</p>{/if}
      {/if}
    </div>
  </div>

  {#snippet footer()}
    <div class="actions">
      {#if !usable}
        <span class="spacer"></span>
        <Button size="lg" class="grow sm:grow-0" onclick={close}>Cerrar</Button>
      {:else if step === 'signal'}
        {#if reporting}
          <span class="spacer"></span>
          {#if canTrack}
            <Button variant="secondary" size="lg" onclick={close}>Cerrar</Button>
            <Button size="lg" class="grow sm:grow-0" onclick={() => goto('/tracking')}>
              Ver en Seguimiento
            </Button>
          {:else}
            <Button size="lg" class="grow sm:grow-0" onclick={close}>Listo</Button>
          {/if}
        {:else}
          {#if kind}
            <Button
              variant="ghost"
              size="lg"
              onclick={() =>
                kind && void goTo(showHelpNow ? resumeStep(kind) : previousStep(kind, step))}
            >
              Revisar datos
            </Button>
          {/if}
          <span class="spacer"></span>
          <Button variant="secondary" size="lg" class="grow sm:grow-0" onclick={close}>
            Terminar después
          </Button>
        {/if}
      {:else}
        {#if step === 'kind'}
          <Button variant="ghost" size="lg" disabled={busy} onclick={close}>Cancelar</Button>
        {:else}
          <Button variant="ghost" size="lg" disabled={busy} onclick={back}>Atrás</Button>
        {/if}
        <span class="spacer"></span>
        {#if setup?.configured}
          {#if step === 'model' && modelKey === OTHER_MODEL}
            <Button size="lg" class="grow sm:grow-0" onclick={close}>Entendido</Button>
          {:else}
            <Button
              size="lg"
              class="grow sm:grow-0"
              disabled={blocked || busy}
              onclick={() => void advance()}
            >
              {busy ? 'Guardando…' : primaryLabel}
            </Button>
          {/if}
        {/if}
      {/if}
    </div>
  {/snippet}
</Modal>

<style>
  .wizard {
    display: flex;
    flex-direction: column;
  }
  .progress {
    display: grid;
    gap: 8px;
    padding: 12px 16px;
    border-bottom: 1px solid rgb(var(--border));
  }
  .count {
    color: rgb(var(--foreground-muted));
    font-size: 13px;
    font-weight: 500;
  }
  .bar {
    overflow: hidden;
    height: 4px;
    border-radius: 2px;
    background: rgb(var(--surface-muted));
  }
  .bar span {
    display: block;
    height: 100%;
    border-radius: 2px;
    background: rgb(var(--foreground));
    transition: width 0.2s ease-out;
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 16px;
  }
  header h3 {
    margin: 0;
    color: rgb(var(--foreground));
    font-size: 18px;
    font-weight: 600;
  }
  /* El foco aquí es para lectores de pantalla: el título no es un control. */
  header h3:focus-visible {
    box-shadow: none;
  }
  header p {
    margin: 4px 0 0;
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  .kinds {
    display: grid;
    gap: 10px;
  }
  .kind {
    position: relative;
    display: flex;
    min-height: 76px;
    align-items: center;
    gap: 12px;
    padding: 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface-elevated));
    cursor: pointer;
  }
  .kind:hover {
    background: rgb(var(--surface-hover));
  }
  .kind.selected {
    border-color: rgb(var(--foreground));
    box-shadow: inset 0 0 0 1px rgb(var(--foreground));
  }
  .kind:focus-within {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 2px;
  }
  .kind input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
  }
  .kind-icon {
    display: flex;
    width: 44px;
    height: 44px;
    flex: none;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    color: rgb(var(--foreground));
    background: rgb(var(--surface-muted));
  }
  .kind-text strong {
    display: block;
    color: rgb(var(--foreground));
    font-size: 15px;
    font-weight: 600;
  }
  .kind-text small {
    display: block;
    margin-top: 2px;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .alert {
    display: grid;
    justify-items: start;
    gap: 10px;
    padding: 14px;
    border: 1px solid rgb(var(--warning) / 45%);
    border-radius: 12px;
    color: rgb(var(--foreground));
    background: rgb(var(--warning) / 10%);
    font-size: 14px;
  }
  .alert p {
    margin: 0;
  }
  .loading {
    margin: 0;
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  .error {
    margin: 0;
    color: rgb(var(--danger));
    font-size: 14px;
  }
  .actions {
    display: flex;
    width: 100%;
    align-items: center;
    gap: 8px;
  }
  .spacer {
    flex: 1;
  }
  @media (min-width: 640px) {
    .progress {
      padding-inline: 20px;
    }
    .body {
      padding: 20px;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .bar span {
      transition: none;
    }
  }
</style>
