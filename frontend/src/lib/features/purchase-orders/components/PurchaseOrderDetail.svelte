<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchaseOrdersApi } from '$lib/api/purchase-orders';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { suppliersApi } from '$lib/api/suppliers';
  import PurchaseOrderExpenseDocuments from '$lib/features/purchase-orders/components/PurchaseOrderExpenseDocuments.svelte';
  import PurchaseOrderWorkflowActions from '$lib/features/purchase-orders/components/PurchaseOrderWorkflowActions.svelte';
  import { getWarehouse } from '$lib/services/warehouses';
  import { branch } from '$lib/stores/branch.svelte';
  import type { PurchaseOrder, PurchaseOrderStatus } from '$lib/types/purchase-order';

  let { id }: { id: string } = $props();

  const STATUS_LABELS: Record<PurchaseOrderStatus, string> = {
    draft: 'Borrador',
    pending_approval: 'Pendiente de aprobación',
    approved: 'Aprobada',
    sent: 'Enviada',
    partially_received: 'Parcialmente recibida',
    received: 'Recibida',
    cancelled: 'Cancelada',
    closed: 'Cerrada'
  };

  let item = $state<PurchaseOrder | null>(null);
  let supplierLabel = $state('');
  let branchLabel = $state('');
  let warehouseLabel = $state('');
  let quotationLabel = $state('');
  let productLabels = $state<Map<number, string>>(new Map());
  let unitLabels = $state<Map<number, string>>(new Map());
  let expenseTypeLabels = $state<Map<string, string>>(new Map());
  let loading = $state(true);
  let error = $state<string | null>(null);
  let requestSequence = 0;

  function errorMessage(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return 'No se pudo cargar la orden de compra.';
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

  function expenseTypeLabel(id: string): string {
    return expenseTypeLabels.get(id) ?? id;
  }

  function handleWorkflowUpdated(updated: PurchaseOrder) {
    item = updated;
  }

  async function load(currentId: string) {
    const sequence = ++requestSequence;
    loading = true;
    error = null;

    try {
      const order = await purchaseOrdersApi.get(currentId);
      if (sequence !== requestSequence) return;

      item = order;

      const productIds = [...new Set(order.details.map((detail) => detail.product_id))];
      const [supplier, quotation, warehouse, units, products, expenseTypes] = await Promise.all([
        suppliersApi.getSupplier(order.supplier_id).catch(() => null),
        purchaseQuotationsApi.get(order.purchase_quotation_id).catch(() => null),
        getWarehouse(order.warehouse_id).catch(() => null),
        catalogApi.listUnits(false).catch(() => []),
        Promise.all(
          productIds.map((productId) => catalogApi.getProduct(productId).catch(() => null))
        ),
        purchaseOrdersApi.listExpenseTypes().catch(() => [])
      ]);

      if (sequence !== requestSequence) return;

      supplierLabel = supplier?.code
        ? `${supplier.code} — ${supplier.name}`
        : (supplier?.name ?? `Proveedor #${order.supplier_id}`);

      const currentBranch = branch.branches.find((candidate) => candidate.id === order.branch_id);
      branchLabel = currentBranch
        ? `${currentBranch.code ? `${currentBranch.code} — ` : ''}${currentBranch.name}`
        : `Sucursal ${order.branch_id}`;

      warehouseLabel = warehouse
        ? `${warehouse.code ? `${warehouse.code} — ` : ''}${warehouse.name}`
        : `Almacén ${order.warehouse_id}`;

      quotationLabel = quotation?.code ?? order.purchase_quotation_id;

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

      const nextExpenseTypeLabels = new Map<string, string>();
      for (const expenseType of expenseTypes) {
        nextExpenseTypeLabels.set(expenseType.id, expenseType.name);
      }
      expenseTypeLabels = nextExpenseTypeLabels;
    } catch (cause: unknown) {
      if (sequence !== requestSequence) return;
      item = null;
      supplierLabel = '';
      branchLabel = '';
      warehouseLabel = '';
      quotationLabel = '';
      productLabels = new Map();
      unitLabels = new Map();
      expenseTypeLabels = new Map();
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
    <a href="/purchase-orders" class="text-sm font-medium text-primary hover:underline">
      ← Volver a órdenes de compra
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
    <div class="space-y-4">
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
        <p class="text-sm font-medium text-primary">Orden de compra</p>
        <h1 class="text-2xl font-semibold tracking-tight text-foreground">{item.code}</h1>
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

    <PurchaseOrderWorkflowActions order={item} onupdated={handleWorkflowUpdated} />

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
          Cotización origen
        </p>
        <a
          href={`/purchase-quotations/${item.purchase_quotation_id}`}
          class="mt-2 inline-block font-medium text-primary hover:underline"
        >
          {quotationLabel || item.purchase_quotation_id}
        </a>
      </article>
    </div>

    <div class="grid gap-5 xl:grid-cols-[2fr_1fr]">
      <div class="space-y-5">
        <article class="rounded-xl border border-border bg-surface">
          <div class="border-b border-border px-4 py-3">
            <h2 class="font-semibold text-foreground">Líneas ordenadas</h2>
          </div>

          {#if item.details.length === 0}
            <p class="p-4 text-sm text-foreground-muted">No hay líneas en la orden.</p>
          {:else}
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-border text-sm">
                <thead
                  class="bg-surface-muted text-left text-xs uppercase tracking-wide text-foreground-muted"
                >
                  <tr>
                    <th class="px-4 py-3 font-medium">Producto</th>
                    <th class="px-4 py-3 font-medium">Unidad</th>
                    <th class="px-4 py-3 font-medium">Cantidad</th>
                    <th class="px-4 py-3 font-medium">Precio unit.</th>
                    <th class="px-4 py-3 font-medium">Subtotal</th>
                    <th class="px-4 py-3 font-medium">Impuesto</th>
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
                        {formatQuantity(detail.quantity)}
                      </td>
                      <td class="whitespace-nowrap px-4 py-3">
                        {formatMoney(detail.unit_price, item.currency)}
                      </td>
                      <td class="whitespace-nowrap px-4 py-3">
                        {formatMoney(detail.subtotal, item.currency)}
                      </td>
                      <td class="whitespace-nowrap px-4 py-3">
                        {formatMoney(detail.tax_amount, item.currency)}
                      </td>
                      <td class="whitespace-nowrap px-4 py-3 font-medium">
                        {formatMoney(detail.total, item.currency)}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </article>

        <article class="rounded-xl border border-border bg-surface">
          <div class="border-b border-border px-4 py-3">
            <h2 class="font-semibold text-foreground">Gastos adicionales</h2>
          </div>

          {#if item.expenses.length === 0}
            <p class="p-4 text-sm text-foreground-muted">
              Esta orden no tiene gastos adicionales registrados.
            </p>
          {:else}
            <ul class="divide-y divide-border">
              {#each item.expenses as expense (expense.id)}
                <li class="space-y-3 px-4 py-3 text-sm">
                  <div class="flex items-start justify-between gap-4">
                    <div>
                      <p class="font-medium text-foreground">
                        {expense.description ?? 'Gasto adicional'}
                      </p>
                      <p class="mt-1 text-xs text-foreground-muted">
                        Tipo de gasto: {expenseTypeLabel(expense.expense_type_id)}
                      </p>
                    </div>
                    <span class="whitespace-nowrap font-medium text-foreground">
                      {formatMoney(expense.amount, item.currency)}
                    </span>
                  </div>

                  <PurchaseOrderExpenseDocuments
                    orderId={item.id}
                    {expense}
                    orderStatus={item.status}
                  />
                </li>
              {/each}
            </ul>
          {/if}
        </article>
      </div>

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
              <dd class="font-medium text-foreground">{formatMoney(item.tax, item.currency)}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-foreground-muted">Gastos adicionales</dt>
              <dd class="font-medium text-foreground">
                {formatMoney(item.additional_expenses, item.currency)}
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
          <h2 class="font-semibold text-foreground">Condiciones</h2>
          <dl class="mt-4 space-y-3 text-sm">
            <div>
              <dt class="text-foreground-muted">Fecha de orden</dt>
              <dd class="mt-1 font-medium text-foreground">{formatDate(item.order_date)}</dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Fecha esperada</dt>
              <dd class="mt-1 font-medium text-foreground">{formatDate(item.expected_date)}</dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Moneda</dt>
              <dd class="mt-1 font-medium text-foreground">{item.currency}</dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Términos de pago</dt>
              <dd class="mt-1 whitespace-pre-wrap text-foreground">
                {item.payment_terms ?? '—'}
              </dd>
            </div>
          </dl>
        </article>

        {#if item.notes}
          <article class="rounded-xl border border-border bg-surface p-4">
            <h2 class="font-semibold text-foreground">Notas</h2>
            <p class="mt-3 whitespace-pre-wrap text-sm text-foreground-muted">{item.notes}</p>
          </article>
        {/if}
      </aside>
    </div>
  {/if}
</section>
