<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type FleetVehicle } from './api';
  import FleetIcon from './FleetIcon.svelte';

  let { vehicle, onchanged }: { vehicle: FleetVehicle; onchanged: (next: FleetVehicle) => void } =
    $props();

  let uniqueId = $state('');
  let saving = $state(false);
  let confirmUnlink = $state(false);
  let error = $state<string | null>(null);

  const canManage = $derived(
    permissions.hasPermission('fleet:gps') && vehicle.status !== 'retired'
  );
  const canTrack = $derived(permissions.hasPermission('tracking:read'));
  const valid = $derived(/^[A-Za-z0-9._-]{3,64}$/.test(uniqueId.trim()));

  async function run(action: () => Promise<FleetVehicle>) {
    saving = true;
    error = null;
    try {
      onchanged(await action());
      uniqueId = '';
      confirmUnlink = false;
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo actualizar el GPS.';
    } finally {
      saving = false;
    }
  }
</script>

<div class="panel">
  <section class="card">
    <h2>Dispositivo GPS</h2>
    {#if vehicle.gps_linked}
      <p class="linked">
        <FleetIcon name="check" size={14} />Vinculado · <code>{vehicle.gps_device_unique_id}</code>
      </p>
      <p class="muted">
        El dispositivo aparece en Seguimiento con el código {vehicle.code} y solo lo ven los usuarios
        de {vehicle.branch_name} o con acceso a todas las sucursales.
      </p>
      {#if canTrack}<a class="link" href="/tracking">Ver en Seguimiento</a>{/if}
    {:else}
      <p class="muted">
        Sin GPS vinculado. Registra el identificador (IMEI) que el equipo reporta al servidor GPS.
      </p>
    {/if}

    {#if canManage}
      <div class="form">
        <label>
          <span
            >{vehicle.gps_linked
              ? 'Reemplazar por otro dispositivo'
              : 'Identificador del equipo'}</span
          >
          <input bind:value={uniqueId} maxlength="64" placeholder="Ej. 358240051111110" />
        </label>
        <Button
          size="sm"
          disabled={saving || !valid}
          onclick={() => run(() => fleetApi.linkGps(vehicle.id, uniqueId.trim()))}
          >{saving ? 'Guardando…' : 'Vincular'}</Button
        >
      </div>
      {#if vehicle.gps_linked}
        <div class="unlink">
          {#if confirmUnlink}
            <span class="muted">El vehículo dejará de verse en Seguimiento.</span>
            <Button size="sm" variant="secondary" onclick={() => (confirmUnlink = false)}
              >Cancelar</Button
            >
            <Button
              size="sm"
              variant="danger"
              disabled={saving}
              onclick={() => run(() => fleetApi.unlinkGps(vehicle.id))}>Desvincular</Button
            >
          {:else}
            <Button size="sm" variant="secondary" onclick={() => (confirmUnlink = true)}
              >Desvincular GPS</Button
            >
          {/if}
        </div>
      {/if}
    {/if}
    {#if error}<p class="error" role="alert">{error}</p>{/if}
  </section>
</div>

<style>
  .panel {
    max-width: 640px;
  }
  .card {
    padding: 18px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  h2 {
    margin-bottom: 10px;
    font-size: 13px;
    font-weight: 600;
  }
  .linked {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
    color: rgb(var(--success));
    font-size: 13px;
    font-weight: 500;
  }
  code {
    font-family: ui-monospace, monospace;
    color: rgb(var(--foreground));
  }
  .muted {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .link {
    display: inline-block;
    margin-top: 8px;
    font-size: 12px;
    font-weight: 500;
    color: rgb(var(--primary));
  }
  .form {
    display: flex;
    align-items: flex-end;
    gap: 8px;
    margin-top: 16px;
  }
  label {
    display: grid;
    flex: 1;
    gap: 6px;
    font-size: 12px;
    font-weight: 500;
  }
  input {
    min-height: 36px;
    padding: 0 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  .unlink {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-top: 14px;
  }
  .error {
    margin-top: 10px;
    color: rgb(var(--danger));
    font-size: 12px;
  }
</style>
