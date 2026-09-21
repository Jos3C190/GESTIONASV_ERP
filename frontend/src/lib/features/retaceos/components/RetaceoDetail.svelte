<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchasesApi } from '$lib/api/purchases';
  import { retaceosApi } from '$lib/api/retaceos';
  import RetaceoWorkflowActions from '$lib/features/retaceos/components/RetaceoWorkflowActions.svelte';
  import type { Retaceo, RetaceoStatus } from '$lib/types/retaceo';

  let { id }: { id: string } = $props();

  const STATUS_LABELS: Record<RetaceoStatus, string> = {
    draft: 'Borrador',
    calculated: 'Calculado',
    verified: 'Verificado',
    closed: 'Cerrado',
    cancelled: 'Cancelado'
  };

  let item = $state<Retaceo | null>(null);
  let purchaseLabel = $state('');
  let productLabels = $state<Map<number, string>>(new Map());
  let unitLabels = $state<Map<number, string>>(new Map());
  let loading = $state(true);
  let error = $state<string | null>(null);
  let requestSequence = 0;

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

  async function load(currentId: string) {
    const sequence = ++requestSequence;
    loading = true;
    error = null;

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
