<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchaseOrdersApi } from '$lib/api/purchase-orders';
  import { purchasesApi } from '$lib/api/purchases';
  import { suppliersApi } from '$lib/api/suppliers';
  import PurchaseWorkflowActions from '$lib/features/purchases/components/PurchaseWorkflowActions.svelte';
  import { getWarehouse } from '$lib/services/warehouses';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Purchase, PurchaseStatus } from '$lib/types/purchase';

  let { id }: { id: string } = $props();

  const STATUS_LABELS: Record<PurchaseStatus, string> = {
    draft: 'Borrador',
    received: 'Recibida',
    verified: 'Verificada',
    cancelled: 'Cancelada',
    closed: 'Cerrada'
  };

  let item = $state<Purchase | null>(null);
  let supplierLabel = $state('');
  let branchLabel = $state('');
  let warehouseLabel = $state('');
  let orderLabel = $state('');
  let productLabels = $state<Map<number, string>>(new Map());
  let unitLabels = $state<Map<number, string>>(new Map());
  let loading = $state(true);
  let error = $state<string | null>(null);
  let requestSequence = 0;

  let canManageRetaceo = $derived(permissions.hasPermission('retaceos:manage'));
  let canCreateRetaceo = $derived(
    canManageRetaceo &&
      item !== null &&
      (item.status === 'received' || item.status === 'verified' || item.status === 'closed')
  );

  function errorMessage(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;

    return 'No se pudo cargar la compra.';
  }

  function formatDate(value: string | null): string {
    if (!value) return '—';

    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      const [year, month, day] = value.split('-');
      return `${day}/${month}/${year}`;
    }

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

  function formatQuantity(value: string): string {
    const quantity = Number(value);
    if (!Number.isFinite(quantity)) return value;

    return new Intl.NumberFormat('es-SV', {
      maximumFractionDigits: 6
    }).format(quantity);
  }

  function productLabel(id: number): string {
    return productLabels.get(id) ?? `Producto #${id}`;
  }

  function unitLabel(id: number): string {
    return unitLabels.get(id) ?? `Unidad #${id}`;
  }

  function handleUpdated(updated: Purchase) {
    item = updated;
  }

  async function load(currentId: string) {
    const sequence = ++requestSequence;
    loading = true;
    error = null;

    try {
      const purchase = await purchasesApi.get(currentId);
      if (sequence !== requestSequence) return;

      item = purchase;

      const productIds = [...new Set(purchase.details.map((detail) => detail.product_id))];

      const [supplier, order, warehouse, units, products] = await Promise.all([
        suppliersApi.getSupplier(purchase.supplier_id).catch(() => null),
        purchaseOrdersApi.get(purchase.purchase_order_id).catch(() => null),
        getWarehouse(purchase.warehouse_id).catch(() => null),
        catalogApi.listUnits(false).catch(() => []),
        Promise.all(
          productIds.map((productId) => catalogApi.getProduct(productId).catch(() => null))
        )
      ]);

      if (sequence !== requestSequence) return;

      supplierLabel = supplier?.code
        ? `${supplier.code} — ${supplier.name}`
        : (supplier?.name ?? `Proveedor #${purchase.supplier_id}`);

      const currentBranch = branch.branches.find(
        (candidate) => candidate.id === purchase.branch_id
      );

      branchLabel = currentBranch
        ? `${currentBranch.code ? `${currentBranch.code} — ` : ''}${currentBranch.name}`
        : `Sucursal ${purchase.branch_id}`;

      warehouseLabel = warehouse
        ? `${warehouse.code ? `${warehouse.code} — ` : ''}${warehouse.name}`
        : `Almacén ${purchase.warehouse_id}`;

      orderLabel = order?.code ?? purchase.purchase_order_id;

      const nextUnitLabels = new Map<number, string>();
      for (const unit of units) {
        nextUnitLabels.set(unit.id_unit, unit.code ? `${unit.code} — ${unit.name}` : unit.name);
      }
      unitLabels = nextUnitLabels;

      const nextProductLabels = new Map<number, string>();
      for (const product of products) {
        if (product) {
          nextProductLabels.set(product.id_product, `${product.sku} — ${product.name}`);
        }
      }
      productLabels = nextProductLabels;
    } catch (cause: unknown) {
      if (sequence !== requestSequence) return;

      item = null;
      supplierLabel = '';
      branchLabel = '';
      warehouseLabel = '';
      orderLabel = '';
      productLabels = new Map();
      unitLabels = new Map();
      error = errorMessage(cause);
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  function retry() {
    void load(id);
  }

  $effect(() => {
    const currentId = id;
    if (currentId) void load(currentId);
  });
</script>

<section class="space-y-5">
  <div>
    <a href="/purchases" class="text-sm font-medium text-primary hover:underline">
      ← Volver a compras
    </a>
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
    <div class="space-y-4" aria-label="Cargando detalle de compra">
      <div class="skeleton h-9 w-56 rounded"></div>
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {#each Array(4) as _}
          <div class="skeleton h-28 rounded-xl"></div>
        {/each}
      </div>
      <div class="skeleton h-64 rounded-xl"></div>
    </div>
  {:else if item}
    <header class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <p class="text-sm font-medium text-primary">Compra / recepción</p>
        <h1 class="text-2xl font-semibold tracking-tight text-foreground">
          {item.code}
        </h1>
        <p class="mt-1 text-sm text-foreground-muted">
          {supplierLabel || `Proveedor #${item.supplier_id}`}
        </p>
      </div>

      <span
        class="inline-flex w-fit rounded-full border border-border bg-surface-muted px-3 py-1.5 text-sm font-medium text-foreground"
      >
        {STATUS_LABELS[item.status]}
      </span>
    </header>

    <PurchaseWorkflowActions purchase={item} onupdated={handleUpdated} />

    {#if canCreateRetaceo}
      <section
        class="rounded-xl border border-border bg-surface p-4"
        aria-label="Retaceo de compra"
      >
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 class="font-semibold text-foreground">Retaceo</h2>
            <p class="mt-1 text-sm text-foreground-muted">
              Registra los costos de importación asociados a esta compra.
            </p>
          </div>

          <a
            href={`/retaceos/new?purchase_id=${item.id}`}
            class="inline-flex h-9 items-center justify-center rounded-lg bg-foreground px-3.5 text-sm font-medium text-surface transition-all duration-150 hover:bg-foreground-muted"
          >
            Crear retaceo
          </a>
        </div>
      </section>
    {/if}

    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <article class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">Proveedor</p>
        <p class="mt-2 font-medium text-foreground">
          {supplierLabel || `Proveedor #${item.supplier_id}`}
        </p>
      </article>

      <article class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">Sucursal</p>
        <p class="mt-2 font-medium text-foreground">
          {branchLabel || `Sucursal ${item.branch_id}`}
        </p>
      </article>

      <article class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">Almacén</p>
        <p class="mt-2 font-medium text-foreground">
          {warehouseLabel || `Almacén ${item.warehouse_id}`}
        </p>
      </article>

      <article class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">
          Orden origen
        </p>
        <a
          href={`/purchase-orders/${item.purchase_order_id}`}
          class="mt-2 inline-block font-medium text-primary hover:underline"
        >
          {orderLabel || item.purchase_order_id}
        </a>
      </article>
    </div>

    <div class="grid gap-5 xl:grid-cols-[2fr_1fr]">
      <article class="rounded-xl border border-border bg-surface">
        <div class="border-b border-border px-4 py-3">
          <h2 class="font-semibold text-foreground">Detalle recibido</h2>
        </div>

        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-border text-sm">
            <thead
              class="bg-surface-muted text-left text-xs uppercase tracking-wide text-foreground-muted"
            >
              <tr>
                <th class="px-4 py-3 font-medium">Producto</th>
                <th class="px-4 py-3 font-medium">Unidad</th>
                <th class="px-4 py-3 font-medium">Ordenado</th>
                <th class="px-4 py-3 font-medium">Recibido</th>
                <th class="px-4 py-3 font-medium">Precio unit.</th>
                <th class="px-4 py-3 font-medium">Total</th>
              </tr>
            </thead>

            <tbody class="divide-y divide-border">
              {#each item.details as detail (detail.id)}
                <tr class="text-foreground">
                  <td class="min-w-56 px-4 py-3 font-medium">
                    {productLabel(detail.product_id)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3 text-foreground-muted">
                    {unitLabel(detail.unit_id)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3">
                    {formatQuantity(detail.quantity_ordered)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3 font-medium">
                    {formatQuantity(detail.quantity_received)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3">
                    {formatMoney(detail.unit_price, item.currency)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3 font-medium">
                    {formatMoney(detail.total, item.currency)}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </article>

      <aside class="space-y-5">
        <article class="rounded-xl border border-border bg-surface p-4">
          <h2 class="font-semibold text-foreground">Totales</h2>

          <dl class="mt-4 space-y-3 text-sm">
            <div class="flex justify-between gap-4">
              <dt class="text-foreground-muted">Subtotal</dt>
              <dd class="font-medium text-foreground">
                {formatMoney(item.subtotal, item.currency)}
              </dd>
            </div>

            <div class="flex justify-between gap-4">
              <dt class="text-foreground-muted">Descuento</dt>
              <dd class="font-medium text-foreground">
                {formatMoney(item.discount, item.currency)}
              </dd>
            </div>

            <div class="flex justify-between gap-4">
              <dt class="text-foreground-muted">Impuestos</dt>
              <dd class="font-medium text-foreground">
                {formatMoney(item.tax, item.currency)}
              </dd>
            </div>

            <div class="flex justify-between gap-4 border-t border-border pt-3">
              <dt class="font-semibold text-foreground">Total</dt>
              <dd class="font-semibold text-foreground">
                {formatMoney(item.total, item.currency)}
              </dd>
            </div>
          </dl>
        </article>

        <article class="rounded-xl border border-border bg-surface p-4">
          <h2 class="font-semibold text-foreground">Documento proveedor</h2>

          <dl class="mt-4 space-y-3 text-sm">
            <div>
              <dt class="text-foreground-muted">Fecha de registro</dt>
              <dd class="mt-1 font-medium text-foreground">
                {formatDate(item.purchase_date)}
              </dd>
            </div>

            <div>
              <dt class="text-foreground-muted">Factura</dt>
              <dd class="mt-1 font-medium text-foreground">
                {item.supplier_invoice_number ?? '—'}
              </dd>
            </div>

            <div>
              <dt class="text-foreground-muted">Fecha factura</dt>
              <dd class="mt-1 font-medium text-foreground">
                {formatDate(item.supplier_invoice_date)}
              </dd>
            </div>

            <div>
              <dt class="text-foreground-muted">Moneda</dt>
              <dd class="mt-1 font-medium text-foreground">
                {item.currency}
              </dd>
            </div>
          </dl>
        </article>

        {#if item.notes}
          <article class="rounded-xl border border-border bg-surface p-4">
            <h2 class="font-semibold text-foreground">Notas</h2>
            <p class="mt-3 whitespace-pre-wrap text-sm text-foreground-muted">
              {item.notes}
            </p>
          </article>
        {/if}
      </aside>
    </div>
  {/if}
</section>
