<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type FleetVehicle, type OdometerReading } from './api';
  import { formatDateTime, formatNumber } from './catalog';

  let { vehicle, onchanged }: { vehicle: FleetVehicle; onchanged: () => void } = $props();

  const SOURCE_LABELS: Record<OdometerReading['source'], string> = {
    manual: 'Manual',
    fuel: 'Carga de combustible',
    maintenance: 'Mantenimiento',
    gps: 'GPS'
  };

  let readings = $state<OdometerReading[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let reading = $state('');
  let notes = $state('');
  let saving = $state(false);
  let formError = $state<string | null>(null);

  const canRecord = $derived(
    permissions.hasPermission('fleet:maintenance') && vehicle.status !== 'retired'
  );
  const tooLow = $derived(reading !== '' && Number(reading) < Number(vehicle.odometer_km));

  async function load() {
    loading = true;
    error = null;
    try {
      readings = await fleetApi.odometer(vehicle.id);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar el odómetro.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void vehicle.id;
    void load();
  });

  async function save() {
    saving = true;
    formError = null;
    try {
      await fleetApi.addOdometer(vehicle.id, {
        reading_km: reading,
        notes: notes.trim() || undefined
      });
      reading = '';
      notes = '';
      await load();
      onchanged();
    } catch (err) {
      formError = err instanceof HttpError ? err.message : 'No se pudo registrar la lectura.';
    } finally {
      saving = false;
    }
  }
</script>

<div class="panel">
  <section class="card">
    <h2>Odómetro actual</h2>
    <p class="current">{formatNumber(vehicle.odometer_km)} <small>km</small></p>
    <p class="muted">
      Las lecturas nunca retroceden. También se registran al cargar combustible y al cerrar un
      mantenimiento.
    </p>
    {#if canRecord}
      <div class="form">
        <label>
          <span>Nueva lectura (km)</span>
          <input type="number" min={vehicle.odometer_km} step="0.1" bind:value={reading} />
        </label>
        <label>
          <span>Nota</span>
          <input bind:value={notes} maxlength="500" placeholder="Opcional" />
        </label>
        {#if tooLow}
          <p class="error">La lectura no puede ser menor que la actual.</p>
        {/if}
        {#if formError}<p class="error" role="alert">{formError}</p>{/if}
        <div class="actions">
          <Button size="sm" disabled={saving || reading === '' || tooLow} onclick={save}
            >Registrar lectura</Button
          >
        </div>
      </div>
    {/if}
  </section>

  <section class="card">
    <h2>Historial de lecturas</h2>
    {#if loading && readings.length === 0}
      <p class="muted">Cargando…</p>
    {:else if error}
      <p class="error" role="alert">{error}</p>
    {:else if readings.length === 0}
      <p class="muted">Sin lecturas registradas.</p>
    {:else}
      <table>
        <thead>
          <tr><th>Fecha</th><th class="num">Lectura</th><th>Origen</th><th>Registró</th></tr>
        </thead>
        <tbody>
          {#each readings as item (item.id)}
            <tr>
              <td>
                {formatDateTime(item.read_at)}
                {#if item.notes}<small>{item.notes}</small>{/if}
              </td>
              <td class="num">{formatNumber(item.reading_km)} km</td>
              <td>{SOURCE_LABELS[item.source]}</td>
              <td>{item.recorded_by_name ?? '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>
</div>

<style>
  .panel {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
    gap: 16px;
    align-items: start;
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
  .current {
    font-size: 26px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .current small {
    font-size: 13px;
    color: rgb(var(--foreground-muted));
  }
  .muted,
  td small {
    display: block;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .form {
    display: grid;
    gap: 10px;
    margin-top: 14px;
  }
  label {
    display: grid;
    gap: 6px;
    font-size: 12px;
    font-weight: 500;
  }
  input {
    min-height: 38px;
    padding: 0 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  .actions {
    display: flex;
    justify-content: flex-end;
  }
  .error {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }
  th,
  td {
    padding: 8px 10px;
    border-bottom: 1px solid rgb(var(--border));
    text-align: left;
  }
  th {
    font-weight: 600;
    color: rgb(var(--foreground-muted));
  }
  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  @media (max-width: 900px) {
    .panel {
      grid-template-columns: 1fr;
    }
  }
</style>
