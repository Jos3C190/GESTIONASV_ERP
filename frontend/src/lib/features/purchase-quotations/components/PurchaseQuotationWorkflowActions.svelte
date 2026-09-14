<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { PurchaseQuotation } from '$lib/types/purchase-quotation';

  type WorkflowAction = 'send' | 'evaluate' | 'select' | 'reject' | 'cancel';

  let {
    quotation,
    onupdated
  }: {
    quotation: PurchaseQuotation;
    onupdated: (quotation: PurchaseQuotation) => void;
  } = $props();

  let pending = $state<WorkflowAction | null>(null);
  let error = $state<string | null>(null);

  let canManage = $derived(permissions.hasPermission('purchase_quotations:manage'));
  let canSelect = $derived(permissions.hasPermission('purchase_quotations:select'));
  let canCreatePurchaseOrder = $derived(permissions.hasPermission('purchase_orders:manage'));
  let hasActions = $derived(
    (quotation.status === 'draft' && canManage) ||
      (quotation.status === 'requested' && canManage) ||
      (quotation.status === 'received' && (canManage || canSelect)) ||
      (quotation.status === 'under_evaluation' && (canManage || canSelect)) ||
      (quotation.status === 'selected' && canCreatePurchaseOrder)
  );

  function errorMessage(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return 'No se pudo completar la acción de la cotización.';
  }

  async function run(action: WorkflowAction) {
    if (pending) return;

    pending = action;
    error = null;

    try {
      let updated: PurchaseQuotation;

      if (action === 'send') {
        updated = await purchaseQuotationsApi.send(quotation.id);
      } else if (action === 'evaluate') {
        updated = await purchaseQuotationsApi.evaluate(quotation.id);
      } else if (action === 'select') {
        updated = await purchaseQuotationsApi.select(quotation.id);
      } else if (action === 'reject') {
        updated = await purchaseQuotationsApi.reject(quotation.id);
      } else {
        updated = await purchaseQuotationsApi.cancel(quotation.id);
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
    aria-label="Acciones de cotización"
  >
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="font-semibold text-foreground">Acciones</h2>
        <p class="mt-1 text-sm text-foreground-muted">
          Ejecuta únicamente las acciones disponibles para el estado actual.
        </p>
      </div>

      <div class="flex flex-wrap gap-2">
        {#if quotation.status === 'draft' && canManage}
          <Button disabled={pending !== null} onclick={() => void run('send')}>
            {pending === 'send' ? 'Enviando…' : 'Enviar al proveedor'}
          </Button>
          <Button variant="danger" disabled={pending !== null} onclick={() => void run('cancel')}>
            {pending === 'cancel' ? 'Cancelando…' : 'Cancelar cotización'}
          </Button>
        {:else if quotation.status === 'requested' && canManage}
          <a
            href={`/purchase-quotations/${quotation.id}/response`}
            class="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            Registrar respuesta
          </a>
          <Button variant="danger" disabled={pending !== null} onclick={() => void run('cancel')}>
            {pending === 'cancel' ? 'Cancelando…' : 'Cancelar cotización'}
          </Button>
        {:else if quotation.status === 'received'}
          {#if canManage}
            <Button
              variant="secondary"
              disabled={pending !== null}
              onclick={() => void run('evaluate')}
            >
              {pending === 'evaluate' ? 'Procesando…' : 'Pasar a evaluación'}
            </Button>
            <Button variant="danger" disabled={pending !== null} onclick={() => void run('reject')}>
              {pending === 'reject' ? 'Rechazando…' : 'Rechazar oferta'}
            </Button>
          {/if}
          {#if canSelect}
            <Button
              variant="success"
              disabled={pending !== null}
              onclick={() => void run('select')}
            >
              {pending === 'select' ? 'Seleccionando…' : 'Seleccionar oferta'}
            </Button>
          {/if}
        {:else if quotation.status === 'under_evaluation'}
          {#if canManage}
            <Button variant="danger" disabled={pending !== null} onclick={() => void run('reject')}>
              {pending === 'reject' ? 'Rechazando…' : 'Rechazar oferta'}
            </Button>
          {/if}
          {#if canSelect}
            <Button
              variant="success"
              disabled={pending !== null}
              onclick={() => void run('select')}
            >
              {pending === 'select' ? 'Seleccionando…' : 'Seleccionar oferta'}
            </Button>
          {/if}
        {:else if quotation.status === 'selected' && canCreatePurchaseOrder}
          <a
            href={`/purchase-orders/new?quotation_id=${quotation.id}`}
            class="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            Crear orden de compra
          </a>
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
