<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesReceivablesApi } from '#lib/api/sales-receivables.ts';
  import { todayLocal } from '#lib/features/sales-receivables/labels.ts';
  import { formatDay, formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import type { CreditStatus } from '#lib/types/sales-receivables.ts';

  let {
    customerId,
    canCollect,
    canControlCredit
  }: { customerId: string; canCollect: boolean; canControlCredit: boolean } = $props();

  const inputClass =
    'h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  let status = $state<CreditStatus | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let busy = $state(false);
  let note = $state('');
  let nextAction = $state('');
  let blocking = $state(false);
  let blockReason = $state('');
  let sending = $state(false);
  let sendTo = $state('');

  async function load() {
    loading = true;
    loadError = null;
    try {
      status = await salesReceivablesApi.credit(customerId);
      sendTo = status.customer.email ?? '';
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudo cargar la situación de crédito.';
    } finally {
      loading = false;
    }
  }

  onMount(load);

  async function act(work: () => Promise<CreditStatus | null>, message: string) {
    busy = true;
    actionError = null;
    notice = null;
    try {
      const next = await work();
      if (next) status = next;
      notice = message;
    } catch (cause) {
      actionError = cause instanceof HttpError ? cause.message : 'No se pudo completar la acción.';
    } finally {
      busy = false;
    }
  }

  async function addNote() {
    await act(async () => {
      const next = await salesReceivablesApi.addNote(customerId, note.trim(), nextAction || null);
      note = '';
      nextAction = '';
      return next;
    }, 'Se guardó la nota de cobro.');
  }

  async function block() {
    await act(async () => {
      const next = await salesReceivablesApi.block(customerId, blockReason.trim());
      blocking = false;
      blockReason = '';
      return next;
    }, 'Se bloqueó el crédito del cliente: sus pedidos a crédito pedirán autorización.');
  }

  async function openStatement() {
    actionError = null;
    try {
      const url = URL.createObjectURL(await salesReceivablesApi.statementPdf(customerId));
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (cause) {
      actionError =
        cause instanceof HttpError ? cause.message : 'No se pudo abrir el estado de cuenta.';
    }
  }

  async function send() {
    busy = true;
    actionError = null;
    notice = null;
    try {
      const result = await salesReceivablesApi.sendStatement(customerId, sendTo.trim() || null);
      sending = false;
      notice = `Se envió el estado de cuenta a ${result.sent_to}.`;
    } catch (cause) {
      actionError =
        cause instanceof HttpError ? cause.message : 'No se pudo enviar el estado de cuenta.';
    } finally {
      busy = false;
    }
  }
</script>

{#if loading}
  <div class="skeleton h-40 rounded-xl" aria-hidden="true"></div>
{:else if loadError}
  <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    {loadError}
  </div>
{:else if status}
  <section
    class="space-y-4 rounded-xl border border-border bg-surface p-4"
    aria-label="Crédito y cobranza"
  >
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="font-semibold text-foreground">Crédito y cobranza</h2>
        {#if status.customer.credit_blocked}
          <p class="mt-1 text-sm text-danger">
            Crédito bloqueado{status.customer.credit_blocked_at
              ? ` desde el ${formatDay(status.customer.credit_blocked_at)}`
              : ''}: {status.customer.credit_block_reason}
          </p>
        {:else}
          <p class="mt-1 text-sm text-foreground-muted">
            Los pedidos a crédito piden autorización si pasan el cupo, si hay saldos vencidos con
            más de {status.grace_days} días o si el crédito está bloqueado.
          </p>
        {/if}
      </div>
      <div class="flex flex-wrap gap-2">
        <Button variant="ghost" size="sm" onclick={openStatement}>Estado de cuenta (PDF)</Button>
        {#if canCollect}
          <Button variant="secondary" size="sm" onclick={() => (sending = !sending)}
            >Enviar por correo</Button
          >
        {/if}
        {#if canControlCredit}
          {#if status.customer.credit_blocked}
            <Button
              variant="secondary"
              size="sm"
              disabled={busy}
              onclick={() =>
                act(
                  () => salesReceivablesApi.unblock(customerId),
                  'Se desbloqueó el crédito del cliente.'
                )}>Desbloquear crédito</Button
            >
          {:else}
            <Button variant="danger" size="sm" onclick={() => (blocking = !blocking)}
              >Bloquear crédito</Button
            >
          {/if}
        {/if}
      </div>
    </div>

    {#if notice}
      <p class="text-sm text-success" role="status">{notice}</p>
    {/if}
    {#if actionError}
      <div
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {actionError}
      </div>
    {/if}

    <dl class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
      <div>
        <dt class="text-foreground-muted">Límite</dt>
        <dd class="tabular-nums text-foreground">
          {status.credit_limit ? formatMoney(status.credit_limit) : 'Sin límite'}
        </dd>
      </div>
      <div>
        <dt class="text-foreground-muted">Pedidos sin facturar</dt>
        <dd class="tabular-nums text-foreground">{formatMoney(status.pending_orders)}</dd>
      </div>
      <div>
        <dt class="text-foreground-muted">Disponible</dt>
        <dd
          class="font-semibold tabular-nums {status.available !== null &&
          Number(status.available) < 0
            ? 'text-danger'
            : 'text-foreground'}"
        >
          {status.available === null ? '—' : formatMoney(status.available)}
        </dd>
      </div>
      <div>
        <dt class="text-foreground-muted">Mora</dt>
        <dd
          class="tabular-nums {Number(status.overdue_beyond_grace) > 0
            ? 'text-danger'
            : 'text-foreground'}"
        >
          {formatMoney(status.overdue_beyond_grace)}
        </dd>
      </div>
    </dl>

    {#if blocking}
      <div class="flex flex-wrap items-end gap-2">
        <label class="flex-1 space-y-1 text-sm text-foreground-muted"
          >Motivo del bloqueo
          <input class={inputClass} maxlength="300" bind:value={blockReason} />
        </label>
        <Button variant="danger" disabled={busy || blockReason.trim().length < 5} onclick={block}
          >Bloquear</Button
        >
      </div>
    {/if}
    {#if sending}
      <div class="flex flex-wrap items-end gap-2">
        <label class="flex-1 space-y-1 text-sm text-foreground-muted"
          >Correo del cliente
          <input class={inputClass} type="email" maxlength="320" bind:value={sendTo} />
        </label>
        <Button disabled={busy || !sendTo.includes('@')} onclick={send}>Enviar</Button>
      </div>
    {/if}

    <div class="space-y-2">
      <h3 class="text-sm font-medium text-foreground">Notas de seguimiento</h3>
      {#if canCollect}
        <div class="grid gap-2 sm:grid-cols-[1fr_11rem_auto]">
          <input
            class={inputClass}
            maxlength="1000"
            placeholder="Qué se habló con el cliente"
            aria-label="Nota de cobro"
            bind:value={note}
          />
          <input
            class={inputClass}
            type="date"
            min={todayLocal()}
            aria-label="Próxima acción"
            bind:value={nextAction}
          />
          <Button disabled={busy || note.trim().length < 5} onclick={addNote}>Agregar nota</Button>
        </div>
      {/if}
      {#if status.notes.length === 0}
        <p class="text-sm text-foreground-muted">Sin notas de cobro.</p>
      {:else}
        <ul class="divide-y divide-border text-sm">
          {#each status.notes as item (item.id)}
            <li class="py-2">
              <p class="text-foreground">{item.note}</p>
              <p class="text-xs text-foreground-muted">
                {item.created_by} · {formatDay(item.created_at)}{item.next_action_on
                  ? ` · próxima acción ${formatDay(item.next_action_on)}`
                  : ''}
              </p>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  </section>
{/if}
