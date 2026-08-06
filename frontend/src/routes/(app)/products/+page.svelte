<script lang="ts">
  import { onMount } from 'svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import Callout from '$lib/components/ui/Callout.svelte';
  import { catalogApi } from '$lib/api/catalog';
  import type { Category, Product, SubCategory, Unit } from '$lib/types/catalog';

  // Svelte 5 Runes State
  let products = $state<Product[]>([]);
  let categories = $state<Category[]>([]);
  let subCategories = $state<SubCategory[]>([]);
  let units = $state<Unit[]>([]);
  let loading = $state<boolean>(true);
  let errorMsg = $state<string | null>(null);

  // Search & Filter state
  let search = $state<string>('');
  let selectedCategory = $state<number | undefined>(undefined);
  let selectedSubCategory = $state<number | undefined>(undefined);

  // Pagination state
  let page = $state<number>(1);
  let totalPages = $state<number>(1);
  let totalItems = $state<number>(0);

  // Modal State
  let showModal = $state<boolean>(false);
  let isEditing = $state<boolean>(false);
  let editingId = $state<number | null>(null);
  let saving = $state<boolean>(false);

  // Form State
  let formSku = $state<string>('');
  let formName = $state<string>('');
  let formCategory = $state<number | undefined>(undefined);
  let formSubCategory = $state<number | undefined>(undefined);
  let formPurchaseUnit = $state<number | undefined>(undefined);
  let formSaleUnit = $state<number | undefined>(undefined);
  let formOriginalCode = $state<string>('');
  let formInternalCode = $state<string>('');
  let formSize = $state<string>('');
  let formDimensions = $state<string>('');
  let formPresentation = $state<string>('');
  let formDescription = $state<string>('');
  let formIsActive = $state<boolean>(true);

  // Derived filtered subcategories for form
  let formFilteredSubCategories = $derived(
    formCategory ? subCategories.filter((s) => s.id_category === formCategory) : []
  );

  async function loadData() {
    loading = true;
    errorMsg = null;
    try {
      const [catsRes, subsRes, unitsRes, prodsRes] = await Promise.all([
        catalogApi.listCategories(true),
        catalogApi.listSubCategories(undefined, true),
        catalogApi.listUnits(true),
        catalogApi.listProducts({
          category_id: selectedCategory,
          sub_category_id: selectedSubCategory,
          search: search.trim() || undefined,
          page,
          size: 10,
        }),
      ]);
      categories = catsRes;
      subCategories = subsRes;
      units = unitsRes;
      products = prodsRes.items;
      totalItems = prodsRes.meta.total;
      totalPages = prodsRes.meta.pages;
    } catch (err: any) {
      errorMsg = err.message || 'Error al cargar productos';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadData();
  });

  function handleSearch(e: Event) {
    e.preventDefault();
    page = 1;
    loadData();
  }

  function openCreateModal() {
    isEditing = false;
    editingId = null;
    formSku = '';
    formName = '';
    formCategory = categories[0]?.id_category;
    formSubCategory = undefined;
    formPurchaseUnit = units[0]?.id_unit;
    formSaleUnit = units[0]?.id_unit;
    formOriginalCode = '';
    formInternalCode = '';
    formSize = '';
    formDimensions = '';
    formPresentation = '';
    formDescription = '';
    formIsActive = true;
    showModal = true;
  }

  function openEditModal(prod: Product) {
    isEditing = true;
    editingId = prod.id_product;
    formSku = prod.sku;
    formName = prod.name;
    formCategory = prod.id_category;
    formSubCategory = prod.id_sub_category ?? undefined;
    formPurchaseUnit = prod.purchase_unit;
    formSaleUnit = prod.sale_unit;
    formOriginalCode = prod.original_code ?? '';
    formInternalCode = prod.internal_code ?? '';
    formSize = prod.size ?? '';
    formDimensions = prod.dimensions ?? '';
    formPresentation = prod.presentation ?? '';
    formDescription = prod.description ?? '';
    formIsActive = prod.is_active;
    showModal = true;
  }

  async function handleSave(e: SubmitEvent) {
    e.preventDefault();
    if (!formCategory || !formPurchaseUnit || !formSaleUnit) return;
    saving = true;
    try {
      if (isEditing && editingId) {
        await catalogApi.updateProduct(editingId, {
          id_category: formCategory,
          id_sub_category: formSubCategory || null,
          sku: formSku,
          name: formName,
          purchase_unit: formPurchaseUnit,
          sale_unit: formSaleUnit,
          original_code: formOriginalCode,
          internal_code: formInternalCode,
          size: formSize,
          dimensions: formDimensions,
          presentation: formPresentation,
          description: formDescription,
          is_active: formIsActive,
        });
      } else {
        await catalogApi.createProduct({
          id_category: formCategory,
          id_sub_category: formSubCategory || null,
          sku: formSku,
          name: formName,
          purchase_unit: formPurchaseUnit,
          sale_unit: formSaleUnit,
          original_code: formOriginalCode,
          internal_code: formInternalCode,
          size: formSize,
          dimensions: formDimensions,
          presentation: formPresentation,
          description: formDescription,
        });
      }
      showModal = false;
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Error al guardar el producto');
    } finally {
      saving = false;
    }
  }

  function getCategoryName(catId: number): string {
    return categories.find((c) => c.id_category === catId)?.name || 'N/A';
  }

  function getUnitName(unitId: number): string {
    return units.find((u) => u.id_unit === unitId)?.name || 'N/A';
  }
</script>

<svelte:head><title>Catálogo de Productos — ERP System</title></svelte:head>

<div class="flex flex-col gap-6 p-6 animate-fade-scale">
  <!-- Page header -->
  <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
    <div>
      <h1 class="text-2xl font-bold text-foreground">Catálogo de Productos</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Administra los productos de inventario, SKU, categorías y unidades de medida.
      </p>
    </div>
    <div class="flex items-center gap-3">
      <Button variant="primary" onclick={openCreateModal}>
        <svg class="h-4 w-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        Nuevo Producto
      </Button>
    </div>
  </div>

  <!-- Filters & Search Bar -->
  <Card class="p-4">
    <form onsubmit={handleSearch} class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="md:col-span-2">
        <input
          type="text"
          placeholder="Buscar por SKU, Nombre o Código..."
          bind:value={search}
          class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
        />
      </div>
      <div>
        <select
          bind:value={selectedCategory}
          onchange={handleSearch}
          class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
        >
          <option value={undefined}>Todas las categorías</option>
          {#each categories as cat}
            <option value={cat.id_category}>{cat.name}</option>
          {/each}
        </select>
      </div>
      <div class="flex gap-2">
        <Button type="submit" variant="secondary" class="w-full">Filtrar</Button>
      </div>
    </form>
  </Card>

  {#if errorMsg}
    <Callout variant="warning">{errorMsg}</Callout>
  {/if}

  <!-- Data Table -->
  <Card class="overflow-hidden p-0">
    {#if loading}
      <div class="p-8 space-y-4">
        {#each Array(5) as _}
          <div class="h-8 bg-surface-muted rounded animate-pulse"></div>
        {/each}
      </div>
    {:else if products.length === 0}
      <div class="flex flex-col items-center justify-center p-12 text-center">
        <div class="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 mb-4">
          <svg class="h-8 w-8 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
        </div>
        <h3 class="text-lg font-semibold text-foreground">No hay productos encontrados</h3>
        <p class="text-sm text-foreground-muted mt-1">Intenta ajustar la búsqueda o agrega un nuevo producto.</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm text-foreground">
          <thead class="bg-surface-muted text-xs uppercase text-foreground-muted border-b border-border">
            <tr>
              <th class="px-4 py-3">SKU</th>
              <th class="px-4 py-3">Producto</th>
              <th class="px-4 py-3">Categoría</th>
              <th class="px-4 py-3">Unid. Compra</th>
              <th class="px-4 py-3">Unid. Venta</th>
              <th class="px-4 py-3">Estado</th>
              <th class="px-4 py-3 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each products as prod}
              <tr class="hover:bg-surface-muted/50 transition-colors">
                <td class="px-4 py-3 font-mono font-semibold text-xs text-primary">{prod.sku}</td>
                <td class="px-4 py-3">
                  <div class="font-medium text-foreground">{prod.name}</div>
                  {#if prod.internal_code || prod.presentation}
                    <div class="text-xs text-foreground-muted">
                      {prod.internal_code ? `Cód. Int: ${prod.internal_code}` : ''} {prod.presentation ? `| Pres: ${prod.presentation}` : ''}
                    </div>
                  {/if}
                </td>
                <td class="px-4 py-3 text-foreground-muted">{getCategoryName(prod.id_category)}</td>
                <td class="px-4 py-3 text-foreground-muted">{getUnitName(prod.purchase_unit)}</td>
                <td class="px-4 py-3 text-foreground-muted">{getUnitName(prod.sale_unit)}</td>
                <td class="px-4 py-3">
                  <Badge variant={prod.is_active ? 'success' : 'neutral'}>
                    {prod.is_active ? 'Activo' : 'Inactivo'}
                  </Badge>
                </td>
                <td class="px-4 py-3 text-right">
                  <Button variant="ghost" size="sm" onclick={() => openEditModal(prod)}>Editar</Button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <!-- Pagination Footer -->
      <div class="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-foreground-muted">
        <div>Mostrando {products.length} de {totalItems} productos</div>
        <div class="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={page <= 1}
            onclick={() => { page--; loadData(); }}
          >
            Anterior
          </Button>
          <span class="flex items-center px-2">Página {page} de {totalPages || 1}</span>
          <Button
            variant="secondary"
            size="sm"
            disabled={page >= totalPages}
            onclick={() => { page++; loadData(); }}
          >
            Siguiente
          </Button>
        </div>
      </div>
    {/if}
  </Card>

  <!-- Modal Form -->
  {#if showModal}
    <Modal open={showModal} title={isEditing ? 'Editar Producto' : 'Nuevo Producto'} onclose={() => (showModal = false)}>
      <form onsubmit={handleSave} class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="sku-field" class="block text-xs font-medium text-foreground-muted mb-1">SKU *</label>
            <input id="sku-field" type="text" required bind:value={formSku} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" />
          </div>
          <div>
            <label for="name-field" class="block text-xs font-medium text-foreground-muted mb-1">Nombre del Producto *</label>
            <input id="name-field" type="text" required bind:value={formName} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" />
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="cat-field" class="block text-xs font-medium text-foreground-muted mb-1">Categoría *</label>
            <select id="cat-field" required bind:value={formCategory} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
              {#each categories as cat}
                <option value={cat.id_category}>{cat.name}</option>
              {/each}
            </select>
          </div>
          <div>
            <label for="subcat-field" class="block text-xs font-medium text-foreground-muted mb-1">Subcategoría</label>
            <select id="subcat-field" bind:value={formSubCategory} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
              <option value={undefined}>-- Sin Subcategoría --</option>
              {#each formFilteredSubCategories as sub}
                <option value={sub.id_sub_category}>{sub.name}</option>
              {/each}
            </select>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="punit-field" class="block text-xs font-medium text-foreground-muted mb-1">Unidad de Compra *</label>
            <select id="punit-field" required bind:value={formPurchaseUnit} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
              {#each units as unit}
                <option value={unit.id_unit}>{unit.name} ({unit.type})</option>
              {/each}
            </select>
          </div>
          <div>
            <label for="sunit-field" class="block text-xs font-medium text-foreground-muted mb-1">Unidad de Venta *</label>
            <select id="sunit-field" required bind:value={formSaleUnit} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
              {#each units as unit}
                <option value={unit.id_unit}>{unit.name} ({unit.type})</option>
              {/each}
            </select>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label for="orig-field" class="block text-xs font-medium text-foreground-muted mb-1">Código Original</label>
            <input id="orig-field" type="text" bind:value={formOriginalCode} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" />
          </div>
          <div>
            <label for="int-field" class="block text-xs font-medium text-foreground-muted mb-1">Código Interno</label>
            <input id="int-field" type="text" bind:value={formInternalCode} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" />
          </div>
          <div>
            <label for="pres-field" class="block text-xs font-medium text-foreground-muted mb-1">Presentación</label>
            <input id="pres-field" type="text" bind:value={formPresentation} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="Ej: Ck 50lb" />
          </div>
        </div>

        <div>
          <label for="desc-field" class="block text-xs font-medium text-foreground-muted mb-1">Descripción</label>
          <textarea id="desc-field" rows="2" bind:value={formDescription} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"></textarea>
        </div>

        {#if isEditing}
          <div class="flex items-center gap-2">
            <input type="checkbox" id="is_active" bind:checked={formIsActive} class="rounded border-border text-primary" />
            <label for="is_active" class="text-sm font-medium text-foreground">Producto Activo</label>
          </div>
        {/if}

        <div class="flex justify-end gap-3 pt-4 border-t border-border">
          <Button type="button" variant="secondary" onclick={() => (showModal = false)}>Cancelar</Button>
          <Button type="submit" variant="primary" disabled={saving}>
            {saving ? 'Guardando...' : 'Guardar Producto'}
          </Button>
        </div>
      </form>
    </Modal>
  {/if}
</div>
