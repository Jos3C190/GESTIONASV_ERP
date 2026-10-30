<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { suppliersApi } from '$lib/api/suppliers';
  import { branch } from '$lib/stores/branch.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { PurchaseQuotation } from '$lib/types/purchase-quotation';
  import type { Supplier } from '$lib/types/supplier';

  let {
    id,
    consolidationId = null
  }: {
    id: string;
    consolidationId?: string | null;
  } = $props();

  let quotation = $state<PurchaseQuotation | null>(null);
  let supplier = $state<Supplier | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let generation = 0;
  let canRead = $derived(permissions.hasPermission('purchase_quotations:read'));

  function message(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return 'No se pudo cargar el documento de solicitud.';
  }

  function formatDate(value: string | null): string {
    if (!value) return '—';
    return new Intl.DateTimeFormat('es-SV', {
      day: '2-digit', month: 'long', year: 'numeric',
      timeZone: 'America/El_Salvador'
    }).format(new Date(value));
  }

  function formatQuantity(value: string): string {
    return new Intl.NumberFormat('es-SV', { maximumFractionDigits: 6 }).format(Number(value));
  }

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try {
      const item = await purchaseQuotationsApi.get(id, branch.id, consolidationId);
      if (current !== generation) return;
      quotation = item;
      supplier = await suppliersApi.getSupplier(item.supplier_id).catch(() => null);
      if (current !== generation) return;
      if (!item.consolidation_id || item.snapshots.length === 0) {
        error = 'Este documento solo está disponible para RFQ creadas desde un consolidado.';
      }
    } catch (cause: unknown) {
      if (current !== generation) return;
      quotation = null;
      supplier = null;
      error = message(cause);
    } finally {
      if (current === generation) loading = false;
    }
  }

  function print() {
    window.print();
  }

  $effect(() => {
    if (id && canRead) void load();
    else loading = false;
  });
</script>

<div class="rfq-page min-h-full bg-background px-4 pb-8 pt-4 sm:px-6 sm:pt-6 md:px-8 md:pt-8">
  <div class="print-controls mb-5 flex flex-wrap items-center justify-between gap-3">
    <a
      href={`/purchase-quotations/${id}${consolidationId ? `?consolidation_id=${consolidationId}` : ''}`}
      class="text-sm font-medium text-primary hover:underline"
    >
      ← Volver a la RFQ
    </a>
    <Button disabled={!quotation || !quotation.consolidation_id || loading} onclick={print}>
      Imprimir o guardar como PDF
    </Button>
  </div>

  {#if !canRead}
    <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
      No tienes permiso para consultar cotizaciones de compra.
    </div>
  {:else if loading}
    <div class="space-y-4" role="status" aria-label="Cargando documento de solicitud">
      <div class="skeleton h-36 rounded-xl"></div>
      <div class="skeleton h-72 rounded-xl"></div>
    </div>
  {:else if error || !quotation}
    <div class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
      <span>{error ?? 'No se encontró la solicitud.'}</span>
      <Button size="sm" variant="secondary" onclick={() => void load()}>Reintentar</Button>
    </div>
  {:else}
    <main class="rfq-document mx-auto max-w-5xl space-y-6 rounded-xl border border-border bg-surface p-5 text-foreground shadow-soft sm:p-8">
      <header class="border-b-2 border-primary pb-5">
        <div class="flex flex-wrap items-start justify-between gap-5">
          <div>
            <p class="rfq-company-name text-sm font-semibold text-primary">{company.active?.name ?? 'GestionaSV'}</p>
            <h1 class="rfq-title mt-2 text-2xl font-bold tracking-tight sm:text-3xl">Solicitud de cotización</h1>
            <p class="mt-1 text-sm text-foreground-muted">Documento para solicitar precios y condiciones al proveedor.</p>
          </div>
          <div class="text-left sm:text-right">
            <p class="rfq-code font-mono text-xl font-bold">{quotation.code}</p>
            <p class="mt-1 text-sm text-foreground-muted">Versión {quotation.version_number}</p>
            <p class="mt-1 text-sm text-foreground-muted">Fecha: {formatDate(quotation.created_at ?? quotation.quotation_date)}</p>
          </div>
        </div>
      </header>

      <section class="rfq-parties grid gap-5 sm:grid-cols-2">
        <div class="rfq-party-card rounded-lg border border-border p-4">
          <h2 class="text-xs font-semibold uppercase tracking-wide text-foreground-muted">Solicitar a</h2>
          <p class="mt-2 text-lg font-semibold">{supplier?.name ?? `Proveedor #${quotation.supplier_id}`}</p>
          {#if supplier?.code}<p class="mt-1 text-sm text-foreground-muted">Código: {supplier.code}</p>{/if}
          {#if supplier?.legal_name}<p class="mt-1 text-sm text-foreground-muted">{supplier.legal_name}</p>{/if}
          {#if supplier?.email}<p class="mt-2 text-sm">{supplier.email}</p>{/if}
          {#if supplier?.address}<p class="mt-1 text-sm text-foreground-muted">{supplier.address}</p>{/if}
        </div>
        <div class="rfq-party-card rounded-lg border border-border p-4">
          <h2 class="text-xs font-semibold uppercase tracking-wide text-foreground-muted">Referencia de compra</h2>
          <p class="mt-2 text-lg font-semibold">{quotation.consolidation_code}</p>
          <p class="mt-1 text-sm text-foreground-muted">Demanda consolidada · moneda solicitada: {quotation.currency}</p>
          <p class="mt-1 text-sm text-foreground-muted">Responde indicando precio, cantidad ofrecida, plazo y condiciones.</p>
        </div>
      </section>

      <section>
        <h2 class="rfq-section-title mb-3 text-lg font-semibold">Productos solicitados</h2>
        <div class="rfq-table-wrap overflow-x-auto rounded-lg border border-border">
          <table class="rfq-products-table w-full min-w-[640px] text-sm">
            <thead class="bg-surface-muted text-left text-xs uppercase tracking-wide text-foreground-muted">
              <tr>
                <th class="px-3 py-3">SKU</th>
                <th class="px-3 py-3">Producto</th>
                <th class="px-3 py-3">Unidad</th>
                <th class="px-3 py-3 text-right">Cantidad solicitada</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              {#each quotation.snapshots as snapshot (snapshot.purchase_quotation_detail_id)}
                {@const detail = quotation.details.find((line) => line.id === snapshot.purchase_quotation_detail_id)}
                <tr>
                  <td class="whitespace-nowrap px-3 py-3 font-mono">{snapshot.product_sku}</td>
                  <td class="px-3 py-3 font-medium">{snapshot.product_name}</td>
                  <td class="px-3 py-3">{snapshot.unit_name}</td>
                  <td class="whitespace-nowrap px-3 py-3 text-right font-mono font-semibold">
                    {formatQuantity(detail?.quantity ?? '0')}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>

      {#if quotation.notes}
        <section class="rfq-notes rounded-lg border border-border p-4">
          <h2 class="font-semibold">Indicaciones</h2>
          <p class="mt-2 whitespace-pre-wrap text-sm">{quotation.notes}</p>
        </section>
      {/if}

      <footer class="rfq-document-footer border-t border-border pt-4 text-xs text-foreground-muted">
        Indica en tu respuesta las cantidades que puedes suministrar. Si no puedes cotizar una línea, señálala como no disponible.
      </footer>
    </main>
  {/if}
</div>

<style>
  @media print {
    @page { size: A4 portrait; margin: 12mm 14mm; }

    :global(html), :global(body) {
      width: 100% !important;
      min-height: 0 !important;
      height: auto !important;
      overflow: visible !important;
      background: #fff !important;
      color: #17212b !important;
    }
    :global(body > #svelte), :global(body > #svelte > div) {
      width: 100% !important;
      min-height: 0 !important;
      height: auto !important;
      overflow: visible !important;
      background: #fff !important;
    }
    :global([data-app-global-chrome]) { display: none !important; }
    :global([data-app-scroll-container]) {
      display: block !important;
      min-height: 0 !important;
      height: auto !important;
      overflow: visible !important;
      background: #fff !important;
    }
    :global(.fixed.inset-0.flex.overflow-hidden.bg-surface) {
      position: static !important;
      display: block !important;
      width: 100% !important;
      min-height: 0 !important;
      height: auto !important;
      overflow: visible !important;
      background: #fff !important;
    }
    :global(.fixed.inset-0.flex.overflow-hidden.bg-surface > .flex.flex-1.flex-col.overflow-hidden) {
      display: block !important;
      min-height: 0 !important;
      height: auto !important;
      overflow: visible !important;
      background: #fff !important;
    }
    .print-controls { display: none !important; }
    .rfq-page {
      width: 100% !important;
      min-height: 0 !important;
      height: auto !important;
      margin: 0 !important;
      padding: 0 !important;
      overflow: visible !important;
      background: #fff !important;
      color: #17212b !important;
    }
    .rfq-document {
      width: 100% !important;
      max-width: none !important;
      margin: 0 !important;
      padding: 0 !important;
      border: 0 !important;
      border-radius: 0 !important;
      background: #fff !important;
      box-shadow: none !important;
      color: #17212b !important;
      font-size: 10pt !important;
      line-height: 1.45 !important;
    }
    .rfq-document * {
      box-sizing: border-box !important;
      color: #17212b !important;
      box-shadow: none !important;
      text-shadow: none !important;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .rfq-document header {
      border-color: #0891b2 !important;
      padding-bottom: 5mm !important;
    }
    .rfq-company-name {
      color: #087e9d !important;
      font-size: 10pt !important;
      letter-spacing: 0.02em !important;
    }
    .rfq-title {
      margin-top: 2mm !important;
      font-size: 22pt !important;
      line-height: 1.15 !important;
    }
    .rfq-code { font-size: 15pt !important; }
    .rfq-parties {
      grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
      gap: 5mm !important;
      break-inside: avoid-page;
    }
    .rfq-party-card,
    .rfq-notes {
      border-color: #d6e0e7 !important;
      border-radius: 2mm !important;
      background: #f7fafc !important;
      padding: 4mm !important;
      break-inside: avoid-page;
    }
    .rfq-party-card h2 {
      color: #526575 !important;
      font-size: 8pt !important;
      letter-spacing: 0.06em !important;
    }
    .rfq-section-title {
      margin-bottom: 2mm !important;
      font-size: 13pt !important;
      break-after: avoid-page;
    }
    .rfq-table-wrap {
      width: 100% !important;
      overflow: visible !important;
      border-color: #cbd5df !important;
      border-radius: 2mm !important;
      break-inside: auto;
    }
    .rfq-products-table {
      width: 100% !important;
      min-width: 0 !important;
      table-layout: fixed !important;
      border-collapse: collapse !important;
      font-size: 9pt !important;
    }
    .rfq-products-table th,
    .rfq-products-table td {
      padding: 2.5mm 2.2mm !important;
      border-color: #dbe3e9 !important;
      vertical-align: top !important;
      overflow-wrap: anywhere !important;
    }
    .rfq-products-table th {
      background: #e8f4f8 !important;
      color: #173b4c !important;
      font-size: 7.5pt !important;
      letter-spacing: 0.04em !important;
    }
    .rfq-products-table th:nth-child(1) { width: 19% !important; }
    .rfq-products-table th:nth-child(2) { width: 39% !important; }
    .rfq-products-table th:nth-child(3) { width: 18% !important; }
    .rfq-products-table th:nth-child(4) { width: 24% !important; }
    .rfq-products-table tbody tr:nth-child(even) td { background: #f8fafc !important; }
    .rfq-products-table thead { display: table-header-group; }
    .rfq-products-table tr { break-inside: avoid-page; page-break-inside: avoid; }
    .rfq-document-footer {
      margin-top: 5mm !important;
      padding-top: 3mm !important;
      border-color: #cbd5df !important;
      color: #526575 !important;
      font-size: 8.5pt !important;
      break-inside: avoid-page;
    }
  }
</style>
