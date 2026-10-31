<script lang="ts">
  import { goto } from '$app/navigation';
  import { tick } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchasesApi } from '$lib/api/purchases';
  import { retaceosApi } from '$lib/api/retaceos';
  import CustomsReferencePanel from '$lib/features/retaceos/components/CustomsReferencePanel.svelte';
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
    { value: 'freight', label: 'Flete' },
    { value: 'expense', label: 'Otro gasto' },
    { value: 'dai', label: 'DAI' },
    { value: 'import_vat', label: 'IVA de importación' }
  ];

  let item = $state<Retaceo | null>(null);
  let purchaseLabel = $state('');
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
    return COST_CLASSES.find((option) => option.value === value)?.label ?? 'Otro gasto';
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
      },
      {
        classification: 'import_vat',
        title: 'IVA de importación heredado',
        total: current.import_vat,
        amountFor: () => '0'
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
    item = current;
    const activeCosts = (current.costs ?? []).filter((cost) => cost.is_active).map(mapCost);
    const nextCosts = activeCosts.length > 0 ? activeCosts : legacyCosts(current);
    const firstCost = nextCosts[0];
    if (firstCost) firstCost.expanded = true;
    costs = nextCosts;
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
        purchasesApi.get(current.purchase_id).catch(() => null),
        catalogApi.listUnits(false).catch(() => []),
        Promise.all(
          [...new Set(current.details.map((detail) => detail.product_id))].map((productId) =>
            catalogApi.getProduct(productId).catch(() => null)
          )
        )
      ]);

      if (sequence !== requestSequence) return;

      purchaseLabel = purchase?.code ?? current.purchase_id;
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
    if (!cost || cost.sourcePurchaseOrderExpenseId) return;
    costs = costs.filter((row) => row.key !== key);
  }

  function allocatedTotal(cost: EditableRetaceoCost): number {
    return Object.values(cost.allocations).reduce((total, amount) => {
      const parsed = Number(amount);
      return total + (Number.isFinite(parsed) ? parsed : 0);
    }, 0);
  }

  function remaining(cost: EditableRetaceoCost): number {
    return Number(cost.amount || 0) - allocatedTotal(cost);
  }

  function allocationPercent(cost: EditableRetaceoCost): number {
    const amount = Number(cost.amount);
    if (!Number.isFinite(amount) || amount <= 0) return 0;
    return Math.max(0, Math.min(100, (allocatedTotal(cost) / amount) * 100));
  }

  function clearValidation(key: string) {
    if (!(key in validation)) return;
    const next = { ...validation };
    delete next[key];
    validation = next;
  }

  function validate(): boolean {
    const next: Record<string, string> = {};
    for (const cost of costs) {
      const amount = Number(cost.amount);
      if (!cost.title.trim()) next[`${cost.key}-title`] = 'Escribe el concepto del gasto.';
      if (!cost.amount.trim() || !Number.isFinite(amount) || amount <= 0) {
        next[`${cost.key}-amount`] = 'El monto debe ser mayor que cero.';
      } else if (cost.classification !== 'import_vat' && allocatedTotal(cost) - amount > 0.000001) {
        next[`${cost.key}-allocation`] = 'La distribución no puede superar el monto del gasto.';
      }
    }
    validation = next;
    return Object.keys(next).length === 0;
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

    const cost = costs.find((row) => firstInvalidField.startsWith(`${row.key}-`));
    const details = cost
      ? document.querySelector<HTMLDetailsElement>(`details[data-cost-key="${cost.key}"]`)
      : null;
    const control = firstInvalidField.endsWith('-allocation')
      ? details?.querySelector<HTMLInputElement>('input[aria-invalid="true"]')
      : document.getElementById(firstInvalidField);

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
        total_freight: item.total_freight,
        total_expenses: item.total_expenses,
        total_dai: item.total_dai,
        import_vat: item.import_vat,
        notes: item.notes,
        costs: costs.map((cost) => ({
          ...(cost.id ? { id: cost.id } : {}),
          classification: cost.classification,
          title: cost.title.trim(),
          description: cost.description.trim() || null,
          amount: cost.amount,
          allocations:
            cost.classification === 'import_vat'
              ? []
              : Object.entries(cost.allocations)
                  .filter(([, amount]) => Number(amount) > 0)
                  .map(([purchase_detail_id, amount]) => ({ purchase_detail_id, amount }))
        }))
      });
      hydrate(updated);
      item = updated;
      notice = 'Borrador guardado. Abriendo el detalle para calcular el retaceo.';
      try {
        await goto(`/retaceos/${updated.id}`);
      } catch {
        notice = null;
        error = 'El borrador se guardó, pero no se pudo abrir el detalle para calcularlo.';
      }
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
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
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
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
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
          Orden {purchaseLabel} · {item.currency}. Distribuye cada costo manualmente entre las
          líneas aceptadas.
        </p>
      </div>
      <span
        class="inline-flex w-fit rounded-full border border-warning/30 bg-warning/10 px-3 py-1.5 text-sm font-medium text-warning"
      >
        Borrador editable
      </span>
    </header>

    {#if error}
      <div
        class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
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
      </div>
    {/if}

    <CustomsReferencePanel />

    <article class="rounded-xl border border-primary/20 bg-primary/5 p-4">
      <div class="flex gap-3">
        <span
          class="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
          aria-hidden="true">i</span
        >
        <div>
          <h2 class="text-base font-semibold text-foreground">Criterio del retaceo</h2>
          <p class="mt-2 max-w-4xl text-sm leading-6 text-foreground-muted">
            Los gastos que vienen de la orden conservan su referencia y sus comprobantes. Adjunta un
            documento a cada gasto y reparte su monto entre los productos aceptados. El IVA de
            importación queda informativo y no se suma al costo aterrizado. Estos cambios solo
            afectan costos; no crean movimientos de inventario.
          </p>
        </div>
      </div>
    </article>

    <form
      class="space-y-5"
      onsubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <article class="overflow-hidden rounded-xl border border-border bg-surface">
        <div
          class="flex flex-col gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h2 class="font-semibold text-foreground">Gastos reales</h2>
            <p class="mt-1 text-sm text-foreground-muted">
              {costs.length} concepto(s) · Los gastos añadidos aquí también requieren comprobante.
            </p>
          </div>
          <Button
            type="button"
            variant="secondary"
            onclick={addCost}
            disabled={saving || uploadingCostId !== null || deletingDocumentId !== null}
          >
            + Agregar gasto
          </Button>
        </div>

        {#if costs.length === 0}
          <div class="m-4 rounded-xl border border-dashed border-border px-5 py-8 text-center">
            <p class="font-medium text-foreground">Todavía no hay gastos para distribuir</p>
            <p class="mt-1 text-sm text-foreground-muted">
              Agrega flete, gastos, DAI u otro costo real vinculado a esta compra.
            </p>
          </div>
        {:else}
          <div class="divide-y divide-border">
            {#each costs as cost, index (cost.key)}
              <RetaceoCostEditor
                {cost}
                {index}
                currency={item.currency}
                purchaseLines={item.details}
                {validation}
                {saving}
                uploading={uploadingCostId === cost.key}
                {deletingDocumentId}
                {downloadingDocumentId}
                allocatedAmount={allocatedTotal(cost)}
                remainingAmount={remaining(cost)}
                allocatedPercent={allocationPercent(cost)}
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
                  clearValidation(`${cost.key}-allocation`);
                }}
                onAmountInput={(value) => {
                  cost.amount = value;
                  clearValidation(`${cost.key}-amount`);
                  clearValidation(`${cost.key}-allocation`);
                }}
                onDescriptionInput={(value) => (cost.description = value)}
                onAllocationInput={(purchaseDetailId, value) => {
                  cost.allocations[purchaseDetailId] = value;
                  clearValidation(`${cost.key}-allocation`);
                }}
                onRemove={() => removeCost(cost.key)}
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
          Al calcular, cada gasto debe estar respaldado y distribuido por completo.
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
