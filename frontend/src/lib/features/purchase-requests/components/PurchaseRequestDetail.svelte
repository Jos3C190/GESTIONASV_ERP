<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import PurchaseRequestActions from '$lib/features/purchase-requests/components/PurchaseRequestActions.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseRequestsApi } from '$lib/api/purchase-requests';
  import type { PurchaseRequest, PurchaseRequestStatus } from '$lib/types/purchase-request';

  let { requestId }: { requestId: string } = $props();

  const statusLabels: Record<PurchaseRequestStatus, string> = {
    draft: 'Borrador',
    submitted: 'Enviada',
    approved: 'Aprobada',
    rejected: 'Rechazada',
    partially_quoted: 'Parcialmente cotizada',
    quoted: 'Cotizada',
    partially_ordered: 'Parcialmente ordenada',
    completed: 'Completada',
    cancelled: 'Cancelada'
  };

  let item = $state<PurchaseRequest | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let generation = 0;

  async function loadData(id: string) {
    const currentGeneration = ++generation;
    loading = true;
    error = null;

    try {
      const response = await purchaseRequestsApi.get(id);
      if (currentGeneration !== generation) return;
      item = response;
    } catch (err: unknown) {
      if (currentGeneration !== generation) return;
      item = null;
      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudo cargar la solicitud de compra.';
    } finally {
      if (currentGeneration === generation) loading = false;
    }
  }

  $effect(() => {
    if (requestId) void loadData(requestId);
  });

  function formatDate(value: string | null) {
    if (!value) return '—';
    return new Intl.DateTimeFormat('es-SV', {
      timeZone: 'America/El_Salvador',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    }).format(new Date(value));
  }
</script>

<div class="min-h-full bg-background px-4 pb-8 pt-4 sm:px-6 sm:pt-6 md:px-8 md:pt-8">
  <header class="mb-6 flex items-center gap-3 border-b border-border pb-4">
    <a
      href="/purchase-requests"
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-muted hover:text-foreground"
      aria-label="Volver a solicitudes de compra"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <path d="M19 12H5M12 19l-7-7 7-7" />
      </svg>
    </a>
    <div class="min-w-0 flex-1">
      <h1 class="text-xl font-semibold text-foreground">Detalle de solicitud de compra</h1>
      <p class="mt-1 text-sm text-foreground-muted">Información registrada y líneas solicitadas.</p>
    </div>
  </header>

  {#if loading}
    <div class="space-y-4" aria-label="Cargando detalle de solicitud">
      <div class="skeleton h-32 rounded-xl"></div>
      <div class="skeleton h-64 rounded-xl"></div>
    </div>
  {:else if error}
    <div
      class="flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{error}</span>
      <Button size="sm" variant="secondary" onclick={() => void loadData(requestId)}>
        Reintentar
      </Button>
    </div>
  {:else if item}
    <div class="space-y-5">
      <PurchaseRequestActions {item} onupdated={(updated) => (item = updated)} />

      <Card class="p-5">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p class="font-mono text-xs text-foreground-muted">{item.code}</p>
            <h2 class="mt-1 text-lg font-semibold text-foreground">{item.justification}</h2>
            {#if item.notes}
              <p class="mt-2 text-sm text-foreground-muted">{item.notes}</p>
            {/if}
          </div>
          <span
            class="inline-flex w-fit rounded-md bg-surface-muted px-2.5 py-1 text-xs font-medium text-foreground"
          >
            {statusLabels[item.status]}
          </span>
        </div>

        <dl class="mt-5 grid gap-4 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt class="text-xs text-foreground-muted">Fecha de solicitud</dt>
            <dd class="mt-1 text-sm font-medium text-foreground">
              {formatDate(item.request_date)}
            </dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">Fecha requerida</dt>
            <dd class="mt-1 text-sm font-medium text-foreground">
              {formatDate(item.required_date)}
            </dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">Sucursal</dt>
            <dd class="mt-1 break-all font-mono text-xs text-foreground">{item.branch_id}</dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">Almacén</dt>
            <dd class="mt-1 break-all font-mono text-xs text-foreground">{item.warehouse_id}</dd>
          </div>
        </dl>
      </Card>

      <Card class="overflow-hidden p-0">
        <div class="border-b border-border px-4 py-3">
          <h2 class="text-sm font-semibold text-foreground">Detalle solicitado</h2>
          <p class="mt-1 text-xs text-foreground-muted">{item.details.length} línea(s)</p>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full min-w-[760px] text-sm">
            <thead class="border-b border-border bg-surface-muted">
              <tr>
                <th class="px-4 py-3 text-left font-semibold text-foreground">Producto ID</th>
                <th class="px-4 py-3 text-left font-semibold text-foreground">Unidad ID</th>
                <th class="px-4 py-3 text-right font-semibold text-foreground">Cantidad</th>
                <th class="px-4 py-3 text-left font-semibold text-foreground">Descripción</th>
                <th class="px-4 py-3 text-left font-semibold text-foreground">Notas</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              {#each item.details as detail (detail.id)}
                <tr>
                  <td class="px-4 py-3 font-mono text-xs text-foreground">{detail.product_id}</td>
                  <td class="px-4 py-3 font-mono text-xs text-foreground">{detail.unit_id}</td>
                  <td class="px-4 py-3 text-right font-mono text-foreground">{detail.quantity}</td>
                  <td class="px-4 py-3 text-foreground-muted">{detail.description || '—'}</td>
                  <td class="px-4 py-3 text-foreground-muted">{detail.notes || '—'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  {/if}
</div>
