<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseOrdersApi } from '$lib/api/purchase-orders';
  import { suppliersApi } from '$lib/api/suppliers';
  import type { PurchaseOrder, PurchaseOrderStatus } from '$lib/types/purchase-order';
  import type { Supplier } from '$lib/types/supplier';

  const STATUS_OPTIONS: { value: PurchaseOrderStatus; label: string }[] = [
    { value: 'draft', label: 'Borrador' },
    { value: 'pending_approval', label: 'Pendiente de aprobación' },
    { value: 'approved', label: 'Aprobada' },
    { value: 'sent', label: 'Enviada' },
    { value: 'partially_received', label: 'Parcialmente recibida' },
    { value: 'received', label: 'Recibida' },
    { value: 'cancelled', label: 'Cancelada' },
    { value: 'closed', label: 'Cerrada' }
  ];

  let items = $state<PurchaseOrder[]>([]);
  let suppliers = $state<Supplier[]>([]);
  let statusFilter = $state<PurchaseOrderStatus | ''>('');
  let supplierFilter = $state('');
  let page = $state(1);
  let total = $state(0);
  let pages = $state(0);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let suppliersError = $state<string | null>(null);
  let requestSequence = 0;

  let supplierNames = $derived(
    new Map(suppliers.map((supplier) => [supplier.id_supplier, supplier.name]))
  );

  function errorMessage(cause: unknown, fallback: string): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return fallback;
  }

  function statusLabel(status: PurchaseOrderStatus): string {
    return STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status;
  }

  function supplierLabel(id: number): string {
    return supplierNames.get(id) ?? `Proveedor #${id}`;
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

  function formatMoney(value: string, currency: string): string {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return value;
    return new Intl.NumberFormat('es-SV', {
      style: 'currency',
      currency
    }).format(amount);
  }

  function handleStatusChange(event: Event) {
    statusFilter = (event.currentTarget as HTMLSelectElement).value as PurchaseOrderStatus | '';
    page = 1;
  }

  function handleSupplierChange(event: Event) {
    supplierFilter = (event.currentTarget as HTMLSelectElement).value;
    page = 1;
  }

  async function loadSuppliers() {
    suppliersError = null;
    try {
      const response = await suppliersApi.listSuppliers({
        active_only: false,
        page: 1,
        size: 100
      });
      suppliers = response.items;
    } catch (cause: unknown) {
      suppliersError = errorMessage(cause, 'No se pudieron cargar los proveedores.');
    }
  }

  async function loadOrders(
    currentStatus: PurchaseOrderStatus | '',
    currentSupplier: string,
    currentPage: number
  ) {
    const sequence = ++requestSequence;
    loading = true;
    error = null;

    try {
      const response = await purchaseOrdersApi.list({
        status: currentStatus || undefined,
        supplier_id: currentSupplier ? Number(currentSupplier) : undefined,
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
      error = errorMessage(cause, 'No se pudieron cargar las órdenes de compra.');
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  function retry() {
    void loadOrders(statusFilter, supplierFilter, page);
  }

  function emptyAction() {
    if (statusFilter || supplierFilter) {
      statusFilter = '';
      supplierFilter = '';
      page = 1;
      return;
    }
    retry();
  }

  $effect(() => {
    void loadSuppliers();
  });

  $effect(() => {
    const currentStatus = statusFilter;
    const currentSupplier = supplierFilter;
    const currentPage = page;
    void loadOrders(currentStatus, currentSupplier, currentPage);
  });
</script>

<section class="space-y-5">
  <header class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <p class="text-sm font-medium text-primary">Compras</p>
      <h1 class="text-2xl font-semibold tracking-tight text-foreground">Órdenes de compra</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Consulta las órdenes generadas desde cotizaciones seleccionadas y su estado operativo.
      </p>
    </div>
    <p class="text-sm text-foreground-muted">
      {total}
      {total === 1 ? 'orden' : 'órdenes'}
    </p>
  </header>

  <div class="grid gap-3 rounded-xl border border-border bg-surface p-4 md:grid-cols-2">
    <label class="space-y-1.5 text-sm font-medium text-foreground">
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

    <label class="space-y-1.5 text-sm font-medium text-foreground">
      <span>Proveedor</span>
      <select
        aria-label="Proveedor"
        value={supplierFilter}
        onchange={handleSupplierChange}
        disabled={suppliers.length === 0}
        class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
      >
        <option value="">Todos los proveedores</option>
        {#each suppliers as supplier (supplier.id_supplier)}
          <option value={String(supplier.id_supplier)}>{supplier.code} — {supplier.name}</option>
        {/each}
      </select>
      {#if suppliersError}
        <span class="block text-xs text-danger">{suppliersError}</span>
      {/if}
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
      <div class="space-y-3 p-4" aria-label="Cargando órdenes de compra">
        {#each Array(5) as _}
          <div class="grid grid-cols-6 gap-3">
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
      <h2 class="font-medium text-foreground">No hay órdenes para mostrar</h2>
      <p class="mt-1 max-w-md text-sm text-foreground-muted">
        Las órdenes se generan desde cotizaciones seleccionadas. Ajusta los filtros si esperabas ver
        una orden existente.
      </p>
      <Button class="mt-4" size="sm" variant="secondary" onclick={emptyAction}>
        {statusFilter || supplierFilter ? 'Limpiar filtros' : 'Actualizar'}
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
            <th class="px-4 py-3 font-medium">Proveedor</th>
            <th class="px-4 py-3 font-medium">Fecha orden</th>
            <th class="px-4 py-3 font-medium">Fecha esperada</th>
            <th class="px-4 py-3 font-medium">Total</th>
            <th class="px-4 py-3 font-medium">Estado</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border">
          {#each items as item (item.id)}
            <tr class="text-foreground">
              <td class="whitespace-nowrap px-4 py-3 font-medium">
                <a href={`/purchase-orders/${item.id}`} class="text-primary hover:underline">
                  {item.code}
                </a>
              </td>
              <td class="px-4 py-3">{supplierLabel(item.supplier_id)}</td>
              <td class="whitespace-nowrap px-4 py-3 text-foreground-muted">
                {formatDate(item.order_date)}
              </td>
              <td class="whitespace-nowrap px-4 py-3 text-foreground-muted">
                {formatDate(item.expected_date)}
              </td>
              <td class="whitespace-nowrap px-4 py-3">
                {formatMoney(item.total, item.currency)}
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
