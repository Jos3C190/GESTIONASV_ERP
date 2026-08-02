<script lang="ts">
  import {
    api,
    HttpError,
    type DepartmentOut,
    type DepartmentBranchAssignmentOut,
    type BranchOut,
    type PageMeta
  } from '$lib/api/client';
  import { onDestroy, onMount } from 'svelte';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';

  let departments = $state<DepartmentOut[]>([]);
  let departmentCatalogue = $state<DepartmentOut[]>([]);
  let meta = $state<PageMeta | null>(null);
  let page = $state(1);
  // La cuadrícula de escritorio usa tres columnas: 15 elementos completan cinco filas útiles.
  const pageSize = 15;
  let loading = $state(false);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);

  let modalMode = $state<'create' | 'edit' | null>(null);
  let modalDept = $state<DepartmentOut | null>(null);
  let formError = $state<string | null>(null);
  let formLoading = $state(false);
  let fName = $state('');
  let fDescription = $state('');
  let fParentId = $state('');
  let branchDept = $state<DepartmentOut | null>(null);
  let branchAssignments = $state<DepartmentBranchAssignmentOut[]>([]);
  let branches = $state<BranchOut[]>([]);
  let fBranchId = $state('');
  let listController: AbortController | null = null;
  let requestGeneration = 0;

  async function loadDepartments(
    requestedPage = page,
    search = globalSearch.query.trim(),
    level = levelFilter
  ) {
    listController?.abort();
    const controller = new AbortController();
    listController = controller;
    const generation = ++requestGeneration;
    loading = true;
    error = null;
    try {
      const response = await api.departments.list({
        page: requestedPage,
        size: pageSize,
        search: search || undefined,
        level: level === 'root' || level === 'child' ? level : undefined,
        signal: controller.signal
      });
      if (generation !== requestGeneration) return;
      departments = response.items;
      meta = response.meta;
      if (requestedPage > response.meta.pages) page = response.meta.pages;
    } catch (err) {
      if (controller.signal.aborted) return;
      error = err instanceof HttpError ? err.message : 'Error.';
    } finally {
      if (generation === requestGeneration) loading = false;
    }
  }

  async function loadDepartmentCatalogue() {
    try {
      departmentCatalogue = await api.departments.catalogue();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar el catálogo.';
    }
  }

  function parentName(id: string | null): string {
    if (!id) return 'Sin padre (raíz)';
    return departmentCatalogue.find((d) => d.id === id)?.name ?? '—';
  }

  function openCreate() {
    modalMode = 'create';
    modalDept = null;
    formError = null;
    fName = '';
    fDescription = '';
    fParentId = '';
  }
  function openEdit(d: DepartmentOut) {
    modalMode = 'edit';
    modalDept = d;
    formError = null;
    fName = d.name;
    fDescription = d.description ?? '';
    fParentId = d.parent_department_id ?? '';
  }
  function closeModal() {
    modalMode = null;
    modalDept = null;
    formError = null;
  }

  async function handleSubmit() {
    formLoading = true;
    formError = null;
    try {
      const data = {
        name: fName,
        description: fDescription || undefined,
        parent_department_id: fParentId || undefined
      };
      if (modalMode === 'create') {
        await api.departments.create(data);
        success = 'Departamento creado correctamente.';
      } else if (modalMode === 'edit' && modalDept) {
        await api.departments.update(modalDept.id, data);
        success = 'Departamento actualizado correctamente.';
      }
      closeModal();
      await Promise.all([loadDepartments(), loadDepartmentCatalogue()]);
    } catch (err) {
      formError = err instanceof HttpError ? err.message : 'Error.';
    } finally {
      formLoading = false;
    }
  }

  function deleteDept(d: DepartmentOut) {
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar departamento',
      description:
        'Esta acción eliminará el departamento. No podrá completarse si todavía tiene empleados o dependencias activas.',
      resourceName: d.name,
      confirmLabel: 'Eliminar',
      execute: async () => {
        await api.departments.delete(d.id);
        success = 'Departamento eliminado correctamente.';
        await Promise.all([loadDepartments(), loadDepartmentCatalogue()]);
      }
    });
  }

  function departmentMenuItems(department: DepartmentOut): KebabItem[] {
    if (!permissions.hasPermission('departments:manage')) return [];

    return [
      { id: 'branches', label: 'Gestionar sucursales', icon: 'link', onClick: () => openBranches(department) },
      { id: 'edit', label: 'Editar', icon: 'edit', onClick: () => openEdit(department) },
      {
        id: 'delete',
        label: 'Eliminar',
        icon: 'delete',
        variant: 'danger',
        onClick: () => deleteDept(department)
      }
    ];
  }

  async function openBranches(d: DepartmentOut) {
    branchDept = d;
    formError = null;
    fBranchId = '';
    try {
      [branchAssignments, branches] = await Promise.all([
        api.workforce.departmentAssignments(d.id),
        api.branches.list()
      ]);
    } catch (err) {
      formError = err instanceof HttpError ? err.message : 'No se pudieron cargar las sucursales.';
    }
  }

  async function enableBranch() {
    if (!branchDept || !fBranchId) return;
    try {
      await api.workforce.enableDepartment({ department_id: branchDept.id, branch_id: fBranchId });
      await openBranches(branchDept);
    } catch (err) {
      formError = err instanceof HttpError ? err.message : 'No se pudo habilitar la sucursal.';
    }
  }

  async function disableBranch(id: string) {
    try {
      await api.workforce.endDepartmentAssignment(id);
      if (branchDept) await openBranches(branchDept);
    } catch (err) {
      formError = err instanceof HttpError ? err.message : 'No se pudo deshabilitar la sucursal.';
    }
  }

  function branchName(id: string) {
    return branches.find((b) => b.id === id)?.name ?? 'Sucursal';
  }

  let levelFilter = $state('');

  let previousFilterKey = '';
  $effect(() => {
    const filterKey = `${globalSearch.query.trim()}|${levelFilter}`;
    if (filterKey !== previousFilterKey) {
      previousFilterKey = filterKey;
      page = 1;
    }
    const requestedPage = page;
    const search = globalSearch.query.trim();
    const level = levelFilter;
    const timer = window.setTimeout(() => loadDepartments(requestedPage, search, level), 250);
    return () => window.clearTimeout(timer);
  });

  onMount(() => {
    void loadDepartmentCatalogue();
  });
  onDestroy(() => listController?.abort());
</script>

<svelte:head><title>Departamentos — ERP System</title></svelte:head>

<div class="p-6 md:p-8">
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">{meta?.total ?? 0} departamento(s)</p>
    <div class="flex items-center gap-2">
      <select
        bind:value={levelFilter}
        class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
      >
        <option value="">Todos</option>
        <option value="root">Raíz</option>
        <option value="child">Con padre</option>
      </select>
      {#if permissions.hasPermission('departments:manage')}
        <Button size="sm" onclick={openCreate}>
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

  {#if error}
    <div
      class="mb-4 animate-fade-scale rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {/if}
  {#if success}
    <div
      class="mb-4 animate-fade-scale rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-success"
      role="status"
    >
      {success}
    </div>
  {/if}

  {#if loading}
    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {#each Array(6) as _}
        <div class="h-36 rounded-2xl border border-border skeleton"></div>
      {/each}
    </div>
  {:else if departments.length === 0}
    <Card class="p-12">
      <div class="flex flex-col items-center text-center">
        <div class="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-muted">
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
            class="text-foreground-subtle"
            ><path
              d="M19 21V5a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5"
            /></svg
          >
        </div>
        <p class="text-sm text-foreground-muted">
          No hay departamentos para los filtros seleccionados.
        </p>
        {#if departments.length === 0 && permissions.hasPermission('departments:manage')}
          <div class="mt-4"><Button onclick={openCreate}>Crear departamento</Button></div>
        {/if}
      </div>
    </Card>
  {:else}
    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {#each departments as dept (dept.id)}
        {@const menuItems = departmentMenuItems(dept)}
        <Card class="p-5 hover-lift">
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-3">
              <div
                class="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-accent/10"
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  aria-hidden="true"
                  class="text-accent"
                  ><path
                    d="M19 21V5a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5"
                  /></svg
                >
              </div>
              <div>
                <h3 class="text-base font-bold text-foreground">{dept.name}</h3>
                <p class="text-xs text-foreground-muted">{dept.description ?? 'Sin descripción'}</p>
              </div>
            </div>
            {#if menuItems.length > 0}
              <KebabMenu items={menuItems} ariaLabel={`Acciones para ${dept.name}`} />
            {/if}
          </div>

          <div class="mt-4 flex items-center gap-2 rounded-lg bg-surface-muted/50 px-3 py-2">
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
              class="text-foreground-subtle"><path d="M15 18l-6-6 6-6" /></svg
            >
            <span class="text-xs text-foreground-subtle"
              >{parentName(dept.parent_department_id)}</span
            >
          </div>
        </Card>
      {/each}
    </div>
  {/if}

  {#if meta && meta.pages > 1}
    <div class="mt-5 flex items-center justify-between gap-4">
      <p class="text-xs text-foreground-muted">
        Página {meta.page} de {meta.pages} · {meta.total} departamentos
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
  open={modalMode !== null}
  title={modalMode === 'create' ? 'Crear departamento' : 'Editar departamento'}
  onclose={closeModal}
>
  <form
    onsubmit={(e) => {
      e.preventDefault();
      handleSubmit();
    }}
    class="space-y-4"
  >
    {#if formError}<div
        class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-2.5 text-sm text-danger"
      >
        {formError}
      </div>{/if}
    <FormField id="d-name" label="Nombre" bind:value={fName} required placeholder="Ventas" />
    <FormField
      id="d-desc"
      label="Descripción"
      bind:value={fDescription}
      placeholder="Departamento de ventas"
    />
    <SmartSelect
      id="d-parent"
      label="Departamento padre"
      bind:value={fParentId}
      placeholder="Buscar departamento padre…"
      options={[
        { value: '', label: '— Ninguno (raíz) —' },
        ...departmentCatalogue
          .filter((d) => d.id !== modalDept?.id)
          .map((d) => ({ value: d.id, label: d.name, description: d.description ?? undefined }))
      ]}
    />
    <div class="flex justify-end gap-2 pt-2">
      <Button variant="secondary" onclick={closeModal}>Cancelar</Button><Button
        type="submit"
        disabled={formLoading}>{formLoading ? 'Guardando...' : 'Guardar'}</Button
      >
    </div>
  </form>
</Modal>

<Modal
  open={branchDept !== null}
  title={`Sucursales de ${branchDept?.name ?? ''}`}
  onclose={() => (branchDept = null)}
>
  <div class="space-y-4">
    {#if formError}<div class="rounded-lg bg-danger/10 p-3 text-sm text-danger">
        {formError}
      </div>{/if}
    <div class="flex gap-2">
      <div class="flex-1">
        <SmartSelect
          id="department-branch"
          label="Habilitar en sucursal"
          bind:value={fBranchId}
          placeholder="Buscar sucursal…"
          options={[
            { value: '', label: '— Seleccionar —' },
            ...branches
              .filter(
                (b) =>
                  b.operational_status === 'active' &&
                  !branchAssignments.some((a) => a.branch_id === b.id && a.is_active)
              )
              .map((b) => ({ value: b.id, label: b.name, description: b.code }))
          ]}
        />
      </div>
      <div class="self-end">
        <Button disabled={!fBranchId} onclick={enableBranch}>Habilitar</Button>
      </div>
    </div>
    <div class="divide-y divide-border rounded-lg border border-border">
      {#each branchAssignments as item (item.id)}
        <div class="flex items-center justify-between gap-3 p-3">
          <div>
            <p class="text-sm font-medium text-foreground">{branchName(item.branch_id)}</p>
            <p class="text-xs text-foreground-muted">
              {item.is_active ? 'Operativo' : `Cerrado ${item.closed_at ?? ''}`}
            </p>
          </div>
          {#if item.is_active}<Button
              variant="ghost"
              size="sm"
              onclick={() => disableBranch(item.id)}>Deshabilitar</Button
            >{/if}
        </div>
      {:else}<p class="p-4 text-sm text-foreground-muted">
          El departamento no opera en ninguna sucursal.
        </p>{/each}
    </div>
  </div>
</Modal>
