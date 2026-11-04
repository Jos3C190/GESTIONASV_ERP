<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import { driversApi, type Assignment, type Driver } from '$lib/features/drivers/api';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { FleetVehicle } from './api';
  import { formatDate, LICENSE_LABELS, localDate } from './catalog';
  import FleetIcon from './FleetIcon.svelte';

  let { vehicle, onchanged }: { vehicle: FleetVehicle; onchanged: () => void } = $props();

  let drivers = $state<Driver[]>([]);
  let history = $state<Assignment[]>([]);
  let selectedDriver = $state('');
  let overrideReason = $state('');
  let temporary = $state(false);
  let expectedEnd = $state('');
  let endReason = $state('');
  let ending = $state(false);
  let saving = $state(false);
  let error = $state<string | null>(null);

  const canAssign = $derived(permissions.hasPermission('drivers:assign'));
  const canOverride = $derived(permissions.hasPermission('fleet:compliance_override'));
  const today = localDate(new Date());
  const overdueCover = $derived(
    Boolean(vehicle.driver?.expected_end_on && vehicle.driver.expected_end_on < today)
  );
  const candidate = $derived(drivers.find((item) => item.id === selectedDriver) ?? null);
  const candidateBlocking = $derived(
    candidate?.compliance.issues.filter((issue) => issue.severity === 'blocking') ?? []
  );

  async function load() {
    error = null;
    try {
      const [list, assignments] = await Promise.all([
        canAssign
          ? driversApi.forBranch(vehicle.branch_id)
          : Promise.resolve({ items: [] as Driver[] }),
        driversApi.vehicleAssignments(vehicle.id)
      ]);
      drivers = list.items.filter((item) => item.id !== vehicle.driver?.driver_id);
      history = assignments;
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar la información.';
    }
  }

  $effect(() => {
    void vehicle.id;
    void vehicle.driver?.driver_id;
    void load();
  });

  async function assign() {
    saving = true;
    error = null;
    try {
      await driversApi.assign(vehicle.id, selectedDriver, overrideReason.trim() || undefined, {
        expected_end_on: temporary ? expectedEnd : null,
        // Se cubre a quien tiene el vehículo ahora; a él vuelve después.
        // Si ya era una cobertura, el titular sigue siendo el mismo.
        covers_driver_id: temporary
          ? (vehicle.driver?.covers_driver_id ?? vehicle.driver?.driver_id ?? null)
          : null
      });
      selectedDriver = '';
      overrideReason = '';
      temporary = false;
      expectedEnd = '';
      onchanged();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo asignar el conductor.';
    } finally {
      saving = false;
    }
  }

  function giveBack() {
    const titular = vehicle.driver?.covers_driver_id;
    if (!titular) return;
    confirmation.request({
      kind: 'restore',
      title: 'Devolver el vehículo',
      description:
        'Termina la cobertura. Si el titular tiene otro vehículo asignado, esa asignación se cierra.',
      resourceName: vehicle.driver?.covers_driver_name ?? undefined,
      confirmLabel: 'Devolver',
      // No se revierte sola: el titular puede no estar disponible, y el diálogo dice por qué.
      execute: async () => {
        await driversApi.assign(vehicle.id, titular);
        onchanged();
      }
    });
  }

  async function end() {
    saving = true;
    error = null;
    try {
      await driversApi.endAssignment(vehicle.id, endReason.trim());
      ending = false;
      endReason = '';
      onchanged();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo finalizar la asignación.';
    } finally {
      saving = false;
    }
  }
</script>

<div class="panel">
  <section class="card">
    <h2>Conductor actual</h2>
    {#if vehicle.driver}
      <div class="current">
        <span class="avatar">{vehicle.driver.initials}</span>
        <span class="who">
          <a href={`/drivers/${vehicle.driver.driver_id}`}><strong>{vehicle.driver.name}</strong></a
          >
          <small
            >Licencia {LICENSE_LABELS[vehicle.driver.license_class]} · desde {formatDate(
              vehicle.driver.since
            )}</small
          >
          {#if vehicle.driver.expected_end_on}
            <small class:late={overdueCover}>
              Temporal hasta el {formatDate(vehicle.driver.expected_end_on)}{vehicle.driver
                .covers_driver_name
                ? ` · cubre a ${vehicle.driver.covers_driver_name}`
                : ''}
            </small>
          {/if}
        </span>
        {#if canAssign && !ending && vehicle.driver.covers_driver_id}
          <Button size="sm" onclick={giveBack}>
            Devolver a {vehicle.driver.covers_driver_name}
          </Button>
        {/if}
        {#if canAssign && !ending}
          <Button size="sm" variant="secondary" onclick={() => (ending = true)}
            >Finalizar asignación</Button
          >
        {/if}
      </div>
      {#if ending}
        <div class="inline-form">
          <label>
            <span>Motivo</span>
            <input bind:value={endReason} maxlength="500" placeholder="Ej. cambio de turno" />
          </label>
          <Button size="sm" variant="secondary" onclick={() => (ending = false)}>Cancelar</Button>
          <Button size="sm" disabled={saving || endReason.trim().length < 3} onclick={end}
            >Confirmar</Button
          >
        </div>
      {/if}
    {:else}
      <p class="muted">Este vehículo no tiene conductor asignado.</p>
    {/if}
  </section>

  {#if canAssign && vehicle.status !== 'retired'}
    <section class="card">
      <h2>{vehicle.driver ? 'Reasignar a otro conductor' : 'Asignar conductor'}</h2>
      <p class="muted">
        Solo conductores activos de {vehicle.branch_name}. Asignar cierra la asignación anterior del
        vehículo y la del conductor.
      </p>
      {#if drivers.length === 0}
        <p class="muted">
          No hay otros conductores activos en la sucursal. <a href="/drivers">Registrar conductor</a
          >
        </p>
      {:else}
        <label class="field">
          <span>Conductor</span>
          <select bind:value={selectedDriver}>
            <option value="">Seleccione…</option>
            {#each drivers as driver (driver.id)}
              <option value={driver.id}
                >{driver.employee.name} · {LICENSE_LABELS[driver.license.license_class]}{driver
                  .compliance.state === 'blocked'
                  ? ' · no apto'
                  : ''}</option
              >
            {/each}
          </select>
        </label>
        {#if candidate && candidateBlocking.length}
          <ul class="blocking">
            {#each candidateBlocking as issue, index (index)}
              <li><FleetIcon name="alert" size={13} />{issue.message}</li>
            {/each}
          </ul>
          {#if canOverride}
            <label class="field">
              <span>Motivo de la excepción (queda auditado)</span>
              <input bind:value={overrideReason} maxlength="500" />
            </label>
          {:else}
            <p class="muted">Solo un usuario autorizado para excepciones puede asignarlo.</p>
          {/if}
        {/if}
        <label class="temporary">
          <input type="checkbox" bind:checked={temporary} />
          <span>Es temporal{vehicle.driver ? `: cubre a ${vehicle.driver.name}` : ''}</span>
        </label>
        {#if temporary}
          <label class="field">
            <span>Hasta</span>
            <input type="date" min={today} bind:value={expectedEnd} />
          </label>
          {#if !expectedEnd || expectedEnd < today}
            <p class="muted">Indica hasta cuándo dura, desde hoy en adelante.</p>
          {/if}
        {/if}
        <div class="actions">
          <Button
            size="sm"
            disabled={saving ||
              !selectedDriver ||
              (temporary && (!expectedEnd || expectedEnd < today)) ||
              (candidateBlocking.length > 0 && (!canOverride || overrideReason.trim().length < 5))}
            onclick={assign}>{saving ? 'Asignando…' : 'Asignar'}</Button
          >
        </div>
      {/if}
    </section>
  {/if}

  {#if error}<p class="error" role="alert">{error}</p>{/if}

  <section class="card wide">
    <h2>Historial de conductores</h2>
    {#if history.length === 0}
      <p class="muted">Sin asignaciones registradas.</p>
    {:else}
      <table>
        <thead>
          <tr><th>Conductor</th><th>Desde</th><th>Hasta</th><th>Motivo de cierre</th></tr>
        </thead>
        <tbody>
          {#each history as item (item.id)}
            <tr>
              <td><a href={`/drivers/${item.driver_id}`}>{item.driver_name}</a></td>
              <td>{formatDate(item.starts_at)}</td>
              <td>{item.ends_at ? formatDate(item.ends_at) : 'Actual'}</td>
              <td>{item.end_reason ?? '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>
</div>

<style>
  .late {
    color: rgb(var(--warning));
  }
  .temporary {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    font-size: 13px;
  }
  .panel {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }
  .card {
    padding: 18px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  .wide,
  .error {
    grid-column: 1 / -1;
  }
  h2 {
    margin-bottom: 10px;
    font-size: 13px;
    font-weight: 600;
  }
  .current {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .who {
    display: grid;
    flex: 1;
    gap: 2px;
  }
  .avatar {
    display: grid;
    place-items: center;
    width: 38px;
    height: 38px;
    border: 1px solid rgb(var(--border));
    border-radius: 50%;
    background: rgb(var(--surface-hover));
    font-size: 12px;
    font-weight: 600;
  }
  strong {
    font-size: 13px;
  }
  small,
  .muted {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .muted a {
    color: rgb(var(--primary));
  }
  .inline-form {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 8px;
    margin-top: 12px;
  }
  .inline-form label,
  .field {
    display: grid;
    flex: 1;
    gap: 6px;
    margin-top: 10px;
    font-size: 12px;
    font-weight: 500;
  }
  input,
  select {
    min-height: 38px;
    padding: 0 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  .blocking {
    display: grid;
    gap: 5px;
    margin: 10px 0 0;
    padding: 9px 11px;
    border-radius: 8px;
    background: rgb(var(--danger) / 0.07);
    color: rgb(var(--danger));
    font-size: 12px;
    list-style: none;
  }
  .blocking li {
    display: flex;
    gap: 6px;
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 12px;
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
  td a {
    color: rgb(var(--primary));
  }
  @media (max-width: 900px) {
    .panel {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
