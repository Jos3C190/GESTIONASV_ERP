<script lang="ts">
  import { purchaseOrdersApi } from '$lib/api/purchase-orders';
  import type { PurchaseOrder } from '$lib/types/purchase-order';
  import Button from '$lib/components/ui/Button.svelte';
  let {
    orderId,
    actualExpenses,
    currency
  }: { orderId: string; actualExpenses: number; currency: string } = $props();
  let order = $state<PurchaseOrder | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let retry = $state(0);
  function money(amount: number) {
    return new Intl.NumberFormat('es-SV', { style: 'currency', currency }).format(amount);
  }
  let planned = $derived(order?.expenses.reduce((sum, cost) => sum + Number(cost.amount), 0) ?? 0);
  $effect(() => {
    const id = orderId;
    void retry;
    let active = true;
    order = null;
    loading = true;
    error = null;
    void purchaseOrdersApi
      .get(id)
      .then((value) => {
        if (active) order = value;
      })
      .catch((cause) => {
        if (active)
          error =
            cause instanceof Error
              ? cause.message
              : 'No se pudieron consultar los gastos previstos.';
      })
      .finally(() => {
        if (active) loading = false;
      });
    return () => {
      active = false;
    };
  });
</script>

<section
  class="rounded-xl border border-border bg-surface p-4"
  aria-labelledby="planned-expenses-heading"
  aria-busy={loading}
>
  <h2 id="planned-expenses-heading" class="font-semibold text-foreground">
    Comparación de gastos previstos y reales
  </h2>
  <p class="mt-1 text-sm leading-6 text-foreground-muted">
    Los previstos corresponden a la orden completa. Para una recepción parcial, compara solamente
    los gastos reales atribuibles a esta compra. Esta consulta no asigna importes al retaceo.
  </p>
  {#if loading}<div
      class="skeleton mt-4 h-20 rounded-lg"
      aria-label="Cargando gastos previstos"
    ></div>
  {:else if error}<p class="mt-3 text-sm text-foreground" role="alert">{error}</p>
    <Button class="mt-3" size="sm" variant="secondary" onclick={() => (retry += 1)}
      >Reintentar consulta</Button
    >
  {:else if order}
    <div class="mt-4 grid gap-4 sm:grid-cols-3">
      <div>
        <p class="text-xs text-foreground-muted">Previstos en {order.code}</p>
        <p class="mt-1 font-semibold tabular-nums text-foreground">{money(planned)}</p>
      </div>
      <div>
        <p class="text-xs text-foreground-muted">Reales de este retaceo · sin IVA</p>
        <p class="mt-1 font-semibold tabular-nums text-foreground">{money(actualExpenses)}</p>
      </div>
      <div>
        <p class="text-xs text-foreground-muted">Variación frente a la orden completa</p>
        <p class="mt-1 font-semibold tabular-nums text-foreground">
          {money(actualExpenses - planned)}
        </p>
      </div>
    </div>
    <details class="mt-4 border-t border-border pt-3">
      <summary class="cursor-pointer text-sm font-medium text-foreground"
        >Conceptos previstos ({order.expenses.length})</summary
      >
      <ul class="mt-3 space-y-2">
        {#each order.expenses as expense (expense.id)}<li
            class="flex justify-between gap-3 text-sm text-foreground-muted"
          >
            <span>{expense.description ?? 'Gasto previsto en la orden'}</span><span
              class="shrink-0 tabular-nums">{money(Number(expense.amount))}</span
            >
          </li>{/each}
      </ul>
      {#if !order.expenses.length}<p class="mt-2 text-sm text-foreground-muted">
          Esta orden no tiene gastos previstos registrados.
        </p>{/if}<a
        href={`/purchase-orders/${order.id}`}
        class="mt-3 inline-block rounded text-sm text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >Consultar orden de compra</a
      >
    </details>
  {/if}
</section>
