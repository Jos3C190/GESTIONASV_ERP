<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import type {
    InventoryTransfer,
    TransferStatus
  } from '$lib/features/inventory/transfer-documents';
  import { transferStatusLabel } from '$lib/features/inventory/transfer-operations';
  import TransferRouteBadge from './TransferRouteBadge.svelte';

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
    /** Shows the "Todos / Por aprobar" switch to people who can approve. */
    canApprove?: boolean;
    awaitingApproval?: boolean;
    pendingApprovalCount?: number;
    onAwaitingApproval?: (value: boolean) => void;
    /** Only transfers with a shortage or surplus not yet counted at the origin warehouse. */
    originCountPending?: boolean;
    onOriginCountPending?: (value: boolean) => void;
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
    canApprove = false,
    awaitingApproval = false,
    pendingApprovalCount = 0,
    onAwaitingApproval,
    originCountPending = false,
    onOriginCountPending,
    formatDate,
    documentSummary,
    onFilter,
    onRetry,
    onOpen,
    onLoadMore
  }: Props = $props();

  const STATUS_TONE: Record<string, string> = {
    in_transit: 'border-primary/30 bg-primary/10 text-primary',
    approved: 'border-primary/30 bg-primary/10 text-primary',
    incident: 'border-warning/30 bg-warning/10 text-warning',
    partially_received: 'border-warning/30 bg-warning/10 text-warning',
    discrepancy: 'border-warning/30 bg-warning/10 text-warning',
    pending_approval: 'border-warning/30 bg-warning/10 text-warning',
    received: 'border-success/30 bg-success/10 text-success'
  };
  const NEUTRAL_TONE = 'border-border bg-surface-muted text-foreground-muted';
  const scopeOptions = $derived([
    { value: false, label: 'Todos' },
    { value: true, label: `Por aprobar (${pendingApprovalCount})` }
  ]);
</script>

<section class="space-y-5" aria-labelledby="documents-heading">
  <div class="flex flex-wrap items-end justify-between gap-3">
    <div>
      <h2 id="documents-heading" class="text-lg font-semibold text-foreground">
        Documentos de traslado
      </h2>
      <p class="mt-1 text-sm text-foreground-muted">
        La lista respeta el alcance de empresa y sucursal del servidor.
      </p>
    </div>
    <div class="flex w-full flex-wrap items-end gap-3 sm:w-auto">
      {#if canApprove}
        <div
          class="flex max-w-full flex-wrap gap-1 rounded-lg border border-border bg-surface-muted p-1"
          role="group"
          aria-label="Qué documentos mostrar"
        >
          {#each scopeOptions as option (option.label)}
            <button
              type="button"
              class="min-h-10 rounded-md px-3 text-xs font-medium transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50 {awaitingApproval ===
              option.value
                ? 'bg-surface-elevated text-foreground shadow-soft'
                : 'text-foreground-muted'}"
              aria-pressed={awaitingApproval === option.value}
              disabled={busy}
              onclick={() => onAwaitingApproval?.(option.value)}>{option.label}</button
            >
          {/each}
        </div>
      {/if}
    <label class="min-w-52 flex-1 space-y-1 text-sm font-medium text-foreground sm:flex-none">
      Estado
      <select
        class="w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
        disabled={busy || awaitingApproval}
        value={awaitingApproval ? 'pending_approval' : filter}
        onchange={(event) => onFilter(event.currentTarget.value)}
      >
        {#each statuses as status (status.value)}<option value={status.value}>{status.label}</option
          >{/each}
      </select>
    </label>
    <label
      class="flex min-h-10 items-center gap-2 rounded-lg border border-border bg-surface-muted px-3 text-xs font-medium text-foreground"
    >
      <input
        type="checkbox"
        class="size-4"
        checked={originCountPending}
        disabled={busy || awaitingApproval}
        onchange={(event) => onOriginCountPending?.(event.currentTarget.checked)}
      />
      Conteo pendiente en origen
    </label>
    </div>
  </div>

  {#if error}<div
      class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      No se pudo confirmar el listado de documentos. {error}
    </div>{/if}
  {#if state === 'loading'}
    <div
      class="rounded-2xl border border-border bg-surface p-6 text-sm text-foreground-muted"
      role="status"
    >
      Consultando documentos…
    </div>
  {:else if state === 'error'}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      No se interpreta un error de consulta como una lista vacía.
      <button class="underline" type="button" onclick={onRetry}>Reintentar</button>
    </div>
  {:else if transfers.length === 0}
    <div class="rounded-2xl border border-border border-dashed bg-surface p-8 text-center">
      {#if awaitingApproval}
        <p class="font-medium text-foreground">No tienes traslados por aprobar</p>
        <p class="mt-1 text-sm text-foreground-muted">
          Cuando alguien envíe un traslado de tus sucursales a aprobación, aparecerá aquí.
        </p>
      {:else}
        <p class="font-medium text-foreground">
          {originCountPending ? 'Ningún traslado espera un conteo en origen' : 'No hay documentos en este estado'}
        </p>
        <p class="mt-1 text-sm text-foreground-muted">
          Al guardar una preparación aparecerá aquí sin mover existencias.
        </p>
      {/if}
    </div>
  {:else}
    <div class="grid gap-3 xl:grid-cols-2">
      {#each transfers as transfer (transfer.id)}
        <div class="relative">
          <button
            class="w-full rounded-2xl border border-border bg-surface p-4 text-left transition-colors hover:border-primary/40 hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
            type="button"
            disabled={busy}
            onclick={() => onOpen(transfer.id)}
          >
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p class="font-mono text-sm font-semibold text-primary">{transfer.code}</p>
                <p class="mt-1 font-medium text-foreground">
                  {transfer.origin_warehouse_name} → {transfer.destination_warehouse_name}
                </p>
              </div>
              <div class="flex flex-wrap items-center justify-end gap-1.5">
                {#if transfer.route_type && transfer.route_type !== 'central_distribution'}
                  <TransferRouteBadge route={transfer.route_type} />
                {/if}
                <span
                  class="inline-flex rounded-full border px-2.5 py-1 text-xs font-medium {STATUS_TONE[
                    transfer.status
                  ] ?? NEUTRAL_TONE}"
                  data-status={transfer.status}>{transferStatusLabel(transfer.status)}</span
                >
                {#if transfer.origin_count_pending}
                  <span
                    class="inline-flex rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary"
                    >Conteo pendiente en origen</span
                  >
                {/if}
              </div>
            </div>
            <p class="mt-3 text-sm text-foreground-muted">{documentSummary(transfer)}</p>
            <p class="mt-3 text-xs text-foreground-muted">
              Creado {formatDate(transfer.created_at)}{transfer.vehicle
                ? ` · ${transfer.vehicle.code} ${transfer.vehicle.name}`
                : ''}
            </p>
          </button>
          {#if transfer.status === 'in_transit' || transfer.status === 'partially_received' || transfer.status === 'incident'}
            <a
              class="absolute bottom-3 right-4 inline-flex items-center gap-1 rounded-lg border border-primary/30 bg-surface px-2.5 py-1 text-xs font-medium text-primary hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              href={`/tracking?transfer=${transfer.id}`}>Ver en mapa</a
            >
          {/if}
        </div>
      {/each}
    </div>
    {#if hasMore}
      <div class="text-center">
        <Button variant="secondary" disabled={loadingMore || busy} onclick={onLoadMore}
          >{loadingMore ? 'Cargando…' : 'Cargar más documentos'}</Button
        >
      </div>
    {/if}
  {/if}
</section>
