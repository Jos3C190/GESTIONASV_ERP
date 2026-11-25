<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesReceivablesApi } from '#lib/api/sales-receivables.ts';
  import ReceiptForm from '#lib/features/sales-receivables/ReceiptForm.svelte';
  import {
    BUCKETS,
    BUCKET_LABELS,
    DOCUMENT_LABELS,
    METHOD_LABELS,
    fromCents,
    sumCents
  } from '#lib/features/sales-receivables/labels.ts';
  import { formatDay, formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import type { CustomerAccount, Receipt } from '#lib/types/sales-receivables.ts';

  let { customerId, canCollect }: { customerId: string; canCollect: boolean } = $props();

  const inputClass =
    'h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';
  const head = 'px-3 py-2 text-left text-xs font-medium uppercase text-foreground-muted';
  const cell = 'px-3 py-2 text-right tabular-nums';

  let account = $state<CustomerAccount | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let creating = $state(false);
  let notice = $state<string | null>(null);
  let annulling = $state<string | null>(null);
  let annulReason = $state('');
  let applying = $state<string | null>(null);
  let applyAmounts = $state<Record<string, string>>({});
  let actionError = $state<string | null>(null);
  let busy = $state(false);

  const openDocuments = $derived(
    account ? account.documents.filter((item) => Number(item.balance) > 0) : []
  );

  async function load() {
    loading = true;
    loadError = null;
    try {
      account = await salesReceivablesApi.account(customerId);
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudo cargar el estado de cuenta.';
    } finally {
      loading = false;
    }
  }

  onMount(load);

  async function done(receipt: Receipt) {
    creating = false;
    notice = `Se registró el recibo ${receipt.code} por ${formatMoney(receipt.total)}.`;
    await load();
  }

  async function openPdf(receipt: Receipt) {
    actionError = null;
    try {
      const url = URL.createObjectURL(await salesReceivablesApi.receiptPdf(receipt.id));
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (cause) {
      actionError = cause instanceof HttpError ? cause.message : 'No se pudo abrir el recibo.';
    }
  }

  async function annul(receipt: Receipt) {
    busy = true;
    actionError = null;
    try {
      await salesReceivablesApi.annul(receipt.id, annulReason.trim());
      annulling = null;
      annulReason = '';
      notice = `Se anuló el recibo ${receipt.code}; sus saldos volvieron a los documentos.`;
      await load();
    } catch (cause) {
      actionError = cause instanceof HttpError ? cause.message : 'No se pudo anular el recibo.';
    } finally {
      busy = false;
    }
  }

  async function apply(receipt: Receipt) {
    busy = true;
    actionError = null;
    try {
      await salesReceivablesApi.apply(
        receipt.id,
        Object.entries(applyAmounts)
          .filter(([, value]) => Number(value) > 0)
          .map(([document_id, value]) => ({ document_id, amount: Number(value).toFixed(2) }))
      );
      applying = null;
      applyAmounts = {};
      notice = `Se aplicó saldo a favor del recibo ${receipt.code}.`;
      await load();
    } catch (cause) {
      actionError =
        cause instanceof HttpError ? cause.message : 'No se pudo aplicar el saldo a favor.';
    } finally {
      busy = false;
    }
  }
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
{:else if account}
  <div class="space-y-5">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p class="text-xs font-semibold uppercase tracking-wider text-primary">
          Cuentas por cobrar
        </p>
        <h1 class="mt-1 text-2xl font-bold tracking-tight text-foreground">
          {account.customer.name}
        </h1>
        <p class="text-sm text-foreground-muted">
          {account.customer.code} · Crédito a {account.customer.credit_days} días
          {#if account.customer.credit_limit}
            · Límite {formatMoney(account.customer.credit_limit)}{/if}
        </p>
      </div>
      {#if canCollect && !creating}
        <Button onclick={() => (creating = true)}>Registrar cobro</Button>
      {/if}
    </header>

    {#if notice}
      <p class="text-sm text-success" role="status">{notice}</p>
    {/if}

    <dl class="grid gap-3 sm:grid-cols-3">
      {#each [['Saldo', account.balance], ['Vencido', account.overdue], ['Saldo a favor', account.credit]] as [label, value] (label)}
        <div class="rounded-xl border border-border bg-surface p-4">
          <dt class="text-sm text-foreground-muted">{label}</dt>
          <dd
            class="mt-1 text-xl font-semibold tabular-nums {label === 'Vencido' && Number(value) > 0
              ? 'text-danger'
              : 'text-foreground'}"
          >
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
          <dd class="tabular-nums text-foreground">{formatMoney(account.aging[bucket])}</dd>
        </div>
      {/each}
    </dl>

    {#if creating}
      <ReceiptForm
        customerId={account.customer.id}
        documents={account.documents}
        onDone={done}
        onCancel={() => (creating = false)}
      />
    {/if}

    <section
      class="overflow-x-auto rounded-xl border border-border bg-surface"
      aria-label="Documentos"
    >
      {#if account.documents.length === 0}
        <p class="p-6 text-center text-sm text-foreground-muted">
          Este cliente no tiene documentos por cobrar.
        </p>
      {:else}
        <table class="min-w-full text-sm">
          <thead class="bg-surface-muted">
            <tr>
              <th class={head}>Documento</th>
              <th class={head}>Pedido</th>
              <th class={head}>Emisión</th>
              <th class={head}>Vence</th>
              <th class="{head} text-right">Total a pagar</th>
              <th class="{head} text-right">Notas y retornos</th>
              <th class="{head} text-right">Cobrado</th>
              <th class="{head} text-right">Saldo</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each account.documents as item (item.id)}
              <tr>
                <td class="px-3 py-2"
                  ><a class="text-primary hover:underline" href="/sales/fiscal-documents/{item.id}"
                    >{DOCUMENT_LABELS[item.document_type] ?? item.document_type}</a
                  >
                  <span class="block text-xs text-foreground-muted">{item.control_number}</span>
                  {#if item.invalidated}<span class="text-xs text-warning">Invalidado</span>{/if}
                </td>
                <td class="px-3 py-2"
                  ><a class="hover:underline" href="/sales/{item.sale_id}">{item.sale_code}</a></td
                >
                <td class="px-3 py-2 whitespace-nowrap">{formatDay(item.issued_on)}</td>
                <td
                  class="px-3 py-2 whitespace-nowrap {item.overdue
                    ? 'font-medium text-danger'
                    : ''}">{formatDay(item.due_on)}</td
                >
                <td class={cell}>{formatMoney(item.payable)}</td>
                <td class={cell}>{formatMoney(item.credited)}</td>
                <td class={cell}>{formatMoney(item.applied)}</td>
                <td class="{cell} font-medium">{formatMoney(item.balance)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </section>

    <section class="space-y-3" aria-label="Recibos de cobro">
      <h2 class="font-semibold text-foreground">Recibos de cobro</h2>
      {#if actionError}
        <div
          class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
          role="alert"
        >
          {actionError}
        </div>
      {/if}
      {#if account.receipts.length === 0}
        <p class="text-sm text-foreground-muted">Todavía no hay recibos.</p>
      {/if}
      {#each account.receipts as receipt (receipt.id)}
        <article class="space-y-2 rounded-xl border border-border bg-surface p-4 text-sm">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p>
              <span class="font-medium text-foreground">{receipt.code}</span>
              <span class="text-foreground-muted">· {formatDay(receipt.received_on)}</span>
              <span class="tabular-nums text-foreground">· {formatMoney(receipt.total)}</span>
              {#if receipt.status === 'annulled'}
                <span
                  class="rounded-full bg-surface-muted px-2 py-0.5 text-xs text-foreground-muted"
                  >Anulado</span
                >
              {:else if Number(receipt.unapplied) > 0}
                <span class="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary"
                  >Saldo a favor {formatMoney(receipt.unapplied)}</span
                >
              {/if}
            </p>
            <div class="flex gap-2">
              <Button variant="ghost" size="sm" onclick={() => openPdf(receipt)}>PDF</Button>
              {#if canCollect && receipt.status === 'issued'}
                {#if Number(receipt.unapplied) > 0 && openDocuments.length}
                  <Button variant="secondary" size="sm" onclick={() => (applying = receipt.id)}
                    >Aplicar saldo a favor</Button
                  >
                {/if}
                <Button variant="ghost" size="sm" onclick={() => (annulling = receipt.id)}
                  >Anular</Button
                >
              {/if}
            </div>
          </div>
          <p class="text-xs text-foreground-muted">
            {receipt.payments
              .map(
                (payment) =>
                  `${METHOD_LABELS[payment.method]} ${formatMoney(payment.amount)}${payment.reference ? ` (${payment.reference})` : ''}`
              )
              .join(' · ')}
          </p>
          {#if receipt.applications.length}
            <p class="text-xs text-foreground-muted">
              Aplicado a: {receipt.applications
                .map((item) => `${item.control_number} ${formatMoney(item.amount)}`)
                .join(' · ')}
            </p>
          {/if}
          {#if receipt.annul_reason}
            <p class="text-xs text-foreground-muted">Motivo de anulación: {receipt.annul_reason}</p>
          {/if}
          {#if annulling === receipt.id}
            <div class="flex flex-wrap items-end gap-2">
              <label class="flex-1 space-y-1 text-foreground-muted"
                >Motivo de la anulación
                <input class={inputClass} maxlength="300" bind:value={annulReason} />
              </label>
              <Button
                variant="danger"
                disabled={busy || annulReason.trim().length < 5}
                onclick={() => annul(receipt)}>Anular recibo</Button
              >
              <Button variant="ghost" onclick={() => (annulling = null)}>Cancelar</Button>
            </div>
          {/if}
          {#if applying === receipt.id}
            <div class="space-y-2">
              {#each openDocuments as item (item.id)}
                <label class="flex items-center gap-3 text-foreground-muted">
                  <span class="flex-1"
                    >{item.control_number} · saldo {formatMoney(item.balance)}</span
                  >
                  <input
                    class="{inputClass} w-32"
                    type="number"
                    min="0"
                    step="0.01"
                    aria-label="Saldo a favor aplicado a {item.control_number}"
                    value={applyAmounts[item.id] ?? ''}
                    oninput={(event) =>
                      (applyAmounts = { ...applyAmounts, [item.id]: event.currentTarget.value })}
                  />
                </label>
              {/each}
              <div class="flex gap-2">
                <Button
                  disabled={busy ||
                    sumCents(Object.values(applyAmounts)) <= 0 ||
                    sumCents(Object.values(applyAmounts)) > sumCents([receipt.unapplied])}
                  onclick={() => apply(receipt)}
                  >Aplicar {formatMoney(fromCents(sumCents(Object.values(applyAmounts))))}</Button
                >
                <Button variant="ghost" onclick={() => (applying = null)}>Cancelar</Button>
              </div>
            </div>
          {/if}
        </article>
      {/each}
    </section>
  </div>
{/if}
