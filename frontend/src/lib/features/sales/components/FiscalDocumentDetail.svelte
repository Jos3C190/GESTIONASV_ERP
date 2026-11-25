<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesInvoicesApi } from '#lib/api/sales-invoices.ts';
  import { downloadFiscalJson, openFiscalPdf } from '#lib/features/sales/fiscal-downloads.ts';
  import {
    CONTINGENCY_TYPE_LABELS,
    FISCAL_DOCUMENT_LABELS,
    FISCAL_MODE_LABELS,
    FISCAL_STATUS_BADGES,
    FISCAL_STATUS_LABELS,
    canRetry,
    isFinal,
    isNote,
    isRemission,
    isVigent
  } from '#lib/features/sales/fiscal-labels.ts';
  import { formatDay, formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import { rentaLabel } from '#lib/features/sales/renta-labels.ts';
  import FiscalDocumentEmails from './FiscalDocumentEmails.svelte';
  import FiscalInvalidationPanel from './FiscalInvalidationPanel.svelte';
  import FiscalNotesPanel from './FiscalNotesPanel.svelte';
  import type { FiscalDocument, NotesOverview } from '#lib/types/sales-invoices.ts';

  let { id }: { id: string } = $props();
  let document = $state<FiscalDocument | null>(null);
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let vigentNotes = $state(0);
  let generation = 0;

  function noted(overview: NotesOverview) {
    vigentNotes = overview.notes.filter((note) => isVigent(note.document)).length;
  }
  onDestroy(() => generation++);

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try {
      const response = await salesInvoicesApi.get(id);
      if (current === generation) document = response;
    } catch (cause) {
      if (current === generation) {
        error =
          cause instanceof HttpError ? cause.message : 'No se pudo cargar el documento fiscal.';
      }
    } finally {
      if (current === generation) loading = false;
    }
  }
  onMount(() => void load());

  async function act(action: 'retry' | 'json' | 'pdf') {
    if (!document || busy) return;
    busy = true;
    error = null;
    try {
      if (action === 'retry') document = await salesInvoicesApi.retry(document.id);
      else if (action === 'json') await downloadFiscalJson(document);
      else await openFiscalPdf(document);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo completar la acción.';
    } finally {
      busy = false;
    }
  }
</script>

<svelte:head
  ><title
    >{document?.control_number ? `DTE ${document.control_number}` : 'Documento fiscal'} | GestionaSV</title
  ></svelte:head
>

<div class="space-y-5">
  <a class="text-sm text-primary hover:underline" href="/sales/fiscal-documents"
    >← Documentos fiscales</a
  >
  {#if error}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {/if}

  {#if loading}
    <div class="space-y-3" aria-busy="true">
      <div class="skeleton h-8 w-1/2 rounded-md"></div>
      <div class="skeleton h-40 w-full rounded-xl"></div>
    </div>
  {:else if document}
    <header class="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p class="text-xs font-semibold uppercase tracking-widest text-primary">
          {FISCAL_DOCUMENT_LABELS[document.document_type]}
        </p>
        <h1 class="mt-1 break-all font-mono text-xl font-bold text-foreground">
          {document.control_number ?? 'Sin número de control todavía'}
        </h1>
      </div>
      <span
        class={`self-start rounded-full px-3 py-1 text-sm ${FISCAL_STATUS_BADGES[document.status]}`}
        >{FISCAL_STATUS_LABELS[document.status]}</span
      >
    </header>

    {#if document.contingency_type}
      <p
        class={`rounded-lg border px-4 py-3 text-sm ${document.status === 'contingency' ? 'border-warning/30 bg-warning/10 text-warning' : 'border-border bg-surface-muted text-foreground-muted'}`}
      >
        Generado en contingencia ({CONTINGENCY_TYPE_LABELS[document.contingency_type] ??
          'Otro'}{document.contingency_reason ? `: ${document.contingency_reason}` : ''}).
        {document.status === 'contingency'
          ? 'Se transmitirá a Hacienda al cerrar la contingencia; el sello aparecerá cuando lo reciba. El cliente ya puede recibir su PDF.'
          : 'Ya se transmitió después del evento de contingencia.'}
      </p>
    {/if}
    {#if document.status === 'simulated'}
      <p
        class="rounded-lg border border-border bg-surface-muted px-4 py-3 text-sm text-foreground-muted"
      >
        Documento emitido en modo simulado: no tiene validez fiscal ni se envió a Hacienda.
      </p>
    {/if}
    {#if document.error_message}
      <div
        class={`rounded-lg border px-4 py-3 text-sm ${document.error_code === 'dte_totals_mismatch' ? 'border-warning/30 bg-warning/10 text-warning' : 'border-danger/30 bg-danger/10 text-danger'}`}
        role="alert"
      >
        <p class="font-medium">
          {document.error_code === 'dte_totals_mismatch'
            ? 'Los totales del DTE no coinciden con los del pedido'
            : document.status === 'pending'
              ? 'El último intento no terminó; se reintentará solo'
              : 'Motivo'}
        </p>
        <p class="mt-1 break-words">{document.error_message}</p>
      </div>
    {/if}

    {#if isNote(document) && document.related_document_id}
      <p class="rounded-lg border border-border bg-surface-muted px-4 py-3 text-sm text-foreground">
        Ajusta el
        <a
          class="text-primary hover:underline"
          href={`/sales/fiscal-documents/${document.related_document_id}`}>crédito fiscal</a
        >{document.note_reason ? `. Motivo: ${document.note_reason}` : ''}.
      </p>
    {/if}

    <section class="rounded-xl border border-border bg-surface">
      <dl class="grid gap-x-6 gap-y-3 p-4 text-sm sm:grid-cols-2">
        {#if document.sale_id}
          <div>
            <dt class="text-foreground-muted">Pedido</dt>
            <dd>
              <a class="font-mono text-primary hover:underline" href={`/sales/${document.sale_id}`}
                >{document.sale_code}</a
              >
            </dd>
          </div>
          <div>
            <dt class="text-foreground-muted">Cliente</dt>
            <dd class="text-foreground">{document.customer_name}</dd>
          </div>
        {:else if document.transfer_id}
          <div class="sm:col-span-2">
            <dt class="text-foreground-muted">Traslado</dt>
            <dd>
              <a
                class="font-mono text-primary hover:underline"
                href={`/transfers?transfer=${document.transfer_id}`}>{document.transfer_code}</a
              >
              <span class="text-foreground-muted">
                · ampara lo despachado; recepciones y diferencias no la cambian.</span
              >
            </dd>
          </div>
        {/if}
        <div>
          <dt class="text-foreground-muted">Total</dt>
          <dd class="font-mono text-foreground">{formatMoney(document.total)}</dd>
        </div>
        <div>
          <dt class="text-foreground-muted">Fecha de emisión</dt>
          <dd class="text-foreground">{formatDay(document.issued_at)}</dd>
        </div>
        <div>
          <dt class="text-foreground-muted">Establecimiento y punto de venta</dt>
          <dd class="font-mono text-foreground">
            {document.establishment_code} · {document.point_of_sale_code}
          </dd>
        </div>
        <div>
          <dt class="text-foreground-muted">Modo</dt>
          <dd class="text-foreground">{FISCAL_MODE_LABELS[document.mode] ?? document.mode}</dd>
        </div>
        <div class="sm:col-span-2">
          <dt class="text-foreground-muted">Código de generación</dt>
          <dd class="break-all font-mono text-xs text-foreground">
            {document.generation_code?.toUpperCase() ?? '—'}
          </dd>
        </div>
        {#if document.seal}
          <div class="sm:col-span-2">
            <dt class="text-foreground-muted">Sello de recepción</dt>
            <dd class="break-all font-mono text-xs text-foreground">{document.seal}</dd>
          </div>
        {/if}
        {#if !isRemission(document)}
          <div class="sm:col-span-2">
            <dt class="text-foreground-muted">Clasificación de renta (F-07)</dt>
            <dd class="text-foreground">
              {rentaLabel(document.renta_operation_type, document.renta_income_type)}
            </dd>
          </div>
        {/if}
        <div>
          <dt class="text-foreground-muted">Intentos de emisión</dt>
          <dd class="text-foreground">{document.attempts}</dd>
        </div>
      </dl>
    </section>

    <section class="flex flex-wrap gap-2 rounded-xl border border-border bg-surface p-4">
      {#if document.has_pdf}
        <button
          class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          disabled={busy}
          onclick={() => void act('pdf')}>Ver PDF</button
        >
      {/if}
      {#if document.has_json}
        <button
          class="rounded-md border border-border px-4 py-2 text-sm text-foreground disabled:opacity-50"
          disabled={busy}
          onclick={() => void act('json')}>Descargar JSON</button
        >
      {/if}
      {#if canRetry(document) && permissions.hasPermission('sales_invoices:issue')}
        <button
          class="rounded-md border border-border px-4 py-2 text-sm text-foreground disabled:opacity-50"
          disabled={busy}
          onclick={() => void act('retry')}>Reintentar emisión</button
        >
      {/if}
      {#if !document.has_pdf && !document.has_json}
        <p class="text-sm text-foreground-muted">
          El JSON y el PDF aparecen aquí cuando el documento termine de emitirse.
        </p>
      {/if}
    </section>

    {#key `${document.status}-${document.superseded_by_id ?? ''}`}
      {#if document.document_type === '03' && isFinal(document)}
        <FiscalNotesPanel
          {document}
          canIssue={permissions.hasPermission('sales_invoices:notes')}
          onOverview={noted}
        />
      {/if}
      <FiscalInvalidationPanel
        {document}
        canInvalidate={permissions.hasPermission('sales_invoices:invalidate')}
        lockedReason={vigentNotes > 0
          ? 'Este crédito fiscal tiene notas vigentes: anúlalas antes de anularlo o corregirlo.'
          : null}
        onChanged={() => void load()}
      />
      {#if !isRemission(document)}
        <FiscalDocumentEmails {document} />
      {/if}
    {/key}
  {/if}
</div>
