<script lang="ts">
  import { tick } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type FleetLoan, type FleetReservation, type FleetVehicle } from './api';
  import { formatDate, formatDateTime, localDate, localDateTime } from './catalog';

  let { vehicle, onchanged }: { vehicle: FleetVehicle; onchanged: () => void } = $props();

  let panel = $state<HTMLElement | null>(null);
  let reservations = $state<FleetReservation[]>([]);
  let loans = $state<FleetLoan[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let saving = $state(false);
  let attempted = $state(false);
  let formError = $state<string | null>(null);
  let reserving = $state(false);
  let reserve = $state({ starts_at: '', ends_at: '', reason: '' });
  let lending = $state(false);
  let lend = $state({ to_branch_id: '', expected_return_on: '', reason: '' });
  let today = $state(localDate(new Date()));

  const canManageReservations = $derived(permissions.hasPermission('fleet:reservations'));
  const canReserve = $derived(canManageReservations && vehicle.status !== 'retired');
  const canLend = $derived(
    permissions.hasPermission('fleet:loans') && vehicle.status !== 'retired'
  );
  const onRoad = $derived(vehicle.operational_status === 'in_route');
  const openLoan = $derived(loans.find((item) => !item.returned_at) ?? null);
  const pastLoans = $derived(loans.filter((item) => item.returned_at));
  const upcoming = $derived(
    reservations.filter(
      (item) => item.status === 'active' && new Date(item.ends_at).getTime() > Date.now()
    )
  );
  const clashes = $derived(
    upcoming.filter(
      (item) =>
        lend.expected_return_on && localDate(new Date(item.starts_at)) <= lend.expected_return_on
    )
  );
  const branchOptions = $derived([
    { value: '', label: 'Elige la sucursal' },
    ...branch.branches
      .filter((item) => item.id !== vehicle.branch_id)
      .map((item) => ({ value: item.id, label: item.name }))
  ]);
  const startError = $derived(reserve.starts_at ? undefined : 'Indica cuándo empieza.');
  const endError = $derived(
    !reserve.ends_at
      ? 'Indica cuándo termina.'
      : reserve.starts_at && reserve.ends_at <= reserve.starts_at
        ? 'Debe terminar después de empezar.'
        : undefined
  );
  const reasonError = $derived(reserve.reason.trim().length >= 3 ? undefined : 'Indica el motivo.');
  const targetError = $derived(lend.to_branch_id ? undefined : 'Elige la sucursal.');
  const returnError = $derived(
    !lend.expected_return_on
      ? 'Indica cuándo vuelve.'
      : lend.expected_return_on < today
        ? 'No puede ser una fecha pasada.'
        : undefined
  );
  const lendReasonError = $derived(
    lend.reason.trim().length >= 3 ? undefined : 'Indica el motivo.'
  );

  function message(err: unknown, fallback: string): string {
    return err instanceof HttpError ? err.message : fallback;
  }

  async function load() {
    loading = true;
    error = null;
    try {
      [reservations, loans] = await Promise.all([
        fleetApi.reservations(vehicle.id),
        fleetApi.loans(vehicle.id)
      ]);
    } catch (err) {
      error = message(err, 'No se pudo cargar la agenda del vehículo.');
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void vehicle.id;
    void load();
  });

  async function focusFirst(id: string) {
    await tick();
    document.getElementById(id)?.focus();
  }

  async function showResult() {
    await tick();
    panel?.scrollIntoView?.({ block: 'start' });
  }

  function openReserve() {
    const start = new Date();
    reserve = {
      starts_at: localDateTime(start),
      ends_at: localDateTime(new Date(start.getTime() + 2 * 60 * 60 * 1000)),
      reason: ''
    };
    attempted = false;
    formError = null;
    success = null;
    reserving = true;
  }

  async function saveReserve(event: SubmitEvent) {
    event.preventDefault();
    attempted = true;
    if (startError || endError || reasonError) {
      await focusFirst(startError ? 'reserve-start' : endError ? 'reserve-end' : 'reserve-reason');
      return;
    }
    saving = true;
    formError = null;
    try {
      await fleetApi.addReservation(vehicle.id, {
        starts_at: new Date(reserve.starts_at).toISOString(),
        ends_at: new Date(reserve.ends_at).toISOString(),
        reason: reserve.reason.trim()
      });
      success = 'Reserva registrada.';
      reserving = false;
      await load();
      void showResult();
    } catch (err) {
      formError = message(err, 'No se pudo registrar la reserva.');
    } finally {
      saving = false;
    }
  }

  function askCancel(reservation: FleetReservation) {
    success = null;
    confirmation.request({
      kind: 'revoke',
      title: 'Cancelar reserva',
      description: 'Esas fechas volverán a quedar libres.',
      resourceName: reservation.reason,
      confirmLabel: 'Cancelar reserva',
      requireReason: true,
      reasonLabel: 'Motivo',
      execute: async (why) => {
        await fleetApi.cancelReservation(vehicle.id, reservation.id, why ?? '');
        success = 'Reserva cancelada.';
        await load();
      }
    });
  }

  function openLend() {
    today = localDate(new Date());
    lend = { to_branch_id: '', expected_return_on: '', reason: '' };
    attempted = false;
    formError = null;
    success = null;
    lending = true;
  }

  async function saveLend(event: SubmitEvent) {
    event.preventDefault();
    attempted = true;
    if (targetError || returnError || lendReasonError) {
      await focusFirst(targetError ? 'lend-branch' : returnError ? 'lend-return' : 'lend-reason');
      return;
    }
    saving = true;
    formError = null;
    try {
      await fleetApi.lend(vehicle.id, {
        to_branch_id: lend.to_branch_id,
        expected_return_on: lend.expected_return_on,
        reason: lend.reason.trim()
      });
      success = 'Vehículo prestado.';
      lending = false;
      await load();
      onchanged();
      void showResult();
    } catch (err) {
      formError = message(err, 'No se pudo prestar el vehículo.');
    } finally {
      saving = false;
    }
  }

  function askReturn(loan: FleetLoan) {
    success = null;
    confirmation.request({
      kind: 'restore',
      title: 'Registrar devolución',
      description: `Volverá a despacharse desde ${loan.from_branch_name}.`,
      confirmLabel: 'Registrar devolución',
      execute: async () => {
        await fleetApi.returnLoan(vehicle.id, loan.id);
        success = 'Devolución registrada.';
        await load();
        onchanged();
      }
    });
  }
</script>

<div class="panel" bind:this={panel}>
  <div role="status">
    {#if success}<p class="success">{success}</p>{/if}
  </div>

  {#if error}
    <div class="failure" role="alert">
      <p>{error}</p>
      <Button size="lg" variant="secondary" onclick={load}>Reintentar</Button>
    </div>
  {:else}
    <section class="card">
      <div class="head">
        <div>
          <h2>Préstamo a otra sucursal</h2>
          <p class="muted">
            Sigue siendo de su sucursal; mientras tanto se despacha desde la otra.
          </p>
        </div>
        {#if canLend && !openLoan && !loading && branchOptions.length > 1}
          <Button size="lg" class="action" disabled={onRoad} onclick={openLend}>Prestar</Button>
        {/if}
      </div>
      {#if onRoad}
        <p class="muted state">
          Está en un traslado: se podrá {openLoan ? 'devolver' : 'prestar'} cuando termine.
        </p>
      {:else if canLend && !openLoan && !loading && branchOptions.length <= 1}
        <p class="muted state">Prestarlo requiere acceso a otra sucursal.</p>
      {/if}
      {#if loading && loans.length === 0}
        <p class="muted state" role="status">Cargando…</p>
      {:else if openLoan}
        <div class="current" class:late={openLoan.expected_return_on < today}>
          <strong>Prestado a {openLoan.to_branch_name}</strong>
          <small>
            Desde el {formatDate(openLoan.starts_on)} · vuelve el {formatDate(
              openLoan.expected_return_on
            )}{openLoan.expected_return_on < today ? ' (atrasado)' : ''}
          </small>
          <small>{openLoan.reason}</small>
          {#if canLend}
            <Button
              size="lg"
              variant="secondary"
              disabled={onRoad}
              onclick={() => askReturn(openLoan)}>Registrar devolución</Button
            >
          {/if}
        </div>
      {:else if pastLoans.length === 0}
        <p class="muted state">No se ha prestado.</p>
      {/if}
      {#if pastLoans.length}
        <ul class="list">
          {#each pastLoans as loan (loan.id)}
            <li>
              <span>{loan.to_branch_name}</span>
              <small>
                {formatDate(loan.starts_on)} — devuelto el {formatDate(loan.returned_at)}
              </small>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <section class="card">
      <div class="head">
        <div>
          <h2>Reservas</h2>
          <p class="muted">Avisan al despachar; no impiden la salida.</p>
        </div>
        {#if canReserve}
          <Button size="lg" class="action" onclick={openReserve}>Reservar</Button>
        {/if}
      </div>
      {#if loading && reservations.length === 0}
        <p class="muted state" role="status">Cargando…</p>
      {:else if upcoming.length === 0}
        <p class="muted state">No hay reservas próximas.</p>
      {:else}
        <ul class="list">
          {#each upcoming as reservation (reservation.id)}
            <li>
              <span>{reservation.reason}</span>
              <small class="dates">
                {formatDateTime(reservation.starts_at)} — {formatDateTime(reservation.ends_at)}
              </small>
              <small>Reservó: {reservation.reserved_by_name ?? '—'}</small>
              {#if canManageReservations}
                <button
                  type="button"
                  class="link"
                  aria-label={`Cancelar la reserva ${reservation.reason}`}
                  onclick={() => askCancel(reservation)}>Cancelar</button
                >
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>
  {/if}
</div>

<Modal
  open={reserving}
  title="Reservar vehículo"
  mobileFullScreen
  preventClose={saving}
  onclose={() => (reserving = false)}
>
  <form id="reserve-form" class="form" onsubmit={saveReserve} novalidate>
    <FormField
      id="reserve-start"
      label="Desde"
      type="datetime-local"
      bind:value={reserve.starts_at}
      required
      error={attempted ? startError : undefined}
    />
    <FormField
      id="reserve-end"
      label="Hasta"
      type="datetime-local"
      bind:value={reserve.ends_at}
      required
      error={attempted ? endError : undefined}
    />
    <FormField
      id="reserve-reason"
      label="Motivo"
      bind:value={reserve.reason}
      maxlength={300}
      required
      placeholder="Ej. Visita a clientes"
      error={attempted ? reasonError : undefined}
    />
    {#if formError}<p class="error" role="alert">{formError}</p>{/if}
  </form>
  {#snippet footer()}
    <Button size="lg" variant="secondary" disabled={saving} onclick={() => (reserving = false)}>
      Cancelar
    </Button>
    <Button size="lg" type="submit" form="reserve-form" disabled={saving}>
      {saving ? 'Reservando…' : 'Reservar'}
    </Button>
  {/snippet}
</Modal>

<Modal
  open={lending}
  title="Prestar a otra sucursal"
  mobileFullScreen
  preventClose={saving}
  onclose={() => (lending = false)}
>
  <form id="lend-form" class="form" onsubmit={saveLend} novalidate>
    <FormField
      id="lend-branch"
      label="Sucursal"
      type="select"
      bind:value={lend.to_branch_id}
      options={branchOptions}
      required
      error={attempted ? targetError : undefined}
    />
    <FormField
      id="lend-return"
      label="Devolución esperada"
      type="date"
      min={today}
      bind:value={lend.expected_return_on}
      required
      error={attempted ? returnError : undefined}
    />
    <FormField
      id="lend-reason"
      label="Motivo"
      bind:value={lend.reason}
      maxlength={500}
      required
      placeholder="Ej. Apoyo por temporada"
      error={attempted ? lendReasonError : undefined}
    />
    {#if clashes.length}
      <p class="warn" role="status">
        Tiene {clashes.length === 1 ? '1 reserva' : `${clashes.length} reservas`} antes de volver:
        {clashes.map((item) => item.reason).join(', ')}.
      </p>
    {/if}
    {#if vehicle.driver}
      <p class="muted">
        Su conductor sigue asignado. Para salir desde la otra sucursal, el despacho pedirá un
        conductor de allá.
      </p>
    {/if}
    {#if formError}<p class="error" role="alert">{formError}</p>{/if}
  </form>
  {#snippet footer()}
    <Button size="lg" variant="secondary" disabled={saving} onclick={() => (lending = false)}>
      Cancelar
    </Button>
    <Button size="lg" type="submit" form="lend-form" disabled={saving}>
      {saving ? 'Guardando…' : 'Prestar'}
    </Button>
  {/snippet}
</Modal>

<style>
  .panel {
    display: grid;
    gap: 16px;
    scroll-margin-top: 72px;
  }
  .card {
    padding: 16px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }
  .head > div {
    flex: 1 1 220px;
  }
  .head :global(.action) {
    flex: 1 1 100%;
  }
  h2 {
    font-size: 14px;
    font-weight: 600;
  }
  small,
  .muted {
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  small {
    display: block;
  }
  .state,
  .current,
  .list {
    margin-top: 12px;
  }
  .current {
    display: grid;
    gap: 6px;
    justify-items: start;
    padding: 12px;
    border: 1px solid rgb(var(--border));
    border-radius: 10px;
    overflow-wrap: anywhere;
    font-size: 13px;
  }
  .late {
    border-color: rgb(var(--warning) / 0.5);
    background: rgb(var(--warning) / 0.08);
  }
  .list {
    display: grid;
    gap: 8px;
    list-style: none;
  }
  .list li {
    display: grid;
    gap: 2px;
    padding: 10px 12px;
    border: 1px solid rgb(var(--border));
    border-radius: 10px;
    overflow-wrap: anywhere;
    font-size: 13px;
  }
  .link {
    justify-self: start;
    min-width: 44px;
    min-height: 44px;
    color: rgb(var(--foreground-muted));
    font-size: 12px;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .success,
  .failure {
    padding: 12px 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    font-size: 13px;
  }
  .success {
    border-color: rgb(var(--success) / 0.3);
    background: rgb(var(--success) / 0.1);
    color: rgb(var(--success));
  }
  .failure {
    display: grid;
    gap: 10px;
    justify-items: start;
    border-color: rgb(var(--danger) / 0.3);
    color: rgb(var(--danger));
  }
  .form {
    display: grid;
    gap: 12px;
  }
  .form :global(input),
  .form :global(select) {
    border-color: rgb(var(--control-border));
    font-size: 16px;
    font-weight: 400;
  }
  .error {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  .warn {
    padding: 10px 12px;
    border: 1px solid rgb(var(--warning) / 0.4);
    border-radius: 10px;
    background: rgb(var(--warning) / 0.08);
    font-size: 13px;
  }
  @media (min-width: 640px) {
    .head :global(.action) {
      flex: 0 0 auto;
    }
  }
  @media (min-width: 768px) {
    .form :global(input),
    .form :global(select) {
      font-size: 13px;
    }
  }
</style>
