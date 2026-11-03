<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { driversApi, type Driver } from '$lib/features/drivers/api';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type FleetVehicle, type FuelLog, type FuelStats } from './api';
  import { formatDateTime, formatMoney, formatNumber, isBlank } from './catalog';

  let { vehicle, onchanged }: { vehicle: FleetVehicle; onchanged: () => void } = $props();

  let logs = $state<FuelLog[]>([]);
  let stats = $state<FuelStats | null>(null);
  let drivers = $state<Driver[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let open = $state(false);
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let form = $state({
    filled_at: '',
    liters: '',
    total_amount: '',
    odometer_km: '',
    full_tank: true,
    station: '',
    driver_id: ''
  });

  const canLog = $derived(permissions.hasPermission('fleet:fuel') && vehicle.status !== 'retired');
  const unitPrice = $derived(
    Number(form.liters) > 0 && form.total_amount !== ''
      ? Number(form.total_amount) / Number(form.liters)
      : null
  );

  function localNow(): string {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 16);
  }

  async function load() {
    loading = true;
    error = null;
    try {
      const result = await fleetApi.fuel(vehicle.id);
      logs = result.items;
      stats = result.stats;
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar el combustible.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void vehicle.id;
    void load();
  });

  async function openForm() {
    form = {
      filled_at: localNow(),
      liters: '',
      total_amount: '',
      odometer_km: '',
      full_tank: true,
      station: '',
      driver_id: vehicle.driver?.driver_id ?? ''
    };
    formError = null;
    open = true;
    if (permissions.hasPermission('drivers:read') && drivers.length === 0) {
      try {
        drivers = (await driversApi.forBranch(vehicle.branch_id)).items;
      } catch {
        drivers = [];
      }
    }
  }

  async function save() {
    saving = true;
    formError = null;
    try {
      await fleetApi.addFuel(vehicle.id, {
        filled_at: new Date(form.filled_at).toISOString(),
        liters: form.liters,
        total_amount: form.total_amount,
        odometer_km: form.odometer_km,
        full_tank: form.full_tank,
        station: form.station.trim() || null,
        driver_id: form.driver_id || null
      });
      open = false;
      await load();
      onchanged();
    } catch (err) {
      formError = err instanceof HttpError ? err.message : 'No se pudo registrar la carga.';
    } finally {
      saving = false;
    }
  }
</script>

<div class="panel">
  <div class="kpis">
    <div><span>Litros cargados</span><strong>{formatNumber(stats?.liters)}</strong></div>
    <div><span>Gasto total</span><strong>{formatMoney(stats?.amount)}</strong></div>
    <div>
      <span>Rendimiento promedio</span>
      <strong
        >{stats?.average_km_per_liter
          ? `${formatNumber(stats.average_km_per_liter)} km/L`
          : '—'}</strong
      >
    </div>
    <div>
      <span>Costo por km</span>
      <strong>{stats?.cost_per_km ? formatMoney(stats.cost_per_km) : '—'}</strong>
    </div>
  </div>

  <section class="card">
    <header>
      <div>
        <h2>Cargas de combustible</h2>
        <p class="muted">
          El rendimiento se mide entre tanques llenos. Cada carga registra también el odómetro.
        </p>
      </div>
      {#if canLog}<Button size="sm" onclick={openForm}>Registrar carga</Button>{/if}
    </header>
    {#if loading && logs.length === 0}
      <p class="muted">Cargando…</p>
    {:else if error}
      <p class="error" role="alert">{error}</p>
    {:else if logs.length === 0}
      <p class="muted">Sin cargas registradas.</p>
    {:else}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Fecha</th><th>Estación</th><th>Conductor</th><th class="num">Odómetro</th>
              <th class="num">Litros</th><th class="num">Precio/L</th><th class="num">Total</th>
              <th class="num">km/L</th>
            </tr>
          </thead>
          <tbody>
            {#each logs as log (log.id)}
              <tr>
                <td>{formatDateTime(log.filled_at)}{log.full_tank ? '' : ' · parcial'}</td>
                <td>{log.station ?? '—'}</td>
                <td>{log.driver_name ?? '—'}</td>
                <td class="num">{formatNumber(log.odometer_km)} km</td>
                <td class="num">{formatNumber(log.liters)}</td>
                <td class="num">{formatMoney(log.unit_price)}</td>
                <td class="num">{formatMoney(log.total_amount)}</td>
                <td class="num">{log.km_per_liter ? formatNumber(log.km_per_liter) : '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>
</div>

<Modal {open} title="Registrar carga de combustible" onclose={() => (open = false)}>
  <div class="form">
    <div class="pair">
      <label
        ><span>Fecha y hora</span><input type="datetime-local" bind:value={form.filled_at} /></label
      >
      <label>
        <span>Odómetro (km)</span>
        <input
          type="number"
          min="0"
          step="0.1"
          bind:value={form.odometer_km}
          placeholder={`≥ ${vehicle.odometer_km}`}
        />
      </label>
    </div>
    <div class="pair">
      <label
        ><span>Litros</span><input
          type="number"
          min="0"
          step="0.001"
          bind:value={form.liters}
        /></label
      >
      <label
        ><span>Total (USD)</span><input
          type="number"
          min="0"
          step="0.01"
          bind:value={form.total_amount}
        /></label
      >
    </div>
    {#if unitPrice !== null}<p class="muted">Precio por litro: {formatMoney(unitPrice)}</p>{/if}
    <div class="pair">
      <label><span>Estación</span><input bind:value={form.station} maxlength="160" /></label>
      {#if drivers.length}
        <label>
          <span>Conductor</span>
          <select bind:value={form.driver_id}>
            <option value="">Sin conductor</option>
            {#each drivers as driver (driver.id)}
              <option value={driver.id}>{driver.employee.name}</option>
            {/each}
          </select>
        </label>
      {/if}
    </div>
    <label class="check">
      <input type="checkbox" bind:checked={form.full_tank} />
      <span>Tanque lleno (necesario para calcular rendimiento)</span>
    </label>
    {#if formError}<p class="error" role="alert">{formError}</p>{/if}
    <div class="actions">
      <Button variant="secondary" onclick={() => (open = false)}>Cancelar</Button>
      <Button
        disabled={saving ||
          !form.filled_at ||
          !(Number(form.liters) > 0) ||
          isBlank(form.total_amount) ||
          isBlank(form.odometer_km)}
        onclick={save}>Registrar</Button
      >
    </div>
  </div>
</Modal>

<style>
  .panel {
    display: grid;
    gap: 16px;
  }
  .kpis {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }
  .kpis div {
    display: grid;
    gap: 4px;
    padding: 14px 16px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  .kpis span {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .kpis strong {
    font-size: 18px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .card {
    padding: 18px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }
  h2 {
    font-size: 13px;
    font-weight: 600;
  }
  .muted {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .table-wrap {
    overflow-x: auto;
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
    white-space: nowrap;
  }
  th {
    font-weight: 600;
    color: rgb(var(--foreground-muted));
  }
  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .form {
    display: grid;
    gap: 12px;
  }
  .pair {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  label {
    display: grid;
    gap: 6px;
    font-size: 12px;
    font-weight: 500;
  }
  .check {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  input:not([type='checkbox']),
  select {
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
    gap: 8px;
  }
  .error {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  @media (max-width: 900px) {
    .kpis {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .pair {
      grid-template-columns: 1fr;
    }
  }
</style>
