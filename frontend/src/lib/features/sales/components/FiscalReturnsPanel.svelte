<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesInvoicesApi } from '#lib/api/sales-invoices.ts';
  import {
    RESPONSIBLE_DOCUMENT_LABELS,
    RETURN_STATUS_BADGES,
    RETURN_STATUS_LABELS
  } from '#lib/features/sales/fiscal-labels.ts';
  import { formatQuantity, returnAmount } from '#lib/features/sales/note-calc.ts';
  import { formatDay, formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import type { FiscalDocument, FiscalReturn, ReturnsOverview } from '#lib/types/sales-invoices.ts';

  let {
    document,
    canReturn,
    onOverview = () => {}
  }: {
    document: FiscalDocument;
    canReturn: boolean;
    onOverview?: (overview: ReturnsOverview) => void;
  } = $props();

  const inputClass =
    'h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';

  let overview = $state<ReturnsOverview | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let formOpen = $state(false);
  let reason = $state('');
  let quantities = $state<Record<number, string>>({});
  let annulling = $state<FiscalReturn | null>(null);
  let requesterName = $state('');
  let requesterType = $state('13');
  let requesterNumber = $state('');
  let busy = $state(false);
  let formError = $state<string | null>(null);
  let notice = $state<string | null>(null);

  async function load(quiet = false) {
    if (!quiet) loading = true;
    loadError = null;
    try {
      overview = await salesInvoicesApi.returns(document.id);
      onOverview(overview);
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudieron consultar los retornos.';
    } finally {
      loading = false;
    }
  }
  onMount(() => void load());

  // Mientras un retorno o su anulación se transmiten, el panel se actualiza solo.
  $effect(() => {
    const waiting = overview?.returns.some(
      (item) => item.status === 'pending' || item.annul_status === 'pending'
    );
    if (!waiting) return;
    const timer = setTimeout(() => void load(true), 5000);
    return () => clearTimeout(timer);
  });

  const chosen = $derived(
    (overview?.lines ?? []).flatMap((line) => {
      const quantity = Number(quantities[line.number] ?? '');
      if (!(quantity > 0)) return [];
      return [{ line, quantity, amount: returnAmount(line, quantity) }];
    })
  );
  const estimate = $derived.by(() => {
    const taxed = chosen
      .filter((item) => item.line.nature === 'taxed')
      .reduce((sum, item) => sum + item.amount, 0);
    const subtotal = chosen.reduce((sum, item) => sum + item.amount, 0);
    const base = Math.round((taxed / 1.13) * 100) / 100;
    const withheld = overview?.withholding ? Math.round(base * 0.01 * 100) / 100 : 0;
    return {
      subtotal,
      vat: Math.round((taxed - base) * 100) / 100,
      withheld,
      total: subtotal - withheld
    };
  });
  const tooMuch = $derived(
    chosen.some((item) => item.quantity > Number(item.line.remaining_quantity))
  );
  const ready = $derived(reason.trim().length >= 5 && chosen.length > 0 && !tooMuch && !busy);

  function openForm() {
    formOpen = true;
    annulling = null;
    reason = '';
    quantities = {};
    formError = null;
    notice = null;
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (!ready) return;
    busy = true;
    formError = null;
    try {
      await salesInvoicesApi.registerReturn(document.id, {
        reason: reason.trim(),
        lines: chosen.map((item) => ({
          invoice_line_number: item.line.number,
          quantity: String(item.quantity)
        }))
      });
      formOpen = false;
      notice = 'Se registró el retorno; se está transmitiendo a Hacienda.';
      await load(true);
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo registrar el retorno.';
    } finally {
      busy = false;
    }
  }

  function openAnnul(item: FiscalReturn) {
    annulling = item;
    formOpen = false;
    requesterName = '';
    requesterType = '13';
    requesterNumber = '';
    formError = null;
    notice = null;
  }

  async function annul(event: SubmitEvent) {
    event.preventDefault();
    if (!annulling || busy) return;
    busy = true;
    formError = null;
    try {
      await salesInvoicesApi.annulReturn(annulling.id, {
        name: requesterName.trim(),
        document_type: requesterType,
        document_number: requesterNumber.trim()
      });
      annulling = null;
      notice = 'Se pidió la anulación del retorno a Hacienda.';
      await load(true);
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo anular el retorno.';
    } finally {
      busy = false;
    }
  }

  async function open(item: FiscalReturn, kind: 'pdf' | 'json') {
    formError = null;
    try {
      const blob =
        kind === 'pdf'
          ? await salesInvoicesApi.returnPdf(item.id)
          : await salesInvoicesApi.returnJson(item.id);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo abrir el archivo.';
    }
  }

  function annullable(item: FiscalReturn): boolean {
    return (
      (item.status === 'issued' || item.status === 'simulated') &&
      item.annul_status !== 'pending' &&
      item.annul_status !== 'accepted'
    );
  }
</script>

<section class="space-y-4 rounded-xl border border-border bg-surface p-4" aria-label="Retornos">
  <div>
    <h2 class="font-semibold text-foreground">Eventos de retorno</h2>
    <p class="mt-1 text-sm text-foreground-muted">
      Documentan los bienes que el cliente devuelve de esta factura: reducen la venta y el IVA
      declarado. Se registran por cantidad, al precio neto con el que se vendió (IVA incluido), y no
      mueven inventario.
    </p>
  </div>

  {#if loading}
    <div class="space-y-2" aria-busy="true">
      <div class="skeleton h-5 w-1/2 rounded"></div>
      <div class="skeleton h-24 w-full rounded"></div>
    </div>
  {:else if loadError}
    <div
      class="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
      role="alert"
    >
      {loadError}
      <button class="ml-2 underline" onclick={() => void load()}>Reintentar</button>
    </div>
  {:else if overview}
    {#if overview.blocker}
      <p class="text-sm text-foreground-muted">{overview.blocker}</p>
    {:else if overview.deadline}
      <p class="text-sm text-foreground-muted">
        Se pueden registrar retornos hasta el {formatDay(overview.deadline)}.
      </p>
    {/if}
    {#if notice}
      <p class="text-sm text-success" aria-live="polite">{notice}</p>
    {/if}

    <div class="overflow-x-auto">
      <table class="w-full min-w-[560px] text-left text-sm">
        <caption class="sr-only">Saldo por línea de la factura</caption>
        <thead class="bg-surface-muted text-xs uppercase text-foreground-muted">
          <tr>
            <th class="px-3 py-2">Línea</th>
            <th class="px-3 py-2 text-right">Vendido</th>
            <th class="px-3 py-2 text-right">Devuelto</th>
            <th class="px-3 py-2 text-right">Neto vendido</th>
            <th class="px-3 py-2 text-right">Saldo</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border">
          {#each overview.lines as line (line.number)}
            <tr>
              <td class="px-3 py-2 text-foreground">{line.number}. {line.description}</td>
              <td class="px-3 py-2 text-right font-mono">{formatQuantity(line.quantity)}</td>
              <td class="px-3 py-2 text-right font-mono">{formatQuantity(line.returned)}</td>
              <td class="px-3 py-2 text-right font-mono">{formatMoney(line.net)}</td>
              <td class="px-3 py-2 text-right font-mono">{formatMoney(line.remaining_amount)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if canReturn && !formOpen && !annulling}
      <Button variant="secondary" disabled={!!overview.blocker} onclick={openForm}
        >Registrar retorno</Button
      >
    {/if}

    {#if formError}
      <div
        class="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
        role="alert"
      >
        {formError}
      </div>
    {/if}

    {#if formOpen}
      <form
        class="space-y-3 rounded-lg border border-border bg-surface-muted p-4"
        onsubmit={submit}
      >
        <p class="text-sm text-foreground">
          Indica cuántas unidades devolvió el cliente de cada línea. El retorno no es un descuento:
          si cambia el producto, emite una factura nueva.
        </p>
        <ul class="space-y-3">
          {#each overview.lines.filter((line) => Number(line.remaining_quantity) > 0) as line (line.number)}
            <li class="grid gap-2 sm:grid-cols-[1fr_12rem] sm:items-end">
              <p class="text-sm text-foreground">
                {line.number}. {line.description}
                <span class="block text-xs text-foreground-muted"
                  >Quedan {formatQuantity(line.remaining_quantity)} por devolver ·
                  {formatMoney(line.remaining_amount)}</span
                >
              </p>
              <label class="space-y-1 text-sm text-foreground-muted"
                >Cantidad devuelta
                <input
                  aria-label={`Cantidad devuelta de la línea ${line.number}`}
                  class={inputClass}
                  type="number"
                  min="0"
                  step="any"
                  max={line.remaining_quantity}
                  value={quantities[line.number] ?? ''}
                  oninput={(event) =>
                    (quantities = { ...quantities, [line.number]: event.currentTarget.value })}
                />
              </label>
            </li>
          {/each}
        </ul>
        <label class="block space-y-1 text-sm text-foreground-muted"
          >Motivo del retorno
          <input
            class={inputClass}
            maxlength="300"
            value={reason}
            oninput={(event) => (reason = event.currentTarget.value)}
          />
        </label>
        <dl class="grid gap-1 text-sm sm:max-w-xs">
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Devuelto (IVA incluido)</dt>
            <dd class="font-mono">{formatMoney(estimate.subtotal)}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">IVA contenido</dt>
            <dd class="font-mono">{formatMoney(estimate.vat)}</dd>
          </div>
          {#if estimate.withheld > 0}
            <div class="flex justify-between">
              <dt class="text-foreground-muted">IVA retenido</dt>
              <dd class="font-mono">−{formatMoney(estimate.withheld)}</dd>
            </div>
          {/if}
          <div class="flex justify-between font-semibold">
            <dt>Total del retorno</dt>
            <dd class="font-mono">{formatMoney(estimate.total)}</dd>
          </div>
        </dl>
        {#if tooMuch}
          <p class="text-sm text-danger">Una cantidad pasa de lo que queda por devolver.</p>
        {/if}
        <div class="flex flex-wrap gap-2">
          <Button type="submit" disabled={!ready}
            >{busy ? 'Registrando…' : 'Registrar ante Hacienda'}</Button
          >
          <Button variant="secondary" onclick={() => (formOpen = false)}>Cancelar</Button>
        </div>
      </form>
    {/if}

    {#if annulling}
      <form class="space-y-3 rounded-lg border border-border bg-surface-muted p-4" onsubmit={annul}>
        <p class="text-sm text-foreground">
          Anular el retorno de {formatMoney(annulling.total)} devuelve su saldo a la factura. Indica quién
          lo solicita.
        </p>
        <div class="grid gap-3 sm:grid-cols-3">
          <label class="space-y-1 text-sm text-foreground-muted"
            >Nombre del solicitante
            <input
              class={inputClass}
              maxlength="100"
              value={requesterName}
              oninput={(event) => (requesterName = event.currentTarget.value)}
            />
          </label>
          <label class="space-y-1 text-sm text-foreground-muted"
            >Documento del solicitante
            <select
              class={inputClass}
              value={requesterType}
              onchange={(event) => (requesterType = event.currentTarget.value)}
            >
              {#each Object.entries(RESPONSIBLE_DOCUMENT_LABELS) as [value, label] (value)}
                <option {value}>{label}</option>
              {/each}
            </select>
          </label>
          <label class="space-y-1 text-sm text-foreground-muted"
            >Número de documento del solicitante
            <input
              class={inputClass}
              maxlength="25"
              value={requesterNumber}
              oninput={(event) => (requesterNumber = event.currentTarget.value)}
            />
          </label>
        </div>
        <div class="flex flex-wrap gap-2">
          <Button
            type="submit"
            disabled={busy || requesterName.trim().length < 3 || !requesterNumber.trim()}
            >{busy ? 'Anulando…' : 'Anular ante Hacienda'}</Button
          >
          <Button variant="secondary" onclick={() => (annulling = null)}>Cancelar</Button>
        </div>
      </form>
    {/if}

    {#if overview.returns.length === 0}
      <p class="text-sm text-foreground-muted">Esta factura no tiene retornos.</p>
    {:else}
      <ul class="divide-y divide-border rounded-lg border border-border">
        {#each overview.returns as item (item.id)}
          <li class="space-y-2 p-3 text-sm">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="font-medium text-foreground">
                {formatMoney(item.total)}
                <span class="font-normal text-foreground-muted">
                  · {item.issued_at ? formatDay(item.issued_at) : 'sin sello'} · {item.reason}</span
                >
              </p>
              <span class={`rounded-full px-2 py-1 text-xs ${RETURN_STATUS_BADGES[item.status]}`}
                >{RETURN_STATUS_LABELS[item.status]}</span
              >
            </div>
            <p class="text-xs text-foreground-muted">
              {item.lines
                .map((line) => `${formatQuantity(line.quantity)} × ${line.description}`)
                .join(' · ')}
            </p>
            {#if item.error_message}
              <p class="text-xs text-danger">{item.error_message}</p>
            {/if}
            {#if item.annul_status === 'pending'}
              <p class="text-xs text-warning">Anulación en curso ante Hacienda.</p>
            {:else if item.annul_status === 'rejected' || item.annul_status === 'failed'}
              <p class="text-xs text-danger">
                No se pudo anular: {item.annul_error_message ?? 'sin detalle'}
              </p>
            {/if}
            <div class="flex flex-wrap gap-2">
              {#if item.has_json}
                <Button size="sm" variant="secondary" onclick={() => void open(item, 'pdf')}
                  >Ver PDF</Button
                >
                <Button size="sm" variant="secondary" onclick={() => void open(item, 'json')}
                  >Descargar JSON</Button
                >
              {/if}
              {#if canReturn && annullable(item) && !annulling && !formOpen}
                <Button size="sm" variant="secondary" onclick={() => openAnnul(item)}
                  >Anular retorno</Button
                >
              {/if}
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>
