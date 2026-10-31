<script lang="ts">
  import { onDestroy } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import ReportDownloads from '$lib/components/ui/ReportDownloads.svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchasesApi } from '$lib/api/purchases';
  import { retaceosApi } from '$lib/api/retaceos';
  import { openResolvedDocumentInBrowser } from '$lib/features/documents/open-document';
  import RetaceoWorkflowActions from '$lib/features/retaceos/components/RetaceoWorkflowActions.svelte';
  import RetaceoAveragePanel from './RetaceoAveragePanel.svelte';
  import RetaceoPlannedExpenses from './RetaceoPlannedExpenses.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Purchase } from '$lib/types/purchase';
  import type {
    Retaceo,
    RetaceoCost,
    RetaceoCostClass,
    RetaceoCostDocument,
    RetaceoStatus
  } from '$lib/types/retaceo';

  let { id }: { id: string } = $props();

  const STATUS_LABELS: Record<RetaceoStatus, string> = {
    draft: 'Borrador',
    calculated: 'Calculado',
    verified: 'Verificado',
    closed: 'Cerrado',
    cancelled: 'Cancelado'
  };

  let item = $state<Retaceo | null>(null);
  let costs = $derived(item?.costs ?? []);
  let receiptPurchase = $state<Purchase | null>(null);
  let purchaseLabel = $derived(receiptPurchase?.code ?? item?.purchase_id ?? '');
  let needsReceipt = $derived(
    ['retaceo_before_inventory', 'placement_before_inventory'].includes(
      receiptPurchase?.inventory_workflow ?? ''
    ) && receiptPurchase?.status === 'received'
  );
  let canContinueToInventory = $derived(
    permissions.hasPermission('inventory:read') && permissions.hasPermission('warehouses.view')
  );
  let inventoryHref = $derived(
    item &&
      receiptPurchase?.warehouse_id &&
      receiptPurchase.id === item.purchase_id &&
      receiptPurchase.company_id === item.company_id
      ? receiptPurchase.inventory_workflow === 'placement_before_inventory'
        ? `/inventory?warehouse_id=${encodeURIComponent(receiptPurchase.warehouse_id)}`
        : `/warehouses/${encodeURIComponent(receiptPurchase.warehouse_id)}?tab=inventario`
      : null
  );
  let contextKey = $derived([company.id ?? '', branch.id ?? ''].join('|'));
  let productLabels = $state<Map<number, string>>(new Map());
  let unitLabels = $state<Map<number, string>>(new Map());
  let loading = $state(true);
  let error = $state<string | null>(null);
  let documentError = $state<string | null>(null);
  let downloadingDocumentId = $state<string | null>(null);
  let requestSequence = 0;

  onDestroy(() => {
    requestSequence += 1;
  });

  const COST_CLASS_LABELS: Record<RetaceoCostClass, string> = {
    freight: 'Flete',
    expense: 'Otro gasto',
    dai: 'DAI',
    import_vat: 'IVA de importación'
  };

  function errorMessage(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;

    return 'No se pudo cargar el retaceo.';
  }

  function formatMoney(value: string, currency: string): string {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return value;

    return new Intl.NumberFormat('es-SV', {
      style: 'currency',
      currency
    }).format(amount);
  }

  function formatQuantity(value: string): string {
    const quantity = Number(value);
    if (!Number.isFinite(quantity)) return value;

    return new Intl.NumberFormat('es-SV', {
      maximumFractionDigits: 6
    }).format(quantity);
  }

  function formatPercentage(value: string): string {
    const percentage = Number(value);
    if (!Number.isFinite(percentage)) return `${value}%`;

    return `${new Intl.NumberFormat('es-SV', {
      maximumFractionDigits: 6
    }).format(percentage)}%`;
  }

  function formatDate(value: string | null): string {
    if (!value) return '—';

    return new Intl.DateTimeFormat('es-SV', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      timeZone: 'America/El_Salvador'
    }).format(new Date(value));
  }

  function productLabel(id: number): string {
    return productLabels.get(id) ?? `Producto #${id}`;
  }

  function unitLabel(id: number): string {
    return unitLabels.get(id) ?? `Unidad #${id}`;
  }

  function costClassLabel(classification: RetaceoCostClass): string {
    return COST_CLASS_LABELS[classification];
  }

  function allocationProductLabel(purchaseDetailId: string): string {
    const detail = item?.details.find((line) => line.purchase_detail_id === purchaseDetailId);
    if (!detail) return `Línea recibida ${purchaseDetailId.slice(0, 8)}`;
    return `${productLabel(detail.product_id)} · ${unitLabel(detail.unit_id)}`;
  }

  async function downloadDocument(cost: RetaceoCost, document: RetaceoCostDocument) {
    if (!item || downloadingDocumentId) return;
    downloadingDocumentId = document.id;
    documentError = null;
    try {
      await openResolvedDocumentInBrowser(async () => {
        const result = await retaceosApi.createCostDocumentDownloadUrl(
          item!.id,
          cost.id,
          document.document_id
        );
        return result.url;
      });
    } catch (cause: unknown) {
      documentError = errorMessage(cause);
    } finally {
      downloadingDocumentId = null;
    }
  }

  async function load(currentId: string) {
    const sequence = ++requestSequence;
    loading = true;
    error = null;
    documentError = null;
    item = null;
    receiptPurchase = null;

    try {
      const retaceo = await retaceosApi.get(currentId);

      if (sequence !== requestSequence) return;

      item = retaceo;

      const productIds = [...new Set(retaceo.details.map((detail) => detail.product_id))];

      const [purchase, units, products] = await Promise.all([
        purchasesApi.get(retaceo.purchase_id),
        catalogApi.listUnits(false).catch(() => []),
        Promise.all(
          productIds.map((productId) => catalogApi.getProduct(productId).catch(() => null))
        )
      ]);

      if (sequence !== requestSequence) return;

      receiptPurchase = purchase;

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

      item = null;
      receiptPurchase = null;
      documentError = null;
      productLabels = new Map();
      unitLabels = new Map();
      error = errorMessage(cause);
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  function handleUpdated(updated: Retaceo) {
    item = updated;
  }

  function retry() {
    void load(id);
  }

  $effect(() => {
    const currentId = id;
    void contextKey;
    if (currentId) void load(currentId);
  });
</script>

<section class="space-y-5">
  <div>
    <a href="/retaceos" class="text-sm font-medium text-primary hover:underline">
      ← Volver a retaceos
    </a>
  </div>

  {#if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-foreground"
      role="alert"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span>{error}</span>
        <Button size="sm" variant="secondary" onclick={retry}>Reintentar</Button>
      </div>
    </div>
  {:else if loading}
    <div class="space-y-4" aria-label="Cargando detalle de retaceo">
      <div class="skeleton h-9 w-56 rounded"></div>

      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {#each Array(4) as _}
          <div class="skeleton h-28 rounded-xl"></div>
        {/each}
      </div>

      <div class="skeleton h-72 rounded-xl"></div>
    </div>
  {:else if item}
    <header class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <p class="text-sm font-medium text-primary">Retaceo</p>

        <h1 class="text-2xl font-semibold tracking-tight text-foreground">
          {item.code}
        </h1>

        <p class="mt-1 text-sm text-foreground-muted">
          Creado {formatDate(item.created_at)}
        </p>
      </div>

      <span
        class="inline-flex w-fit rounded-full border border-border bg-surface-muted px-3 py-1.5 text-sm font-medium text-foreground"
      >
        {STATUS_LABELS[item.status]}
      </span>
    </header>

    <RetaceoWorkflowActions retaceo={item} onupdated={handleUpdated} />
    <ReportDownloads path={`/retaceos/${item.id}/export`} code={item.code} />
    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <article class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">
          Compra origen
        </p>

        <a
          href={`/purchases/${item.purchase_id}`}
          class="mt-2 inline-block font-medium text-primary hover:underline"
        >
          {purchaseLabel || item.purchase_id}
        </a>
      </article>

      <article class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">FOB total</p>

        <p class="mt-2 font-semibold text-foreground">
          {formatMoney(item.total_fob, item.currency)}
        </p>
      </article>

      <article class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">
          Costo aterrizado
        </p>

        <p class="mt-2 font-semibold text-foreground">
          {formatMoney(item.total_cost, item.currency)}
        </p>
      </article>

      <article class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">
          IVA de importación
        </p>

        <p class="mt-2 font-semibold text-foreground">
          {formatMoney(item.import_vat, item.currency)}
        </p>

        <p class="mt-1 text-xs text-foreground-muted">
          Informativo. No forma parte del costo aterrizado.
        </p>
      </article>
    </div>

    {#if item.origin_country || item.import_invoice_number || item.import_invoice_date || item.import_policy_number || item.import_policy_date}
      <section
        class="rounded-xl border border-border bg-surface p-5"
        aria-labelledby="import-data-heading"
      >
        <h2 id="import-data-heading" class="font-semibold text-foreground">
          Documentación de importación
        </h2>
        <dl class="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <dt class="text-xs text-foreground-muted">País de origen</dt>
            <dd class="mt-1 text-foreground">{item.origin_country ?? 'No informado'}</dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">Factura</dt>
            <dd class="mt-1 text-foreground">{item.import_invoice_number ?? 'No informada'}</dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">Fecha de factura</dt>
            <dd class="mt-1 text-foreground">
              {item.import_invoice_date
                ? item.import_invoice_date.split('-').reverse().join('/')
                : 'No informada'}
            </dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">Póliza</dt>
            <dd class="mt-1 text-foreground">{item.import_policy_number ?? 'No informada'}</dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">Fecha de póliza</dt>
            <dd class="mt-1 text-foreground">
              {item.import_policy_date
                ? item.import_policy_date.split('-').reverse().join('/')
                : 'No informada'}
            </dd>
          </div>
        </dl>
      </section>
    {/if}
    {#if receiptPurchase && ['retaceo_before_inventory', 'placement_before_inventory'].includes(receiptPurchase.inventory_workflow ?? '') && permissions.hasPermission('purchase_orders:read')}
      <RetaceoPlannedExpenses
        orderId={receiptPurchase.purchase_order_id}
        currency={item.currency}
        actualExpenses={Number(item.total_freight) +
          Number(item.total_expenses) +
          Number(item.total_dai)}
      />
    {/if}
    {#if ['retaceo_before_inventory', 'placement_before_inventory'].includes(receiptPurchase?.inventory_workflow ?? '') && permissions.hasPermission('inventory:valuation') && branch.accessAllBranches}
      <RetaceoAveragePanel
        retaceoId={item.id}
        {contextKey}
        {productLabels}
        {unitLabels}
        revision={`${item.updated_at}:${item.applied_at}`}
      />
    {/if}
    {#if item.status === 'closed' && item.applied_at}
      <p class="rounded-lg border border-success/30 bg-success/5 p-4 text-sm text-success">
        Costo aplicado al inventario el {new Date(item.applied_at).toLocaleString('es-SV', {
          timeZone: 'America/El_Salvador'
        })}. El registro permanece disponible para consulta.
      </p>
    {/if}

    {#if item.status === 'closed'}
      <section
        class="rounded-xl border border-border bg-surface p-4"
        aria-labelledby="retaceo-next-step"
      >
        <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div class="min-w-0">
            <h2 id="retaceo-next-step" class="font-semibold text-foreground">
              Siguiente paso: {needsReceipt
                ? 'verificar recepción en bodega'
                : 'ubicación y etiquetas'}
            </h2>
            <p class="mt-1 text-sm text-foreground-muted">
              {#if needsReceipt}El retaceo está cerrado. Verifica las cantidades desde la compra {purchaseLabel}.
                Después continúa con medidas, etiquetas y ubicación en bodega.
                {#if receiptPurchase?.inventory_workflow === 'placement_before_inventory'}La
                  cantidad y el valor se ingresan al confirmar la ubicación.{/if}
              {:else}Continúa en la bodega de recepción de {purchaseLabel}. Revisa la ubicación, las
                medidas y las etiquetas de los productos hasta dejarlos disponibles.
              {/if}
            </p>
          </div>
          {#if needsReceipt && permissions.hasPermission('purchases:read')}
            <a
              class="rounded-lg bg-foreground px-4 py-2.5 text-sm font-medium text-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              href={`/purchases/${item.purchase_id}`}>Verificar recepción →</a
            >
          {:else if canContinueToInventory && inventoryHref}
            <a
              href={inventoryHref}
              class="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-surface hover:bg-foreground-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              Continuar en inventario <span aria-hidden="true">→</span>
            </a>
          {/if}
        </div>
        {#if !canContinueToInventory}
          <p class="mt-3 text-sm text-foreground-muted">
            Un usuario con acceso a almacenes e inventario debe continuar con esta revisión.
          </p>
        {:else if !inventoryHref}
          <div
            class="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-foreground"
            role="alert"
          >
            <p>No se pudo identificar la bodega de esta compra. Vuelve a cargar para continuar.</p>
            <Button size="sm" variant="secondary" onclick={retry}>Volver a cargar</Button>
          </div>
        {/if}
      </section>
    {/if}

    {#if costs.length > 0}
      <article class="overflow-hidden rounded-xl border border-border bg-surface">
        <div
          class="flex flex-col gap-1 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h2 class="font-semibold text-foreground">Gastos reales y comprobantes</h2>
            <p class="mt-1 text-sm text-foreground-muted">
              Origen, distribución manual por producto y respaldo documental conservado.
            </p>
          </div>
          <span class="text-sm text-foreground-muted">{costs.length} registro(s)</span>
        </div>

        {#if documentError}
          <p
            class="m-4 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-foreground"
            role="alert"
          >
            {documentError}
          </p>
        {/if}

        <div class="divide-y divide-border">
          {#each costs as cost (cost.id)}
            <section class="space-y-4 p-4" aria-label={`Costo ${cost.title}`}>
              <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-2">
                    <h3 class="font-medium text-foreground">{cost.title}</h3>
                    <span
                      class="rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs text-foreground-muted"
                    >
                      {costClassLabel(cost.classification)}
                    </span>
                    {#if !cost.is_active}
                      <span
                        class="rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-xs text-foreground"
                        >Histórico · inactivo</span
                      >
                    {/if}
                  </div>
                  {#if cost.description}
                    <p class="mt-1 whitespace-pre-wrap text-sm text-foreground-muted">
                      {cost.description}
                    </p>
                  {/if}
                  {#if cost.source_purchase_order_expense_id}
                    <p
                      class="mt-1 text-xs text-foreground-muted"
                      title={cost.source_purchase_order_expense_id}
                    >
                      Importado de gasto de la orden de compra · referencia {cost.source_purchase_order_expense_id.slice(
                        0,
                        8
                      )}
                    </p>
                  {:else}
                    <p class="mt-1 text-xs text-foreground-muted">Gasto agregado en el retaceo</p>
                  {/if}
                </div>
                <p class="shrink-0 font-semibold text-foreground">
                  {formatMoney(cost.amount, item.currency)}
                </p>
              </div>

              {#if cost.classification === 'import_vat'}
                <p
                  class="rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-sm text-foreground-muted"
                >
                  IVA informativo; no forma parte del costo aterrizado.
                </p>
              {:else if cost.allocations.length > 0}
                <div class="rounded-lg border border-border">
                  <h4
                    class="border-b border-border px-3 py-2 text-xs font-semibold uppercase tracking-wide text-foreground-muted"
                  >
                    Distribución registrada por línea recibida
                  </h4>
                  <ul class="divide-y divide-border">
                    {#each cost.allocations as allocation (allocation.purchase_detail_id)}
                      <li
                        class="flex flex-col gap-1 px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between"
                      >
                        <span class="min-w-0 truncate text-foreground"
                          >{allocationProductLabel(allocation.purchase_detail_id)}</span
                        >
                        <span class="font-medium text-foreground"
                          >{formatMoney(allocation.amount, item.currency)}</span
                        >
                      </li>
                    {/each}
                  </ul>
                </div>
              {/if}

              <div>
                <h4 class="text-xs font-semibold uppercase tracking-wide text-foreground-muted">
                  Comprobantes
                </h4>
                {#if cost.documents.length === 0}
                  <p class="mt-2 text-sm text-foreground-muted">
                    No hay comprobantes adjuntos a este gasto.
                  </p>
                {:else}
                  <ul class="mt-2 divide-y divide-border rounded-lg border border-border">
                    {#each cost.documents as document (document.id)}
                      <li
                        class="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div class="min-w-0">
                          <p class="truncate text-sm font-medium text-foreground">
                            {document.file_name}
                          </p>
                          <p class="mt-0.5 text-xs text-foreground-muted">
                            {document.uploaded_at ? 'Comprobante conservado' : 'Carga incompleta'} · {document.file_type}
                          </p>
                        </div>
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={downloadingDocumentId !== null || !document.uploaded_at}
                          onclick={() => void downloadDocument(cost, document)}
                        >
                          {downloadingDocumentId === document.id
                            ? 'Preparando…'
                            : 'Ver comprobante'}
                        </Button>
                      </li>
                    {/each}
                  </ul>
                {/if}
              </div>
            </section>
          {/each}
        </div>
      </article>
    {/if}

    <div class="grid gap-5 xl:grid-cols-[2fr_1fr]">
      <article class="rounded-xl border border-border bg-surface">
        <div class="border-b border-border px-4 py-3">
          <h2 class="font-semibold text-foreground">Distribución por producto</h2>

          <p class="mt-1 text-sm text-foreground-muted">
            Los importes corresponden al cálculo guardado de este retaceo.
          </p>
        </div>

        <div class="divide-y divide-border md:hidden">
          {#each item.details as detail (detail.id)}
            <article class="p-4">
              <h3 class="text-sm font-semibold text-foreground">
                {productLabel(detail.product_id)}
              </h3>
              <p class="mt-1 text-xs text-foreground-muted">
                {formatQuantity(detail.quantity)}
                {unitLabel(detail.unit_id)}
              </p>
              <dl class="mt-4 space-y-3 text-sm">
                <div class="flex justify-between gap-3">
                  <dt class="text-foreground-muted">FOB</dt>
                  <dd class="tabular-nums text-foreground">
                    {formatMoney(detail.cost_fob, item.currency)}
                  </dd>
                </div>
                <div class="flex justify-between gap-3">
                  <dt class="font-medium text-foreground">Costo total</dt>
                  <dd class="font-semibold tabular-nums text-foreground">
                    {formatMoney(detail.total_cost, item.currency)}
                  </dd>
                </div>
              </dl>
              <details class="mt-4 border-t border-border pt-3">
                <summary class="cursor-pointer text-sm font-medium text-foreground"
                  >Desglose del costo</summary
                >
                <dl class="mt-3 space-y-3 text-sm">
                  {#each [['Flete', detail.freight], ['Gastos', detail.expenses], ['DAI', detail.dai], ['Costo unitario', detail.unit_cost]] as cost (cost[0])}<div
                      class="flex justify-between gap-3"
                    >
                      <dt class="text-foreground-muted">{cost[0]}</dt>
                      <dd class="tabular-nums text-foreground">
                        {formatMoney(cost[1] ?? '0', item.currency)}
                      </dd>
                    </div>{/each}
                </dl>
              </details>
            </article>
          {/each}
        </div>
        <div class="hidden overflow-x-auto md:block">
          <table class="min-w-full divide-y divide-border text-sm">
            <thead
              class="bg-surface-muted text-left text-xs uppercase tracking-wide text-foreground-muted"
            >
              <tr>
                <th class="px-4 py-3 font-medium">Producto</th>
                <th class="px-4 py-3 font-medium">Unidad</th>
                <th class="px-4 py-3 font-medium">Cantidad</th>
                <th class="px-4 py-3 font-medium">FOB</th>
                <th class="px-4 py-3 font-medium">Flete</th>
                <th class="px-4 py-3 font-medium">Gastos</th>
                <th class="px-4 py-3 font-medium">DAI</th>
                <th class="px-4 py-3 font-medium">Costo total</th>
                <th class="px-4 py-3 font-medium">Costo unitario</th>
              </tr>
            </thead>

            <tbody class="divide-y divide-border">
              {#each item.details as detail (detail.id)}
                <tr class="text-foreground">
                  <td class="min-w-56 px-4 py-3 font-medium">
                    {productLabel(detail.product_id)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3 text-foreground-muted">
                    {unitLabel(detail.unit_id)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3">
                    {formatQuantity(detail.quantity)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3">
                    {formatMoney(detail.cost_fob, item.currency)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3">
                    {formatMoney(detail.freight, item.currency)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3">
                    {formatMoney(detail.expenses, item.currency)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3">
                    {formatMoney(detail.dai, item.currency)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3 font-medium">
                    {formatMoney(detail.total_cost, item.currency)}
                  </td>

                  <td class="whitespace-nowrap px-4 py-3 font-medium">
                    {formatMoney(detail.unit_cost, item.currency)}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </article>

      <aside class="space-y-5">
        <article class="rounded-xl border border-border bg-surface p-4">
          <h2 class="font-semibold text-foreground">Costos de importación</h2>

          <dl class="mt-4 space-y-3 text-sm">
            <div class="flex justify-between gap-4">
              <dt class="text-foreground-muted">
                Flete · {formatPercentage(item.freight_percentage)}
              </dt>

              <dd class="font-medium text-foreground">
                {formatMoney(item.total_freight, item.currency)}
              </dd>
            </div>

            <div class="flex justify-between gap-4">
              <dt class="text-foreground-muted">
                Gastos · {formatPercentage(item.expense_percentage)}
              </dt>

              <dd class="font-medium text-foreground">
                {formatMoney(item.total_expenses, item.currency)}
              </dd>
            </div>

            <div class="flex justify-between gap-4">
              <dt class="text-foreground-muted">
                DAI · {formatPercentage(item.dai_percentage)}
              </dt>

              <dd class="font-medium text-foreground">
                {formatMoney(item.total_dai, item.currency)}
              </dd>
            </div>

            <div class="flex justify-between gap-4 border-t border-border pt-3">
              <dt class="font-semibold text-foreground">Costo aterrizado</dt>

              <dd class="font-semibold text-foreground">
                {formatMoney(item.total_cost, item.currency)}
              </dd>
            </div>
          </dl>
        </article>

        {#if item.notes}
          <article class="rounded-xl border border-border bg-surface p-4">
            <h2 class="font-semibold text-foreground">Notas</h2>

            <p class="mt-3 whitespace-pre-wrap text-sm text-foreground-muted">
              {item.notes}
            </p>
          </article>
        {/if}
      </aside>
    </div>
  {/if}
</section>
