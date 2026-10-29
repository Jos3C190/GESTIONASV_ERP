<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import type { TransferDemandRecord } from '$lib/features/inventory/transfer-documents';
  import { compareQuantities, formatQuantity, quantityFromScaled, scaledQuantity } from '$lib/features/inventory/transfer-operations';
  import type { TransferHandlingUnit } from '$lib/features/inventory/types';

  type CollectionState = 'loading' | 'loaded' | 'empty' | 'error';
  interface ProductRow {
    key: string;
    productId: number;
    productName: string;
    sku: string | null;
    unitLabel: string;
    units: TransferHandlingUnit[];
    demands: TransferDemandRecord[];
    availableQuantity: bigint;
  }

  interface Props {
    products: ProductRow[];
    stockState: CollectionState;
    demandState: CollectionState;
    supplyError: string | null;
    search: string;
    canMoveInventory: boolean;
    onSearch: (value: string) => void;
    onPrepareManual: (productKey: string) => void;
    onPrepareDemand: (productKey: string, demand: TransferDemandRecord) => void;
  }

  let {
    products,
    stockState,
    demandState,
    supplyError,
    search,
    canMoveInventory,
    onSearch,
    onPrepareManual,
    onPrepareDemand
  }: Props = $props();

  function formatDate(value: string | null): string {
    if (!value) return 'Fecha no indicada';
    const parsed = new Date(`${value.slice(0, 10)}T12:00:00Z`);
    if (Number.isNaN(parsed.getTime())) return 'Fecha no indicada';
    return new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium', timeZone: 'UTC' }).format(parsed);
  }

  function assignmentProgress(demand: TransferDemandRecord): number {
    const requested = scaledQuantity(demand.quantity_requested);
    const assigned = scaledQuantity(demand.quantity_assigned);
    if (requested == null || requested <= 0n || assigned == null) return 0;
    const bounded = assigned > requested ? requested : assigned;
    return Number((bounded * 10_000n) / requested) / 100;
  }

  function assignmentProgressText(demand: TransferDemandRecord): string {
    return `${assignmentProgress(demand).toLocaleString('es-SV', { maximumFractionDigits: 2 })}% asignado`;
  }
</script>

<section class="space-y-3" aria-labelledby="transfer-demand-heading">
  <div class="flex flex-wrap items-end justify-between gap-2">
    <div>
      <h3 id="transfer-demand-heading" class="font-semibold text-foreground">Existencias disponibles para despacho</h3>
      <p class="text-xs text-foreground-muted">Abre un producto para revisar solicitudes por sucursal.</p>
    </div>
    <span class="text-xs text-foreground-muted">Cantidades en unidad base</span>
  </div>

  <label class="block max-w-xl space-y-1 text-sm font-medium text-foreground">
    Buscar producto, SKU, sucursal o solicitud
    <input
      class="w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      type="search"
      value={search}
      oninput={(event) => onSearch(event.currentTarget.value)}
      placeholder="Ej. Café, PRD-CAF-011 o SCR-00016"
    />
  </label>

  {#if stockState === 'loading' || demandState === 'loading'}
    <div class="rounded-2xl border border-border bg-surface p-6 text-sm text-foreground-muted" role="status">
      Consultando inventario disponible y solicitudes…
    </div>
  {:else if stockState === 'error'}
    <div class="rounded-2xl border border-danger/30 bg-danger/10 p-5 text-sm text-danger" role="alert">
      El inventario no se pudo cargar; no se muestra como existencia cero. {supplyError}
    </div>
  {:else if products.length === 0}
    <div class="rounded-2xl border border-border border-dashed bg-surface p-8 text-center">
      <p class="font-medium text-foreground">{stockState === 'empty' && demandState === 'empty' ? 'No hay productos disponibles ni demanda para mostrar' : 'No hay productos que coincidan'}</p>
      <p class="mt-1 text-sm text-foreground-muted">Solo se muestran HUs disponibles para despacho y solicitudes consultables.</p>
    </div>
  {:else}
    <div class="space-y-3">
      {#each products as product (product.key)}
        <article class="overflow-hidden rounded-2xl border border-border bg-surface">
          <div class="flex flex-wrap items-start justify-between gap-4 p-4 sm:p-5">
            <div class="min-w-56 flex-1">
              <h4 class="font-semibold text-foreground">{product.productName}</h4>
              <p class="mt-1 font-mono text-xs text-foreground-muted">{product.sku ?? `Producto ${product.productId}`} · {product.unitLabel}</p>
              <p class="mt-2 text-sm text-foreground-muted">{product.units.length} unidad(es) logística(s) · {formatQuantity(quantityFromScaled(product.availableQuantity))} {product.unitLabel}</p>
            </div>
            <Button variant="secondary" size="sm" class="min-h-11" disabled={!canMoveInventory || product.units.length === 0} onclick={() => onPrepareManual(product.key)}>
              Envío manual
            </Button>
          </div>

          {#if product.demands.length > 0}
            <div class="hidden overflow-x-auto border-t border-border 2xl:block">
              <table class="min-w-[1040px] w-full text-left text-sm">
                <thead class="bg-surface-muted text-xs uppercase tracking-wide text-foreground-muted">
                  <tr>
                    <th scope="col" class="px-4 py-3">Sucursal / solicitud</th>
                    <th scope="col" class="px-4 py-3">Fecha requerida</th>
                    <th scope="col" class="px-4 py-3 text-right">Solicitado</th>
                    <th scope="col" class="px-4 py-3 text-right">Asignado</th>
                    <th scope="col" class="px-4 py-3 text-right">Despachado</th>
                    <th scope="col" class="px-4 py-3 text-right">En tránsito</th>
                    <th scope="col" class="px-4 py-3 text-right">Recibido</th>
                    <th scope="col" class="px-4 py-3 text-right">Pendiente de asignar</th>
                    <th scope="col" class="px-4 py-3"><span class="sr-only">Acción</span></th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-border">
                  {#each product.demands as demand (demand.purchase_request_detail_id)}
                    <tr>
                      <td class="px-4 py-3"><span class="font-medium text-foreground">{demand.branch_name}</span><span class="ml-2 font-mono text-xs text-primary">{demand.request_code}</span></td>
                      <td class="px-4 py-3 text-foreground-muted">{formatDate(demand.required_date)}</td>
                      <td class="px-4 py-3 text-right">{formatQuantity(demand.quantity_requested)} {product.unitLabel}</td>
                      <td class="px-4 py-3 text-right">{formatQuantity(demand.quantity_assigned)}</td>
                      <td class="px-4 py-3 text-right">{formatQuantity(demand.quantity_dispatched)}</td>
                      <td class="px-4 py-3 text-right">{formatQuantity(demand.quantity_in_transit)}</td>
                      <td class="px-4 py-3 text-right">{formatQuantity(demand.quantity_received)}</td>
                      <td class="px-4 py-3 text-right font-semibold text-primary">{formatQuantity(demand.quantity_pending)}</td>
                      <td class="px-4 py-3 text-right">
                        <Button size="sm" disabled={!canMoveInventory || compareQuantities(demand.quantity_pending, '0') <= 0 || product.units.length === 0 || demandState === 'error'} onclick={() => onPrepareDemand(product.key, demand)}>Preparar</Button>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
            <div class="divide-y divide-border border-t border-border 2xl:hidden">
              {#each product.demands as demand (demand.purchase_request_detail_id)}
                <article class="space-y-3 p-4">
                  <div class="flex items-start justify-between gap-3">
                    <div><p class="font-medium text-foreground">{demand.branch_name}</p><p class="font-mono text-xs text-primary">{demand.request_code}</p></div>
                    <span class="shrink-0 text-right text-xs text-foreground-muted">Requerida<br />{formatDate(demand.required_date)}</span>
                  </div>
                  <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                    <div class="col-span-2 rounded-xl border border-primary/15 bg-primary/5 p-3">
                      <div class="flex items-baseline justify-between gap-3">
                        <dt class="text-xs font-medium text-foreground-muted">Pendiente de asignar</dt>
                        <dd class="text-lg font-semibold text-primary">{formatQuantity(demand.quantity_pending)} {product.unitLabel}</dd>
                      </div>
                      <p class="mt-2 text-xs text-foreground-muted">Avance: {assignmentProgressText(demand)}</p>
                      <div
                        class="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-muted"
                        role="progressbar"
                        aria-label="Asignación de {demand.request_code} para {demand.branch_name}"
                        aria-valuetext={assignmentProgressText(demand)}
                        aria-valuemin="0"
                        aria-valuemax="100"
                        aria-valuenow={assignmentProgress(demand)}
                      >
                        <div class="h-full rounded-full bg-primary transition-[width] duration-300 motion-reduce:transition-none" style:width="{assignmentProgress(demand)}%"></div>
                      </div>
                    </div>
                    <div><dt class="text-xs text-foreground-muted">Solicitado</dt><dd>{formatQuantity(demand.quantity_requested)} {product.unitLabel}</dd></div>
                    <div><dt class="text-xs text-foreground-muted">Asignado</dt><dd>{formatQuantity(demand.quantity_assigned)}</dd></div>
                  </dl>
                  <details class="rounded-xl border border-border bg-surface-muted/40 px-3">
                    <summary class="min-h-11 cursor-pointer py-3 text-sm font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                      Ver despacho, tránsito y recepción
                    </summary>
                    <dl class="grid grid-cols-3 gap-2 border-t border-border py-3 text-sm">
                      <div><dt class="text-xs text-foreground-muted">Despachado</dt><dd>{formatQuantity(demand.quantity_dispatched)}</dd></div>
                      <div><dt class="text-xs text-foreground-muted">En tránsito</dt><dd>{formatQuantity(demand.quantity_in_transit)}</dd></div>
                      <div><dt class="text-xs text-foreground-muted">Recibido</dt><dd>{formatQuantity(demand.quantity_received)}</dd></div>
                    </dl>
                  </details>
                  <Button class="min-h-11 w-full" size="sm" disabled={!canMoveInventory || compareQuantities(demand.quantity_pending, '0') <= 0 || product.units.length === 0 || demandState === 'error'} onclick={() => onPrepareDemand(product.key, demand)}>Preparar traslado</Button>
                </article>
              {/each}
            </div>
          {:else}
            <p class="border-t border-border px-4 py-3 text-sm text-foreground-muted">No hay solicitudes asociadas. El envío manual requiere documentar el motivo del excedente.</p>
          {/if}
        </article>
      {/each}
    </div>
  {/if}
</section>

