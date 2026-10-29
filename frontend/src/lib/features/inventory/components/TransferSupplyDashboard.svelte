<script lang="ts">
  import type {
    TransferReceiptSummary,
    TransferSupplyProduct
  } from '$lib/features/inventory/transfer-supply';

  interface Props {
    warehouseName: string;
    products: TransferSupplyProduct[];
    receipts: TransferReceiptSummary[];
    requestError: string | null;
    handlingUnitCount: number;
    receiptLoading: boolean;
    receiptError: string | null;
    onPrepareRequest: (requestId: string, productId: number, unitId: number) => void;
    onPrepareManualDispatch: () => void;
  }

  let {
    warehouseName,
    products,
    receipts,
    requestError,
    handlingUnitCount,
    receiptLoading,
    receiptError,
    onPrepareRequest,
    onPrepareManualDispatch
  }: Props = $props();

  let productSearch = $state('');
  let showAllProducts = $state(false);
  let productsWithStock = $derived(
    new Set(
      products
        .filter((product) => product.availableQuantity > 0)
        .map((product) => (product.productId == null ? product.key : String(product.productId)))
    ).size
  );
  let stockedProducts = $derived(products.filter((product) => product.availableQuantity > 0));
  let branchesWithPendingDemand = $derived(
    new Set(
      stockedProducts.flatMap((product) =>
        product.demands
          .filter((demand) => demand.remainingQuantity > 0)
          .map((demand) => demand.warehouseId)
      )
    ).size
  );
  let latestReceipt = $derived(receipts[0] ?? null);
  let filteredProducts = $derived.by(() => {
    const query = productSearch.trim().toLocaleLowerCase('es-SV');
    if (!query) return stockedProducts;
    return stockedProducts.filter((product) =>
      [
        product.productName,
        product.sku,
        ...product.demands.flatMap((demand) => [demand.branchName, demand.requestCode])
      ]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLocaleLowerCase('es-SV').includes(query))
    );
  });
  let visibleProducts = $derived(
    productSearch.trim() || showAllProducts ? filteredProducts : filteredProducts.slice(0, 12)
  );

  function formatQuantity(value: number): string {
    return value.toLocaleString('es-SV', { maximumFractionDigits: 3 });
  }

  function formatDate(value: string | null): string {
    if (!value) return 'Fecha no indicada';
    const parsed = new Date(`${value.slice(0, 10)}T12:00:00Z`);
    if (Number.isNaN(parsed.getTime())) return 'Fecha no indicada';
    return new Intl.DateTimeFormat('es-SV', {
      dateStyle: 'medium',
      timeZone: 'UTC'
    }).format(parsed);
  }

  function formatDateTime(value: string): string {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return 'Fecha no disponible';
    return new Intl.DateTimeFormat('es-SV', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'America/El_Salvador'
    }).format(parsed);
  }

  function demandsByBranch(demands: TransferSupplyProduct['demands']) {
    const grouped = new Map<string, TransferSupplyProduct['demands']>();
    for (const demand of demands) {
      grouped.set(demand.warehouseId, [...(grouped.get(demand.warehouseId) ?? []), demand]);
    }
    return [...grouped.entries()]
      .map(([warehouseId, branchDemands]) => {
        const ordered = [...branchDemands].sort(
          (left, right) =>
            (left.requiredDate?.slice(0, 10) ?? '9999-12-31').localeCompare(
              right.requiredDate?.slice(0, 10) ?? '9999-12-31'
            ) || left.requestDate.localeCompare(right.requestDate)
        );
        return {
          warehouseId,
          branchName: ordered[0]?.branchName ?? 'Sucursal',
          requestedQuantity: ordered.reduce((total, demand) => total + demand.quantity, 0),
          dispatchedQuantity: ordered.reduce(
            (total, demand) => total + demand.dispatchedQuantity,
            0
          ),
          remainingQuantity: ordered.reduce((total, demand) => total + demand.remainingQuantity, 0),
          requests: ordered,
          nextRequest: ordered.find((demand) => demand.remainingQuantity > 0) ?? null
        };
      })
      .sort((left, right) => left.branchName.localeCompare(right.branchName, 'es-SV'));
  }
</script>

<section
  class="space-y-5 rounded-2xl border border-border bg-surface p-5 sm:p-6"
  aria-labelledby="transfer-supply-heading"
>
  <header class="flex flex-wrap items-start justify-between gap-3">
    <div class="space-y-1">
      <h2 id="transfer-supply-heading" class="text-lg font-semibold text-foreground">
        Panorama de abastecimiento
      </h2>
      <p class="max-w-3xl text-sm text-foreground-muted">
        Empieza por el producto disponible en la matriz. Desde cada producto puedes revisar el
        pendiente por sucursal y preparar el despacho.
      </p>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <span
        class="inline-block max-w-full truncate rounded-full border border-border-subtle bg-surface-subtle px-3 py-1 text-xs font-medium text-foreground-muted"
        title={warehouseName}
      >
        {warehouseName}
      </span>
      <button
        type="button"
        class="rounded-xl border border-border bg-surface-subtle px-3 py-2 text-sm font-medium text-foreground-muted hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        disabled={handlingUnitCount === 0}
        onclick={onPrepareManualDispatch}
      >
        Envío sin solicitud
      </button>
    </div>
  </header>

  <section class="space-y-3" aria-labelledby="transfer-demand-heading">
    <div class="flex flex-wrap items-end justify-between gap-2">
      <div>
        <h3 id="transfer-demand-heading" class="font-semibold text-foreground">
          Existencias disponibles para despacho
        </h3>
        <p class="text-xs text-foreground-muted">
          Abre un producto para ver el reparto sugerido por sucursal.
        </p>
      </div>
      <span class="text-xs text-foreground-muted">Cantidades en la unidad mostrada</span>
    </div>

    {#if stockedProducts.length > 0}
      <label class="block">
        <span class="sr-only">Buscar producto, SKU o sucursal</span>
        <input
          class="w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          type="search"
          bind:value={productSearch}
          placeholder="Buscar producto, SKU o sucursal"
        />
      </label>
    {/if}

    {#if requestError && stockedProducts.length === 0}
      <div
        class="rounded-xl border border-border border-dashed px-4 py-6 text-sm text-foreground-muted"
      >
        No hay existencias liberadas en la matriz y no se pudo cargar el detalle de solicitudes.
      </div>
    {:else if stockedProducts.length === 0}
      <div
        class="rounded-xl border border-border border-dashed px-4 py-6 text-sm text-foreground-muted"
      >
        No hay existencias liberadas para trasladar. Cuando una recepción sea revisada y liberada,
        el producto aparecerá aquí.
      </div>
    {:else if visibleProducts.length === 0}
      <div
        class="rounded-xl border border-border border-dashed px-4 py-6 text-sm text-foreground-muted"
      >
        No hay productos o sucursales que coincidan con “{productSearch}”.
      </div>
    {:else}
      <p class="text-xs text-foreground-muted">
        {#if productSearch.trim() || showAllProducts}
          {filteredProducts.length.toLocaleString('es-SV')} producto(s) con existencia
        {:else}
          Mostrando {visibleProducts.length.toLocaleString('es-SV')} de {stockedProducts.length.toLocaleString(
            'es-SV'
          )} producto(s) con existencia
        {/if}
      </p>
      <div class="space-y-2">
        {#each visibleProducts as product (product.key)}
          {@const branchDemands = demandsByBranch(product.demands)}
          <details class="group rounded-xl border border-border bg-surface-subtle">
            <summary
              class="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <div class="min-w-48 flex-1">
                <p class="font-medium text-foreground">{product.productName}</p>
                <p class="font-mono text-xs text-foreground-muted">
                  {product.sku ?? `Producto ${product.productId ?? 'sin SKU'}`}
                </p>
                {#if branchDemands.length}
                  <p class="mt-1 text-xs text-foreground-muted">
                    Pendiente en {branchDemands.filter((item) => item.remainingQuantity > 0).length} sucursal(es)
                  </p>
                {/if}
              </div>
              <div class="grid w-full gap-2 text-xs sm:w-auto sm:grid-cols-3 sm:text-right">
                <p>
                  <span class="text-foreground-muted">Disponible en matriz </span><strong
                    class="text-foreground"
                    >{formatQuantity(product.availableQuantity)} {product.unitLabel}</strong
                  >
                </p>
                <p>
                  <span class="text-foreground-muted">Solicitado pendiente </span><strong
                    class="text-foreground"
                    >{formatQuantity(product.pendingQuantity)} {product.unitLabel}</strong
                  >
                </p>
                <p>
                  <span class="text-foreground-muted">Reserva estimada </span>
                  {#if product.canEstimateReserve && product.reserveQuantity !== null}
                    <strong class="text-primary"
                      >{formatQuantity(product.reserveQuantity)} {product.unitLabel}</strong
                    >
                  {:else}
                    <strong class="text-warning">Revisar unidad</strong>
                  {/if}
                </p>
              </div>
              <span
                class="inline-flex items-center gap-1 text-xs font-medium text-primary"
                aria-hidden="true"
              >
                Ver reparto por sucursal <span class="transition-transform group-open:rotate-180"
                  >⌄</span
                >
              </span>
              <span class="sr-only">Ver reparto por sucursal de {product.productName}</span>
            </summary>

            <div class="space-y-3 border-t border-border px-4 py-4">
              {#if product.shortageQuantity !== null && product.shortageQuantity > 0}
                <p
                  class="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning"
                >
                  Faltan {formatQuantity(product.shortageQuantity)}
                  {product.unitLabel} para cubrir las solicitudes mostradas.
                </p>
              {/if}
              {#if !product.canEstimateReserve}
                <p
                  class="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning"
                >
                  La existencia y la solicitud están en unidades distintas; no se calcula una
                  reserva hasta conocer su equivalencia.
                </p>
              {/if}

              {#if branchDemands.length === 0}
                <p class="text-sm text-foreground-muted">
                  No hay solicitudes de sucursal para este producto. La existencia queda como
                  reserva de la matriz.
                </p>
              {:else}
                <ul class="divide-y divide-border">
                  {#each branchDemands as branchDemand (branchDemand.warehouseId)}
                    {@const nextRequest = branchDemand.nextRequest}
                    <li class="space-y-3 py-4 first:pt-0 last:pb-0">
                      <div class="flex flex-wrap items-start justify-between gap-3">
                        <div class="min-w-48 flex-1">
                          <p class="font-medium text-foreground">{branchDemand.branchName}</p>
                          <p class="text-xs text-foreground-muted">
                            {branchDemand.requests.length} solicitud(es) relacionada(s)
                          </p>
                        </div>
                        <div class="grid gap-x-5 gap-y-1 text-xs sm:grid-cols-3 sm:text-right">
                          <p>
                            <span class="text-foreground-muted">Solicitado </span><strong
                              class="text-foreground"
                              >{formatQuantity(branchDemand.requestedQuantity)}
                              {product.unitLabel}</strong
                            >
                          </p>
                          <p>
                            <span class="text-foreground-muted">Despachado </span><strong
                              class="text-foreground"
                              >{formatQuantity(branchDemand.dispatchedQuantity)}
                              {product.unitLabel}</strong
                            >
                          </p>
                          <p>
                            <span class="text-foreground-muted">Pendiente </span><strong
                              class="text-primary"
                              >{formatQuantity(branchDemand.remainingQuantity)}
                              {product.unitLabel}</strong
                            >
                          </p>
                        </div>
                        {#if nextRequest && product.productId != null}
                          <button
                            type="button"
                            class="rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-sm font-medium text-primary hover:bg-primary/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                            aria-label={`Preparar despacho de ${product.productName} para ${branchDemand.branchName}`}
                            onclick={() =>
                              onPrepareRequest(
                                nextRequest.requestId,
                                product.productId!,
                                product.unitId
                              )}
                          >
                            Preparar despacho
                          </button>
                        {/if}
                      </div>
                      <details class="rounded-lg border border-border px-3 py-2">
                        <summary
                          class="cursor-pointer text-xs font-medium text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                          >Ver solicitudes y fechas originales</summary
                        >
                        <ul class="mt-2 space-y-2">
                          {#each branchDemand.requests as demand (demand.id)}
                            <li class="flex flex-wrap items-center justify-between gap-2 text-xs">
                              <a
                                class="font-mono text-primary hover:underline"
                                href={`/purchase-requests/${demand.requestId}`}
                                >{demand.requestCode}</a
                              >
                              <span class="text-foreground-muted"
                                >Solicitó {formatDate(demand.requestDate)} · Requerida {formatDate(
                                  demand.requiredDate
                                )} · Pendiente {formatQuantity(demand.remainingQuantity)}
                                {product.unitLabel}</span
                              >
                            </li>
                          {/each}
                        </ul>
                      </details>
                    </li>
                  {/each}
                </ul>
              {/if}
            </div>
          </details>
        {/each}
      </div>
      {#if !showAllProducts && !productSearch.trim() && filteredProducts.length > visibleProducts.length}
        <button
          type="button"
          class="w-full rounded-xl border border-border px-4 py-2.5 text-sm font-medium text-primary hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          onclick={() => {
            showAllProducts = true;
          }}
        >
          Mostrar los {filteredProducts.length - visibleProducts.length} productos restantes
        </button>
      {/if}
    {/if}
    <p class="text-xs text-foreground-muted">
      El resumen agrupa los pendientes por sucursal. Al preparar un despacho se toma como referencia
      el pendiente más próximo y se conserva la trazabilidad del pedido; los excedentes requieren
      indicar el motivo.
    </p>
  </section>

  <dl class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
    <div class="rounded-xl border border-border-subtle bg-surface-subtle p-4">
      <dt class="text-xs font-medium text-foreground-muted">Productos con existencia liberada</dt>
      <dd class="mt-1 text-2xl font-semibold text-foreground">
        {productsWithStock.toLocaleString('es-SV')}
      </dd>
      <p class="mt-1 text-xs text-foreground-muted">Listos para asignar a un despacho</p>
    </div>
    <div class="rounded-xl border border-border-subtle bg-surface-subtle p-4">
      <dt class="text-xs font-medium text-foreground-muted">Unidades disponibles para despacho</dt>
      <dd class="mt-1 text-2xl font-semibold text-foreground">
        {handlingUnitCount.toLocaleString('es-SV')}
      </dd>
      <p class="mt-1 text-xs text-foreground-muted">Cajas, pallets u otras unidades completas</p>
    </div>
    <div class="rounded-xl border border-border-subtle bg-surface-subtle p-4">
      <dt class="text-xs font-medium text-foreground-muted">Sucursales con pendiente</dt>
      <dd class="mt-1 text-2xl font-semibold text-foreground">
        {branchesWithPendingDemand.toLocaleString('es-SV')}
      </dd>
      <p class="mt-1 text-xs text-foreground-muted">Relacionadas con productos disponibles</p>
    </div>
    <div class="rounded-xl border border-border-subtle bg-surface-subtle p-4">
      <dt class="text-xs font-medium text-foreground-muted">Última recepción central</dt>
      {#if latestReceipt}
        <dd
          class="mt-1 truncate text-base font-semibold text-foreground"
          title={latestReceipt.purchaseCode ?? latestReceipt.reference}
        >
          {latestReceipt.purchaseCode ?? latestReceipt.reference}
        </dd>
        <p class="mt-1 text-xs text-foreground-muted">{formatDateTime(latestReceipt.receivedAt)}</p>
      {:else}
        <dd class="mt-1 text-base font-semibold text-foreground">Sin recepciones</dd>
        <p class="mt-1 text-xs text-foreground-muted">No hay ingresos registrados en la matriz</p>
      {/if}
    </div>
  </dl>

  {#if requestError}
    <p
      class="rounded-xl border border-danger/30 bg-danger/10 px-3 py-3 text-sm text-danger"
      role="alert"
    >
      {requestError} El reparto sugerido está incompleto.
    </p>
  {/if}

  <p
    class="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-foreground-muted"
  >
    Las compras se reciben desde su proceso de recepción. Aquí solo aparecen existencias liberadas
    en la matriz; lo que siga en cuarentena debe revisarse y liberarse antes de despacharlo.
  </p>

  <section
    class="space-y-3 border-t border-border pt-5"
    aria-labelledby="transfer-receipts-heading"
  >
    <div>
      <h3 id="transfer-receipts-heading" class="font-semibold text-foreground">
        Recepciones recientes en matriz
      </h3>
      <p class="text-xs text-foreground-muted">
        Este historial sirve para ubicar compras recibidas; solo el stock liberado aparece arriba
        como disponible.
      </p>
    </div>

    {#if receiptLoading}
      <div class="space-y-2" aria-live="polite">
        <div class="h-16 animate-pulse rounded-xl bg-surface-subtle"></div>
        <div class="h-16 animate-pulse rounded-xl bg-surface-subtle"></div>
        <span class="sr-only">Cargando recepciones recientes</span>
      </div>
    {:else if receiptError}
      <p
        class="rounded-xl border border-danger/30 bg-danger/10 px-3 py-3 text-sm text-danger"
        role="alert"
      >
        {receiptError}
      </p>
    {:else if receipts.length === 0}
      <div
        class="rounded-xl border border-border border-dashed px-4 py-6 text-sm text-foreground-muted"
      >
        Todavía no hay recepciones de inventario registradas para esta matriz.
      </div>
    {:else}
      <ol class="grid gap-2 lg:grid-cols-2">
        {#each receipts as receipt (receipt.id)}
          <li class="rounded-xl border border-border bg-surface-subtle p-3">
            <div class="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p class="font-mono text-sm font-semibold text-primary">
                  {receipt.purchaseCode ?? receipt.reference}
                </p>
                <p class="text-xs text-foreground-muted">{formatDateTime(receipt.receivedAt)}</p>
              </div>
              <span
                class="rounded-full border border-success/30 bg-success/10 px-2 py-1 text-xs text-success"
                >Recepción registrada</span
              >
            </div>
            <ul class="mt-2 space-y-1">
              {#each receipt.products.slice(0, 3) as product (product.key)}
                <li class="flex justify-between gap-3 text-xs">
                  <span class="min-w-0 truncate text-foreground">{product.productName}</span>
                  <span class="shrink-0 text-foreground-muted"
                    >{formatQuantity(product.quantity)} {product.unitLabel}</span
                  >
                </li>
              {/each}
            </ul>
            {#if receipt.products.length > 3}
              <p class="mt-1 text-xs text-foreground-muted">
                y {receipt.products.length - 3} producto(s) más
              </p>
            {/if}
          </li>
        {/each}
      </ol>
    {/if}
  </section>
</section>
