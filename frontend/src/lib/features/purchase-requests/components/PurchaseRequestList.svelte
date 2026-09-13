<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseRequestsApi } from '$lib/api/purchase-requests';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { PurchaseRequest, PurchaseRequestStatus } from '$lib/types/purchase-request';

  const statusOptions: Array<{ value: '' | PurchaseRequestStatus; label: string }> = [
    { value: '', label: 'Todos los estados' },
    { value: 'draft', label: 'Borrador' },
    { value: 'submitted', label: 'Enviada' },
    { value: 'approved', label: 'Aprobada' },
    { value: 'rejected', label: 'Rechazada' },
    { value: 'partially_quoted', label: 'Parcialmente cotizada' },
    { value: 'quoted', label: 'Cotizada' },
    { value: 'partially_ordered', label: 'Parcialmente ordenada' },
    { value: 'completed', label: 'Completada' },
    { value: 'cancelled', label: 'Cancelada' }
  ];

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

  let items = $state<PurchaseRequest[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let selectedStatus = $state<'' | PurchaseRequestStatus>('');
  let page = $state(1);
  let totalPages = $state(0);
  let totalItems = $state(0);
  let requestGeneration = 0;

  async function loadData(
    status: '' | PurchaseRequestStatus = selectedStatus,
    currentPage: number = page
  ) {
    const generation = ++requestGeneration;
    loading = true;
    error = null;

    try {
      const response = await purchaseRequestsApi.list({
        status: status || undefined,
        page: currentPage,
        size: 20
      });

      if (generation !== requestGeneration) return;

      items = response.items;
      totalPages = response.meta.pages;
      totalItems = response.meta.total;
    } catch (err: unknown) {
      if (generation !== requestGeneration) return;

      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudieron cargar las solicitudes de compra.';
      items = [];
      totalPages = 0;
      totalItems = 0;
    } finally {
      if (generation === requestGeneration) loading = false;
    }
  }

  $effect(() => {
    void loadData(selectedStatus, page);
  });

  function changeStatus(event: Event) {
    selectedStatus = (event.currentTarget as HTMLSelectElement).value as '' | PurchaseRequestStatus;
    page = 1;
  }

  function pageTo(nextPage: number) {
    if (nextPage < 1 || nextPage > totalPages || nextPage === page) return;
    page = nextPage;
  }

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
  <header
    class="mb-5 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center sm:gap-4"
  >
    <div>
      <h1 class="text-xl font-semibold text-foreground">Solicitudes de compra</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        {totalItems} solicitud(es) registradas
      </p>
    </div>

    <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto">
      <select
        aria-label="Filtrar por estado"
        value={selectedStatus}
        onchange={changeStatus}
        class="h-9 rounded-md border border-border bg-surface px-3 text-xs font-medium text-foreground focus:border-primary focus:outline-none"
      >
        {#each statusOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>

      {#if permissions.hasPermission('purchase_requests:manage')}
        <Button size="sm" onclick={() => goto('/purchase-requests/new')}>Nueva solicitud</Button>
      {/if}
    </div>
  </header>

  {#if error}
    <div
      class="mb-4 flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{error}</span>
      <Button size="sm" variant="secondary" onclick={() => void loadData()}>Reintentar</Button>
    </div>
  {/if}

  <Card class="overflow-hidden p-0">
    {#if loading}
      <div class="space-y-3 p-4" aria-label="Cargando solicitudes de compra">
        {#each Array(5) as _}
          <div class="skeleton h-12 w-full rounded-md"></div>
        {/each}
      </div>
    {:else if items.length === 0}
      <div class="flex flex-col items-center justify-center px-6 py-16 text-center">
        <div
          class="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-surface-muted text-foreground-muted"
          aria-hidden="true"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path
              d="M9 12h6M9 16h6M7 3h5.586a1 1 0 01.707.293l3.414 3.414A1 1 0 0117 7.414V21H7z"
            />
          </svg>
        </div>
        <p class="text-sm font-medium text-foreground">No hay solicitudes para mostrar</p>
        <p class="mt-1 max-w-md text-xs text-foreground-muted">
          Ajusta el filtro de estado o vuelve a cargar la información.
        </p>
        <Button class="mt-4" size="sm" variant="secondary" onclick={() => void loadData()}>
          Recargar
        </Button>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full min-w-[820px] text-sm">
          <thead class="border-b border-border bg-surface-muted">
            <tr>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Código</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Estado</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Fecha solicitud</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Fecha requerida</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Justificación</th>
              <th class="px-4 py-3 text-right font-semibold text-foreground">Líneas</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each items as item (item.id)}
              <tr class="hover:bg-surface-muted">
                <td class="px-4 py-3 font-mono text-xs font-medium text-foreground">
                  <a
                    href={`/purchase-requests/${item.id}`}
                    class="hover:text-primary hover:underline"
                  >
                    {item.code}
                  </a>
                </td>
                <td class="px-4 py-3 text-foreground-muted">{statusLabels[item.status]}</td>
                <td class="px-4 py-3 text-foreground-muted">{formatDate(item.request_date)}</td>
                <td class="px-4 py-3 text-foreground-muted">{formatDate(item.required_date)}</td>
                <td class="max-w-sm truncate px-4 py-3 text-foreground-muted">
                  {item.justification}
                </td>
                <td class="px-4 py-3 text-right font-mono text-foreground">
                  {item.details.length}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div
        class="flex flex-col gap-3 border-t border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
      >
        <p class="text-xs text-foreground-muted">
          Página {page} de {totalPages}
        </p>
        <div class="flex gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={page <= 1}
            onclick={() => pageTo(page - 1)}
          >
            Anterior
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={page >= totalPages}
            onclick={() => pageTo(page + 1)}
          >
            Siguiente
          </Button>
        </div>
      </div>
    {/if}
  </Card>
</div>
