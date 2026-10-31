<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import type {
    PurchaseConsolidationAwardDecision,
    PurchaseConsolidationAwardLine
  } from '$lib/types/purchase-consolidation';
  import { formatDate, formatQuantity } from '../adjudication-formatters';

  interface Props {
    line: PurchaseConsolidationAwardLine;
    supplierNames: Record<number, string>;
    actorNames: Record<string, string>;
    canAward: boolean;
    savingKey: string | null;
    success: { targetId: string; message: string } | null;
    onRevoke: (decision: PurchaseConsolidationAwardDecision, reason: string) => Promise<boolean>;
  }

  let { line, supplierNames, actorNames, canAward, savingKey, success, onRevoke }: Props = $props();
  let revokeId = $state<string | null>(null);
  let revokeReason = $state('');

  function actorLabel(id: string) {
    return actorNames[id] ? `${actorNames[id]} · ID ${id}` : `ID ${id}`;
  }

  async function submit(event: SubmitEvent, decision: PurchaseConsolidationAwardDecision) {
    event.preventDefault();
    if (await onRevoke(decision, revokeReason)) {
      revokeId = null;
      revokeReason = '';
    }
  }
</script>

{#if line.decisions.length > 0}
  <div class="mt-4 rounded-lg border border-border p-3 sm:p-4">
    <h4 class="text-sm font-semibold text-foreground">Historial de adjudicaciones</h4>
    <ul class="mt-2 divide-y divide-border">
      {#each line.decisions as decision (decision.id)}
        <li
          class="flex flex-col gap-2 py-3 first:pt-1 last:pb-1 sm:flex-row sm:items-start sm:justify-between"
        >
          <div class="text-sm">
            <p class="font-medium text-foreground">
              {formatQuantity(decision.quantity)}
              {line.unit_name} · {decision.quotation_code} · {supplierNames[decision.supplier_id] ??
                `Proveedor #${decision.supplier_id}`}
            </p>
            <p class="mt-1 text-xs text-foreground-muted">Motivo: {decision.reason}</p>
            <p class="mt-1 break-all text-xs text-foreground-muted">
              Decidió {actorLabel(decision.decided_by_id)} · {decision.created_at
                ? formatDate(decision.created_at)
                : 'fecha pendiente'}
            </p>
            {#if decision.revoked_at}
              <p class="mt-1 break-all text-xs text-warning">
                Revertida por {decision.revoked_by_id
                  ? actorLabel(decision.revoked_by_id)
                  : 'usuario desconocido'} · Motivo: {decision.revocation_reason}
              </p>
            {/if}
          </div>
          {#if decision.revoked_at === null && canAward}
            {#if revokeId === decision.id}
              <form
                class="flex w-full flex-col gap-2 sm:max-w-md sm:flex-row"
                onsubmit={(event) => submit(event, decision)}
              >
                <input
                  aria-label={`Motivo para revertir adjudicación de ${line.product_name} a ${supplierNames[decision.supplier_id] ?? `Proveedor #${decision.supplier_id}`}`}
                  bind:value={revokeReason}
                  class="h-10 min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 text-sm text-foreground"
                  placeholder="Motivo de reversión"
                  maxlength="2000"
                  required
                />
                <Button
                  type="submit"
                  size="sm"
                  variant="danger"
                  disabled={savingKey !== null}
                  class="focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  >{savingKey === decision.id ? 'Revirtiendo…' : 'Confirmar'}</Button
                >
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={savingKey !== null}
                  class="focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  onclick={() => {
                    revokeId = null;
                    revokeReason = '';
                  }}>Cerrar</Button
                >
              </form>
            {:else}
              <Button
                size="sm"
                variant="secondary"
                disabled={savingKey !== null}
                class="focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                onclick={() => {
                  revokeId = decision.id;
                  revokeReason = '';
                }}>Revertir</Button
              >
            {/if}
          {/if}
          {#if success?.targetId === decision.id}
            <p
              class="w-full rounded-md border border-success/30 bg-success/5 px-3 py-2 text-sm text-success sm:mt-2"
              role="status"
              aria-live="polite"
            >
              {success.message}
            </p>
          {/if}
        </li>
      {/each}
    </ul>
  </div>
{/if}
