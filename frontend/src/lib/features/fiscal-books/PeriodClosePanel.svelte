<script lang="ts">
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { fiscalBooksApi } from '#lib/api/fiscal-books.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type { PeriodStatus } from '#lib/types/fiscal-books.ts';

  /** Cierre del mes (V8b2): bloquea los movimientos con fecha de un mes ya declarado. */
  let { period }: { period: string } = $props();

  const canClose = $derived(permissions.hasPermission('fiscal_periods:manage'));
  const inputClass =
    'h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  let status = $state<PeriodStatus | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let confirming = $state(false);
  let reopening = $state(false);
  let reason = $state('');
  let busy = $state(false);
  let notice = $state<string | null>(null);
  let generation = 0;

  function moment(value: string): string {
    return new Intl.DateTimeFormat('es-SV', {
      dateStyle: 'short',
      timeStyle: 'short',
      timeZone: 'America/El_Salvador'
    }).format(new Date(value));
  }

  async function load(key: string) {
    const current = ++generation;
    loading = true;
    loadError = null;
    try {
      const found = await fiscalBooksApi.periodStatus(key);
      if (current === generation) status = found;
    } catch (cause) {
      if (current === generation) {
        status = null;
        loadError =
          cause instanceof HttpError ? cause.message : 'No se pudo consultar el cierre del mes.';
      }
    } finally {
      if (current === generation) loading = false;
    }
  }

  $effect(() => {
    confirming = false;
    reopening = false;
    notice = null;
    actionError = null;
    void load(period);
  });

  async function close() {
    busy = true;
    actionError = null;
    try {
      status = await fiscalBooksApi.closePeriod(period);
      confirming = false;
      notice = `Se cerró ${status.label}.`;
    } catch (cause) {
      actionError = cause instanceof HttpError ? cause.message : 'No se pudo cerrar el período.';
    } finally {
      busy = false;
    }
  }

  async function reopen() {
    busy = true;
    actionError = null;
    try {
      status = await fiscalBooksApi.reopenPeriod(period, reason.trim());
      reopening = false;
      reason = '';
      notice = `Se reabrió ${status.label}.`;
    } catch (cause) {
      actionError = cause instanceof HttpError ? cause.message : 'No se pudo reabrir el período.';
    } finally {
      busy = false;
    }
  }
</script>

<section
  class="space-y-3 rounded-xl border border-border bg-surface p-4 text-sm"
  aria-label="Cierre del período"
>
  {#if loading}
    <div class="skeleton h-10 rounded-md" aria-hidden="true"></div>
  {:else if loadError}
    <div class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-danger" role="alert">
      {loadError}
    </div>
  {:else if status}
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        {#if status.closed}
          <p class="font-medium text-foreground">
            <span class="rounded-full bg-success/10 px-2 py-0.5 text-xs text-success">Cerrado</span>
            el {moment(status.closed.closed_at)}{status.closed.closed_by
              ? ` por ${status.closed.closed_by}`
              : ''}
          </p>
          <p class="mt-1 text-foreground-muted">
            Los cobros, reintegros, comprobantes de retención, documentos de proveedor e
            invalidaciones con fecha de este mes quedan bloqueados.
          </p>
        {:else}
          <p class="font-medium text-foreground">
            <span class="rounded-full bg-surface-muted px-2 py-0.5 text-xs text-foreground-muted"
              >Abierto</span
            >
            Cierra el mes cuando ya lo declaraste: así nadie registra movimientos con su fecha.
          </p>
        {/if}
      </div>
      {#if canClose && status.closed && !reopening}
        <Button variant="ghost" size="sm" onclick={() => (reopening = true)}>Reabrir período</Button
        >
      {:else if canClose && !status.closed && !confirming}
        <Button
          variant="secondary"
          size="sm"
          disabled={status.blockers.length > 0}
          onclick={() => (confirming = true)}>Cerrar período</Button
        >
      {/if}
    </div>
    {#if notice}
      <p class="text-success" role="status">{notice}</p>
    {/if}
    {#if actionError}
      <div class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-danger" role="alert">
        {actionError}
      </div>
    {/if}
    {#if !status.closed && status.blockers.length}
      <ul class="space-y-1 text-foreground-muted" aria-label="Impide cerrar el período">
        {#each status.blockers as blocker (blocker)}
          <li class="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-foreground">
            {blocker}
          </li>
        {/each}
      </ul>
    {/if}
    {#if confirming}
      <div class="flex flex-wrap items-center gap-2 rounded-lg border border-border p-3">
        <span class="flex-1 text-foreground"
          >¿Cerrar {status.label}? Se puede reabrir con motivo.</span
        >
        <Button variant="danger" size="sm" disabled={busy} onclick={close}>Confirmar cierre</Button>
        <Button variant="ghost" size="sm" onclick={() => (confirming = false)}>Cancelar</Button>
      </div>
    {/if}
    {#if reopening}
      <div class="flex flex-wrap items-end gap-2">
        <label class="flex-1 space-y-1 text-foreground-muted"
          >Motivo de la reapertura
          <input class={inputClass} maxlength="500" bind:value={reason} />
        </label>
        <Button
          variant="danger"
          size="sm"
          disabled={busy || reason.trim().length < 10}
          onclick={reopen}>Reabrir</Button
        >
        <Button variant="ghost" size="sm" onclick={() => (reopening = false)}>Cancelar</Button>
      </div>
    {/if}
    {#if status.history.some((item) => item.status === 'reopened')}
      <details class="text-xs text-foreground-muted">
        <summary class="cursor-pointer">Historial de cierres</summary>
        <ul class="mt-2 space-y-1">
          {#each status.history as item (item.id)}
            <li>
              Cerrado el {moment(item.closed_at)}{item.closed_by
                ? ` por ${item.closed_by}`
                : ''}{#if item.reopened_at}
                · reabierto el {moment(item.reopened_at)}{item.reopened_by
                  ? ` por ${item.reopened_by}`
                  : ''}: {item.reopen_reason}{/if}
            </li>
          {/each}
        </ul>
      </details>
    {/if}
  {/if}
</section>
