<script lang="ts">
  import { onDestroy } from 'svelte';
  import {
    api,
    HttpError,
    type PageMeta,
    type WarehouseCategoryOut
  } from '$lib/api/client';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import KebabMenu from '$lib/components/ui/KebabMenu.svelte';
  import type { KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';

  type Category = WarehouseCategoryOut;
  let items = $state<Category[]>([]);
  let meta = $state<PageMeta | null>(null);
  let page = $state(1);
  const pageSize = 12;
  let loading = $state(true);
  let error = $state<string | null>(null);
  let open = $state(false);
  let editing = $state<Category | null>(null);
  let saving = $state(false);
  let changingState = $state<string | null>(null);
  let name = $state('');
  let description = $state('');
  let listController: AbortController | null = null;
  let requestGeneration = 0;

  async function load(requestedPage = page, search = globalSearch.query.trim()) {
    listController?.abort();
    const controller = new AbortController();
    listController = controller;
    const generation = ++requestGeneration;
    loading = true;
    error = null;
    try {
      const response = await api.warehouseCategories.list({
        page: requestedPage,
        size: pageSize,
        search: search || undefined,
        signal: controller.signal
      });
      if (generation !== requestGeneration) return;
      items = response.items;
      meta = response.meta;
      if (requestedPage > response.meta.pages) page = response.meta.pages;
    } catch (err) {
      if (controller.signal.aborted) return;
      error = err instanceof HttpError ? err.message : 'No se pudieron cargar las categorías.';
    } finally {
      if (generation === requestGeneration) loading = false;
    }
  }

  let previousSearch = '';
  $effect(() => {
    const search = globalSearch.query.trim();
    if (search !== previousSearch) {
      previousSearch = search;
      page = 1;
    }
    const requestedPage = page;
    const timer = window.setTimeout(() => void load(requestedPage, search), 250);
    return () => window.clearTimeout(timer);
  });

  onDestroy(() => listController?.abort());

  function create() {
    editing = null;
    name = '';
    description = '';
    open = true;
  }
  function edit(category: Category) {
    editing = category;
    name = category.name;
    description = category.description ?? '';
    open = true;
  }
  async function save(event: SubmitEvent) {
    event.preventDefault();
    saving = true;
    error = null;
    try {
      const payload = { name, description: description || null };
      if (editing) await api.warehouseCategories.update(editing.id, payload);
      else await api.warehouseCategories.create(payload);
      open = false;
      await load();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo guardar.';
    } finally {
      saving = false;
    }
  }
  async function toggle(category: Category) {
    if (changingState) return;
    if (category.is_active) {
      confirmation.request({
        kind: 'deactivate',
        title: 'Desactivar categoría',
        description:
          'La categoría dejará de estar disponible para nuevas asignaciones. No podrá desactivarse si la utilizan almacenes activos.',
        resourceName: category.name,
        confirmLabel: 'Desactivar categoría',
        execute: async () => {
          changingState = category.id;
          try {
            await api.warehouseCategories.deactivate(category.id);
            await load();
          } finally {
            changingState = null;
          }
        }
      });
      return;
    }
    changingState = category.id;
    error = null;
    try {
      await api.warehouseCategories.activate(category.id);
      await load();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cambiar el estado.';
    } finally {
      changingState = null;
    }
  }


  function deleteCategory(category: Category) {
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar categoría de almacén',
      description:
        'La categoría se ocultará de la operación diaria y pasará a la Papelera. No podrá eliminarse mientras existan almacenes que dependan de ella.',
      resourceName: category.name,
      confirmLabel: 'Eliminar categoría',
      requireReason: true,
      reasonLabel: 'Motivo de eliminación',
      execute: async (reason) => {
        if (!reason) return;
        await api.lifecycle.delete('warehouse_categories', category.id, reason);
        await load();
      }
    });
  }

  function menuItems(category: Category): KebabItem[] {
    const actions: KebabItem[] = [];
    if (permissions.hasPermission('warehouse_categories.update')) {
      actions.push({
        id: 'edit',
        label: 'Editar',
        icon: 'edit',
        onClick: () => edit(category)
      });
    }
    if (
      permissions.hasAnyPermission([
        'warehouse_categories.activate',
        'warehouse_categories.deactivate'
      ])
    ) {
      actions.push({
        id: 'state',
        label: category.is_active ? 'Desactivar' : 'Activar',
        icon: 'power',
        variant: category.is_active ? 'danger' : 'default',
        onClick: () => void toggle(category)
      });
    }
    if (permissions.hasPermission('warehouse_categories.delete')) {
      actions.push({
        id: 'delete',
        label: 'Eliminar',
        icon: 'delete',
        variant: 'danger',
        onClick: () => deleteCategory(category)
      });
    }
    return actions;
  }
</script>

<svelte:head><title>Categorías de almacén — GestionaSV</title></svelte:head>

<div class="space-y-4 p-4 sm:space-y-6 sm:p-6 md:p-8">
  <div class="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center sm:gap-4">
    <p class="text-sm text-foreground-muted">
      {meta?.total ?? 0} categoría(s) registradas · Clasificación operativa de almacenes
    </p>
    {#if permissions.hasPermission('warehouse_categories.create')}
      <Button size="sm" onclick={create}>
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
    {/if}
  </div>

  {#if error}
    <p class="rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger" role="alert">
      {error}
    </p>
  {/if}

  {#if loading}
    <div class="h-64 rounded-xl skeleton"></div>
  {:else if items.length === 0}
    <div
      class="rounded-xl border border-dashed border-border bg-surface-elevated px-6 py-12 text-center"
    >
      <p class="text-sm font-medium text-foreground">
        {globalSearch.query ? 'Sin coincidencias' : 'No hay categorías registradas'}
      </p>
      <p class="mt-1 text-xs text-foreground-muted">
        {globalSearch.query
          ? 'Pruebe con otro término de búsqueda.'
          : 'Cree la primera categoría para clasificar sus almacenes.'}
      </p>
    </div>
  {:else}
    <div class="overflow-x-auto rounded-xl border border-border bg-surface-elevated">
      <table class="w-full min-w-[680px] text-sm">
        <thead class="bg-surface-muted"
          ><tr
            ><th class="p-3 text-left">Nombre</th><th class="p-3 text-left">Descripción</th><th
              class="p-3 text-left">Estado</th
            ><th class="w-11 px-2 py-3 text-center"></th></tr
          ></thead
        >
        <tbody>
          {#each items as category (category.id)}
            <tr class="border-t border-border">
              <td class="p-3 font-semibold">{category.name}</td>
              <td class="p-3 text-foreground-muted">{category.description ?? '—'}</td>
              <td class="p-3">{category.is_active ? 'Activa' : 'Inactiva'}</td>
              <td class="px-2 py-3 text-center"><KebabMenu items={menuItems(category)} /></td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if meta && meta.pages > 1}
    <div class="flex items-center justify-between gap-4">
      <p class="text-xs text-foreground-muted">
        Página {meta.page} de {meta.pages} · {meta.total} categorías
      </p>
      <div class="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          onclick={() => (page = Math.max(1, page - 1))}
          disabled={loading || meta.page <= 1}>Anterior</Button
        >
        <Button
          variant="secondary"
          size="sm"
          onclick={() => (page = Math.min(meta!.pages, page + 1))}
          disabled={loading || meta.page >= meta.pages}>Siguiente</Button
        >
      </div>
    </div>
  {/if}
</div>

<Modal
  {open}
  title={editing ? 'Editar categoría' : 'Nueva categoría'}
  onclose={() => (open = false)}
>
  <form class="space-y-4" onsubmit={save}>
    <FormField id="category-name" label="Nombre" bind:value={name} required />
    <FormField id="category-description" label="Descripción" bind:value={description} />
    <div class="flex justify-end gap-2">
      <Button variant="ghost" onclick={() => (open = false)}>Cancelar</Button><Button
        type="submit"
        disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</Button
      >
    </div>
  </form>
</Modal>
