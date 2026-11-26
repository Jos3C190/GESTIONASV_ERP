<script lang="ts">
  import { untrack } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesReceivablesApi } from '#lib/api/sales-receivables.ts';
  import {
    METHOD_LABELS,
    REFERENCE_HINTS,
    sumCents,
    todayLocal
  } from '#lib/features/sales-receivables/labels.ts';
  import { formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import type { PaymentMethod, Receipt } from '#lib/types/sales-receivables.ts';

  let {
    receipt,
    onDone,
    onCancel
  }: { receipt: Receipt; onDone: (receipt: Receipt) => void; onCancel: () => void } = $props();

  const inputClass =
    'h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';

  // Una llave por formulario: un doble clic o un reintento no reintegra dos veces.
  const key = `ri-${crypto.randomUUID()}`;
  const available = untrack(() => receipt.unapplied);
  let refundedOn = $state(todayLocal());
  let amount = $state(available);
  let method = $state<PaymentMethod>('cash');
  let reference = $state('');
  let reason = $state('');
  let busy = $state(false);
  let formError = $state<string | null>(null);

  const problem = $derived.by(() => {
    const cents = sumCents([String(amount ?? '')]);
    if (cents <= 0) return 'Indica cuánto se reintegra.';
    if (cents > sumCents([available])) return 'El reintegro pasa del saldo a favor del recibo.';
    if (method !== 'cash' && !reference.trim()) return 'Indica la referencia del reintegro.';
    if (reason.trim().length < 5) return 'Indica el motivo (mínimo 5 caracteres).';
    return null;
  });

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (problem) return;
    busy = true;
    formError = null;
    try {
      const saved = await salesReceivablesApi.refund(receipt.id, {
        refunded_on: refundedOn,
        amount: Number(amount).toFixed(2),
        method,
        reference: method === 'cash' ? null : reference.trim(),
        reason: reason.trim(),
        idempotency_key: key
      });
      onDone(saved);
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo registrar el reintegro.';
    } finally {
      busy = false;
    }
  }
</script>

<form
  class="space-y-3 rounded-lg border border-border bg-surface-muted/40 p-3"
  aria-label="Reintegro del recibo {receipt.code}"
  onsubmit={submit}
>
  <p class="text-sm font-medium text-foreground">
    Reintegrar saldo a favor · disponible {formatMoney(available)}
  </p>
  <p class="text-xs text-foreground-muted">
    Es una salida de dinero al cliente; no emite documento tributario.
  </p>
  {#if formError}
    <div
      class="rounded-md border border-danger/30 bg-danger/10 p-2 text-sm text-danger"
      role="alert"
    >
      {formError}
    </div>
  {/if}
  <div class="grid gap-3 sm:grid-cols-2">
    <label class="space-y-1 text-sm text-foreground-muted"
      >Fecha del reintegro
      <input class={inputClass} type="date" max={todayLocal()} bind:value={refundedOn} required />
    </label>
    <label class="space-y-1 text-sm text-foreground-muted"
      >Monto del reintegro
      <input class={inputClass} type="number" min="0.01" step="0.01" bind:value={amount} />
    </label>
    <label class="space-y-1 text-sm text-foreground-muted"
      >Forma de reintegro
      <select
        class={inputClass}
        value={method}
        onchange={(event) => (method = event.currentTarget.value as PaymentMethod)}
      >
        {#each Object.entries(METHOD_LABELS) as [value, label] (value)}
          <option {value}>{label}</option>
        {/each}
      </select>
    </label>
    {#if method !== 'cash'}
      <label class="space-y-1 text-sm text-foreground-muted"
        >{REFERENCE_HINTS[method]}
        <input class={inputClass} maxlength="100" bind:value={reference} />
      </label>
    {/if}
  </div>
  <label class="block space-y-1 text-sm text-foreground-muted"
    >Motivo del reintegro
    <input
      class={inputClass}
      maxlength="300"
      placeholder="Ej.: devolución de mercadería ya pagada"
      bind:value={reason}
    />
  </label>
  {#if problem}<p class="text-xs text-foreground-muted">{problem}</p>{/if}
  <div class="flex gap-2">
    <Button type="submit" disabled={busy || problem !== null}
      >Reintegrar {formatMoney(Number(amount || 0).toFixed(2))}</Button
    >
    <Button variant="ghost" onclick={onCancel}>Cancelar</Button>
  </div>
</form>
