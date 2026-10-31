<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { retaceosApi } from '$lib/api/retaceos';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import type { Retaceo } from '$lib/types/retaceo';

  type WorkflowAction = 'calculate' | 'verify' | 'cancel' | 'close' | 'apply';

  let {
    retaceo,
    onupdated
  }: {
    retaceo: Retaceo;
    onupdated: (retaceo: Retaceo) => void;
  } = $props();

  let processing = $state<WorkflowAction | null>(null);
  let error = $state<string | null>(null);

  let canManage = $derived(permissions.hasPermission('retaceos:manage'));
  let canCalculate = $derived(permissions.hasPermission('retaceos:calculate'));
  let canVerify = $derived(permissions.hasPermission('retaceos:verify'));
  let canApply = $derived(
    canVerify && permissions.hasPermission('inventory:valuation') && branch.accessAllBranches
  );
  let valuationEnabled = $state<boolean | null>(null);
  let valuationError = $state<string | null>(null);
  let statusRevision = $state(0);

  $effect(() => {
    const id = retaceo.id;
    void statusRevision;
    let active = true;
    valuationEnabled = null;
    valuationError = null;
    void retaceosApi
      .valuationStatus(id)
      .then((status) => {
        if (active) valuationEnabled = status.enabled;
      })
      .catch((cause: unknown) => {
        if (active) valuationError = errorMessage(cause);
      });
    return () => {
      active = false;
    };
  });

  let hasActions = $derived(
    (retaceo.status === 'draft' && (canCalculate || canManage)) ||
      (retaceo.status === 'calculated' && (canVerify || canManage)) ||
      (retaceo.status === 'verified' && canVerify)
  );

  function errorMessage(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;

    return 'No se pudo completar la acción sobre el retaceo.';
  }

  function editDraft() {
    void goto(`/retaceos/${retaceo.id}/edit`);
  }

  async function runAction(action: WorkflowAction) {
    if (processing) return;

    processing = action;
    error = null;

    try {
      let updated: Retaceo;

      if (action === 'calculate') {
        updated = await retaceosApi.calculate(retaceo.id);
      } else if (action === 'verify') {
        updated = await retaceosApi.verify(retaceo.id);
      } else if (action === 'cancel') {
        updated = await retaceosApi.cancel(retaceo.id);
      } else if (action === 'apply') {
        updated = await retaceosApi.apply(retaceo.id);
      } else {
        updated = await retaceosApi.close(retaceo.id);
      }

      onupdated(updated);
    } catch (cause: unknown) {
      error = errorMessage(cause);
    } finally {
      processing = null;
    }
  }
</script>

{#if hasActions}
  <section class="rounded-xl border border-border bg-surface p-4" aria-label="Acciones de retaceo">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="font-semibold text-foreground">Acciones</h2>

        <p class="mt-1 text-sm text-foreground-muted">
          Revisa el cálculo, verifica los costos y completa el retaceo.
        </p>
      </div>

      <div class="flex flex-wrap gap-2">
        {#if retaceo.status === 'draft'}
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

          {#if canCalculate}
            <Button
              size="sm"
              variant="success"
              disabled={processing !== null}
              onclick={() => void runAction('calculate')}
            >
              {processing === 'calculate' ? 'Calculando…' : 'Calcular retaceo'}
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
        {:else if retaceo.status === 'calculated'}
          {#if canVerify}
            <Button
              size="sm"
              variant="success"
              disabled={processing !== null}
              onclick={() => void runAction('verify')}
            >
              {processing === 'verify' ? 'Verificando…' : 'Verificar retaceo'}
            </Button>
          {/if}

          {#if canManage}
            <Button
              size="sm"
              variant="danger"
              disabled={processing !== null}
              onclick={() => void runAction('cancel')}
            >
              {processing === 'cancel' ? 'Cancelando…' : 'Cancelar retaceo'}
            </Button>
          {/if}
        {:else if retaceo.status === 'verified' && canVerify}
          {#if valuationEnabled && !retaceo.applied_at}
            {#if canApply}
              <Button
                size="sm"
                variant="success"
                disabled={processing !== null}
                onclick={() => void runAction('apply')}
              >
                {processing === 'apply' ? 'Aplicando costo…' : 'Aplicar costo al inventario'}
              </Button>
            {/if}
          {:else}
            <Button
              size="sm"
              disabled={processing !== null || valuationEnabled === null}
              onclick={() => void runAction('close')}
            >
              {processing === 'close' ? 'Cerrando…' : 'Cerrar retaceo'}
            </Button>
          {/if}
        {/if}
      </div>
    </div>

    {#if retaceo.status === 'verified' && valuationEnabled === null && !valuationError}
      <p class="mt-3 text-sm text-foreground-muted" role="status">
        Consultando estado de valoración…
      </p>
    {/if}

    {#if retaceo.applied_at}
      <p class="mt-3 text-sm text-success" role="status">
        Costo aplicado al inventario. El cierre conservará este registro.
      </p>
    {:else if retaceo.status === 'verified' && valuationEnabled}
      <p class="mt-3 text-sm text-foreground-muted">
        Aplica el costo verificado antes de cerrar. Se ajustarán las existencias y las salidas
        afectadas, sin agregar unidades.
        {#if !canApply}Esta acción requiere permiso de valoración y acceso a todas las sucursales.{/if}
      </p>
    {:else if retaceo.status === 'verified' && valuationEnabled === false}
      <p class="mt-3 text-sm text-foreground-muted">
        La valoración está pendiente de un saldo inicial aprobado. Este cierre conserva el cálculo
        del retaceo sin registrar un ajuste de inventario.
      </p>
      {#if canApply}<a
          class="mt-2 inline-block text-sm text-primary underline"
          href="/inventory/valuation">Revisar valoración de inventario</a
        >{/if}
    {/if}

    {#if valuationError}
      <div class="mt-3 text-sm text-danger" role="alert">
        {valuationError}
        <Button size="sm" variant="secondary" onclick={() => statusRevision++}
          >Reintentar consulta</Button
        >
      </div>
    {/if}

    {#if retaceo.status === 'draft' && canManage && !canCalculate}
      <p
        class="mt-3 rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-sm text-warning"
        role="status"
      >
        Puedes editar o cancelar este borrador. Para calcularlo, pide al administrador que habilite
        el cálculo de retaceos para tu perfil.
      </p>
    {:else if retaceo.status === 'calculated' && canManage && !canVerify}
      <p
        class="mt-3 rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-sm text-warning"
        role="status"
      >
        El cálculo está listo. Para verificar y cerrar este retaceo, pide al administrador que
        habilite la revisión de retaceos para tu perfil.
      </p>
    {/if}

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
