<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import type { InventoryTransfer, TransferStatus } from '$lib/features/inventory/transfer-documents';
  import { transferStatusLabel } from '$lib/features/inventory/transfer-operations';

  type CollectionState = 'loading' | 'loaded' | 'empty' | 'error';
  interface StatusOption {
    value: TransferStatus | '';
    label: string;
  }

  interface Props {
    transfers: InventoryTransfer[];
    state: CollectionState;
    error: string | null;
    filter: TransferStatus | '';
    statuses: StatusOption[];
    hasMore: boolean;
    loadingMore: boolean;
    busy?: boolean;
    formatDate: (value: string | null | undefined) => string;
    documentSummary: (transfer: InventoryTransfer) => string;
    onFilter: (value: string) => void;
    onRetry: () => void;
    onOpen: (transferId: string) => void;
    onLoadMore: () => void;
  }

  let {
    transfers,
    state,
    error,
    filter,
    statuses,
    hasMore,
    loadingMore,
    busy = false,
    formatDate,
    documentSummary,
    onFilter,
    onRetry,
    onOpen,
    onLoadMore
  }: Props = $props();
</script>

<section class="space-y-5" aria-labelledby="documents-heading">
  <div class="flex flex-wrap items-end justify-between gap-3">
    <div>
      <h2 id="documents-heading" class="text-lg font-semibold text-foreground">Documentos de traslado</h2>
      <p class="mt-1 text-sm text-foreground-muted">La lista respeta el alcance de empresa y sucursal del servidor.</p>
    </div>
    <label class="min-w-52 space-y-1 text-sm font-medium text-foreground">
      Estado
      <select class="w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" disabled={busy} value={filter} onchange={(event) => onFilter(event.currentTarget.value)}>
        {#each statuses as status (status.value)}<option value={status.value}>{status.label}</option>{/each}
      </select>
    </label>
  </div>

  {#if error}<div class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">No se pudo confirmar el listado de documentos. {error}</div>{/if}
  {#if state === 'loading'}
    <div class="rounded-2xl border border-border bg-surface p-6 text-sm text-foreground-muted" role="status">Consultando documentos…</div>
  {:else if state === 'error'}
    <div class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">
      No se interpreta un error de consulta como una lista vacía.
      <button class="underline" type="button" onclick={onRetry}>Reintentar</button>
    </div>
  {:else if transfers.length === 0}
    <div class="rounded-2xl border border-border border-dashed bg-surface p-8 text-center">
      <p class="font-medium text-foreground">No hay documentos en este estado</p>
      <p class="mt-1 text-sm text-foreground-muted">Al guardar una preparación aparecerá aquí sin mover existencias.</p>
    </div>
  {:else}
    <div class="grid gap-3 xl:grid-cols-2">
      {#each transfers as transfer (transfer.id)}
        <button class="rounded-2xl border border-border bg-surface p-4 text-left transition-colors hover:border-primary/40 hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50" type="button" disabled={busy} onclick={() => onOpen(transfer.id)}>
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p class="font-mono text-sm font-semibold text-primary">{transfer.code}</p>
              <p class="mt-1 font-medium text-foreground">{transfer.origin_warehouse_name} → {transfer.destination_warehouse_name}</p>
            </div>
            <span class="inline-flex rounded-full border px-2.5 py-1 text-xs font-medium {transfer.status === 'in_transit' ? 'border-primary/30 bg-primary/10 text-primary' : transfer.status === 'incident' ? 'border-warning/30 bg-warning/10 text-warning' : transfer.status === 'received' ? 'border-success/30 bg-success/10 text-success' : 'border-border bg-surface-muted text-foreground-muted'}" data-status={transfer.status}>{transferStatusLabel(transfer.status)}</span>
          </div>
          <p class="mt-3 text-sm text-foreground-muted">{documentSummary(transfer)}</p>
          <p class="mt-3 text-xs text-foreground-muted">Creado {formatDate(transfer.created_at)}{transfer.vehicle ? ` · ${transfer.vehicle.code} ${transfer.vehicle.name}` : ''}</p>
        </button>
      {/each}
    </div>
    {#if hasMore}
      <div class="text-center">
        <Button variant="secondary" disabled={loadingMore || busy} onclick={onLoadMore}>{loadingMore ? 'Cargando…' : 'Cargar más documentos'}</Button>
      </div>
    {/if}
  {/if}
</section>

