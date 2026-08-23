<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { catalogApi } from '$lib/api/catalog';
  import { HttpError } from '$lib/api/client';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import PackagingManager from '$lib/features/inventory/components/PackagingManager.svelte';
  import ProductIdentifiersDisplay from '$lib/features/products/components/ProductIdentifiersDisplay.svelte';
  import { inventoryApi } from '$lib/features/inventory/services';
  import {
    type InventoryItem,
    type InventoryItemSummary,
    type StockStatus
  } from '$lib/features/inventory/types';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Product, ProductVariant, Unit } from '$lib/types/catalog';

  const STATUS_LABEL: Record<ProductVariant['lifecycle_status'], string> = {
    draft: 'Borrador',
    active: 'Activa',
    blocked: 'Bloqueada',
    discontinued: 'Descontinuada',
    retired: 'Retirada'
  };

  const STOCK_STATUS_LABEL: Record<StockStatus, string> = {
    available: 'Disponible',
    quarantine: 'Cuarentena',
    blocked: 'Bloqueada',
    damaged: 'Dañada',
    in_transit: 'En tránsito'
  };

  const STOCK_STATUS_VARIANT: Record<
    StockStatus,
    'success' | 'warning' | 'danger' | 'neutral' | 'primary'
  > = {
    available: 'success',
    quarantine: 'warning',
    blocked: 'danger',
    damaged: 'danger',
    in_transit: 'primary'
  };

  const STORAGE_LABEL: Record<string, string> = {
    ambient: 'Ambiente',
    cool: 'Fresco',
    refrigerated: 'Refrigerado',
    frozen: 'Congelado',
    dry: 'Seco',
    other: 'Otra'
  };

  let productId = $derived(Number(page.params.id));
  let variantId = $derived((page.params as { variantId?: string }).variantId ?? '');
  let product = $state<Product | null>(null);
  let variant = $state<ProductVariant | null>(null);
  let units = $state<Unit[]>([]);
  let inventoryItem = $state<InventoryItem | null>(null);
  let inventoryItemResolved = $state(false);
  let inventorySummary = $state<InventoryItemSummary | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let inventoryLoading = $state(false);
  let inventoryError = $state<string | null>(null);
  let summaryError = $state<string | null>(null);
  let unitsError = $state<string | null>(null);

  let canReadInventory = $derived(permissions.hasPermission('inventory:read'));
  let canEditVariant = $derived(
    permissions.hasPermission('products:variants') ||
      permissions.hasPermission('products:identifiers') ||
      permissions.hasPermission('products:images')
  );

  function statusVariant(status: ProductVariant['lifecycle_status']) {
    if (status === 'active') return 'success';
    if (status === 'draft') return 'primary';
    if (status === 'blocked' || status === 'retired') return 'danger';
    return 'warning';
  }

  function unitName(id: number): string {
    return units.find((unit) => unit.id_unit === id)?.name ?? `Unidad #${id}`;
  }

  function number(value: number, maximumFractionDigits = 3): string {
    return value.toLocaleString('es-SV', { maximumFractionDigits });
  }

  function quantity(value: number): string {
    return number(value, 6);
  }

  function physical(value: number | null, unit: string): string {
    return value == null ? 'Desconocido' : `${number(value)} ${unit}`;
  }

  function dateTime(value?: string | null): string {
    if (!value) return 'No registrada';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? 'No registrada' : parsed.toLocaleString('es-SV');
  }

  function storageLabel(value?: Product['storage_condition']): string {
    return value ? (STORAGE_LABEL[value] ?? value) : 'No definida';
  }

  function errorMessage(value: unknown, fallback: string): string {
    return value instanceof HttpError || value instanceof Error ? value.message : fallback;
  }

  async function loadInventory() {
    if (!variantId || !canReadInventory) return;
    inventoryLoading = true;
    inventoryError = null;
    summaryError = null;
    inventoryItem = null;
    inventorySummary = null;
    inventoryItemResolved = false;

    try {
      const item = await inventoryApi.getItemByTarget({ variantId });
      inventoryItem = item;
      inventoryItemResolved = true;
      if (!item) return;

      const [summaryResult] = await Promise.allSettled([inventoryApi.getItemSummary(item.id)]);
      if (summaryResult.status === 'fulfilled') inventorySummary = summaryResult.value;
      else
        summaryError = errorMessage(
          summaryResult.reason,
          'No se pudo cargar el resumen de inventario.'
        );
    } catch (err: unknown) {
      inventoryItemResolved = true;
      inventoryError = errorMessage(err, 'No se pudo resolver la identidad inventariable.');
    } finally {
      inventoryLoading = false;
    }
  }

  async function load() {
    if (!Number.isInteger(productId) || productId < 1 || !variantId) {
      error = 'La variante solicitada no es válida.';
      loading = false;
      return;
    }
    loading = true;
    error = null;
    unitsError = null;
    try {
      const [catalogResult, unitsResult] = await Promise.allSettled([
        Promise.all([
          catalogApi.getProduct(productId),
          catalogApi.getProductVariant(productId, variantId)
        ]),
        catalogApi.listUnits(true)
      ]);
      if (catalogResult.status === 'rejected') throw catalogResult.reason;
      [product, variant] = catalogResult.value;
      if (unitsResult.status === 'fulfilled') units = unitsResult.value;
      else
        unitsError = 'No se pudo cargar el catálogo de unidades; se mostrarán sus identificadores.';
    } catch (err: unknown) {
      error = errorMessage(err, 'No se pudo cargar el detalle de la variante.');
    } finally {
      loading = false;
    }
    if (!error && canReadInventory) void loadInventory();
  }

  function retryCatalog() {
    void load();
  }

  function retryInventory() {
    void loadInventory();
  }

  $effect(() => {
    if (productId && variantId) void load();
  });
</script>

<svelte:head>
  <title
    >{variant ? `${variant.display_name} — Productos` : 'Detalle de variante — Productos'}</title
  >
</svelte:head>

<div class="p-6 md:p-8">
  {#if loading}
    <div class="space-y-5" aria-busy="true" role="status">
      <span class="sr-only">Cargando detalle de variante…</span>
      <div class="h-28 rounded-2xl skeleton"></div>
      <div class="grid gap-5 lg:grid-cols-2">
        <div class="h-56 rounded-2xl skeleton"></div>
        <div class="h-56 rounded-2xl skeleton"></div>
      </div>
      <div class="h-64 rounded-2xl skeleton"></div>
    </div>
  {:else if error || !product || !variant}
    <div>
      <div
        class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-4 text-sm text-danger"
        role="alert"
      >
        {error ?? 'La variante no está disponible.'}
      </div>
      <div class="mt-4 flex gap-2">
        <Button size="sm" onclick={retryCatalog}>Reintentar</Button>
        <Button size="sm" variant="secondary" onclick={() => goto(`/products/${productId}`)}>
          Volver al producto
        </Button>
      </div>
    </div>
  {:else}
    <header class="mb-6">
      <div class="flex items-center gap-3">
        <a
          href={`/products/${product.id_product}`}
          class="flex h-8 w-8 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground"
          aria-label="Volver al producto"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
            ><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg
          >
        </a>
        <div class="min-w-0 flex-1">
          <h1 class="text-xl font-bold text-foreground">Detalle de la variante</h1>
          <div
            class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-foreground-muted"
          >
            <span class="min-w-0 truncate">{variant.display_name}</span>
            <span class="font-mono text-xs">{variant.sku}</span>
            <Badge variant={statusVariant(variant.lifecycle_status)}
              >{STATUS_LABEL[variant.lifecycle_status]}</Badge
            >
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          {#if canEditVariant}
            <Button
              variant="secondary"
              size="sm"
              onclick={() => goto(`/products/${product!.id_product}/variants/${variant!.id}/edit`)}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
                ><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z" /></svg
              >
              Editar variante
            </Button>
          {/if}
          <Button
            variant="secondary"
            size="sm"
            onclick={() => goto(`/products/${product!.id_product}/variants`)}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
              ><path d="M4 5h16M4 12h16M4 19h16" /><circle cx="8" cy="5" r="2" /><circle
                cx="16"
                cy="12"
                r="2"
              /><circle cx="10" cy="19" r="2" /></svg
            >
            Gestionar variantes
          </Button>
        </div>
      </div>
      <div class="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-xs text-foreground-muted">
        <span>Producto padre: <strong class="text-foreground">{product.sku}</strong></span>
        <span
          >Actualizada: <strong class="text-foreground">{dateTime(variant.updated_at)}</strong
          ></span
        >
      </div>
    </header>

    <main class="space-y-5">
      <div class="grid gap-5 lg:grid-cols-2">
        <Card class="p-6">
          <div class="mb-5">
            <h2 class="text-base font-semibold text-foreground">Identidad y combinación</h2>
            <p class="mt-1 text-sm text-foreground-muted">
              Valores que diferencian esta variante dentro del producto padre.
            </p>
          </div>
          <div class="flex flex-wrap gap-2" aria-label="Combinación de atributos">
            {#if variant.values.length}
              {#each variant.values as value (value.attribute_code)}
                <span
                  class="rounded-full border border-primary/25 bg-primary/5 px-3 py-1.5 text-xs text-foreground-muted"
                >
                  {value.attribute_code}: <strong class="text-foreground">{value.label}</strong>
                </span>
              {/each}
            {:else}
              <span class="text-sm text-foreground-muted">Sin atributos configurados.</span>
            {/if}
          </div>
          <dl class="mt-5 grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt class="text-xs text-foreground-muted">SKU</dt>
              <dd class="mt-1 font-mono text-foreground">{variant.sku}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Nombre mostrado</dt>
              <dd class="mt-1 text-foreground">{variant.display_name}</dd>
            </div>
            <div class="sm:col-span-2">
              <dt class="text-xs text-foreground-muted">Clave de combinación</dt>
              <dd class="mt-1 break-all font-mono text-xs text-foreground-muted">
                {variant.combination_key || '—'}
              </dd>
            </div>
          </dl>
        </Card>

        <Card class="p-6">
          <div class="mb-5 flex items-start justify-between gap-3">
            <div>
              <h2 class="text-base font-semibold text-foreground">Producto padre</h2>
              <p class="mt-1 text-sm text-foreground-muted">
                Datos heredados que se administran desde el producto.
              </p>
            </div>
            <a
              class="text-xs font-medium text-primary hover:underline"
              href={`/products/${product.id_product}`}>Ver producto</a
            >
          </div>
          <dl class="grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt class="text-xs text-foreground-muted">Nombre</dt>
              <dd class="mt-1 text-foreground">{product.name}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">SKU</dt>
              <dd class="mt-1 font-mono text-foreground">{product.sku}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Categoría</dt>
              <dd class="mt-1 text-foreground">
                {product.category_name ?? 'Categoría no disponible'}
              </dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Unidades</dt>
              <dd class="mt-1 text-foreground">
                {unitName(product.purchase_unit)} / {unitName(product.sale_unit)}
              </dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Almacenamiento</dt>
              <dd class="mt-1 text-foreground">{storageLabel(product.storage_condition)}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Apilado</dt>
              <dd class="mt-1 text-foreground">{product.stackable ? 'Apilable' : 'No apilable'}</dd>
            </div>
          </dl>
        </Card>
      </div>

      <div class="grid gap-5 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <Card class="p-6">
          <div class="mb-5">
            <h2 class="text-base font-semibold text-foreground">Imagen principal</h2>
            <p class="mt-1 text-sm text-foreground-muted">Imagen propia de esta variante.</p>
          </div>
          {#if variant.image?.url}
            <img
              src={variant.image.url}
              alt={variant.image.alt_text || variant.display_name}
              class="mx-auto aspect-square max-h-64 w-full rounded-xl border border-border object-contain"
              referrerpolicy="no-referrer"
            />
          {:else}
            <div
              class="flex aspect-square max-h-64 items-center justify-center rounded-xl border border-dashed border-border bg-surface-muted/30 text-sm text-foreground-subtle"
            >
              Sin imagen registrada
            </div>
          {/if}
        </Card>

        <Card class="p-6">
          <ProductIdentifiersDisplay
            identifiers={variant.identifiers ?? []}
            title="Identificadores de la variante"
            description="Códigos propios de esta combinación. No incluye los identificadores del producto padre."
          />
        </Card>
      </div>

      {#if canReadInventory}
        <Card class="p-6">
          {#if inventoryError}
            <div
              class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
              role="alert"
            >
              <p>{inventoryError}</p>
              <button type="button" class="mt-2 font-medium underline" onclick={retryInventory}
                >Reintentar inventario</button
              >
            </div>
          {:else if inventoryLoading && !inventoryItemResolved}
            <div class="h-24 rounded-xl skeleton" role="status">
              <span class="sr-only">Cargando identidad de inventario…</span>
            </div>
          {:else}
            <div class="mb-5 flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 class="text-base font-semibold text-foreground">
                  Resumen global de inventario
                </h2>
                <p class="mt-1 text-sm text-foreground-muted">
                  Existencias de esta variante en todos los almacenes.
                </p>
              </div>
              {#if inventorySummary}<Badge
                  variant={inventorySummary.measurement_status === 'complete'
                    ? 'success'
                    : 'warning'}
                  >{inventorySummary.measurement_status === 'complete'
                    ? 'Medición completa'
                    : 'Medición incompleta'}</Badge
                >{/if}
            </div>
            {#if !inventoryItem}
              <div class="rounded-xl border border-dashed border-border p-6 text-center">
                <p class="text-sm font-medium text-foreground">Inventario aún no habilitado</p>
                <p class="mt-1 text-xs text-foreground-muted">
                  Esta variante todavía no tiene una identidad inventariable ni existencias
                  registradas.
                </p>
              </div>
            {:else if summaryError}
              <div
                class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
                role="alert"
              >
                <p>{summaryError}</p>
                <button type="button" class="mt-2 font-medium underline" onclick={retryInventory}
                  >Reintentar resumen</button
                >
              </div>
            {:else if inventoryLoading || !inventorySummary}
              <div class="h-40 rounded-xl skeleton" role="status">
                <span class="sr-only">Cargando resumen de inventario…</span>
              </div>
            {:else}
              <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div class="rounded-lg border border-border bg-surface-muted/20 p-3">
                  <p class="text-xs text-foreground-muted">Cantidad base total</p>
                  <p class="mt-1 text-lg font-semibold text-foreground">
                    {quantity(inventorySummary.total_quantity_base)}
                  </p>
                </div>
                <div class="rounded-lg border border-border bg-surface-muted/20 p-3">
                  <p class="text-xs text-foreground-muted">Peso ocupado</p>
                  <p class="mt-1 text-lg font-semibold text-foreground">
                    {physical(inventorySummary.occupied_weight_kg, 'kg')}
                  </p>
                </div>
                <div class="rounded-lg border border-border bg-surface-muted/20 p-3">
                  <p class="text-xs text-foreground-muted">Volumen ocupado</p>
                  <p class="mt-1 text-lg font-semibold text-foreground">
                    {physical(inventorySummary.occupied_volume_m3, 'm³')}
                  </p>
                </div>
                <div class="rounded-lg border border-border bg-surface-muted/20 p-3">
                  <p class="text-xs text-foreground-muted">Unidades logísticas</p>
                  <p class="mt-1 text-lg font-semibold text-foreground">
                    {number(inventorySummary.handling_unit_count, 0)}
                  </p>
                  <p class="mt-1 text-[11px] text-foreground-muted">
                    {inventorySummary.unmeasured_handling_units
                      ? `${inventorySummary.unmeasured_handling_units} sin medir`
                      : 'Todas medidas'}
                  </p>
                </div>
              </div>
              <div class="mt-5 overflow-x-auto rounded-xl border border-border">
                <table class="w-full min-w-[720px] text-sm">
                  <caption class="sr-only">Existencias de la variante por estado</caption>
                  <thead
                    class="border-b border-border bg-surface-muted/30 text-left text-xs text-foreground-muted"
                    ><tr
                      ><th scope="col" class="px-3 py-2">Estado</th><th
                        scope="col"
                        class="px-3 py-2">Cantidad base</th
                      ><th scope="col" class="px-3 py-2">Peso</th><th scope="col" class="px-3 py-2"
                        >Volumen</th
                      ><th scope="col" class="px-3 py-2">Medición</th></tr
                    ></thead
                  >
                  <tbody class="divide-y divide-border">
                    {#each inventorySummary.status_totals as status (status.stock_status)}
                      <tr>
                        <td class="px-3 py-2"
                          ><Badge variant={STOCK_STATUS_VARIANT[status.stock_status]}
                            >{STOCK_STATUS_LABEL[status.stock_status]}</Badge
                          ></td
                        >
                        <td class="px-3 py-2 text-foreground">{quantity(status.quantity_base)}</td>
                        <td class="px-3 py-2 text-foreground"
                          >{physical(status.occupied_weight_kg, 'kg')}</td
                        >
                        <td class="px-3 py-2 text-foreground"
                          >{physical(status.occupied_volume_m3, 'm³')}</td
                        >
                        <td class="px-3 py-2 text-xs text-foreground-muted"
                          >{status.measurement_status === 'complete'
                            ? 'Completa'
                            : 'Incompleta'}</td
                        >
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
              <div class="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-xs text-foreground-muted">
                <span
                  >Almacenes: <strong class="text-foreground"
                    >{inventorySummary.warehouse_count}</strong
                  ></span
                >
                <span
                  >Ubicaciones: <strong class="text-foreground"
                    >{inventorySummary.location_count}</strong
                  ></span
                >
                <span
                  >Lotes: <strong class="text-foreground">{inventorySummary.lot_count}</strong
                  ></span
                >
              </div>
              {#if inventorySummary.measurement_status === 'incomplete'}
                <p
                  class="mt-4 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning"
                >
                  Hay unidades logísticas sin medición completa. El peso y volumen total se muestran
                  como desconocidos hasta verificarlas.
                </p>
              {/if}
            {/if}
          {/if}
        </Card>

        {#if unitsError}
          <div
            class="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning"
            role="status"
          >
            {unitsError}
          </div>
        {/if}

        {#if inventoryItemResolved && !inventoryError}
          <PackagingManager
            variantId={variant.id}
            defaultBaseUnitId={inventoryItem?.base_unit_id ?? product.sale_unit}
            unitOptions={units.map((unit) => ({ id: unit.id_unit, label: unit.name }))}
            canManage={false}
            {inventoryItem}
            {inventoryItemResolved}
          />
        {/if}
      {:else}
        <Card class="p-6">
          <h2 class="text-base font-semibold text-foreground">Inventario y empaques</h2>
          <p class="mt-2 text-sm text-foreground-muted">
            No tiene permiso para consultar la información de inventario de esta variante.
          </p>
        </Card>
      {/if}
    </main>
  {/if}
</div>
