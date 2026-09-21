<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { retaceosApi } from '$lib/api/retaceos';
  import { branch } from '$lib/stores/branch.svelte';
  import type { Retaceo, RetaceoStatus } from '$lib/types/retaceo';

  const STATUS_OPTIONS: { value: RetaceoStatus; label: string }[] = [
    { value: 'draft', label: 'Borrador' },
    { value: 'calculated', label: 'Calculado' },
    { value: 'verified', label: 'Verificado' },
    { value: 'closed', label: 'Cerrado' },
    { value: 'cancelled', label: 'Cancelado' }
  ];

  let items = $state<Retaceo[]>([]);
  let statusFilter = $state<RetaceoStatus | ''>('');
  let page = $state(1);
  let total = $state(0);
  let pages = $state(0);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let requestSequence = 0;

  function errorMessage(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;

    return 'No se pudieron cargar los retaceos.';
  }

  function statusLabel(status: RetaceoStatus): string {
    return STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status;
  }

  function formatMoney(value: string | number, currency: string): string {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return String(value);

    return new Intl.NumberFormat('es-SV', {
      style: 'currency',
      currency
    }).format(amount);
  }

  function formatDate(value: string | null): string {
    if (!value) return '—';

    return new Intl.DateTimeFormat('es-SV', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      timeZone: 'America/El_Salvador'
    }).format(new Date(value));
  }

  function purchaseReference(purchaseId: string): string {
    return `${purchaseId.slice(0, 8)}…`;
  }

  function handleStatusChange(event: Event) {
    statusFilter = (event.currentTarget as HTMLSelectElement).value as RetaceoStatus | '';
    page = 1;
  }

  async function loadRetaceos(
    currentStatus: RetaceoStatus | '',
    currentPage: number,
    currentBranchId: string | null
  ) {
    const sequence = ++requestSequence;
    loading = true;
    error = null;

    try {
      const response = await retaceosApi.list({
        status: currentStatus || undefined,
        branch_id: currentBranchId ?? undefined,
        page: currentPage,
        size: 20
      });

      if (sequence !== requestSequence) return;

      items = response.items;
      total = response.meta.total;
      pages = response.meta.pages;
    } catch (cause: unknown) {
      if (sequence !== requestSequence) return;

      items = [];
      total = 0;
      pages = 0;
      error = errorMessage(cause);
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  function retry() {
    if (!branch.ready) return;
    void loadRetaceos(statusFilter, page, branch.id);
  }

  function emptyAction() {
    if (statusFilter) {
      statusFilter = '';
      page = 1;
      return;
    }

    retry();
  }

  $effect(() => {
    const ready = branch.ready;
    const currentBranchId = branch.id;
    const currentStatus = statusFilter;
    const currentPage = page;

    if (!ready) {
      loading = true;
      return;
    }

    void loadRetaceos(currentStatus, currentPage, currentBranchId);
  });
</script>

<section class="space-y-5">
  <header class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <p class="text-sm font-medium text-primary">Compras</p>
      <h1 class="text-2xl font-semibold tracking-tight text-foreground">Retaceo de importación</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Consulta la distribución de flete, gastos y DAI aplicada sobre compras recibidas.
      </p>
    </div>

    <p class="text-sm text-foreground-muted">
      {total}
      {total === 1 ? 'retaceo' : 'retaceos'}
    </p>
  </header>

  <div class="rounded-xl border border-border bg-surface p-4">
    <label class="block max-w-sm space-y-1.5 text-sm font-medium text-foreground">
      <span>Estado</span>

      <select
        aria-label="Estado"
        value={statusFilter}
        onchange={handleStatusChange}
        class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
      >
        <option value="">Todos los estados</option>

        {#each STATUS_OPTIONS as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </label>
  </div>

  {#if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span>{error}</span>
        <Button size="sm" variant="secondary" onclick={retry}>Reintentar</Button>
      </div>
    </div>
  {:else if loading}
    <div class="overflow-hidden rounded-xl border border-border bg-surface">
      <div class="space-y-3 p-4" aria-label="Cargando retaceos">
        {#each Array(5) as _}
          <div class="grid grid-cols-6 gap-3">
            <div class="skeleton h-5 rounded"></div>
            <div class="skeleton h-5 rounded"></div>
            <div class="skeleton h-5 rounded"></div>
            <div class="skeleton h-5 rounded"></div>
            <div class="skeleton h-5 rounded"></div>
            <div class="skeleton h-5 rounded"></div>
            <div class="skeleton h-5 rounded"></div>
          </div>
        {/each}
      </div>
    </div>
  {:else if items.length === 0}
    <div
      class="flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface px-6 text-center"
    >
      <div
        class="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-surface-muted text-foreground-muted"
        aria-hidden="true"
      >
        <span class="text-lg">∅</span>
      </div>

      <h2 class="font-medium text-foreground">No hay retaceos para mostrar</h2>

      <p class="mt-1 max-w-md text-sm text-foreground-muted">
        Los retaceos se generan desde compras recibidas, verificadas o cerradas. Ajusta el filtro si
        esperabas encontrar un registro existente.
      </p>

      <Button class="mt-4" size="sm" variant="secondary" onclick={emptyAction}>
        {statusFilter ? 'Limpiar filtro' : 'Actualizar'}
      </Button>
    </div>
  {:else}
    <div class="overflow-x-auto rounded-xl border border-border bg-surface">
      <table class="min-w-full divide-y divide-border text-sm">
        <thead
          class="bg-surface-muted text-left text-xs uppercase tracking-wide text-foreground-muted"
        >
          <tr>
            <th class="px-4 py-3 font-medium">Código</th>
            <th class="px-4 py-3 font-medium">Compra origen</th>
            <th class="px-4 py-3 font-medium">FOB</th>
            <th class="px-4 py-3 font-medium">Costo total</th>
            <th class="px-4 py-3 font-medium">IVA importación</th>
            <th class="px-4 py-3 font-medium">Estado</th>
          </tr>
        </thead>

        <tbody class="divide-y divide-border">
          {#each items as item (item.id)}
            <tr class="text-foreground">
              <td class="whitespace-nowrap px-4 py-3 font-medium">
                <a href={`/retaceos/${item.id}`} class="text-primary hover:underline">
                  {item.code}
                </a>

                <p class="mt-1 text-xs font-normal text-foreground-muted">
                  {formatDate(item.created_at)}
                </p>
              </td>

              <td class="whitespace-nowrap px-4 py-3">
                <a
                  href={`/purchases/${item.purchase_id}`}
                  class="font-medium text-primary hover:underline"
                >
                  Abrir compra
                </a>

                <p class="mt-1 text-xs text-foreground-muted">
                  {purchaseReference(item.purchase_id)}
                </p>
              </td>

              <td class="whitespace-nowrap px-4 py-3">
                {formatMoney(item.total_fob, item.currency)}
              </td>

              <td class="whitespace-nowrap px-4 py-3 font-medium">
                {formatMoney(item.total_cost, item.currency)}
              </td>

              <td class="whitespace-nowrap px-4 py-3 text-foreground-muted">
                {formatMoney(item.import_vat, item.currency)}
              </td>

              <td class="whitespace-nowrap px-4 py-3">
                <span
                  class="inline-flex rounded-full border border-border bg-surface-muted px-2.5 py-1 text-xs font-medium text-foreground"
                >
                  {statusLabel(item.status)}
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <footer class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <p class="text-sm text-foreground-muted">
        Página {page} de {Math.max(pages, 1)}
      </p>

      <div class="flex gap-2">
        <Button
          size="sm"
          variant="secondary"
          disabled={loading || page <= 1}
          onclick={() => (page -= 1)}
        >
          Anterior
        </Button>

        <Button
          size="sm"
          variant="secondary"
          disabled={loading || pages === 0 || page >= pages}
          onclick={() => (page += 1)}
        >
          Siguiente
        </Button>
      </div>
    </footer>
  {/if}
</section>
