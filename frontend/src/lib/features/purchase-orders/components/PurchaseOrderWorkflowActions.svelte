<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseOrdersApi } from '$lib/api/purchase-orders';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { PurchaseOrder } from '$lib/types/purchase-order';

  type WorkflowAction = 'submit' | 'approve' | 'send' | 'cancel';

  let {
    order,
    onupdated
  }: {
    order: PurchaseOrder;
    onupdated: (order: PurchaseOrder) => void;
  } = $props();

  let pending = $state<WorkflowAction | null>(null);
  let error = $state<string | null>(null);

  let canManage = $derived(permissions.hasPermission('purchase_orders:manage'));
  let canApprove = $derived(permissions.hasPermission('purchase_orders:approve'));
  let canSend = $derived(permissions.hasPermission('purchase_orders:send'));
  let hasActions = $derived(
    (order.status === 'draft' && canManage) ||
      (order.status === 'pending_approval' && (canManage || canApprove)) ||
      (order.status === 'approved' && (canManage || canSend))
  );

  function errorMessage(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return 'No se pudo completar la acción de la orden de compra.';
  }

  async function run(action: WorkflowAction) {
    if (pending) return;

    pending = action;
    error = null;

    try {
      let updated: PurchaseOrder;

      if (action === 'submit') {
        updated = await purchaseOrdersApi.submit(order.id);
      } else if (action === 'approve') {
        updated = await purchaseOrdersApi.approve(order.id);
      } else if (action === 'send') {
        updated = await purchaseOrdersApi.send(order.id);
      } else {
        updated = await purchaseOrdersApi.cancel(order.id);
      }

      onupdated(updated);
    } catch (cause: unknown) {
      error = errorMessage(cause);
    } finally {
      pending = null;
    }
  }
</script>

{#if hasActions}
  <section
    class="rounded-xl border border-border bg-surface p-4"
    aria-label="Acciones de orden de compra"
  >
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="font-semibold text-foreground">Acciones</h2>
        <p class="mt-1 text-sm text-foreground-muted">
          Ejecuta únicamente las transiciones expuestas por el backend para el estado actual.
        </p>
      </div>

      <div class="flex flex-wrap gap-2">
        {#if order.status === 'draft' && canManage}
          <Button
            size="sm"
            variant="secondary"
            disabled={pending !== null}
            onclick={() => goto(`/purchase-orders/${order.id}/edit`)}
          >
            Editar
          </Button>
          <Button disabled={pending !== null} onclick={() => void run('submit')}>
            {pending === 'submit' ? 'Enviando…' : 'Enviar a aprobación'}
          </Button>
          <Button variant="danger" disabled={pending !== null} onclick={() => void run('cancel')}>
            {pending === 'cancel' ? 'Cancelando…' : 'Cancelar orden'}
          </Button>
        {:else if order.status === 'pending_approval'}
          {#if canApprove}
            <Button
              variant="success"
              disabled={pending !== null}
              onclick={() => void run('approve')}
            >
              {pending === 'approve' ? 'Aprobando…' : 'Aprobar orden'}
            </Button>
          {/if}
          {#if canManage}
            <Button variant="danger" disabled={pending !== null} onclick={() => void run('cancel')}>
              {pending === 'cancel' ? 'Cancelando…' : 'Cancelar orden'}
            </Button>
          {/if}
        {:else if order.status === 'approved'}
          {#if canSend}
            <Button disabled={pending !== null} onclick={() => void run('send')}>
              {pending === 'send' ? 'Enviando…' : 'Enviar al proveedor'}
            </Button>
          {/if}
          {#if canManage}
            <Button variant="danger" disabled={pending !== null} onclick={() => void run('cancel')}>
              {pending === 'cancel' ? 'Cancelando…' : 'Cancelar orden'}
            </Button>
          {/if}
        {/if}
      </div>
    </div>

    {#if error}
      <div
        class="mt-4 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
        role="alert"
      >
        {error}
      </div>
    {/if}
  </section>
{/if}
