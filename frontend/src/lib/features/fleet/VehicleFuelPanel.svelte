<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { driversApi, type Driver } from '$lib/features/drivers/api';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type FleetVehicle, type FuelLog, type FuelStats } from './api';
  import {
    formatDateTime,
    formatMoney,
    formatNumber,
    isBlank,
    meterName,
    meterShort
  } from './catalog';
  import ReceiptField from './ReceiptField.svelte';
  import ReceiptLink from './ReceiptLink.svelte';
  import SupplierField from './SupplierField.svelte';

  let { vehicle, onchanged }: { vehicle: FleetVehicle; onchanged: () => void } = $props();

  const unit = $derived(meterShort(vehicle.type.meter_unit));

  let logs = $state<FuelLog[]>([]);
  let stats = $state<FuelStats | null>(null);
  let drivers = $state<Driver[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let open = $state(false);
  let correcting = $state<FuelLog | null>(null);
  let reason = $state('');
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let form = $state({
    filled_at: '',
    liters: '',
    total_amount: '',
    odometer_km: '',
    full_tank: true,
    station: '',
    supplier_id: '',
    receipt_document_id: '',
    driver_id: ''
  });

  const canLog = $derived(permissions.hasPermission('fleet:fuel') && vehicle.status !== 'retired');
  const canCorrect = $derived(
    permissions.hasPermission('fleet:correct_records') && vehicle.status !== 'retired'
  );
  const overTank = $derived(
    Boolean(vehicle.tank_liters) && Number(form.liters) > Number(vehicle.tank_liters)
  );
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

  function toLocal(iso: string): string {
    const date = new Date(iso);
    date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    return date.toISOString().slice(0, 16);
  }

  function askVoid(log: FuelLog) {
    confirmation.request({
      kind: 'revoke',
      title: 'Anular carga',
      description:
        'Dejará de contar en gasto y rendimiento, y también su lectura. Queda en el historial, tachada.',
      confirmLabel: 'Anular',
      requireReason: true,
      reasonLabel: 'Motivo',
      execute: async (why) => {
        await fleetApi.voidFuel(vehicle.id, log.id, why ?? '');
        await load();
        onchanged();
      }
    });
  }

  async function openForm(log: FuelLog | null = null) {
    correcting = log;
    reason = '';
    form = {
      filled_at: log ? toLocal(log.filled_at) : localNow(),
      liters: log ? String(Number(log.liters)) : '',
      total_amount: log ? String(Number(log.total_amount)) : '',
      odometer_km: log ? String(Number(log.odometer_km)) : '',
      full_tank: log?.full_tank ?? true,
      station: log?.station ?? '',
      supplier_id: log?.supplier_id ? String(log.supplier_id) : '',
      receipt_document_id: log?.receipt_document_id ?? '',
      driver_id: log ? (log.driver_id ?? '') : (vehicle.driver?.driver_id ?? '')
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
      const data = {
        filled_at: new Date(form.filled_at).toISOString(),
        liters: String(form.liters),
        total_amount: String(form.total_amount),
        odometer_km: String(form.odometer_km),
        full_tank: form.full_tank,
        station: form.supplier_id ? null : form.station.trim() || null,
        supplier_id: form.supplier_id ? Number(form.supplier_id) : null,
        receipt_document_id: form.receipt_document_id || null,
        driver_id: form.driver_id || null
      };
      if (correcting) {
        await fleetApi.correctFuel(vehicle.id, correcting.id, { ...data, reason: reason.trim() });
      } else {
        await fleetApi.addFuel(vehicle.id, data);
      }
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
          ? `${formatNumber(stats.average_km_per_liter)} ${unit}/L`
          : '—'}</strong
      >
    </div>
    <div>
      <span>Costo por {unit}</span>
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
      {#if canLog}<Button size="sm" onclick={() => openForm()}>Registrar carga</Button>{/if}
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
              <th class="num">{unit}/L</th>
              {#if canCorrect}<th><span class="sr-only">Acciones</span></th>{/if}
            </tr>
          </thead>
          <tbody>
            {#each logs as log (log.id)}
              <tr class:voided={log.voided_at}>
                <td>
                  {formatDateTime(log.filled_at)}{log.full_tank ? '' : ' · parcial'}
                  {#if log.voided_at}
                    <small class="void-note">
                      Anulada por {log.voided_by_name ?? '—'}: {log.void_reason}
                    </small>
                  {/if}
                </td>
                <td>
                  {log.station ?? '—'}
                  {#if log.receipt_document_id}
                    <ReceiptLink vehicleId={vehicle.id} documentId={log.receipt_document_id} />
                  {/if}
                </td>
                <td>{log.driver_name ?? '—'}</td>
                <td class="num">{formatNumber(log.odometer_km)} {unit}</td>
                <td class="num">{formatNumber(log.liters)}</td>
                <td class="num">{formatMoney(log.unit_price)}</td>
                <td class="num">{formatMoney(log.total_amount)}</td>
                <td class="num">{log.km_per_liter ? formatNumber(log.km_per_liter) : '—'}</td>
                {#if canCorrect}
                  <td class="row-action">
                    {#if !log.voided_at}
                      <button type="button" onclick={() => openForm(log)}>Corregir</button>
                      <button type="button" onclick={() => askVoid(log)}>Anular</button>
                    {/if}
                  </td>
                {/if}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>
</div>

<Modal
  {open}
  title={correcting ? 'Corregir carga' : 'Registrar carga de combustible'}
  onclose={() => (open = false)}
>
  <div class="form">
    <div class="pair">
      <label
        ><span>Fecha y hora</span><input type="datetime-local" bind:value={form.filled_at} /></label
      >
      <label>
        <span>{meterName(vehicle.type.meter_unit)} ({unit})</span>
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
    {#if overTank}
      <p class="warn">
        Supera el tanque de este vehículo ({formatNumber(vehicle.tank_liters)} L). Revisa los litros.
      </p>
    {/if}
    {#if vehicle.fuel_type === 'electric'}
      <p class="warn">Este vehículo está registrado como eléctrico. Revisa que sea correcto.</p>
    {/if}
    {#if correcting}
      <label>
        <span>Motivo de la corrección</span>
        <input bind:value={reason} maxlength="500" placeholder="Ej. Litros mal digitados" />
      </label>
    {/if}
    <div class="pair">
      <SupplierField
        id="fuel-station"
        label="Estación"
        bind:supplierId={form.supplier_id}
        bind:text={form.station}
      />
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
    <ReceiptField id="fuel-receipt" vehicleId={vehicle.id} bind:value={form.receipt_document_id} />
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
          isBlank(form.odometer_km) ||
          (correcting !== null && reason.trim().length < 3)}
        onclick={save}>{correcting ? 'Guardar corrección' : 'Registrar'}</Button
      >
    </div>
  </div>
</Modal>

<style>
  .voided td {
    color: rgb(var(--foreground-muted));
  }
  .voided .num {
    text-decoration: line-through;
  }
  .void-note {
    display: block;
  }
  .warn {
    margin: 0;
    color: rgb(var(--warning));
    font-size: 13px;
  }
  .row-action {
    white-space: nowrap;
  }
  .row-action button {
    min-height: 44px;
    margin-right: 8px;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
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
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
