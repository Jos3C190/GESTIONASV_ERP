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
  let readiness = $state<Awaited<ReturnType<typeof purchasesApi.receivingReadiness>> | null>(null);
  let readinessError = $state<string | null>(null);
  let readinessRevision = $state(0);
  $effect(() => {
    const id = purchase.id;
    const status = purchase.status;
    void readinessRevision;
    readiness = null;
    readinessError = null;
    if (!['received', 'verified', 'closed'].includes(status)) return;
    let active = true;
    void purchasesApi
      .receivingReadiness(id)
      .then((value) => {
        if (active) readiness = value;
      })
      .catch((cause) => {
        if (active)
          readinessError =
            cause instanceof Error ? cause.message : 'No se pudo consultar el cierre de retaceo.';
      });
    return () => {
      active = false;
    };
  });

  let canManage = $derived(permissions.hasPermission('purchases:manage'));
  let canReceive = $derived(permissions.hasPermission('purchases:receive'));
  let canVerify = $derived(permissions.hasPermission('purchases:verify'));
  let canReceiveInventory = $derived(permissions.hasPermission('inventory:receive'));
  let canViewLocations = $derived(permissions.hasPermission('locations.view'));
  let canCompleteVerification = $derived(canVerify && canReceiveInventory && canViewLocations);

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

{#if purchase.inventory_workflow === 'placement_before_inventory' && ['verified', 'closed'].includes(purchase.status) && permissions.hasPermission('inventory:warehouse_receipts')}
  <section class="rounded-xl border border-border bg-surface p-4">
    <h2 class="font-semibold text-foreground">Continuar con el bodeguero</h2>
    <p class="mt-2 text-sm leading-6 text-foreground-muted">
      Las unidades están preparadas. Revisa medidas y etiquetas y confirma su ubicación para
      ingresar cantidad y valor al inventario.
    </p>
    <a
      class="mt-3 inline-flex min-h-11 items-center rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      href={`/inventory?warehouse_id=${encodeURIComponent(purchase.warehouse_id)}`}
      >Preparar y ubicar →</a
    >
  </section>
{/if}

{#if ['retaceo_before_inventory', 'placement_before_inventory'].includes(purchase.inventory_workflow ?? '') && ['verified', 'closed'].includes(purchase.status) && permissions.hasPermission('retaceos:read')}
  <section class="rounded-xl border border-border bg-surface p-4" aria-label="Retaceo de la compra">
    {#if readiness?.retaceo_id}
      <a
        class="rounded text-sm font-medium text-primary underline underline-offset-4"
        href={`/retaceos/${readiness.retaceo_id}`}>Consultar {readiness.retaceo_code}</a
      >
      <p class="mt-2 text-sm text-foreground-muted">
        El retaceo cerrado conserva los costos utilizados para registrar esta recepción.
      </p>
    {:else if readinessError}
      <p role="alert" class="text-sm text-foreground">{readinessError}</p>
      <Button class="mt-2" variant="secondary" size="sm" onclick={() => (readinessRevision += 1)}
        >Reintentar consulta</Button
      >
    {:else if readiness}<p class="text-sm text-foreground-muted">
        No se encontró un retaceo vinculado. Consulta la compra antes de continuar.
      </p>
    {:else}<p role="status" class="text-sm text-foreground-muted">
        Consultando el retaceo de esta compra…
      </p>{/if}
  </section>
{/if}

{#if hasActions}
  <section class="rounded-xl border border-border bg-surface p-4" aria-label="Acciones de compra">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="font-semibold text-foreground">Acciones</h2>
        <p class="mt-1 text-sm text-foreground-muted">
          Revisa la compra y continúa con el paso de recepción que corresponde.
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
        {:else if purchase.status === 'received' && !readiness}
          {#if readinessError}<p role="alert" class="text-sm text-foreground">{readinessError}</p>
            <Button variant="secondary" size="sm" onclick={() => (readinessRevision += 1)}
              >Reintentar consulta</Button
            >{:else}<p role="status" class="text-sm text-foreground-muted">
              Consultando el cierre de retaceo…
            </p>{/if}
        {:else if purchase.status === 'received' && readiness?.required && !readiness.ready}
          <div class="max-w-xl space-y-3">
            <p class="text-sm leading-6 text-foreground">
              Primero completa y cierra el retaceo. La verificación de bodega y el registro de
              existencias se habilitarán después del cierre.
            </p>
            {#if readiness.retaceo_id && permissions.hasPermission('retaceos:read')}<a
                class="inline-block rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground"
                href={`/retaceos/${readiness.retaceo_id}`}>Continuar {readiness.retaceo_code}</a
              >
            {:else if !readiness.retaceo_id && permissions.hasPermission('retaceos:manage')}<a
                class="inline-block rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground"
                href={`/retaceos/new?purchase_id=${purchase.id}`}>Crear retaceo</a
              >{/if}
            <Button variant="secondary" size="sm" onclick={() => (readinessRevision += 1)}
              >Actualizar estado</Button
            >
          </div>
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
            <p class="max-w-lg text-sm text-foreground" role="status">
              {#if !canReceiveInventory && !canViewLocations}
                Para completar la recepción, tu perfil necesita acceso para registrar la mercancía
                en Inventario y consultar o asignar ubicaciones. Pide al administrador que revise
                esos accesos.
              {:else if !canReceiveInventory}
                Para completar la recepción, tu perfil necesita acceso para registrar la mercancía
                en Inventario. Pide al administrador que revise ese acceso.
              {:else}
                Para completar la recepción, tu perfil necesita acceso para consultar y asignar
                ubicaciones. Pide al administrador que revise ese acceso.
              {/if}
            </p>
          {/if}
        {:else if purchase.status === 'received'}
          <p class="max-w-lg text-sm text-foreground" role="status">
            Tu perfil puede consultar esta recepción. Para verificarla, pide al administrador que
            habilite la revisión de recepciones para tu perfil.
          </p>
        {:else if purchase.status === 'verified' && canVerify}
          <Button size="sm" disabled={processing !== null} onclick={() => void runAction('close')}>
            {processing === 'close' ? 'Cerrando…' : 'Cerrar recepción'}
          </Button>
        {/if}
      </div>
    </div>
    {#if purchase.status === 'received' && readiness?.required && readiness.ready}<p
        class="mt-3 text-sm text-foreground-muted"
      >
        {readiness.retaceo_code}: retaceo cerrado. Continúa con la verificación de recepción para
        registrar las existencias y su costo final.
      </p>{/if}

    {#if error}
      <div
        class="mt-4 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-foreground"
        role="alert"
      >
        {error}
      </div>
    {/if}

    {#if showVerification && purchase.status === 'received' && canCompleteVerification && readiness?.ready}
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
