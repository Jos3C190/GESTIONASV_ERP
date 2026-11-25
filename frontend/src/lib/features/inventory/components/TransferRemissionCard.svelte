<script lang="ts">
  import { HttpError } from '#lib/api/client.ts';
  import { salesInvoicesApi } from '#lib/api/sales-invoices.ts';
  import Button from '#lib/components/ui/Button.svelte';
  import { FISCAL_STATUS_BADGES, FISCAL_STATUS_LABELS } from '#lib/features/sales/fiscal-labels.ts';
  import { formatMoney } from '#lib/features/sales/quotation-labels.ts';
  import type { TransferRemission } from '#lib/types/sales-invoices.ts';

  interface Props {
    transferId: string;
    /** Puede emitir de nuevo la nota (lado de origen, permiso para mover inventario). */
    canReissue: boolean;
    /** Puede abrir el documento fiscal (permiso de facturación). */
    canOpenDocument: boolean;
  }
  let { transferId, canReissue, canOpenDocument }: Props = $props();

  let remission = $state<TransferRemission | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let saving = $state(false);
  let actionError = $state<string | null>(null);

  const document = $derived(remission?.document ?? null);
  const reissuable = $derived(
    document != null && (document.status === 'rejected' || document.status === 'failed')
  );

  async function load(id: string, quiet = false) {
    if (!quiet) loading = true;
    loadError = null;
    try {
      const result = await salesInvoicesApi.transferRemission(id);
      if (id === transferId) remission = result;
    } catch (cause) {
      if (id === transferId) {
        loadError =
          cause instanceof HttpError
            ? cause.message
            : 'No se pudo consultar la nota de remisión del traslado.';
      }
    } finally {
      if (id === transferId) loading = false;
    }
  }

  $effect(() => {
    void load(transferId);
  });

  // Mientras el trabajador la emite, la tarjeta se actualiza sola.
  $effect(() => {
    if (document?.status !== 'pending') return;
    const id = transferId;
    const timer = setTimeout(() => void load(id, true), 5000);
    return () => clearTimeout(timer);
  });

  async function reissue() {
    if (saving) return;
    saving = true;
    actionError = null;
    try {
      const created = await salesInvoicesApi.reissueTransferRemission(transferId);
      remission = { enabled: true, document: created };
    } catch (cause) {
      actionError =
        cause instanceof HttpError ? cause.message : 'No se pudo emitir de nuevo la nota.';
    } finally {
      saving = false;
    }
  }
</script>

{#if loading}
  <section class="space-y-2 rounded-xl border border-border bg-surface p-4" aria-busy="true">
    <div class="skeleton h-5 w-40 rounded"></div>
    <div class="skeleton h-4 w-2/3 rounded"></div>
  </section>
{:else if loadError}
  <div
    class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
    role="alert"
  >
    {loadError}
    <button class="ml-2 underline" onclick={() => void load(transferId)}>Reintentar</button>
  </div>
{:else if remission?.enabled || document}
  <section
    class="space-y-3 rounded-xl border border-border bg-surface p-4"
    aria-labelledby="transfer-remission-title"
  >
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h3 id="transfer-remission-title" class="font-semibold text-foreground">Nota de remisión</h3>
      {#if document}
        <span class={`rounded-full px-2 py-1 text-xs ${FISCAL_STATUS_BADGES[document.status]}`}
          >{FISCAL_STATUS_LABELS[document.status]}</span
        >
      {/if}
    </div>
    {#if document}
      <dl class="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <div>
          <dt class="text-xs text-foreground-muted">Número de control</dt>
          <dd class="break-all font-mono text-foreground">
            {#if canOpenDocument}
              <a
                class="text-primary hover:underline"
                href={`/sales/fiscal-documents/${document.id}`}
                >{document.control_number ?? 'Ver documento'}</a
              >
            {:else}
              {document.control_number ?? '—'}
            {/if}
          </dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Valor de lo despachado (al costo)</dt>
          <dd class="font-mono text-foreground">{formatMoney(document.total)}</dd>
        </div>
      </dl>
      {#if document.status === 'pending'}
        <p class="text-sm text-foreground-muted">
          Se está emitiendo ante Hacienda. Ampara la mercadería mientras va en camino.
        </p>
      {:else if reissuable}
        <div
          class="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
          role="alert"
        >
          {document.status === 'rejected'
            ? 'Hacienda rechazó la nota de remisión.'
            : 'La emisión de la nota de remisión falló.'}
          {document.error_message ? ` ${document.error_message}` : ''}
        </div>
        {#if canReissue}
          <Button size="sm" disabled={saving} onclick={() => void reissue()}>
            {saving ? 'Emitiendo…' : 'Emitir de nuevo'}
          </Button>
        {/if}
      {:else}
        <p class="text-sm text-foreground-muted">
          Ampara lo que salió de la bodega. Las recepciones parciales y las diferencias no la
          cambian.
        </p>
      {/if}
    {:else}
      <p class="text-sm text-foreground-muted">
        Este traslado salió sin nota de remisión: se despachó antes de habilitarla.
      </p>
    {/if}
    {#if actionError}
      <p class="text-sm text-danger" role="alert">{actionError}</p>
    {/if}
  </section>
{/if}
