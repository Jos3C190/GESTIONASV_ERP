<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { catalogApi } from '$lib/api/catalog';
  import type { Category, Product, Unit } from '$lib/types/catalog';
  import { permissions } from '$lib/stores/permissions.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import PackagingManager from '$lib/features/inventory/components/PackagingManager.svelte';

  let product = $state<Product | null>(null);
  let categories = $state<Category[]>([]);
  let units = $state<Unit[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let imageErrors = $state<Record<string, boolean>>({});
  let productId = $derived(Number(page.params.id));

  const statusLabel = (active: boolean) => (active ? 'Activo' : 'Inactivo');

  function categoryName(id: number) {
    return categories.find((item) => item.id_category === id)?.name ?? 'Sin categoría';
  }

  function unitName(id: number) {
    return units.find((item) => item.id_unit === id)?.name ?? '—';
  }

  function handleImageError(id: string) {
    imageErrors = { ...imageErrors, [id]: true };
  }

  async function load() {
    if (!Number.isInteger(productId) || productId < 1) {
      error = 'Producto no válido.';
      loading = false;
      return;
    }
    loading = true;
    error = null;
    try {
      const [productData, categoryData, unitData] = await Promise.all([
        catalogApi.getProduct(productId),
        catalogApi.listCategories(true),
        catalogApi.listUnits(true)
      ]);
      product = productData;
      categories = categoryData;
      units = unitData;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'No se pudo cargar el producto.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (productId) void load();
  });
</script>

<svelte:head>
  <title>{product ? `${product.name} — Productos` : 'Detalle del producto — GestionaSV'}</title>
</svelte:head>

<div class="p-6 md:p-8">
  <div class="mb-6 flex items-center gap-3">
    <a
      href="/products"
      class="flex h-8 w-8 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground"
      aria-label="Volver a productos"
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
      <h1 class="text-xl font-bold text-foreground">Detalle del producto</h1>
      <p class="text-sm text-foreground-muted">
        Información comercial, operativa y visual del producto.
      </p>
    </div>
    {#if product}
      <Button
        variant="secondary"
        size="sm"
        onclick={() => product && goto(`/products/${product.id_product}/variants`)}
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
        {product.variant_mode === 'template' ? 'Gestionar variantes' : 'Configurar variantes'}
      </Button>
    {/if}
    {#if product && permissions.hasPermission('products:manage')}
      <Button
        variant="secondary"
        size="sm"
        onclick={() => product && goto(`/products/${product.id_product}/edit`)}
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
        Editar
      </Button>
    {/if}
  </div>

  {#if loading}
    <div class="space-y-5">
      <div class="h-36 rounded-2xl skeleton"></div>
      <div class="grid gap-4 md:grid-cols-4">
        <div class="h-28 rounded-2xl skeleton"></div>
        <div class="h-28 rounded-2xl skeleton"></div>
        <div class="h-28 rounded-2xl skeleton"></div>
        <div class="h-28 rounded-2xl skeleton"></div>
      </div>
      <div class="h-96 rounded-2xl skeleton"></div>
    </div>
  {:else if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {:else if product}
    {@const cover =
      product.cover_image ?? product.images.find((image) => image.is_cover) ?? product.images[0]}
    <div class="space-y-5">
      <Card class="p-6">
        <div class="flex flex-col gap-5 sm:flex-row sm:items-center">
          <div
            class="h-24 w-24 flex-none overflow-hidden rounded-2xl border border-border bg-surface-muted"
          >
            {#if cover && !imageErrors[cover.id]}
              <img
                src={cover.url}
                alt={cover.alt_text || product.name}
                class="h-full w-full object-cover"
                referrerpolicy="no-referrer"
                onerror={() => handleImageError(cover.id)}
              />
            {:else}
              <div class="flex h-full items-center justify-center text-primary" aria-hidden="true">
                <svg
                  width="36"
                  height="36"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.5"
                  ><rect x="3" y="3" width="18" height="18" rx="3" /><circle
                    cx="8.5"
                    cy="8.5"
                    r="1.5"
                  /><path d="m21 15-5-5L5 21" /></svg
                >
              </div>
            {/if}
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-3">
              <h2 class="text-lg font-bold text-foreground">{product.name}</h2>
              <Badge variant={product.is_active ? 'success' : 'neutral'}
                >{statusLabel(product.is_active)}</Badge
              >
            </div>
            <div
              class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-foreground-muted"
            >
              <span class="font-mono text-xs">{product.sku}</span>
              <span>{categoryName(product.id_category)}</span>
              {#if product.internal_code}<span>Ref. {product.internal_code}</span>{/if}
            </div>
          </div>
          <div class="text-left sm:text-right">
            <p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
              Imágenes
            </p>
            <p class="font-mono text-2xl font-bold tabular-nums text-foreground">
              {product.image_count ?? product.images.length}
            </p>
          </div>
        </div>
      </Card>

      <div class="grid grid-cols-1 gap-4 md:grid-cols-4">
        <Card class="p-5"
          ><p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
            Categoría
          </p>
          <p class="mt-2 truncate text-sm font-semibold text-foreground">
            {categoryName(product.id_category)}
          </p>
          <p class="mt-1 text-xs text-foreground-muted">
            {product.id_sub_category ? 'Subcategoría asignada' : 'Sin subcategoría'}
          </p></Card
        >
        <Card class="p-5"
          ><p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
            Unidad de compra
          </p>
          <p class="mt-2 text-sm font-semibold text-foreground">
            {unitName(product.purchase_unit)}
          </p>
          <p class="mt-1 text-xs text-foreground-muted">Unidad de abastecimiento</p></Card
        >
        <Card class="p-5"
          ><p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
            Unidad de venta
          </p>
          <p class="mt-2 text-sm font-semibold text-foreground">{unitName(product.sale_unit)}</p>
          <p class="mt-1 text-xs text-foreground-muted">Unidad comercial</p></Card
        >
        <Card class="p-5"
          ><p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
            Estado
          </p>
          <p class="mt-2 text-sm font-semibold text-foreground">{statusLabel(product.is_active)}</p>
          <p class="mt-1 text-xs text-foreground-muted">
            {product.updated_at
              ? `Actualizado ${new Date(product.updated_at).toLocaleDateString('es-SV')}`
              : 'Catálogo operativo'}
          </p></Card
        >
      </div>

      <div class="grid gap-5 lg:grid-cols-2">
        <Card class="p-6">
          <h3 class="mb-4 text-sm font-semibold text-foreground">Información comercial</h3>
          <dl class="grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt class="text-xs text-foreground-muted">SKU</dt>
              <dd class="mt-1 font-mono text-foreground">{product.sku}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Código original</dt>
              <dd class="mt-1 text-foreground">{product.original_code || '—'}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Tamaño</dt>
              <dd class="mt-1 text-foreground">{product.size || '—'}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Dimensiones</dt>
              <dd class="mt-1 text-foreground">{product.dimension_summary || '—'}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Peso</dt>
              <dd class="mt-1 text-foreground">
                {product.weight != null ? `${product.weight} ${product.weight_unit ?? ''}` : '—'}
              </dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Volumen</dt>
              <dd class="mt-1 text-foreground">
                {product.volume != null
                  ? `${product.volume} ${product.volume_unit ?? 'm³'}`
                  : 'No calculable'}
              </dd>
            </div>
            {#if product.dimensions_legacy}
              <div class="sm:col-span-2">
                <dt class="text-xs text-foreground-muted">Dimensión anterior</dt>
                <dd class="mt-1 text-foreground-muted">{product.dimensions_legacy}</dd>
              </div>
            {/if}
            <div class="sm:col-span-2">
              <dt class="text-xs text-foreground-muted">Presentación</dt>
              <dd class="mt-1 text-foreground">{product.presentation || '—'}</dd>
            </div>
          </dl>
        </Card>
        <Card class="p-6">
          <h3 class="mb-4 text-sm font-semibold text-foreground">Descripción</h3>
          <p class="min-h-24 whitespace-pre-wrap text-sm leading-relaxed text-foreground-muted">
            {product.description || 'Este producto no tiene descripción registrada.'}
          </p>
        </Card>
      </div>

      <div class="grid gap-5 lg:grid-cols-2">
        <Card class="p-6">
          <h3 class="mb-4 text-sm font-semibold text-foreground">
            Nombres y clasificación operativa
          </h3>
          <dl class="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt class="text-xs text-foreground-muted">Nombre de venta</dt>
              <dd class="mt-1 text-foreground">{product.sales_name || '—'}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Nombre interno</dt>
              <dd class="mt-1 text-foreground">{product.internal_name || '—'}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Nombre para documentos</dt>
              <dd class="mt-1 text-foreground">{product.document_name || '—'}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Tipo</dt>
              <dd class="mt-1 text-foreground">
                {product.product_kind === 'service' ? 'Servicio' : 'Bien físico'}
              </dd>
            </div>
            <div class="sm:col-span-2">
              <dt class="text-xs text-foreground-muted">Palabras clave</dt>
              <dd class="mt-1 text-foreground">{product.keywords?.join(', ') || '—'}</dd>
            </div>
          </dl>
        </Card>
        <Card class="p-6">
          <h3 class="mb-4 text-sm font-semibold text-foreground">Almacenamiento y manipulación</h3>
          {#if product.product_kind === 'service'}
            <p class="text-sm text-foreground-muted">No aplica a servicios.</p>
          {:else}
            <dl class="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt class="text-xs text-foreground-muted">Condición</dt>
                <dd class="mt-1 text-foreground">{product.storage_condition || '—'}</dd>
              </div>
              <div>
                <dt class="text-xs text-foreground-muted">Temperatura</dt>
                <dd class="mt-1 text-foreground">
                  {product.storage_temperature_min_c != null ||
                  product.storage_temperature_max_c != null
                    ? `${product.storage_temperature_min_c ?? '—'} a ${product.storage_temperature_max_c ?? '—'} °C`
                    : '—'}
                </dd>
              </div>
              <div>
                <dt class="text-xs text-foreground-muted">Humedad máxima</dt>
                <dd class="mt-1 text-foreground">
                  {product.storage_humidity_max_percent != null
                    ? `${product.storage_humidity_max_percent}%`
                    : '—'}
                </dd>
              </div>
              <div>
                <dt class="text-xs text-foreground-muted">Apilado</dt>
                <dd class="mt-1 text-foreground">
                  {product.stackable === false ? 'No apilable' : 'Apilable'}
                </dd>
              </div>
              <div class="sm:col-span-2">
                <dt class="text-xs text-foreground-muted">Indicaciones</dt>
                <dd class="mt-1 whitespace-pre-wrap text-foreground-muted">
                  {product.handling_notes || '—'}
                </dd>
              </div>
            </dl>
          {/if}
        </Card>
      </div>

      {#if product.product_kind === 'goods' && product.variant_mode === 'standalone' && permissions.hasPermission('inventory:read')}
        <Card class="p-6">
          <PackagingManager
            productId={product.id_product}
            defaultBaseUnitId={product.sale_unit}
            unitOptions={units.map((unit) => ({ id: unit.id_unit, label: unit.name }))}
            canManage={permissions.hasPermission('inventory:manage_packaging')}
          />
        </Card>
      {/if}

      {#if product.variant_mode === 'template'}
        <Card class="p-6">
          <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 class="text-sm font-semibold text-foreground">Familia y variantes</h3>
              <p class="mt-1 text-xs text-foreground-muted">
                El producto padre es una plantilla; las operaciones futuras usarán el SKU de cada
                variante.
              </p>
            </div>
            <div class="flex items-center gap-2">
              <Badge variant="primary"
                >{product.variant_count ?? product.variants?.length ?? 0} variantes</Badge
              >
              <Button
                size="sm"
                variant="secondary"
                onclick={() => product && goto(`/products/${product.id_product}/variants`)}
                >Gestionar</Button
              >
            </div>
          </div>
          {#if product.variant_attributes?.length}
            <div class="mb-4 flex flex-wrap gap-2">
              {#each product.variant_attributes as attribute (attribute.id)}
                <span
                  class="rounded-full border border-border px-2.5 py-1 text-xs text-foreground-muted"
                  >{attribute.name}: {attribute.values
                    .filter((value) => value.is_active)
                    .map((value) => value.label)
                    .join(', ')}</span
                >
              {/each}
            </div>
          {/if}
          <div class="overflow-x-auto rounded-lg border border-border">
            <table class="w-full min-w-[640px] text-sm">
              <thead
                class="border-b border-border bg-surface-muted/30 text-left text-xs text-foreground-muted"
                ><tr
                  ><th class="px-3 py-2">Imagen</th><th class="px-3 py-2">SKU</th><th
                    class="px-3 py-2">Combinación</th
                  ><th class="px-3 py-2">Estado</th><th class="px-3 py-2">Identificadores</th><th class="px-3 py-2">Acciones</th></tr
                ></thead
              >
              <tbody class="divide-y divide-border">
                {#each product.variants ?? [] as variant (variant.id)}
                  <tr>
                    <td class="px-3 py-2">
                      {#if variant.image?.url}
                        <img
                          src={variant.image.url}
                          alt={variant.display_name}
                          loading="lazy"
                          referrerpolicy="no-referrer"
                          class="h-10 w-10 rounded-md border border-border object-cover"
                        />
                      {:else}
                        <span
                          class="flex h-10 w-10 items-center justify-center rounded-md border border-border bg-surface-muted text-xs text-foreground-subtle"
                          aria-label="Sin imagen">—</span
                        >
                      {/if}
                    </td>
                    <td class="px-3 py-2 font-mono text-foreground"
                      >{variant.sku}
                      <div class="font-sans text-xs text-foreground-muted">
                        {variant.name_override || variant.display_name}
                      </div></td
                    >
                    <td class="px-3 py-2 text-foreground-muted"
                      >{variant.values
                        .map((value) => `${value.attribute_code}: ${value.label}`)
                        .join(' · ')}</td
                    >
                    <td class="px-3 py-2 text-foreground-muted">{variant.lifecycle_status}</td>
                    <td class="px-3 py-2 text-foreground-muted"
                      >{variant.identifiers.length || '—'}</td
                    >
                    <td class="whitespace-nowrap px-3 py-2">
                      <a
                        class="text-xs font-medium text-primary hover:underline"
                        href={`/products/${product.id_product}/variants/${variant.id}/edit`}
                      >Editar variante</a>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </Card>
      {/if}

      <Card class="p-6">
        <div class="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 class="text-sm font-semibold text-foreground">Proveedores vinculados</h3>
            <p class="mt-1 text-xs text-foreground-muted">Relaciones de abastecimiento actuales.</p>
          </div>
          {#if permissions.hasPermission('products:suppliers')}<Badge variant="primary"
              >Gestionable desde Editar</Badge
            >{/if}
        </div>
        {#if product.supplier_links?.length}
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="border-b border-border"
                ><tr
                  ><th class="px-3 py-2 text-left text-xs text-foreground-muted">Proveedor</th><th
                    class="px-3 py-2 text-left text-xs text-foreground-muted">Código</th
                  ><th class="px-3 py-2 text-left text-xs text-foreground-muted">Entrega</th><th
                    class="px-3 py-2 text-left text-xs text-foreground-muted">Estado</th
                  ></tr
                ></thead
              ><tbody class="divide-y divide-border"
                >{#each product.supplier_links as relation (relation.id)}<tr
                    ><td class="px-3 py-2 text-foreground"
                      >#{relation.supplier_id}{#if relation.is_preferred}<span class="ml-2"
                          ><Badge variant="success">Preferido</Badge></span
                        >{/if}</td
                    ><td class="px-3 py-2 text-foreground-muted"
                      >{relation.supplier_product_code || '—'}</td
                    ><td class="px-3 py-2 text-foreground-muted"
                      >{relation.lead_time_days != null
                        ? `${relation.lead_time_days} días`
                        : '—'}</td
                    ><td class="px-3 py-2 text-foreground-muted"
                      >{relation.status === 'active' ? 'Activo' : 'Inactivo'}</td
                    ></tr
                  >{/each}</tbody
              >
            </table>
          </div>
        {:else}<div
            class="rounded-xl border border-dashed border-border p-8 text-center text-sm text-foreground-muted"
          >
            Todavía no hay proveedores vinculados.
          </div>{/if}
      </Card>

      <Card class="p-6">
        <div class="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 class="text-sm font-semibold text-foreground">Galería del producto</h3>
            <p class="mt-1 text-xs text-foreground-muted">
              {product.images.length
                ? `${product.images.length} imagen(es) registrada(s)`
                : 'No hay imágenes registradas.'}
            </p>
          </div>
          {#if cover}<Badge variant="primary">Portada definida</Badge>{/if}
        </div>
        {#if product.images.length}
          <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {#each product.images as image (image.id)}
              <figure class="overflow-hidden rounded-xl border border-border bg-surface-muted">
                <div class="aspect-square">
                  {#if !imageErrors[image.id]}<img
                      src={image.url}
                      alt={image.alt_text || product.name}
                      loading="lazy"
                      referrerpolicy="no-referrer"
                      class="h-full w-full object-cover"
                      onerror={() => handleImageError(image.id)}
                    />{:else}<div
                      class="flex h-full items-center justify-center p-3 text-center text-xs text-foreground-subtle"
                    >
                      No se pudo cargar la imagen
                    </div>{/if}
                </div>
                <figcaption
                  class="flex items-center justify-between gap-2 px-2.5 py-2 text-[11px] text-foreground-muted"
                >
                  <span class="truncate">{image.alt_text || `Imagen ${image.position + 1}`}</span
                  >{#if image.is_cover}<span class="shrink-0 text-primary">Portada</span>{/if}
                </figcaption>
              </figure>
            {/each}
          </div>
        {:else}
          <div
            class="rounded-xl border border-dashed border-border p-10 text-center text-sm text-foreground-muted"
          >
            Agrega una portada o imágenes adicionales desde Editar producto.
          </div>
        {/if}
      </Card>
    </div>
  {/if}
</div>
