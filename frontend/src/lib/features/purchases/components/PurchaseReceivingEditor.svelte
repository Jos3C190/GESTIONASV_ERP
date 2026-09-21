<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchasesApi } from '$lib/api/purchases';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { PurchaseLineInput, PurchaseReceivable } from '$lib/types/purchase';

  let { orderId }: { orderId: string } = $props();

  let receivable = $state<PurchaseReceivable | null>(null);
  let productLabels = $state<Map<number, string>>(new Map());
  let unitLabels = $state<Map<number, string>>(new Map());
  let quantityInputs = $state<Record<string, string>>({});
  let supplierInvoiceNumber = $state('');
  let supplierInvoiceDate = $state('');
  let notes = $state('');
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let validationError = $state<string | null>(null);
  let requestSequence = 0;

  let canManage = $derived(permissions.hasPermission('purchases:manage'));
  let hasPending = $derived(
    receivable?.lines.some((line) => Number(line.quantity_pending) > 0) ?? false
  );

  function errorMessage(cause: unknown, fallback: string): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return fallback;
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

  function handleQuantityInput(lineId: string, event: Event) {
    quantityInputs[lineId] = (event.currentTarget as HTMLInputElement).value;
    validationError = null;
  }

  async function load(currentOrderId: string) {
    const sequence = ++requestSequence;
    loading = true;
    error = null;
    validationError = null;

    if (!currentOrderId) {
      receivable = null;
      loading = false;
      error = 'Selecciona una orden de compra para registrar la recepción.';
      return;
    }

    try {
      const next = await purchasesApi.getReceivable(currentOrderId);
      if (sequence !== requestSequence) return;

      receivable = next;
      quantityInputs = Object.fromEntries(
        next.lines.map((line) => [line.purchase_order_detail_id, ''])
      );

      const productIds = [...new Set(next.lines.map((line) => line.product_id))];

      const [units, products] = await Promise.all([
        catalogApi.listUnits(false).catch(() => []),
        Promise.all(
          productIds.map((productId) => catalogApi.getProduct(productId).catch(() => null))
        )
      ]);

      if (sequence !== requestSequence) return;

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

      receivable = null;
      productLabels = new Map();
      unitLabels = new Map();
      quantityInputs = {};
      error = errorMessage(cause, 'No se pudieron cargar las cantidades pendientes de la orden.');
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  async function saveDraft() {
    if (!receivable || saving || !canManage) return;

    validationError = null;

    const lines: PurchaseLineInput[] = [];

    for (const line of receivable.lines) {
      const quantity = Number(quantityInputs[line.purchase_order_detail_id] ?? '');

      if (Number.isFinite(quantity) && quantity > 0) {
        lines.push({
          purchase_order_detail_id: line.purchase_order_detail_id,
          quantity_received: quantity
        });
      }
    }

    if (lines.length === 0) {
      validationError = 'Ingresa una cantidad mayor que cero en al menos una línea.';
      return;
    }

    saving = true;

    try {
      await purchasesApi.create({
        purchase_order_id: receivable.purchase_order_id,
        supplier_invoice_number: supplierInvoiceNumber.trim() || null,
        supplier_invoice_date: supplierInvoiceDate || null,
        lines,
        notes: notes.trim() || null
      });

      await goto('/purchases');
    } catch (cause: unknown) {
      validationError = errorMessage(cause, 'No se pudo guardar el borrador de recepción.');
    } finally {
      saving = false;
    }
  }

  function cancel() {
    const current = receivable;
    if (current === null) return;

    void goto(`/purchase-orders/${current.purchase_order_id}`);
  }

  function retry() {
    void load(orderId);
  }

  $effect(() => {
    const currentOrderId = orderId;
    void load(currentOrderId);
  });
</script>

<section class="space-y-5">
  <div>
    <a
      href={orderId ? `/purchase-orders/${orderId}` : '/purchase-orders'}
      class="text-sm font-medium text-primary hover:underline"
    >
      ← Volver a la orden de compra
    </a>
  </div>

  {#if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span>{error}</span>
        {#if orderId}
          <Button size="sm" variant="secondary" onclick={retry}>Reintentar</Button>
        {/if}
      </div>
    </div>
  {:else if loading}
    <div class="space-y-4" aria-label="Cargando recepción">
      <div class="skeleton h-9 w-64 rounded"></div>
      <div class="skeleton h-32 rounded-xl"></div>
      <div class="skeleton h-72 rounded-xl"></div>
    </div>
  {:else if receivable}
    <header>
      <p class="text-sm font-medium text-primary">Recepción de compra</p>
      <h1 class="text-2xl font-semibold tracking-tight text-foreground">Registrar recepción</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Orden {receivable.code} · Proveedor #{receivable.supplier_id}
      </p>
    </header>

    {#if !canManage}
      <div
        class="rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-foreground"
        role="status"
      >
        No tienes permiso para registrar recepciones de compra.
      </div>
    {/if}

    <article class="rounded-xl border border-border bg-surface p-4">
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <label class="space-y-1.5 text-sm font-medium text-foreground">
          <span>Factura del proveedor</span>
          <input
            type="text"
            maxlength="80"
            bind:value={supplierInvoiceNumber}
            disabled={!canManage || saving}
            placeholder="Ej. FAC-00125"
            class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none disabled:opacity-60"
          />
        </label>

        <label class="space-y-1.5 text-sm font-medium text-foreground">
          <span>Fecha de factura</span>
          <input
            type="date"
            bind:value={supplierInvoiceDate}
            disabled={!canManage || saving}
            class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:opacity-60"
          />
        </label>

        <label class="space-y-1.5 text-sm font-medium text-foreground md:col-span-2 xl:col-span-1">
          <span>Moneda</span>
          <input
            type="text"
            value={receivable.currency}
            disabled
            class="h-10 w-full rounded-md border border-border bg-surface-muted px-3 text-sm text-foreground-muted"
          />
        </label>
      </div>

      <label class="mt-4 block space-y-1.5 text-sm font-medium text-foreground">
        <span>Notas</span>
        <textarea
          rows="3"
          maxlength="4000"
          bind:value={notes}
          disabled={!canManage || saving}
          placeholder="Observaciones de la recepción"
          class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none disabled:opacity-60"
        ></textarea>
      </label>
    </article>

    <article class="overflow-hidden rounded-xl border border-border bg-surface">
      <div class="border-b border-border px-4 py-3">
        <h2 class="font-semibold text-foreground">Cantidades a recibir</h2>
        <p class="mt-1 text-sm text-foreground-muted">
          El pendiente proviene del backend y se vuelve a validar al confirmar la recepción.
        </p>
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
              <th class="px-4 py-3 font-medium">Pendiente</th>
              <th class="px-4 py-3 font-medium">Recibir ahora</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-border">
            {#each receivable.lines as line (line.purchase_order_detail_id)}
              <tr class="text-foreground">
                <td class="min-w-56 px-4 py-3 font-medium">
                  {productLabel(line.product_id)}
                </td>

                <td class="whitespace-nowrap px-4 py-3 text-foreground-muted">
                  {unitLabel(line.unit_id)}
                </td>

                <td class="whitespace-nowrap px-4 py-3">
                  {formatQuantity(line.quantity_ordered)}
                </td>

                <td class="whitespace-nowrap px-4 py-3">
                  {formatQuantity(line.quantity_received)}
                </td>

                <td class="whitespace-nowrap px-4 py-3 font-medium">
                  {formatQuantity(line.quantity_pending)}
                </td>

                <td class="min-w-44 px-4 py-3">
                  <input
                    type="number"
                    min="0"
                    max={line.quantity_pending}
                    step="0.000001"
                    value={quantityInputs[line.purchase_order_detail_id] ?? ''}
                    disabled={!canManage || saving || Number(line.quantity_pending) <= 0}
                    aria-label={`Cantidad a recibir para ${productLabel(line.product_id)}`}
                    oninput={(event) => handleQuantityInput(line.purchase_order_detail_id, event)}
                    class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:bg-surface-muted disabled:opacity-60"
                  />
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </article>

    {#if !hasPending}
      <div
        class="rounded-xl border border-border bg-surface-muted p-4 text-sm text-foreground-muted"
        role="status"
      >
        Esta orden ya no tiene cantidades pendientes de recibir.
      </div>
    {/if}

    {#if validationError}
      <div
        class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
        role="alert"
      >
        {validationError}
      </div>
    {/if}

    <div class="flex flex-wrap justify-end gap-2">
      <Button variant="secondary" disabled={saving} onclick={cancel}>Cancelar</Button>

      <Button disabled={!canManage || saving || !hasPending} onclick={() => void saveDraft()}>
        {saving ? 'Guardando…' : 'Guardar borrador'}
      </Button>
    </div>
  {/if}
</section>
