<script lang="ts">
  import { tick } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Callout from '$lib/components/ui/Callout.svelte';
  import { HttpError } from '$lib/api/client';
  import {
    inventoryTransfersApi,
    type AssignmentCheck,
    type DispatchIssue,
    type InventoryTransfer
  } from '$lib/features/inventory/transfer-documents';
  import { assignmentFitness, FITNESS_LABEL } from '$lib/features/inventory/transfer-operations';

  interface Props {
    transfer: InventoryTransfer;
    /** Can prepare, send and withdraw (inventory:move). */
    canMove: boolean;
    /** Can approve or reject (inventory:transfer_approve). */
    canApprove: boolean;
    currentUserId: string | null;
    /** The server lets a superuser decide on their own transfers. */
    isSuperuser?: boolean;
    /** Only people who cover the origin branch may decide; false hides the decision buttons. */
    canAccessOrigin?: boolean;
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
    canAccessOrigin = true,
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
  let check = $state<AssignmentCheck | null>(null);
  let checking = $state(false);
  let checkError = $state<string | null>(null);
  let checkSequence = 0;

  const missingTransport = $derived(!transfer.vehicle || !transfer.driver);
  // The live verdict only matters while somebody still has to send or approve the transfer.
  const liveCheck = $derived(
    transfer.status === 'pending_approval' ||
      (transfer.status === 'preparation' && transfer.requires_approval)
  );
  const fitness = $derived(assignmentFitness(check));
  const planningBlocked = $derived(missingTransport || check?.planning_blocked === true);
  const issues = $derived<DispatchIssue[]>(
    check ? [...check.vehicle_issues, ...check.driver_issues] : []
  );
  const blockingIssues = $derived(issues.filter((issue) => issue.severity === 'blocking'));
  const warningIssues = $derived(issues.filter((issue) => issue.severity === 'warning'));
  // The transport the approver authorised, or the one saved while still being prepared.
  const shownVehicle = $derived(
    transfer.status === 'approved' ? (transfer.approved_vehicle ?? transfer.vehicle) : transfer.vehicle
  );
  const shownDriver = $derived(
    transfer.status === 'approved' ? (transfer.approved_driver ?? transfer.driver) : transfer.driver
  );
  const transportNote = $derived(
    missingTransport
      ? 'Elige vehículo y conductor antes de enviar el traslado a aprobación. Usa «Editar preparación» para asignarlos.'
      : check?.planning_blocked
        ? 'El transporte asignado no es apto para planificar. Corrige la preparación antes de continuar.'
        : ''
  );
  const decisionNote = $derived(
    missingTransport
      ? 'No se puede aprobar un traslado sin vehículo y conductor. Quien lo preparó debe asignarlos.'
      : check?.planning_blocked
        ? 'No se puede aprobar mientras el transporte asignado no sea apto. Recházalo para que lo corrijan.'
        : ''
  );

  $effect(() => {
    const id = transfer.id;
    // Re-judge when somebody changes the vehicle or the driver of the saved preparation.
    const vehicleKey = transfer.vehicle?.id;
    const driverKey = transfer.driver?.id;
    const sequence = ++checkSequence;
    check = null;
    checkError = null;
    if (!liveCheck || !vehicleKey || !driverKey) {
      checking = false;
      return;
    }
    checking = true;
    void (async () => {
      try {
        const result = await inventoryTransfersApi.transferAssignmentCheck(id);
        if (sequence === checkSequence) check = result;
      } catch (cause) {
        if (sequence === checkSequence)
          checkError =
            cause instanceof HttpError
              ? cause.message
              : 'No se pudo revisar el transporte. El servidor lo validará de todos modos.';
      } finally {
        if (sequence === checkSequence) checking = false;
      }
    })();
  });

  // Whoever prepared, edited or sent the transfer cannot decide on it (the server enforces it).
  const isAuthor = $derived(
    currentUserId != null &&
      (transfer.created_by_id === currentUserId ||
        transfer.submitted_by_id === currentUserId ||
        transfer.last_edited_by_id === currentUserId)
  );
  const isRequester = $derived(
    currentUserId != null &&
      (transfer.created_by_id === currentUserId || transfer.submitted_by_id === currentUserId)
  );
  const canDecide = $derived(canApprove && canAccessOrigin && (!isAuthor || isSuperuser));
  // Someone who could decide can still take back what they sent, even as a superuser.
  const canWithdraw = $derived(canMove && (!canDecide || isRequester));
  const originName = $derived(transfer.origin_branch_name ?? transfer.origin_warehouse_name);
  // A rejection reason may already end in punctuation; the sentence adds its own.
  const rejectionReason = $derived.by(() => {
    const text = (transfer.rejection_reason ?? '').trim();
    return text.replace(/[\s.,;:!?¡¿…]+$/u, '') || text;
  });

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

{#snippet transport()}
  <section
    class="space-y-3 rounded-xl border border-border bg-surface-muted/40 p-3 sm:p-4"
    aria-labelledby="transfer-assignment-title"
  >
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h3 id="transfer-assignment-title" class="text-sm font-semibold text-foreground">
        Transporte asignado
      </h3>
      {#if liveCheck && checking}
        <span class="text-xs text-foreground-muted" role="status">Revisando el transporte…</span>
      {:else if fitness}
        <Badge variant={fitness === 'blocked' ? 'danger' : fitness === 'warning' ? 'warning' : 'success'}
          >{FITNESS_LABEL[fitness]}</Badge
        >
      {/if}
    </div>
    <dl class="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
      <div>
        <dt class="text-xs text-foreground-muted">Vehículo</dt>
        <dd class="font-medium text-foreground">
          {#if shownVehicle}
            {shownVehicle.code} · {shownVehicle.plate ?? 'Sin placa'}
            {#if shownVehicle.name}<span class="font-normal text-foreground-muted"
                >{shownVehicle.name}</span
              >{/if}
          {:else}
            <span class="text-danger">Sin asignar</span>
          {/if}
        </dd>
      </div>
      <div>
        <dt class="text-xs text-foreground-muted">Conductor</dt>
        <dd class="font-medium text-foreground">
          {#if shownDriver}
            {shownDriver.name}
            <span class="font-normal text-foreground-muted">{shownDriver.employee_code}</span>
          {:else}
            <span class="text-danger">Sin asignar</span>
          {/if}
        </dd>
      </div>
    </dl>
    {#if liveCheck}
      <div class="space-y-2" aria-live="polite">
        {#if blockingIssues.length}
          <ul
            class="space-y-1 rounded-xl border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger"
            aria-label="Impedimentos del transporte"
          >
            {#each blockingIssues as issue, index (index)}<li>{issue.message}</li>{/each}
          </ul>
        {/if}
        {#if warningIssues.length}
          <ul
            class="space-y-1 rounded-xl border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-foreground"
            aria-label="Advertencias del transporte"
          >
            {#each warningIssues as issue, index (index)}<li>{issue.message}</li>{/each}
          </ul>
        {/if}
        {#if check?.conflicts.length}
          <ul
            class="space-y-1 rounded-xl border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-foreground"
            aria-label="Otros traslados con este transporte"
          >
            {#each check.conflicts as conflict (conflict.transfer_id)}
              <li>{conflict.message}</li>
            {/each}
          </ul>
        {/if}
        {#if checkError}<p class="text-xs text-foreground-muted" role="status">{checkError}</p>{/if}
      </div>
    {/if}
  </section>
{/snippet}

<section class="space-y-3" aria-label="Aprobación del traslado">
  {#if transfer.status === 'preparation' && transfer.requires_approval}
    {#if transfer.rejection_reason}
      <Callout variant="danger" dismissible={false} class="mb-0">
        <p>
          Rechazado por {transfer.rejected_by_name ?? 'un aprobador'} el {formatDate(
            transfer.rejected_at
          )}: {rejectionReason}. Corrige la preparación y vuelve a enviarla.
        </p>
      </Callout>
    {/if}
    {#if routeEnabled}
      <Callout variant="info" dismissible={false} class="mb-0">
        <p>Este traslado sale de {originName} y necesita aprobación antes de despacharse.</p>
      </Callout>
    {:else}
      <div id="transfer-route-disabled-note">
        <Callout variant="warning" dismissible={false} class="mb-0">
          <p>
            Esta ruta está desactivada en las reglas de traslados, así que no se puede enviar a
            aprobación. Todavía puedes cancelar el traslado.
          </p>
        </Callout>
      </div>
    {/if}
    {@render transport()}
    <div class="flex flex-wrap items-center gap-2">
      <Button
        disabled={!canMove || busy || !routeEnabled || planningBlocked}
        describedby={!routeEnabled
          ? 'transfer-route-disabled-note'
          : planningBlocked
            ? 'transfer-transport-note'
            : undefined}
        onclick={onSubmit}
      >
        Enviar a aprobación
      </Button>
      {#if !canMove}
        <p class="text-xs text-foreground-muted">
          Necesitas el permiso de movimiento de inventario para enviarlo.
        </p>
      {/if}
    </div>
    {#if routeEnabled && planningBlocked && transportNote}
      <p id="transfer-transport-note" class="text-sm text-foreground">{transportNote}</p>
    {/if}
  {:else if transfer.status === 'pending_approval'}
    <Callout variant="warning" dismissible={false} class="mb-0">
      <p>
        Enviado por {transfer.submitted_by_name ?? 'un usuario'} el {formatDate(
          transfer.submitted_at
        )}. Esperando aprobación.
      </p>
    </Callout>
    {@render transport()}
    {#if !routeEnabled}
      <div id="transfer-route-disabled-note">
        <Callout variant="warning" dismissible={false} class="mb-0">
          <p>
            Esta ruta está desactivada en las reglas de traslados, así que no se puede aprobar. Aún
            puedes rechazarlo, retirarlo o cancelarlo.
          </p>
        </Callout>
      </div>
    {/if}
    {#if canApprove && !canAccessOrigin}
      <p class="text-sm text-foreground-muted" role="note">
        No tienes acceso a la sucursal de origen para decidir este traslado.
      </p>
    {:else if canApprove && !canDecide}
      <p class="text-sm text-foreground-muted" role="note">
        No puedes aprobar un traslado que tú preparaste, editaste o enviaste.
      </p>
    {/if}
    {#if canDecide}
      <div class="flex flex-wrap items-center gap-2">
        <Button
          disabled={busy || !routeEnabled || planningBlocked}
          describedby={!routeEnabled
            ? 'transfer-route-disabled-note'
            : planningBlocked
              ? 'transfer-decision-note'
              : undefined}
          onclick={onApprove}>Aprobar traslado</Button
        >
        <Button
          id="transfer-reject-open"
          variant="secondary"
          disabled={busy || rejecting}
          onclick={() => void openRejection()}>Rechazar</Button
        >
      </div>
      {#if routeEnabled && planningBlocked && decisionNote}
        <p id="transfer-decision-note" class="text-sm text-foreground">{decisionNote}</p>
      {/if}
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
    {#if canWithdraw}
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
    {@render transport()}
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
