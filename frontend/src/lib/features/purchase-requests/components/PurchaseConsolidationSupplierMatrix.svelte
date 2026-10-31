<script lang="ts">
  import type { PurchaseConsolidationAwardBoard } from '$lib/types/purchase-consolidation';
  import { formatQuantity } from '../adjudication-formatters';
  import PurchaseConsolidationMatrixOffer from './PurchaseConsolidationMatrixOffer.svelte';

  let {
    board,
    supplierNames,
    onInspect,
    onRefresh,
    query = $bindable(''),
    requestedSupplier = $bindable<number | null>(null)
  }: {
    board: PurchaseConsolidationAwardBoard;
    supplierNames: Record<number, string>;
    onInspect: (lineId: string, offerId: string) => void;
    onRefresh: () => void;
    query?: string;
    requestedSupplier?: number | null;
  } = $props();

  const normalize = (value: string) =>
    value
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLocaleLowerCase('es-SV');
  const supplierIds = $derived([
    ...new Set(board.lines.flatMap((line) => line.offers.map((offer) => offer.supplier_id)))
  ]);
  const selectedSupplier = $derived(
    requestedSupplier !== null && supplierIds.includes(requestedSupplier)
      ? requestedSupplier
      : supplierIds[0]
  );
  const rows = $derived(
    board.lines
      .filter((line) =>
        normalize(`${line.product_name} ${line.product_sku}`).includes(normalize(query.trim()))
      )
      .map((line) => ({
        line,
        cells: supplierIds.map((id) => ({
          supplierId: id,
          offers: line.offers.filter((offer) => offer.supplier_id === id)
        }))
      }))
  );
</script>

<section aria-labelledby="supplier-matrix-title">
  <div class="flex flex-wrap items-end justify-between gap-4 px-4 py-5 sm:px-5">
    <div class="max-w-xl">
      <h3 id="supplier-matrix-title" class="font-semibold text-foreground">
        Matriz de proveedores
      </h3>
      <p class="mt-1 hidden text-sm leading-6 text-foreground-muted sm:block">
        Respuestas recibidas para {board.consolidation_code}. Compara cada producto y abre una
        oferta para revisar sus condiciones y adjudicar manualmente.
      </p>
    </div>
    <label class="w-full text-sm font-medium text-foreground sm:w-72">
      Buscar producto o código
      <input
        type="search"
        bind:value={query}
        placeholder="Ej. Azúcar o PRD-AZU-004"
        class="mt-1.5 min-h-11 w-full rounded-lg border border-[rgb(var(--control-border))] bg-surface px-3 py-2 font-normal text-foreground placeholder:text-foreground-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      />
    </label>
  </div>

  {#if supplierIds.length === 0}
    <div
      class="mx-4 mb-5 flex gap-3 rounded-lg border border-border bg-surface-muted p-5 sm:mx-5"
      role="status"
    >
      <span
        class="flex size-10 shrink-0 items-center justify-center rounded-full border border-border text-foreground-muted"
        aria-hidden="true">≡</span
      >
      <div>
        <p class="font-medium text-foreground">Todavía no hay ofertas para comparar</p>
        <p class="mt-1 text-sm leading-6 text-foreground-muted">
          Registra las respuestas de los proveedores de este consolidado y actualiza la comparación.
        </p>
        <button
          type="button"
          onclick={onRefresh}
          class="mt-3 min-h-11 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >Actualizar ofertas</button
        >
      </div>
    </div>
  {:else}
    <label class="mx-4 mb-4 block text-sm font-medium text-foreground sm:hidden">
      Proveedor a comparar
      <select
        value={selectedSupplier}
        onchange={(event) => (requestedSupplier = Number(event.currentTarget.value))}
        class="mt-1.5 min-h-11 w-full rounded-lg border border-[rgb(var(--control-border))] bg-surface px-3 py-2 text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        {#each supplierIds as supplierId (supplierId)}<option value={supplierId}
            >{supplierNames[supplierId] ?? `Proveedor #${supplierId}`}</option
          >{/each}
      </select>
    </label>
    <div
      class="flex flex-wrap items-center justify-between gap-2 border-y border-border bg-surface-muted/40 px-4 py-2.5 text-xs text-foreground-muted sm:px-5"
    >
      <p aria-live="polite">
        {rows.length} de {board.lines.length} productos · {supplierIds.length} proveedores
      </p>
      <p id="matrix-scroll-hint">
        <span class="sm:hidden">Elige un proveedor para consultar su columna.</span><span
          class="hidden sm:inline">Desplaza la tabla para consultar todos los proveedores.</span
        >
      </p>
    </div>
    {#if rows.length === 0}
      <div class="flex flex-wrap items-center justify-between gap-3 p-5" role="status">
        <p class="text-sm text-foreground">No hay productos que coincidan con «{query}».</p>
        <button
          type="button"
          onclick={() => (query = '')}
          class="min-h-11 rounded-lg border border-border px-3 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >Limpiar búsqueda</button
        >
      </div>
    {:else}
      <!-- Keyboard focus lets users scroll the overflowing table without a pointer. -->
      <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
      <div
        class="matrix-scroll max-h-[65vh] overflow-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-primary"
        role="region"
        aria-label="Tabla comparativa de proveedores"
        aria-describedby="matrix-scroll-hint"
        tabindex="0"
      >
        <table
          class="w-full table-fixed border-separate border-spacing-0 text-left text-sm sm:table-auto"
        >
          <caption class="sr-only"
            >Productos y ofertas por proveedor de {board.consolidation_code}. Cada importe conserva
            su moneda y la cantidad cotizada.</caption
          >
          <thead>
            <tr>
              <th
                scope="col"
                class="sticky left-0 top-0 z-30 w-28 min-w-28 max-w-28 border-b border-r border-border bg-surface-muted px-3 py-4 font-semibold text-foreground sm:w-60 sm:min-w-60 sm:max-w-60 sm:px-4"
              >
                Producto y demanda
              </th>
              {#each supplierIds as supplierId (supplierId)}
                <th
                  scope="col"
                  class={`sticky top-0 z-20 min-w-0 break-words border-b border-r border-border bg-surface-muted px-3 py-4 font-semibold text-foreground sm:min-w-64 sm:max-w-72 sm:px-4 ${supplierId === selectedSupplier ? '' : 'hidden sm:table-cell'}`}
                >
                  {supplierNames[supplierId] ?? `Proveedor #${supplierId}`}
                </th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each rows as { line, cells } (line.id)}
              <tr>
                <th
                  scope="row"
                  class="sticky left-0 z-10 w-28 min-w-28 max-w-28 border-b border-r border-border bg-surface px-3 py-5 align-top font-normal sm:w-60 sm:min-w-60 sm:max-w-60 sm:px-4"
                >
                  <p class="break-words font-semibold leading-6 text-foreground">
                    {line.product_name}
                  </p>
                  <p class="mt-1 break-all font-mono text-xs text-foreground-muted">
                    {line.product_sku}
                  </p>
                  <dl class="mt-4 space-y-2 text-xs">
                    <div>
                      <dt class="text-foreground-muted">Solicitado</dt>
                      <dd class="mt-0.5 font-medium tabular-nums text-foreground">
                        {formatQuantity(line.demand_quantity)}
                        {line.unit_name}
                      </dd>
                    </div>
                    <div>
                      <dt class="text-foreground-muted">Pendiente de adjudicar</dt>
                      <dd class="mt-0.5 font-medium tabular-nums text-foreground">
                        {formatQuantity(line.remaining_quantity)}
                        {line.unit_name}
                      </dd>
                    </div>
                  </dl>
                </th>
                {#each cells as cell (cell.supplierId)}
                  <td
                    class={`min-w-0 break-words border-b border-r border-border bg-surface px-3 py-5 align-top sm:min-w-64 sm:max-w-72 sm:px-4 ${cell.supplierId === selectedSupplier ? '' : 'hidden sm:table-cell'}`}
                  >
                    {#if cell.offers.length === 0}
                      <p class="text-sm font-medium text-foreground-muted">Sin oferta recibida</p>
                      <p class="mt-1 text-xs leading-5 text-foreground-muted">
                        Este proveedor no tiene una respuesta para este producto.
                      </p>
                    {:else}
                      <div class="space-y-5 divide-y divide-border">
                        {#each cell.offers as offer (offer.quotation_detail_id)}
                          <div class="pt-5 first:pt-0">
                            <PurchaseConsolidationMatrixOffer
                              {line}
                              {offer}
                              supplierName={supplierNames[cell.supplierId] ??
                                `Proveedor #${cell.supplierId}`}
                              onInspect={() => onInspect(line.id, offer.quotation_detail_id)}
                            />
                          </div>
                        {/each}
                      </div>
                    {/if}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <p class="px-4 py-4 text-xs leading-5 text-foreground-muted sm:px-5">
        El total cotizado corresponde a la cantidad ofrecida de cada línea e incluye sus descuentos
        e impuestos. Los cargos compartidos de la cotización se consultan por separado en cada
        oferta.
      </p>
    {/if}
  {/if}
</section>
