<script lang="ts">
  import { untrack } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesReceivablesApi } from '#lib/api/sales-receivables.ts';
  import {
    DOCUMENT_LABELS,
    METHOD_LABELS,
    REFERENCE_HINTS,
    fromCents,
    sumCents,
    todayLocal
  } from '#lib/features/sales-receivables/labels.ts';
  import { formatDay, formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import type { AccountDocument, PaymentMethod, Receipt } from '#lib/types/sales-receivables.ts';

  let {
    customerId,
    documents,
    preset = null,
    onDone,
    onCancel
  }: {
    customerId: string;
    /** Documentos con saldo del cliente. */
    documents: AccountDocument[];
    /** Cobro de un documento: lo deja marcado por su saldo. */
    preset?: { document_id: string; amount: string } | null;
    onDone: (receipt: Receipt) => void;
    onCancel: () => void;
  } = $props();

  const inputClass =
    'h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';

  const key = `rc-${crypto.randomUUID()}`;
  // El documento a cobrar se toma al abrir el formulario; cambiarlo después no reinicia lo escrito.
  const initial = untrack(() => preset);
  let receivedOn = $state(todayLocal());
  let branchId = $state(branch.id ?? branch.branches[0]?.id ?? '');
  let payments = $state<{ method: PaymentMethod; amount: string; reference: string }[]>([
    { method: 'cash', amount: initial?.amount ?? '', reference: '' }
  ]);
  let amounts = $state<Record<string, string>>(
    initial ? { [initial.document_id]: initial.amount } : {}
  );
  let notes = $state('');
  let busy = $state(false);
  let formError = $state<string | null>(null);

  const open = $derived(documents.filter((item) => Number(item.balance) > 0));
  const paidCents = $derived(sumCents(payments.map((item) => item.amount)));
  const appliedCents = $derived(sumCents(Object.values(amounts)));
  const problem = $derived.by(() => {
    if (!branchId) return 'Elige la sucursal donde se recibe el cobro.';
    if (paidCents <= 0) return 'Indica cuánto se cobró.';
    if (payments.some((item) => item.method !== 'cash' && !item.reference.trim()))
      return 'Indica la referencia de cada pago que no es en efectivo.';
    for (const item of open) {
      const value = Number(amounts[item.id] || 0);
      if (value < 0 || Math.round(value * 100) > Math.round(Number(item.balance) * 100))
        return `Lo aplicado a ${item.control_number} pasa de su saldo.`;
    }
    if (appliedCents > paidCents) return 'Lo aplicado pasa de lo cobrado.';
    return null;
  });

  function settle(item: AccountDocument) {
    amounts = { ...amounts, [item.id]: item.balance };
  }

  function distribute() {
    let left = paidCents;
    const next: Record<string, string> = {};
    for (const item of [...open].sort((a, b) => a.due_on.localeCompare(b.due_on))) {
      if (left <= 0) break;
      const take = Math.min(left, Math.round(Number(item.balance) * 100));
      next[item.id] = fromCents(take);
      left -= take;
    }
    amounts = next;
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (problem || busy) return;
    busy = true;
    formError = null;
    try {
      const receipt = await salesReceivablesApi.register({
        branch_id: branchId,
        customer_id: customerId,
        received_on: receivedOn,
        payments: payments.map((item) => ({
          method: item.method,
          amount: Number(item.amount).toFixed(2),
          reference: item.method === 'cash' ? null : item.reference.trim()
        })),
        applications: Object.entries(amounts)
          .filter(([, value]) => Number(value) > 0)
          .map(([document_id, value]) => ({ document_id, amount: Number(value).toFixed(2) })),
        notes: notes.trim() || null,
        idempotency_key: key
      });
      onDone(receipt);
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo registrar el cobro.';
    } finally {
      busy = false;
    }
  }
</script>

<form
  class="space-y-4 rounded-xl border border-border bg-surface-muted/40 p-4"
  onsubmit={submit}
  aria-label="Nuevo recibo de cobro"
>
  <div class="grid gap-3 sm:grid-cols-2">
    <label class="space-y-1 text-sm text-foreground-muted"
      >Fecha del cobro
      <input class={inputClass} type="date" max={todayLocal()} bind:value={receivedOn} required />
    </label>
    {#if !branch.id}
      <label class="space-y-1 text-sm text-foreground-muted"
        >Sucursal que recibe
        <select class={inputClass} bind:value={branchId}>
          {#each branch.branches as item (item.id)}
            <option value={item.id}>{item.name}</option>
          {/each}
        </select>
      </label>
    {/if}
  </div>

  <fieldset class="space-y-2">
    <legend class="text-sm font-medium text-foreground">Formas de pago</legend>
    {#each payments as payment, index (index)}
      <div class="grid gap-2 sm:grid-cols-[10rem_8rem_1fr_auto]">
        <select
          class={inputClass}
          aria-label="Forma de pago {index + 1}"
          bind:value={payment.method}
        >
          {#each Object.entries(METHOD_LABELS) as [value, label] (value)}
            <option {value}>{label}</option>
          {/each}
        </select>
        <input
          class={inputClass}
          type="number"
          min="0.01"
          step="0.01"
          aria-label="Monto del pago {index + 1}"
          bind:value={payment.amount}
        />
        <input
          class={inputClass}
          aria-label="Referencia del pago {index + 1}"
          placeholder={REFERENCE_HINTS[payment.method]}
          disabled={payment.method === 'cash'}
          bind:value={payment.reference}
        />
        {#if payments.length > 1}
          <Button
            variant="ghost"
            size="sm"
            onclick={() => (payments = payments.filter((_, position) => position !== index))}
            >Quitar</Button
          >
        {/if}
      </div>
    {/each}
    {#if payments.length < 10}
      <Button
        variant="ghost"
        size="sm"
        onclick={() => (payments = [...payments, { method: 'card', amount: '', reference: '' }])}
        >Agregar forma de pago</Button
      >
    {/if}
  </fieldset>

  {#if open.length}
    <fieldset class="space-y-2">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <legend class="text-sm font-medium text-foreground">Aplicar a documentos</legend>
        <Button variant="ghost" size="sm" onclick={distribute}>Aplicar a los más antiguos</Button>
      </div>
      <ul class="divide-y divide-border rounded-lg border border-border bg-surface">
        {#each open as item (item.id)}
          <li class="flex flex-wrap items-center gap-3 p-3 text-sm">
            <div class="min-w-48 flex-1">
              <p class="text-foreground">
                {DOCUMENT_LABELS[item.document_type] ?? item.document_type}
                <span class="text-xs text-foreground-muted">{item.control_number}</span>
              </p>
              <p class="text-xs {item.overdue ? 'text-danger' : 'text-foreground-muted'}">
                Vence {formatDay(item.due_on)} · saldo {formatMoney(item.balance)}
              </p>
            </div>
            <input
              class={inputClass.replace('w-full', 'w-32 shrink-0')}
              type="number"
              min="0"
              step="0.01"
              aria-label="Monto aplicado a {item.control_number}"
              value={amounts[item.id] ?? ''}
              oninput={(event) => (amounts = { ...amounts, [item.id]: event.currentTarget.value })}
            />
            <Button variant="ghost" size="sm" onclick={() => settle(item)}>Saldar</Button>
          </li>
        {/each}
      </ul>
    </fieldset>
  {/if}

  <label class="block space-y-1 text-sm text-foreground-muted"
    >Notas
    <input class={inputClass} maxlength="300" bind:value={notes} />
  </label>

  <dl class="grid grid-cols-3 gap-3 text-sm">
    <div>
      <dt class="text-foreground-muted">Cobrado</dt>
      <dd class="font-semibold tabular-nums text-foreground">
        {formatMoney(fromCents(paidCents))}
      </dd>
    </div>
    <div>
      <dt class="text-foreground-muted">Aplicado</dt>
      <dd class="font-semibold tabular-nums text-foreground">
        {formatMoney(fromCents(appliedCents))}
      </dd>
    </div>
    <div>
      <dt class="text-foreground-muted">Saldo a favor</dt>
      <dd class="font-semibold tabular-nums text-foreground">
        {formatMoney(fromCents(Math.max(paidCents - appliedCents, 0)))}
      </dd>
    </div>
  </dl>

  {#if problem}
    <p class="text-sm text-foreground-muted">{problem}</p>
  {/if}
  {#if formError}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
      role="alert"
    >
      {formError}
    </div>
  {/if}
  <div class="flex flex-wrap gap-2">
    <Button type="submit" disabled={Boolean(problem) || busy}>
      {busy ? 'Registrando…' : 'Registrar cobro'}
    </Button>
    <Button variant="ghost" onclick={onCancel}>Cancelar</Button>
  </div>
</form>
