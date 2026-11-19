<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesInvoicesApi } from '#lib/api/sales-invoices.ts';
  import {
    FISCAL_DOCUMENT_LABELS,
    FISCAL_STATUS_BADGES,
    FISCAL_STATUS_LABELS,
    NATURE_LABELS,
    NOTE_LINE_KIND_LABELS
  } from '#lib/features/sales/fiscal-labels.ts';
  import { estimate, formatQuantity, returnAmount } from '#lib/features/sales/note-calc.ts';
  import { formatDay, formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import type {
    CreditLineInput,
    DebitChargeInput,
    FiscalDocument,
    FiscalNature,
    NotesOverview
  } from '#lib/types/sales-invoices.ts';

  let {
    document,
    canIssue,
    onOverview = () => {}
  }: {
    document: FiscalDocument;
    canIssue: boolean;
    onOverview?: (overview: NotesOverview) => void;
  } = $props();

  const inputClass =
    'h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';

  type CreditChoice = { kind: '' | 'return' | 'discount'; value: string };
  type Charge = {
    key: number;
    line: string;
    description: string;
    quantity: string;
    unitPrice: string;
    nature: FiscalNature;
  };

  let overview = $state<NotesOverview | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let mode = $state<'credit' | 'debit' | null>(null);
  let reason = $state('');
  let choices = $state<Record<number, CreditChoice>>({});
  let charges = $state<Charge[]>([]);
  let nextKey = 0;
  let busy = $state(false);
  let formError = $state<string | null>(null);
  let notice = $state<string | null>(null);

  async function load() {
    loading = true;
    loadError = null;
    try {
      overview = await salesInvoicesApi.notes(document.id);
      onOverview(overview);
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudieron consultar las notas.';
    } finally {
      loading = false;
    }
  }
  onMount(() => void load());

  function newCharge(): Charge {
    return {
      key: nextKey++,
      line: '',
      description: '',
      quantity: '1',
      unitPrice: '',
      nature: 'taxed'
    };
  }

  function open(next: 'credit' | 'debit') {
    mode = next;
    reason = '';
    choices = {};
    charges = next === 'debit' ? [newCharge()] : [];
    formError = null;
    notice = null;
  }

  function choice(line: number): CreditChoice {
    return choices[line] ?? { kind: '', value: '' };
  }

  function setChoice(line: number, next: Partial<CreditChoice>) {
    choices = { ...choices, [line]: { ...choice(line), ...next } };
  }

  function updateCharge(key: number, next: Partial<Charge>) {
    charges = charges.map((item) => (item.key === key ? { ...item, ...next } : item));
  }

  const creditLines = $derived(
    (overview?.lines ?? []).flatMap((line) => {
      const picked = choice(line.number);
      const value = Number(picked.value);
      if (!picked.kind || !(value > 0)) return [];
      const amount = picked.kind === 'return' ? returnAmount(line, value) : value;
      return [{ line, kind: picked.kind, value: picked.value, amount }];
    })
  );

  const debitLines = $derived(
    charges.flatMap((item) => {
      const amount = Number(item.quantity) * Number(item.unitPrice);
      if (!(amount > 0)) return [];
      const linked = overview?.lines.find((line) => String(line.number) === item.line);
      return [{ item, nature: linked?.nature ?? item.nature, amount }];
    })
  );

  const totals = $derived(
    estimate(
      mode === 'credit'
        ? creditLines.map((line) => ({ nature: line.line.nature, amount: line.amount }))
        : debitLines.map((line) => ({ nature: line.nature, amount: line.amount })),
      {
        withholding: overview?.withholding ?? false,
        perception: overview?.perception ?? false
      }
    )
  );

  const ready = $derived(
    reason.trim().length >= 5 &&
      (mode === 'credit'
        ? creditLines.length > 0
        : debitLines.length === charges.length &&
          charges.every((item) => item.description.trim().length >= 3))
  );

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (busy || !mode || !ready) return;
    busy = true;
    formError = null;
    try {
      if (mode === 'credit') {
        const lines: CreditLineInput[] = creditLines.map((line) =>
          line.kind === 'return'
            ? { ccf_line_number: line.line.number, kind: 'return', quantity: line.value }
            : { ccf_line_number: line.line.number, kind: 'discount', amount: line.value }
        );
        await salesInvoicesApi.creditNote(document.id, { reason: reason.trim(), lines });
        notice = 'Se está emitiendo la nota de crédito. Al quedar emitida se envía al cliente.';
      } else {
        const payload: DebitChargeInput[] = charges.map((item) => ({
          description: item.description.trim(),
          quantity: item.quantity,
          unit_price: item.unitPrice,
          ccf_line_number: item.line ? Number(item.line) : null,
          nature: item.line ? null : item.nature
        }));
        await salesInvoicesApi.debitNote(document.id, { reason: reason.trim(), charges: payload });
        notice = 'Se está emitiendo la nota de débito. Al quedar emitida se envía al cliente.';
      }
      mode = null;
      await load();
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo emitir la nota.';
    } finally {
      busy = false;
    }
  }
</script>

<section
  class="space-y-4 rounded-xl border border-border bg-surface p-4"
  aria-label="Notas de crédito y de débito"
>
  <div>
    <h2 class="font-semibold text-foreground">Notas de crédito y de débito</h2>
    <p class="text-sm text-foreground-muted">
      La nota de crédito rebaja lo documentado en este crédito fiscal (devoluciones o rebajas); la
      de débito lo aumenta (ajustes de precio, intereses u otros cargos). Son solo fiscales: no
      mueven inventario ni dinero.
    </p>
  </div>

  {#if loading}
    <div class="space-y-2" aria-busy="true">
      <div class="skeleton h-6 w-1/2 rounded-md motion-reduce:animate-none"></div>
      <div class="skeleton h-24 w-full rounded-lg motion-reduce:animate-none"></div>
    </div>
  {:else if loadError || !overview}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
      role="alert"
    >
      {loadError ?? 'No se pudieron consultar las notas.'}
      <button class="ml-2 underline" onclick={() => void load()}>Reintentar</button>
    </div>
  {:else}
    <div class="space-y-1 text-sm">
      {#if overview.credit_blocker && overview.credit_blocker === overview.debit_blocker}
        <p class="text-foreground-muted">{overview.credit_blocker}</p>
      {:else}
        {#if overview.deadline}
          <p class="text-foreground-muted">
            Se pueden emitir notas de crédito y de débito hasta el {formatDay(overview.deadline)}
            (tres meses desde el crédito fiscal).
          </p>
        {/if}
        {#if overview.credit_blocker}
          <p class="text-foreground-muted">Nota de crédito: {overview.credit_blocker}</p>
        {/if}
        {#if overview.debit_blocker}
          <p class="text-foreground-muted">Nota de débito: {overview.debit_blocker}</p>
        {/if}
      {/if}
      {#if overview.withholding || overview.perception}
        <p class="text-foreground-muted">
          Este crédito fiscal {overview.withholding ? 'retuvo' : 'percibió'} el 1 % de IVA: sus notas
          repiten la misma {overview.withholding ? 'retención' : 'percepción'} sobre lo gravado.
        </p>
      {/if}
    </div>
    {#if notice}
      <p class="text-sm text-success" aria-live="polite">{notice}</p>
    {/if}

    <div class="overflow-x-auto">
      <table class="w-full min-w-[640px] text-left text-sm">
        <caption class="sr-only">Saldo por línea del crédito fiscal</caption>
        <thead class="bg-surface-muted text-xs uppercase text-foreground-muted">
          <tr>
            <th class="px-3 py-2">Línea</th>
            <th class="px-3 py-2 text-right">Vendido</th>
            <th class="px-3 py-2 text-right">Devuelto</th>
            <th class="px-3 py-2 text-right">Neto vendido</th>
            <th class="px-3 py-2 text-right">Saldo por acreditar</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border">
          {#each overview.lines as line (line.number)}
            <tr>
              <td class="px-3 py-2 text-foreground">
                {line.number}. {line.description}
                <span class="text-xs text-foreground-muted">· {NATURE_LABELS[line.nature]}</span>
              </td>
              <td class="px-3 py-2 text-right font-mono">{formatQuantity(line.quantity)}</td>
              <td class="px-3 py-2 text-right font-mono">{formatQuantity(line.returned)}</td>
              <td class="px-3 py-2 text-right font-mono">{formatMoney(line.net)}</td>
              <td class="px-3 py-2 text-right font-mono">{formatMoney(line.remaining_amount)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if canIssue && !mode}
      <div class="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          disabled={!!overview.credit_blocker}
          onclick={() => open('credit')}>Emitir nota de crédito</Button
        >
        <Button
          variant="secondary"
          disabled={!!overview.debit_blocker}
          onclick={() => open('debit')}>Emitir nota de débito</Button
        >
      </div>
    {/if}

    {#if mode}
      <form
        class="space-y-3 rounded-lg border border-border bg-surface-muted p-4"
        onsubmit={submit}
      >
        <p class="text-sm text-foreground">
          {mode === 'credit'
            ? 'Elige qué se ajusta en cada línea: la cantidad devuelta (se acredita al precio neto con el que se vendió) o el monto que se rebaja, sin IVA.'
            : 'Agrega los cargos sin IVA. Un cargo puede ajustar una línea del crédito fiscal o ser libre (intereses, flete).'}
        </p>
        {#if formError}
          <div
            class="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
            role="alert"
          >
            {formError}
          </div>
        {/if}

        {#if mode === 'credit'}
          <ul class="space-y-3">
            {#each overview.lines.filter((line) => Number(line.remaining_amount) > 0) as line (line.number)}
              <li class="grid gap-2 sm:grid-cols-[1fr_12rem_10rem] sm:items-end">
                <p class="text-sm text-foreground">
                  {line.number}. {line.description}
                  <span class="block text-xs text-foreground-muted"
                    >Quedan {formatQuantity(line.remaining_quantity)} por devolver ·
                    {formatMoney(line.remaining_amount)} por acreditar</span
                  >
                </p>
                <label class="space-y-1 text-sm text-foreground-muted"
                  >Ajuste de la línea {line.number}
                  <select
                    class={inputClass}
                    value={choice(line.number).kind}
                    onchange={(event) =>
                      setChoice(line.number, {
                        kind: event.currentTarget.value as CreditChoice['kind'],
                        value: ''
                      })}
                  >
                    <option value="">Sin ajuste</option>
                    {#if Number(line.remaining_quantity) > 0}
                      <option value="return">Devolución</option>
                    {/if}
                    <option value="discount">Rebaja</option>
                  </select>
                </label>
                <label class="space-y-1 text-sm text-foreground-muted"
                  >{choice(line.number).kind === 'discount'
                    ? `Monto rebajado de la línea ${line.number}`
                    : `Cantidad devuelta de la línea ${line.number}`}
                  <input
                    class={inputClass}
                    type="number"
                    min="0"
                    step={choice(line.number).kind === 'discount' ? '0.01' : 'any'}
                    max={choice(line.number).kind === 'discount'
                      ? line.remaining_amount
                      : line.remaining_quantity}
                    disabled={!choice(line.number).kind}
                    value={choice(line.number).value}
                    oninput={(event) =>
                      setChoice(line.number, { value: event.currentTarget.value })}
                  />
                </label>
              </li>
            {/each}
          </ul>
        {:else}
          <ul class="space-y-3">
            {#each charges as item, index (item.key)}
              <li class="grid gap-2 rounded-md border border-border bg-surface p-3 sm:grid-cols-6">
                <label class="space-y-1 text-sm text-foreground-muted sm:col-span-2"
                  >Cargo {index + 1}: línea del crédito fiscal
                  <select
                    class={inputClass}
                    value={item.line}
                    onchange={(event) =>
                      updateCharge(item.key, { line: event.currentTarget.value })}
                  >
                    <option value="">Cargo libre</option>
                    {#each overview.lines as line (line.number)}
                      <option value={String(line.number)}>{line.number}. {line.description}</option>
                    {/each}
                  </select>
                </label>
                <label class="space-y-1 text-sm text-foreground-muted sm:col-span-4"
                  >Cargo {index + 1}: descripción
                  <input
                    class={inputClass}
                    maxlength="1000"
                    value={item.description}
                    oninput={(event) =>
                      updateCharge(item.key, { description: event.currentTarget.value })}
                  />
                </label>
                <label class="space-y-1 text-sm text-foreground-muted sm:col-span-2"
                  >Cargo {index + 1}: cantidad
                  <input
                    class={inputClass}
                    type="number"
                    min="0"
                    step="any"
                    value={item.quantity}
                    oninput={(event) =>
                      updateCharge(item.key, { quantity: event.currentTarget.value })}
                  />
                </label>
                <label class="space-y-1 text-sm text-foreground-muted sm:col-span-2"
                  >Cargo {index + 1}: precio unitario sin IVA
                  <input
                    class={inputClass}
                    type="number"
                    min="0"
                    step="any"
                    value={item.unitPrice}
                    oninput={(event) =>
                      updateCharge(item.key, { unitPrice: event.currentTarget.value })}
                  />
                </label>
                <label class="space-y-1 text-sm text-foreground-muted sm:col-span-2"
                  >Cargo {index + 1}: tipo de venta
                  <select
                    class={inputClass}
                    value={item.line
                      ? (overview.lines.find((line) => String(line.number) === item.line)?.nature ??
                        item.nature)
                      : item.nature}
                    disabled={!!item.line}
                    onchange={(event) =>
                      updateCharge(item.key, {
                        nature: event.currentTarget.value as FiscalNature
                      })}
                  >
                    {#each Object.entries(NATURE_LABELS) as [value, label] (value)}
                      <option {value}>{label}</option>
                    {/each}
                  </select>
                </label>
                {#if charges.length > 1}
                  <div class="sm:col-span-6">
                    <button
                      type="button"
                      class="text-sm text-danger hover:underline"
                      onclick={() => (charges = charges.filter((other) => other.key !== item.key))}
                      >Quitar cargo {index + 1}</button
                    >
                  </div>
                {/if}
              </li>
            {/each}
          </ul>
          <Button variant="secondary" onclick={() => (charges = [...charges, newCharge()])}
            >Agregar cargo</Button
          >
        {/if}

        <label class="block space-y-1 text-sm text-foreground-muted"
          >Motivo de la nota
          <input
            class={inputClass}
            maxlength="300"
            value={reason}
            oninput={(event) => (reason = event.currentTarget.value)}
            required
          />
        </label>

        <dl class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:max-w-sm" aria-live="polite">
          <dt class="text-foreground-muted">Subtotal</dt>
          <dd class="text-right font-mono">{formatMoney(totals.subtotal)}</dd>
          <dt class="text-foreground-muted">IVA 13 %</dt>
          <dd class="text-right font-mono">{formatMoney(totals.vat)}</dd>
          {#if overview.perception}
            <dt class="text-foreground-muted">IVA percibido 1 %</dt>
            <dd class="text-right font-mono">{formatMoney(totals.perceived)}</dd>
          {/if}
          {#if overview.withholding}
            <dt class="text-foreground-muted">IVA retenido 1 %</dt>
            <dd class="text-right font-mono">−{formatMoney(totals.withheld)}</dd>
          {/if}
          <dt class="font-medium text-foreground">Total estimado</dt>
          <dd class="text-right font-mono font-medium">{formatMoney(totals.total)}</dd>
        </dl>

        <div class="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy || !ready}
            >{busy
              ? 'Emitiendo…'
              : mode === 'credit'
                ? 'Emitir nota de crédito'
                : 'Emitir nota de débito'}</Button
          >
          <Button variant="secondary" onclick={() => (mode = null)}>Cancelar</Button>
        </div>
      </form>
    {/if}

    {#if overview.notes.length === 0}
      <div class="flex flex-col items-center gap-2 py-4 text-center">
        <span
          class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-lg text-foreground-muted"
          aria-hidden="true">∅</span
        >
        <p class="text-sm text-foreground-muted">Este crédito fiscal no tiene notas.</p>
        {#if canIssue && !mode && !overview.credit_blocker}
          <Button variant="secondary" onclick={() => open('credit')}
            >Emitir la primera nota de crédito</Button
          >
        {/if}
      </div>
    {:else}
      <ul class="divide-y divide-border text-sm">
        {#each overview.notes as note (note.document.id)}
          <li class="space-y-1 py-2">
            <div class="flex flex-wrap items-center gap-2">
              <a
                class="font-medium text-primary hover:underline"
                href={`/sales/fiscal-documents/${note.document.id}`}
                >{FISCAL_DOCUMENT_LABELS[note.document.document_type]}
                {note.document.control_number ?? '(sin número todavía)'}</a
              >
              <span
                class={`rounded-full px-2 py-0.5 text-xs ${FISCAL_STATUS_BADGES[note.document.status]}`}
                >{FISCAL_STATUS_LABELS[note.document.status]}</span
              >
              <span class="font-mono text-foreground">{formatMoney(note.document.total)}</span>
            </div>
            <p class="text-foreground-muted">
              {note.document.note_reason} ·
              {note.lines
                .map(
                  (line) =>
                    `${NOTE_LINE_KIND_LABELS[line.kind]}${line.ccf_line_number ? ` línea ${line.ccf_line_number}` : ''}: ${formatMoney(line.amount)}`
                )
                .join(' · ')}
            </p>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>
