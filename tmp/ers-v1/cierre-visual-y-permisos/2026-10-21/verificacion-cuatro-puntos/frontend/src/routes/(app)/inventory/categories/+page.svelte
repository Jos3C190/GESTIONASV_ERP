<script lang="ts">
  import { onMount } from 'svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import Callout from '$lib/components/ui/Callout.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import { api, HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import type { Category, SubCategory } from '$lib/types/catalog';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { search as globalSearch } from '$lib/stores/search.svelte';

  // Svelte 5 Runes State
  let categories = $state<Category[]>([]);
  let subCategories = $state<SubCategory[]>([]);
  let loading = $state<boolean>(true);
  let errorMsg = $state<string | null>(null);

  // Category Modal State
  let showCatModal = $state<boolean>(false);
  let isEditingCat = $state<boolean>(false);
  let editingCatId = $state<number | null>(null);
  let formCatName = $state<string>('');
  let formCatDesc = $state<string>('');
  let formCatIsActive = $state<boolean>(true);
  let savingCat = $state<boolean>(false);

  // SubCategory Modal State
  let showSubModal = $state<boolean>(false);
  let isEditingSub = $state<boolean>(false);
  let editingSubId = $state<number | null>(null);
  let formSubCategoryId = $state<number | undefined>(undefined);
  let formSubName = $state<string>('');
  let formSubDesc = $state<string>('');
  let formSubIsActive = $state<boolean>(true);
  let savingSub = $state<boolean>(false);

  let filteredCategories = $derived.by(() => {
    const query = globalSearch.query.trim().toLocaleLowerCase('es-SV');
    if (!query) return categories;

    return categories.filter((category) => {
      const categoryMatches = [category.name, category.description]
        .filter(Boolean)
        .some((value) => value!.toLocaleLowerCase('es-SV').includes(query));
      const hasMatchingSubCategory = subCategories.some(
        (subCategory) =>
          subCategory.id_category === category.id_category &&
          [subCategory.name, subCategory.description]
            .filter(Boolean)
            .some((value) => value!.toLocaleLowerCase('es-SV').includes(query))
      );
      return categoryMatches || hasMatchingSubCategory;
    });
  });

  async function loadData() {
    loading = true;
    errorMsg = null;
    try {
      const [cats, subs] = await Promise.all([
        catalogApi.listCategories(false),
        catalogApi.listSubCategories(undefined, false),
      ]);
      categories = cats;
      subCategories = subs;
    } catch (err) {
      errorMsg = err instanceof HttpError ? err.message : 'Error al cargar categorías';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadData();
  });

  // Category actions
  function openCreateCategoryModal() {
    isEditingCat = false;
    editingCatId = null;
    formCatName = '';
    formCatDesc = '';
    formCatIsActive = true;
    showCatModal = true;
  }

  function openEditCategoryModal(cat: Category) {
    isEditingCat = true;
    editingCatId = cat.id_category;
    formCatName = cat.name;
    formCatDesc = cat.description ?? '';
    formCatIsActive = cat.is_active;
    showCatModal = true;
  }

  async function handleSaveCategory(e: SubmitEvent) {
    e.preventDefault();
    savingCat = true;
    try {
      if (isEditingCat && editingCatId) {
        await catalogApi.updateCategory(editingCatId, {
          name: formCatName,
          description: formCatDesc,
          is_active: formCatIsActive,
        });
      } else {
        await catalogApi.createCategory({
          name: formCatName,
          description: formCatDesc,
        });
      }
      showCatModal = false;
      await loadData();
    } catch (err) {
      errorMsg = err instanceof HttpError ? err.message : 'Error al guardar categoría';
    } finally {
      savingCat = false;
    }
  }

  // SubCategory actions
  function openCreateSubCategoryModal(catId?: number) {
    isEditingSub = false;
    editingSubId = null;
    formSubCategoryId = catId || categories[0]?.id_category;
    formSubName = '';
    formSubDesc = '';
    formSubIsActive = true;
    showSubModal = true;
  }

  function openEditSubCategoryModal(sub: SubCategory) {
    isEditingSub = true;
    editingSubId = sub.id_sub_category;
    formSubCategoryId = sub.id_category;
    formSubName = sub.name;
    formSubDesc = sub.description ?? '';
    formSubIsActive = sub.is_active;
    showSubModal = true;
  }

  async function handleSaveSubCategory(e: SubmitEvent) {
    e.preventDefault();
    if (!formSubCategoryId) return;
    savingSub = true;
    try {
      if (isEditingSub && editingSubId) {
        await catalogApi.updateSubCategory(editingSubId, {
          name: formSubName,
          description: formSubDesc,
          is_active: formSubIsActive,
        });
      } else {
        await catalogApi.createSubCategory({
          id_category: formSubCategoryId,
          name: formSubName,
          description: formSubDesc,
        });
      }
      showSubModal = false;
      await loadData();
    } catch (err) {
      errorMsg = err instanceof HttpError ? err.message : 'Error al guardar subcategoría';
    } finally {
      savingSub = false;
    }
  }

  async function toggleCategory(cat: Category) {
    if (!cat.is_active) {
      try {
        await catalogApi.updateCategory(cat.id_category, { is_active: true });
        await loadData();
      } catch (err) {
        errorMsg = err instanceof HttpError ? err.message : 'No se pudo activar la categoría.';
      }
      return;
    }
    confirmation.request({
      kind: 'deactivate',
      title: 'Desactivar categoría de productos',
      description:
        'La categoría dejará de estar disponible para nuevas asignaciones. Los productos y el historial existentes se conservarán.',
      resourceName: cat.name,
      confirmLabel: 'Desactivar categoría',
      execute: async () => {
        await catalogApi.updateCategory(cat.id_category, { is_active: false });
        await loadData();
      }
    });
  }

  async function toggleSubCategory(sub: SubCategory) {
    if (!sub.is_active) {
      try {
        await catalogApi.updateSubCategory(sub.id_sub_category, { is_active: true });
        await loadData();
      } catch (err) {
        errorMsg = err instanceof HttpError ? err.message : 'No se pudo activar la subcategoría.';
      }
      return;
    }
    confirmation.request({
      kind: 'deactivate',
      title: 'Desactivar subcategoría de productos',
      description:
        'La subcategoría dejará de estar disponible para nuevas asignaciones. Los productos y el historial existentes se conservarán.',
      resourceName: sub.name,
      confirmLabel: 'Desactivar subcategoría',
      execute: async () => {
        await catalogApi.updateSubCategory(sub.id_sub_category, { is_active: false });
        await loadData();
      }
    });
  }

  function deleteCategory(cat: Category) {
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar categoría de productos',
      description:
        'La categoría se ocultará de la operación diaria y pasará a la Papelera. No podrá eliminarse mientras conserve subcategorías o productos dependientes.',
      resourceName: cat.name,
      confirmLabel: 'Eliminar categoría',
      requireReason: true,
      reasonLabel: 'Motivo de eliminación',
      execute: async (reason) => {
        if (!reason) return;
        await api.lifecycle.delete('product_categories', String(cat.id_category), reason);
        await loadData();
      }
    });
  }

  function deleteSubCategory(sub: SubCategory) {
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar subcategoría de productos',
      description:
        'La subcategoría se ocultará de la operación diaria y pasará a la Papelera. No podrá eliminarse mientras conserve productos dependientes.',
      resourceName: sub.name,
      confirmLabel: 'Eliminar subcategoría',
      requireReason: true,
      reasonLabel: 'Motivo de eliminación',
      execute: async (reason) => {
        if (!reason) return;
        await api.lifecycle.delete('product_subcategories', String(sub.id_sub_category), reason);
        await loadData();
      }
    });
  }

  function categoryActions(cat: Category): KebabItem[] {
    const actions: KebabItem[] = [];
    if (permissions.hasPermission('products:manage')) {
      actions.push(
        { id: 'add-subcategory', label: 'Nueva subcategoría', icon: 'custom', onClick: () => openCreateSubCategoryModal(cat.id_category) },
        { id: 'edit', label: 'Editar', icon: 'edit', onClick: () => openEditCategoryModal(cat) },
        {
          id: 'status',
          label: cat.is_active ? 'Desactivar' : 'Activar',
          icon: 'power',
          variant: cat.is_active ? 'danger' : 'default',
          onClick: () => void toggleCategory(cat)
        }
      );
    }
    if (permissions.hasPermission('product_categories:delete')) {
      actions.push({ id: 'delete', label: 'Eliminar', icon: 'delete', variant: 'danger', onClick: () => deleteCategory(cat) });
    }
    return actions;
  }

  function subCategoryActions(sub: SubCategory): KebabItem[] {
    const actions: KebabItem[] = [];
    if (permissions.hasPermission('products:manage')) {
      actions.push(
        { id: 'edit', label: 'Editar', icon: 'edit', onClick: () => openEditSubCategoryModal(sub) },
        {
          id: 'status',
          label: sub.is_active ? 'Desactivar' : 'Activar',
          icon: 'power',
          variant: sub.is_active ? 'danger' : 'default',
          onClick: () => void toggleSubCategory(sub)
        }
      );
    }
    if (permissions.hasPermission('product_categories:delete')) {
      actions.push({ id: 'delete', label: 'Eliminar', icon: 'delete', variant: 'danger', onClick: () => deleteSubCategory(sub) });
    }
    return actions;
  }
</script>

<svelte:head><title>Categorías de Productos — GestionaSV</title></svelte:head>

<div class="p-6 md:p-8 animate-fade-scale">
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">
      {loading
        ? 'Cargando...'
        : globalSearch.query.trim()
          ? `${filteredCategories.length} categorías encontradas`
          : `${categories.length} categorías`}
    </p>
    {#if permissions.hasPermission('products:manage')}
      <div class="flex items-center gap-2">
        <Button size="sm" variant="secondary" onclick={() => openCreateSubCategoryModal()}>
          Nueva subcategoría
        </Button>
        <Button size="sm" variant="primary" onclick={openCreateCategoryModal}>
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
          Nueva categoría
        </Button>
      </div>
    {/if}
  </div>

  {#if errorMsg}
    <Callout variant="warning">{errorMsg}</Callout>
  {/if}

  {#if loading}
    <div class="space-y-4">
      {#each Array(3) as _}
        <div class="h-24 bg-surface-muted rounded-xl animate-pulse"></div>
      {/each}
    </div>
  {:else if filteredCategories.length === 0}
    <Card class="p-12 text-center">
      <h3 class="text-lg font-semibold text-foreground">
        {globalSearch.query.trim() ? 'No se encontraron categorías' : 'Sin categorías registradas'}
      </h3>
      {#if globalSearch.query.trim()}
        <p class="mt-1 text-sm text-foreground-muted">Pruebe con otro término de búsqueda.</p>
      {/if}
    </Card>
  {:else}
    <div class="grid grid-cols-1 gap-6">
      {#each filteredCategories as cat}
        {@const catSubList = subCategories.filter((s) => s.id_category === cat.id_category)}
        <Card class="p-5">
          <div class="flex items-start justify-between border-b border-border pb-4 mb-4">
            <div>
              <div class="flex items-center gap-3">
                <h3 class="text-lg font-bold text-foreground">{cat.name}</h3>
                <Badge variant={cat.is_active ? 'success' : 'neutral'}>{cat.is_active ? 'Activa' : 'Inactiva'}</Badge>
              </div>
              <p class="text-xs text-foreground-muted mt-1">{cat.description || 'Sin descripción'}</p>
            </div>
            {#if categoryActions(cat).length > 0}
              <KebabMenu items={categoryActions(cat)} ariaLabel={`Acciones de ${cat.name}`} />
            {/if}
          </div>

          <!-- Subcategories -->
          <div class="pl-4 border-l-2 border-primary/20 space-y-2">
            <h4 class="text-xs font-semibold uppercase text-foreground-muted">Subcategorías ({catSubList.length})</h4>
            {#if catSubList.length === 0}
              <p class="text-xs text-foreground-muted italic">No hay subcategorías en esta categoría.</p>
            {:else}
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                {#each catSubList as sub}
                  <div class="flex items-center justify-between p-2.5 rounded-lg border border-border bg-surface-muted/40">
                    <div>
                      <span class="text-sm font-medium text-foreground">{sub.name}</span>
                      {#if sub.description}
                        <span class="text-xs text-foreground-muted block">{sub.description}</span>
                      {/if}
                    </div>
                    {#if subCategoryActions(sub).length > 0}
                      <KebabMenu items={subCategoryActions(sub)} ariaLabel={`Acciones de ${sub.name}`} />
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        </Card>
      {/each}
    </div>
  {/if}

  <!-- Category Modal -->
  {#if showCatModal}
    <Modal open={showCatModal} title={isEditingCat ? 'Editar Categoría' : 'Nueva Categoría'} onclose={() => (showCatModal = false)}>
      <form onsubmit={handleSaveCategory} class="space-y-4">
        <div>
          <label for="cname" class="block text-xs font-medium text-foreground-muted mb-1">Nombre *</label>
          <input id="cname" type="text" required bind:value={formCatName} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" />
        </div>
        <div>
          <label for="cdesc" class="block text-xs font-medium text-foreground-muted mb-1">Descripción</label>
          <textarea id="cdesc" rows="2" bind:value={formCatDesc} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"></textarea>
        </div>
        <div class="flex justify-end gap-2 pt-4 border-t border-border">
          <Button type="button" variant="secondary" onclick={() => (showCatModal = false)}>Cancelar</Button>
          <Button type="submit" variant="primary" disabled={savingCat}>{savingCat ? 'Guardando...' : 'Guardar'}</Button>
        </div>
      </form>
    </Modal>
  {/if}

  <!-- SubCategory Modal -->
  {#if showSubModal}
    <Modal open={showSubModal} title={isEditingSub ? 'Editar Subcategoría' : 'Nueva Subcategoría'} onclose={() => (showSubModal = false)}>
      <form onsubmit={handleSaveSubCategory} class="space-y-4">
        <div>
          <label for="subcat-select" class="block text-xs font-medium text-foreground-muted mb-1">Categoría Padre *</label>
          <select id="subcat-select" required bind:value={formSubCategoryId} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
            {#each categories as cat}
              <option value={cat.id_category}>{cat.name}</option>
            {/each}
          </select>
        </div>
        <div>
          <label for="sname" class="block text-xs font-medium text-foreground-muted mb-1">Nombre de Subcategoría *</label>
          <input id="sname" type="text" required bind:value={formSubName} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" />
        </div>
        <div>
          <label for="sdesc" class="block text-xs font-medium text-foreground-muted mb-1">Descripción</label>
          <textarea id="sdesc" rows="2" bind:value={formSubDesc} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"></textarea>
        </div>
        <div class="flex justify-end gap-2 pt-4 border-t border-border">
          <Button type="button" variant="secondary" onclick={() => (showSubModal = false)}>Cancelar</Button>
          <Button type="submit" variant="primary" disabled={savingSub}>{savingSub ? 'Guardando...' : 'Guardar'}</Button>
        </div>
      </form>
    </Modal>
  {/if}
</div>
