<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchasesApi } from '$lib/api/purchases';
  import { permissions } from '$lib/stores/permissions.svelte';
  import PurchaseVerificationEditor from '$lib/features/purchases/components/PurchaseVerificationEditor.svelte';
  import type { Purchase } from '$lib/types/purchase';

  type WorkflowAction = 'receive' | 'cancel' | 'close';

  let {
    purchase,
    productLabels = new Map<number, string>(),
    unitLabels = new Map<number, string>(),
    onupdated
  }: {
    purchase: Purchase;
    productLabels?: Map<number, string>;
    unitLabels?: Map<number, string>;
    onupdated: (purchase: Purchase) => void;
  } = $props();

  let processing = $state<WorkflowAction | null>(null);
  let error = $state<string | null>(null);
  let showVerification = $state(false);

  let canManage = $derived(permissions.hasPermission('purchases:manage'));
  let canReceive = $derived(permissions.hasPermission('purchases:receive'));
  let canVerify = $derived(permissions.hasPermission('purchases:verify'));
  let canReceiveInventory = $derived(permissions.hasPermission('inventory:receive'));
  let canViewLocations = $derived(permissions.hasPermission('locations.view'));
  let canCompleteVerification = $derived(
    canVerify && canReceiveInventory && canViewLocations
  );

  let hasActions = $derived(
    (purchase.status === 'draft' && (canManage || canReceive)) ||
      (purchase.status === 'received' && permissions.hasPermission('purchases:read')) ||
      (purchase.status === 'verified' && canVerify)
  );

  function errorMessage(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;

    return 'No se pudo completar la acción sobre la compra.';
  }

  async function runAction(action: WorkflowAction) {
    if (processing) return;

    processing = action;
    error = null;

    try {
      let updated: Purchase;

      if (action === 'receive') {
        updated = await purchasesApi.receive(purchase.id);
      } else if (action === 'cancel') {
        updated = await purchasesApi.cancel(purchase.id);
      } else {
        updated = await purchasesApi.close(purchase.id);
      }

      onupdated(updated);
    } catch (cause: unknown) {
      error = errorMessage(cause);
    } finally {
      processing = null;
    }
  }

  function editDraft() {
    void goto(`/purchases/${purchase.id}/edit`);
  }
</script>

{#if hasActions}
  <section class="rounded-xl border border-border bg-surface p-4" aria-label="Acciones de compra">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="font-semibold text-foreground">Acciones</h2>
        <p class="mt-1 text-sm text-foreground-muted">
          Ejecuta las transiciones permitidas para el estado actual de la recepción.
        </p>
      </div>

      <div class="flex flex-wrap gap-2">
        {#if purchase.status === 'draft'}
          {#if canManage}
            <Button
              size="sm"
              variant="secondary"
              disabled={processing !== null}
              onclick={editDraft}
            >
              Editar borrador
            </Button>
          {/if}

          {#if canReceive}
            <Button
              size="sm"
              variant="success"
              disabled={processing !== null}
              onclick={() => void runAction('receive')}
            >
              {processing === 'receive' ? 'Confirmando…' : 'Confirmar recepción'}
            </Button>
          {/if}

          {#if canManage}
            <Button
              size="sm"
              variant="danger"
              disabled={processing !== null}
              onclick={() => void runAction('cancel')}
            >
              {processing === 'cancel' ? 'Cancelando…' : 'Cancelar borrador'}
            </Button>
          {/if}
        {:else if purchase.status === 'received' && canVerify}
          {#if canCompleteVerification}
            <Button
              size="sm"
              variant="success"
              disabled={processing !== null}
              onclick={() => (showVerification = !showVerification)}
            >
              {showVerification ? 'Ocultar verificación' : 'Verificar recepción'}
            </Button>
          {:else}
            <p class="max-w-lg text-sm text-warning" role="status">
              {#if !canReceiveInventory && !canViewLocations}
                Para completar la recepción, tu perfil necesita acceso para registrar la mercancía en
                Inventario y consultar o asignar ubicaciones. Pide al administrador que revise esos accesos.
              {:else if !canReceiveInventory}
                Para completar la recepción, tu perfil necesita acceso para registrar la mercancía en
                Inventario. Pide al administrador que revise ese acceso.
              {:else}
                Para completar la recepción, tu perfil necesita acceso para consultar y asignar
                ubicaciones. Pide al administrador que revise ese acceso.
              {/if}
            </p>
          {/if}
        {:else if purchase.status === 'received'}
          <p class="max-w-lg text-sm text-warning" role="status">
            Tu perfil puede consultar esta recepción. Para verificarla, pide al administrador que habilite
            la revisión de recepciones para tu perfil.
          </p>
        {:else if purchase.status === 'verified' && canVerify}
          <Button size="sm" disabled={processing !== null} onclick={() => void runAction('close')}>
            {processing === 'close' ? 'Cerrando…' : 'Cerrar recepción'}
          </Button>
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

    {#if showVerification && purchase.status === 'received' && canCompleteVerification}
      <PurchaseVerificationEditor
        {purchase}
        {productLabels}
        {unitLabels}
        onupdated={(updated) => {
          showVerification = false;
          onupdated(updated);
        }}
        oncancel={() => (showVerification = false)}
      />
    {/if}
  </section>
{/if}
