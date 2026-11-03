<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import {
    fleetApi,
    type DueState,
    type FleetVehicle,
    type MaintenanceOrder,
    type MaintenancePlan,
    type OrderStatus
  } from './api';
  import { formatDate, formatMoney, formatNumber, isBlank, meterName, meterShort } from './catalog';

  let { vehicle, onchanged }: { vehicle: FleetVehicle; onchanged: () => void } = $props();

  const DUE_META: Record<DueState, { label: string; tone: string }> = {
    ok: { label: 'Al día', tone: 'ok' },
    soon: { label: 'Próximo', tone: 'warn' },
    overdue: { label: 'Vencido', tone: 'danger' },
    unknown: { label: 'Sin referencia', tone: 'muted' }
  };
  const ORDER_META: Record<OrderStatus, { label: string; tone: string }> = {
    scheduled: { label: 'Programada', tone: 'muted' },
    in_progress: { label: 'En taller', tone: 'warn' },
    completed: { label: 'Completada', tone: 'ok' },
    cancelled: { label: 'Cancelada', tone: 'danger' }
  };

  let plans = $state<MaintenancePlan[]>([]);
  let orders = $state<MaintenanceOrder[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let saving = $state(false);
  let formError = $state<string | null>(null);

  let planOpen = $state(false);
  let editingPlan = $state<MaintenancePlan | null>(null);
  let plan = $state({ name: '', interval_km: '', interval_days: '', last_km: '', last_on: '' });

  let orderOpen = $state(false);
  let order = $state({
    kind: 'preventive' as 'preventive' | 'corrective',
    title: '',
    description: '',
    workshop: '',
    scheduled_on: '',
    plan_id: ''
  });

  let closing = $state<{ order: MaintenanceOrder; mode: 'complete' | 'cancel' } | null>(null);
  let close = $state({ odometer: '', cost: '', workshop: '', notes: '', reason: '' });

  const unit = $derived(meterShort(vehicle.type.meter_unit));
  const canManage = $derived(
    permissions.hasPermission('fleet:maintenance') && vehicle.status !== 'retired'
  );
  const onRoad = $derived(vehicle.operational_status === 'in_route');
  const openOrders = $derived(
    orders.filter((item) => item.status === 'scheduled' || item.status === 'in_progress')
  );
  const closedOrders = $derived(
    orders.filter((item) => item.status === 'completed' || item.status === 'cancelled')
  );
  const spent = $derived(closedOrders.reduce((total, item) => total + Number(item.cost ?? 0), 0));

  const message = (err: unknown, fallback: string) =>
    err instanceof HttpError ? err.message : fallback;

  async function load() {
    loading = true;
    error = null;
    try {
      [plans, orders] = await Promise.all([
        fleetApi.plans(vehicle.id),
        fleetApi.orders(vehicle.id)
      ]);
    } catch (err) {
      error = message(err, 'No se pudo cargar el mantenimiento.');
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void vehicle.id;
    void load();
  });

  async function run(action: () => Promise<unknown>, after: () => void) {
    saving = true;
    formError = null;
    try {
      await action();
      after();
      await load();
      onchanged();
    } catch (err) {
      formError = message(err, 'No se pudo completar la operación.');
    } finally {
      saving = false;
    }
  }

  function askDeactivate(target: MaintenancePlan) {
    confirmation.request({
      kind: 'deactivate',
      title: 'Desactivar plan de mantenimiento',
      description: 'Dejará de avisar cuando venza. Sus órdenes anteriores se conservan.',
      resourceName: target.name,
      confirmLabel: 'Desactivar',
      execute: async () => {
        await fleetApi.deactivatePlan(vehicle.id, target.id);
        await load();
      }
    });
  }

  function openPlan(target: MaintenancePlan | null) {
    editingPlan = target;
    plan = {
      name: target?.name ?? '',
      interval_km: target?.interval_km?.toString() ?? '',
      interval_days: target?.interval_days?.toString() ?? '',
      last_km: target?.last_service_km ?? '',
      last_on: target?.last_service_on ?? ''
    };
    formError = null;
    planOpen = true;
  }

  function savePlan() {
    const data = {
      name: plan.name.trim(),
      interval_km: plan.interval_km ? Number(plan.interval_km) : null,
      interval_days: plan.interval_days ? Number(plan.interval_days) : null,
      last_service_km: plan.last_km || null,
      last_service_on: plan.last_on || null
    };
    void run(
      () =>
        editingPlan
          ? fleetApi.updatePlan(vehicle.id, editingPlan.id, data)
          : fleetApi.createPlan(vehicle.id, data),
      () => (planOpen = false)
    );
  }

  function openOrder(fromPlan: MaintenancePlan | null) {
    order = {
      kind: 'preventive',
      title: fromPlan ? fromPlan.name : '',
      description: '',
      workshop: '',
      scheduled_on: '',
      plan_id: fromPlan?.id ?? ''
    };
    if (!fromPlan) order.kind = 'corrective';
    formError = null;
    orderOpen = true;
  }

  function saveOrder() {
    void run(
      () =>
        fleetApi.createOrder(vehicle.id, {
          kind: order.kind,
          title: order.title.trim(),
          description: order.description.trim() || null,
          workshop: order.workshop.trim() || null,
          scheduled_on: order.scheduled_on || null,
          plan_id: order.plan_id || null
        }),
      () => (orderOpen = false)
    );
  }

  function openClose(target: MaintenanceOrder, mode: 'complete' | 'cancel') {
    close = {
      odometer: vehicle.odometer_km,
      cost: '',
      workshop: target.workshop ?? '',
      notes: '',
      reason: ''
    };
    formError = null;
    closing = { order: target, mode };
  }

  function confirmClose() {
    const target = closing;
    if (!target) return;
    void run(
      () =>
        target.mode === 'complete'
          ? fleetApi.completeOrder(vehicle.id, target.order.id, {
              odometer_km: close.odometer,
              cost: close.cost,
              workshop: close.workshop.trim() || null,
              notes: close.notes.trim() || null
            })
          : fleetApi.cancelOrder(vehicle.id, target.order.id, close.reason.trim()),
      () => (closing = null)
    );
  }

  function start(target: MaintenanceOrder) {
    void run(
      () => fleetApi.startOrder(vehicle.id, target.id),
      () => undefined
    );
  }
</script>

{#if loading && plans.length === 0 && orders.length === 0}
  <p class="muted">Cargando mantenimiento…</p>
{:else if error}
  <p class="error" role="alert">{error}</p>
{:else}
  <div class="panel">
    <section class="card">
      <header>
        <div>
          <h2>Planes preventivos</h2>
          <p class="muted">
            Se calculan con la lectura actual ({formatNumber(vehicle.odometer_km)}
            {unit}).
          </p>
        </div>
        {#if canManage}
          <Button size="sm" variant="secondary" onclick={() => openPlan(null)}>Nuevo plan</Button>
        {/if}
      </header>
      {#if plans.length === 0}
        <p class="muted">Sin planes. Defina cada cuánto se da servicio (km, días o ambos).</p>
      {:else}
        <ul class="plans">
          {#each plans as item (item.id)}
            <li>
              <div class="plan-head">
                <strong>{item.name}</strong>
                <span class={`badge ${DUE_META[item.state].tone}`}
                  >{DUE_META[item.state].label}</span
                >
              </div>
              <small>
                Cada
                {[
                  item.interval_km ? `${formatNumber(item.interval_km)} ${unit}` : null,
                  item.interval_days ? `${item.interval_days} días` : null
                ]
                  .filter(Boolean)
                  .join(' o ')}
                · Último: {item.last_service_km
                  ? `${formatNumber(item.last_service_km)} ${unit}`
                  : '—'}{item.last_service_on ? `, ${formatDate(item.last_service_on)}` : ''}
              </small>
              <small>
                Próximo: {item.due_km ? `${formatNumber(item.due_km)} ${unit}` : ''}{item.due_km &&
                item.due_on
                  ? ' o '
                  : ''}{item.due_on ? formatDate(item.due_on) : ''}{!item.due_km && !item.due_on
                  ? 'registre el último servicio'
                  : ''}
              </small>
              {#if canManage}
                <div class="row-actions">
                  <button type="button" onclick={() => openOrder(item)}>Programar orden</button>
                  <button type="button" onclick={() => openPlan(item)}>Editar</button>
                  <button type="button" onclick={() => askDeactivate(item)}>Desactivar</button>
                </div>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <section class="card">
      <header>
        <div>
          <h2>Órdenes abiertas</h2>
          <p class="muted">Iniciar una orden pone el vehículo en mantenimiento.</p>
        </div>
        {#if canManage}
          <Button size="sm" variant="secondary" onclick={() => openOrder(null)}>Nueva orden</Button>
        {/if}
      </header>
      {#if openOrders.length === 0}
        <p class="muted">No hay órdenes abiertas.</p>
      {:else}
        <ul class="orders">
          {#each openOrders as item (item.id)}
            <li>
              <div class="plan-head">
                <strong>{item.title}</strong>
                <span class={`badge ${ORDER_META[item.status].tone}`}
                  >{ORDER_META[item.status].label}</span
                >
              </div>
              <small>
                {item.kind === 'preventive' ? 'Preventiva' : 'Correctiva'}
                {item.workshop ? ` · ${item.workshop}` : ''}
                {item.scheduled_on ? ` · ${formatDate(item.scheduled_on)}` : ''}
              </small>
              {#if canManage}
                <div class="row-actions">
                  {#if item.status === 'scheduled'}
                    <button
                      type="button"
                      disabled={saving || onRoad}
                      title={onRoad ? 'El vehículo está en ruta' : undefined}
                      onclick={() => start(item)}>Iniciar</button
                    >
                  {:else}
                    <button type="button" onclick={() => openClose(item, 'complete')}
                      >Completar</button
                    >
                  {/if}
                  <button type="button" onclick={() => openClose(item, 'cancel')}>Cancelar</button>
                </div>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
      {#if formError && !planOpen && !orderOpen && !closing}
        <p class="error" role="alert">{formError}</p>
      {/if}
    </section>

    <section class="card wide">
      <header>
        <h2>Historial</h2>
        <span class="muted">Gasto registrado: {formatMoney(spent)}</span>
      </header>
      {#if closedOrders.length === 0}
        <p class="muted">Aún no hay servicios cerrados.</p>
      {:else}
        <div class="table-wrap">
          <table>
            <thead>
              <tr
                ><th>Servicio</th><th>Estado</th><th>Cierre</th><th>Odómetro</th><th>Taller</th><th
                  class="num">Costo</th
                ></tr
              >
            </thead>
            <tbody>
              {#each closedOrders as item (item.id)}
                <tr>
                  <td>
                    {item.title}
                    {#if item.cancel_reason}<small class="block">{item.cancel_reason}</small>{/if}
                  </td>
                  <td>{ORDER_META[item.status].label}</td>
                  <td>{formatDate(item.completed_at ?? item.created_at)}</td>
                  <td>{item.odometer_km ? `${formatNumber(item.odometer_km)} ${unit}` : '—'}</td>
                  <td>{item.workshop ?? '—'}</td>
                  <td class="num">{formatMoney(item.cost)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>
  </div>
{/if}

<Modal
  open={planOpen}
  title={editingPlan ? 'Editar plan' : 'Nuevo plan preventivo'}
  onclose={() => (planOpen = false)}
>
  <div class="form">
    <label
      ><span>Nombre</span><input
        bind:value={plan.name}
        maxlength="120"
        placeholder="Cambio de aceite"
      /></label
    >
    <div class="pair">
      <label
        ><span>Cada ({unit})</span><input
          type="number"
          min="1"
          bind:value={plan.interval_km}
        /></label
      >
      <label
        ><span>Cada (días)</span><input
          type="number"
          min="1"
          bind:value={plan.interval_days}
        /></label
      >
    </div>
    <div class="pair">
      <label
        ><span>Último servicio ({unit})</span><input
          type="number"
          min="0"
          step="0.1"
          bind:value={plan.last_km}
        /></label
      >
      <label
        ><span>Fecha del último servicio</span><input
          type="date"
          bind:value={plan.last_on}
        /></label
      >
    </div>
    {#if formError}<p class="error" role="alert">{formError}</p>{/if}
    <div class="actions">
      <Button variant="secondary" onclick={() => (planOpen = false)}>Cancelar</Button>
      <Button
        disabled={saving ||
          plan.name.trim().length < 2 ||
          (!plan.interval_km && !plan.interval_days)}
        onclick={savePlan}>Guardar</Button
      >
    </div>
  </div>
</Modal>

<Modal open={orderOpen} title="Nueva orden de mantenimiento" onclose={() => (orderOpen = false)}>
  <div class="form">
    <div class="pair">
      <label>
        <span>Tipo</span>
        <select bind:value={order.kind}>
          <option value="preventive">Preventiva</option>
          <option value="corrective">Correctiva</option>
        </select>
      </label>
      <label>
        <span>Plan</span>
        <select bind:value={order.plan_id}>
          <option value="">Ninguno</option>
          {#each plans as item (item.id)}<option value={item.id}>{item.name}</option>{/each}
        </select>
      </label>
    </div>
    <label><span>Título</span><input bind:value={order.title} maxlength="160" /></label>
    <label
      ><span>Descripción</span><textarea rows="3" bind:value={order.description} maxlength="4000"
      ></textarea></label
    >
    <div class="pair">
      <label><span>Taller</span><input bind:value={order.workshop} maxlength="160" /></label>
      <label
        ><span>Fecha programada</span><input type="date" bind:value={order.scheduled_on} /></label
      >
    </div>
    {#if formError}<p class="error" role="alert">{formError}</p>{/if}
    <div class="actions">
      <Button variant="secondary" onclick={() => (orderOpen = false)}>Cancelar</Button>
      <Button disabled={saving || order.title.trim().length < 2} onclick={saveOrder}
        >Crear orden</Button
      >
    </div>
  </div>
</Modal>

<Modal
  open={closing !== null}
  title={closing?.mode === 'complete' ? 'Completar mantenimiento' : 'Cancelar orden'}
  onclose={() => (closing = null)}
>
  <div class="form">
    {#if closing?.mode === 'complete'}
      <p class="muted">
        Se registrará la lectura actual, se actualizará el plan y el vehículo volverá a operar si no
        tiene otras órdenes en taller.
      </p>
      <div class="pair">
        <label
          ><span>{meterName(vehicle.type.meter_unit)} ({unit})</span><input
            type="number"
            min="0"
            step="0.1"
            bind:value={close.odometer}
          /></label
        >
        <label
          ><span>Costo total (USD)</span><input
            type="number"
            min="0"
            step="0.01"
            bind:value={close.cost}
          /></label
        >
      </div>
      <label><span>Taller</span><input bind:value={close.workshop} maxlength="160" /></label>
      <label
        ><span>Trabajos realizados</span><textarea
          rows="3"
          bind:value={close.notes}
          maxlength="4000"
        ></textarea></label
      >
    {:else}
      <label
        ><span>Motivo</span><textarea rows="3" bind:value={close.reason} maxlength="500"
        ></textarea></label
      >
    {/if}
    {#if formError}<p class="error" role="alert">{formError}</p>{/if}
    <div class="actions">
      <Button variant="secondary" onclick={() => (closing = null)}>Volver</Button>
      <Button
        disabled={saving ||
          (closing?.mode === 'complete'
            ? isBlank(close.odometer) || isBlank(close.cost)
            : close.reason.trim().length < 3)}
        onclick={confirmClose}>Confirmar</Button
      >
    </div>
  </div>
</Modal>

<style>
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
  .wide {
    grid-column: 1 / -1;
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
  small,
  .muted {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .block {
    display: block;
  }
  .plans,
  .orders {
    display: grid;
    gap: 10px;
    list-style: none;
  }
  .plans li,
  .orders li {
    display: grid;
    gap: 3px;
    padding: 11px 12px;
    border: 1px solid rgb(var(--border));
    border-radius: 10px;
  }
  .plan-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    font-size: 13px;
  }
  .badge {
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
  }
  .ok {
    background: rgb(var(--success) / 0.12);
    color: rgb(var(--success));
  }
  .warn {
    background: rgb(var(--warning) / 0.14);
    color: rgb(var(--warning));
  }
  .danger {
    background: rgb(var(--danger) / 0.1);
    color: rgb(var(--danger));
  }
  .badge.muted {
    background: rgb(var(--surface-hover));
  }
  .row-actions {
    display: flex;
    gap: 12px;
    margin-top: 6px;
  }
  .row-actions button {
    font-size: 12px;
    font-weight: 500;
    color: rgb(var(--primary));
  }
  .row-actions button:disabled {
    cursor: not-allowed;
    opacity: 0.5;
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
  input,
  select,
  textarea {
    min-height: 38px;
    padding: 8px 10px;
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
    .panel,
    .pair {
      grid-template-columns: 1fr;
    }
  }
</style>
