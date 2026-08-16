<script lang="ts">
  import { untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import type { Category, Product, SubCategory, Unit } from '$lib/types/catalog';
  import Card from '$lib/components/ui/Card.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';

  let products = $state<Product[]>([]);
  let categories = $state<Category[]>([]);
  let subCategories = $state<SubCategory[]>([]);
  let units = $state<Unit[]>([]);
  let loading = $state(true);
  let errorMsg = $state<string | null>(null);
  let successMsg = $state<string | null>(null);
  let selectedCategory = $state<number | undefined>(undefined);
  let selectedSubCategory = $state<number | undefined>(undefined);
  let page = $state(1);
  let totalPages = $state(1);
  let totalItems = $state(0);
  let kpiTotal = $state(0);
  let kpiActive = $state(0);
  let kpiInactive = $state(0);
  let kpiCategories = $state(0);
  let dataGeneration = 0;

  let filteredSubCategories = $derived(
    selectedCategory
      ? subCategories.filter((item) => item.id_category === selectedCategory)
      : subCategories
  );
  let activeRatio = $derived(kpiTotal > 0 ? Math.round((kpiActive / kpiTotal) * 100) : 0);

  function categoryName(id: number) {
    return categories.find((item) => item.id_category === id)?.name ?? '—';
  }

  async function loadData() {
    const generation = ++dataGeneration;
    loading = true;
    errorMsg = null;
    try {
      const [categoryData, subCategoryData, unitData, productPage, stats] = await Promise.all([
        catalogApi.listCategories(true),
        catalogApi.listSubCategories(undefined, true),
        catalogApi.listUnits(true),
        catalogApi.listProducts({
          category_id: selectedCategory,
          sub_category_id: selectedSubCategory,
          search: globalSearch.query.trim() || undefined,
          active_only: false,
          page: untrack(() => page),
          size: 10
        }),
        catalogApi.productStats()
      ]);
      if (generation !== dataGeneration) return;
      categories = categoryData;
      subCategories = subCategoryData;
      units = unitData;
      products = productPage.items;
      totalItems = productPage.meta.total;
      totalPages = productPage.meta.pages;
      kpiTotal = stats.total;
      kpiActive = stats.active;
      kpiInactive = stats.inactive;
      kpiCategories = stats.categories;
    } catch (err: unknown) {
      if (generation !== dataGeneration) return;
      errorMsg = err instanceof Error ? err.message : 'No se pudo cargar el catálogo.';
    } finally {
      if (generation === dataGeneration) loading = false;
    }
  }

  function goToPage(next: number) {
    if (next < 1 || next > totalPages) return;
    page = next;
    void loadData();
  }

  $effect(() => {
    const query = globalSearch.query;
    const category = selectedCategory;
    const subCategory = selectedSubCategory;
    untrack(() => {
      void query;
      void category;
      void subCategory;
      page = 1;
      void loadData();
    });
  });

  function toggleProductStatus(product: Product) {
    confirmation.request({
      kind: 'deactivate',
      title: `${product.is_active ? 'Desactivar' : 'Activar'} producto`,
      description: `¿Desea ${product.is_active ? 'desactivar' : 'activar'} "${product.name}"?`,
      resourceName: product.name,
      confirmLabel: product.is_active ? 'Desactivar' : 'Activar',
      execute: async () => {
        try {
          await catalogApi.updateProduct(product.id_product, { is_active: !product.is_active });
          successMsg = `Producto ${product.is_active ? 'desactivado' : 'activado'} correctamente.`;
          await loadData();
        } catch (err: unknown) {
          errorMsg = err instanceof Error ? err.message : 'No se pudo cambiar el estado.';
        }
      }
    });
  }

  function deleteProduct(product: Product) {
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar producto',
      description:
        'El producto quedará en la Papelera y dejará de mostrarse en el catálogo operativo.',
      resourceName: `${product.name} · ${product.sku}`,
      confirmLabel: 'Eliminar producto',
      requireReason: true,
      execute: async (reason) => {
        if (!reason) throw new Error('Indique el motivo de eliminación.');
        await api.lifecycle.delete('products', String(product.id_product), reason);
        successMsg = 'Producto enviado a la Papelera.';
        await loadData();
      }
    });
  }

  function menuItems(product: Product): KebabItem[] {
    const items: KebabItem[] = [
      {
        id: 'detail',
        label: 'Ver detalle',
        icon: 'detail',
        onClick: () => void goto(`/products/${product.id_product}`)
      }
    ];
    if (permissions.hasPermission('products:manage')) {
      items.push({
        id: 'edit',
        label: 'Editar',
        icon: 'edit',
        onClick: () => void goto(`/products/${product.id_product}/edit`)
      });
      items.push({
        id: 'toggle-status',
        label: product.is_active ? 'Desactivar' : 'Activar',
        icon: product.is_active ? 'delete' : 'power',
        variant: product.is_active ? 'danger' : 'default',
        onClick: () => toggleProductStatus(product)
      });
    }
    if (permissions.hasPermission('products:delete')) {
      items.push({
        id: 'delete',
        label: 'Eliminar',
        icon: 'delete',
        variant: 'danger',
        onClick: () => deleteProduct(product)
      });
    }
    return items;
  }
</script>

<svelte:head><title>Catálogo de productos — GestionaSV</title></svelte:head>

<div class="p-6 md:p-8">
  <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="text-xs font-medium uppercase tracking-wider text-foreground-subtle">Inventario</p>
      <h1 class="mt-1 text-2xl font-bold text-foreground">Catálogo de productos</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Identidad comercial, unidades e imágenes de tus productos.
      </p>
    </div>
    <div class="flex items-center gap-2">
      {#if permissions.hasPermission('products:manage')}
        <Button size="sm" onclick={() => goto('/products/new')}>
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg
          >
          Nuevo producto
        </Button>
      {/if}
    </div>
  </div>

  <div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
    <Card class="p-5"
      ><p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
        Total productos
      </p>
      <p class="mt-2 font-mono text-2xl font-bold tabular-nums text-foreground">
        {loading ? '—' : kpiTotal}
      </p>
      <p class="mt-1 text-xs text-foreground-muted">Registrados en el catálogo</p></Card
    >
    <Card class="p-5"
      ><p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">Activos</p>
      <p class="mt-2 font-mono text-2xl font-bold tabular-nums text-success">
        {loading ? '—' : kpiActive}
      </p>
      <p class="mt-1 text-xs text-foreground-muted">{activeRatio}% del catálogo</p></Card
    >
    <Card class="p-5"
      ><p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
        Categorías
      </p>
      <p class="mt-2 font-mono text-2xl font-bold tabular-nums text-foreground">
        {loading ? '—' : kpiCategories}
      </p>
      <p class="mt-1 text-xs text-foreground-muted">Líneas disponibles</p></Card
    >
    <Card class="p-5"
      ><p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
        Inactivos
      </p>
      <p class="mt-2 font-mono text-2xl font-bold tabular-nums text-warning">
        {loading ? '—' : kpiInactive}
      </p>
      <p class="mt-1 text-xs text-foreground-muted">Requieren revisión</p></Card
    >
  </div>

  <Card class="mb-5 p-4">
    <div class="grid gap-3 md:grid-cols-[minmax(0,1.6fr)_minmax(180px,1fr)_minmax(180px,1fr)]">
      <div class="relative">
        <svg
          class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg
        ><input
          aria-label="Buscar productos"
          placeholder="Buscar por SKU, nombre o código..."
          value={globalSearch.query}
          oninput={(event) =>
            globalSearch.setDebounced((event.currentTarget as HTMLInputElement).value)}
          class="h-10 w-full rounded-lg border border-border bg-surface px-3 pl-9 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>
      <select
        aria-label="Filtrar por categoría"
        bind:value={selectedCategory}
        onchange={() => {
          selectedSubCategory = undefined;
          page = 1;
        }}
        class="h-10 rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
        ><option value={undefined}>Todas las categorías</option
        >{#each categories as category}<option value={category.id_category}>{category.name}</option
          >{/each}</select
      >
      <select
        aria-label="Filtrar por subcategoría"
        bind:value={selectedSubCategory}
        disabled={!selectedCategory}
        onchange={() => {
          page = 1;
        }}
        class="h-10 rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none"
        ><option value={undefined}>Todas las subcategorías</option
        >{#each filteredSubCategories as item}<option value={item.id_sub_category}
            >{item.name}</option
          >{/each}</select
      >
    </div>
  </Card>

  {#if errorMsg}<div
      class="mb-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {errorMsg}
    </div>{/if}
  {#if successMsg}<div
      class="mb-4 rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-success"
      role="status"
    >
      {successMsg}
    </div>{/if}

  <Card class="overflow-hidden p-0">
    {#if loading}
      <div class="flex items-center justify-center py-20 text-sm text-foreground-muted">
        Cargando catálogo...
      </div>
    {:else if products.length === 0}
      <div class="flex flex-col items-center justify-center px-6 py-20 text-center">
        <div
          class="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            ><path d="m21 16-9 5-9-5V8l9-5 9 5v8Z" /><path d="m3 8 9 5 9-5M12 13v8" /></svg
          >
        </div>
        <h2 class="text-base font-semibold text-foreground">No hay productos para mostrar</h2>
        <p class="mt-1 max-w-md text-sm text-foreground-muted">
          Crea el primer producto o ajusta los filtros de búsqueda.
        </p>
        {#if permissions.hasPermission('products:manage')}<Button
            class="mt-5"
            size="sm"
            onclick={() => goto('/products/new')}>Crear primer producto</Button
          >{/if}
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full min-w-[760px] text-sm">
          <thead class="border-b border-border bg-surface-muted/40"
            ><tr
              ><th class="px-5 py-3 text-left font-semibold text-foreground">Producto</th><th
                class="px-5 py-3 text-left font-semibold text-foreground">Categoría</th
              ><th class="px-5 py-3 text-left font-semibold text-foreground">Unidades</th><th
                class="px-5 py-3 text-left font-semibold text-foreground">Estado</th
              ><th class="px-5 py-3 text-right font-semibold text-foreground">Acciones</th></tr
            ></thead
          ><tbody class="divide-y divide-border">
            {#each products as product (product.id_product)}
              <tr class="transition-colors hover:bg-surface-muted/30">
                <td class="px-5 py-3.5"
                  ><div class="flex items-center gap-3">
                    <a
                      href={`/products/${product.id_product}`}
                      class="flex h-11 w-11 flex-none items-center justify-center overflow-hidden rounded-xl border border-border bg-surface-muted text-primary hover:border-primary/50"
                      >{#if product.cover_image}<img
                          src={product.cover_image.url}
                          alt={product.cover_image.alt_text || product.name}
                          loading="lazy"
                          referrerpolicy="no-referrer"
                          class="h-full w-full object-cover"
                        />{:else}<svg
                          width="21"
                          height="21"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="1.5"
                          aria-hidden="true"
                          ><rect x="3" y="3" width="18" height="18" rx="3" /><circle
                            cx="8.5"
                            cy="8.5"
                            r="1.5"
                          /><path d="m21 15-5-5L5 21" /></svg
                        >{/if}</a
                    >
                    <div class="min-w-0">
                      <a
                        href={`/products/${product.id_product}`}
                        class="block truncate font-medium text-foreground hover:text-primary"
                        >{product.name}</a
                      >
                      <div class="mt-0.5 flex items-center gap-2 text-xs text-foreground-muted">
                        <span class="font-mono">{product.sku}</span
                        >{#if product.image_count > 1}<span
                            class="rounded-full bg-surface-muted px-1.5 py-0.5"
                            >+{product.image_count - 1}</span
                          >{/if}
                      </div>
                    </div>
                  </div></td
                >
                <td class="px-5 py-3.5 text-foreground-muted"
                  >{categoryName(product.id_category)}</td
                >
                <td class="px-5 py-3.5 text-xs text-foreground-muted"
                  ><span
                    >Compra {units.find((unit) => unit.id_unit === product.purchase_unit)?.name ??
                      `#${product.purchase_unit}`}</span
                  ><span class="mx-1 text-foreground-subtle">·</span><span
                    >Venta {units.find((unit) => unit.id_unit === product.sale_unit)?.name ??
                      `#${product.sale_unit}`}</span
                  ></td
                >
                <td class="px-5 py-3.5"
                  ><Badge variant={product.is_active ? 'success' : 'neutral'}
                    >{product.is_active ? 'Activo' : 'Inactivo'}</Badge
                  ></td
                >
                <td class="px-5 py-3.5 text-right"
                  ><KebabMenu
                    items={menuItems(product)}
                    ariaLabel={`Acciones de ${product.name}`}
                  /></td
                >
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div
        class="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3 text-xs text-foreground-muted"
      >
        <span>{totalItems} producto(s) · Página {page} de {totalPages}</span>
        <div class="flex items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={page <= 1}
            onclick={() => goToPage(page - 1)}>Anterior</Button
          ><Button
            size="sm"
            variant="secondary"
            disabled={page >= totalPages}
            onclick={() => goToPage(page + 1)}>Siguiente</Button
          >
        </div>
      </div>
    {/if}
  </Card>
</div>
