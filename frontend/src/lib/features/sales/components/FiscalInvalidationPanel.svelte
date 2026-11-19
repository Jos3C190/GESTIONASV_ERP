<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesInvoicesApi } from '#lib/api/sales-invoices.ts';
  import {
    INVALIDATION_KIND_LABELS,
    INVALIDATION_STATUS_BADGES,
    INVALIDATION_STATUS_LABELS,
    RESPONSIBLE_DOCUMENT_LABELS,
    formatMoment,
    isNote,
    isSealed
  } from '#lib/features/sales/fiscal-labels.ts';
  import { formatDay } from '#lib/features/sales/quotation-labels.ts';
  import type { FiscalDocument, InvalidationOverview } from '#lib/types/sales-invoices.ts';

  let {
    document,
    canInvalidate,
    lockedReason = null,
    onChanged = () => {}
  }: {
    document: FiscalDocument;
    canInvalidate: boolean;
    /** Por qué no se puede anular ahora (un CCF con notas vigentes, V4c). */
    lockedReason?: string | null;
    onChanged?: () => void;
  } = $props();
  const note = $derived(isNote(document));

  const inputClass =
    'h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  let overview = $state<InvalidationOverview | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let mode = $state<'cancel' | 'correct' | null>(null);
  let reason = $state('');
  let requesterName = $state('');
  let requesterType = $state('13');
  let requesterNumber = $state('');
  let busy = $state(false);
  let formError = $state<string | null>(null);
  let notice = $state<string | null>(null);

  const pending = $derived(overview?.history.some((item) => item.status === 'pending') ?? false);
  const canAct = $derived(
    canInvalidate &&
      isSealed(document) &&
      !document.superseded_by_id &&
      !pending &&
      !lockedReason &&
      !(overview?.expired ?? false)
  );

  async function load() {
    loading = true;
    loadError = null;
    try {
      overview = await salesInvoicesApi.invalidation(document.id);
    } catch (cause) {
      loadError = cause instanceof HttpError ? cause.message : 'No se pudo consultar la anulación.';
    } finally {
      loading = false;
    }
  }
  onMount(() => void load());

  function open(next: 'cancel' | 'correct') {
    mode = next;
    formError = null;
    notice = null;
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (busy || !mode) return;
    busy = true;
    formError = null;
    const requester = {
      name: requesterName,
      document_type: requesterType,
      document_number: requesterNumber
    };
    try {
      if (mode === 'cancel') {
        await salesInvoicesApi.invalidate(document.id, { reason, requester });
        notice = 'Se pidió la anulación a Hacienda. El estado se actualiza cuando responda.';
      } else {
        await salesInvoicesApi.correct(document.id, requester);
        notice =
          'Se emite el documento de reemplazo; cuando quede sellado, este se invalidará solo.';
      }
      mode = null;
      reason = '';
      await load();
      onChanged();
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo enviar la solicitud.';
    } finally {
      busy = false;
    }
  }
</script>

<section class="space-y-3 rounded-xl border border-border bg-surface p-4" aria-label="Anulación">
  <div>
    <h2 class="font-semibold text-foreground">{note ? 'Anulación' : 'Anulación y corrección'}</h2>
    <p class="text-sm text-foreground-muted">
      {note
        ? 'Una nota sellada no se borra ni se corrige: se anula ante Hacienda y, si hace falta, se emite otra.'
        : 'Un documento sellado no se borra: se anula ante Hacienda o se corrige con otro que lo reemplaza.'}
    </p>
  </div>

  {#if document.replaces_document_id}
    <p class="text-sm text-foreground">
      Reemplaza al documento
      <a
        class="text-primary hover:underline"
        href={`/sales/fiscal-documents/${document.replaces_document_id}`}>anterior</a
      >.
    </p>
  {/if}
  {#if document.superseded_by_id && document.status === 'invalidated'}
    <p class="text-sm text-foreground">
      Se invalidó y lo reemplaza
      <a
        class="text-primary hover:underline"
        href={`/sales/fiscal-documents/${document.superseded_by_id}`}>el documento corregido</a
      >.
    </p>
  {:else if document.superseded_by_id}
    <p class="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
      Se está corrigiendo con
      <a class="underline" href={`/sales/fiscal-documents/${document.superseded_by_id}`}
        >un documento de reemplazo</a
      >. Este se invalidará cuando el reemplazo quede sellado.
    </p>
  {/if}

  {#if loading}
    <div class="skeleton h-16 rounded-lg motion-reduce:animate-none" aria-busy="true"></div>
  {:else if loadError || !overview}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
      role="alert"
    >
      {loadError ?? 'No se pudo consultar la anulación.'}
      <button class="ml-2 underline" onclick={() => void load()}>Reintentar</button>
    </div>
  {:else}
    {#if isSealed(document) && overview.deadline}
      <p class={`text-sm ${overview.expired ? 'text-danger' : 'text-foreground-muted'}`}>
        {overview.expired
          ? `El plazo para anularlo venció el ${formatDay(overview.deadline)}; Hacienda ya no lo acepta.`
          : `Se puede anular o corregir hasta el ${formatDay(overview.deadline)}${overview.estimated ? ' (fecha estimada por los feriados)' : ''}.`}
      </p>
    {/if}
    {#if notice}
      <p class="text-sm text-success" aria-live="polite">{notice}</p>
    {/if}

    {#if lockedReason && isSealed(document)}
      <p class="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
        {lockedReason}
      </p>
    {/if}
    {#if canAct && !mode}
      <div class="flex flex-wrap gap-2">
        {#if !note}
          <Button variant="secondary" onclick={() => open('correct')}>Corregir documento</Button>
        {/if}
        <Button variant="secondary" onclick={() => open('cancel')}>Anular documento</Button>
      </div>
    {/if}

    {#if mode}
      <form
        class="space-y-3 rounded-lg border border-border bg-surface-muted p-4"
        onsubmit={submit}
      >
        <p class="text-sm text-foreground">
          {mode === 'correct'
            ? 'Se emite un documento nuevo con los datos actuales del cliente y del pedido (corrígelos antes). Cuando quede sellado, este se invalida y se vinculan.'
            : 'La operación se rescinde: el documento queda sin validez y no se emite otro. El pedido no se cancela desde aquí.'}
        </p>
        {#if formError}
          <div
            class="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
            role="alert"
          >
            {formError}
          </div>
        {/if}
        {#if mode === 'cancel'}
          <label class="block space-y-1 text-sm text-foreground-muted"
            >Motivo de la anulación
            <input
              class={inputClass}
              maxlength="200"
              value={reason}
              oninput={(event) => (reason = event.currentTarget.value)}
              required
            />
          </label>
        {/if}
        <fieldset class="grid gap-3 sm:grid-cols-3">
          <legend class="mb-1 text-sm text-foreground">Quién la solicita</legend>
          <label class="space-y-1 text-sm text-foreground-muted sm:col-span-3"
            >Nombre del solicitante
            <input
              class={inputClass}
              maxlength="100"
              value={requesterName}
              oninput={(event) => (requesterName = event.currentTarget.value)}
              required
            />
          </label>
          <label class="space-y-1 text-sm text-foreground-muted"
            >Documento
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
          <label class="space-y-1 text-sm text-foreground-muted sm:col-span-2"
            >Número de documento del solicitante
            <input
              class={inputClass}
              maxlength="25"
              value={requesterNumber}
              oninput={(event) => (requesterNumber = event.currentTarget.value)}
              required
            />
          </label>
        </fieldset>
        <div class="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy}
            >{busy
              ? 'Enviando…'
              : mode === 'correct'
                ? 'Emitir reemplazo'
                : 'Anular ante Hacienda'}</Button
          >
          <Button variant="secondary" onclick={() => (mode = null)}>Cancelar</Button>
        </div>
      </form>
    {/if}

    {#if overview.history.length > 0}
      <ul class="divide-y divide-border text-sm">
        {#each overview.history as item (item.id)}
          <li class="space-y-1 py-2">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-foreground">{INVALIDATION_KIND_LABELS[item.kind]}</span>
              <span
                class={`rounded-full px-2 py-0.5 text-xs ${INVALIDATION_STATUS_BADGES[item.status]}`}
                >{INVALIDATION_STATUS_LABELS[item.status]}</span
              >
              {#if item.cancel_order}
                <span class="text-xs text-foreground-muted">· cancela el pedido</span>
              {/if}
            </div>
            <p class="text-foreground-muted">
              Solicitó {item.requester.name} · {formatMoment(item.created_at)}{item.reason
                ? ` · ${item.reason}`
                : ''}
            </p>
            {#if item.event_seal}
              <p class="break-all font-mono text-xs text-foreground">
                Sello del evento: {item.event_seal}
              </p>
            {/if}
            {#if item.error_message}
              <p class="text-danger">{item.error_message}</p>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>
