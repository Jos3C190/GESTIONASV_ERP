<script lang="ts">
  import { tick } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type FleetVehicle, type GpsStatus } from './api';
  import FleetIcon from './FleetIcon.svelte';
  import GpsSetupDialog from './gps/GpsSetupDialog.svelte';
  import {
    CARD_POLL_MS,
    cardView,
    readingRows,
    resumeStep,
    type CardTone,
    type DeviceKind,
    type SetupStep
  } from './gps/setup-flow';

  let { vehicle, onchanged }: { vehicle: FleetVehicle; onchanged: (next: FleetVehicle) => void } =
    $props();

  let status = $state<GpsStatus | null>(null);
  let loaded = $state(false);
  let now = $state(Date.now());
  let saving = $state(false);
  let confirmUnlink = $state(false);
  let error = $state<string | null>(null);
  let dialogOpen = $state(false);
  let startKind = $state<DeviceKind | null>(null);
  let startStep = $state<SetupStep>('kind');
  let cardHeading = $state<HTMLHeadingElement | null>(null);
  let deviceActions = $state<HTMLDivElement | null>(null);

  const retired = $derived(vehicle.status === 'retired');
  const canManage = $derived(permissions.hasPermission('fleet:gps') && !retired);
  const canTrack = $derived(permissions.hasPermission('tracking:read'));
  const view = $derived(cardView(status, now, canManage, retired));
  const readings = $derived(readingRows(status?.readings));
  const toneIcon: Record<CardTone, 'navigation' | 'clock' | 'check' | 'alert'> = {
    neutral: 'navigation',
    waiting: 'clock',
    good: 'check',
    warning: 'alert'
  };

  async function refresh() {
    try {
      status = await fleetApi.gpsStatus(vehicle.id);
    } catch {
      status = null;
    } finally {
      now = Date.now();
      loaded = true;
    }
  }

  $effect(() => {
    void vehicle.id;
    void refresh();
    const timer = setInterval(() => {
      if (!document.hidden && !dialogOpen) void refresh();
    }, CARD_POLL_MS);
    return () => clearInterval(timer);
  });

  function openWizard(kind: DeviceKind | null, step: SetupStep) {
    startKind = kind;
    startStep = step;
    dialogOpen = true;
  }

  /** El botón que abrió el asistente puede ya no existir: el foco vuelve al estado. */
  async function closeWizard(value: boolean) {
    dialogOpen = value;
    if (value) return;
    await refresh();
    await tick();
    cardHeading?.focus();
  }

  /** El botón pulsado desaparece al cambiar de vista; el foco no debe perderse. */
  async function askUnlink(next: boolean) {
    confirmUnlink = next;
    error = null;
    await tick();
    const buttons = deviceActions?.querySelectorAll('button');
    (next ? buttons?.[0] : buttons?.[buttons.length - 1])?.focus();
  }

  async function unlink() {
    saving = true;
    error = null;
    try {
      onchanged(await fleetApi.unlinkGps(vehicle.id));
      confirmUnlink = false;
      await refresh();
      await tick();
      cardHeading?.focus();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo desvincular el GPS.';
    } finally {
      saving = false;
    }
  }
</script>

<div class="panel">
  <section class="card">
    {#if !loaded}
      <p class="muted" role="status">Comprobando el GPS…</p>
    {:else}
      <div class="status {view.tone}">
        <span class="badge" aria-hidden="true"
          ><FleetIcon name={toneIcon[view.tone]} size={20} /></span
        >
        <div class="text">
          <h2 tabindex="-1" bind:this={cardHeading}>{view.title}</h2>
          <p>{view.detail}</p>
          {#if status?.battery_level != null && status.state === 'reporting'}
            <p class="meta">
              <FleetIcon name="battery" size={14} />Batería {Math.round(status.battery_level)} %
            </p>
          {/if}
        </div>
      </div>

      {#if readings.length}
        <section class="readings" aria-labelledby="gps-readings-title">
          <h3 id="gps-readings-title">
            {status?.state === 'silent' ? 'Datos de la última señal' : 'Datos del equipo'}
          </h3>
          <dl>
            {#each readings as reading (reading.label)}
              <div>
                <dt>{reading.label}</dt>
                <dd>{reading.value}</dd>
              </div>
            {/each}
          </dl>
        </section>
      {/if}

      {#if view.action === 'connect' && canManage}
        <Button size="lg" class="w-full sm:w-auto" onclick={() => openWizard(null, 'kind')}>
          Conectar GPS
        </Button>
      {:else if view.action === 'resume' && canManage && status?.kind}
        <Button
          size="lg"
          class="w-full sm:w-auto"
          onclick={() => openWizard(status!.kind, resumeStep(status!.kind!))}
        >
          Continuar configuración
        </Button>
      {:else if view.action === 'help' && canManage && status?.kind}
        <Button
          size="lg"
          class="w-full sm:w-auto"
          onclick={() => openWizard(status!.kind, 'signal')}
        >
          Ver cómo resolverlo
        </Button>
      {:else if view.action === 'track' && canTrack}
        <a class="track" href="/tracking">Ver en Seguimiento</a>
      {:else if view.action === 'retry'}
        <Button
          variant="secondary"
          size="lg"
          class="w-full sm:w-auto"
          onclick={() => void refresh()}
        >
          Reintentar
        </Button>
      {/if}

      {#if vehicle.gps_linked && canManage}
        <div class="device">
          <div>
            <span class="muted">Identificador</span>
            <code>{vehicle.gps_device_unique_id}</code>
          </div>
          {#if confirmUnlink}
            <p class="muted">El vehículo dejará de verse en Seguimiento.</p>
          {/if}
          <div class="row" bind:this={deviceActions}>
            {#if confirmUnlink}
              <Button
                size="lg"
                variant="secondary"
                disabled={saving}
                onclick={() => void askUnlink(false)}
              >
                Cancelar
              </Button>
              <Button size="lg" variant="danger" disabled={saving} onclick={() => void unlink()}>
                Desvincular
              </Button>
            {:else}
              <Button size="lg" variant="secondary" onclick={() => openWizard(null, 'kind')}>
                Conectar otro equipo
              </Button>
              <Button size="lg" variant="ghost" onclick={() => void askUnlink(true)}>
                Desvincular GPS
              </Button>
            {/if}
          </div>
        </div>
      {/if}
    {/if}
    {#if error}<p class="error" role="alert">{error}</p>{/if}
  </section>
</div>

{#if dialogOpen}
  <GpsSetupDialog
    bind:open={() => dialogOpen, closeWizard}
    {vehicle}
    {startKind}
    {startStep}
    {onchanged}
  />
{/if}

<style>
  .panel {
    max-width: 640px;
  }
  .card {
    display: grid;
    gap: 16px;
    padding: 16px;
    border: 1px solid rgb(var(--border));
    border-radius: 14px;
    background: rgb(var(--surface));
  }
  .status {
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }
  .badge {
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
  .good .badge {
    color: rgb(var(--success));
    background: rgb(var(--success) / 14%);
  }
  .warning .badge {
    color: rgb(var(--warning));
    background: rgb(var(--warning) / 14%);
  }
  .text {
    min-width: 0;
  }
  h2 {
    margin: 0;
    color: rgb(var(--foreground));
    font-size: 16px;
    font-weight: 600;
  }
  /* El foco aquí es para lectores de pantalla: el título no es un control. */
  h2:focus-visible {
    box-shadow: none;
  }
  .text p {
    margin: 2px 0 0;
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  .text .meta {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 6px;
  }
  .readings {
    width: 100%;
  }
  h3 {
    margin: 0 0 8px;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
    font-weight: 500;
  }
  dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 8px;
    margin: 0;
  }
  dl div {
    padding: 10px 12px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface-elevated));
  }
  dt {
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  dd {
    margin: 2px 0 0;
    color: rgb(var(--foreground));
    font-size: 15px;
    font-weight: 600;
  }
  .muted {
    margin: 0;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .track {
    display: inline-flex;
    min-height: 44px;
    align-items: center;
    justify-content: center;
    padding: 0 20px;
    border-radius: 8px;
    color: rgb(var(--surface));
    background: rgb(var(--foreground));
    font-size: 14px;
    font-weight: 500;
    text-decoration: none;
  }
  .track:hover {
    background: rgb(var(--foreground-muted));
  }
  .track:focus-visible {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 2px;
  }
  .device {
    display: grid;
    gap: 10px;
    padding-top: 14px;
    border-top: 1px solid rgb(var(--border));
  }
  code {
    display: block;
    color: rgb(var(--foreground));
    font-size: 14px;
    overflow-wrap: anywhere;
  }
  .row {
    display: grid;
    gap: 8px;
  }
  @media (min-width: 640px) {
    .row {
      display: flex;
      flex-wrap: wrap;
    }
  }
  .error {
    margin: 0;
    color: rgb(var(--danger));
    font-size: 14px;
  }
  @media (min-width: 640px) {
    .card {
      justify-items: start;
      padding: 20px;
    }
    .device {
      width: 100%;
    }
  }
</style>
