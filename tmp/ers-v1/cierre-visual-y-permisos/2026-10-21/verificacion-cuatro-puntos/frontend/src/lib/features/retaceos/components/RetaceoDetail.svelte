<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchasesApi } from '$lib/api/purchases';
  import { retaceosApi } from '$lib/api/retaceos';
  import { openResolvedDocumentInBrowser } from '$lib/features/documents/open-document';
  import RetaceoWorkflowActions from '$lib/features/retaceos/components/RetaceoWorkflowActions.svelte';
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
  let purchaseLabel = $state('');
  let productLabels = $state<Map<number, string>>(new Map());
  let unitLabels = $state<Map<number, string>>(new Map());
  let loading = $state(true);
  let error = $state<string | null>(null);
  let documentError = $state<string | null>(null);
  let downloadingDocumentId = $state<string | null>(null);
  let requestSequence = 0;

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

    try {
      const retaceo = await retaceosApi.get(currentId);

      if (sequence !== requestSequence) return;

      item = retaceo;

      const productIds = [...new Set(retaceo.details.map((detail) => detail.product_id))];

      const [purchase, units, products] = await Promise.all([
        purchasesApi.get(retaceo.purchase_id).catch(() => null),
        catalogApi.listUnits(false).catch(() => []),
        Promise.all(
          productIds.map((productId) => catalogApi.getProduct(productId).catch(() => null))
        )
      ]);

      if (sequence !== requestSequence) return;

      purchaseLabel = purchase?.code ?? retaceo.purchase_id;

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
      purchaseLabel = '';
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
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
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
    {#if item.status === 'closed' && item.applied_at}
      <p class="rounded-lg border border-success/30 bg-success/5 p-4 text-sm text-success">
        Costo aplicado al inventario el {new Date(item.applied_at).toLocaleString('es-SV', {
          timeZone: 'America/El_Salvador'
        })}. El registro permanece disponible para consulta.
      </p>
    {/if}

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
            class="m-4 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
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
                        class="rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-xs text-warning"
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
                  class="rounded-lg border border-info/20 bg-info/5 px-3 py-2 text-sm text-foreground-muted"
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
            Los importes mostrados corresponden al cálculo realizado por el backend.
          </p>
        </div>

        <div class="overflow-x-auto">
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
