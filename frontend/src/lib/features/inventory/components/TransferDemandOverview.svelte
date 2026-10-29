<script lang="ts">
  import { tick } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import type { TransferDemandRecord } from '$lib/features/inventory/transfer-documents';
  import {
    compareQuantities,
    formatQuantity,
    quantityFromScaled,
    scaledQuantity
  } from '$lib/features/inventory/transfer-operations';
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
    selectedProductKey?: string;
    demandIncomplete?: boolean;
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
    selectedProductKey = '',
    demandIncomplete = false,
    canMoveInventory,
    onSearch,
    onPrepareManual,
    onPrepareDemand
  }: Props = $props();
  let inspectedKey = $state('');
  let filter = $state<'all' | 'pending' | 'available'>('all');
  let productHeading = $state<HTMLHeadingElement | null>(null);
  let detailHeading = $state<HTMLHeadingElement | null>(null);
  const stockReady = $derived(stockState === 'loaded' || stockState === 'empty');
  const demandReady = $derived(demandState === 'loaded' || demandState === 'empty');
  const loading = $derived(stockState === 'loading' || demandState === 'loading');
  const pendingDemands = $derived(
    products
      .flatMap((product) => product.demands)
      .filter((demand) => compareQuantities(demand.quantity_pending, '0') > 0)
  );
  const stockedCount = $derived(
    new Set(
      products.filter((product) => product.units.length > 0).map((product) => product.productId)
    ).size
  );
  const unitCount = $derived(products.reduce((sum, product) => sum + product.units.length, 0));
  const requestCount = $derived(
    new Set(pendingDemands.map((demand) => demand.purchase_request_id)).size
  );
  const branchCount = $derived(new Set(pendingDemands.map((demand) => demand.branch_id)).size);
  let visibleProducts = $derived.by(() => {
    const query = search.trim().toLocaleLowerCase('es-SV');
    return products.filter((product) => {
      if (filter === 'available' && product.units.length === 0) return false;
      if (filter === 'pending' && pendingQuantity(product) <= 0n) return false;
      return (
        !query ||
        [
          product.productName,
          product.sku,
          ...product.demands.flatMap((demand) => [demand.branch_name, demand.request_code])
        ].some((value) => value?.toLocaleLowerCase('es-SV').includes(query))
      );
    });
  });
  const activeProduct = $derived(
    visibleProducts.find((product) => product.key === inspectedKey) ??
      visibleProducts.find((product) => product.key === selectedProductKey) ??
      visibleProducts[0] ??
      null
  );
  const metrics = $derived([
    {
      label: 'Productos disponibles',
      value: stockReady ? String(stockedCount) : '—',
      hint: 'Con unidades listas para despacho'
    },
    {
      label: 'Unidades logísticas',
      value: stockReady ? String(unitCount) : '—',
      hint: 'En la bodega de origen'
    },
    {
      label: 'Solicitudes pendientes',
      value: demandReady ? `${demandIncomplete ? '≥ ' : ''}${requestCount}` : '—',
      hint: demandIncomplete ? 'Consulta parcial de sucursales' : 'Con cantidad por asignar'
    },
    {
      label: 'Sucursales solicitantes',
      value: demandReady ? `${demandIncomplete ? '≥ ' : ''}${branchCount}` : '—',
      hint: demandIncomplete ? 'Consulta parcial de sucursales' : 'Esperando abastecimiento'
    }
  ]);

  function pendingQuantity(product: ProductRow): bigint {
    return product.demands.reduce(
      (sum, demand) => sum + (scaledQuantity(demand.quantity_pending) ?? 0n),
      0n
    );
  }
  function formatDate(value: string | null): string {
    if (!value) return 'Sin fecha requerida';
    const parsed = new Date(`${value.slice(0, 10)}T12:00:00Z`);
    return Number.isNaN(parsed.getTime())
      ? 'Sin fecha requerida'
      : new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium', timeZone: 'UTC' }).format(parsed);
  }
  function assignmentProgress(demand: TransferDemandRecord): number {
    const requested = scaledQuantity(demand.quantity_requested);
    const assigned = scaledQuantity(demand.quantity_assigned);
    if (requested == null || requested <= 0n || assigned == null) return 0;
    return Number(((assigned > requested ? requested : assigned) * 10_000n) / requested) / 100;
  }
  function assignmentProgressText(demand: TransferDemandRecord): string {
    return `${assignmentProgress(demand).toLocaleString('es-SV', { maximumFractionDigits: 2 })}% asignado`;
  }
  function prepareIssue(product: ProductRow, demand?: TransferDemandRecord): string | null {
    if (!canMoveInventory) return 'Tu perfil no tiene permiso para preparar traslados.';
    if (!stockReady) return 'Actualiza las existencias antes de preparar.';
    if (demand && !demandReady) return 'Actualiza las solicitudes antes de preparar.';
    if (!product.units.length) return 'No hay unidades disponibles para este producto.';
    if (demand && compareQuantities(demand.quantity_pending, '0') <= 0)
      return 'La solicitud ya no tiene cantidad pendiente de asignar.';
    return null;
  }
  async function inspectProduct(key: string) {
    inspectedKey = key;
    await tick();
    if (window.matchMedia('(max-width: 1023px)').matches) {
      detailHeading?.focus({ preventScroll: true });
      detailHeading?.scrollIntoView({ block: 'start', behavior: 'instant' });
    }
  }
</script>

<section class="space-y-4" aria-label="Dashboard de abastecimiento">
  <dl class="grid grid-cols-2 gap-3 xl:grid-cols-4">
    {#each metrics as metric (metric.label)}
      <div class="min-w-0 rounded-xl border border-border bg-surface-elevated p-4">
        <dt class="text-xs font-medium text-foreground-muted">{metric.label}</dt>
        {#if loading}
          <dd class="skeleton mt-3 h-8 w-16 rounded" aria-label="Cargando resumen"></dd>
        {:else}
          <dd
            class="mt-2 font-mono text-2xl font-semibold tracking-tight text-foreground sm:text-3xl"
          >
            {metric.value}
          </dd>
        {/if}
        <dd class="mt-2 text-xs leading-5 text-foreground-muted">{metric.hint}</dd>
      </div>
    {/each}
  </dl>

  <div class="rounded-2xl border border-border bg-surface">
    <div class="flex flex-wrap items-end justify-between gap-3 border-b border-border p-4">
      <label class="block w-full space-y-1.5 text-sm font-medium text-foreground lg:max-w-lg">
        Buscar producto, SKU, sucursal o solicitud
        <input
          class="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus-visible:ring-2 focus-visible:ring-primary"
          type="search"
          value={search}
          oninput={(event) => onSearch(event.currentTarget.value)}
          placeholder="Ej. Harina, PRD-HAR-003 o SCR-00016"
        />
      </label>
      <div
        class="flex max-w-full flex-wrap gap-1 rounded-lg border border-border bg-surface-muted p-1"
        role="group"
        aria-label="Filtrar productos"
      >
        {#each [{ value: 'all', label: 'Todos' }, { value: 'pending', label: 'Con solicitudes' }, { value: 'available', label: 'Disponibles' }] as option (option.value)}
          <button
            type="button"
            class="min-h-10 rounded-md px-3 text-xs font-medium transition-colors hover:bg-surface-hover focus-visible:ring-2 focus-visible:ring-primary"
            class:bg-surface-elevated={filter === option.value}
            class:text-foreground={filter === option.value}
            class:text-foreground-muted={filter !== option.value}
            aria-pressed={filter === option.value}
            disabled={option.value === 'pending' && !demandReady}
            onclick={() => (filter = option.value as typeof filter)}>{option.label}</button
          >
        {/each}
      </div>
    </div>

    {#if loading}
      <div class="grid gap-4 p-5 lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.5fr)]" role="status">
        <span class="sr-only">Consultando existencias y solicitudes…</span>
        <div class="space-y-3">
          {#each [1, 2, 3] as row (row)}<div class="skeleton h-20 rounded-lg"></div>{/each}
        </div>
        <div class="skeleton h-64 rounded-xl"></div>
      </div>
    {:else if stockState === 'error'}
      <div class="space-y-2 p-8" role="alert">
        <h3 class="font-semibold text-foreground">No se pudo consultar la existencia</h3>
        <p class="text-sm text-foreground-muted">
          {supplyError} Usa «Actualizar información» para reintentar. Los saldos desconocidos no se consideran
          cero.
        </p>
      </div>
    {:else if visibleProducts.length === 0}
      <div class="space-y-3 p-8 text-center">
        <span
          class="mx-auto grid size-12 place-items-center rounded-full bg-surface-muted text-xl text-foreground-muted"
          aria-hidden="true">⌕</span
        >
        <h3 class="font-semibold text-foreground">
          {products.length
            ? 'No hay productos que coincidan'
            : demandIncomplete
              ? 'No hay productos entre los datos consultados'
              : 'Sin existencias ni solicitudes para mostrar'}
        </h3>
        <p class="text-sm text-foreground-muted">
          {products.length
            ? 'Prueba otro nombre, SKU o sucursal, o muestra todos los productos.'
            : demandIncomplete
              ? 'Faltan sucursales por consultar. Actualiza la información para completar la demanda.'
              : 'Libera las unidades recibidas en la matriz y actualiza la información.'}
        </p>
        {#if search || filter !== 'all'}<Button
            variant="secondary"
            onclick={() => {
              onSearch('');
              filter = 'all';
            }}>Limpiar filtros</Button
          >{/if}
      </div>
    {:else}
      <div class="grid min-w-0 lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.5fr)]">
        <section
          class="min-w-0 border-b border-border lg:border-b-0 lg:border-r"
          aria-labelledby="transfer-products-heading"
        >
          <header
            class="flex items-center justify-between gap-2 border-b border-border bg-surface-muted/50 px-4 py-3"
          >
            <h3
              id="transfer-products-heading"
              bind:this={productHeading}
              tabindex="-1"
              class="text-sm font-semibold text-foreground"
            >
              Productos
            </h3>
            <span class="text-xs text-foreground-muted">{visibleProducts.length} resultados</span>
          </header>
          <ul class="max-h-72 divide-y divide-border overflow-y-auto lg:max-h-[38rem]">
            {#each visibleProducts as product (product.key)}
              <li>
                <button
                  class="flex min-h-24 w-full min-w-0 items-start gap-3 border-l-2 p-4 text-left transition-colors hover:bg-surface-hover focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
                  class:border-primary={activeProduct?.key === product.key}
                  class:border-transparent={activeProduct?.key !== product.key}
                  class:product-selected={activeProduct?.key === product.key}
                  aria-pressed={activeProduct?.key === product.key}
                  aria-controls="transfer-demand-detail"
                  onclick={() => void inspectProduct(product.key)}
                >
                  <span class="min-w-0 flex-1"
                    ><span class="block break-words text-sm font-semibold text-foreground"
                      >{product.productName}</span
                    ><span class="mt-1 block break-all font-mono text-xs text-foreground-muted"
                      >{product.sku ?? `Producto ${product.productId}`}</span
                    ><span class="mt-2 block text-xs text-foreground-muted"
                      >{product.units.length}
                      {product.units.length === 1 ? 'unidad logística' : 'unidades logísticas'} · {formatQuantity(
                        quantityFromScaled(product.availableQuantity)
                      )}
                      {product.unitLabel}</span
                    ></span
                  >
                  <span class="mt-0.5 shrink-0 text-xs text-foreground-muted" aria-hidden="true"
                    >›</span
                  >
                </button>
              </li>
            {/each}
          </ul>
        </section>
        {#if activeProduct}
          <section
            id="transfer-demand-detail"
            class="min-w-0 space-y-4 p-4 sm:p-5"
            aria-labelledby="transfer-demand-heading"
          >
            <button
              type="button"
              class="min-h-10 text-xs font-medium text-foreground-muted underline underline-offset-4 lg:hidden"
              onclick={() => {
                productHeading?.focus();
                productHeading?.scrollIntoView({ block: 'start', behavior: 'instant' });
              }}>Cambiar producto</button
            >
            <header class="flex flex-wrap items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <h3
                  id="transfer-demand-heading"
                  bind:this={detailHeading}
                  tabindex="-1"
                  class="scroll-mt-24 break-words text-base font-semibold text-foreground"
                >
                  {activeProduct.productName}
                </h3>
                <p class="mt-1 break-all font-mono text-xs text-foreground-muted">
                  {activeProduct.sku ?? `Producto ${activeProduct.productId}`} · {activeProduct.unitLabel}
                </p>
              </div>
              <Button
                variant="secondary"
                class="min-h-11"
                size="sm"
                disabled={Boolean(prepareIssue(activeProduct))}
                onclick={() => {
                  inspectedKey = activeProduct.key;
                  onPrepareManual(activeProduct.key);
                }}>Envío manual</Button
              >
            </header>
            <dl
              class="grid grid-cols-2 gap-3 rounded-xl border border-border bg-surface-muted/50 p-4"
            >
              <div>
                <dt class="text-xs text-foreground-muted">Disponible en matriz</dt>
                <dd class="mt-1 font-mono text-lg font-semibold text-foreground">
                  {formatQuantity(quantityFromScaled(activeProduct.availableQuantity))}
                  <span class="text-sm font-normal">{activeProduct.unitLabel}</span>
                </dd>
              </div>
              <div>
                <dt class="text-xs text-foreground-muted">Pendiente en sucursales</dt>
                <dd class="mt-1 font-mono text-lg font-semibold text-foreground">
                  {demandReady
                    ? `${demandIncomplete ? '≥ ' : ''}${formatQuantity(quantityFromScaled(pendingQuantity(activeProduct)))} ${activeProduct.unitLabel}`
                    : 'Sin consultar'}
                </dd>
              </div>
            </dl>
            {#if prepareIssue(activeProduct)}<p class="text-xs leading-5 text-foreground-muted">
                {prepareIssue(activeProduct)}
              </p>{/if}
            <div class="flex flex-wrap items-center justify-between gap-2">
              <h4 class="text-sm font-semibold text-foreground">Sucursales solicitantes</h4>
              <span class="text-xs text-foreground-muted">Cantidades en unidad base</span>
            </div>
            {#if !demandReady}
              <p
                class="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-foreground"
                role="status"
              >
                No se pudo consultar la demanda. Actualiza la información para preparar por
                solicitud.
              </p>
            {:else if activeProduct.demands.length === 0}
              <div class="rounded-xl border border-dashed border-border p-5">
                <p class="text-sm font-medium text-foreground">
                  {demandIncomplete
                    ? 'No se encontraron solicitudes entre las sucursales consultadas'
                    : 'Sin solicitudes asociadas'}
                </p>
                <p class="mt-1 text-xs leading-5 text-foreground-muted">
                  Puedes preparar un envío manual indicando la sucursal y el motivo.
                </p>
              </div>
            {:else}
              <div class="space-y-3">
                {#each activeProduct.demands as demand (demand.purchase_request_detail_id)}
                  {@const issue = prepareIssue(activeProduct, demand)}
                  <article class="rounded-xl border border-border p-3 sm:p-4">
                    <div class="flex flex-wrap items-start justify-between gap-3">
                      <div class="min-w-0">
                        <h5 class="break-words text-sm font-semibold text-foreground">
                          {demand.branch_name}
                        </h5>
                        <p class="mt-1 font-mono text-xs text-foreground-muted">
                          {demand.request_code}
                        </p>
                        <p class="mt-1 text-xs text-foreground-muted">
                          {formatDate(demand.required_date)}
                        </p>
                      </div>
                      <div class="text-right">
                        <p class="text-xs text-foreground-muted">Pendiente de asignar</p>
                        <p class="mt-1 font-mono text-lg font-semibold text-foreground">
                          {formatQuantity(demand.quantity_pending)}
                          {activeProduct.unitLabel}
                        </p>
                      </div>
                    </div>
                    <div
                      class="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-hover"
                      role="progressbar"
                      aria-label="Asignación de {demand.request_code} para {demand.branch_name}"
                      aria-valuetext={assignmentProgressText(demand)}
                      aria-valuemin="0"
                      aria-valuemax="100"
                      aria-valuenow={assignmentProgress(demand)}
                    >
                      <div
                        class="h-full rounded-full bg-primary"
                        style:width="{assignmentProgress(demand)}%"
                      ></div>
                    </div>
                    <div
                      class="mt-2 flex flex-wrap justify-between gap-2 text-xs text-foreground-muted"
                    >
                      <span
                        >Solicitado {formatQuantity(demand.quantity_requested)}
                        {activeProduct.unitLabel} · Asignado {formatQuantity(
                          demand.quantity_assigned
                        )}</span
                      ><span>{assignmentProgressText(demand)}</span>
                    </div>
                    <details class="mt-3 border-t border-border">
                      <summary
                        class="cursor-pointer rounded py-3 text-xs font-medium text-foreground focus-visible:ring-2 focus-visible:ring-primary"
                        >Ver despacho, tránsito y recepción</summary
                      >
                      <dl class="grid grid-cols-3 gap-2 pb-3 text-sm text-foreground">
                        <div>
                          <dt class="text-xs text-foreground-muted">Despachado</dt>
                          <dd>{formatQuantity(demand.quantity_dispatched)}</dd>
                        </div>
                        <div>
                          <dt class="text-xs text-foreground-muted">En tránsito</dt>
                          <dd>{formatQuantity(demand.quantity_in_transit)}</dd>
                        </div>
                        <div>
                          <dt class="text-xs text-foreground-muted">Recibido</dt>
                          <dd>{formatQuantity(demand.quantity_received)}</dd>
                        </div>
                      </dl>
                    </details>
                    <div class="flex flex-wrap items-center justify-between gap-2">
                      <p class="text-xs leading-5 text-foreground-muted">
                        {issue ?? 'Se abrirá la preparación con esta sucursal y solicitud.'}
                      </p>
                      <Button
                        class="min-h-11 shrink-0"
                        size="sm"
                        disabled={Boolean(issue)}
                        onclick={() => {
                          inspectedKey = activeProduct.key;
                          onPrepareDemand(activeProduct.key, demand);
                        }}>Preparar traslado</Button
                      >
                    </div>
                  </article>
                {/each}
              </div>
            {/if}
          </section>
        {/if}
      </div>
    {/if}
  </div>
</section>

<style>
  .product-selected {
    background-color: rgb(var(--primary) / 0.05);
  }
</style>
