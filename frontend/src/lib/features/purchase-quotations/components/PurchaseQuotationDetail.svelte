<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import PurchaseQuotationWorkflowActions from '$lib/features/purchase-quotations/components/PurchaseQuotationWorkflowActions.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { suppliersApi } from '$lib/api/suppliers';
  import type { PurchaseQuotation, PurchaseQuotationStatus } from '$lib/types/purchase-quotation';
  import type { Supplier } from '$lib/types/supplier';

  let { id }: { id: string } = $props();

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

  let item = $state<PurchaseQuotation | null>(null);
  let supplier = $state<Supplier | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let requestSequence = 0;

  function errorMessage(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return 'No se pudo cargar la cotización de compra.';
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

  async function load(currentId: string) {
    const sequence = ++requestSequence;
    loading = true;
    error = null;

    try {
      const quotation = await purchaseQuotationsApi.get(currentId);
      if (sequence !== requestSequence) return;

      item = quotation;

      try {
        supplier = await suppliersApi.getSupplier(quotation.supplier_id);
      } catch {
        supplier = null;
      }
    } catch (cause: unknown) {
      if (sequence !== requestSequence) return;
      item = null;
      supplier = null;
      error = errorMessage(cause);
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  function handleWorkflowUpdated(updated: PurchaseQuotation) {
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
    <a href="/purchase-quotations" class="text-sm font-medium text-primary hover:underline">
      ← Volver a cotizaciones
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
    <div class="space-y-4">
      <div class="skeleton h-9 w-56 rounded"></div>
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {#each Array(4) as _}
          <div class="skeleton h-28 rounded-xl"></div>
        {/each}
      </div>
      <div class="skeleton h-64 rounded-xl"></div>
    </div>
  {:else if item}
    <header class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <p class="text-sm font-medium text-primary">Cotización de compra</p>
        <h1 class="text-2xl font-semibold tracking-tight text-foreground">{item.code}</h1>
        <p class="mt-1 text-sm text-foreground-muted">
          {supplier?.name ?? `Proveedor #${item.supplier_id}`}
        </p>
      </div>
      <span
        class="inline-flex w-fit rounded-full border border-border bg-surface-muted px-3 py-1.5 text-sm font-medium text-foreground"
      >
        {STATUS_LABELS[item.status]}
      </span>
    </header>

    <PurchaseQuotationWorkflowActions quotation={item} onupdated={handleWorkflowUpdated} />

    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <article class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">Proveedor</p>
        <p class="mt-2 font-medium text-foreground">
          {supplier?.code
            ? `${supplier.code} — ${supplier.name}`
            : `Proveedor #${item.supplier_id}`}
        </p>
      </article>

      <article class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">
          Fecha cotización
        </p>
        <p class="mt-2 font-medium text-foreground">{formatDate(item.quotation_date)}</p>
      </article>

      <article class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">Vigencia</p>
        <p class="mt-2 font-medium text-foreground">{formatDate(item.valid_until)}</p>
      </article>

      <article class="rounded-xl border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">Entrega</p>
        <p class="mt-2 font-medium text-foreground">
          {item.delivery_days === null ? '—' : `${item.delivery_days} días`}
        </p>
      </article>
    </div>

    <div class="grid gap-5 xl:grid-cols-[2fr_1fr]">
      <div class="space-y-5">
        <article class="rounded-xl border border-border bg-surface">
          <div class="border-b border-border px-4 py-3">
            <h2 class="font-semibold text-foreground">Solicitudes vinculadas</h2>
          </div>
          {#if item.request_links.length === 0}
            <p class="p-4 text-sm text-foreground-muted">No hay solicitudes vinculadas.</p>
          {:else}
            <ul class="divide-y divide-border">
              {#each item.request_links as link (link.id)}
                <li class="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                  <div>
                    <a
                      href={`/purchase-requests/${link.purchase_request_id}`}
                      class="font-medium text-primary hover:underline"
                    >
                      Solicitud {link.purchase_request_id}
                    </a>
                    <p class="mt-1 text-xs text-foreground-muted">
                      {link.details.length}
                      {link.details.length === 1 ? 'línea vinculada' : 'líneas vinculadas'}
                    </p>
                  </div>
                  <a
                    href={`/purchase-quotations/comparison/${link.purchase_request_id}`}
                    class="text-sm font-medium text-primary hover:underline"
                  >
                    Comparar ofertas
                  </a>
                </li>
              {/each}
            </ul>
          {/if}
        </article>

        <article class="rounded-xl border border-border bg-surface">
          <div class="border-b border-border px-4 py-3">
            <h2 class="font-semibold text-foreground">Oferta del proveedor</h2>
          </div>

          {#if item.details.length === 0}
            <div class="p-6 text-center">
              <p class="font-medium text-foreground">Aún no hay respuesta registrada</p>
              <p class="mt-1 text-sm text-foreground-muted">
                Las líneas y precios aparecerán cuando se registre la oferta del proveedor.
              </p>
            </div>
          {:else}
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-border text-sm">
                <thead
                  class="bg-surface-muted text-left text-xs uppercase tracking-wide text-foreground-muted"
                >
                  <tr>
                    <th class="px-4 py-3 font-medium">Producto</th>
                    <th class="px-4 py-3 font-medium">Cantidad</th>
                    <th class="px-4 py-3 font-medium">Precio unit.</th>
                    <th class="px-4 py-3 font-medium">Impuesto</th>
                    <th class="px-4 py-3 font-medium">Total</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-border">
                  {#each item.details as detail (detail.id)}
                    <tr class="text-foreground">
                      <td class="px-4 py-3">
                        <span class="font-medium">Producto #{detail.product_id}</span>
                        <span class="block text-xs text-foreground-muted"
                          >Unidad #{detail.unit_id}</span
                        >
                      </td>
                      <td class="whitespace-nowrap px-4 py-3">{formatQuantity(detail.quantity)}</td>
                      <td class="whitespace-nowrap px-4 py-3">
                        {formatMoney(detail.unit_price, item.currency)}
                      </td>
                      <td class="whitespace-nowrap px-4 py-3">
                        {formatMoney(detail.tax_amount, item.currency)}
                      </td>
                      <td class="whitespace-nowrap px-4 py-3 font-medium">
                        {formatMoney(detail.total, item.currency)}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </article>

        {#if item.expenses.length > 0}
          <article class="rounded-xl border border-border bg-surface">
            <div class="border-b border-border px-4 py-3">
              <h2 class="font-semibold text-foreground">Gastos adicionales</h2>
            </div>
            <ul class="divide-y divide-border">
              {#each item.expenses as expense (expense.id)}
                <li class="flex items-start justify-between gap-4 px-4 py-3 text-sm">
                  <div>
                    <p class="font-medium text-foreground">
                      {expense.description ?? 'Gasto adicional'}
                    </p>
                    <p class="mt-1 text-xs text-foreground-muted">{expense.expense_type_id}</p>
                  </div>
                  <span class="whitespace-nowrap font-medium text-foreground">
                    {formatMoney(expense.amount, item.currency)}
                  </span>
                </li>
              {/each}
            </ul>
          </article>
        {/if}
      </div>

      <aside class="space-y-5">
        <article class="rounded-xl border border-border bg-surface p-4">
          <h2 class="font-semibold text-foreground">Totales</h2>
          <dl class="mt-4 space-y-3 text-sm">
            <div class="flex justify-between gap-4">
              <dt class="text-foreground-muted">Subtotal</dt>
              <dd class="font-medium text-foreground">
                {formatMoney(item.subtotal, item.currency)}
              </dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-foreground-muted">Descuento</dt>
              <dd class="font-medium text-foreground">
                {formatMoney(item.discount, item.currency)}
              </dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-foreground-muted">Impuestos</dt>
              <dd class="font-medium text-foreground">{formatMoney(item.tax, item.currency)}</dd>
            </div>
            <div class="flex justify-between gap-4 border-t border-border pt-3">
              <dt class="font-semibold text-foreground">Total</dt>
              <dd class="font-semibold text-foreground">
                {formatMoney(item.total, item.currency)}
              </dd>
            </div>
          </dl>
        </article>

        <article class="rounded-xl border border-border bg-surface p-4">
          <h2 class="font-semibold text-foreground">Condiciones</h2>
          <dl class="mt-4 space-y-3 text-sm">
            <div>
              <dt class="text-foreground-muted">Moneda</dt>
              <dd class="mt-1 font-medium text-foreground">{item.currency}</dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Términos de pago</dt>
              <dd class="mt-1 whitespace-pre-wrap text-foreground">{item.payment_terms ?? '—'}</dd>
            </div>
          </dl>
        </article>

        {#if item.notes}
          <article class="rounded-xl border border-border bg-surface p-4">
            <h2 class="font-semibold text-foreground">Notas</h2>
            <p class="mt-3 whitespace-pre-wrap text-sm text-foreground-muted">{item.notes}</p>
          </article>
        {/if}
      </aside>
    </div>
  {/if}
</section>
