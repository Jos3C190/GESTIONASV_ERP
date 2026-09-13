<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchaseRequestsApi } from '$lib/api/purchase-requests';
  import { getWarehouses } from '$lib/services/warehouses';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Product } from '$lib/types/catalog';
  import type { PurchaseRequestDetailInput } from '$lib/types/purchase-request';
  import type { Warehouse } from '$lib/features/warehouses/types';

  interface DraftLine {
    productId: string;
    quantity: string;
    description: string;
    notes: string;
  }

  const emptyLine = (): DraftLine => ({
    productId: '',
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
  let loadingOptions = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let validation = $state<Record<string, string>>({});
  let loadGeneration = 0;

  let canManage = $derived(permissions.hasPermission('purchase_requests:manage'));

  async function loadOptions(selectedBranchId: string) {
    const generation = ++loadGeneration;
    loadingOptions = true;
    error = null;

    try {
      const [warehousePage, productPage] = await Promise.all([
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
      products = productPage.items.filter((product) => product.can_purchase !== false);

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

  $effect(() => {
    void loadOptions(branchId);
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

  function detailPayload(): PurchaseRequestDetailInput[] {
    return lines.map((line) => ({
      product_id: Number(line.productId),
      quantity: Number(line.quantity),
      description: line.description.trim() || null,
      notes: line.notes.trim() || null
    }));
  }

  async function submit() {
    if (!canManage || saving || !validate()) return;

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

  {#if !canManage}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      No tienes permiso para gestionar solicitudes de compra.
    </div>
  {:else if loadingOptions}
    <div class="space-y-4" aria-label="Cargando formulario de solicitud">
      <div class="skeleton h-40 rounded-xl"></div>
      <div class="skeleton h-64 rounded-xl"></div>
    </div>
  {:else}
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
              bind:value={branchId}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
            >
              <option value="">Selecciona una sucursal</option>
              {#each branch.branches.filter((item) => item.is_active) as item}
                <option value={item.id}>{item.code ? `${item.code} — ` : ''}{item.name}</option>
              {/each}
            </select>
            {#if validation.branchId}
              <p class="mt-1 text-xs text-danger">{validation.branchId}</p>
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
              bind:value={warehouseId}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
            >
              <option value="">Selecciona un almacén</option>
              {#each warehouses as warehouse}
                <option value={warehouse.id}>{warehouse.code} — {warehouse.name}</option>
              {/each}
            </select>
            {#if validation.warehouseId}
              <p class="mt-1 text-xs text-danger">{validation.warehouseId}</p>
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
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
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
              bind:value={justification}
              maxlength="4000"
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
              placeholder="Motivo de la solicitud"
            />
            {#if validation.justification}
              <p class="mt-1 text-xs text-danger">{validation.justification}</p>
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
            class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
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
              <div>
                <label
                  for={`purchase-request-product-${index}`}
                  class="mb-1 block text-sm font-medium text-foreground"
                >
                  Producto {index + 1} <span class="text-danger">*</span>
                </label>
                <select
                  id={`purchase-request-product-${index}`}
                  aria-label={`Producto ${index + 1}`}
                  value={line.productId}
                  onchange={(event) =>
                    updateLine(index, {
                      productId: (event.currentTarget as HTMLSelectElement).value
                    })}
                  class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
                >
                  <option value="">Selecciona un producto</option>
                  {#each products as product}
                    <option value={product.id_product}>{product.sku} — {product.name}</option>
                  {/each}
                </select>
                {#if validation[`product-${index}`]}
                  <p class="mt-1 text-xs text-danger">{validation[`product-${index}`]}</p>
                {/if}
              </div>

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
                  type="number"
                  min="0.000001"
                  step="0.000001"
                  value={line.quantity}
                  oninput={(event) =>
                    updateLine(index, {
                      quantity: (event.currentTarget as HTMLInputElement).value
                    })}
                  class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
                />
                {#if validation[`quantity-${index}`]}
                  <p class="mt-1 text-xs text-danger">{validation[`quantity-${index}`]}</p>
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
                  class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
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
                  class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
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
