<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { kardexMoney, kardexNumber } from '$lib/features/inventory/kardex-format';
  import type { Reconciliation, ReconciliationRow } from '$lib/features/inventory/kardex';

  let {
    data,
    page,
    onPageChange,
    onOpenKardex
  }: {
    data: Reconciliation;
    page: number;
    onPageChange: (page: number) => void;
    onOpenKardex: (row: ReconciliationRow) => void;
  } = $props();
</script>

<div class="space-y-3 xl:hidden">
  {#each data.items as row (row.inventory_item_id)}
    <article class="space-y-3 rounded-lg border border-border bg-surface p-4">
      <header>
        <h3 class="font-semibold text-foreground">{row.product_name}</h3>
        {#if row.sku}<p class="mt-1 font-mono text-xs text-foreground-muted">{row.sku}</p>{/if}
        <p class="mt-1 text-xs text-foreground-muted">Unidad base: {row.base_unit_symbol}</p>
      </header>
      <dl class="grid grid-cols-2 gap-3 rounded-lg bg-surface-muted/50 p-3 text-sm">
        <div>
          <dt class="text-xs text-foreground-muted">Cantidad física</dt>
          <dd class="mt-1 font-semibold tabular-nums">{kardexNumber(row.physical_quantity)}</dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Cantidad valorada</dt>
          <dd class="mt-1 font-semibold tabular-nums">{kardexNumber(row.valued_quantity)}</dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Diferencia</dt>
          <dd class="mt-1 font-semibold tabular-nums">{kardexNumber(row.quantity_difference)}</dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Costo promedio</dt>
          <dd class="mt-1 font-semibold tabular-nums">
            {kardexMoney(row.average_unit_cost, data.currency ?? 'USD', 6)}
          </dd>
        </div>
        <div class="col-span-2 border-t border-border pt-2">
          <dt class="text-xs text-foreground-muted">Valor del inventario</dt>
          <dd class="mt-1 font-semibold tabular-nums">
            {kardexMoney(row.inventory_value, data.currency ?? 'USD')}
          </dd>
        </div>
      </dl>
      <Button variant="secondary" class="whitespace-nowrap" onclick={() => onOpenKardex(row)}
        ><span>Ver Kardex<span class="sr-only"> de {row.product_name}</span></span></Button
      >
    </article>
  {/each}
</div>

<div class="hidden overflow-x-auto rounded-lg border border-border xl:block">
  <table class="w-full min-w-[760px] text-left text-sm">
    <caption class="sr-only">Conciliación entre cantidad física y valorada</caption>
    <thead class="bg-surface-muted/60 text-xs text-foreground-muted">
      <tr>
        <th scope="col" class="px-3 py-3">Artículo</th>
        <th scope="col" class="px-3 py-3 text-right">Cantidad física</th>
        <th scope="col" class="px-3 py-3 text-right">Cantidad valorada</th>
        <th scope="col" class="px-3 py-3 text-right">Diferencia</th>
        <th scope="col" class="px-3 py-3 text-right">Valor</th>
        <th scope="col" class="px-3 py-3 text-right">Costo promedio</th>
        <th scope="col" class="px-3 py-3">Historial</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-border">
      {#each data.items as row (row.inventory_item_id)}
        <tr>
          <th scope="row" class="px-3 py-3 font-medium text-foreground">
            <span>{row.product_name}</span>
            {#if row.sku}<span class="mt-1 block font-mono text-xs text-foreground-muted"
                >{row.sku}</span
              >{/if}
            <span class="mt-1 block text-xs text-foreground-muted"
              >Unidad base: {row.base_unit_symbol}</span
            >
          </th>
          <td class="px-3 py-3 text-right tabular-nums">{kardexNumber(row.physical_quantity)}</td>
          <td class="px-3 py-3 text-right tabular-nums">{kardexNumber(row.valued_quantity)}</td>
          <td class="px-3 py-3 text-right tabular-nums">{kardexNumber(row.quantity_difference)}</td>
          <td class="px-3 py-3 text-right tabular-nums"
            >{kardexMoney(row.inventory_value, data.currency ?? 'USD')}</td
          >
          <td class="px-3 py-3 text-right tabular-nums"
            >{kardexMoney(row.average_unit_cost, data.currency ?? 'USD', 6)}</td
          >
          <td class="px-3 py-3"
            ><Button variant="secondary" class="whitespace-nowrap" onclick={() => onOpenKardex(row)}
              ><span>Ver Kardex<span class="sr-only"> de {row.product_name}</span></span></Button
            ></td
          >
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
  <p class="text-sm text-foreground-muted">
    {data.total} artículo(s) · Página {data.page} de {Math.max(
      1,
      Math.ceil(data.total / data.page_size)
    )}
  </p>
  <div class="flex gap-2">
    <Button variant="secondary" disabled={page <= 1} onclick={() => onPageChange(page - 1)}
      >Anterior</Button
    >
    <Button
      variant="secondary"
      disabled={page * data.page_size >= data.total}
      onclick={() => onPageChange(page + 1)}>Siguiente</Button
    >
  </div>
</div>
