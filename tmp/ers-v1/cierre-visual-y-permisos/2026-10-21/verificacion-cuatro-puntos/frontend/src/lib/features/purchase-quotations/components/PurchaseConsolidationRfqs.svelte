<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { suppliersApi } from '$lib/api/suppliers';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { PurchaseConsolidationStatus } from '$lib/types/purchase-consolidation';
  import type { PurchaseQuotation, PurchaseQuotationStatus } from '$lib/types/purchase-quotation';

  let {
    consolidationId,
    status
  }: {
    consolidationId: string;
    status: PurchaseConsolidationStatus;
  } = $props();

  const STATUS_LABELS: Record<PurchaseQuotationStatus, string> = {
    draft: 'Borrador',
    requested: 'Enviada al proveedor',
    received: 'Respuesta recibida',
    under_evaluation: 'En evaluación',
    selected: 'Oferta seleccionada',
    not_selected: 'No seleccionada',
    rejected: 'Oferta rechazada',
    expired: 'Vencida',
    cancelled: 'Cancelada'
  };

  let quotations = $state<PurchaseQuotation[]>([]);
  let supplierNames = $state<Record<number, string>>({});
  let loading = $state(true);
  let error = $state<string | null>(null);
  let generation = 0;

  let canRead = $derived(permissions.hasPermission('purchase_quotations:read'));
  let canCreate = $derived(
    status !== 'cancelled' && status !== 'closed' &&
      permissions.hasPermission('purchase_requests:read') &&
      permissions.hasPermission('purchase_quotations:manage')
  );

  function message(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return 'No se pudieron cargar las solicitudes a proveedores.';
  }

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try {
      const result = await purchaseQuotationsApi.listForConsolidation(consolidationId);
      if (current !== generation) return;
      quotations = result;
      const ids = [...new Set(result.map((item) => item.supplier_id))];
      const entries = await Promise.all(
        ids.map(async (id) => {
          const supplier = await suppliersApi.getSupplier(id).catch(() => null);
          return [id, supplier?.name ?? `Proveedor #${id}`] as const;
        })
      );
      if (current === generation) supplierNames = Object.fromEntries(entries);
    } catch (cause: unknown) {
      if (current !== generation) return;
      quotations = [];
      error = message(cause);
    } finally {
      if (current === generation) loading = false;
    }
  }

  $effect(() => {
    const id = consolidationId;
    if (id && canRead) void load();
    else loading = false;
  });
</script>

{#if canRead}
  <Card class="mb-4 overflow-hidden p-0">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
      <div>
        <h2 class="font-semibold text-foreground">Solicitudes a proveedores</h2>
        <p class="mt-1 text-sm text-foreground-muted">
          Cada proveedor recibe una RFQ versionada con una copia fija de las cantidades.
        </p>
      </div>
      {#if canCreate}
        <a
          href={`/purchase-quotations/from-consolidation/${consolidationId}`}
          class="inline-flex min-h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          Preparar RFQ
        </a>
      {/if}
    </div>

    {#if error}
      <div class="flex flex-wrap items-center justify-between gap-3 p-4" role="alert">
        <p class="text-sm text-danger">{error}</p>
        <Button size="sm" variant="secondary" onclick={() => void load()}>Reintentar</Button>
      </div>
    {:else if loading}
      <div class="space-y-3 p-4" role="status" aria-label="Cargando solicitudes a proveedores">
        <div class="skeleton h-12 rounded-lg"></div>
        <div class="skeleton h-12 rounded-lg"></div>
      </div>
    {:else if quotations.length === 0}
      <div class="flex flex-col items-start gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          {#if status === 'closed'}
            <p class="font-medium text-foreground">El consolidado está cerrado</p>
            <p class="mt-1 text-sm text-foreground-muted">La gestión de la demanda finalizó; no se pueden preparar nuevas RFQ.</p>
          {:else}
            <p class="font-medium text-foreground">Todavía no hay RFQ para este consolidado</p>
            <p class="mt-1 text-sm text-foreground-muted">
              Prepara una copia por proveedor y luego descarga el documento para enviarlo.
            </p>
          {/if}
        </div>
        {#if !canCreate && status !== 'closed'}
          <p class="text-xs text-foreground-muted">Se requieren permisos para consultar compras y gestionar cotizaciones.</p>
        {/if}
      </div>
    {:else}
      <ul class="divide-y divide-border">
        {#each quotations as quotation (quotation.id)}
          <li class="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span class="font-mono text-sm font-semibold text-primary">{quotation.code}</span>
                <span class="rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs text-foreground-muted">
                  Versión {quotation.version_number}
                </span>
                <span class="text-xs text-foreground-muted">{STATUS_LABELS[quotation.status]}</span>
              </div>
              <p class="mt-1 truncate text-sm font-medium text-foreground">
                {supplierNames[quotation.supplier_id] ?? `Proveedor #${quotation.supplier_id}`}
              </p>
              <p class="mt-1 text-xs text-foreground-muted">
                {quotation.details.length} {quotation.details.length === 1 ? 'producto' : 'productos'}
                {#if quotation.sent_at} · Enviada {new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium', timeZone: 'America/El_Salvador' }).format(new Date(quotation.sent_at))}{/if}
              </p>
            </div>
            <a
              href={`/purchase-quotations/${quotation.id}?consolidation_id=${consolidationId}`}
              class="inline-flex min-h-10 shrink-0 items-center justify-center rounded-lg border border-border px-3 text-sm font-medium text-foreground hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Abrir RFQ
            </a>
          </li>
        {/each}
      </ul>
    {/if}
  </Card>
{/if}
