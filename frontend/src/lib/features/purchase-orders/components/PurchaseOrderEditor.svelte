<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchaseOrdersApi } from '$lib/api/purchase-orders';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { suppliersApi } from '$lib/api/suppliers';
  import { getWarehouses } from '$lib/services/warehouses';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Warehouse } from '$lib/features/warehouses/types';
  import type { PurchaseQuotation } from '$lib/types/purchase-quotation';
  import type { PurchaseOrderExpenseType } from '$lib/types/purchase-order';

  interface DraftLine {
    quotationDetailId: string;
    productId: number;
    unitId: number;
    sourceQuantity: string;
    quantity: string;
    unitPrice: string;
    included: boolean;
  }

  interface DraftExpense {
    key: string;
    expenseTypeId: string;
    amount: string;
    description: string;
  }

  let { quotationId }: { quotationId: string } = $props();

  let quotation = $state<PurchaseQuotation | null>(null);
  let supplierLabel = $state('');
  let productLabels = $state<Map<number, string>>(new Map());
  let unitLabels = $state<Map<number, string>>(new Map());
  let lines = $state<DraftLine[]>([]);
  let branchId = $state(branch.id ?? branch.branches.find((item) => item.is_active)?.id ?? '');
  let warehouseId = $state('');
  let warehouses = $state<Warehouse[]>([]);
  let expectedDate = $state('');
  let notes = $state('');
  let expenseTypes = $state<PurchaseOrderExpenseType[]>([]);
  let expenses = $state<DraftExpense[]>([]);
  let loadingExpenseTypes = $state(false);
  let expenseTypesError = $state<string | null>(null);
  let expenseSequence = 0;
  let loading = $state(true);
  let loadingWarehouses = $state(true);
  let saving = $state(false);
  let loadError = $state<string | null>(null);
  let warehouseError = $state<string | null>(null);
  let submitError = $state<string | null>(null);
  let validation = $state<Record<string, string>>({});
  let loadGeneration = 0;
  let warehouseGeneration = 0;

  let canManage = $derived(permissions.hasPermission('purchase_orders:manage'));
  let selectedCount = $derived(lines.filter((line) => line.included).length);

  function errorMessage(cause: unknown, fallback: string): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return fallback;
  }

  function productLabel(productId: number): string {
    return productLabels.get(productId) ?? `Producto #${productId}`;
  }

  function unitLabel(unitId: number): string {
    return unitLabels.get(unitId) ?? `Unidad #${unitId}`;
  }

  function formatQuantity(value: string): string {
    const quantity = Number(value);
    if (!Number.isFinite(quantity)) return value;
    return new Intl.NumberFormat('es-SV', { maximumFractionDigits: 6 }).format(quantity);
  }

  function formatMoney(value: string, currency: string): string {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return value;
    return new Intl.NumberFormat('es-SV', {
      style: 'currency',
      currency
    }).format(amount);
  }

  function addExpense() {
    const firstType = expenseTypes[0];
    if (!firstType || expenses.length >= 50) return;

    expenses = [
      ...expenses,
      {
        key: `expense-${++expenseSequence}`,
        expenseTypeId: firstType.id,
        amount: '',
        description: ''
      }
    ];
    validation = {};
  }

  function updateExpense(index: number, patch: Partial<Omit<DraftExpense, 'key'>>) {
    expenses = expenses.map((expense, currentIndex) =>
      currentIndex === index ? { ...expense, ...patch } : expense
    );
    validation = {};
  }

  function removeExpense(index: number) {
    expenses = expenses.filter((_, currentIndex) => currentIndex !== index);
    validation = {};
  }

  async function loadExpenseTypes() {
    loadingExpenseTypes = true;
    expenseTypesError = null;

    try {
      expenseTypes = await purchaseOrdersApi.listExpenseTypes();
    } catch (cause: unknown) {
      expenseTypes = [];
      expenseTypesError = errorMessage(cause, 'No se pudieron cargar los tipos de gasto.');
    } finally {
      loadingExpenseTypes = false;
    }
  }

  async function loadQuotation(currentQuotationId: string) {
    const generation = ++loadGeneration;
    loading = true;
    loadError = null;
    submitError = null;
    quotation = null;
    lines = [];
    supplierLabel = '';
    productLabels = new Map();
    unitLabels = new Map();

    if (!currentQuotationId) {
      quotation = null;
      lines = [];
      loadError = 'Selecciona una cotización para crear la orden de compra.';
      loading = false;
      return;
    }

    try {
      const loaded = await purchaseQuotationsApi.get(currentQuotationId);
      if (generation !== loadGeneration) return;

      quotation = loaded;
      lines = loaded.details.map((detail) => ({
        quotationDetailId: detail.id,
        productId: detail.product_id,
        unitId: detail.unit_id,
        sourceQuantity: detail.quantity,
        quantity: detail.quantity,
        unitPrice: detail.unit_price,
        included: true
      }));

      if (loaded.status !== 'selected') return;

      const productIds = [...new Set(loaded.details.map((detail) => detail.product_id))];
      const [supplier, units, products] = await Promise.all([
        suppliersApi.getSupplier(loaded.supplier_id).catch(() => null),
        catalogApi.listUnits(false).catch(() => []),
        Promise.all(
          productIds.map((productId) => catalogApi.getProduct(productId).catch(() => null))
        )
      ]);

      if (generation !== loadGeneration) return;

      supplierLabel = supplier?.code
        ? `${supplier.code} — ${supplier.name}`
        : (supplier?.name ?? `Proveedor #${loaded.supplier_id}`);

      const nextUnitLabels = new Map<number, string>();
      for (const unit of units) {
        nextUnitLabels.set(unit.id_unit, unit.code ? `${unit.code} — ${unit.name}` : unit.name);
      }
      unitLabels = nextUnitLabels;

      const nextProductLabels = new Map<number, string>();
      for (const product of products) {
        if (product) nextProductLabels.set(product.id_product, `${product.sku} — ${product.name}`);
      }
      productLabels = nextProductLabels;
    } catch (cause: unknown) {
      if (generation !== loadGeneration) return;
      quotation = null;
      lines = [];
      loadError = errorMessage(cause, 'No se pudo cargar la cotización seleccionada.');
    } finally {
      if (generation === loadGeneration) loading = false;
    }
  }

  async function loadWarehouses(selectedBranchId: string) {
    const generation = ++warehouseGeneration;
    loadingWarehouses = true;
    warehouseError = null;

    if (!selectedBranchId) {
      warehouses = [];
      warehouseId = '';
      loadingWarehouses = false;
      return;
    }

    try {
      const response = await getWarehouses({
        branchId: selectedBranchId,
        page: 1,
        size: 100,
        status: 'active'
      });

      if (generation !== warehouseGeneration) return;

      warehouses = response.items.filter((warehouse) => warehouse.branchId === selectedBranchId);
      if (!warehouses.some((warehouse) => warehouse.id === warehouseId)) {
        warehouseId = warehouses[0]?.id ?? '';
      }
    } catch (cause: unknown) {
      if (generation !== warehouseGeneration) return;
      warehouses = [];
      warehouseId = '';
      warehouseError = errorMessage(cause, 'No se pudieron cargar los almacenes de la sucursal.');
    } finally {
      if (generation === warehouseGeneration) loadingWarehouses = false;
    }
  }

  function handleBranchChange(event: Event) {
    branchId = (event.currentTarget as HTMLSelectElement).value;
    warehouseId = '';
    validation = {};
  }

  function handleWarehouseChange(event: Event) {
    warehouseId = (event.currentTarget as HTMLSelectElement).value;
    validation = {};
  }

  function updateLine(index: number, patch: Partial<Pick<DraftLine, 'quantity' | 'included'>>) {
    lines = lines.map((line, currentIndex) =>
      currentIndex === index ? { ...line, ...patch } : line
    );
    validation = {};
  }

  function validate(): boolean {
    const next: Record<string, string> = {};

    if (!quotation || quotation.status !== 'selected') {
      next.quotation = 'La orden debe crearse desde una cotización seleccionada.';
    }
    if (!branchId) next.branch = 'Selecciona una sucursal.';
    if (!warehouseId) next.warehouse = 'Selecciona un almacén.';

    const selectedLines = lines.filter((line) => line.included);
    if (selectedLines.length === 0) next.lines = 'Selecciona al menos una línea de la cotización.';

    lines.forEach((line, index) => {
      if (!line.included) return;
      const quantity = Number(line.quantity);
      if (!Number.isFinite(quantity) || quantity <= 0) {
        next[`quantity-${index}`] = 'La cantidad debe ser mayor que cero.';
      }
    });

    expenses.forEach((expense, index) => {
      if (!expense.expenseTypeId) {
        next[`expenseType-${index}`] = 'Selecciona un tipo de gasto.';
      }

      const amount = Number(expense.amount);
      if (!Number.isFinite(amount) || amount <= 0) {
        next[`expenseAmount-${index}`] = 'El monto debe ser mayor que cero.';
      }
    });

    validation = next;
    return Object.keys(next).length === 0;
  }

  async function submit() {
    if (!canManage || saving || !quotation || !validate()) return;

    saving = true;
    submitError = null;

    try {
      const created = await purchaseOrdersApi.create({
        purchase_quotation_id: quotation.id,
        branch_id: branchId,
        warehouse_id: warehouseId,
        expected_date: expectedDate ? `${expectedDate}T12:00:00-06:00` : null,
        lines: lines
          .filter((line) => line.included)
          .map((line) => ({
            purchase_quotation_detail_id: line.quotationDetailId,
            quantity: Number(line.quantity)
          })),
        expenses: expenses.map((expense) => ({
          expense_type_id: expense.expenseTypeId,
          amount: Number(expense.amount),
          description: expense.description.trim() || null
        })),
        notes: notes.trim() || null
      });

      await goto(`/purchase-orders/${created.id}`);
    } catch (cause: unknown) {
      submitError = errorMessage(cause, 'No se pudo crear la orden de compra.');
    } finally {
      saving = false;
    }
  }

  function retry() {
    void loadQuotation(quotationId);
  }

  $effect(() => {
    if (canManage) {
      void loadQuotation(quotationId);
      void loadExpenseTypes();
    } else {
      loading = false;
    }
  });

  $effect(() => {
    if (canManage) {
      void loadWarehouses(branchId);
    } else {
      loadingWarehouses = false;
    }
  });
</script>

<section class="space-y-5">
  <div>
    <a
      href={quotationId ? `/purchase-quotations/${quotationId}` : '/purchase-quotations'}
      class="text-sm font-medium text-primary hover:underline"
    >
      ← Volver a cotización
    </a>
  </div>

  {#if !canManage}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      No tienes permiso para gestionar órdenes de compra.
    </div>
  {:else if loading}
    <div class="space-y-4" aria-label="Cargando formulario de orden de compra">
      <div class="skeleton h-28 rounded-xl"></div>
      <div class="skeleton h-48 rounded-xl"></div>
      <div class="skeleton h-64 rounded-xl"></div>
    </div>
  {:else if loadError}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span>{loadError}</span>
        {#if quotationId}
          <Button size="sm" variant="secondary" onclick={retry}>Reintentar</Button>
        {/if}
      </div>
    </div>
  {:else if quotation}
    <header>
      <p class="text-sm font-medium text-primary">Orden de compra</p>
      <h1 class="text-2xl font-semibold tracking-tight text-foreground">
        Crear desde {quotation.code}
      </h1>
      <p class="mt-1 text-sm text-foreground-muted">
        {supplierLabel || `Proveedor #${quotation.supplier_id}`} · {quotation.currency}
      </p>
    </header>

    {#if quotation.status !== 'selected'}
      <div
        class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
        role="alert"
      >
        Solo una cotización seleccionada puede originar una orden de compra.
      </div>
    {:else}
      {#if submitError}
        <div
          class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
          role="alert"
        >
          {submitError}
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
          <h2 class="mb-4 text-sm font-semibold text-foreground">Destino de la orden</h2>
          <div class="grid gap-4 md:grid-cols-2">
            <div>
              <label
                for="purchase-order-branch"
                class="mb-1 block text-sm font-medium text-foreground"
              >
                Sucursal <span class="text-danger">*</span>
              </label>
              <select
                id="purchase-order-branch"
                aria-label="Sucursal"
                value={branchId}
                onchange={handleBranchChange}
                class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
              >
                <option value="">Selecciona una sucursal</option>
                {#each branch.branches.filter((item) => item.is_active) as item (item.id)}
                  <option value={item.id}>{item.code ? `${item.code} — ` : ''}{item.name}</option>
                {/each}
              </select>
              {#if validation.branch}
                <p class="mt-1 text-xs text-danger">{validation.branch}</p>
              {/if}
            </div>

            <div>
              <label
                for="purchase-order-warehouse"
                class="mb-1 block text-sm font-medium text-foreground"
              >
                Almacén <span class="text-danger">*</span>
              </label>
              <select
                id="purchase-order-warehouse"
                aria-label="Almacén"
                value={warehouseId}
                onchange={handleWarehouseChange}
                disabled={loadingWarehouses || warehouses.length === 0}
                class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
              >
                <option value="">Selecciona un almacén</option>
                {#each warehouses as warehouse (warehouse.id)}
                  <option value={warehouse.id}>{warehouse.code} — {warehouse.name}</option>
                {/each}
              </select>
              {#if warehouseError}
                <p class="mt-1 text-xs text-danger">{warehouseError}</p>
              {:else if validation.warehouse}
                <p class="mt-1 text-xs text-danger">{validation.warehouse}</p>
              {/if}
            </div>

            <div>
              <label
                for="purchase-order-expected-date"
                class="mb-1 block text-sm font-medium text-foreground"
              >
                Fecha esperada
              </label>
              <input
                id="purchase-order-expected-date"
                aria-label="Fecha esperada"
                type="date"
                bind:value={expectedDate}
                class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
              />
            </div>

            <div>
              <label
                for="purchase-order-notes"
                class="mb-1 block text-sm font-medium text-foreground"
              >
                Notas
              </label>
              <textarea
                id="purchase-order-notes"
                aria-label="Notas"
                bind:value={notes}
                maxlength="4000"
                rows="3"
                class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
                placeholder="Observaciones opcionales"
              ></textarea>
            </div>
          </div>
        </Card>

        <Card class="overflow-hidden p-0">
          <div class="border-b border-border px-4 py-3">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 class="text-sm font-semibold text-foreground">Líneas de la cotización</h2>
                <p class="mt-1 text-xs text-foreground-muted">
                  Selecciona el subconjunto que deseas ordenar. El backend valida la disponibilidad
                  restante.
                </p>
              </div>
              <span class="text-sm text-foreground-muted">{selectedCount} seleccionadas</span>
            </div>
          </div>

          {#if lines.length === 0}
            <div class="p-6 text-center text-sm text-foreground-muted">
              La cotización no contiene líneas disponibles para crear una orden.
            </div>
          {:else}
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-border text-sm">
                <thead
                  class="bg-surface-muted text-left text-xs uppercase tracking-wide text-foreground-muted"
                >
                  <tr>
                    <th class="px-4 py-3 font-medium">Incluir</th>
                    <th class="px-4 py-3 font-medium">Producto</th>
                    <th class="px-4 py-3 font-medium">Unidad</th>
                    <th class="px-4 py-3 font-medium">Cotizado</th>
                    <th class="px-4 py-3 font-medium">Cantidad a ordenar</th>
                    <th class="px-4 py-3 font-medium">Precio unit.</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-border">
                  {#each lines as line, index (line.quotationDetailId)}
                    <tr class="text-foreground">
                      <td class="px-4 py-3">
                        <input
                          type="checkbox"
                          aria-label={`Incluir línea ${index + 1}`}
                          checked={line.included}
                          onchange={(event) =>
                            updateLine(index, {
                              included: (event.currentTarget as HTMLInputElement).checked
                            })}
                          class="h-4 w-4 rounded border-border"
                        />
                      </td>
                      <td class="min-w-56 px-4 py-3 font-medium">{productLabel(line.productId)}</td>
                      <td class="whitespace-nowrap px-4 py-3 text-foreground-muted">
                        {unitLabel(line.unitId)}
                      </td>
                      <td class="whitespace-nowrap px-4 py-3">
                        {formatQuantity(line.sourceQuantity)}
                      </td>
                      <td class="min-w-44 px-4 py-3">
                        <input
                          aria-label={`Cantidad línea ${index + 1}`}
                          type="number"
                          min="0.000001"
                          step="0.000001"
                          value={line.quantity}
                          disabled={!line.included}
                          oninput={(event) =>
                            updateLine(index, {
                              quantity: (event.currentTarget as HTMLInputElement).value
                            })}
                          class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
                        />
                        {#if validation[`quantity-${index}`]}
                          <p class="mt-1 text-xs text-danger">{validation[`quantity-${index}`]}</p>
                        {/if}
                      </td>
                      <td class="whitespace-nowrap px-4 py-3">
                        {formatMoney(line.unitPrice, quotation.currency)}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}

          {#if validation.lines}
            <p class="border-t border-border px-4 py-3 text-sm text-danger">{validation.lines}</p>
          {/if}
        </Card>

        <Card class="p-5">
          <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 class="text-sm font-semibold text-foreground">Gastos adicionales</h2>
              <p class="mt-1 text-xs text-foreground-muted">
                Agrega únicamente los gastos que correspondan a esta orden.
              </p>
            </div>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={loadingExpenseTypes || expenseTypes.length === 0 || expenses.length >= 50}
              onclick={addExpense}
            >
              Agregar gasto
            </Button>
          </div>

          {#if expenseTypesError}
            <p class="text-sm text-danger" role="alert">{expenseTypesError}</p>
          {:else if loadingExpenseTypes}
            <p class="text-sm text-foreground-muted">Cargando tipos de gasto…</p>
          {:else if expenseTypes.length === 0}
            <p class="text-sm text-foreground-muted">No hay tipos de gasto activos disponibles.</p>
          {/if}

          {#if expenses.length > 0}
            <div class="space-y-4">
              {#each expenses as expense, index (expense.key)}
                <div
                  class="grid gap-3 rounded-lg border border-border p-4 md:grid-cols-[1fr_180px_1fr_auto]"
                >
                  <div>
                    <label
                      for={`purchase-order-expense-type-${index}`}
                      class="mb-1 block text-xs font-medium text-foreground"
                    >
                      Tipo de gasto
                    </label>
                    <select
                      id={`purchase-order-expense-type-${index}`}
                      aria-label={`Tipo de gasto ${index + 1}`}
                      value={expense.expenseTypeId}
                      onchange={(event) =>
                        updateExpense(index, {
                          expenseTypeId: (event.currentTarget as HTMLSelectElement).value
                        })}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
                    >
                      {#each expenseTypes as expenseType (expenseType.id)}
                        <option value={expenseType.id}>{expenseType.name}</option>
                      {/each}
                    </select>
                    {#if validation[`expenseType-${index}`]}
                      <p class="mt-1 text-xs text-danger">{validation[`expenseType-${index}`]}</p>
                    {/if}
                  </div>

                  <div>
                    <label
                      for={`purchase-order-expense-amount-${index}`}
                      class="mb-1 block text-xs font-medium text-foreground"
                    >
                      Monto
                    </label>
                    <input
                      id={`purchase-order-expense-amount-${index}`}
                      aria-label={`Monto gasto ${index + 1}`}
                      type="number"
                      min="0.000001"
                      step="0.000001"
                      value={expense.amount}
                      oninput={(event) =>
                        updateExpense(index, {
                          amount: (event.currentTarget as HTMLInputElement).value
                        })}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
                    />
                    {#if validation[`expenseAmount-${index}`]}
                      <p class="mt-1 text-xs text-danger">{validation[`expenseAmount-${index}`]}</p>
                    {/if}
                  </div>

                  <div>
                    <label
                      for={`purchase-order-expense-description-${index}`}
                      class="mb-1 block text-xs font-medium text-foreground"
                    >
                      Descripción
                    </label>
                    <input
                      id={`purchase-order-expense-description-${index}`}
                      aria-label={`Descripción gasto ${index + 1}`}
                      maxlength="1000"
                      value={expense.description}
                      oninput={(event) =>
                        updateExpense(index, {
                          description: (event.currentTarget as HTMLInputElement).value
                        })}
                      class="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
                      placeholder="Opcional"
                    />
                  </div>

                  <div class="flex items-end">
                    <Button
                      type="button"
                      size="sm"
                      variant="danger"
                      onclick={() => removeExpense(index)}
                    >
                      Eliminar gasto {index + 1}
                    </Button>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </Card>

        <div class="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <a
            href={`/purchase-quotations/${quotation.id}`}
            class="inline-flex h-10 items-center justify-center rounded-lg border border-border bg-surface px-4 text-sm font-medium text-foreground hover:bg-surface-muted"
          >
            Cancelar
          </a>
          <Button type="submit" disabled={saving || loadingWarehouses || lines.length === 0}>
            {saving ? 'Creando…' : 'Crear orden'}
          </Button>
        </div>
      </form>
    {/if}
  {/if}
</section>
