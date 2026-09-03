<script lang="ts">
  import { api, HttpError, type DocumentCategoryOut } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  let categories = $state<DocumentCategoryOut[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let moduleFilter = $state<'general' | 'employees' | ''>('employees');
  let groupFilter = $state('');
  let includeInactive = $state(true);
  let newCode = $state('');
  let newName = $state('');
  let newGroup = $state('General');
  let saving = $state(false);
  let editingCategory = $state<DocumentCategoryOut | null>(null);
  let editName = $state('');
  let editGroup = $state('');
  let editDescription = $state('');
  let editSortOrder = $state('0');
  let editSaving = $state(false);
  let canManage = $derived(
    permissions.hasAnyPermission(['employee_documents:manage_categories', 'documents:categories'])
  );
  let canManageGeneral = $derived(permissions.hasPermission('documents:categories'));
  let canManageEmployees = $derived(
    permissions.hasPermission('employee_documents:manage_categories')
  );

  $effect(() => {
    const general = canManageGeneral;
    const employees = canManageEmployees;
    if (!general && employees && moduleFilter !== 'employees') moduleFilter = 'employees';
    if (!employees && general && moduleFilter !== 'general') moduleFilter = 'general';
  });

  async function load() {
    if (!canManage) {
      loading = false;
      return;
    }
    loading = true;
    error = null;
    try {
      categories = await api.documents.manageCategories.list({
        module: moduleFilter || undefined,
        includeInactive,
        group: groupFilter.trim() || undefined
      });
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudieron cargar las categorías.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    const _module = moduleFilter;
    const _group = groupFilter;
    const _inactive = includeInactive;
    void _module;
    void _group;
    void _inactive;
    void load();
  });

  async function createCategory() {
    if (!newCode.trim() || !newName.trim()) return;
    saving = true;
    error = null;
    try {
      await api.documents.manageCategories.create({
        module: moduleFilter || (canManageEmployees ? 'employees' : 'general'),
        code: newCode.trim().toLowerCase(),
        name: newName.trim(),
        group_name: newGroup.trim() || 'General'
      });
      newCode = '';
      newName = '';
      newGroup = 'General';
      await load();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo crear la categoría.';
    } finally {
      saving = false;
    }
  }

  async function toggle(category: DocumentCategoryOut) {
    try {
      if (category.is_active) await api.documents.manageCategories.deactivate(category.id);
      else await api.documents.manageCategories.activate(category.id);
      await load();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cambiar el estado.';
    }
  }

  function openEdit(category: DocumentCategoryOut) {
    editingCategory = category;
    editName = category.name;
    editGroup = category.group_name;
    editDescription = category.description ?? '';
    editSortOrder = String(category.sort_order);
  }

  async function saveEdit() {
    if (!editingCategory || !editName.trim() || !editGroup.trim()) return;
    editSaving = true;
    error = null;
    try {
      await api.documents.manageCategories.update(editingCategory.id, {
        name: editName.trim(),
        group_name: editGroup.trim(),
        description: editDescription.trim() || undefined,
        sort_order: Math.max(0, Number.parseInt(editSortOrder, 10) || 0)
      });
      editingCategory = null;
      await load();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo actualizar la categoría.';
    } finally {
      editSaving = false;
    }
  }
</script>

<svelte:head><title>Categorías documentales — GestionaSV</title></svelte:head>

<div class="p-6 md:p-8">
  <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
    <div>
      <a href="/documents" class="text-xs font-medium text-primary hover:underline">← Documentos</a>
      <h1 class="mt-2 text-2xl font-bold text-foreground">Categorías documentales</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Catálogo editable para clasificar expedientes y documentos generales.
      </p>
    </div>
  </div>

  {#if !canManage}
    <Card class="p-6"
      ><p class="text-sm text-foreground-muted">
        No tiene permiso para administrar categorías documentales.
      </p></Card
    >
  {:else}
    <Card class="mb-5 p-4">
      <div class="grid grid-cols-1 gap-3 md:grid-cols-[180px_1fr_auto] md:items-end">
        <FormField
          id="category-module-filter"
          label="Módulo"
          bind:value={moduleFilter}
          options={[
            ...(canManageGeneral && canManageEmployees ? [{ value: '', label: 'Todos' }] : []),
            ...(canManageEmployees ? [{ value: 'employees', label: 'Empleados' }] : []),
            ...(canManageGeneral ? [{ value: 'general', label: 'Generales' }] : [])
          ]}
        />
        <FormField
          id="category-group-filter"
          label="Grupo"
          bind:value={groupFilter}
          placeholder="Ej. Relación laboral"
        />
        <label class="flex items-center gap-2 pb-2 text-xs text-foreground-muted"
          ><input type="checkbox" bind:checked={includeInactive} /> Mostrar inactivas</label
        >
      </div>
    </Card>

    <Card class="mb-5 p-4">
      <p class="mb-3 text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
        Nueva categoría
      </p>
      <div class="grid grid-cols-1 gap-3 md:grid-cols-4 md:items-end">
        <FormField
          id="new-category-code"
          label="Código"
          bind:value={newCode}
          placeholder="ej. seguro_medico"
        />
        <FormField
          id="new-category-name"
          label="Nombre"
          bind:value={newName}
          placeholder="Seguro médico"
        />
        <FormField
          id="new-category-group"
          label="Grupo"
          bind:value={newGroup}
          placeholder="Beneficios"
        />
        <Button onclick={createCategory} disabled={saving || !newCode.trim() || !newName.trim()}
          >{saving ? 'Guardando…' : 'Crear categoría'}</Button
        >
      </div>
    </Card>

    {#if error}<div
        class="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        role="alert"
      >
        {error}
      </div>{/if}
    <Card class="overflow-hidden">
      {#if loading}
        <div class="space-y-2 p-5">
          {#each [1, 2, 3] as item (item)}<div
              class="h-12 animate-pulse rounded-lg bg-surface-muted"
            ></div>{/each}
        </div>
      {:else if categories.length === 0}
        <p class="p-8 text-center text-sm text-foreground-muted">
          No hay categorías con estos filtros.
        </p>
      {:else}
        <div class="divide-y divide-border">
          {#each categories as category (category.id)}
            <div class="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-foreground">{category.name}</p>
                <p class="text-xs text-foreground-muted">
                  {category.module === 'employees' ? 'Empleados' : 'Generales'} · {category.group_name}
                  · <span class="font-mono">{category.code}</span> · {category.document_count} documento(s)
                </p>
              </div>
              <div class="flex items-center gap-3">
                <span
                  class="text-xs {category.is_active ? 'text-success' : 'text-foreground-subtle'}"
                  >{category.is_active ? 'Activa' : 'Inactiva'}</span
                ><Button variant="ghost" size="sm" onclick={() => openEdit(category)}>Editar</Button
                ><Button variant="ghost" size="sm" onclick={() => toggle(category)}
                  >{category.is_active ? 'Desactivar' : 'Activar'}</Button
                >
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </Card>
  {/if}
</div>

{#if editingCategory}<Modal
    open={true}
    title={`Editar · ${editingCategory.name}`}
    onclose={() => (editingCategory = null)}
    ><div class="space-y-4">
      <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
        <FormField id="edit-category-name" label="Nombre" bind:value={editName} required />
        <FormField id="edit-category-group" label="Grupo" bind:value={editGroup} required />
        <FormField
          id="edit-category-order"
          label="Orden"
          type="number"
          min="0"
          bind:value={editSortOrder}
        />
      </div>
      <div>
        <label
          for="edit-category-description"
          class="mb-1 block text-sm font-medium text-foreground">Descripción</label
        >
        <textarea
          id="edit-category-description"
          bind:value={editDescription}
          maxlength="1000"
          rows="3"
          class="w-full resize-y rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        ></textarea>
      </div>
      <div class="flex justify-end gap-2 border-t border-border pt-4">
        <Button variant="ghost" onclick={() => (editingCategory = null)} disabled={editSaving}
          >Cancelar</Button
        >
        <Button onclick={saveEdit} disabled={editSaving || !editName.trim() || !editGroup.trim()}
          >{editSaving ? 'Guardando…' : 'Guardar cambios'}</Button
        >
      </div>
    </div></Modal
  >{/if}
