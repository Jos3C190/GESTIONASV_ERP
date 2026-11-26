<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesReceivablesApi } from '#lib/api/sales-receivables.ts';
  import ReceiptForm from '#lib/features/sales-receivables/ReceiptForm.svelte';
  import { fromCents, sumCents, todayLocal } from '#lib/features/sales-receivables/labels.ts';
  import { formatDay, formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import type { AccountDocument, Receipt } from '#lib/types/sales-receivables.ts';

  let { documentId, canCollect }: { documentId: string; canCollect: boolean } = $props();

  const inputClass =
    'h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  let receivable = $state<AccountDocument | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let collecting = $state(false);
  let notice = $state<string | null>(null);
  let certificateOpen = $state(false);
  let certificateNumber = $state('');
  let certificateDate = $state(todayLocal());
  let certificateAmount = $state('');
  let certificateError = $state<string | null>(null);
  /** Recibos del cliente con saldo a favor (V8b1: p. ej. lo que liberó una devolución). */
  let credits = $state<Receipt[]>([]);
  let applyError = $state<string | null>(null);
  let applying = $state(false);

  function applicable(receipt: Receipt): string {
    if (!receivable) return '0.00';
    return fromCents(Math.min(sumCents([receipt.unapplied]), sumCents([receivable.balance])));
  }

  async function loadCredits() {
    credits = [];
    if (!canCollect || !receivable || Number(receivable.balance) <= 0) return;
    try {
      const account = await salesReceivablesApi.account(receivable.customer_id);
      credits = account.receipts.filter(
        (item) => item.status === 'issued' && Number(item.unapplied) > 0
      );
    } catch {
      // El saldo a favor es una ayuda: si no carga, el cobro normal sigue disponible.
      credits = [];
    }
  }

  async function applyCredit(receipt: Receipt) {
    if (!receivable) return;
    applying = true;
    applyError = null;
    const amount = applicable(receipt);
    try {
      await salesReceivablesApi.apply(receipt.id, [{ document_id: receivable.id, amount }]);
      notice = `Se aplicó ${formatMoney(amount)} del saldo a favor del recibo ${receipt.code}.`;
      await load();
    } catch (cause) {
      applyError =
        cause instanceof HttpError ? cause.message : 'No se pudo aplicar el saldo a favor.';
    } finally {
      applying = false;
    }
  }

  async function load() {
    loading = true;
    loadError = null;
    try {
      receivable = await salesReceivablesApi.document(documentId);
      certificateAmount = receivable.withholding;
      await loadCredits();
    } catch (cause) {
      receivable = null;
      loadError =
        cause instanceof HttpError && cause.status === 404
          ? null
          : 'No se pudo cargar el saldo del documento.';
    } finally {
      loading = false;
    }
  }

  onMount(load);

  async function collected(receipt: Receipt) {
    collecting = false;
    notice = `Se registró el recibo ${receipt.code}.`;
    await load();
  }

  async function saveCertificate() {
    certificateError = null;
    try {
      receivable = await salesReceivablesApi.recordCertificate(documentId, {
        certificate_number: certificateNumber.trim(),
        issued_on: certificateDate,
        amount: Number(certificateAmount).toFixed(2)
      });
      certificateOpen = false;
    } catch (cause) {
      certificateError =
        cause instanceof HttpError ? cause.message : 'No se pudo guardar el comprobante.';
    }
  }
</script>

{#if loading}
  <div class="skeleton h-24 rounded-xl" aria-hidden="true"></div>
{:else if loadError}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger" role="alert">
    {loadError}
  </div>
{:else if receivable && !receivable.invalidated}
  <section class="space-y-3 rounded-xl border border-border bg-surface p-4" aria-label="Cobro">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="font-semibold text-foreground">Cobro</h2>
        <p class="mt-1 text-sm text-foreground-muted">
          Vence el {formatDay(receivable.due_on)}.
          <a class="text-primary hover:underline" href="/sales/receivables/{receivable.customer_id}"
            >Ver estado de cuenta</a
          >
        </p>
      </div>
      {#if canCollect && Number(receivable.balance) > 0 && !collecting}
        <Button onclick={() => (collecting = true)}>Registrar cobro</Button>
      {/if}
    </div>
    {#if notice}
      <p class="text-sm text-success" role="status">{notice}</p>
    {/if}
    <dl class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
      <div>
        <dt class="text-foreground-muted">Total a pagar</dt>
        <dd class="tabular-nums text-foreground">{formatMoney(receivable.payable)}</dd>
      </div>
      <div>
        <dt class="text-foreground-muted">Notas y retornos</dt>
        <dd class="tabular-nums text-foreground">{formatMoney(receivable.credited)}</dd>
      </div>
      <div>
        <dt class="text-foreground-muted">Cobrado</dt>
        <dd class="tabular-nums text-foreground">{formatMoney(receivable.applied)}</dd>
      </div>
      <div>
        <dt class="text-foreground-muted">Saldo</dt>
        <dd
          class="font-semibold tabular-nums {receivable.overdue
            ? 'text-danger'
            : 'text-foreground'}"
        >
          {formatMoney(receivable.balance)}{receivable.overdue ? ' · vencido' : ''}
        </dd>
      </div>
    </dl>
    {#if credits.length && Number(receivable.balance) > 0}
      <div
        class="space-y-2 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm"
        aria-label="Saldo a favor del cliente"
      >
        <p class="font-medium text-foreground">El cliente tiene saldo a favor</p>
        {#if applyError}
          <p class="text-danger" role="alert">{applyError}</p>
        {/if}
        {#each credits as item (item.id)}
          <div class="flex flex-wrap items-center justify-between gap-2">
            <span class="text-foreground-muted"
              >{item.code} · saldo a favor {formatMoney(item.unapplied)}</span
            >
            <Button
              size="sm"
              variant="secondary"
              disabled={applying}
              onclick={() => applyCredit(item)}>Aplicar {formatMoney(applicable(item))}</Button
            >
          </div>
        {/each}
      </div>
    {/if}
    {#if collecting}
      <ReceiptForm
        customerId={receivable.customer_id}
        documents={[receivable]}
        preset={{ document_id: receivable.id, amount: receivable.balance }}
        onDone={collected}
        onCancel={() => (collecting = false)}
      />
    {/if}
    {#if Number(receivable.withholding) > 0}
      <div class="rounded-lg border border-border p-3 text-sm">
        <p class="text-foreground">
          Retención del 1 %: {formatMoney(receivable.withholding)}
          {#if receivable.certificate}
            · comprobante {receivable.certificate.certificate_number} del
            {formatDay(receivable.certificate.issued_on)}
          {:else}
            · <span class="text-warning">falta el comprobante del cliente</span>
          {/if}
        </p>
        {#if canCollect && !certificateOpen}
          <Button variant="ghost" size="sm" onclick={() => (certificateOpen = true)}>
            {receivable.certificate ? 'Corregir comprobante' : 'Registrar comprobante de retención'}
          </Button>
        {/if}
        {#if certificateOpen}
          <div class="mt-2 grid gap-2 sm:grid-cols-3">
            <input
              class={inputClass}
              aria-label="Número del comprobante de retención"
              placeholder="Número o código de generación"
              bind:value={certificateNumber}
            />
            <input
              class={inputClass}
              type="date"
              aria-label="Fecha del comprobante"
              bind:value={certificateDate}
            />
            <input
              class={inputClass}
              type="number"
              step="0.01"
              min="0.01"
              aria-label="Monto retenido"
              bind:value={certificateAmount}
            />
          </div>
          {#if certificateError}
            <p class="mt-2 text-sm text-danger" role="alert">{certificateError}</p>
          {/if}
          <div class="mt-2 flex gap-2">
            <Button size="sm" disabled={!certificateNumber.trim()} onclick={saveCertificate}
              >Guardar comprobante</Button
            >
            <Button variant="ghost" size="sm" onclick={() => (certificateOpen = false)}
              >Cancelar</Button
            >
          </div>
        {/if}
      </div>
    {/if}
  </section>
{/if}
