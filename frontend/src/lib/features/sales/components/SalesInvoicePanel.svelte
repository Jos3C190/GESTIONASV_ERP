<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesInvoicesApi } from '#lib/api/sales-invoices.ts';
  import { downloadFiscalJson, openFiscalPdf } from '#lib/features/sales/fiscal-downloads.ts';
  import {
    FISCAL_MODE_LABELS,
    FISCAL_STATUS_BADGES,
    FISCAL_STATUS_LABELS,
    canRetry
  } from '#lib/features/sales/fiscal-labels.ts';
  import { DOCUMENT_LABELS, formatDay, formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type { Sale } from '#lib/types/sales.ts';
  import FiscalDocumentEmails from './FiscalDocumentEmails.svelte';
  import type { FiscalDocument, InvoiceOptions } from '#lib/types/sales-invoices.ts';

  let {
    sale,
    onInvoiced = () => {},
    pollMs = 3000
  }: {
    sale: Sale;
    onInvoiced?: (document: FiscalDocument | null) => void;
    pollMs?: number;
  } = $props();

  let options = $state<InvoiceOptions | null>(null);
  let current = $state<FiscalDocument | null>(null);
  let pointOfSale = $state('');
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let timer: ReturnType<typeof setTimeout> | null = null;
  let generation = 0;

  const canIssue = $derived(permissions.hasPermission('sales_invoices:issue'));
  const label = $derived(DOCUMENT_LABELS[sale.document_type as '01' | '03'] ?? 'Documento');
  const named = $derived(sale.document_type === '03' ? 'el crédito fiscal' : 'la factura');

  function stopPolling() {
    if (timer) clearTimeout(timer);
    timer = null;
  }
  onDestroy(() => {
    generation++;
    stopPolling();
  });

  function track(next: FiscalDocument | null) {
    current = next;
    onInvoiced(next !== null && next.status !== 'failed' ? next : null);
    stopPolling();
    if (next?.status === 'pending') {
      timer = setTimeout(() => void refresh(next.id), pollMs);
    }
  }

  async function refresh(id: string) {
    const run = generation;
    try {
      const next = await salesInvoicesApi.get(id);
      if (run === generation) track(next);
    } catch {
      if (run === generation) timer = setTimeout(() => void refresh(id), pollMs * 2);
    }
  }

  async function load() {
    const run = ++generation;
    loading = true;
    error = null;
    try {
      const response = await salesInvoicesApi.options(sale.id);
      if (run !== generation) return;
      options = response;
      const [only, ...others] = response.points_of_sale;
      if (only && others.length === 0) pointOfSale = only.id;
      track(response.document);
    } catch (cause) {
      if (run === generation) {
        error = cause instanceof HttpError ? cause.message : 'No se pudo consultar la facturación.';
      }
    } finally {
      if (run === generation) loading = false;
    }
  }
  onMount(() => void load());

  async function invoice() {
    if (busy || !options) return;
    busy = true;
    error = null;
    try {
      track(await salesInvoicesApi.invoice(sale.id, pointOfSale || null));
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo facturar el pedido.';
    } finally {
      busy = false;
    }
  }

  async function retry() {
    if (busy || !current) return;
    busy = true;
    error = null;
    try {
      track(await salesInvoicesApi.retry(current.id));
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo reintentar la emisión.';
    } finally {
      busy = false;
    }
  }

  async function download(kind: 'json' | 'pdf') {
    if (!current) return;
    error = null;
    try {
      await (kind === 'json' ? downloadFiscalJson(current) : openFiscalPdf(current));
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo descargar el archivo.';
    }
  }

  const needsPoint = $derived((options?.points_of_sale.length ?? 0) > 1);
  const blocked = $derived(!options || options.blockers.length > 0 || (needsPoint && !pointOfSale));
</script>

<section class="space-y-3 rounded-xl border border-border bg-surface p-4" aria-label="Factura">
  <div class="flex flex-wrap items-center justify-between gap-2">
    <h2 class="font-semibold text-foreground">{label}</h2>
    {#if options}
      <span class="text-xs text-foreground-muted"
        >{FISCAL_MODE_LABELS[options.mode] ?? options.mode}</span
      >
    {/if}
  </div>

  {#if error}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {/if}

  {#if loading}
    <div class="space-y-2" aria-busy="true">
      <div class="skeleton h-5 w-1/3 rounded-md"></div>
      <div class="skeleton h-9 w-full rounded-md"></div>
    </div>
  {:else if current && current.status !== 'failed'}
    <div class="flex flex-wrap items-center gap-3 text-sm">
      <span class={`rounded-full px-2 py-1 text-xs ${FISCAL_STATUS_BADGES[current.status]}`}
        >{FISCAL_STATUS_LABELS[current.status]}</span
      >
      <span class="font-mono text-xs text-foreground"
        >{current.control_number ?? 'Asignando número de control…'}</span
      >
      <span class="font-mono text-foreground">{formatMoney(current.total)}</span>
      {#if current.issued_at}
        <span class="text-foreground-muted">{formatDay(current.issued_at)}</span>
      {/if}
    </div>
    {#if current.status === 'pending'}
      <p class="text-sm text-foreground-muted" aria-live="polite">
        El documento se está emitiendo. Esta sección se actualiza sola.
        {#if current.error_message}<span class="block text-warning"
            >Último intento: {current.error_message}</span
          >{/if}
      </p>
    {/if}
    {#if current.status === 'rejected' && current.error_message}
      <p class="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
        {current.error_message}
      </p>
    {/if}
    {#if current.error_code === 'dte_totals_mismatch'}
      <p class="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
        Los totales del DTE no coinciden con los del pedido: {current.error_message}
      </p>
    {/if}
    <div class="flex flex-wrap gap-2">
      {#if current.has_pdf}
        <button
          class="rounded-md border border-border px-4 py-2 text-sm text-foreground"
          onclick={() => void download('pdf')}>Ver PDF</button
        >
      {/if}
      {#if current.has_json}
        <button
          class="rounded-md border border-border px-4 py-2 text-sm text-foreground"
          onclick={() => void download('json')}>Descargar JSON</button
        >
      {/if}
      <a
        class="rounded-md border border-border px-4 py-2 text-sm text-foreground"
        href={`/sales/fiscal-documents/${current.id}`}>Ver documento</a
      >
      {#if canIssue && canRetry(current)}
        <button
          class="rounded-md border border-border px-4 py-2 text-sm text-foreground disabled:opacity-50"
          disabled={busy}
          onclick={() => void retry()}>Reintentar emisión</button
        >
      {/if}
    </div>
    {#if current.status === 'issued' || current.status === 'simulated'}
      {#key current.status}
        <FiscalDocumentEmails document={current} />
      {/key}
    {/if}
  {:else if options}
    {#if !current && options.previous_document}
      {@const previous = options.previous_document}
      <div
        class="rounded-lg border border-border bg-surface-muted px-4 py-3 text-sm text-foreground"
        role="status"
      >
        <p class="font-medium">
          {previous.status === 'invalidated'
            ? `El documento ${previous.control_number ?? ''} se invalidó.`
            : previous.status === 'rejected'
              ? 'Hacienda rechazó el documento anterior.'
              : 'El documento anterior no se emitió.'}
        </p>
        {#if previous.status === 'rejected' && previous.error_message}
          <p class="mt-1 break-words text-danger">{previous.error_message}</p>
          <p class="mt-1 text-foreground-muted">
            Corrige los datos del cliente o del pedido y vuelve a facturar: se emite un documento
            nuevo.
          </p>
        {/if}
        <a
          class="mt-1 inline-block text-primary hover:underline"
          href={`/sales/fiscal-documents/${previous.id}`}>Ver el documento anterior</a
        >
      </div>
    {/if}
    {#if current?.status === 'failed'}
      <div
        class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        role="alert"
      >
        <p class="font-medium">El último intento de emisión falló.</p>
        <p class="mt-1">{current.error_message ?? 'El servicio no dio detalle.'}</p>
        {#if canIssue}
          <button
            class="mt-2 underline disabled:opacity-50"
            disabled={busy}
            onclick={() => void retry()}>Reintentar con los mismos datos</button
          >
        {/if}
      </div>
    {/if}
    {#if options.blockers.length > 0}
      <div class="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
        <p class="font-medium">Antes de facturar:</p>
        <ul class="mt-1 list-disc space-y-1 pl-5">
          {#each options.blockers as blocker (blocker)}
            <li>{blocker}</li>
          {/each}
        </ul>
      </div>
    {:else}
      <p class="text-sm text-foreground-muted">
        Emite {named} del pedido completo por {formatMoney(sale.total)}. Se puede facturar antes,
        durante o después de entregar.
      </p>
    {/if}
    {#if canIssue}
      <div class="flex flex-col gap-2 sm:flex-row sm:items-end">
        {#if needsPoint}
          <label class="flex flex-col gap-1 text-sm text-foreground-muted"
            >Punto de venta
            <select
              class="h-10 rounded-md border border-border bg-background px-3 text-foreground"
              value={pointOfSale}
              onchange={(event) => (pointOfSale = event.currentTarget.value)}
            >
              <option value="">Elige la caja</option>
              {#each options.points_of_sale as point (point.id)}
                <option value={point.id}>{point.code} · {point.name}</option>
              {/each}
            </select>
          </label>
        {/if}
        <button
          class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          disabled={busy || blocked}
          onclick={() => void invoice()}
          >{busy ? 'Facturando…' : current ? 'Facturar de nuevo' : 'Facturar'}</button
        >
      </div>
    {/if}
  {/if}
</section>
