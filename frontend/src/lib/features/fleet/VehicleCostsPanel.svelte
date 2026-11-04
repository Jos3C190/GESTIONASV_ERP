<script lang="ts">
  import { tick } from 'svelte';
  import { page } from '$app/state';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import {
    fleetApi,
    type CostCategory,
    type CostReport,
    type FleetCost,
    type FleetVehicle
  } from './api';
  import {
    COST_CATEGORY_LABELS,
    costPeriods,
    formatDate,
    formatMoney,
    formatNumber,
    formatRate,
    localDate,
    meterShort,
    type CostPeriodId
  } from './catalog';
  import CostKpis from './CostKpis.svelte';
  import PeriodSwitch from './PeriodSwitch.svelte';
  import ReceiptField from './ReceiptField.svelte';
  import ReceiptLink from './ReceiptLink.svelte';
  import SupplierField from './SupplierField.svelte';

  let { vehicle }: { vehicle: FleetVehicle } = $props();

  type Period = CostPeriodId | 'all' | 'linked';
  const EARLIEST = '2000-01-01';
  // Del reporte se llega con su rango, para ver aquí las mismas cifras.
  const linked = {
    from: page.url?.searchParams.get('from') ?? '',
    to: page.url?.searchParams.get('to') ?? ''
  };

  let periods = $state(costPeriods(new Date()));
  let today = $state(localDate(new Date()));
  const unit = $derived(meterShort(vehicle.type.meter_unit));
  // Sin categoría por defecto: quien no la elija archivaría todo como seguro.
  const categoryOptions = [
    { value: '', label: 'Elige una categoría' },
    ...(Object.keys(COST_CATEGORY_LABELS) as CostCategory[]).map((value) => ({
      value,
      label: COST_CATEGORY_LABELS[value]
    }))
  ];
  const LIST_LIMIT = 200;

  let period = $state<Period>(initialPeriod());
  let report = $state<CostReport | null>(null);
  let costs = $state<FleetCost[]>([]);
  let loading = $state(true);
  let reportError = $state<string | null>(null);
  let listError = $state<string | null>(null);
  let success = $state<string | null>(null);
  let open = $state(false);
  let saving = $state(false);
  let attempted = $state(false);
  let formError = $state<string | null>(null);
  let proposed = $state<{ amount: string; supplierId: string } | null>(null);
  let form = $state(blank());
  let requestId = 0;

  const range = $derived(
    period === 'all'
      ? { from: EARLIEST, to: today }
      : period === 'linked'
        ? linked
        : periods[period]
  );
  const hasFee = $derived(Number(vehicle.monthly_fee) > 0);
  const canRecord = $derived(permissions.hasPermission('fleet:costs'));
  const row = $derived(report?.rows[0] ?? null);
  // Sin fila en un reporte que sí cargó significa que el vehículo no costó nada.
  const totals = $derived(
    report ? (row ?? { total: '0', fuel: '0', maintenance: '0', other: '0', incidents: '0' }) : null
  );
  const detail = $derived.by(() => {
    if (!report) return undefined;
    return row?.cost_per_unit
      ? `${formatRate(row.cost_per_unit)} por ${unit} · ${formatNumber(row.distance)} ${unit} recorridos`
      : `Sin recorrido en el periodo para calcular costo por ${unit}`;
  });
  const visibleCosts = $derived(
    costs.filter((cost) => cost.incurred_on >= range.from && cost.incurred_on <= range.to)
  );
  const categoryError = $derived(form.category ? undefined : 'Elige la categoría.');
  const amountError = $derived(
    /^\d{1,8}(\.\d{1,2})?$/.test(String(form.amount ?? '')) && Number(form.amount) > 0
      ? undefined
      : 'Monto mayor que cero, con hasta 2 decimales.'
  );
  const dateError = $derived(
    !form.incurred_on
      ? 'Indica la fecha.'
      : form.incurred_on > today
        ? 'La fecha no puede ser futura.'
        : undefined
  );

  function initialPeriod(): Period {
    if (!linked.from || !linked.to) return 'month';
    const start = costPeriods(new Date());
    const match = (Object.keys(start) as CostPeriodId[]).find(
      (id) => start[id].from === linked.from && start[id].to === linked.to
    );
    return match ?? 'linked';
  }

  function blank() {
    return {
      category: '' as CostCategory | '',
      incurred_on: localDate(new Date()),
      amount: '',
      description: '',
      supplier_id: '',
      supplier_text: '',
      document_id: ''
    };
  }

  function message(err: unknown, fallback: string): string {
    return err instanceof HttpError ? err.message : fallback;
  }

  async function load() {
    const current = ++requestId;
    const { from, to } = range;
    loading = true;
    reportError = null;
    listError = null;
    const [nextReport, nextCosts] = await Promise.allSettled([
      fleetApi.costReport({ date_from: from, date_to: to, vehicle_id: vehicle.id }),
      fleetApi.costs(vehicle.id)
    ]);
    // Si el periodo cambió mientras tanto, esta respuesta ya no vale.
    if (current !== requestId) return;
    if (nextReport.status === 'fulfilled') report = nextReport.value;
    else {
      report = null;
      reportError = message(nextReport.reason, 'No se pudieron calcular los costos.');
    }
    if (nextCosts.status === 'fulfilled') costs = nextCosts.value;
    else listError = message(nextCosts.reason, 'No se pudo cargar la lista de costos.');
    loading = false;
  }

  $effect(() => {
    void vehicle.id;
    void period;
    void load();
  });

  function openForm() {
    // Una pestaña abierta de un día para otro no debe rechazar la fecha de hoy.
    today = localDate(new Date());
    periods = costPeriods(new Date());
    form = blank();
    attempted = false;
    proposed = null;
    formError = null;
    success = null;
    open = true;
  }

  function chooseCategory(next: CostCategory | '') {
    form.category = next;
    // La cuota del contrato se conoce: se propone, pero se puede cambiar.
    if (next === 'fee' && !form.amount && hasFee) {
      form.amount = String(Number(vehicle.monthly_fee));
      if (vehicle.owner_supplier_id && !form.supplier_id) {
        form.supplier_id = String(vehicle.owner_supplier_id);
      }
      proposed = { amount: String(form.amount), supplierId: form.supplier_id };
    } else if (next !== 'fee' && proposed) {
      // No arrastrar a un seguro lo que solo se propuso para la cuota; lo editado se respeta.
      if (String(form.amount) === proposed.amount) form.amount = '';
      if (form.supplier_id === proposed.supplierId) form.supplier_id = '';
      proposed = null;
    }
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    attempted = true;
    if (categoryError || amountError || dateError) {
      const first = categoryError ? 'cost-category' : amountError ? 'cost-amount' : 'cost-date';
      // Primero debe existir el mensaje, para que el lector lo anuncie con el campo.
      await tick();
      document.getElementById(first)?.focus();
      return;
    }
    saving = true;
    formError = null;
    const typed = form.supplier_id ? '' : form.supplier_text.trim();
    try {
      await fleetApi.addCost(vehicle.id, {
        category: form.category as CostCategory,
        incurred_on: form.incurred_on,
        amount: String(form.amount),
        description: [form.description.trim(), typed].filter(Boolean).join(' · ') || null,
        supplier_id: form.supplier_id ? Number(form.supplier_id) : null,
        document_id: form.document_id || null
      });
      const date = form.incurred_on;
      const label = COST_CATEGORY_LABELS[form.category as CostCategory];
      // Que lo recién guardado se vea: pasar al periodo de su fecha, o decir dónde quedó.
      const holder = (Object.keys(periods) as CostPeriodId[]).find(
        (id) => date >= periods[id].from && date <= periods[id].to
      );
      if (date < range.from || date > range.to) period = holder ?? 'all';
      success = `Costo registrado: ${label}, ${formatMoney(form.amount)}, del ${formatDate(date)}.`;
      open = false;
      await load();
    } catch (err) {
      formError = message(err, 'No se pudo registrar el costo.');
    } finally {
      saving = false;
    }
  }

  function askVoid(cost: FleetCost) {
    success = null;
    confirmation.request({
      kind: 'revoke',
      title: 'Anular costo',
      description: 'Dejará de contar en los reportes. Queda en el historial, tachado.',
      confirmLabel: 'Anular',
      requireReason: true,
      reasonLabel: 'Motivo',
      execute: async (why) => {
        await fleetApi.voidCost(vehicle.id, cost.id, why ?? '');
        success = 'Costo anulado.';
        await load();
      }
    });
  }
</script>

<div class="panel">
  <div class="toolbar">
    <PeriodSwitch
      value={period === 'linked' ? null : period}
      withAll
      onselect={(next) => {
        period = next;
        success = null;
      }}
      onall={() => {
        period = 'all';
        success = null;
      }}
    />
    {#if canRecord}
      <Button size="lg" class="record" onclick={openForm}>Registrar costo</Button>
    {/if}
  </div>

  <div role="status">
    {#if success}<p class="success">{success}</p>{/if}
  </div>

  {#if reportError}
    <div class="failure" role="alert">
      <p>{reportError}</p>
      <Button size="lg" variant="secondary" onclick={load}>Reintentar</Button>
    </div>
  {:else}
    <CostKpis {totals} {detail} busy={loading} />
  {/if}

  <section class="card">
    <h2>Otros costos</h2>
    <p class="muted">Seguros, impuestos, lavados, cuotas y peajes de este vehículo.</p>
    {#if period === 'linked'}
      <p class="muted fee">Del {formatDate(linked.from)} al {formatDate(linked.to)}.</p>
    {/if}
    {#if hasFee}
      <p class="muted fee">
        La cuota de {formatMoney(vehicle.monthly_fee)} al mes no se suma sola: regístrala cuando se pague.
      </p>
    {/if}
    {#if listError}
      <div class="failure list-failure" role="alert">
        <p>{listError}</p>
        <Button size="lg" variant="secondary" onclick={load}>Reintentar</Button>
      </div>
    {:else if loading && costs.length === 0}
      <p class="muted state" role="status">Cargando…</p>
    {:else if visibleCosts.length === 0}
      <p class="muted state">No hay otros costos en este periodo.</p>
    {:else}
      <ul class="costs">
        {#each visibleCosts as cost (cost.id)}
          <li class:voided={cost.voided_at}>
            <div class="line">
              <strong>{COST_CATEGORY_LABELS[cost.category]}</strong>
              <span class="amount">{formatMoney(cost.amount)}</span>
            </div>
            <small>
              {formatDate(cost.incurred_on)}{cost.supplier_name
                ? ` · ${cost.supplier_name}`
                : ''}{cost.description ? ` · ${cost.description}` : ''}
            </small>
            {#if cost.voided_at}
              <small>Anulado por {cost.voided_by_name ?? '—'}: {cost.void_reason}</small>
            {/if}
            {#if cost.document_id || (canRecord && !cost.voided_at)}
              <div class="row-actions">
                {#if cost.document_id}
                  <ReceiptLink vehicleId={vehicle.id} documentId={cost.document_id} />
                {/if}
                {#if canRecord && !cost.voided_at}
                  <button
                    type="button"
                    class="void"
                    aria-label={`Anular ${COST_CATEGORY_LABELS[cost.category]} del ${formatDate(cost.incurred_on)}`}
                    onclick={() => askVoid(cost)}>Anular</button
                  >
                {/if}
              </div>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
    {#if !listError && costs.length >= LIST_LIMIT}
      <p class="muted state">Solo se consideran los {LIST_LIMIT} costos más recientes.</p>
    {/if}
  </section>
</div>

<Modal
  {open}
  title="Registrar costo"
  mobileFullScreen
  preventClose={saving}
  onclose={() => (open = false)}
>
  <form id="cost-form" class="form" onsubmit={save} novalidate>
    <div class="pair">
      <FormField
        id="cost-category"
        label="Categoría"
        type="select"
        bind:value={form.category}
        options={categoryOptions}
        required
        error={attempted ? categoryError : undefined}
        oninput={(event) =>
          chooseCategory((event.target as HTMLSelectElement).value as CostCategory | '')}
      />
      <FormField
        id="cost-amount"
        label="Monto (USD)"
        type="number"
        bind:value={form.amount}
        min="0"
        step="0.01"
        required
        error={attempted ? amountError : undefined}
      />
    </div>
    <FormField
      id="cost-date"
      label="Fecha"
      type="date"
      max={today}
      bind:value={form.incurred_on}
      required
      error={attempted ? dateError : undefined}
    />
    <SupplierField
      id="cost-supplier"
      label="Proveedor (opcional)"
      bind:supplierId={form.supplier_id}
      bind:text={form.supplier_text}
    />
    <FormField
      id="cost-detail"
      label="Detalle (opcional)"
      bind:value={form.description}
      maxlength={120}
      placeholder="Ej. Póliza anual"
    />
    <ReceiptField
      id="cost-document"
      label="Factura (opcional)"
      vehicleId={vehicle.id}
      bind:value={form.document_id}
    />
    {#if formError}<p class="error" role="alert">{formError}</p>{/if}
  </form>
  {#snippet footer()}
    <Button size="lg" variant="secondary" disabled={saving} onclick={() => (open = false)}>
      Cancelar
    </Button>
    <Button size="lg" type="submit" form="cost-form" disabled={saving}>
      {saving ? 'Registrando…' : 'Registrar'}
    </Button>
  {/snippet}
</Modal>

<style>
  .panel {
    display: grid;
    gap: 16px;
  }
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .toolbar :global(.record) {
    flex: 1 1 100%;
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
  small,
  .muted {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .card {
    padding: 18px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  h2 {
    font-size: 14px;
    font-weight: 600;
  }
  .fee {
    margin-top: 8px;
  }
  .state,
  .costs,
  .list-failure {
    margin-top: 12px;
  }
  .costs {
    display: grid;
    gap: 10px;
    list-style: none;
  }
  .costs li {
    display: grid;
    gap: 3px;
    padding: 11px 12px;
    border: 1px solid rgb(var(--border));
    border-radius: 10px;
  }
  .line {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    font-size: 13px;
  }
  .amount {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .voided strong,
  .voided .amount {
    color: rgb(var(--foreground-muted));
    font-weight: 500;
    text-decoration: line-through;
  }
  .row-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 14px;
  }
  .void {
    min-width: 44px;
    min-height: 44px;
    color: rgb(var(--foreground-muted));
    font-size: 12px;
    text-decoration: underline;
    text-underline-offset: 2px;
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
  @media (min-width: 768px) {
    .form :global(input),
    .form :global(select) {
      font-size: 13px;
    }
  }
  .pair {
    display: grid;
    gap: 12px;
  }
  .error {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  @media (min-width: 640px) {
    .toolbar :global(.record) {
      flex: 0 0 auto;
    }
    .pair {
      grid-template-columns: 1fr 1fr;
    }
  }
</style>
