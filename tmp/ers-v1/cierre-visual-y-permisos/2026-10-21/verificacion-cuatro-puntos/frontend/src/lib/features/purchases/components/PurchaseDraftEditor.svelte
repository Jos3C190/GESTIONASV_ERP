<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchasesApi } from '$lib/api/purchases';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Purchase, PurchaseReceivable } from '$lib/types/purchase';

  interface DraftLine {
    purchaseOrderDetailId: string;
    productId: number;
    unitId: number;
    quantityOrdered: string;
    quantityReceived: string;
    quantityPending: string;
    quantity: string;
    included: boolean;
  }

  let { purchaseId }: { purchaseId: string } = $props();

  let purchase = $state<Purchase | null>(null);
  let receivable = $state<PurchaseReceivable | null>(null);
  let lines = $state<DraftLine[]>([]);
  let supplierInvoiceNumber = $state('');
  let supplierInvoiceDate = $state('');
  let notes = $state('');
  let productLabels = $state<Map<number, string>>(new Map());
  let unitLabels = $state<Map<number, string>>(new Map());
  let loading = $state(true);
  let saving = $state(false);
  let editable = $state(true);
  let error = $state<string | null>(null);
  let validation = $state<Record<string, string>>({});
  let requestSequence = 0;

  let canManage = $derived(permissions.hasPermission('purchases:manage'));
  let selectedCount = $derived(lines.filter((line) => line.included).length);

  function errorMessage(cause: unknown, fallback: string): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return fallback;
  }

  function productLabel(id: number): string {
    return productLabels.get(id) ?? `Producto #${id}`;
  }

  function unitLabel(id: number): string {
    return unitLabels.get(id) ?? `Unidad #${id}`;
  }

  function formatQuantity(value: string): string {
    const quantity = Number(value);
    if (!Number.isFinite(quantity)) return value;

    return new Intl.NumberFormat('es-SV', {
      maximumFractionDigits: 6
    }).format(quantity);
  }

  function updateLine(index: number, patch: Partial<Pick<DraftLine, 'quantity' | 'included'>>) {
    lines = lines.map((line, currentIndex) =>
      currentIndex === index ? { ...line, ...patch } : line
    );
    validation = {};
  }

  function buildLines(current: Purchase, pending: PurchaseReceivable): DraftLine[] {
    const currentDetails = new Map(
      current.details.map((detail) => [detail.purchase_order_detail_id, detail])
    );

    return pending.lines.map((line) => {
      const existing = currentDetails.get(line.purchase_order_detail_id);

      return {
        purchaseOrderDetailId: line.purchase_order_detail_id,
        productId: line.product_id,
        unitId: line.unit_id,
        quantityOrdered: line.quantity_ordered,
        quantityReceived: line.quantity_received,
        quantityPending: line.quantity_pending,
        quantity: existing?.quantity_received ?? '',
        included: existing !== undefined
      };
    });
  }

  async function load(currentPurchaseId: string) {
    const sequence = ++requestSequence;
    loading = true;
    editable = true;
    error = null;
    validation = {};

    try {
      const current = await purchasesApi.get(currentPurchaseId);
      if (sequence !== requestSequence) return;

      purchase = current;

      if (current.status !== 'draft') {
        editable = false;
        error = 'Solo las compras en borrador pueden editarse.';
        return;
      }

      supplierInvoiceNumber = current.supplier_invoice_number ?? '';
      supplierInvoiceDate = current.supplier_invoice_date ?? '';
      notes = current.notes ?? '';

      const pending = await purchasesApi.getReceivable(current.purchase_order_id);

      if (sequence !== requestSequence) return;

      receivable = pending;
      lines = buildLines(current, pending);

      const productIds = [...new Set(pending.lines.map((line) => line.product_id))];

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

      purchase = null;
      receivable = null;
      lines = [];
      editable = false;
      error = errorMessage(cause, 'No se pudo cargar el borrador de recepción.');
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  function validate(): boolean {
    const next: Record<string, string> = {};
    const selectedLines = lines.filter((line) => line.included);

    if (selectedLines.length === 0) {
      next.lines = 'Selecciona al menos una línea para recibir.';
    }

    lines.forEach((line, index) => {
      if (!line.included) return;

      const quantity = Number(line.quantity);

      if (!Number.isFinite(quantity) || quantity <= 0) {
        next[`quantity-${index}`] = 'La cantidad debe ser mayor que cero.';
      }
    });

    validation = next;
    return Object.keys(next).length === 0;
  }

  async function submit() {
    if (!canManage || !editable || saving || !purchase || !validate()) {
      return;
    }

    saving = true;
    error = null;

    try {
      const updated = await purchasesApi.update(purchase.id, {
        supplier_invoice_number: supplierInvoiceNumber.trim() || null,
        supplier_invoice_date: supplierInvoiceDate || null,
        lines: lines
          .filter((line) => line.included)
          .map((line) => ({
            purchase_order_detail_id: line.purchaseOrderDetailId,
            quantity_received: Number(line.quantity)
          })),
        notes: notes.trim() || null
      });

      await goto(`/purchases/${updated.id}`);
    } catch (cause: unknown) {
      error = errorMessage(cause, 'No se pudo actualizar el borrador de recepción.');
    } finally {
      saving = false;
    }
  }

  function retry() {
    void load(purchaseId);
  }

  $effect(() => {
    const currentPurchaseId = purchaseId;

    if (canManage && currentPurchaseId) {
      void load(currentPurchaseId);
    } else {
      loading = false;
    }
  });
</script>

<section class="space-y-5">
  <div>
    <a
      href={purchaseId ? `/purchases/${purchaseId}` : '/purchases'}
      class="text-sm font-medium text-primary hover:underline"
    >
      ← Volver a compra
    </a>
  </div>

  {#if !canManage}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      No tienes permiso para gestionar recepciones de compra.
    </div>
  {:else if loading}
    <div class="space-y-4" aria-label="Cargando formulario de recepción">
      <div class="skeleton h-28 rounded-xl"></div>
      <div class="skeleton h-64 rounded-xl"></div>
    </div>
  {:else if !editable}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span>{error ?? 'Esta recepción no puede editarse.'}</span>

        {#if purchaseId}
          <Button size="sm" variant="secondary" onclick={retry}>Reintentar</Button>
        {/if}
      </div>
    </div>
  {:else if purchase && receivable}
    <header>
      <p class="text-sm font-medium text-primary">Compra / recepción</p>

      <h1 class="text-2xl font-semibold tracking-tight text-foreground">
        Editar {purchase.code}
      </h1>

      <p class="mt-1 text-sm text-foreground-muted">
        Orden {receivable.code}. Las cantidades pendientes se consultan nuevamente antes de editar
        el borrador.
      </p>
    </header>

    {#if error}
      <div
        class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        role="alert"
      >
        {error}
      </div>
    {/if}

    <form
      class="space-y-5"
      onsubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <article class="rounded-xl border border-border bg-surface p-4">
        <div class="grid gap-4 md:grid-cols-2">
          <label class="space-y-1.5 text-sm font-medium text-foreground">
            <span>Factura del proveedor</span>

            <input
              aria-label="Factura del proveedor"
              type="text"
              maxlength="80"
              bind:value={supplierInvoiceNumber}
              disabled={saving}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:opacity-60"
            />
          </label>

          <label class="space-y-1.5 text-sm font-medium text-foreground">
            <span>Fecha de factura</span>

            <input
              aria-label="Fecha de factura"
              type="date"
              bind:value={supplierInvoiceDate}
              disabled={saving}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:opacity-60"
            />
          </label>
        </div>

        <label class="mt-4 block space-y-1.5 text-sm font-medium text-foreground">
          <span>Notas</span>

          <textarea
            aria-label="Notas"
            rows="3"
            maxlength="4000"
            bind:value={notes}
            disabled={saving}
            class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none disabled:opacity-60"
          ></textarea>
        </label>
      </article>

      <article class="overflow-hidden rounded-xl border border-border bg-surface">
        <div class="border-b border-border px-4 py-3">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 class="font-semibold text-foreground">Líneas de recepción</h2>

              <p class="mt-1 text-sm text-foreground-muted">
                Cada línea conserva la referencia exacta al detalle de la orden de compra.
              </p>
            </div>

            <span class="text-sm text-foreground-muted">
              {selectedCount} seleccionadas
            </span>
          </div>
        </div>

        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-border text-sm">
            <thead
              class="bg-surface-muted text-left text-xs uppercase tracking-wide text-foreground-muted"
            >
              <tr>
                <th class="px-4 py-3 font-medium">Incluir</th>
                <th class="px-4 py-3 font-medium">Producto</th>
                <th class="px-4 py-3 font-medium">Unidad</th>
                <th class="px-4 py-3 font-medium">Ordenado</th>
                <th class="px-4 py-3 font-medium">Recibido</th>
                <th class="px-4 py-3 font-medium">Pendiente</th>
                <th class="px-4 py-3 font-medium">Recibir</th>
              </tr>
            </thead>

            <tbody class="divide-y divide-border">
              {#each lines as line, index (line.purchaseOrderDetailId)}
                <tr class="text-foreground">
                  <td class="px-4 py-3">
                    <input
                      type="checkbox"
                      aria-label={`Incluir línea ${index + 1}`}
                      checked={line.included}
                      disabled={saving}
                      onchange={(event) =>
                        updateLine(index, {
                          included: (event.currentTarget as HTMLInputElement).checked
                        })}
                      class="h-4 w-4 rounded border-border"
                    />
                  </td>

                  <td class="min-w-56 px-4 py-3 font-medium">
                    {productLabel(line.productId)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3 text-foreground-muted">
                    {unitLabel(line.unitId)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3">
                    {formatQuantity(line.quantityOrdered)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3">
                    {formatQuantity(line.quantityReceived)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3 font-medium">
                    {formatQuantity(line.quantityPending)}
                  </td>

                  <td class="min-w-44 px-4 py-3">
                    <input
                      aria-label={`Cantidad a recibir línea ${index + 1}`}
                      type="number"
                      min="0.000001"
                      max={line.quantityPending}
                      step="0.000001"
                      value={line.quantity}
                      disabled={!line.included || saving}
                      oninput={(event) =>
                        updateLine(index, {
                          quantity: (event.currentTarget as HTMLInputElement).value
                        })}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
                    />

                    {#if validation[`quantity-${index}`]}
                      <p class="mt-1 text-xs text-danger">
                        {validation[`quantity-${index}`]}
                      </p>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>

        {#if validation.lines}
          <p class="border-t border-border px-4 py-3 text-sm text-danger">
            {validation.lines}
          </p>
        {/if}
      </article>

      <div class="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <a
          href={`/purchases/${purchase.id}`}
          class="inline-flex h-10 items-center justify-center rounded-lg border border-border bg-surface px-4 text-sm font-medium text-foreground hover:bg-surface-muted"
        >
          Cancelar
        </a>

        <Button type="submit" disabled={saving || lines.length === 0}>
          {saving ? 'Guardando…' : 'Guardar cambios'}
        </Button>
      </div>
    </form>
  {/if}
</section>
