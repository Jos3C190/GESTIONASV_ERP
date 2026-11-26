<script lang="ts">
  /** Entrada, salida o retiro a caja fuerte; una salida sobre el tope de la caja pide supervisor. */
  import Button from '#lib/components/ui/Button.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { posApi } from '#lib/api/pos.ts';
  import type { MovementKind, PosMovement, SupervisorApproval } from '#lib/types/pos.ts';
  import SupervisorApprovalFields from './SupervisorApprovalFields.svelte';
  import { MOVEMENT_KIND, centsToAmount, formatMoney, idempotencyKey, toCents } from './format.ts';

  interface Props {
    open: boolean;
    kind: MovementKind;
    shiftId: string;
    branchId: string;
    threshold: string;
    onclose: () => void;
    onsaved: (movement: PosMovement) => void;
  }

  let { open, kind, shiftId, branchId, threshold, onclose, onsaved }: Props = $props();
  let amount = $state('');
  let reason = $state('');
  let reference = $state('');
  let approval = $state<SupervisorApproval | null>(null);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let key = $state(idempotencyKey('movimiento'));

  const cents = $derived(toCents(amount));
  const needsSupervisor = $derived(
    kind === 'cash_out' && cents !== null && cents > (toCents(threshold) ?? 0)
  );
  const valid = $derived(
    cents !== null &&
      cents > 0 &&
      reason.trim().length >= 5 &&
      (!needsSupervisor || approval !== null)
  );

  $effect(() => {
    if (open) {
      amount = '';
      reason = '';
      reference = '';
      approval = null;
      error = null;
      key = idempotencyKey('movimiento');
    }
  });

  async function save() {
    if (!valid || cents === null) return;
    saving = true;
    error = null;
    try {
      const movement = await posApi.addMovement(shiftId, {
        kind,
        amount: centsToAmount(cents),
        reason: reason.trim(),
        reference: reference.trim() || null,
        approval: needsSupervisor ? approval : null,
        idempotency_key: key
      });
      onsaved(movement);
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudo registrar el movimiento.';
      if (!(err instanceof HttpError && err.status === 0)) key = idempotencyKey('movimiento');
    } finally {
      saving = false;
    }
  }
</script>

<Modal {open} title={MOVEMENT_KIND[kind].label} {onclose} size="md">
  <form
    id="movement-form"
    class="space-y-4"
    onsubmit={(event) => {
      event.preventDefault();
      void save();
    }}
  >
    <p class="text-sm text-foreground-muted">{MOVEMENT_KIND[kind].hint}</p>
    <label class="block text-sm font-medium text-foreground">
      Monto
      <span class="relative mt-1 block">
        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle">$</span>
        <input
          class="h-12 w-full rounded-lg border border-border bg-surface pl-7 pr-3 text-xl font-semibold tabular-nums text-foreground"
          inputmode="decimal"
          autocomplete="off"
          placeholder="0.00"
          bind:value={amount}
        />
      </span>
      {#if amount && cents === null}
        <span class="mt-1 block text-xs text-danger">Escribe un monto con hasta dos decimales.</span
        >
      {/if}
    </label>
    <label class="block text-sm font-medium text-foreground">
      Motivo
      <input
        class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground"
        maxlength="200"
        placeholder={kind === 'cash_in' ? 'Cambio de monedas del banco' : 'Compra de bolsas'}
        bind:value={reason}
      />
    </label>
    <label class="block text-sm font-medium text-foreground">
      Referencia <span class="font-normal text-foreground-subtle">(opcional)</span>
      <input
        class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground"
        maxlength="60"
        placeholder="N.º de comprobante o bolsa"
        bind:value={reference}
      />
    </label>
    {#if needsSupervisor}
      <SupervisorApprovalFields
        {branchId}
        reason={`Las salidas mayores que ${formatMoney(threshold)} necesitan autorización.`}
        onchange={(value) => (approval = value)}
      />
    {/if}
    {#if error}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {error}
      </p>
    {/if}
  </form>
  {#snippet footer()}
    <Button variant="secondary" onclick={onclose}>Cancelar</Button>
    <Button type="submit" form="movement-form" disabled={!valid || saving}>
      {saving ? 'Registrando…' : 'Registrar'}
    </Button>
  {/snippet}
</Modal>
