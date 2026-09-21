<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { retaceosApi } from '$lib/api/retaceos';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Retaceo } from '$lib/types/retaceo';

  type WorkflowAction = 'calculate' | 'verify' | 'cancel' | 'close';

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
          Ejecuta las transiciones permitidas para el estado actual del retaceo.
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
          <Button size="sm" disabled={processing !== null} onclick={() => void runAction('close')}>
            {processing === 'close' ? 'Cerrando…' : 'Cerrar retaceo'}
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
  </section>
{/if}
