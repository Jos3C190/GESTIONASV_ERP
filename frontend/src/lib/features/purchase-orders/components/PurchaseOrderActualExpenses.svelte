<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { purchaseOrdersApi } from '$lib/api/purchase-orders';
  import {
    actualExpensesApi,
    type ActualPurchaseExpense,
    type ActualExpenseAvailability
  } from '../actual-expenses';
  import { otherExpenseCategory } from '$lib/features/retaceos/manual-costs';
  import PurchaseOrderExpenseDocuments from './PurchaseOrderExpenseDocuments.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { PurchaseOrder, PurchaseOrderExpenseType } from '$lib/types/purchase-order';

  let { order }: { order: PurchaseOrder } = $props();
  let expenses = $state<ActualPurchaseExpense[]>([]);
  let categories = $state<PurchaseOrderExpenseType[]>([]);
  let availability = $state<ActualExpenseAvailability | null>(null);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state('');
  let notice = $state('');
  let category = $state('');
  let amount = $state('');
  let incurredOn = $state('');
  let reference = $state('');
  let description = $state('');
  let expanded = $state(false);
  let sequence = 0;
  let active = true;
  const canRead = $derived(permissions.hasPermission('purchase_orders:read'));
  const canRecord = $derived(
    permissions.hasPermission('purchase_orders:manage') &&
      availability?.can_record === true &&
      ['approved', 'sent', 'partially_received', 'received'].includes(order.status)
  );
  onDestroy(() => {
    active = false;
    sequence++;
  });

  function money(value: string) {
    return new Intl.NumberFormat('es-SV', { style: 'currency', currency: order.currency }).format(
      Number(value)
    );
  }
  function date(value: string) {
    return value.split('-').reverse().join('/');
  }
  async function load() {
    const request = ++sequence;
    loading = true;
    availability = null;
    error = '';
    try {
      const [rows, types, available] = await Promise.all([
        actualExpensesApi.list(order.id),
        purchaseOrdersApi.listExpenseTypes(),
        actualExpensesApi.availability(order.id)
      ]);
      if (!active || request !== sequence) return;
      expenses = rows;
      availability = available;
      categories = types.filter((row) => otherExpenseCategory(row.name));
    } catch (cause) {
      if (active && request === sequence)
        error = cause instanceof Error ? cause.message : 'No se pudo cargar la bitácora.';
    } finally {
      if (active && request === sequence) loading = false;
    }
  }
  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (saving || !canRecord) return;
    saving = true;
    error = '';
    notice = '';
    const currentOrderId = order.id;
    try {
      const saved = await actualExpensesApi.create(currentOrderId, {
        expense_type_id: category,
        amount,
        incurred_on: incurredOn,
        reference,
        description
      });
      if (!active || currentOrderId !== order.id) return;
      expenses = [...expenses, saved];
      category = '';
      amount = '';
      incurredOn = '';
      reference = '';
      description = '';
      notice =
        'Gasto real registrado, pendiente de asignar. Relaciónalo al capturarlo en retaceo antes de cerrarlo. Los adjuntos son opcionales.';
      await tick();
      document.getElementById(`actual-expense-${saved.id}`)?.focus();
    } catch (cause) {
      if (active && currentOrderId === order.id) {
        error = cause instanceof Error ? cause.message : 'No se pudo registrar el gasto real.';
        const available = await actualExpensesApi.availability(currentOrderId).catch(() => null);
        if (active && currentOrderId === order.id) availability = available;
      }
    } finally {
      if (active) saving = false;
    }
  }
  $effect(() => {
    const id = order.id;
    if (id && canRead) void load();
  });
</script>

{#if canRead}
  <section
    class="rounded-xl border border-border bg-surface p-4"
    aria-labelledby="actual-expenses-heading"
  >
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-2">
        <h2 id="actual-expenses-heading" class="font-semibold text-foreground">
          Bitácora de otros gastos reales
        </h2>
        <span
          class="rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-medium text-foreground-muted"
          >Opcional</span
        >
      </div>
      <button
        type="button"
        class="inline-flex min-h-11 items-center gap-2 rounded-lg border border-border bg-surface-elevated px-4 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        aria-expanded={expanded}
        aria-controls="actual-expenses-content"
        onclick={() => (expanded = !expanded)}
      >
        {expanded ? 'Ocultar bitácora' : 'Ver / registrar bitácora'}
        <span aria-hidden="true">{expanded ? '−' : '+'}</span>
      </button>
    </div>
    <p class="mt-1 text-sm text-foreground-muted">
      Consulta o registra gastos adicionales realmente incurridos en esta orden.
    </p>
    <div id="actual-expenses-content" hidden={!expanded}>
      <p class="mt-1 text-sm leading-6 text-foreground-muted">
        Si no hubo otros gastos, puedes continuar con la recepción y el retaceo sin llenar esta
        sección. Si registras un gasto, completa sus datos y relaciónalo con el retaceo antes de
        cerrarlo; registrarlo aquí no lo suma automáticamente al costo. FOB, flete, DAI e IVA se
        capturan en sus campos de retaceo.
      </p>
      {#if loading}<div class="mt-4 space-y-2" aria-label="Cargando gastos reales">
          <div class="skeleton h-16 rounded-lg"></div>
          <div class="skeleton h-16 rounded-lg"></div>
        </div>
      {:else}
        {#if error}<div
            class="mt-4 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-foreground"
            role="alert"
          >
            {error}<Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={saving}
              onclick={() => void load()}>Reintentar carga</Button
            >
          </div>{/if}
        {#if notice}<p class="mt-4 text-sm text-success" role="status">{notice}</p>{/if}
        {#if availability && !availability.can_record}
          <div
            class="mt-4 rounded-lg border border-border bg-surface-muted p-3 text-sm"
            role="status"
          >
            <p class="font-medium text-foreground">{availability.reason}</p>
            {#if availability.closed_retaceo_id}
              <p class="mt-1 text-foreground-muted">
                Los importes sin asignar permanecen en la bitácora para revisión; no se suman al
                costo cerrado.
              </p>
              <a
                class="mt-2 inline-block text-primary underline"
                href={`/retaceos/${availability.closed_retaceo_id}`}
                >Consultar {availability.closed_retaceo_code}</a
              >
            {/if}
          </div>
        {/if}
        {#if canRecord}
          <form class="mt-4 space-y-3" onsubmit={submit}>
            <fieldset disabled={saving} class="grid gap-3 sm:grid-cols-2">
              <label class="text-sm font-medium text-foreground"
                >Tipo de gasto<select
                  id="actual-expense-category"
                  required
                  bind:value={category}
                  class="mt-1 h-11 w-full rounded-lg border border-border-control bg-surface px-3 focus-visible:ring-2 focus-visible:ring-primary"
                  ><option value="">Selecciona una categoría</option
                  >{#each categories as row (row.id)}<option value={row.id}>{row.name}</option
                    >{/each}</select
                ></label
              >
              <label class="text-sm font-medium text-foreground"
                >Monto real ({order.currency})<input
                  type="number"
                  min="0.000001"
                  step="0.000001"
                  required
                  bind:value={amount}
                  class="mt-1 h-11 w-full rounded-lg border border-border-control bg-surface px-3 focus-visible:ring-2 focus-visible:ring-primary"
                /></label
              >
              <label class="text-sm font-medium text-foreground"
                >Fecha del gasto<input
                  type="date"
                  required
                  bind:value={incurredOn}
                  class="mt-1 h-11 w-full rounded-lg border border-border-control bg-surface px-3 focus-visible:ring-2 focus-visible:ring-primary"
                /></label
              >
              <label class="text-sm font-medium text-foreground"
                >Referencia del comprobante<input
                  required
                  maxlength="240"
                  bind:value={reference}
                  class="mt-1 h-11 w-full rounded-lg border border-border-control bg-surface px-3 focus-visible:ring-2 focus-visible:ring-primary"
                /></label
              >
              <label class="text-sm font-medium text-foreground sm:col-span-2"
                >Descripción<input
                  required
                  maxlength="1000"
                  bind:value={description}
                  class="mt-1 h-11 w-full rounded-lg border border-border-control bg-surface px-3 focus-visible:ring-2 focus-visible:ring-primary"
                /></label
              >
            </fieldset>
            {#if categories.length === 0}<p class="text-sm text-warning">
                Registra una categoría activa de otros gastos para continuar.
              </p>{/if}
            <Button type="submit" disabled={saving || categories.length === 0}
              >{saving ? 'Registrando…' : 'Registrar gasto real'}</Button
            >
          </form>
        {/if}
        {#if expenses.length === 0 && !error}<div
            class="mt-5 rounded-lg border border-dashed border-border p-5 text-center"
          >
            <span
              class="mx-auto flex size-8 items-center justify-center rounded-full bg-surface-muted text-foreground-muted"
              aria-hidden="true">$</span
            >
            <p class="mt-2 text-sm font-medium text-foreground">
              Todavía no hay gastos reales registrados
            </p>
            <p class="mt-1 text-sm text-foreground-muted">
              {canRecord
                ? 'Puedes dejar la bitácora vacía si no hubo gastos adicionales. Los gastos previstos permanecen en el presupuesto de la orden.'
                : 'Los gastos previstos permanecen en el presupuesto de la orden.'}
            </p>
            {#if canRecord && categories.length > 0}
              <Button
                type="button"
                variant="secondary"
                size="sm"
                class="mt-3"
                onclick={() => document.getElementById('actual-expense-category')?.focus()}
                >Registrar primer gasto</Button
              >
            {/if}
          </div>
        {:else if expenses.length > 0}<ul class="mt-5 divide-y divide-border">
            {#each expenses as expense (expense.id)}<li
                id={`actual-expense-${expense.id}`}
                tabindex="-1"
                class="py-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                <div class="flex flex-wrap justify-between gap-2">
                  <h3 class="font-medium text-foreground">
                    {categories.find((row) => row.id === expense.expense_type_id)?.name ??
                      'Gasto registrado'} · {expense.reference}
                  </h3>
                  <strong class="font-mono text-foreground">{money(expense.amount)}</strong>
                </div>
                <p class="mt-1 text-sm text-foreground-muted">
                  {date(expense.incurred_on)} · {expense.description}
                </p>
                <p class="mt-1 text-xs text-foreground-muted">
                  Asignado a retaceos activos: {money(expense.allocated_amount)}
                </p>
                {#if Number(expense.unallocated_amount) > 0}
                  <p class="mt-1 text-sm text-warning">
                    Sin incorporar al costo: {money(expense.unallocated_amount)} · Pendiente de revisión
                  </p>
                {/if}
                <PurchaseOrderExpenseDocuments
                  orderId={order.id}
                  orderStatus={order.status}
                  expense={{ ...expense, updated_at: null }}
                />
              </li>{/each}
          </ul>{/if}
      {/if}
    </div>
  </section>
{/if}
