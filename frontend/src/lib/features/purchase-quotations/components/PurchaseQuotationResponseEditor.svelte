<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { PurchaseQuotation } from '$lib/types/purchase-quotation';

  interface ResponseLineDraft {
    id: string;
    productId: number;
    unitId: number;
    quantity: string;
    unitPrice: string;
    discount: string;
    taxRate: string;
    deliveryDays: string;
    availableQuantity: string;
    notes: string;
  }

  let { id }: { id: string } = $props();

  let quotation = $state<PurchaseQuotation | null>(null);
  let lines = $state<ResponseLineDraft[]>([]);
  let quotationDate = $state('');
  let validUntil = $state('');
  let paymentTerms = $state('');
  let deliveryDays = $state('');
  let notes = $state('');
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let validation = $state<Record<string, string>>({});
  let loadGeneration = 0;

  let canManage = $derived(permissions.hasPermission('purchase_quotations:manage'));
  let canRecord = $derived(quotation?.status === 'requested');

  function errorMessage(cause: unknown, fallback: string): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return fallback;
  }

  function toLocalDateTimeInput(value: Date): string {
    const offset = value.getTimezoneOffset() * 60_000;
    return new Date(value.getTime() - offset).toISOString().slice(0, 16);
  }

  function initializeLines(item: PurchaseQuotation) {
    lines = item.details.map((detail) => ({
      id: detail.id,
      productId: detail.product_id,
      unitId: detail.unit_id,
      quantity: detail.quantity,
      unitPrice: detail.unit_price === '0.000000' ? '0' : detail.unit_price,
      discount: detail.discount === '0.000000' ? '0' : detail.discount,
      taxRate: detail.tax_rate === '0.000000' ? '0' : detail.tax_rate,
      deliveryDays: detail.delivery_days === null ? '' : String(detail.delivery_days),
      availableQuantity: detail.available_quantity === null ? '' : detail.available_quantity,
      notes: detail.notes ?? ''
    }));
  }

  async function load(currentId: string) {
    const generation = ++loadGeneration;
    loading = true;
    error = null;

    try {
      const item = await purchaseQuotationsApi.get(currentId);
      if (generation !== loadGeneration) return;

      quotation = item;
      quotationDate = toLocalDateTimeInput(new Date());
      validUntil = '';
      paymentTerms = item.payment_terms ?? '';
      deliveryDays = item.delivery_days === null ? '' : String(item.delivery_days);
      notes = item.notes ?? '';
      initializeLines(item);
    } catch (cause: unknown) {
      if (generation !== loadGeneration) return;
      quotation = null;
      lines = [];
      error = errorMessage(cause, 'No se pudo cargar la cotización de compra.');
    } finally {
      if (generation === loadGeneration) loading = false;
    }
  }

  $effect(() => {
    const currentId = id;
    if (canManage && currentId) {
      void load(currentId);
    } else {
      loading = false;
    }
  });

  function updateLine(
    index: number,
    field: 'unitPrice' | 'discount' | 'taxRate' | 'deliveryDays' | 'availableQuantity' | 'notes',
    value: string
  ) {
    lines = lines.map((line, currentIndex) =>
      currentIndex === index ? { ...line, [field]: value } : line
    );
  }

  function validate(): boolean {
    const next: Record<string, string> = {};

    if (!quotationDate) next.quotationDate = 'Indica la fecha de la cotización.';

    lines.forEach((line, index) => {
      const unitPrice = Number(line.unitPrice);
      const discount = Number(line.discount);
      const taxRate = Number(line.taxRate);

      if (!Number.isFinite(unitPrice) || unitPrice < 0) {
        next[`unitPrice-${index}`] = 'El precio unitario no puede ser negativo.';
      }
      if (!Number.isFinite(discount) || discount < 0) {
        next[`discount-${index}`] = 'El descuento no puede ser negativo.';
      }
      if (!Number.isFinite(taxRate) || taxRate < 0 || taxRate > 100) {
        next[`taxRate-${index}`] = 'La tasa debe estar entre 0 y 100.';
      }

      if (line.deliveryDays) {
        const lineDeliveryDays = Number(line.deliveryDays);
        if (!Number.isInteger(lineDeliveryDays) || lineDeliveryDays < 0) {
          next[`deliveryDays-${index}`] = 'Los días deben ser un entero no negativo.';
        }
      }

      if (line.availableQuantity) {
        const availableQuantity = Number(line.availableQuantity);
        if (!Number.isFinite(availableQuantity) || availableQuantity < 0) {
          next[`availableQuantity-${index}`] = 'La cantidad disponible no puede ser negativa.';
        }
      }
    });

    if (deliveryDays) {
      const generalDeliveryDays = Number(deliveryDays);
      if (!Number.isInteger(generalDeliveryDays) || generalDeliveryDays < 0) {
        next.deliveryDays = 'Los días de entrega deben ser un entero no negativo.';
      }
    }

    validation = next;
    return Object.keys(next).length === 0;
  }

  async function submit() {
    if (!quotation || !canManage || !canRecord || saving || !validate()) return;

    saving = true;
    error = null;

    try {
      await purchaseQuotationsApi.recordResponse(quotation.id, {
        quotation_date: new Date(quotationDate).toISOString(),
        valid_until: validUntil ? new Date(validUntil).toISOString() : null,
        payment_terms: paymentTerms.trim() || null,
        delivery_days: deliveryDays ? Number(deliveryDays) : null,
        lines: lines.map((line) => ({
          product_id: line.productId,
          unit_id: line.unitId,
          quantity: Number(line.quantity),
          unit_price: Number(line.unitPrice),
          discount: Number(line.discount || '0'),
          tax_rate: Number(line.taxRate || '0'),
          delivery_days: line.deliveryDays ? Number(line.deliveryDays) : null,
          available_quantity: line.availableQuantity ? Number(line.availableQuantity) : null,
          notes: line.notes.trim() || null
        })),
        expenses: [],
        notes: notes.trim() || null
      });

      await goto(`/purchase-quotations/${quotation.id}`);
    } catch (cause: unknown) {
      error = errorMessage(cause, 'No se pudo registrar la respuesta del proveedor.');
    } finally {
      saving = false;
    }
  }
</script>

<div class="min-h-full bg-background px-4 pb-8 pt-4 sm:px-6 sm:pt-6 md:px-8 md:pt-8">
  <header class="mb-6 flex items-center gap-3 border-b border-border pb-4">
    <a
      href={`/purchase-quotations/${id}`}
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-muted hover:text-foreground"
      aria-label="Volver al detalle de la cotización"
    >
      <span aria-hidden="true">←</span>
    </a>
    <div>
      <h1 class="text-xl font-semibold text-foreground">Registrar respuesta del proveedor</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Captura precios, impuestos y condiciones recibidas para la cotización.
      </p>
    </div>
  </header>

  {#if !canManage}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      No tienes permiso para gestionar cotizaciones de compra.
    </div>
  {:else if loading}
    <div class="space-y-4" aria-label="Cargando respuesta de cotización">
      <div class="skeleton h-40 rounded-xl"></div>
      <div class="skeleton h-64 rounded-xl"></div>
    </div>
  {:else if error && !quotation}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span>{error}</span>
        <Button type="button" size="sm" variant="secondary" onclick={() => load(id)}>
          Reintentar
        </Button>
      </div>
    </div>
  {:else if quotation && !canRecord}
    <div
      class="rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning"
      role="alert"
    >
      Solo las cotizaciones enviadas al proveedor pueden registrar una respuesta.
    </div>
  {:else if quotation}
    {#if error}
      <div
        class="mb-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
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
      <Card class="p-5">
        <div class="mb-4">
          <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">
            Cotización
          </p>
          <p class="mt-1 font-semibold text-foreground">{quotation.code}</p>
        </div>

        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div>
            <label
              for="quotation-response-date"
              class="mb-1 block text-sm font-medium text-foreground"
            >
              Fecha de cotización <span class="text-danger">*</span>
            </label>
            <input
              id="quotation-response-date"
              aria-label="Fecha de cotización"
              type="datetime-local"
              value={quotationDate}
              oninput={(event) => (quotationDate = (event.currentTarget as HTMLInputElement).value)}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
            />
            {#if validation.quotationDate}
              <p class="mt-1 text-xs text-danger">{validation.quotationDate}</p>
            {/if}
          </div>

          <div>
            <label
              for="quotation-response-valid-until"
              class="mb-1 block text-sm font-medium text-foreground"
            >
              Válida hasta
            </label>
            <input
              id="quotation-response-valid-until"
              aria-label="Válida hasta"
              type="datetime-local"
              value={validUntil}
              oninput={(event) => (validUntil = (event.currentTarget as HTMLInputElement).value)}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
            />
          </div>

          <div>
            <label
              for="quotation-response-delivery-days"
              class="mb-1 block text-sm font-medium text-foreground"
            >
              Entrega general (días)
            </label>
            <input
              id="quotation-response-delivery-days"
              aria-label="Entrega general"
              type="number"
              min="0"
              step="1"
              value={deliveryDays}
              oninput={(event) => (deliveryDays = (event.currentTarget as HTMLInputElement).value)}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
            />
            {#if validation.deliveryDays}
              <p class="mt-1 text-xs text-danger">{validation.deliveryDays}</p>
            {/if}
          </div>

          <div>
            <label
              for="quotation-response-payment-terms"
              class="mb-1 block text-sm font-medium text-foreground"
            >
              Términos de pago
            </label>
            <input
              id="quotation-response-payment-terms"
              aria-label="Términos de pago"
              maxlength="4000"
              value={paymentTerms}
              oninput={(event) => (paymentTerms = (event.currentTarget as HTMLInputElement).value)}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
              placeholder="Ej. 30 días crédito"
            />
          </div>
        </div>
      </Card>

      <Card class="overflow-hidden p-0">
        <div class="border-b border-border px-4 py-3">
          <h2 class="text-sm font-semibold text-foreground">Líneas cotizadas</h2>
          <p class="mt-1 text-xs text-foreground-muted">
            La cantidad solicitada se conserva; usa disponibilidad para reportar cobertura parcial.
          </p>
        </div>

        {#if lines.length === 0}
          <div class="p-8 text-center">
            <p class="font-medium text-foreground">No hay líneas para registrar</p>
          </div>
        {:else}
          <div class="divide-y divide-border">
            {#each lines as line, index (line.id)}
              <section class="space-y-4 p-4">
                <div>
                  <h3 class="font-medium text-foreground">Producto #{line.productId}</h3>
                  <p class="mt-1 text-xs text-foreground-muted">
                    Unidad #{line.unitId} · cantidad solicitada {line.quantity}
                  </p>
                </div>

                <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
                  <div>
                    <label
                      for={`response-price-${index}`}
                      class="mb-1 block text-xs font-medium text-foreground"
                    >
                      Precio unitario
                    </label>
                    <input
                      id={`response-price-${index}`}
                      aria-label={`Precio producto ${line.productId}`}
                      type="number"
                      min="0"
                      step="0.000001"
                      value={line.unitPrice}
                      oninput={(event) =>
                        updateLine(
                          index,
                          'unitPrice',
                          (event.currentTarget as HTMLInputElement).value
                        )}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
                    />
                    {#if validation[`unitPrice-${index}`]}
                      <p class="mt-1 text-xs text-danger">
                        {validation[`unitPrice-${index}`]}
                      </p>
                    {/if}
                  </div>

                  <div>
                    <label
                      for={`response-discount-${index}`}
                      class="mb-1 block text-xs font-medium text-foreground"
                    >
                      Descuento
                    </label>
                    <input
                      id={`response-discount-${index}`}
                      aria-label={`Descuento producto ${line.productId}`}
                      type="number"
                      min="0"
                      step="0.000001"
                      value={line.discount}
                      oninput={(event) =>
                        updateLine(
                          index,
                          'discount',
                          (event.currentTarget as HTMLInputElement).value
                        )}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
                    />
                    {#if validation[`discount-${index}`]}
                      <p class="mt-1 text-xs text-danger">
                        {validation[`discount-${index}`]}
                      </p>
                    {/if}
                  </div>

                  <div>
                    <label
                      for={`response-tax-${index}`}
                      class="mb-1 block text-xs font-medium text-foreground"
                    >
                      Impuesto %
                    </label>
                    <input
                      id={`response-tax-${index}`}
                      aria-label={`Impuesto producto ${line.productId}`}
                      type="number"
                      min="0"
                      max="100"
                      step="0.000001"
                      value={line.taxRate}
                      oninput={(event) =>
                        updateLine(
                          index,
                          'taxRate',
                          (event.currentTarget as HTMLInputElement).value
                        )}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
                    />
                    {#if validation[`taxRate-${index}`]}
                      <p class="mt-1 text-xs text-danger">
                        {validation[`taxRate-${index}`]}
                      </p>
                    {/if}
                  </div>

                  <div>
                    <label
                      for={`response-line-delivery-${index}`}
                      class="mb-1 block text-xs font-medium text-foreground"
                    >
                      Entrega (días)
                    </label>
                    <input
                      id={`response-line-delivery-${index}`}
                      aria-label={`Entrega producto ${line.productId}`}
                      type="number"
                      min="0"
                      step="1"
                      value={line.deliveryDays}
                      oninput={(event) =>
                        updateLine(
                          index,
                          'deliveryDays',
                          (event.currentTarget as HTMLInputElement).value
                        )}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
                    />
                    {#if validation[`deliveryDays-${index}`]}
                      <p class="mt-1 text-xs text-danger">
                        {validation[`deliveryDays-${index}`]}
                      </p>
                    {/if}
                  </div>

                  <div>
                    <label
                      for={`response-available-${index}`}
                      class="mb-1 block text-xs font-medium text-foreground"
                    >
                      Disponible
                    </label>
                    <input
                      id={`response-available-${index}`}
                      aria-label={`Disponible producto ${line.productId}`}
                      type="number"
                      min="0"
                      step="0.000001"
                      value={line.availableQuantity}
                      oninput={(event) =>
                        updateLine(
                          index,
                          'availableQuantity',
                          (event.currentTarget as HTMLInputElement).value
                        )}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
                    />
                    {#if validation[`availableQuantity-${index}`]}
                      <p class="mt-1 text-xs text-danger">
                        {validation[`availableQuantity-${index}`]}
                      </p>
                    {/if}
                  </div>
                </div>

                <div>
                  <label
                    for={`response-line-notes-${index}`}
                    class="mb-1 block text-xs font-medium text-foreground"
                  >
                    Notas de línea
                  </label>
                  <input
                    id={`response-line-notes-${index}`}
                    aria-label={`Notas producto ${line.productId}`}
                    maxlength="2000"
                    value={line.notes}
                    oninput={(event) =>
                      updateLine(index, 'notes', (event.currentTarget as HTMLInputElement).value)}
                    class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
                  />
                </div>
              </section>
            {/each}
          </div>
        {/if}
      </Card>

      <Card class="p-5">
        <label
          for="quotation-response-notes"
          class="mb-1 block text-sm font-medium text-foreground"
        >
          Notas generales
        </label>
        <textarea
          id="quotation-response-notes"
          aria-label="Notas generales"
          maxlength="4000"
          rows="3"
          value={notes}
          oninput={(event) => (notes = (event.currentTarget as HTMLTextAreaElement).value)}
          class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
        ></textarea>
      </Card>

      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button
          type="button"
          variant="secondary"
          onclick={() => goto(`/purchase-quotations/${id}`)}
        >
          Cancelar
        </Button>
        <Button type="submit" disabled={saving || lines.length === 0}>
          {saving ? 'Guardando…' : 'Registrar respuesta'}
        </Button>
      </div>
    </form>
  {/if}
</div>
