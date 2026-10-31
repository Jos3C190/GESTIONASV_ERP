<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import PurchaseQuotationDocuments from '$lib/features/purchase-quotations/components/PurchaseQuotationDocuments.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { session } from '$lib/stores/session.svelte';
  import type { PurchaseQuotation } from '$lib/types/purchase-quotation';

  interface ResponseLineDraft {
    id: string;
    productId: number;
    unitId: number;
    quantity: string;
    offeredQuantity: string;
    unitPrice: string;
    discount: string;
    taxRate: string;
    deliveryDays: string;
    availableQuantity: string;
    notes: string;
  }

  interface PersistedResponseDraft {
    quotationId: string;
    userId: string | null;
    quotationDate: string;
    validUntil: string;
    paymentTerms: string;
    deliveryDays: string;
    notes: string;
    lines: ResponseLineDraft[];
  }

  let { id, consolidationId = null }: { id: string; consolidationId?: string | null } = $props();

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
  let draftRestored = $state(false);
  let draftSaved = $state(false);
  let loadGeneration = 0;

  let canManage = $derived(permissions.hasPermission('purchase_quotations:manage'));
  let canRecord = $derived(quotation?.status === 'requested');

  function snapshotFor(detailId: string) {
    return quotation?.snapshots.find(
      (snapshot) => snapshot.purchase_quotation_detail_id === detailId
    );
  }

  function lineLabel(line: ResponseLineDraft): string {
    const snapshot = snapshotFor(line.id);
    return snapshot
      ? `${snapshot.product_sku} · ${snapshot.product_name}`
      : `Producto #${line.productId}`;
  }

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
      offeredQuantity: detail.offered_quantity ?? detail.quantity,
      unitPrice: detail.unit_price === '0.000000' ? '0' : detail.unit_price,
      discount: detail.discount === '0.000000' ? '0' : detail.discount,
      taxRate: detail.tax_rate === '0.000000' ? '0' : detail.tax_rate,
      deliveryDays: detail.delivery_days === null ? '' : String(detail.delivery_days),
      availableQuantity: detail.available_quantity === null ? '' : detail.available_quantity,
      notes: detail.notes ?? ''
    }));
  }

  function draftStorageKey(quotationId: string): string {
    return `erp_purchase_quotation_response_draft:${session.user?.id ?? 'anonymous'}:${quotationId}`;
  }

  function clearResponseDraft(quotationId: string): void {
    if (typeof window === 'undefined') return;
    try {
      window.sessionStorage.removeItem(draftStorageKey(quotationId));
      if (quotation?.id === quotationId) draftSaved = false;
    } catch {
      // Storage may be unavailable in private browsing; the form still works in memory.
    }
  }

  function persistResponseDraft(
    overrides: Partial<Omit<PersistedResponseDraft, 'quotationId' | 'userId'>> = {}
  ): void {
    if (!quotation || quotation.status !== 'requested' || typeof window === 'undefined') return;

    const draft: PersistedResponseDraft = {
      quotationId: quotation.id,
      userId: session.user?.id ?? null,
      quotationDate: overrides.quotationDate ?? quotationDate,
      validUntil: overrides.validUntil ?? validUntil,
      paymentTerms: overrides.paymentTerms ?? paymentTerms,
      deliveryDays: overrides.deliveryDays ?? deliveryDays,
      notes: overrides.notes ?? notes,
      lines: overrides.lines ?? lines
    };

    try {
      window.sessionStorage.setItem(draftStorageKey(quotation.id), JSON.stringify(draft));
      draftSaved = true;
    } catch {
      // Storage may be unavailable in private browsing; the form still works in memory.
      draftSaved = false;
    }
  }

  function restoreResponseDraft(item: PurchaseQuotation): boolean {
    if (typeof window === 'undefined') return false;

    const key = draftStorageKey(item.id);
    let saved: PersistedResponseDraft;
    try {
      const raw = window.sessionStorage.getItem(key);
      if (!raw) return false;
      const parsed: unknown = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') {
        clearResponseDraft(item.id);
        return false;
      }
      saved = parsed as PersistedResponseDraft;
    } catch {
      clearResponseDraft(item.id);
      return false;
    }

    const currentUserId = session.user?.id ?? null;
    const savedById = new Map(
      Array.isArray(saved.lines)
        ? saved.lines
            .filter((line) => line && typeof line.id === 'string')
            .map((line) => [line.id, line])
        : []
    );
    const matchesCurrentQuotation =
      saved.quotationId === item.id &&
      saved.userId === currentUserId &&
      savedById.size === lines.length &&
      lines.every((line) => {
        const previous = savedById.get(line.id);
        return (
          previous !== undefined &&
          previous.productId === line.productId &&
          previous.unitId === line.unitId &&
          previous.quantity === line.quantity &&
          [
            'offeredQuantity',
            'unitPrice',
            'discount',
            'taxRate',
            'deliveryDays',
            'availableQuantity',
            'notes'
          ].every((field) => typeof previous[field as keyof ResponseLineDraft] === 'string')
        );
      });

    if (
      !matchesCurrentQuotation ||
      typeof saved.quotationDate !== 'string' ||
      typeof saved.validUntil !== 'string' ||
      typeof saved.paymentTerms !== 'string' ||
      typeof saved.deliveryDays !== 'string' ||
      typeof saved.notes !== 'string'
    ) {
      clearResponseDraft(item.id);
      return false;
    }

    quotationDate = saved.quotationDate;
    validUntil = saved.validUntil;
    paymentTerms = saved.paymentTerms;
    deliveryDays = saved.deliveryDays;
    notes = saved.notes;
    lines = lines.map((line) => {
      const previous = savedById.get(line.id)!;
      return {
        ...line,
        offeredQuantity: previous.offeredQuantity,
        unitPrice: previous.unitPrice,
        discount: previous.discount,
        taxRate: previous.taxRate,
        deliveryDays: previous.deliveryDays,
        availableQuantity: previous.availableQuantity,
        notes: previous.notes
      };
    });
    draftSaved = true;
    return true;
  }

  async function load(currentId: string, currentBranchId: string | null) {
    const generation = ++loadGeneration;
    loading = true;
    error = null;

    try {
      const item = await purchaseQuotationsApi.get(currentId, currentBranchId, consolidationId);
      if (generation !== loadGeneration) return;

      quotation = item;
      quotationDate = toLocalDateTimeInput(new Date());
      validUntil = '';
      paymentTerms = item.payment_terms ?? '';
      deliveryDays = item.delivery_days === null ? '' : String(item.delivery_days);
      notes = item.response_notes ?? '';
      initializeLines(item);
      draftRestored = item.status === 'requested' ? restoreResponseDraft(item) : false;
      if (item.status === 'requested' && !draftRestored) persistResponseDraft();
      if (item.status !== 'requested') clearResponseDraft(item.id);
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
    const currentBranchId = branch.id;
    if (canManage && currentId) {
      void load(currentId, currentBranchId);
    } else {
      loading = false;
    }
  });

  function updateLine(
    index: number,
    field:
      | 'offeredQuantity'
      | 'unitPrice'
      | 'discount'
      | 'taxRate'
      | 'deliveryDays'
      | 'availableQuantity'
      | 'notes',
    value: string
  ) {
    const nextLines = lines.map((line, currentIndex) => {
      if (currentIndex !== index) return line;
      if (field === 'offeredQuantity' && Number(value) === 0) {
        return {
          ...line,
          offeredQuantity: value,
          unitPrice: '0',
          discount: '0',
          taxRate: '0',
          availableQuantity: ''
        };
      }
      return { ...line, [field]: value };
    });
    lines = nextLines;
    persistResponseDraft({ lines: nextLines });
  }

  function validate(): boolean {
    const next: Record<string, string> = {};

    if (!quotationDate) next.quotationDate = 'Indica la fecha de la cotización.';

    lines.forEach((line, index) => {
      const unitPrice = Number(line.unitPrice);
      const discount = Number(line.discount);
      const taxRate = Number(line.taxRate);
      const offeredQuantity = Number(line.offeredQuantity);

      if (!Number.isFinite(offeredQuantity) || offeredQuantity < 0) {
        next[`offeredQuantity-${index}`] = 'La cantidad ofrecida no puede ser negativa.';
      } else if (offeredQuantity > Number(line.quantity)) {
        next[`offeredQuantity-${index}`] = 'La cantidad ofrecida no puede superar lo solicitado.';
      }

      if (!Number.isFinite(unitPrice) || unitPrice < 0) {
        next[`unitPrice-${index}`] = 'El precio unitario no puede ser negativo.';
      }
      if (!Number.isFinite(discount) || discount < 0) {
        next[`discount-${index}`] = 'El descuento no puede ser negativo.';
      } else if (
        Number.isFinite(offeredQuantity) &&
        Number.isFinite(unitPrice) &&
        discount > offeredQuantity * unitPrice
      ) {
        next[`discount-${index}`] =
          'El descuento no puede superar el importe de la cantidad ofrecida.';
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
        } else if (Number.isFinite(offeredQuantity) && availableQuantity > offeredQuantity) {
          next[`availableQuantity-${index}`] =
            'La disponibilidad no puede superar la cantidad ofrecida.';
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
      await purchaseQuotationsApi.recordResponse(
        quotation.id,
        {
          quotation_date: new Date(quotationDate).toISOString(),
          valid_until: validUntil ? new Date(validUntil).toISOString() : null,
          payment_terms: paymentTerms.trim() || null,
          delivery_days: deliveryDays ? Number(deliveryDays) : null,
          lines: lines.map((line) => ({
            product_id: line.productId,
            unit_id: line.unitId,
            offered_quantity: Number(line.offeredQuantity),
            unit_price: Number(line.unitPrice),
            discount: Number(line.discount || '0'),
            tax_rate: Number(line.taxRate || '0'),
            delivery_days: line.deliveryDays ? Number(line.deliveryDays) : null,
            available_quantity: line.availableQuantity ? Number(line.availableQuantity) : null,
            notes: line.notes.trim() || null
          })),
          expenses: [],
          notes: notes.trim() || null
        },
        branch.id,
        consolidationId
      );

      clearResponseDraft(quotation.id);
      await goto(
        `/purchase-quotations/${quotation.id}${consolidationId ? `?consolidation_id=${consolidationId}` : ''}`
      );
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
      href={`/purchase-quotations/${id}${consolidationId ? `?consolidation_id=${consolidationId}` : ''}`}
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-muted hover:text-foreground"
      aria-label="Volver al detalle de la cotización"
    >
      <span aria-hidden="true">←</span>
    </a>
    <div>
      <h1 class="text-xl font-semibold text-foreground">Registrar respuesta del proveedor</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        La cantidad solicitada queda fija. Registra lo que el proveedor ofrece; usa cero si no
        cotizó una línea.
      </p>
      {#if draftSaved}
        <p class="mt-1 text-xs text-success" role="status">
          Borrador guardado automáticamente en esta pestaña. Adjuntar un archivo no lo envía ni lo
          borra; «Registrar respuesta» guarda la cotización.
        </p>
      {:else}
        <p class="mt-1 text-xs text-warning" role="status">
          El guardado automático del navegador no está disponible. Evita recargar o cerrar esta
          pestaña antes de registrar la respuesta.
        </p>
      {/if}
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
        <Button type="button" size="sm" variant="secondary" onclick={() => load(id, branch.id)}>
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
    {#if draftRestored}
      <div
        class="mb-4 rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm text-foreground"
        role="status"
      >
        Recuperamos el borrador de tu respuesta sin guardar.
      </div>
    {/if}
    {#if error}
      <div
        class="mb-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        role="alert"
      >
        {error}
      </div>
    {/if}

    <form
      id="purchase-quotation-response-form"
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
              aria-invalid={Boolean(validation.quotationDate)}
              aria-describedby={validation.quotationDate
                ? 'quotation-response-date-error'
                : undefined}
              oninput={(event) => {
                quotationDate = (event.currentTarget as HTMLInputElement).value;
                persistResponseDraft({ quotationDate });
              }}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
            {#if validation.quotationDate}
              <p id="quotation-response-date-error" class="mt-1 text-xs text-danger">
                {validation.quotationDate}
              </p>
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
              oninput={(event) => {
                validUntil = (event.currentTarget as HTMLInputElement).value;
                persistResponseDraft({ validUntil });
              }}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
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
              aria-invalid={Boolean(validation.deliveryDays)}
              aria-describedby={validation.deliveryDays
                ? 'quotation-response-delivery-days-error'
                : undefined}
              oninput={(event) => {
                deliveryDays = (event.currentTarget as HTMLInputElement).value;
                persistResponseDraft({ deliveryDays });
              }}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
            {#if validation.deliveryDays}
              <p id="quotation-response-delivery-days-error" class="mt-1 text-xs text-danger">
                {validation.deliveryDays}
              </p>
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
              oninput={(event) => {
                paymentTerms = (event.currentTarget as HTMLInputElement).value;
                persistResponseDraft({ paymentTerms });
              }}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              placeholder="Ej. 30 días crédito"
            />
          </div>
        </div>
      </Card>

      <Card class="overflow-hidden p-0">
        <div class="border-b border-border px-4 py-3">
          <h2 class="text-sm font-semibold text-foreground">Líneas cotizadas</h2>
          <p class="mt-1 text-xs text-foreground-muted">
            «Cantidad ofrecida» es lo que el proveedor cotiza. «Disponible» es lo que confirma que
            puede entregar ahora; si informas una cantidad, no podrás adjudicar más que eso. Déjalo
            vacío si coincide con lo ofrecido.
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
                  <h3 id={`response-line-title-${index}`} class="font-medium text-foreground">
                    {lineLabel(line)}
                  </h3>
                  <p class="mt-1 text-xs text-foreground-muted">
                    Unidad {snapshotFor(line.id)?.unit_name ?? `#${line.unitId}`} · solicitada {line.quantity}
                  </p>
                </div>

                <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  <div>
                    <label
                      for={`response-offered-${index}`}
                      class="mb-1 block text-xs font-medium text-foreground"
                    >
                      Cantidad ofrecida
                    </label>
                    <input
                      id={`response-offered-${index}`}
                      type="number"
                      min="0"
                      max={line.quantity}
                      step="0.000001"
                      value={line.offeredQuantity}
                      aria-invalid={Boolean(validation[`offeredQuantity-${index}`])}
                      aria-describedby={validation[`offeredQuantity-${index}`]
                        ? `response-line-title-${index} response-offered-help-${index} response-offered-error-${index}`
                        : `response-line-title-${index} response-offered-help-${index}`}
                      oninput={(event) =>
                        updateLine(
                          index,
                          'offeredQuantity',
                          (event.currentTarget as HTMLInputElement).value
                        )}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    />
                    {#if validation[`offeredQuantity-${index}`]}
                      <p id={`response-offered-error-${index}`} class="mt-1 text-xs text-danger">
                        {validation[`offeredQuantity-${index}`]}
                      </p>
                    {/if}
                    <p
                      id={`response-offered-help-${index}`}
                      class="mt-1 text-xs text-foreground-muted"
                    >
                      Solicitada: {line.quantity}. Puedes ofrecer una cantidad menor.
                    </p>
                  </div>

                  <div>
                    <label
                      for={`response-price-${index}`}
                      class="mb-1 block text-xs font-medium text-foreground"
                    >
                      Precio unitario
                    </label>
                    <input
                      id={`response-price-${index}`}
                      type="number"
                      min="0"
                      step="0.000001"
                      value={line.unitPrice}
                      aria-invalid={Boolean(validation[`unitPrice-${index}`])}
                      aria-describedby={validation[`unitPrice-${index}`]
                        ? `response-line-title-${index} response-price-error-${index}`
                        : `response-line-title-${index}`}
                      oninput={(event) =>
                        updateLine(
                          index,
                          'unitPrice',
                          (event.currentTarget as HTMLInputElement).value
                        )}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    />
                    {#if validation[`unitPrice-${index}`]}
                      <p id={`response-price-error-${index}`} class="mt-1 text-xs text-danger">
                        {validation[`unitPrice-${index}`]}
                      </p>
                    {/if}
                  </div>

                  <div>
                    <label
                      for={`response-discount-${index}`}
                      class="mb-1 block text-xs font-medium text-foreground"
                    >
                      Descuento total ({quotation.currency})
                    </label>
                    <input
                      id={`response-discount-${index}`}
                      type="number"
                      min="0"
                      step="0.000001"
                      value={line.discount}
                      aria-invalid={Boolean(validation[`discount-${index}`])}
                      aria-describedby={validation[`discount-${index}`]
                        ? `response-line-title-${index} response-discount-help-${index} response-discount-error-${index}`
                        : `response-line-title-${index} response-discount-help-${index}`}
                      oninput={(event) =>
                        updateLine(
                          index,
                          'discount',
                          (event.currentTarget as HTMLInputElement).value
                        )}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    />
                    <p
                      id={`response-discount-help-${index}`}
                      class="mt-1 text-xs text-foreground-muted"
                    >
                      Importe total de descuento de esta línea, expresado en dinero.
                    </p>
                    {#if validation[`discount-${index}`]}
                      <p id={`response-discount-error-${index}`} class="mt-1 text-xs text-danger">
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
                      type="number"
                      min="0"
                      max="100"
                      step="0.000001"
                      value={line.taxRate}
                      aria-invalid={Boolean(validation[`taxRate-${index}`])}
                      aria-describedby={validation[`taxRate-${index}`]
                        ? `response-line-title-${index} response-tax-error-${index}`
                        : `response-line-title-${index}`}
                      oninput={(event) =>
                        updateLine(
                          index,
                          'taxRate',
                          (event.currentTarget as HTMLInputElement).value
                        )}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    />
                    {#if validation[`taxRate-${index}`]}
                      <p id={`response-tax-error-${index}`} class="mt-1 text-xs text-danger">
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
                      type="number"
                      min="0"
                      step="1"
                      value={line.deliveryDays}
                      aria-invalid={Boolean(validation[`deliveryDays-${index}`])}
                      aria-describedby={validation[`deliveryDays-${index}`]
                        ? `response-line-title-${index} response-delivery-error-${index}`
                        : `response-line-title-${index}`}
                      oninput={(event) =>
                        updateLine(
                          index,
                          'deliveryDays',
                          (event.currentTarget as HTMLInputElement).value
                        )}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    />
                    {#if validation[`deliveryDays-${index}`]}
                      <p id={`response-delivery-error-${index}`} class="mt-1 text-xs text-danger">
                        {validation[`deliveryDays-${index}`]}
                      </p>
                    {/if}
                  </div>

                  <div>
                    <label
                      for={`response-available-${index}`}
                      class="mb-1 block text-xs font-medium text-foreground"
                    >
                      Disponible ahora
                    </label>
                    <input
                      id={`response-available-${index}`}
                      type="number"
                      min="0"
                      step="0.000001"
                      value={line.availableQuantity}
                      aria-invalid={Boolean(validation[`availableQuantity-${index}`])}
                      aria-describedby={validation[`availableQuantity-${index}`]
                        ? `response-line-title-${index} response-available-help-${index} response-available-error-${index}`
                        : `response-line-title-${index} response-available-help-${index}`}
                      oninput={(event) =>
                        updateLine(
                          index,
                          'availableQuantity',
                          (event.currentTarget as HTMLInputElement).value
                        )}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    />
                    {#if validation[`availableQuantity-${index}`]}
                      <p id={`response-available-error-${index}`} class="mt-1 text-xs text-danger">
                        {validation[`availableQuantity-${index}`]}
                      </p>
                    {/if}
                    <p
                      id={`response-available-help-${index}`}
                      class="mt-1 text-xs text-foreground-muted"
                    >
                      Vacío = igual a lo ofrecido. Si es menor, limita lo que se puede adjudicar.
                    </p>
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
                    aria-describedby={`response-line-title-${index}`}
                    maxlength="2000"
                    value={line.notes}
                    oninput={(event) =>
                      updateLine(index, 'notes', (event.currentTarget as HTMLInputElement).value)}
                    class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
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
          Notas de respuesta
        </label>
        <textarea
          id="quotation-response-notes"
          maxlength="4000"
          rows="3"
          value={notes}
          oninput={(event) => {
            notes = (event.currentTarget as HTMLTextAreaElement).value;
            persistResponseDraft({ notes });
          }}
          class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        ></textarea>
      </Card>
    </form>

    <div class="mt-5">
      <PurchaseQuotationDocuments
        quotationId={quotation.id}
        quotationStatus={quotation.status}
        {consolidationId}
      />
    </div>

    <div class="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <Button
        type="button"
        variant="secondary"
        onclick={() => {
          clearResponseDraft(id);
          goto(
            `/purchase-quotations/${id}${consolidationId ? `?consolidation_id=${consolidationId}` : ''}`
          );
        }}
      >
        Cancelar
      </Button>
      <Button
        form="purchase-quotation-response-form"
        type="submit"
        disabled={saving || lines.length === 0}
      >
        {saving ? 'Guardando…' : 'Registrar respuesta'}
      </Button>
    </div>
  {/if}
</div>
