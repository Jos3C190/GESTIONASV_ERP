<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { suppliersApi } from '$lib/api/suppliers';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type {
    PurchaseQuotationComparison,
    PurchaseQuotationStatus
  } from '$lib/types/purchase-quotation';
  import type { Currency, Supplier } from '$lib/types/supplier';

  let { requestId }: { requestId: string } = $props();

  const STATUS_LABELS: Record<PurchaseQuotationStatus, string> = {
    draft: 'Borrador',
    requested: 'Solicitada',
    received: 'Recibida',
    under_evaluation: 'En evaluación',
    selected: 'Seleccionada',
    rejected: 'Rechazada',
    expired: 'Vencida',
    cancelled: 'Cancelada'
  };

  let rows = $state<PurchaseQuotationComparison[]>([]);
  let suppliers = $state<Supplier[]>([]);
  let currencies = $state<Currency[]>([]);
  let currency = $state('');
  let loading = $state(true);
  let error = $state<string | null>(null);
  let requestSequence = 0;

  let canRead = $derived(permissions.hasPermission('purchase_quotations:read'));
  let supplierNames = $derived(
    new Map(suppliers.map((supplier) => [supplier.id_supplier, supplier.name]))
  );

  function errorMessage(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return 'No se pudo comparar las cotizaciones de compra.';
  }

  function supplierLabel(id: number): string {
    return supplierNames.get(id) ?? `Proveedor #${id}`;
  }

  function formatMoney(value: string, code: string): string {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return value;
    return new Intl.NumberFormat('es-SV', {
      style: 'currency',
      currency: code
    }).format(amount);
  }

  function formatDate(value: string | null): string {
    if (!value) return 'Sin fecha límite';
    return new Intl.DateTimeFormat('es-SV', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      timeZone: 'America/El_Salvador'
    }).format(new Date(value));
  }

  async function loadOptions() {
    try {
      const [supplierPage, currencyRows] = await Promise.all([
        suppliersApi.listSuppliers({
          active_only: false,
          page: 1,
          size: 100
        }),
        suppliersApi.currencies()
      ]);

      suppliers = supplierPage.items;
      currencies = currencyRows.filter((item) => item.is_active);
    } catch {
      suppliers = [];
      currencies = [];
    }
  }

  async function loadComparison(currentRequestId: string, currentCurrency: string) {
    const sequence = ++requestSequence;
    loading = true;
    error = null;

    try {
      const result = await purchaseQuotationsApi.compare(
        currentRequestId,
        currentCurrency || undefined
      );

      if (sequence !== requestSequence) return;
      rows = result;
    } catch (cause: unknown) {
      if (sequence !== requestSequence) return;
      rows = [];
      error = errorMessage(cause);
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  function handleCurrencyChange(event: Event) {
    currency = (event.currentTarget as HTMLSelectElement).value;
  }

  function retry() {
    void loadComparison(requestId, currency);
  }

  $effect(() => {
    if (canRead) void loadOptions();
  });

  $effect(() => {
    const currentRequestId = requestId;
    const currentCurrency = currency;

    if (canRead && currentRequestId) {
      void loadComparison(currentRequestId, currentCurrency);
    } else {
      loading = false;
    }
  });
</script>

<div class="min-h-full bg-background px-4 pb-8 pt-4 sm:px-6 sm:pt-6 md:px-8 md:pt-8">
  <header class="mb-6 border-b border-border pb-4">
    <a
      href={`/purchase-requests/${requestId}`}
      class="text-sm font-medium text-primary hover:underline"
    >
      ← Volver a la solicitud de compra
    </a>
    <div class="mt-3">
      <p class="text-sm font-medium text-primary">Compras</p>
      <h1 class="text-2xl font-semibold tracking-tight text-foreground">
        Comparación de cotizaciones
      </h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Solicitud {requestId}
      </p>
    </div>
  </header>

  {#if !canRead}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      No tienes permiso para consultar cotizaciones de compra.
    </div>
  {:else}
    <section class="mb-5 rounded-xl border border-border bg-surface p-4">
      <label
        for="quotation-comparison-currency"
        class="mb-1 block text-sm font-medium text-foreground"
      >
        Moneda de comparación
      </label>
      <div class="flex flex-col gap-2 sm:flex-row sm:items-end">
        <select
          id="quotation-comparison-currency"
          aria-label="Moneda de comparación"
          value={currency}
          onchange={handleCurrencyChange}
          class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none sm:max-w-sm"
        >
          <option value="">Automática si todas usan la misma moneda</option>
          {#each currencies as item (item.code)}
            <option value={item.code}>{item.code} — {item.name}</option>
          {/each}
        </select>
        <p class="text-xs text-foreground-muted">
          No se convierten importes entre monedas distintas.
        </p>
      </div>
    </section>

    {#if error}
      <div
        class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
        role="alert"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <span>{error}</span>
          <Button type="button" size="sm" variant="secondary" onclick={retry}>Reintentar</Button>
        </div>
      </div>
    {:else if loading}
      <div class="overflow-hidden rounded-xl border border-border bg-surface">
        <div class="space-y-3 p-4">
          {#each Array(4) as _}
            <div class="grid grid-cols-6 gap-3">
              <div class="skeleton h-5 rounded"></div>
              <div class="skeleton h-5 rounded"></div>
              <div class="skeleton h-5 rounded"></div>
              <div class="skeleton h-5 rounded"></div>
              <div class="skeleton h-5 rounded"></div>
              <div class="skeleton h-5 rounded"></div>
            </div>
          {/each}
        </div>
      </div>
    {:else if rows.length === 0}
      <div
        class="flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface px-6 text-center"
      >
        <h2 class="font-medium text-foreground">No hay ofertas comparables</h2>
        <p class="mt-1 max-w-lg text-sm text-foreground-muted">
          Solo se incluyen cotizaciones recibidas, en evaluación o seleccionadas que sigan vigentes.
        </p>
      </div>
    {:else}
      <div class="overflow-x-auto rounded-xl border border-border bg-surface">
        <table class="min-w-full divide-y divide-border text-sm">
          <thead
            class="bg-surface-muted text-left text-xs uppercase tracking-wide text-foreground-muted"
          >
            <tr>
              <th class="px-4 py-3 font-medium">Orden</th>
              <th class="px-4 py-3 font-medium">Cotización</th>
              <th class="px-4 py-3 font-medium">Proveedor</th>
              <th class="px-4 py-3 font-medium">Total</th>
              <th class="px-4 py-3 font-medium">Entrega</th>
              <th class="px-4 py-3 font-medium">Vigencia</th>
              <th class="px-4 py-3 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each rows as row, index (row.quotation_id)}
              <tr class="text-foreground">
                <td class="whitespace-nowrap px-4 py-3 font-medium">#{index + 1}</td>
                <td class="whitespace-nowrap px-4 py-3">
                  <a
                    href={`/purchase-quotations/${row.quotation_id}`}
                    class="font-medium text-primary hover:underline"
                  >
                    {row.code}
                  </a>
                </td>
                <td class="px-4 py-3">{supplierLabel(row.supplier_id)}</td>
                <td class="whitespace-nowrap px-4 py-3 font-medium">
                  {formatMoney(row.total, row.currency)}
                </td>
                <td class="whitespace-nowrap px-4 py-3">
                  {row.delivery_days === null ? '—' : `${row.delivery_days} días`}
                </td>
                <td class="whitespace-nowrap px-4 py-3">{formatDate(row.valid_until)}</td>
                <td class="whitespace-nowrap px-4 py-3">
                  <span
                    class="inline-flex rounded-full border border-border bg-surface-muted px-2.5 py-1 text-xs font-medium text-foreground"
                  >
                    {STATUS_LABELS[row.status]}
                  </span>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <p class="mt-3 text-xs text-foreground-muted">
        El orden es calculado por el backend: menor total, luego menor plazo de entrega y finalmente
        código.
      </p>
    {/if}
  {/if}
</div>
