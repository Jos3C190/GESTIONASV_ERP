<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type FleetVehicle, type OdometerReading } from './api';
  import {
    formatDateTime,
    formatNumber,
    isBlank,
    meterJumpLimit,
    meterName,
    meterShort
  } from './catalog';

  let { vehicle, onchanged }: { vehicle: FleetVehicle; onchanged: () => void } = $props();

  const SOURCE_LABELS: Record<OdometerReading['source'], string> = {
    manual: 'Manual',
    fuel: 'Carga de combustible',
    maintenance: 'Mantenimiento',
    gps: 'GPS',
    meter_replacement: 'Cambio de tablero'
  };

  let readings = $state<OdometerReading[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let reading = $state('');
  let notes = $state('');
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let total = $state<{ total: string; replacements: number } | null>(null);
  let replaceOpen = $state(false);
  let replaceReading = $state('');
  let replaceReason = $state('');
  let replaceError = $state<string | null>(null);

  const canRecord = $derived(
    permissions.hasPermission('fleet:maintenance') && vehicle.status !== 'retired'
  );
  const unit = $derived(meterShort(vehicle.type.meter_unit));
  const canCorrect = $derived(
    permissions.hasPermission('fleet:correct_records') && vehicle.status !== 'retired'
  );
  const jump = $derived(
    !isBlank(reading) &&
      Number(reading) - Number(vehicle.odometer_km) > meterJumpLimit(vehicle.type.meter_unit)
  );
  const tooLow = $derived(!isBlank(reading) && Number(reading) < Number(vehicle.odometer_km));

  async function load() {
    loading = true;
    error = null;
    try {
      const [items, summary] = await Promise.all([
        fleetApi.odometer(vehicle.id),
        fleetApi.odometerTotal(vehicle.id)
      ]);
      readings = items;
      total = summary;
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

  function save() {
    if (!jump) return void record();
    confirmation.request({
      kind: 'confirm',
      title: '¿La lectura es correcta?',
      description: `Es ${formatNumber(Number(reading) - Number(vehicle.odometer_km))} ${unit} más que la actual. Revisa que no sobre un dígito.`,
      confirmLabel: 'Sí, registrar',
      execute: record
    });
  }

  function askVoid(item: OdometerReading) {
    confirmation.request({
      kind: 'revoke',
      title: 'Anular lectura',
      description: `La lectura de ${formatNumber(item.reading_km)} ${unit} dejará de contar. Queda en el historial, tachada.`,
      confirmLabel: 'Anular',
      requireReason: true,
      reasonLabel: 'Motivo',
      execute: async (why) => {
        await fleetApi.voidReading(vehicle.id, item.id, why ?? '');
        await load();
        onchanged();
      }
    });
  }

  function openReplace() {
    replaceReading = '';
    replaceReason = '';
    replaceError = null;
    replaceOpen = true;
  }

  async function replaceMeter() {
    saving = true;
    replaceError = null;
    try {
      await fleetApi.replaceMeter(vehicle.id, {
        reading_km: String(replaceReading),
        reason: replaceReason.trim()
      });
      replaceOpen = false;
      await load();
      onchanged();
    } catch (err) {
      replaceError = err instanceof HttpError ? err.message : 'No se pudo registrar el cambio.';
    } finally {
      saving = false;
    }
  }

  async function record() {
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
    <h2>{meterName(vehicle.type.meter_unit)} actual</h2>
    <p class="current">{formatNumber(vehicle.odometer_km)} <small>{unit}</small></p>
    {#if total && total.replacements > 0}
      <p class="muted">Recorrido total registrado: {formatNumber(total.total)} {unit}</p>
    {/if}
    <p class="muted">
      Las lecturas nunca retroceden. También se registran al cargar combustible y al cerrar un
      mantenimiento.
    </p>
    {#if canRecord}
      <div class="form">
        <label>
          <span>Nueva lectura ({unit})</span>
          <input type="number" min={vehicle.odometer_km} step="0.1" bind:value={reading} />
        </label>
        <label>
          <span>Nota</span>
          <input bind:value={notes} maxlength="500" placeholder="Opcional" />
        </label>
        {#if tooLow}
          <p class="error">
            La lectura no puede ser menor que la actual. Si la actual es un error, anúlala en el
            historial.
          </p>
        {/if}
        {#if jump}
          <p class="warn">Es un salto grande; te pediremos confirmarlo.</p>
        {/if}
        {#if formError}<p class="error" role="alert">{formError}</p>{/if}
        <div class="actions">
          <Button size="sm" disabled={saving || isBlank(reading) || tooLow} onclick={save}
            >Registrar lectura</Button
          >
        </div>
      </div>
    {/if}
    {#if canCorrect}
      <button type="button" class="link-action" onclick={openReplace}>
        ¿Le cambiaron el tablero? Registrar cambio
      </button>
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
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Fecha</th><th class="num">Lectura</th><th>Origen</th><th>Registró</th>
              {#if canCorrect}<th><span class="sr-only">Acciones</span></th>{/if}
            </tr>
          </thead>
          <tbody>
            {#each readings as item (item.id)}
              <tr class:voided={item.voided_at}>
                <td>
                  {formatDateTime(item.read_at)}
                  {#if item.notes}<small>{item.notes}</small>{/if}
                  {#if item.voided_at}
                    <small class="void-note">
                      Anulada por {item.voided_by_name ?? '—'}: {item.void_reason}
                    </small>
                  {/if}
                </td>
                <td class="num">{formatNumber(item.reading_km)} {unit}</td>
                <td>{SOURCE_LABELS[item.source]}</td>
                <td>{item.recorded_by_name ?? '—'}</td>
                {#if canCorrect}
                  <td class="row-action">
                    {#if !item.voided_at && item.source !== 'fuel'}
                      <button type="button" onclick={() => askVoid(item)}>Anular</button>
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

<Modal open={replaceOpen} title="Cambio de tablero" onclose={() => (replaceOpen = false)}>
  <div class="form">
    <p class="muted">
      El conteo sigue desde la lectura del tablero nuevo. Lo que falta para cada mantenimiento se
      conserva, y el recorrido anterior no se pierde.
    </p>
    <label>
      <span>Lectura del tablero nuevo ({unit})</span>
      <input type="number" min="0" step="0.1" bind:value={replaceReading} />
    </label>
    <label>
      <span>Motivo</span>
      <input bind:value={replaceReason} maxlength="500" placeholder="Ej. Tablero dañado" />
    </label>
    {#if replaceError}<p class="error" role="alert">{replaceError}</p>{/if}
    <div class="actions">
      <Button variant="secondary" onclick={() => (replaceOpen = false)}>Cancelar</Button>
      <Button
        disabled={saving || isBlank(replaceReading) || replaceReason.trim().length < 3}
        onclick={replaceMeter}>Registrar cambio</Button
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
    color: rgb(var(--foreground-muted));
  }
  .warn {
    margin: 0;
    color: rgb(var(--warning));
    font-size: 13px;
  }
  .link-action,
  .row-action button {
    min-height: 44px;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
    text-align: left;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
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
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
