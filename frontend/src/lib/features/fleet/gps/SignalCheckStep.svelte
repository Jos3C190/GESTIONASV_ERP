<script lang="ts">
  import { fleetApi, type GpsStatus } from '../api';
  import FleetIcon from '../FleetIcon.svelte';
  import {
    HELP_AFTER_MS,
    timeAgo,
    troubleshooting,
    WIZARD_POLL_MS,
    type DeviceKind
  } from './setup-flow';

  let {
    vehicleId,
    kind,
    privateNetwork,
    showHelpNow = false,
    onsignal
  }: {
    vehicleId: string;
    kind: DeviceKind;
    privateNetwork: boolean;
    showHelpNow?: boolean;
    onsignal: (reporting: boolean) => void;
  } = $props();

  let status = $state<GpsStatus | null>(null);
  let waitedLong = $state(false);
  let failures = $state(0);

  const reporting = $derived(status?.state === 'reporting');
  const silent = $derived(status?.state === 'silent');
  const showHelp = $derived(!reporting && (showHelpNow || waitedLong || silent));
  const checks = $derived(troubleshooting(kind, privateNetwork));
  const noun = $derived(kind === 'phone' ? 'teléfono' : 'GPS');

  $effect(() => {
    const id = vehicleId;
    const controller = new AbortController();

    async function check() {
      if (document.hidden) return;
      try {
        status = await fleetApi.gpsStatus(id, controller.signal);
        failures = 0;
        onsignal(status.state === 'reporting');
      } catch {
        // Se reintenta en la siguiente vuelta; la espera no se interrumpe.
        if (!controller.signal.aborted) failures += 1;
      }
    }

    void check();
    const poll = setInterval(() => void check(), WIZARD_POLL_MS);
    const help = setTimeout(() => (waitedLong = true), HELP_AFTER_MS);
    return () => {
      controller.abort();
      clearInterval(poll);
      clearTimeout(help);
    };
  });
</script>

<div class="signal" class:good={reporting}>
  <div class="icon" aria-hidden="true">
    {#if reporting}
      <FleetIcon name="check" size={32} />
    {:else}
      <span class="pulse"></span>
      <FleetIcon name="navigation" size={26} />
    {/if}
  </div>
  <div role="status" aria-live="polite" class="message">
    {#if reporting}
      <h4>¡Listo! Ya recibimos su ubicación</h4>
      {#if status?.last_update}<p>Última señal {timeAgo(status.last_update, Date.now())}.</p>{/if}
    {:else if failures >= 2}
      <h4>No podemos comprobar la señal</h4>
      <p>Revisa tu conexión; seguimos intentando.</p>
    {:else if silent && status?.last_update}
      <h4>Sin señal {timeAgo(status.last_update, Date.now())}</h4>
      <p>Seguimos atentos: en cuanto llegue, te avisamos aquí.</p>
    {:else}
      <h4>Esperando la señal del {noun}…</h4>
      <p>
        {status?.state === 'unavailable'
          ? 'El servidor GPS no responde ahora; seguimos intentando.'
          : 'Puede tardar uno o dos minutos. De ser posible, deja el vehículo al aire libre.'}
      </p>
    {/if}
  </div>
</div>

<!-- Montado siempre: un lector de pantalla anuncia la ayuda cuando aparece. -->
<div aria-live="polite">
  {#if showHelp}
    <section class="help">
      <h4>Revisa esto</h4>
      <ul>
        {#each checks as check (check)}<li>{check}</li>{/each}
      </ul>
    </section>
  {/if}
</div>

<style>
  .signal {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    padding: 20px 0;
    text-align: center;
  }
  .icon {
    position: relative;
    display: flex;
    width: 76px;
    height: 76px;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    color: rgb(var(--foreground));
    background: rgb(var(--surface-muted));
  }
  .good .icon {
    color: rgb(var(--success));
    background: rgb(var(--success) / 14%);
  }
  .pulse {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 2px solid rgb(var(--foreground-muted));
    animation: pulse 2s ease-out infinite;
  }
  h4 {
    margin: 0;
    color: rgb(var(--foreground));
    font-size: 16px;
    font-weight: 600;
  }
  p {
    margin: 4px 0 0;
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  .help {
    padding: 14px;
    border: 1px solid rgb(var(--warning) / 45%);
    border-radius: 12px;
    background: rgb(var(--warning) / 10%);
  }
  .help ul {
    display: grid;
    gap: 6px;
    margin: 8px 0 0;
    padding-left: 18px;
    color: rgb(var(--foreground));
    font-size: 14px;
  }
  @media (prefers-reduced-motion: reduce) {
    .pulse {
      animation: none;
      opacity: 0.5;
    }
  }
  @keyframes pulse {
    from {
      opacity: 0.7;
      transform: scale(1);
    }
    to {
      opacity: 0;
      transform: scale(1.35);
    }
  }
</style>
