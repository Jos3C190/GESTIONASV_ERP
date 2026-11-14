<script lang="ts">
  import { tick } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchasesApi } from '$lib/api/purchases';
  import { retaceosApi } from '$lib/api/retaceos';
  import { apiFetch } from '$lib/api/client';
  import {
    actualExpensesApi,
    type ActualPurchaseExpense
  } from '$lib/features/purchase-orders/actual-expenses';
  import type { PurchaseOrderExpenseType } from '$lib/types/purchase-order';
  import RetaceoFixedAmounts from './RetaceoFixedAmounts.svelte';
  import RetaceoFobLines from './RetaceoFobLines.svelte';
  import {
    distributeByFob,
    retaceoExpenseCategory,
    totalAmounts,
    validateImportAmount,
    type FixedAmounts
  } from '../manual-costs';
  import CustomsReferencePanel from '$lib/features/retaceos/components/CustomsReferencePanel.svelte';
  import RetaceoImportFields from './RetaceoImportFields.svelte';
  import RetaceoPlannedExpenses from './RetaceoPlannedExpenses.svelte';
  import type { RetaceoImportData } from '$lib/types/retaceo';
  import RetaceoCostEditor from '$lib/features/retaceos/components/RetaceoCostEditor.svelte';
  import {
    DOCUMENT_MAX_BYTES,
    documentContentType,
    isSupportedDocumentFile
  } from '$lib/features/documents/document-upload';
  import { openResolvedDocumentInBrowser } from '$lib/features/documents/open-document';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import type {
    Retaceo,
    RetaceoCost,
    RetaceoCostClass,
    RetaceoCostDocument
  } from '$lib/types/retaceo';
  import type { EditableRetaceoCost } from '$lib/features/retaceos/retaceo-cost-editor-types';

  let { retaceoId }: { retaceoId: string } = $props();

  const COST_CLASSES: { value: RetaceoCostClass; label: string }[] = [
    { value: 'freight', label: 'Flete y seguro' },
    { value: 'expense', label: 'Gasto adicional' },
    { value: 'dai', label: 'DAI' }
  ];

  let item = $state<Retaceo | null>(null);
  const fobTotal = $derived.by(() => {
    try {
      return totalAmounts(Object.values(fobAmounts));
    } catch {
      return '';
    }
  });
  let manualEntry = $derived(item?.manual_entry ?? false);
  let fixedAmounts = $state<FixedAmounts>({ freight: '', dai: '' });
  let expenseTypes = $state<PurchaseOrderExpenseType[]>([]);
  let actualExpenses = $state<ActualPurchaseExpense[]>([]);
  let catalogError = $state('');
  let catalogLoading = $state(false);
  let capturedTotal = $derived.by(() => {
    try {
      return totalAmounts([
        ...Object.values(fobAmounts),
        fixedAmounts.freight,
        fixedAmounts.dai,
        ...costs.filter((cost) => cost.classification === 'expense').map((cost) => cost.amount)
      ]);
    } catch {
      return null;
    }
  });
  const otherExpenseTotal = $derived.by(() => {
    try {
      return totalAmounts(
        costs.filter((cost) => cost.classification === 'expense').map((cost) => cost.amount)
      );
    } catch {
      return '';
    }
  });
  let importData = $state<RetaceoImportData>({
    origin_country: null,
    import_invoice_number: null,
    import_invoice_date: null,
    import_policy_number: null,
    import_policy_date: null
  });
  let fobAmounts = $state<Record<string, string>>({});
  let purchaseLabel = $state('');
  let purchaseOrderId = $state<string | null>(null);
  let productLabels = $state<Map<number, string>>(new Map());
  let unitLabels = $state<Map<number, string>>(new Map());
  let costs = $state<EditableRetaceoCost[]>([]);
  let loading = $state(true);
  let saving = $state(false);
  let editable = $state(true);
  let uploadingCostId = $state<string | null>(null);
  let downloadingDocumentId = $state<string | null>(null);
  let deletingDocumentId = $state<string | null>(null);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let validation = $state<Record<string, string>>({});
  let requestSequence = 0;

  let canManage = $derived(permissions.hasPermission('retaceos:manage'));

  function errorMessage(cause: unknown, fallback: string): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return fallback;
  }

  function formatMoney(value: string | number, currency: string): string {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return String(value);

    return new Intl.NumberFormat('es-SV', {
      style: 'currency',
      currency
    }).format(amount);
  }

  function formatQuantity(value: string): string {
    const quantity = Number(value);
    if (!Number.isFinite(quantity)) return value;

    return new Intl.NumberFormat('es-SV', { maximumFractionDigits: 6 }).format(quantity);
  }

  function classLabel(value: RetaceoCostClass): string {
    return COST_CLASSES.find((option) => option.value === value)?.label ?? 'Gasto adicional';
  }

  function productLabel(id: number): string {
    return productLabels.get(id) ?? `Producto #${id}`;
  }

  function unitLabel(id: number): string {
    return unitLabels.get(id) ?? `Unidad #${id}`;
  }

  function mapCost(cost: RetaceoCost): EditableRetaceoCost {
    const allocations: Record<string, string> = {};
    for (const allocation of cost.allocations) {
      allocations[allocation.purchase_detail_id] = allocation.amount;
    }
    return {
      key: cost.id,
      id: cost.id,
      sourcePurchaseOrderExpenseId: cost.source_purchase_order_expense_id,
      expenseTypeId: cost.expense_type_id,
      incurredOn: cost.incurred_on ?? '',
      classification: cost.classification,
      title: cost.title,
      description: cost.description ?? '',
      amount: cost.amount,
      allocations,
      documents: cost.documents ?? [],
      expanded: false
    };
  }

  function legacyCosts(current: Retaceo): EditableRetaceoCost[] {
    const groups: {
      classification: RetaceoCostClass;
      title: string;
      total: string;
      amountFor: (cost: Retaceo['details'][number]) => string;
    }[] = [
      {
        classification: 'freight',
        title: 'Flete heredado',
        total: current.total_freight,
        amountFor: (detail) => detail.freight
      },
      {
        classification: 'expense',
        title: 'Gastos heredados',
        total: current.total_expenses,
        amountFor: (detail) => detail.expenses
      },
      {
        classification: 'dai',
        title: 'DAI heredado',
        total: current.total_dai,
        amountFor: (detail) => detail.dai
      }
    ];

    return groups
      .filter((group) => Number(group.total) > 0)
      .map((group) => {
        const allocations: Record<string, string> = {};
        for (const detail of current.details) {
          const amount = group.amountFor(detail);
          if (Number(amount) > 0) allocations[detail.purchase_detail_id] = amount;
        }
        return {
          key: crypto.randomUUID(),
          sourcePurchaseOrderExpenseId: null,
          classification: group.classification,
          title: group.title,
          description: 'Costo existente antes del desglose por comprobante.',
          amount: group.total,
          allocations,
          documents: [],
          expanded: false
        };
      });
  }

  function hydrate(current: Retaceo) {
    importData = {
      origin_country: current.origin_country ?? null,
      import_invoice_number: current.import_invoice_number ?? null,
      import_invoice_date: current.import_invoice_date ?? null,
      import_policy_number: current.import_policy_number ?? null,
      import_policy_date: current.import_policy_date ?? null
    };
    item = current;
    fixedAmounts = {
      freight: current.total_freight,
      dai: current.total_dai
    };
    const activeCosts = (current.costs ?? []).filter((cost) => cost.is_active).map(mapCost);
    const nextCosts = activeCosts.length > 0 ? activeCosts : legacyCosts(current);
    const firstCost = nextCosts[0];
    if (firstCost) firstCost.expanded = true;
    costs = nextCosts;
    fobAmounts = Object.fromEntries(
      current.details.map((line) => [line.purchase_detail_id, line.cost_fob])
    );
  }

  async function load(currentRetaceoId: string) {
    const sequence = ++requestSequence;
    loading = true;
    editable = true;
    error = null;
    notice = null;
    validation = {};

    try {
      const current = await retaceosApi.get(currentRetaceoId);

      if (sequence !== requestSequence) return;

      hydrate(current);

      if (current.status !== 'draft') {
        editable = false;
        error = 'Solo los retaceos en borrador pueden editarse.';
        return;
      }

      const [purchase, units, products] = await Promise.all([
        purchasesApi.get(current.purchase_id),
        catalogApi.listUnits(false).catch(() => []),
        Promise.all(
          [...new Set(current.details.map((detail) => detail.product_id))].map((productId) =>
            catalogApi.getProduct(productId).catch(() => null)
          )
        )
      ]);

      if (sequence !== requestSequence) return;

      purchaseLabel = purchase?.code ?? current.purchase_id;
      purchaseOrderId = purchase?.purchase_order_id ?? null;
      if (current.manual_entry) await loadCostReferences(sequence);
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
      if (sequence !== requestSequence) return;

      item = null;
      purchaseLabel = '';
      costs = [];
      editable = false;
      error = errorMessage(cause, 'No se pudo cargar el borrador de retaceo.');
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  async function loadCostReferences(sequence = requestSequence) {
    if (!purchaseOrderId) return;
    catalogLoading = true;
    catalogError = '';
    try {
      const [types, actuals] = await Promise.all([
        apiFetch<PurchaseOrderExpenseType[]>('/retaceos/cost-categories'),
        permissions.hasPermission('purchase_orders:read')
          ? actualExpensesApi.list(purchaseOrderId)
          : Promise.resolve([])
      ]);
      if (sequence !== requestSequence) return;
      expenseTypes = types.filter((row) => retaceoExpenseCategory(row.name));
      actualExpenses = actuals;
    } catch (cause) {
      if (sequence === requestSequence)
        catalogError = errorMessage(cause, 'No se pudieron cargar categorías y gastos reales.');
    } finally {
      if (sequence === requestSequence) catalogLoading = false;
    }
  }

  function addCost() {
    if (!item || !editable || saving) return;
    costs = [
      ...costs,
      {
        key: crypto.randomUUID(),
        sourcePurchaseOrderExpenseId: null,
        classification: 'expense',
        title: '',
        description: '',
        amount: '',
        allocations: {},
        documents: [],
        expanded: true
      }
    ];
  }

  function removeCost(key: string) {
    const cost = costs.find((row) => row.key === key);
    if (!cost || (cost.sourcePurchaseOrderExpenseId && !manualEntry)) return;
    costs = costs.filter((row) => row.key !== key);
  }

  function clearValidation(key: string) {
    if (!(key in validation)) return;
    const next = { ...validation };
    delete next[key];
    validation = next;
  }

  function validate(): boolean {
    const next: Record<string, string> = {};
    if (manualEntry)
      for (const key of ['freight', 'dai'] as const) {
        const message = validateImportAmount(fixedAmounts[key]);
        if (message) next[`fixed-${key}`] = message;
      }
    for (const cost of costs) {
      // Freight and DAI are validated in their own fields above.
      if (manualEntry && cost.classification !== 'expense') continue;
      const amount = Number(cost.amount);
      if (!cost.title.trim()) next[`${cost.key}-title`] = 'Escribe el concepto del gasto.';
      if (manualEntry && cost.classification === 'expense') {
        if (!cost.expenseTypeId)
          next[`${cost.key}-category`] = 'Selecciona una categoría de gastos adicionales.';
        if (!cost.incurredOn) next[`${cost.key}-date`] = 'Indica la fecha del gasto.';
        if (!cost.description.trim()) next[`${cost.key}-description`] = 'Describe el gasto.';
      }
      if (!cost.amount.trim() || !Number.isFinite(amount) || amount <= 0) {
        next[`${cost.key}-amount`] = 'El monto debe ser mayor que cero.';
      }
    }
    validation = next;
    return Object.keys(next).length === 0;
  }

  /** Preview only: the server distributes every amount by FOB and its result is what counts. */
  function preview(cost: EditableRetaceoCost) {
    if (!item) return;
    try {
      cost.allocations = distributeByFob(
        cost.amount,
        item.details.map((line) => [
          line.purchase_detail_id,
          fobAmounts[line.purchase_detail_id] ?? '0'
        ])
      );
    } catch {
      cost.allocations = {};
    }
  }

  function updateFixed(key: keyof FixedAmounts, value: string) {
    fixedAmounts[key] = value;
    clearValidation(`fixed-${key}`);
    const kind: RetaceoCostClass = key === 'freight' ? 'freight' : 'dai';
    const existing = costs.find((cost) => cost.classification === kind);
    if (existing) {
      existing.amount = value;
      preview(existing);
      return;
    }
    if (validateImportAmount(value) === null && Number(value) > 0) {
      const cost: EditableRetaceoCost = {
        key: crypto.randomUUID(),
        sourcePurchaseOrderExpenseId: null,
        classification: kind,
        title: classLabel(kind),
        description: '',
        amount: value,
        allocations: {},
        documents: [],
        expanded: true
      };
      preview(cost);
      costs = [...costs, cost];
    }
  }

  async function revealValidationIssues() {
    for (const cost of costs) {
      if (Object.keys(validation).some((key) => key.startsWith(`${cost.key}-`))) {
        cost.expanded = true;
      }
    }

    await tick();
    const [firstInvalidField] = Object.keys(validation);
    if (!firstInvalidField) return;

    const control = document.getElementById(firstInvalidField);

    control?.focus();
    control?.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'instant'
        : 'smooth',
      block: 'center'
    });
  }

  async function submit() {
    if (!canManage || !editable || saving || !item) return;
    if (!validate()) {
      await revealValidationIssues();
      return;
    }

    saving = true;
    error = null;
    notice = null;

    try {
      const updated = await retaceosApi.update(item.id, {
        import_data: importData,
        total_freight: manualEntry ? fixedAmounts.freight : item.total_freight,
        total_expenses: manualEntry
          ? totalAmounts(
              costs.filter((cost) => cost.classification === 'expense').map((cost) => cost.amount)
            )
          : item.total_expenses,
        total_dai: manualEntry ? fixedAmounts.dai : item.total_dai,
        notes: item.notes,
        costs: costs
          .filter(
            (cost) => !manualEntry || cost.classification === 'expense' || Number(cost.amount) !== 0
          )
          .map((cost) => ({
            ...(cost.id ? { id: cost.id } : {}),
            ...(manualEntry
              ? {
                  expense_type_id: cost.expenseTypeId ?? null,
                  incurred_on: cost.incurredOn || null,
                  source_purchase_order_expense_id: cost.sourcePurchaseOrderExpenseId
                }
              : {}),
            classification: cost.classification,
            title: cost.title.trim(),
            description: cost.description.trim() || null,
            amount: cost.amount
          }))
      });
      hydrate(updated);
      item = updated;
      notice =
        'Borrador guardado. Puedes adjuntar comprobantes de forma opcional o abrir el detalle para calcular el retaceo.';
    } catch (cause: unknown) {
      error = errorMessage(cause, 'No se pudo guardar el borrador de retaceo.');
    } finally {
      saving = false;
    }
  }

  async function checksum(file: File): Promise<string> {
    const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join(
      ''
    );
  }

  async function chooseFile(cost: EditableRetaceoCost, event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file || !item || !cost.id || uploadingCostId || deletingDocumentId) return;

    if (!isSupportedDocumentFile(file, DOCUMENT_MAX_BYTES)) {
      error = 'Selecciona un comprobante permitido de hasta 50 MB.';
      notice = null;
      return;
    }

    uploadingCostId = cost.key;
    error = null;
    notice = null;
    try {
      const ticket = await retaceosApi.initiateCostDocument(item.id, cost.id, {
        file_name: file.name,
        content_type: documentContentType(file),
        size_bytes: file.size,
        checksum_sha256: await checksum(file)
      });
      const response = await fetch(ticket.upload_url, {
        method: ticket.method,
        headers: ticket.required_headers,
        body: file,
        credentials: 'omit'
      });
      if (!response.ok) throw new Error('No se pudo cargar el archivo al almacenamiento seguro.');
      const completed = await retaceosApi.completeCostDocument(
        item.id,
        cost.id,
        ticket.document.document_id
      );
      cost.documents = [...cost.documents, completed];
      notice = `Comprobante adjuntado a «${cost.title}».`;
    } catch (cause: unknown) {
      error = errorMessage(cause, 'No se pudo adjuntar el comprobante al gasto.');
    } finally {
      uploadingCostId = null;
    }
  }

  async function downloadDocument(cost: EditableRetaceoCost, document: RetaceoCostDocument) {
    if (!item || !cost.id || downloadingDocumentId || deletingDocumentId) return;
    downloadingDocumentId = document.id;
    error = null;
    try {
      await openResolvedDocumentInBrowser(async () => {
        const result = await retaceosApi.createCostDocumentDownloadUrl(
          item!.id,
          cost.id!,
          document.document_id
        );
        return result.url;
      });
    } catch (cause: unknown) {
      error = errorMessage(cause, 'No se pudo preparar la descarga del comprobante.');
    } finally {
      downloadingDocumentId = null;
    }
  }

  function removeDocument(cost: EditableRetaceoCost, document: RetaceoCostDocument) {
    if (!item || !cost.id || saving || uploadingCostId || deletingDocumentId) return;

    const retaceoId = item.id;
    const costId = cost.id;
    confirmation.request({
      kind: 'delete',
      title: 'Quitar comprobante del gasto',
      description:
        'Se desvinculará de este retaceo. El archivo original y el registro de auditoría se conservarán.',
      resourceName: document.file_name,
      confirmLabel: 'Quitar comprobante',
      execute: async () => {
        deletingDocumentId = document.id;
        error = null;
        notice = null;
        try {
          await retaceosApi.removeCostDocument(retaceoId, costId, document.document_id);
          cost.documents = cost.documents.filter((attached) => attached.id !== document.id);
          notice = `Se quitó «${document.file_name}» del gasto. El archivo se conservó para auditoría.`;
        } catch (cause: unknown) {
          throw new Error(errorMessage(cause, 'No se pudo quitar el comprobante.'));
        } finally {
          deletingDocumentId = null;
        }
      }
    });
  }

  function retry() {
    if (retaceoId) void load(retaceoId);
  }

  $effect(() => {
    const currentRetaceoId = retaceoId;

    if (canManage && currentRetaceoId) {
      void load(currentRetaceoId);
    } else {
      loading = false;
    }
  });
</script>

<section class="space-y-5">
  <div>
    <a
      href={retaceoId ? `/retaceos/${retaceoId}` : '/retaceos'}
      class="text-sm font-medium text-primary hover:underline"
    >
      ← Volver al retaceo
    </a>
  </div>

  {#if !canManage}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-foreground"
      role="alert"
    >
      No tienes permiso para gestionar retaceos.
    </div>
  {:else if loading}
    <div class="space-y-4" aria-label="Cargando borrador de retaceo">
      <div class="skeleton h-28 rounded-xl"></div>
      <div class="skeleton h-72 rounded-xl"></div>
    </div>
  {:else if !editable || !item}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-foreground"
      role="alert"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span>{error ?? 'Este retaceo no puede editarse.'}</span>
        {#if retaceoId}<Button size="sm" variant="secondary" onclick={retry}>Reintentar</Button
          >{/if}
      </div>
    </div>
  {:else}
    <header class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p class="text-sm font-medium text-primary">Retaceo · {item.code}</p>
        <h1 class="text-2xl font-semibold tracking-tight text-foreground">Costos y comprobantes</h1>
        <p class="mt-1 text-sm text-foreground-muted">
          Compra {purchaseLabel} · {item.currency}. Flete y seguro, DAI y gastos adicionales se
          reparten según el FOB de cada producto.
        </p>
      </div>
      <span
        class="inline-flex w-fit rounded-full border border-warning/30 bg-warning/10 px-3 py-1.5 text-sm font-medium text-foreground"
      >
        Borrador editable
      </span>
    </header>
    {#if manualEntry}<div
        class="flex flex-wrap items-baseline justify-between gap-2 border-l-4 border-primary bg-primary/5 px-4 py-3"
      >
        <span class="text-sm font-medium text-foreground">Costo de adquisición capturado</span>
        <strong class="font-mono text-2xl text-foreground"
          >{capturedTotal === null
            ? 'Completa los importes'
            : formatMoney(capturedTotal, item.currency)}</strong
        >
      </div>{/if}

    {#if error}
      <div
        class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-foreground"
        role="alert"
      >
        {error}
      </div>
    {/if}
    {#if notice}
      <div
        class="rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-success"
        role="status"
      >
        {notice}
        <a
          class="ml-2 rounded font-medium underline underline-offset-4"
          href={`/retaceos/${item.id}`}>Revisar y calcular</a
        >
      </div>
    {/if}

    <details class="rounded-xl border border-border bg-surface p-4">
      <summary
        class="cursor-pointer rounded text-sm font-medium text-foreground focus-visible:ring-2 focus-visible:ring-primary"
        >Consultar referencias de aduana y DAI</summary
      >
      <div class="mt-4"><CustomsReferencePanel /></div>
    </details>
    {#if catalogError}<div
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-foreground"
        role="alert"
      >
        {catalogError}<Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={saving || catalogLoading}
          onclick={() => void loadCostReferences()}>Reintentar categorías y bitácora</Button
        >
      </div>{/if}
    {#if manualEntry && purchaseOrderId && permissions.hasPermission('purchase_orders:read')}
      <details class="rounded-xl border border-border bg-surface p-4">
        <summary
          class="cursor-pointer rounded text-sm font-medium text-foreground focus-visible:ring-2 focus-visible:ring-primary"
          >Comparar gastos previstos y reales</summary
        >
        <div class="mt-4">
          <RetaceoPlannedExpenses
            orderId={purchaseOrderId}
            currency={item.currency}
            actualExpenses={costs.reduce((sum, cost) => sum + (Number(cost.amount) || 0), 0)}
          />
        </div>
      </details>
    {/if}

    <form
      novalidate
      class="space-y-5"
      onsubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      {#if manualEntry}
        <RetaceoImportFields
          value={importData}
          oninput={(value) => (importData = value)}
          disabled={saving}
          invoiceLocked={manualEntry}
        />
      {/if}
      {#if manualEntry}
        <RetaceoFixedAmounts
          fob={fobTotal}
          otherExpenses={otherExpenseTotal}
          value={fixedAmounts}
          currency={item.currency}
          disabled={saving}
          oninput={updateFixed}
          errors={{
            freight: validation['fixed-freight'],
            dai: validation['fixed-dai']
          }}
        />
      {/if}
      <RetaceoFobLines
        currency={item.currency}
        lines={item.details.map((line) => ({
          key: line.purchase_detail_id,
          label: productLabel(line.product_id),
          detail: `${formatQuantity(line.quantity)} ${unitLabel(line.unit_id)}`,
          amount: line.cost_fob
        }))}
      />

      {#if manualEntry}
        <label
          class="block rounded-xl border border-border bg-surface p-4 text-sm font-medium text-foreground"
        >
          Notas
          <textarea
            rows="3"
            maxlength="4000"
            bind:value={item.notes}
            disabled={saving}
            class="mt-2 w-full rounded-lg border border-border-control bg-surface px-3 py-2 focus-visible:ring-2 focus-visible:ring-primary"
          ></textarea>
        </label>
      {/if}
      <article class="overflow-hidden rounded-xl border border-border bg-surface">
        <div
          class="flex flex-col gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h2 class="font-semibold text-foreground">
              {manualEntry ? 'Desglose y comprobantes' : 'Gastos reales'}
            </h2>
            <p class="mt-1 text-sm text-foreground-muted">
              {costs.length} concepto(s) · Los comprobantes son opcionales.
            </p>
            {#if manualEntry}
              <p class="mt-1 max-w-prose text-xs leading-5 text-foreground-muted">
                Cada importe se reparte automáticamente entre los productos según su FOB. Puedes
                adjuntar comprobantes si los tienes.
              </p>
              {#if purchaseOrderId && permissions.hasPermission('purchase_orders:read')}<a
                  class="mt-2 inline-block rounded text-sm font-medium text-primary underline underline-offset-4 focus-visible:ring-2 focus-visible:ring-primary"
                  href={`/purchase-orders/${purchaseOrderId}`}>Consultar bitácora de la orden</a
                >{/if}
            {/if}
          </div>
          <Button
            type="button"
            variant="secondary"
            onclick={addCost}
            disabled={saving || uploadingCostId !== null || deletingDocumentId !== null}
          >
            + Agregar gasto adicional
          </Button>
        </div>

        {#if costs.length === 0}
          <div class="m-4 rounded-xl border border-dashed border-border px-5 py-8 text-center">
            <p class="font-medium text-foreground">Todavía no hay gastos para distribuir</p>
            <p class="mt-1 text-sm text-foreground-muted">
              {manualEntry
                ? 'Los componentes con importe 0 no requieren desglose. Puedes agregar gastos adicionales reales por categoría.'
                : 'Agrega flete, gastos, DAI u otro costo real vinculado a esta compra.'}
            </p>
          </div>
        {:else}
          <div class="divide-y divide-border">
            {#each costs as cost, index (cost.key)}
              <RetaceoCostEditor
                {manualEntry}
                {expenseTypes}
                {actualExpenses}
                {cost}
                {index}
                currency={item.currency}
                purchaseLines={item.details}
                quantityStage={manualEntry ? 'recibidas' : 'aceptadas'}
                {validation}
                {saving}
                uploading={uploadingCostId === cost.key}
                {deletingDocumentId}
                {downloadingDocumentId}
                {classLabel}
                {formatMoney}
                {formatQuantity}
                {productLabel}
                {unitLabel}
                onExpandedChange={(expanded) => (cost.expanded = expanded)}
                onTitleInput={(value) => {
                  cost.title = value;
                  clearValidation(`${cost.key}-title`);
                }}
                onClassificationChange={(value) => {
                  cost.classification = value;
                }}
                onAmountInput={(value) => {
                  cost.amount = value;
                  clearValidation(`${cost.key}-amount`);
                  preview(cost);
                }}
                onDescriptionInput={(value) => {
                  cost.description = value;
                  clearValidation(`${cost.key}-description`);
                }}
                onRemove={() => removeCost(cost.key)}
                onExpenseTypeChange={(value) => {
                  cost.expenseTypeId = value;
                  clearValidation(`${cost.key}-category`);
                }}
                onIncurredOnChange={(value) => {
                  cost.incurredOn = value;
                  clearValidation(`${cost.key}-date`);
                }}
                onSourceChange={(value) => (cost.sourcePurchaseOrderExpenseId = value || null)}
                onChooseFile={(event) => chooseFile(cost, event)}
                onDownload={(document) => void downloadDocument(cost, document)}
                onRemoveDocument={(document) => removeDocument(cost, document)}
              />
            {/each}
          </div>
        {/if}
      </article>

      <div
        class="flex flex-col gap-2 border-t border-border px-2 py-2 sm:flex-row sm:items-center sm:justify-between sm:px-0 sm:py-3"
        role="group"
        aria-label="Acciones del borrador de retaceo"
      >
        <p class="hidden text-xs text-foreground-muted sm:block">
          Al guardar, el servidor reparte cada importe según el FOB de cada producto.
        </p>
        <div class="flex w-full items-center gap-2 sm:w-auto sm:justify-end">
          <a
            href={`/retaceos/${item.id}`}
            class="inline-flex h-10 flex-1 items-center justify-center rounded-lg border border-border bg-surface px-4 text-sm font-medium text-foreground hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface sm:flex-none"
          >
            Cancelar
          </a>
          <Button
            type="submit"
            disabled={saving || uploadingCostId !== null || deletingDocumentId !== null}
            class="flex-1 sm:flex-none"
          >
            {saving ? 'Guardando…' : 'Guardar borrador'}
          </Button>
        </div>
      </div>
    </form>
  {/if}
</section>
