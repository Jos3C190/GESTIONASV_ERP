<script lang="ts">
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import {
    kardexMoney,
    kardexNumber,
    formatKardexDate
  } from '$lib/features/inventory/kardex-format';
  import { valuationKind } from '$lib/features/inventory/valuation';
  import type { ValuationCostBreakdown, ValuedKardex } from '$lib/features/inventory/kardex';

  let {
    data,
    loading,
    onPageChange,
    canReadRetaceos = false
  }: {
    data: ValuedKardex;
    loading: boolean;
    onPageChange: (page: number) => void;
    canReadRetaceos?: boolean;
  } = $props();

  const breakdownValue = (cost: ValuationCostBreakdown) =>
    cost.cost_adjustment ?? cost.value_delta ?? cost.inventory_delta ?? cost.amount ?? null;
  const breakdownSource = (cost: ValuationCostBreakdown) =>
    cost.source_reference ?? cost.event_id ?? '—';
  const quantityLabel = (kind: string, quantity: string) => {
    const numeric = Number(quantity);
    if (!Number.isFinite(numeric) || numeric === 0) return 'Sin movimiento físico';
    if (['issue', 'supplier_return', 'adjustment_out'].includes(kind)) {
      return `Salida ${kardexNumber(quantity)}`;
    }
    if (['receipt', 'customer_return', 'adjustment_in', 'opening'].includes(kind)) {
      return `Entrada ${kardexNumber(quantity)}`;
    }
    return `Movimiento ${kardexNumber(quantity)}`;
  };
  const breakdownDescription = (entryKind: string, cost: ValuationCostBreakdown) => {
    if (entryKind === 'cost_adjustment') {
      return cost.cost_delta == null
        ? `Efecto en salidas: dato histórico no disponible · origen ${breakdownSource(cost)}`
        : `Efecto en salidas: ${kardexMoney(cost.cost_delta, data.setting?.currency)} · origen ${breakdownSource(cost)}`;
    }
    if (entryKind === 'supplier_credit' || cost.kind === 'supplier_credit') {
      return `Crédito del proveedor: ${kardexMoney(cost.credit_net, data.setting?.currency)} · costo retirado: ${kardexMoney(cost.inventory_cost, data.setting?.currency)} · diferencia: ${kardexMoney(cost.cost_difference, data.setting?.currency)}`;
    }
    return `Origen ${breakdownSource(cost)} · ${kardexMoney(breakdownValue(cost), data.setting?.currency)}`;
  };
</script>

<div class="space-y-3 xl:hidden">
  {#each data.entries as entry (entry.id)}
    <article class="space-y-3 rounded-lg border border-border bg-surface p-4">
      <header class="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p class="font-medium text-foreground">{formatKardexDate(entry.accounting_date)}</p>
          <p class="mt-1 text-xs text-foreground-muted">
            Fecha operativa: {formatKardexDate(entry.operational_date)}
          </p>
        </div>
        <Badge>{valuationKind[entry.kind] ?? entry.kind}</Badge>
      </header>
      <p class="break-all font-mono text-xs text-foreground-muted">{entry.source_reference}</p>
      <dl class="grid grid-cols-2 gap-3 rounded-lg bg-surface-muted/50 p-3 text-sm">
        <div>
          <dt class="text-xs text-foreground-muted">Movimiento físico</dt>
          <dd class="mt-1 font-semibold tabular-nums">
            {quantityLabel(entry.kind, entry.quantity_base)}
          </dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Cambio de valor</dt>
          <dd class="mt-1 font-semibold tabular-nums">
            {kardexMoney(entry.inventory_delta, data.setting?.currency)}
          </dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Saldo en unidades</dt>
          <dd class="mt-1 font-semibold tabular-nums">{kardexNumber(entry.balance_quantity)}</dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Saldo valorizado</dt>
          <dd class="mt-1 font-semibold tabular-nums">
            {kardexMoney(entry.balance_value, data.setting?.currency)}
          </dd>
        </div>
        <div class="col-span-2 border-t border-border pt-2">
          <dt class="text-xs text-foreground-muted">Costo promedio vigente</dt>
          <dd class="mt-1 font-semibold tabular-nums">
            {kardexMoney(entry.average_unit_cost, data.setting?.currency)}
          </dd>
        </div>
      </dl>
      {#if entry.retaceo_id && canReadRetaceos}
        <a
          class="inline-block text-sm font-medium text-primary underline-offset-4 hover:underline"
          href="/retaceos/{entry.retaceo_id}">Ver retaceo aplicado</a
        >
      {/if}
      {#if entry.cost_breakdown.length > 0}
        <details>
          <summary
            class="cursor-pointer text-sm text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >Ver distribución del ajuste</summary
          >
          <ul class="mt-2 space-y-1 text-xs text-foreground-muted">
            {#each entry.cost_breakdown as cost, index (`${entry.id}-${index}`)}
              <li>
                {breakdownDescription(entry.kind, cost)}
              </li>
            {/each}
          </ul>
        </details>
      {/if}
    </article>
  {/each}
</div>

<div class="hidden overflow-x-auto rounded-lg border border-border xl:block">
  <table class="w-full min-w-[900px] text-left text-sm">
    <caption class="sr-only">Movimientos del costo promedio</caption>
    <thead class="bg-surface-muted/60 text-xs text-foreground-muted">
      <tr>
        <th scope="col" class="px-3 py-3">Fecha contable / operativa</th>
        <th scope="col" class="px-3 py-3">Evento y documento</th>
        <th scope="col" class="px-3 py-3 text-right">Cantidad</th>
        <th scope="col" class="px-3 py-3 text-right">Cambio de valor</th>
        <th scope="col" class="px-3 py-3 text-right">Saldo de cantidad / valor</th>
        <th scope="col" class="px-3 py-3 text-right">Costo promedio</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-border">
      {#each data.entries as entry (entry.id)}
        <tr class="align-top">
          <td class="whitespace-nowrap px-3 py-3">
            <p>{formatKardexDate(entry.accounting_date)}</p>
            <p class="mt-1 text-xs text-foreground-muted">
              Operativa: {formatKardexDate(entry.operational_date)}
            </p>
          </td>
          <td class="px-3 py-3">
            <Badge>{valuationKind[entry.kind] ?? entry.kind}</Badge>
            <p class="mt-2 break-all font-mono text-xs text-foreground-muted">
              {entry.source_reference}
            </p>
            {#if entry.retaceo_id && canReadRetaceos}
              <a
                class="mt-1 inline-block text-xs text-primary underline-offset-4 hover:underline"
                href="/retaceos/{entry.retaceo_id}">Ver retaceo aplicado</a
              >
            {/if}
            {#if entry.cost_breakdown.length > 0}
              <details class="mt-2">
                <summary
                  class="cursor-pointer text-xs text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >Ver distribución del ajuste</summary
                >
                <ul class="mt-2 space-y-1 text-xs text-foreground-muted">
                  {#each entry.cost_breakdown as cost, index (`${entry.id}-${index}`)}
                    <li>
                      {breakdownDescription(entry.kind, cost)}
                    </li>
                  {/each}
                </ul>
              </details>
            {/if}
          </td>
          <td class="px-3 py-3 text-right tabular-nums"
            >{quantityLabel(entry.kind, entry.quantity_base)}</td
          >
          <td class="px-3 py-3 text-right tabular-nums"
            >{kardexMoney(entry.inventory_delta, data.setting?.currency)}</td
          >
          <td class="px-3 py-3 text-right tabular-nums">
            {kardexNumber(entry.balance_quantity)}
            <span class="block text-xs text-foreground-muted"
              >{kardexMoney(entry.balance_value, data.setting?.currency)}</span
            >
          </td>
          <td class="px-3 py-3 text-right tabular-nums"
            >{kardexMoney(entry.average_unit_cost, data.setting?.currency)}</td
          >
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
  <p class="text-sm text-foreground-muted">
    {data.total} evento(s) · Página {data.page} de {Math.max(
      1,
      Math.ceil(data.total / data.page_size)
    )}
  </p>
  <div class="flex gap-2">
    <Button
      variant="secondary"
      disabled={data.page <= 1 || loading}
      onclick={() => onPageChange(data.page - 1)}>Anterior</Button
    >
    <Button
      variant="secondary"
      disabled={data.page * data.page_size >= data.total || loading}
      onclick={() => onPageChange(data.page + 1)}>Siguiente</Button
    >
  </div>
</div>
