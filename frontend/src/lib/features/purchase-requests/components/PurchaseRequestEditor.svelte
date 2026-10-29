<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import PurchaseRequestProductPicker from '$lib/features/purchase-requests/components/PurchaseRequestProductPicker.svelte';
  import { api, HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchaseRequestsApi } from '$lib/api/purchase-requests';
  import { getWarehouses } from '$lib/services/warehouses';
  import { branch } from '$lib/stores/branch.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Product } from '$lib/types/catalog';
  import type { PurchaseRequestDetailInput } from '$lib/types/purchase-request';
  import type { Warehouse } from '$lib/features/warehouses/types';

  interface DraftLine {
    productId: string;
    productSearch: string;
    quantity: string;
    description: string;
    notes: string;
  }

  const emptyLine = (): DraftLine => ({
    productId: '',
    productSearch: '',
    quantity: '1',
    description: '',
    notes: ''
  });

  let branchId = $state(branch.id ?? branch.branches[0]?.id ?? '');
  let warehouseId = $state('');
  let requiredDate = $state('');
  let justification = $state('');
  let notes = $state('');
  let lines = $state<DraftLine[]>([emptyLine()]);
  let warehouses = $state<Warehouse[]>([]);
  let products = $state<Product[]>([]);
  let productCurrentPage = $state(1);
  let productPages = $state(1);
  let loadingMoreProducts = $state(false);
  let loadingOptions = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let productPageError = $state<string | null>(null);
  let validation = $state<Record<string, string>>({});
  let loadGeneration = 0;
  let branchContextReady = $state(false);
  let availableBranches = $state(branch.branches.filter((item) => item.is_active));
  let loadedCompanyId: string | null = null;

  let canCreate = $derived(
    permissions.hasAnyPermission(['purchase_requests:create', 'purchase_requests:manage'])
  );

  async function loadOptions(selectedBranchId: string) {
    const generation = ++loadGeneration;
    loadingOptions = true;
    loadingMoreProducts = false;
    error = null;
    productPageError = null;

    try {
      const [warehousePage, productPageResponse] = await Promise.all([
        getWarehouses({
          branchId: selectedBranchId || undefined,
          page: 1,
          size: 100,
          status: 'active'
        }),
        catalogApi.listProducts({
          active_only: true,
          page: 1,
          size: 100
        })
      ]);

      if (generation !== loadGeneration) return;

      warehouses = warehousePage.items.filter(
        (warehouse) => !selectedBranchId || warehouse.branchId === selectedBranchId
      );
      products = productPageResponse.items.filter((product) => product.can_purchase !== false);
      productCurrentPage = productPageResponse.meta.page;
      productPages = productPageResponse.meta.pages;

      if (!warehouses.some((warehouse) => warehouse.id === warehouseId)) {
        warehouseId = warehouses[0]?.id ?? '';
      }
    } catch (err: unknown) {
      if (generation !== loadGeneration) return;

      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudieron cargar las opciones del formulario.';
    } finally {
      if (generation === loadGeneration) loadingOptions = false;
    }
  }

  async function loadBranchContext(companyId: string) {
    branchContextReady = false;
    loadingOptions = true;
    error = null;

    try {
      const context = await api.operationalContext.get(companyId);
      if (company.id !== companyId) return;

      branch.configure(context);
      availableBranches = context.branches.filter((item) => item.is_active);
      if (!availableBranches.some((item) => item.id === branchId)) {
        branchId = branch.id ?? context.last_branch_id ?? availableBranches[0]?.id ?? '';
      }
      branchContextReady = true;
    } catch (err: unknown) {
      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudieron cargar las sucursales autorizadas.';
    } finally {
      if (!branchContextReady) loadingOptions = false;
    }
  }

  async function loadMoreProducts() {
    if (loadingMoreProducts || productCurrentPage >= productPages) return;

    const generation = loadGeneration;
    loadingMoreProducts = true;
    productPageError = null;

    try {
      const nextPage = await catalogApi.listProducts({
        active_only: true,
        page: productCurrentPage + 1,
        size: 100
      });

      if (generation !== loadGeneration) return;

      const knownProductIds = new Set(products.map((product) => product.id_product));
      products = [
        ...products,
        ...nextPage.items.filter(
          (product) => product.can_purchase !== false && !knownProductIds.has(product.id_product)
        )
      ];
      productCurrentPage = nextPage.meta.page;
      productPages = nextPage.meta.pages;
    } catch (err: unknown) {
      if (generation !== loadGeneration) return;

      productPageError =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudieron cargar más productos.';
    } finally {
      if (generation === loadGeneration) loadingMoreProducts = false;
    }
  }

  $effect(() => {
    const companyId = company.id;
    if (!companyId || companyId === loadedCompanyId) return;
    loadedCompanyId = companyId;
    void loadBranchContext(companyId);
  });

  $effect(() => {
    const selectedBranchId = branchId;
    if (!branchContextReady) return;
    void loadOptions(selectedBranchId);
  });

  function updateLine(index: number, patch: Partial<DraftLine>) {
    lines = lines.map((line, currentIndex) =>
      currentIndex === index ? { ...line, ...patch } : line
    );
  }

  function addLine() {
    lines = [...lines, emptyLine()];
  }

  function removeLine(index: number) {
    if (lines.length === 1) return;
    lines = lines.filter((_, currentIndex) => currentIndex !== index);
  }

  function validate() {
    const next: Record<string, string> = {};

    if (!branchId) next.branchId = 'Selecciona una sucursal.';
    if (!warehouseId) next.warehouseId = 'Selecciona un almacén.';
    if (!justification.trim()) next.justification = 'La justificación es obligatoria.';

    lines.forEach((line, index) => {
      if (!line.productId) next[`product-${index}`] = 'Selecciona un producto.';

      const quantity = Number(line.quantity);
      if (!Number.isFinite(quantity) || quantity <= 0) {
        next[`quantity-${index}`] = 'La cantidad debe ser mayor que cero.';
      }
    });

    validation = next;
    return Object.keys(next).length === 0;
  }

  function focusFirstInvalidField() {
    const firstError = Object.keys(validation)[0];
    if (!firstError) return;

    const inputId =
      firstError === 'branchId'
        ? 'purchase-request-branch'
        : firstError === 'warehouseId'
          ? 'purchase-request-warehouse'
          : firstError === 'justification'
            ? 'purchase-request-justification'
            : firstError.startsWith('product-')
              ? `purchase-request-product-${firstError.slice('product-'.length)}-search`
              : `purchase-request-${firstError}`;

    window.requestAnimationFrame(() => document.getElementById(inputId)?.focus());
  }

  function detailPayload(): PurchaseRequestDetailInput[] {
    return lines.map((line) => ({
      product_id: Number(line.productId),
      quantity: Number(line.quantity),
      description: line.description.trim() || null,
      notes: line.notes.trim() || null
    }));
  }

  async function submit() {
    if (!canCreate || saving) return;
    if (!validate()) {
      focusFirstInvalidField();
      return;
    }

    saving = true;
    error = null;

    try {
      const created = await purchaseRequestsApi.create({
        branch_id: branchId,
        warehouse_id: warehouseId,
        required_date: requiredDate ? `${requiredDate}T12:00:00-06:00` : null,
        justification: justification.trim(),
        notes: notes.trim() || null,
        details: detailPayload()
      });

      await goto(`/purchase-requests/${created.id}`);
    } catch (err: unknown) {
      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudo crear la solicitud de compra.';
    } finally {
      saving = false;
    }
  }
</script>

<div class="min-h-full bg-background px-4 pb-8 pt-4 sm:px-6 sm:pt-6 md:px-8 md:pt-8">
  <header class="mb-6 flex items-center gap-3 border-b border-border pb-4">
    <a
      href="/purchase-requests"
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-muted hover:text-foreground"
      aria-label="Volver a solicitudes de compra"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <path d="M19 12H5M12 19l-7-7 7-7" />
      </svg>
    </a>
    <div>
      <h1 class="text-xl font-semibold text-foreground">Nueva solicitud de compra</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Registra un borrador para iniciar el flujo de compras.
      </p>
    </div>
  </header>

  {#if !canCreate}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-foreground"
      role="alert"
    >
      Tu rol no tiene permiso para crear solicitudes de compra. Pide a un administrador que habilite la creación para tu rol.
    </div>
  {:else if loadingOptions}
    <div class="space-y-4" aria-label="Cargando formulario de solicitud">
      <div class="skeleton h-40 rounded-xl"></div>
      <div class="skeleton h-64 rounded-xl"></div>
    </div>
  {:else}
    {#if error}
      <div
        class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-foreground"
        role="alert"
      >
        {error}
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onclick={() => {
            if (company.id) void loadBranchContext(company.id);
          }}
          disabled={loadingOptions}
        >
          Reintentar
        </Button>
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
              for="purchase-request-branch"
              class="mb-1 block text-sm font-medium text-foreground"
            >
              Sucursal <span class="text-danger">*</span>
            </label>
            <select
              id="purchase-request-branch"
              aria-label="Sucursal"
              aria-invalid={validation.branchId ? 'true' : undefined}
              aria-describedby={validation.branchId ? 'purchase-request-branch-error' : undefined}
              bind:value={branchId}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <option value="">Selecciona una sucursal</option>
              {#each availableBranches as item}
                <option value={item.id}>{item.code ? `${item.code} — ` : ''}{item.name}</option>
              {/each}
            </select>
            {#if validation.branchId}
              <p id="purchase-request-branch-error" class="mt-1 text-xs text-danger">
                {validation.branchId}
              </p>
            {/if}
          </div>

          <div>
            <label
              for="purchase-request-warehouse"
              class="mb-1 block text-sm font-medium text-foreground"
            >
              Almacén <span class="text-danger">*</span>
            </label>
            <select
              id="purchase-request-warehouse"
              aria-label="Almacén"
              aria-invalid={validation.warehouseId ? 'true' : undefined}
              aria-describedby={validation.warehouseId
                ? 'purchase-request-warehouse-error'
                : undefined}
              bind:value={warehouseId}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <option value="">Selecciona un almacén</option>
              {#each warehouses as warehouse}
                <option value={warehouse.id}>{warehouse.code} — {warehouse.name}</option>
              {/each}
            </select>
            {#if validation.warehouseId}
              <p id="purchase-request-warehouse-error" class="mt-1 text-xs text-danger">
                {validation.warehouseId}
              </p>
            {/if}
          </div>

          <div>
            <label
              for="purchase-request-required-date"
              class="mb-1 block text-sm font-medium text-foreground"
            >
              Fecha requerida
            </label>
            <input
              id="purchase-request-required-date"
              aria-label="Fecha requerida"
              type="date"
              bind:value={requiredDate}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
          </div>

          <div>
            <label
              for="purchase-request-justification"
              class="mb-1 block text-sm font-medium text-foreground"
            >
              Justificación <span class="text-danger">*</span>
            </label>
            <input
              id="purchase-request-justification"
              aria-label="Justificación"
              aria-invalid={validation.justification ? 'true' : undefined}
              aria-describedby={validation.justification
                ? 'purchase-request-justification-error'
                : undefined}
              bind:value={justification}
              maxlength="4000"
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              placeholder="Motivo de la solicitud"
            />
            {#if validation.justification}
              <p id="purchase-request-justification-error" class="mt-1 text-xs text-danger">
                {validation.justification}
              </p>
            {/if}
          </div>
        </div>

        <div class="mt-4">
          <label
            for="purchase-request-notes"
            class="mb-1 block text-sm font-medium text-foreground"
          >
            Notas
          </label>
          <textarea
            id="purchase-request-notes"
            aria-label="Notas"
            bind:value={notes}
            maxlength="4000"
            rows="3"
            class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            placeholder="Observaciones opcionales"
          ></textarea>
        </div>
      </Card>

      <Card class="overflow-hidden p-0">
        <div class="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div>
            <h2 class="text-sm font-semibold text-foreground">Productos solicitados</h2>
            <p class="mt-1 text-xs text-foreground-muted">Agrega entre 1 y 100 líneas.</p>
          </div>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onclick={addLine}
            disabled={lines.length >= 100}
          >
            Agregar línea
          </Button>
        </div>

        <div class="divide-y divide-border">
          {#each lines as line, index (index)}
            <div class="grid gap-3 p-4 lg:grid-cols-[2fr_1fr_2fr_2fr_auto] lg:items-start">
              <PurchaseRequestProductPicker
                id={`purchase-request-product-${index}`}
                label={`Producto ${index + 1}`}
                {products}
                bind:value={line.productId}
                bind:query={line.productSearch}
                hasMoreProducts={productCurrentPage < productPages}
                {loadingMoreProducts}
                loadMoreError={productPageError}
                onloadmore={loadMoreProducts}
                error={validation[`product-${index}`]}
                onselect={() => {
                  const nextValidation = { ...validation };
                  delete nextValidation[`product-${index}`];
                  validation = nextValidation;
                }}
              />

              <div>
                <label
                  for={`purchase-request-quantity-${index}`}
                  class="mb-1 block text-sm font-medium text-foreground"
                >
                  Cantidad <span class="text-danger">*</span>
                </label>
                <input
                  id={`purchase-request-quantity-${index}`}
                  aria-label={`Cantidad ${index + 1}`}
                  aria-invalid={validation[`quantity-${index}`] ? 'true' : undefined}
                  aria-describedby={validation[`quantity-${index}`]
                    ? `purchase-request-quantity-${index}-error`
                    : undefined}
                  type="number"
                  min="0.000001"
                  step="0.000001"
                  value={line.quantity}
                  oninput={(event) =>
                    updateLine(index, {
                      quantity: (event.currentTarget as HTMLInputElement).value
                    })}
                  class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                />
                {#if validation[`quantity-${index}`]}
                  <p
                    id={`purchase-request-quantity-${index}-error`}
                    class="mt-1 text-xs text-danger"
                  >
                    {validation[`quantity-${index}`]}
                  </p>
                {/if}
              </div>

              <div>
                <label
                  for={`purchase-request-description-${index}`}
                  class="mb-1 block text-sm font-medium text-foreground"
                >
                  Descripción
                </label>
                <input
                  id={`purchase-request-description-${index}`}
                  aria-label={`Descripción ${index + 1}`}
                  maxlength="1000"
                  value={line.description}
                  oninput={(event) =>
                    updateLine(index, {
                      description: (event.currentTarget as HTMLInputElement).value
                    })}
                  class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                />
              </div>

              <div>
                <label
                  for={`purchase-request-line-notes-${index}`}
                  class="mb-1 block text-sm font-medium text-foreground"
                >
                  Notas
                </label>
                <input
                  id={`purchase-request-line-notes-${index}`}
                  aria-label={`Notas de línea ${index + 1}`}
                  maxlength="2000"
                  value={line.notes}
                  oninput={(event) =>
                    updateLine(index, {
                      notes: (event.currentTarget as HTMLInputElement).value
                    })}
                  class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                />
              </div>

              <Button
                type="button"
                size="sm"
                variant="secondary"
                class="lg:mt-6"
                disabled={lines.length === 1}
                onclick={() => removeLine(index)}
              >
                Quitar
              </Button>
            </div>
          {/each}
        </div>
      </Card>

      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" onclick={() => goto('/purchase-requests')}>
          Cancelar
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? 'Guardando…' : 'Crear borrador'}
        </Button>
      </div>
    </form>
  {/if}
</div>
