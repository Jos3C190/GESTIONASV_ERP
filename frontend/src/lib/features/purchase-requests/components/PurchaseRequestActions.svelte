<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseRequestsApi } from '$lib/api/purchase-requests';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { PurchaseRequest } from '$lib/types/purchase-request';

  interface Props {
    item: PurchaseRequest;
    onupdated?: (item: PurchaseRequest) => void;
  }

  type WorkflowAction = 'submit' | 'approve' | 'reject' | 'cancel';

  let { item, onupdated }: Props = $props();
  let processing = $state<WorkflowAction | null>(null);
  let error = $state<string | null>(null);

  let canManage = $derived(permissions.hasPermission('purchase_requests:manage'));
  let canApprove = $derived(permissions.hasPermission('purchase_requests:approve'));

  async function runAction(action: WorkflowAction) {
    if (processing) return;

    processing = action;
    error = null;

    try {
      const updated = await purchaseRequestsApi[action](item.id);
      onupdated?.(updated);
    } catch (err: unknown) {
      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudo completar la acción sobre la solicitud.';
    } finally {
      processing = null;
    }
  }
</script>

<div class="space-y-3">
  {#if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {/if}

  <div class="flex flex-wrap items-center gap-2">
    {#if item.status === 'draft' && canManage}
      <Button
        size="sm"
        variant="secondary"
        disabled={processing !== null}
        onclick={() => goto(`/purchase-requests/${item.id}/edit`)}
      >
        Editar
      </Button>
      <Button size="sm" disabled={processing !== null} onclick={() => void runAction('submit')}>
        {processing === 'submit' ? 'Enviando…' : 'Enviar a aprobación'}
      </Button>
      <Button
        size="sm"
        variant="danger"
        disabled={processing !== null}
        onclick={() => void runAction('cancel')}
      >
        {processing === 'cancel' ? 'Cancelando…' : 'Cancelar solicitud'}
      </Button>
    {:else if item.status === 'submitted'}
      {#if canApprove}
        <Button
          size="sm"
          variant="success"
          disabled={processing !== null}
          onclick={() => void runAction('approve')}
        >
          {processing === 'approve' ? 'Aprobando…' : 'Aprobar'}
        </Button>
        <Button
          size="sm"
          variant="danger"
          disabled={processing !== null}
          onclick={() => void runAction('reject')}
        >
          {processing === 'reject' ? 'Rechazando…' : 'Rechazar'}
        </Button>
      {/if}

      {#if canManage}
        <Button
          size="sm"
          variant="danger"
          disabled={processing !== null}
          onclick={() => void runAction('cancel')}
        >
          {processing === 'cancel' ? 'Cancelando…' : 'Cancelar solicitud'}
        </Button>
      {/if}
    {/if}
  </div>
</div>
