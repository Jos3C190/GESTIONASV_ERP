<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesInvoicesApi } from '#lib/api/sales-invoices.ts';
  import {
    EMAIL_STATUS_BADGES,
    EMAIL_STATUS_LABELS,
    splitRecipients
  } from '#lib/features/sales/fiscal-labels.ts';
  import { formatDay } from '#lib/features/sales/quotation-labels.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type { FiscalDocument, FiscalEmailHistory } from '#lib/types/sales-invoices.ts';

  let { document: fiscal, pollMs = 3000 }: { document: FiscalDocument; pollMs?: number } = $props();

  let history = $state<FiscalEmailHistory | null>(null);
  let recipients = $state('');
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let timer: ReturnType<typeof setTimeout> | null = null;
  let generation = 0;

  const canSend = $derived(permissions.hasPermission('sales_invoices:issue'));
  const sendable = $derived(fiscal.status === 'issued' || fiscal.status === 'simulated');

  function stopPolling() {
    if (timer) clearTimeout(timer);
    timer = null;
  }
  onDestroy(() => {
    generation++;
    stopPolling();
  });

  async function load(initial = false) {
    const run = ++generation;
    if (initial) loading = true;
    try {
      const response = await salesInvoicesApi.emails(fiscal.id);
      if (run !== generation) return;
      history = response;
      if (initial && !recipients) recipients = response.customer_email ?? '';
      stopPolling();
      if (response.items.some((item) => item.status === 'pending')) {
        timer = setTimeout(() => void load(), pollMs);
      }
    } catch (cause) {
      if (run === generation) {
        error = cause instanceof HttpError ? cause.message : 'No se pudieron cargar los envíos.';
      }
    } finally {
      if (run === generation) loading = false;
    }
  }
  onMount(() => void load(true));

  async function send() {
    if (busy) return;
    const list = splitRecipients(recipients);
    if (list.length === 0) {
      error = 'Escribe al menos un correo.';
      return;
    }
    busy = true;
    error = null;
    notice = null;
    try {
      const email = await salesInvoicesApi.sendEmail(fiscal.id, list);
      notice = `Se enviará a ${email.recipients.join(', ')}.`;
      await load();
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo enviar el correo.';
    } finally {
      busy = false;
    }
  }
</script>

<section class="space-y-3 rounded-xl border border-border bg-surface p-4" aria-label="Correo">
  <h2 class="font-semibold text-foreground">Envío por correo</h2>

  {#if error}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {/if}
  {#if notice}
    <p class="text-sm text-success" aria-live="polite">{notice}</p>
  {/if}

  {#if loading}
    <div class="space-y-2" aria-busy="true">
      <div class="skeleton h-5 w-1/2 rounded-md"></div>
      <div class="skeleton h-9 w-full rounded-md"></div>
    </div>
  {:else if history}
    {#if !history.enabled}
      <p class="text-sm text-foreground-muted">
        La empresa no tiene configurado su correo saliente (Configuración fiscal → Correo).
      </p>
    {:else if canSend && sendable}
      <form
        class="flex flex-col gap-2 sm:flex-row sm:items-end"
        onsubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <label class="flex min-w-0 flex-1 flex-col gap-1 text-sm text-foreground-muted"
          >Enviar a
          <input
            class="h-10 rounded-md border border-border bg-background px-3 text-foreground"
            type="text"
            inputmode="email"
            placeholder="cliente@empresa.com, contabilidad@empresa.com"
            maxlength="600"
            value={recipients}
            oninput={(event) => (recipients = event.currentTarget.value)}
          />
        </label>
        <button
          class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          disabled={busy}>{busy ? 'Enviando…' : 'Enviar por correo'}</button
        >
      </form>
      <p class="text-xs text-foreground-muted">
        Hasta 5 correos, separados por comas. Se adjuntan el PDF y el JSON.
      </p>
    {:else if !sendable}
      <p class="text-sm text-foreground-muted">
        {fiscal.status === 'invalidated'
          ? 'Un documento invalidado ya no se envía; el historial muestra el aviso de anulación.'
          : 'El documento se podrá enviar cuando termine de emitirse.'}
      </p>
    {/if}

    {#if history.items.length === 0}
      <p class="text-sm text-foreground-muted">Todavía no se ha enviado por correo.</p>
    {:else}
      <ul class="divide-y divide-border text-sm">
        {#each history.items as item (item.id)}
          <li class="flex flex-col gap-1 py-2 sm:flex-row sm:items-center sm:justify-between">
            <div class="min-w-0">
              <p class="break-all text-foreground">{item.recipients.join(', ')}</p>
              <p class="text-xs text-foreground-muted">
                {item.invalidation_id
                  ? 'Aviso de anulación'
                  : item.origin === 'auto'
                    ? 'Automático al emitirse'
                    : `Enviado por ${item.requested_by_name ?? '—'}`} · {formatDay(
                  item.sent_at ?? item.created_at
                )}
              </p>
              {#if item.status === 'failed' && item.error_message}
                <p class="text-xs text-danger">{item.error_message}</p>
              {/if}
            </div>
            <span
              class={`self-start rounded-full px-2 py-1 text-xs sm:self-center ${EMAIL_STATUS_BADGES[item.status]}`}
              >{EMAIL_STATUS_LABELS[item.status]}</span
            >
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>
