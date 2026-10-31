<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { catalogApi } from '$lib/api/catalog';
  import { HttpError } from '$lib/api/client';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { purchaseRequestsApi } from '$lib/api/purchase-requests';
  import { suppliersApi } from '$lib/api/suppliers';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { PurchaseRequest, PurchaseRequestStatus } from '$lib/types/purchase-request';
  import type { Currency, Supplier } from '$lib/types/supplier';

  interface DraftLine {
    detailId: string;
    productId: number;
    unitId: number;
    sourceQuantity: string;
    quantity: string;
    description: string | null;
    included: boolean;
  }

  interface DraftRequest {
    requestId: string;
    code: string;
    status: PurchaseRequestStatus;
    lines: DraftLine[];
  }

  interface Props {
    initialRequestId?: string;
  }

  let { initialRequestId }: Props = $props();

  const QUOTABLE_STATUSES: PurchaseRequestStatus[] = ['approved', 'partially_quoted', 'quoted'];

  const REQUEST_STATUS_LABELS: Partial<Record<PurchaseRequestStatus, string>> = {
    approved: 'Aprobada',
    partially_quoted: 'Parcialmente cotizada',
    quoted: 'Cotizada'
  };

  let suppliers = $state<Supplier[]>([]);
  let currencies = $state<Currency[]>([]);
  let availableRequests = $state<PurchaseRequest[]>([]);
  let productNames = $state<Map<number, string>>(new Map());
  let productNamesLoading = $state<Set<number>>(new Set());
  let productNamesUnavailable = $state<Set<number>>(new Set());
  let supplierId = $state('');
  let currency = $state('');
  let notes = $state('');
  let requestToAdd = $state('');
  let linkedRequests = $state<DraftRequest[]>([]);
  let loadingOptions = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let validation = $state<Record<string, string>>({});
  let requestNotice = $state<string | null>(null);
  let loadGeneration = 0;

  let canManage = $derived(permissions.hasPermission('purchase_quotations:manage'));
  let requestOptions = $derived(
    availableRequests.filter(
      (request) => !linkedRequests.some((linked) => linked.requestId === request.id)
    )
  );

  function errorMessage(cause: unknown, fallback: string): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return fallback;
  }

  function requestStatusLabel(status: PurchaseRequestStatus): string {
    return REQUEST_STATUS_LABELS[status] ?? status;
  }

  async function loadOptions(
    requestId: string | undefined = initialRequestId,
    branchId: string | null = branch.id
  ) {
    const generation = ++loadGeneration;
    loadingOptions = true;
    error = null;
    requestNotice = null;

    try {
      const requestPagesPromise = Promise.all(
        QUOTABLE_STATUSES.map((status) =>
          purchaseRequestsApi.list({
            status,
            page: 1,
            size: 100,
            ...(branchId ? { branch_id: branchId } : {})
          })
        )
      );

      const [supplierPage, currencyData, requestPages] = await Promise.all([
        suppliersApi.listSuppliers({
          active_only: true,
          page: 1,
          size: 100
        }),
        suppliersApi.currencies(),
        requestPagesPromise
      ]);

      if (generation !== loadGeneration) return;

      suppliers = supplierPage.items.filter(
        (supplier) => supplier.is_active && supplier.supplier_status === 'approved'
      );
      const activeCurrencies = currencyData.filter((item) => item.is_active);
      currencies = [
        ...activeCurrencies.filter((item) => item.code === 'USD'),
        ...activeCurrencies.filter((item) => item.code !== 'USD')
      ];

      const requestMap = new Map<string, PurchaseRequest>();
      for (const requestPage of requestPages) {
        for (const request of requestPage.items) requestMap.set(request.id, request);
      }
      availableRequests = [...requestMap.values()];

      if (requestId) {
        const requestedItem = availableRequests.find((request) => request.id === requestId);
        if (requestedItem) {
          addRequest(requestId);
        } else {
          requestNotice =
            'La solicitud vinculada no está disponible en este contexto o ya no está lista para cotizar.';
        }
      }

      if (!suppliers.some((supplier) => String(supplier.id_supplier) === supplierId)) {
        supplierId = suppliers[0] ? String(suppliers[0].id_supplier) : '';
      }

      if (!currencies.some((item) => item.code === currency)) {
        currency = '';
      }
    } catch (cause: unknown) {
      if (generation !== loadGeneration) return;
      error = errorMessage(cause, 'No se pudieron cargar las opciones de la cotización.');
    } finally {
      if (generation === loadGeneration) loadingOptions = false;
    }
  }

  $effect(() => {
    const requestId = initialRequestId;
    const branchId = branch.id;
    if (canManage) {
      void loadOptions(requestId, branchId);
    } else {
      loadingOptions = false;
    }
  });

  function handleSupplierChange(event: Event) {
    supplierId = (event.currentTarget as HTMLSelectElement).value;
  }

  function handleCurrencyChange(event: Event) {
    currency = (event.currentTarget as HTMLSelectElement).value;
  }

  function handleRequestSelection(event: Event) {
    requestToAdd = (event.currentTarget as HTMLSelectElement).value;
  }

  function addRequest(requestId = requestToAdd) {
    const request = availableRequests.find((item) => item.id === requestId);
    if (!request || linkedRequests.some((linked) => linked.requestId === request.id)) return;

    void loadProductNames(request.details.map((detail) => detail.product_id));

    linkedRequests = [
      ...linkedRequests,
      {
        requestId: request.id,
        code: request.code,
        status: request.status,
        lines: request.details.map((detail) => ({
          detailId: detail.id,
          productId: detail.product_id,
          unitId: detail.unit_id,
          sourceQuantity: detail.quantity,
          quantity: detail.quantity,
          description: detail.description,
          included: true
        }))
      }
    ];

    requestToAdd = '';
    validation = {};
  }

  async function loadProductNames(productIds: number[]) {
    const pendingIds = new Set(productNamesLoading);
    const unavailableIds = new Set(productNamesUnavailable);
    const missingIds = [...new Set(productIds)].filter(
      (id) => !productNames.has(id) && !pendingIds.has(id) && !unavailableIds.has(id)
    );

    if (missingIds.length === 0) return;

    for (const id of missingIds) pendingIds.add(id);
    productNamesLoading = pendingIds;

    const results = await Promise.all(
      missingIds.map(async (id) => ({
        id,
        product: await catalogApi.getProduct(id).catch(() => null)
      }))
    );

    const nextNames = new Map(productNames);
    const nextLoading = new Set(productNamesLoading);
    const nextUnavailable = new Set(productNamesUnavailable);

    for (const { id, product } of results) {
      nextLoading.delete(id);
      if (product?.name.trim()) {
        nextNames.set(id, product.name.trim());
      } else {
        nextUnavailable.add(id);
      }
    }

    productNames = nextNames;
    productNamesLoading = nextLoading;
    productNamesUnavailable = nextUnavailable;
  }

  function removeRequest(requestIndex: number) {
    linkedRequests = linkedRequests.filter((_, index) => index !== requestIndex);
    validation = {};
  }

  function updateLine(
    requestIndex: number,
    lineIndex: number,
    patch: Partial<Pick<DraftLine, 'quantity' | 'included'>>
  ) {
    linkedRequests = linkedRequests.map((request, currentRequestIndex) => {
      if (currentRequestIndex !== requestIndex) return request;

      return {
        ...request,
        lines: request.lines.map((line, currentLineIndex) =>
          currentLineIndex === lineIndex ? { ...line, ...patch } : line
        )
      };
    });
  }

  function validate(): boolean {
    const next: Record<string, string> = {};

    if (!supplierId) next.supplier = 'Selecciona un proveedor.';
    if (!currency) next.currency = 'Selecciona una moneda.';
    if (linkedRequests.length === 0) {
      next.requests = 'Agrega al menos una solicitud de compra.';
    }

    linkedRequests.forEach((request, requestIndex) => {
      const includedLines = request.lines.filter((line) => line.included);

      if (includedLines.length === 0) {
        next[`request-${requestIndex}`] = 'Selecciona al menos una línea para cotizar.';
      }

      request.lines.forEach((line, lineIndex) => {
        if (!line.included) return;

        const quantity = Number(line.quantity);
        if (!Number.isFinite(quantity) || quantity <= 0) {
          next[`quantity-${requestIndex}-${lineIndex}`] = 'La cantidad debe ser mayor que cero.';
        }
      });
    });

    validation = next;
    return Object.keys(next).length === 0;
  }

  async function submit() {
    if (!canManage || saving || !validate()) return;

    saving = true;
    error = null;

    try {
      const created = await purchaseQuotationsApi.create({
        supplier_id: Number(supplierId),
        currency,
        requests: linkedRequests.map((request) => ({
          purchase_request_id: request.requestId,
          lines: request.lines
            .filter((line) => line.included)
            .map((line) => ({
              purchase_request_detail_id: line.detailId,
              quantity: Number(line.quantity)
            }))
        })),
        notes: notes.trim() || null
      });

      await goto(`/purchase-quotations/${created.id}`);
    } catch (cause: unknown) {
      error = errorMessage(cause, 'No se pudo crear la cotización de compra.');
    } finally {
      saving = false;
    }
  }
</script>

<div class="min-h-full bg-background px-4 pb-8 pt-4 sm:px-6 sm:pt-6 md:px-8 md:pt-8">
  <header class="mb-6 flex items-center gap-3 border-b border-border pb-4">
    <a
      href="/purchase-quotations"
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-muted hover:text-foreground"
      aria-label="Volver a cotizaciones de compra"
    >
      <span aria-hidden="true">←</span>
    </a>
    <div>
      <h1 class="text-xl font-semibold text-foreground">Nueva cotización de compra</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Crea un borrador de solicitud de cotización para uno o más requerimientos aprobados.
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
  {:else if loadingOptions}
    <div class="space-y-4" aria-label="Cargando formulario de cotización">
      <div class="skeleton h-44 rounded-xl"></div>
      <div class="skeleton h-64 rounded-xl"></div>
    </div>
  {:else}
    {#if error}
      <div
        class="mb-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        role="alert"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <span>{error}</span>
          <Button type="button" size="sm" variant="secondary" onclick={() => loadOptions()}>
            Reintentar carga
          </Button>
        </div>
      </div>
    {/if}

    {#if requestNotice}
      <div
        class="rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground-muted"
        role="status"
      >
        {requestNotice}
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
        <h2 class="mb-4 text-sm font-semibold text-foreground">Datos generales</h2>

        <div class="grid gap-4 md:grid-cols-2">
          <div>
            <label
              for="purchase-quotation-supplier"
              class="mb-1 block text-sm font-medium text-foreground"
            >
              Proveedor <span class="text-danger">*</span>
            </label>
            <select
              id="purchase-quotation-supplier"
              aria-label="Proveedor"
              value={supplierId}
              onchange={handleSupplierChange}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
            >
              <option value="">Selecciona un proveedor</option>
              {#each suppliers as supplier (supplier.id_supplier)}
                <option value={String(supplier.id_supplier)}>
                  {supplier.code} — {supplier.name}
                </option>
              {/each}
            </select>
            {#if validation.supplier}
              <p class="mt-1 text-xs text-danger">{validation.supplier}</p>
            {/if}
            {#if suppliers.length === 0}
              <p class="mt-1 text-xs text-foreground-muted">
                No hay proveedores aprobados disponibles.
              </p>
            {/if}
          </div>

          <div>
            <label
              for="purchase-quotation-currency"
              class="mb-1 block text-sm font-medium text-foreground"
            >
              Moneda <span class="text-danger">*</span>
            </label>
            <select
              id="purchase-quotation-currency"
              aria-label="Moneda"
              value={currency}
              onchange={handleCurrencyChange}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
            >
              <option value="">Selecciona una moneda</option>
              {#each currencies as item (item.code)}
                <option value={item.code}>{item.code} — {item.name}</option>
              {/each}
            </select>
            {#if validation.currency}
              <p class="mt-1 text-xs text-danger">{validation.currency}</p>
            {/if}
          </div>
        </div>

        <div class="mt-4">
          <label
            for="purchase-quotation-notes"
            class="mb-1 block text-sm font-medium text-foreground"
          >
            Notas
          </label>
          <textarea
            id="purchase-quotation-notes"
            aria-label="Notas"
            bind:value={notes}
            maxlength="4000"
            rows="3"
            class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
            placeholder="Observaciones opcionales para el proveedor"
          ></textarea>
        </div>
      </Card>

      <Card class="overflow-hidden p-0">
        <div class="border-b border-border px-4 py-3">
          <h2 class="text-sm font-semibold text-foreground">Solicitudes a cotizar</h2>
          <p class="mt-1 text-xs text-foreground-muted">
            Puedes vincular solicitudes aprobadas o que ya tengan cotizaciones previas.
          </p>
        </div>

        <div class="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-end">
          <div class="min-w-0 flex-1">
            <label
              for="purchase-quotation-request"
              class="mb-1 block text-sm font-medium text-foreground"
            >
              Solicitud para agregar
            </label>
            <select
              id="purchase-quotation-request"
              aria-label="Solicitud para agregar"
              value={requestToAdd}
              onchange={handleRequestSelection}
              disabled={requestOptions.length === 0 || linkedRequests.length >= 100}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
            >
              <option value="">Selecciona una solicitud</option>
              {#each requestOptions as request (request.id)}
                <option value={request.id}>
                  {request.code} — {requestStatusLabel(request.status)}
                </option>
              {/each}
            </select>
          </div>

          <Button
            type="button"
            variant="secondary"
            onclick={() => addRequest()}
            disabled={!requestToAdd || linkedRequests.length >= 100}
          >
            Agregar solicitud
          </Button>
        </div>

        {#if validation.requests}
          <p class="border-b border-border px-4 py-3 text-sm text-danger">
            {validation.requests}
          </p>
        {/if}

        {#if linkedRequests.length === 0}
          <div class="p-8 text-center">
            <p class="font-medium text-foreground">Aún no has agregado solicitudes</p>
            <p class="mt-1 text-sm text-foreground-muted">
              Selecciona una solicitud disponible para definir las líneas a cotizar.
            </p>
          </div>
        {:else}
          <div class="divide-y divide-border">
            {#each linkedRequests as request, requestIndex (request.requestId)}
              <section class="p-4">
                <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 class="font-medium text-foreground">{request.code}</h3>
                    <p class="mt-1 text-xs text-foreground-muted">
                      {requestStatusLabel(request.status)}
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onclick={() => removeRequest(requestIndex)}
                  >
                    Quitar solicitud
                  </Button>
                </div>

                {#if validation[`request-${requestIndex}`]}
                  <p class="mb-3 text-sm text-danger">
                    {validation[`request-${requestIndex}`]}
                  </p>
                {/if}

                <div class="space-y-3">
                  {#each request.lines as line, lineIndex (line.detailId)}
                    <div
                      class="grid gap-3 rounded-lg border border-border bg-surface-muted/40 p-3 md:grid-cols-[auto_1fr_180px] md:items-start"
                    >
                      <div class="pt-1">
                        <input
                          id={`quotation-line-${requestIndex}-${lineIndex}`}
                          aria-label={`Incluir producto ${line.productId} de ${request.code}`}
                          type="checkbox"
                          checked={line.included}
                          onchange={(event) =>
                            updateLine(requestIndex, lineIndex, {
                              included: (event.currentTarget as HTMLInputElement).checked
                            })}
                          class="h-4 w-4 rounded border-border"
                        />
                      </div>

                      <label
                        for={`quotation-line-${requestIndex}-${lineIndex}`}
                        class="min-w-0 cursor-pointer"
                      >
                        <span class="block font-medium text-foreground">
                          Producto #{line.productId}
                          {#if productNames.has(line.productId)}
                            <span class="font-normal text-foreground-muted">
                              — {productNames.get(line.productId)}
                            </span>
                          {:else if productNamesLoading.has(line.productId)}
                            <span class="font-normal text-foreground-muted">— Cargando nombre…</span>
                          {:else if productNamesUnavailable.has(line.productId)}
                            <span class="font-normal text-foreground-subtle">— Nombre no disponible</span>
                          {/if}
                        </span>
                        <span class="mt-1 block text-xs text-foreground-muted">
                          Unidad #{line.unitId} · solicitado {line.sourceQuantity}
                        </span>
                        {#if line.description}
                          <span class="mt-1 block text-xs text-foreground-muted">
                            {line.description}
                          </span>
                        {/if}
                      </label>

                      <div>
                        <label
                          for={`quotation-quantity-${requestIndex}-${lineIndex}`}
                          class="mb-1 block text-xs font-medium text-foreground"
                        >
                          Cantidad a cotizar
                        </label>
                        <input
                          id={`quotation-quantity-${requestIndex}-${lineIndex}`}
                          aria-label={`Cantidad producto ${line.productId} de ${request.code}`}
                          type="number"
                          min="0.000001"
                          step="0.000001"
                          value={line.quantity}
                          disabled={!line.included}
                          oninput={(event) =>
                            updateLine(requestIndex, lineIndex, {
                              quantity: (event.currentTarget as HTMLInputElement).value
                            })}
                          class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
                        />
                        {#if validation[`quantity-${requestIndex}-${lineIndex}`]}
                          <p class="mt-1 text-xs text-danger">
                            {validation[`quantity-${requestIndex}-${lineIndex}`]}
                          </p>
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              </section>
            {/each}
          </div>
        {/if}
      </Card>

      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" onclick={() => goto('/purchase-quotations')}>
          Cancelar
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? 'Guardando…' : 'Crear borrador'}
        </Button>
      </div>
    </form>
  {/if}
</div>
