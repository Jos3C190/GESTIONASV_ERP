<script lang="ts">
  import { untrack } from 'svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import { catalogApi } from '$lib/api/catalog';
  import type { Category, Product, SubCategory, Unit } from '$lib/types/catalog';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';

  // Svelte 5 Runes State
  let products = $state<Product[]>([]);
  let categories = $state<Category[]>([]);
  let subCategories = $state<SubCategory[]>([]);
  let units = $state<Unit[]>([]);
  let loading = $state<boolean>(true);
  let errorMsg = $state<string | null>(null);
  let successMsg = $state<string | null>(null);

  // Filters
  let selectedCategory = $state<number | undefined>(undefined);
  let selectedSubCategory = $state<number | undefined>(undefined);

  // Pagination
  let page = $state<number>(1);
  let totalPages = $state<number>(1);
  let totalItems = $state<number>(0);

  // KPI Stats
  let kpiTotal = $state<number>(0);
  let kpiActive = $state<number>(0);
  let kpiCategoriesCount = $state<number>(0);
  let kpiInactive = $state<number>(0);

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

  let dataGeneration = 0;

  // Derived filtered subcategories for header filter & form
  let filteredSubCategories = $derived(
    selectedCategory ? subCategories.filter((s) => s.id_category === selectedCategory) : subCategories
  );

  let formFilteredSubCategories = $derived(
    formCategory ? subCategories.filter((s) => s.id_category === formCategory) : []
  );

  async function loadData() {
    const generation = ++dataGeneration;
    loading = true;
    errorMsg = null;
    try {
      const [catsRes, subsRes, unitsRes, prodsRes, stats] = await Promise.all([
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

      categories = catsRes;
      subCategories = subsRes;
      units = unitsRes;
      products = prodsRes.items;
      totalItems = prodsRes.meta.total;
      totalPages = prodsRes.meta.pages;

      // KPIs
      kpiTotal = stats.total;
      kpiActive = stats.active;
      kpiInactive = stats.inactive;
      kpiCategoriesCount = stats.categories;
    } catch (err: unknown) {
      if (generation !== dataGeneration) return;
      errorMsg = err instanceof Error ? err.message : 'Error al cargar productos';
    } finally {
      if (generation === dataGeneration) loading = false;
    }
  }

  function goToPage(p: number) {
    if (p < 1 || p > totalPages) return;
    page = p;
    loadData();
  }

  $effect(() => {
    const _q = globalSearch.query;
    const _c = selectedCategory;
    const _sc = selectedSubCategory;
    untrack(() => {
      page = 1;
      loadData();
    });
  });

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
    errorMsg = null;
    successMsg = null;
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
          is_active: formIsActive
        });
        successMsg = 'Producto actualizado exitosamente.';
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
          description: formDescription
        });
        successMsg = 'Producto creado exitosamente.';
      }
      showModal = false;
      await loadData();
    } catch (err: unknown) {
      errorMsg = err instanceof Error ? err.message : 'Error al guardar el producto';
    } finally {
      saving = false;
    }
  }

  function toggleProductStatus(prod: Product) {
    const actionText = prod.is_active ? 'desactivar' : 'activar';
    confirmation.request({
      kind: prod.is_active ? 'deactivate' : 'deactivate',
      title: `${prod.is_active ? 'Desactivar' : 'Activar'} producto`,
      description: `¿Está seguro de que desea ${actionText} el producto "${prod.name}" (SKU: ${prod.sku})?`,
      resourceName: prod.name,
      confirmLabel: prod.is_active ? 'Desactivar' : 'Activar',
      execute: async () => {
        try {
          await catalogApi.updateProduct(prod.id_product, { is_active: !prod.is_active });
          successMsg = `Producto ${prod.is_active ? 'desactivado' : 'activado'} correctamente.`;
          await loadData();
        } catch (err: unknown) {
          errorMsg = err instanceof Error ? err.message : 'Error al cambiar estado del producto';
        }
      }
    });
  }

  function menuItems(prod: Product): KebabItem[] {
    const items: KebabItem[] = [];
    if (permissions.hasPermission('products:manage')) {
      items.push({
        id: 'edit',
        label: 'Editar',
        icon: 'edit',
        onClick: () => openEditModal(prod)
      });
      items.push({
        id: 'toggle-status',
        label: prod.is_active ? 'Desactivar' : 'Activar',
        icon: prod.is_active ? 'delete' : 'edit',
        variant: prod.is_active ? 'danger' : 'default',
        onClick: () => toggleProductStatus(prod)
      });
    }
    return items;
  }

  function getCategoryName(catId: number): string {
    return categories.find((c) => c.id_category === catId)?.name || '—';
  }

  function getUnitName(unitId: number): string {
    return units.find((u) => u.id_unit === unitId)?.name || '—';
  }

  // Ring geometry calculation
  const ringR = 16;
  const ringC = 2 * Math.PI * ringR;
  let ringOffset = $derived(kpiTotal > 0 ? ringC - (kpiActive / kpiTotal) * ringC : ringC);
  let activeRatio = $derived(kpiTotal > 0 ? Math.round((kpiActive / kpiTotal) * 100) : 0);
</script>

<svelte:head><title>Catálogo de Productos — ERP System</title></svelte:head>

<div class="p-6 md:p-8">
  <!-- Header -->
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">
      {loading ? 'Cargando...' : `${totalItems} producto(s)`}
    </p>
    <div class="flex items-center gap-2">
      <select
        bind:value={selectedCategory}
        onchange={() => {
          selectedSubCategory = undefined;
          page = 1;
        }}
        class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
      >
        <option value={undefined}>Todas las categorías</option>
        {#each categories as cat}
          <option value={cat.id_category}>{cat.name}</option>
        {/each}
      </select>

      {#if selectedCategory}
        <select
          bind:value={selectedSubCategory}
          onchange={() => {
            page = 1;
          }}
          class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
        >
          <option value={undefined}>Todas las subcategorías</option>
          {#each filteredSubCategories as sub}
            <option value={sub.id_sub_category}>{sub.name}</option>
          {/each}
        </select>
      {/if}

      {#if permissions.hasPermission('products:manage')}
        <Button size="sm" onclick={openCreateModal}>
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
          Crear
        </Button>
      {/if}
    </div>
  </div>

  <!-- KPI CARDS GRID -->
  <div class="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
    <!-- KPI 1: Total Productos -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Total productos</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            ><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {#if loading}<span class="inline-block h-7 w-16 rounded skeleton"></span>{:else}{kpiTotal}{/if}
        </div>
        <p class="text-[11px] text-foreground-subtle mt-1">Registrados en inventario</p>
      </div>
    </div>

    <!-- KPI 2: Productos Activos -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Activos</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-success/10 text-success">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            ><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {#if loading}<span class="inline-block h-7 w-10 rounded skeleton"></span>{:else}{kpiActive}{/if}
        </div>
        <p class="text-[11px] text-foreground-subtle mt-1">Disponibles en el catálogo</p>
      </div>
    </div>

    <!-- KPI 3: Categorías -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Categorías</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-warning/10 text-warning">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            ><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" /><line x1="7" y1="7" x2="7.01" y2="7" /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {#if loading}<span class="inline-block h-7 w-8 rounded skeleton"></span>{:else}{kpiCategoriesCount}{/if}
        </div>
        <p class="text-[11px] text-foreground-subtle mt-1">Líneas de producto</p>
      </div>
    </div>

    <!-- KPI 4: Inactivos + Mini Ring -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Inactivos</span
        >
        <div class="font-mono text-lg font-bold text-foreground">
          {#if loading}<span class="inline-block h-5 w-12 rounded skeleton"></span>{:else}{kpiInactive}
            <span class="text-xs font-normal text-foreground-subtle">/ {kpiTotal}</span>{/if}
        </div>
      </div>
      <div class="flex items-center gap-3">
        <svg
          width="40"
          height="40"
          viewBox="0 0 40 40"
          class="-rotate-90 flex-none"
          aria-hidden="true"
        >
          <circle
            cx="20"
            cy="20"
            r={ringR}
            fill="none"
            stroke="rgb(var(--border))"
            stroke-width="4.5"
          />
          <circle
            cx="20"
            cy="20"
            r={ringR}
            fill="none"
            stroke="rgb(var(--primary))"
            stroke-width="4.5"
            stroke-dasharray={ringC.toFixed(1)}
            stroke-dashoffset={ringOffset.toFixed(1)}
            stroke-linecap="round"
            class="transition-all duration-700 ease-out"
          />
        </svg>
        <div class="text-[11px] space-y-0.5 text-foreground-muted">
          <p><strong class="font-semibold text-foreground">{activeRatio}%</strong> activos</p>
          <p>
            <strong class="font-semibold text-foreground-subtle">{kpiInactive}</strong> inactivos
          </p>
        </div>
      </div>
    </div>
  </div>

  {#if errorMsg}
    <div class="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">
      {errorMsg}
    </div>
  {/if}
  {#if successMsg}
    <div class="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success" role="status">
      {successMsg}
    </div>
  {/if}

  <!-- Data Table -->
  <Card class="overflow-hidden p-0">
    {#if loading}
      <div class="flex items-center justify-center py-16">
        <p class="text-sm text-foreground-muted">Cargando...</p>
      </div>
    {:else if products.length === 0}
      <div class="flex flex-col items-center justify-center py-16">
        <p class="text-sm text-foreground-muted">No se encontraron productos.</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="border-b border-border bg-surface-muted">
            <tr>
              <th class="px-4 py-3 text-left font-semibold text-foreground">SKU</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Producto</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Categoría</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Unid. Compra</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Unid. Venta</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Estado</th>
              <th class="px-2 py-3 text-center font-semibold text-foreground w-11"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each products as prod (prod.id_product)}
              <tr class="hover:bg-surface-muted">
                <td class="px-4 py-3 font-mono text-foreground">{prod.sku}</td>
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
                  <span
                    class="{prod.is_active ? 'badge-success' : 'badge-neutral'} inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"
                  >
                    <span class="h-1.5 w-1.5 rounded-full bg-current"></span>
                    {prod.is_active ? 'Activo' : 'Inactivo'}
                  </span>
                </td>
                <td class="px-2 py-3 text-center">
                  <KebabMenu items={menuItems(prod)} />
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </Card>

  <!-- Pagination -->
  {#if totalPages > 1}
    <div class="mt-4 flex items-center justify-between">
      <p class="text-xs text-foreground-muted">Página {page} de {totalPages}</p>
      <div class="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          onclick={() => goToPage(page - 1)}
          disabled={page <= 1}>Anterior</Button
        >
        <Button
          variant="secondary"
          size="sm"
          onclick={() => goToPage(page + 1)}
          disabled={page >= totalPages}>Siguiente</Button
        >
      </div>
    </div>
  {/if}

  <!-- Modal Form -->
  {#if showModal}
    <Modal open={showModal} title={isEditing ? 'Editar Producto' : 'Nuevo Producto'} onclose={() => (showModal = false)}>
      <form onsubmit={handleSave} class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="sku-field" class="block text-xs font-medium text-foreground-muted mb-1">SKU *</label>
            <input id="sku-field" type="text" required bind:value={formSku} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" />
          </div>
          <div>
            <label for="name-field" class="block text-xs font-medium text-foreground-muted mb-1">Nombre del Producto *</label>
            <input id="name-field" type="text" required bind:value={formName} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" />
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="cat-field" class="block text-xs font-medium text-foreground-muted mb-1">Categoría *</label>
            <select id="cat-field" required bind:value={formCategory} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none">
              {#each categories as cat}
                <option value={cat.id_category}>{cat.name}</option>
              {/each}
            </select>
          </div>
          <div>
            <label for="subcat-field" class="block text-xs font-medium text-foreground-muted mb-1">Subcategoría</label>
            <select id="subcat-field" bind:value={formSubCategory} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none">
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
            <select id="punit-field" required bind:value={formPurchaseUnit} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none">
              {#each units as unit}
                <option value={unit.id_unit}>{unit.name} ({unit.type})</option>
              {/each}
            </select>
          </div>
          <div>
            <label for="sunit-field" class="block text-xs font-medium text-foreground-muted mb-1">Unidad de Venta *</label>
            <select id="sunit-field" required bind:value={formSaleUnit} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none">
              {#each units as unit}
                <option value={unit.id_unit}>{unit.name} ({unit.type})</option>
              {/each}
            </select>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label for="orig-field" class="block text-xs font-medium text-foreground-muted mb-1">Código Original</label>
            <input id="orig-field" type="text" bind:value={formOriginalCode} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" />
          </div>
          <div>
            <label for="int-field" class="block text-xs font-medium text-foreground-muted mb-1">Código Interno</label>
            <input id="int-field" type="text" bind:value={formInternalCode} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" />
          </div>
          <div>
            <label for="pres-field" class="block text-xs font-medium text-foreground-muted mb-1">Presentación</label>
            <input id="pres-field" type="text" bind:value={formPresentation} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" placeholder="Ej: Ck 50lb" />
          </div>
        </div>

        <div>
          <label for="desc-field" class="block text-xs font-medium text-foreground-muted mb-1">Descripción</label>
          <textarea id="desc-field" rows="2" bind:value={formDescription} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"></textarea>
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
