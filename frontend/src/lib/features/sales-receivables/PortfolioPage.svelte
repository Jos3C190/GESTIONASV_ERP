<script lang="ts">
  import { onMount } from 'svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesReceivablesApi } from '#lib/api/sales-receivables.ts';
  import {
    BUCKETS,
    BUCKET_LABELS,
    sumCents,
    fromCents
  } from '#lib/features/sales-receivables/labels.ts';
  import { formatDay, formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import type { AgingBucket, CustomerSummary } from '#lib/types/sales-receivables.ts';

  const head = 'px-3 py-2 text-left text-xs font-medium uppercase text-foreground-muted';
  const cell = 'px-3 py-2 text-right tabular-nums';

  let rows = $state<CustomerSummary[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let search = $state('');

  const visible = $derived(
    rows.filter((row) =>
      `${row.customer.name} ${row.customer.code}`.toLowerCase().includes(search.toLowerCase())
    )
  );
  const totals = $derived({
    balance: fromCents(sumCents(rows.map((row) => row.balance))),
    overdue: fromCents(sumCents(rows.map((row) => row.overdue))),
    credit: fromCents(sumCents(rows.map((row) => row.credit)))
  });

  function bucketTotal(bucket: AgingBucket): string {
    return fromCents(sumCents(rows.map((row) => row.aging[bucket])));
  }

  onMount(async () => {
    try {
      rows = await salesReceivablesApi.portfolio();
    } catch (cause) {
      loadError = cause instanceof HttpError ? cause.message : 'No se pudo cargar la cartera.';
    } finally {
      loading = false;
    }
  });
</script>

{#if loading}
  <div class="space-y-3" aria-hidden="true">
    <div class="skeleton h-20 rounded-xl"></div>
    <div class="skeleton h-64 rounded-xl"></div>
  </div>
{:else if loadError}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    {loadError}
  </div>
{:else if rows.length === 0}
  <div
    class="flex flex-col items-center gap-3 rounded-xl border border-border bg-surface p-10 text-center"
  >
    <span
      class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-foreground-muted"
      >$</span
    >
    <p class="text-sm text-foreground-muted">
      No hay cuentas por cobrar: los documentos emitidos están cobrados.
    </p>
    <a class="text-sm text-primary hover:underline" href="/sales/fiscal-documents"
      >Ver documentos fiscales</a
    >
  </div>
{:else}
  <div class="space-y-4">
    <dl class="grid gap-3 sm:grid-cols-3">
      {#each [['Por cobrar', totals.balance], ['Vencido', totals.overdue], ['Saldos a favor', totals.credit]] as [label, value] (label)}
        <div class="rounded-xl border border-border bg-surface p-4">
          <dt class="text-sm text-foreground-muted">{label}</dt>
          <dd class="mt-1 text-xl font-semibold tabular-nums text-foreground">
            {formatMoney(value)}
          </dd>
        </div>
      {/each}
    </dl>
    <dl
      class="grid grid-cols-2 gap-2 rounded-xl border border-border bg-surface p-4 sm:grid-cols-5"
    >
      {#each BUCKETS as bucket (bucket)}
        <div>
          <dt class="text-xs text-foreground-muted">{BUCKET_LABELS[bucket]}</dt>
          <dd class="tabular-nums text-foreground">{formatMoney(bucketTotal(bucket))}</dd>
        </div>
      {/each}
    </dl>
    <input
      class="h-10 w-full max-w-sm rounded-md border border-border bg-background px-3 text-sm text-foreground"
      placeholder="Buscar cliente"
      aria-label="Buscar cliente"
      bind:value={search}
    />
    <div class="overflow-x-auto rounded-xl border border-border bg-surface">
      <table class="min-w-full text-sm">
        <thead class="bg-surface-muted">
          <tr>
            <th class={head}>Cliente</th>
            <th class="{head} text-right">Saldo</th>
            <th class="{head} text-right">Vencido</th>
            <th class="{head} text-right">Más de 90 días</th>
            <th class="{head} text-right">Saldo a favor</th>
            <th class={head}>Vence desde</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border">
          {#each visible as row (row.customer.id)}
            <tr>
              <td class="px-3 py-2"
                ><a
                  class="font-medium text-primary hover:underline"
                  href="/sales/receivables/{row.customer.id}">{row.customer.name}</a
                >
                <span class="block text-xs text-foreground-muted">{row.customer.code}</span></td
              >
              <td class={cell}>{formatMoney(row.balance)}</td>
              <td class="{cell} {Number(row.overdue) > 0 ? 'text-danger' : ''}"
                >{formatMoney(row.overdue)}</td
              >
              <td class={cell}>{formatMoney(row.aging.over_90)}</td>
              <td class={cell}>{formatMoney(row.credit)}</td>
              <td class="px-3 py-2 whitespace-nowrap">{formatDay(row.oldest_due)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
{/if}
