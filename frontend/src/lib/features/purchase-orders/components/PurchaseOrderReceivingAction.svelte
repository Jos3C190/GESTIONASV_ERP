<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { purchasesApi } from '$lib/api/purchases';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Purchase } from '$lib/types/purchase';
  import type { PurchaseOrder } from '$lib/types/purchase-order';

  let { order }: { order: PurchaseOrder } = $props();
  let existingDraft = $state<Purchase | null>(null);
  let checkingDrafts = $state(true);
  let draftError = $state<string | null>(null);
  let requestSequence = 0;
  let receiptCompleted = $derived(order.status === 'received' || order.status === 'closed');

  let canCreateReceipt = $derived(
    (order.status === 'sent' || order.status === 'partially_received') &&
      permissions.hasPermission('purchases:read') &&
      permissions.hasPermission('purchases:manage')
  );

  function openReceiving() {
    void goto(`/purchases/new?order_id=${order.id}`);
  }

  function continueDraft() {
    if (existingDraft) void goto(`/purchases/${existingDraft.id}`);
  }

  async function checkDrafts(orderId: string) {
    const sequence = ++requestSequence;
    checkingDrafts = true;
    draftError = null;
    existingDraft = null;
    try {
      const page = await purchasesApi.list({
        purchase_order_id: orderId,
        status: 'draft',
        page: 1,
        size: 1
      });
      if (sequence !== requestSequence) return;
      existingDraft = page.items[0] ?? null;
    } catch {
      if (sequence !== requestSequence) return;
      draftError = 'No se pudo comprobar si hay una recepción en borrador para esta orden.';
    } finally {
      if (sequence === requestSequence) checkingDrafts = false;
    }
  }

  $effect(() => {
    const orderId = order.id;
    void order.status;
    if (canCreateReceipt) {
      void checkDrafts(orderId);
    } else {
      requestSequence += 1;
      existingDraft = null;
      checkingDrafts = false;
      draftError = null;
    }
  });
</script>

{#if receiptCompleted}
  <section
    class="rounded-xl border border-success/30 bg-success/10 p-4"
    aria-label="Recepción completada"
  >
    <h2 class="font-semibold text-foreground">Recepción completada</h2>
    <p class="mt-1 text-sm text-foreground-muted" role="status">
      Esta orden ya fue recibida en su totalidad. No admite nuevas recepciones.
    </p>
  </section>
{:else if canCreateReceipt}
  <section
    class="rounded-xl border border-border bg-surface p-4"
    aria-label="Recepción de orden de compra"
  >
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="font-semibold text-foreground">Recepción</h2>
        <p class="mt-1 text-sm text-foreground-muted">
          Guarda el borrador y confirma la recepción para actualizar las cantidades pendientes de la
          orden. Las recepciones parciales mantienen abierto únicamente el saldo pendiente.
        </p>
      </div>

      {#if checkingDrafts}
        <p class="text-sm text-foreground-muted" role="status">
          Consultando recepciones pendientes…
        </p>
      {:else if existingDraft}
        <div class="space-y-2">
          <p class="text-sm text-warning" role="status">
            {existingDraft.code} está en borrador; falta confirmar la recepción.
          </p>
          <Button onclick={continueDraft}>
            Continuar recepción {existingDraft.code}
          </Button>
        </div>
      {:else if draftError}
        <div class="space-y-2">
          <p class="text-sm text-danger" role="alert">{draftError}</p>
          <Button variant="secondary" onclick={() => void checkDrafts(order.id)}>Reintentar</Button>
        </div>
      {:else}
        <Button onclick={openReceiving}>Registrar recepción</Button>
      {/if}
    </div>
  </section>
{/if}
