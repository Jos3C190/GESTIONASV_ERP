<script lang="ts">
  import { tick } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Callout from '$lib/components/ui/Callout.svelte';
  import type { InventoryTransfer } from '$lib/features/inventory/transfer-documents';

  interface Props {
    transfer: InventoryTransfer;
    /** Can prepare, send and withdraw (inventory:move). */
    canMove: boolean;
    /** Can approve or reject (inventory:transfer_approve). */
    canApprove: boolean;
    currentUserId: string | null;
    /** The server lets a superuser decide on their own transfers. */
    isSuperuser?: boolean;
    /** False when the company turned this route off: it can only be rejected, withdrawn or cancelled. */
    routeEnabled?: boolean;
    busy?: boolean;
    formatDate: (value: string | null | undefined) => string;
    onSubmit: () => void;
    onWithdraw: () => void;
    onApprove: () => void;
    onReject: (reason: string) => void;
  }

  const MIN_REASON = 5;
  const MAX_REASON = 1000;

  let {
    transfer,
    canMove,
    canApprove,
    currentUserId,
    isSuperuser = false,
    routeEnabled = true,
    busy = false,
    formatDate,
    onSubmit,
    onWithdraw,
    onApprove,
    onReject
  }: Props = $props();

  let rejecting = $state(false);
  let reason = $state('');
  let reasonError = $state<string | null>(null);
  let reasonField = $state<HTMLTextAreaElement | null>(null);

  const isAuthor = $derived(
    currentUserId != null &&
      (transfer.created_by_id === currentUserId || transfer.submitted_by_id === currentUserId)
  );
  const canDecide = $derived(canApprove && (!isAuthor || isSuperuser));
  const originName = $derived(transfer.origin_branch_name ?? transfer.origin_warehouse_name);

  async function openRejection() {
    rejecting = true;
    await tick();
    reasonField?.focus();
  }

  async function closeRejection() {
    rejecting = false;
    reason = '';
    reasonError = null;
    await tick();
    document.getElementById('transfer-reject-open')?.focus();
  }

  function confirmRejection(event: SubmitEvent) {
    event.preventDefault();
    const text = reason.trim();
    if (text.length < MIN_REASON) {
      reasonError = `Indica el motivo del rechazo (mínimo ${MIN_REASON} caracteres).`;
      reasonField?.focus();
      return;
    }
    reasonError = null;
    onReject(text);
  }
</script>

<section class="space-y-3" aria-label="Aprobación del traslado">
  {#if transfer.status === 'preparation' && transfer.requires_approval}
    {#if transfer.rejection_reason}
      <Callout variant="danger" dismissible={false} class="mb-0">
        <p>
          Rechazado por {transfer.rejected_by_name ?? 'un aprobador'} el {formatDate(
            transfer.rejected_at
          )}: {transfer.rejection_reason}. Corrige la preparación y vuelve a enviarla.
        </p>
      </Callout>
    {/if}
    <Callout variant="info" dismissible={false} class="mb-0">
      <p>Este traslado sale de {originName} y necesita aprobación antes de despacharse.</p>
    </Callout>
    {#if !routeEnabled}
      <Callout variant="warning" dismissible={false} class="mb-0">
        <p>
          Esta ruta está desactivada en las reglas de traslados, así que no se puede enviar a
          aprobación. Todavía puedes cancelar el traslado.
        </p>
      </Callout>
    {/if}
    <div class="flex flex-wrap items-center gap-2">
      <Button disabled={!canMove || busy || !routeEnabled} onclick={onSubmit}>
        Enviar a aprobación
      </Button>
      {#if !canMove}
        <p class="text-xs text-foreground-muted">
          Necesitas el permiso de movimiento de inventario para enviarlo.
        </p>
      {/if}
    </div>
  {:else if transfer.status === 'pending_approval'}
    <Callout variant="warning" dismissible={false} class="mb-0">
      <p>
        Enviado por {transfer.submitted_by_name ?? 'un usuario'} el {formatDate(
          transfer.submitted_at
        )}. Esperando aprobación.
      </p>
    </Callout>
    {#if !routeEnabled}
      <Callout variant="warning" dismissible={false} class="mb-0">
        <p>
          Esta ruta está desactivada en las reglas de traslados, así que no se puede aprobar. Aún
          puedes rechazarlo, retirarlo o cancelarlo.
        </p>
      </Callout>
    {/if}
    {#if canApprove && !canDecide}
      <p class="text-sm text-foreground-muted" role="note">
        No puedes aprobar un traslado que tú preparaste o enviaste.
      </p>
    {/if}
    {#if canDecide}
      <div class="flex flex-wrap items-center gap-2">
        <Button disabled={busy || !routeEnabled} onclick={onApprove}>Aprobar traslado</Button>
        <Button
          id="transfer-reject-open"
          variant="secondary"
          disabled={busy || rejecting}
          onclick={() => void openRejection()}>Rechazar</Button
        >
      </div>
      {#if rejecting}
        <form
          class="space-y-3 rounded-xl border border-border bg-surface p-4"
          onsubmit={confirmRejection}
          novalidate
        >
          <label class="block space-y-1 text-sm font-medium text-foreground" for="reject-reason">
            Motivo del rechazo
          </label>
          <textarea
            id="reject-reason"
            class="field-control min-h-20"
            maxlength={MAX_REASON}
            aria-invalid={reasonError ? 'true' : undefined}
            aria-describedby="reject-reason-help{reasonError ? ' reject-reason-error' : ''}"
            bind:this={reasonField}
            bind:value={reason}
            oninput={() => (reasonError = null)}
            onkeydown={(event) => {
              if (event.key === 'Escape') {
                event.stopPropagation();
                void closeRejection();
              }
            }}
          ></textarea>
          <p id="reject-reason-help" class="text-xs text-foreground-muted">
            Mínimo {MIN_REASON} caracteres. Lo verá quien preparó el traslado para corregirlo.
          </p>
          {#if reasonError}
            <p id="reject-reason-error" class="text-xs text-danger" role="alert">{reasonError}</p>
          {/if}
          <div class="flex flex-wrap justify-end gap-2">
            <Button variant="secondary" disabled={busy} onclick={() => void closeRejection()}
              >Volver</Button
            >
            <Button type="submit" variant="danger" disabled={busy}>Confirmar rechazo</Button>
          </div>
        </form>
      {/if}
    {/if}
    {#if canMove && !canDecide}
      <div class="flex flex-wrap items-center gap-2">
        <Button variant="secondary" disabled={busy} onclick={onWithdraw}>Retirar solicitud</Button>
        <p class="text-xs text-foreground-muted">
          Vuelve a preparación para que puedas corregirlo y enviarlo de nuevo.
        </p>
      </div>
    {/if}
  {:else if transfer.status === 'approved'}
    <Callout variant="success" dismissible={false} class="mb-0">
      <p>
        Aprobado por {transfer.approved_by_name ?? 'un aprobador'} el {formatDate(
          transfer.approved_at
        )}.
      </p>
    </Callout>
    {#if !routeEnabled}
      <Callout variant="warning" dismissible={false} class="mb-0">
        <p>
          Esta ruta está desactivada en las reglas de traslados, así que no se puede despachar. Aún
          puedes cancelar el traslado.
        </p>
      </Callout>
    {/if}
  {/if}
</section>
