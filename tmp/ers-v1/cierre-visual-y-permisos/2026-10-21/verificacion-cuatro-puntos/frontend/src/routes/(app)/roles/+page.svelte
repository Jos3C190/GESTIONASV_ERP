<script lang="ts">
  import {
    api,
    HttpError,
    type RoleWithPermissions,
    type PermissionOut,
    type UserOut,
    type PageMeta
  } from '$lib/api/client';
  import { goto } from '$app/navigation';
  import { onDestroy, onMount } from 'svelte';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';

  let roles = $state<RoleWithPermissions[]>([]);
  let roleCatalogue = $state<RoleWithPermissions[]>([]);
  let allPermissions = $state<PermissionOut[]>([]);
  let meta = $state<PageMeta | null>(null);
  let page = $state(1);
  const pageSize = 12;
  let loading = $state(false);
  let error = $state<string | null>(null);
  let listController: AbortController | null = null;
  let requestGeneration = 0;

  let modalMode = $state<
    'create' | 'edit' | 'duplicate' | 'permission-create' | 'permission-edit' | 'assign' | null
  >(null);
  let modalRole = $state<RoleWithPermissions | null>(null);
  let formError = $state<string | null>(null);
  let formLoading = $state(false);
  let fName = $state('');
  let fDesc = $state('');
  let modalPermission = $state<PermissionOut | null>(null);
  let fPermissionCode = $state('');
  let fPermissionModule = $state('');
  let users = $state<UserOut[]>([]);
  let fUserId = $state('');
  let selectedUserRoleIds = $state<Set<string>>(new Set());
  let originalUserRoleIds = $state<Set<string>>(new Set());
  let success = $state<string | null>(null);
  let assignedRoleQuery = $state('');

  async function loadRoles(
    requestedPage = page,
    search = globalSearch.query.trim(),
    system = systemFilter,
    module = moduleFilter
  ) {
    listController?.abort();
    const controller = new AbortController();
    listController = controller;
    const generation = ++requestGeneration;
    loading = true;
    error = null;
    try {
      const response = await api.roles.list({
        page: requestedPage,
        size: pageSize,
        search: search || undefined,
        isSystem: system === 'system' ? true : system === 'custom' ? false : undefined,
        module: module || undefined,
        signal: controller.signal
      });
      if (generation !== requestGeneration) return;
      roles = response.items;
      meta = response.meta;
      if (requestedPage > response.meta.pages) page = response.meta.pages;
    } catch (err) {
      if (controller.signal.aborted) return;
      error = err instanceof HttpError ? err.message : 'Error.';
    } finally {
      if (generation === requestGeneration) loading = false;
    }
  }

  async function loadPermissions() {
    try {
      allPermissions = await api.roles.listPermissions();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar el catálogo de permisos.';
    }
  }

  function openCreate() {
    modalMode = 'create';
    modalRole = null;
    formError = null;
    fName = '';
    fDesc = '';
  }
  function openEdit(r: RoleWithPermissions) {
    modalMode = 'edit';
    modalRole = r;
    formError = null;
    fName = r.name;
    fDesc = r.description ?? '';
  }
  function openDuplicate(r: RoleWithPermissions) {
    modalMode = 'duplicate';
    modalRole = r;
    formError = null;
    fName = `${r.name}_COPIA`;
    fDesc = r.description ?? '';
  }
  function openPermissionCreate() {
    modalMode = 'permission-create';
    modalPermission = null;
    formError = null;
    fPermissionCode = '';
    fPermissionModule = '';
    fDesc = '';
  }
  function openPermissions(r: RoleWithPermissions) {
    void goto(`/roles/${r.id}/permissions`);
  }
  async function openAssign() {
    modalMode = 'assign';
    formError = null;
    fUserId = '';
    selectedUserRoleIds = new Set();
    originalUserRoleIds = new Set();
    assignedRoleQuery = '';
    try {
      const [userPage, catalogue] = await Promise.all([
        api.users.list({ size: 100 }),
        api.roles.catalogue()
      ]);
      users = userPage.items;
      roleCatalogue = catalogue;
    } catch {
      users = [];
    }
  }
  async function loadSelectedUserRoles() {
    if (!fUserId) {
      selectedUserRoleIds = new Set();
      originalUserRoleIds = new Set();
      return;
    }
    try {
      const assigned = await api.roles.userRoles(fUserId);
      selectedUserRoleIds = new Set(assigned.map((role) => role.id));
      originalUserRoleIds = new Set(selectedUserRoleIds);
    } catch (err) {
      formError = err instanceof HttpError ? err.message : 'No se pudieron cargar los roles.';
    }
  }
  function toggleUserRole(roleId: string) {
    if (selectedUserRoleIds.has(roleId)) selectedUserRoleIds.delete(roleId);
    else selectedUserRoleIds.add(roleId);
    selectedUserRoleIds = new Set(selectedUserRoleIds);
  }
  function closeModal() {
    modalMode = null;
    modalRole = null;
    modalPermission = null;
    formError = null;
  }

  async function handleSubmit() {
    formLoading = true;
    formError = null;
    try {
      if (modalMode === 'create') {
        await api.roles.create({ name: fName, description: fDesc || undefined });
        success = 'Rol creado correctamente.';
      } else if (modalMode === 'edit' && modalRole) {
        await api.roles.update(modalRole.id, { name: fName, description: fDesc || undefined });
        success = 'Rol actualizado correctamente.';
      } else if (modalMode === 'duplicate' && modalRole) {
        await api.roles.duplicate(modalRole.id, { name: fName, description: fDesc || undefined });
        success = 'Rol duplicado correctamente.';
      } else if (modalMode === 'permission-create') {
        await api.roles.createPermission({
          code: fPermissionCode,
          module: fPermissionModule || undefined,
          description: fDesc || undefined
        });
        success = 'Permiso creado correctamente.';
      } else if (modalMode === 'permission-edit' && modalPermission) {
        await api.roles.updatePermission(modalPermission.id, {
          code: fPermissionCode,
          module: fPermissionModule || undefined,
          description: fDesc || undefined
        });
        success = 'Permiso actualizado correctamente.';
      } else if (modalMode === 'assign' && fUserId) {
        if (selectedUserRoleIds.size === 0) {
          throw new Error('El usuario debe conservar al menos un rol.');
        }
        const toAssign = [...selectedUserRoleIds].filter((id) => !originalUserRoleIds.has(id));
        const toRevoke = [...originalUserRoleIds].filter((id) => !selectedUserRoleIds.has(id));
        for (const roleId of toAssign) await api.roles.assign(fUserId, roleId);
        for (const roleId of toRevoke) await api.roles.revoke(fUserId, roleId);
        success = 'Roles del usuario actualizados.';
      }
      closeModal();
      await Promise.all([loadRoles(), loadPermissions()]);
    } catch (err) {
      formError = err instanceof Error ? err.message : 'Error.';
    } finally {
      formLoading = false;
    }
  }

  function deleteRole(r: RoleWithPermissions) {
    if (r.is_system) {
      error = 'Los roles de sistema están protegidos y no pueden eliminarse.';
      return;
    }
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar rol',
      description:
        'El rol desaparecerá de la operación diaria y quedará disponible en la Papelera. Los roles protegidos del sistema no pueden eliminarse.',
      resourceName: r.name,
      confirmLabel: 'Eliminar rol',
      requireReason: true,
      execute: async (reason) => {
        if (!reason) throw new Error('Indique el motivo de eliminación.');
        await api.lifecycle.delete('roles', r.id, reason);
        success = 'Rol enviado a la Papelera.';
        await loadRoles();
      }
    });
  }

  function deletePermission(permission: PermissionOut) {
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar permiso',
      description:
        'El permiso personalizado desaparecerá del catálogo y quedará disponible en la Papelera. Los permisos estándar del sistema están protegidos.',
      resourceName: permission.code,
      confirmLabel: 'Eliminar permiso',
      requireReason: true,
      execute: async (reason) => {
        if (!reason) throw new Error('Indique el motivo de eliminación.');
        await api.lifecycle.delete('permissions', permission.id, reason);
        success = 'Permiso enviado a la Papelera.';
        closeModal();
        await Promise.all([loadRoles(), loadPermissions()]);
      }
    });
  }

  function roleMenuItems(role: RoleWithPermissions): KebabItem[] {
    const items: KebabItem[] = [];

    if (permissions.hasAnyPermission(['permissions:read', 'permissions:manage'])) {
      items.push({
        id: 'permissions',
        label: permissions.hasPermission('permissions:manage')
          ? 'Gestionar permisos'
          : 'Ver permisos',
        icon: 'key',
        onClick: () => openPermissions(role)
      });
    }
    if (!role.is_system && permissions.hasPermission('roles:update')) {
      items.push({ id: 'edit', label: 'Editar', icon: 'edit', onClick: () => openEdit(role) });
    }
    if (permissions.hasPermission('roles:create')) {
      items.push({
        id: 'duplicate',
        label: 'Duplicar',
        icon: 'custom',
        onClick: () => openDuplicate(role)
      });
    }
    if (!role.is_system && permissions.hasPermission('roles:delete')) {
      items.push({
        id: 'delete',
        label: 'Eliminar',
        icon: 'delete',
        variant: 'danger',
        onClick: () => deleteRole(role)
      });
    }

    return items;
  }

  let systemFilter = $state('');
  let moduleFilter = $state('');

  let permModules = $derived.by(() => {
    const s = new Set<string>();
    for (const p of allPermissions) {
      if (p.module) s.add(p.module);
    }
    return [...s].sort();
  });

  let previousFilterKey = '';
  $effect(() => {
    const filterKey = `${globalSearch.query.trim()}|${systemFilter}|${moduleFilter}`;
    if (filterKey !== previousFilterKey) {
      previousFilterKey = filterKey;
      page = 1;
    }
    const requestedPage = page;
    const search = globalSearch.query.trim();
    const system = systemFilter;
    const module = moduleFilter;
    const timer = window.setTimeout(() => loadRoles(requestedPage, search, system, module), 250);
    return () => window.clearTimeout(timer);
  });

  onMount(() => {
    void loadPermissions();
  });
  onDestroy(() => listController?.abort());
</script>

<svelte:head><title>Roles — GestionaSV</title></svelte:head>

<div class="p-6 md:p-8">
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">
      {meta?.total ?? 0} rol(es) · {allPermissions.length} permisos
    </p>
    <div class="flex items-center gap-2">
      <select
        bind:value={systemFilter}
        class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
      >
        <option value="">Todos</option>
        <option value="system">Sistema</option>
        <option value="custom">Personalizados</option>
      </select>
      <select
        bind:value={moduleFilter}
        class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
      >
        <option value="">Todos los módulos</option>
        {#each permModules as m (m)}<option value={m}>{m}</option>{/each}
      </select>
      {#if permissions.hasAnyPermission(['roles:assign', 'roles:revoke'])}
        <Button variant="secondary" size="sm" onclick={openAssign}>Asignar</Button>
      {/if}
      {#if permissions.hasPermission('permissions:manage')}
        <Button variant="secondary" size="sm" onclick={openPermissionCreate}>Nuevo permiso</Button>
      {/if}
      {#if permissions.hasPermission('roles:create')}
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
    <div class="grid gap-5 md:grid-cols-2">
      {#each Array(4) as _}
        <div class="h-44 rounded-2xl border border-border skeleton"></div>
      {/each}
    </div>
  {:else if roles.length === 0}
    <Card class="p-12">
      <div class="flex flex-col items-center text-center">
        <p class="text-sm text-foreground-muted">No hay roles para los filtros seleccionados.</p>
      </div>
    </Card>
  {:else}
    <div class="grid gap-5 md:grid-cols-2">
      {#each roles as role (role.id)}
        {@const visiblePermissions = role.permissions.slice(0, 5)}
        {@const hiddenPermissionCount = role.permissions.length - visiblePermissions.length}
        {@const menuItems = roleMenuItems(role)}
        <Card class="flex h-[252px] flex-col p-5 hover-lift">
          <!-- Header -->
          <div class="flex min-h-[64px] items-start justify-between gap-3">
            <div class="flex min-w-0 items-center gap-3">
              <div
                class="flex h-10 w-10 flex-none items-center justify-center rounded-xl {role.is_system
                  ? 'bg-foreground'
                  : 'bg-primary/10'}"
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
                  class={role.is_system ? 'text-surface' : 'text-primary'}
                >
                  <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" />
                  <path
                    d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
                  />
                </svg>
              </div>
              <div class="min-w-0">
                <h3 class="truncate text-base font-bold text-foreground" title={role.name}>
                  {role.name}
                </h3>
                <p class="line-clamp-2 text-xs text-foreground-muted">
                  {role.description ?? 'Sin descripción'}
                </p>
              </div>
            </div>
            <div class="flex flex-none items-center gap-1">
              {#if role.is_system}
                <span
                  class="badge-primary inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold"
                >
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="3"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg
                  >
                  Sistema
                </span>
              {/if}
              {#if menuItems.length > 0}
                <KebabMenu items={menuItems} ariaLabel={`Acciones para ${role.name}`} />
              {/if}
            </div>
          </div>

          <!-- Permissions -->
          <div class="mt-4 min-h-[120px] flex-1">
            <div class="mb-2.5 flex items-center justify-between gap-3">
              <p
                class="text-[11px] font-semibold uppercase tracking-[0.08em] text-foreground-subtle"
              >
                Permisos asignados
              </p>
              <span
                class="inline-flex min-w-7 items-center justify-center rounded-full border border-border bg-surface-muted px-2 py-0.5 text-[11px] font-semibold tabular-nums text-foreground-muted"
                aria-label={`${role.permissions.length} permisos asignados`}
              >
                {role.permissions.length}
              </span>
            </div>
            <div class="grid grid-cols-2 auto-rows-[28px] gap-1.5">
              {#each visiblePermissions as perm (perm.code)}
                <span
                  class="flex min-w-0 items-center truncate rounded-lg border border-border/80 bg-surface-muted/70 px-2.5 text-[11px] font-mono text-foreground-muted"
                  title={perm.code}>{perm.code}</span
                >
              {:else}
                <span
                  class="col-span-2 flex h-16 items-center justify-center rounded-xl border border-dashed border-border text-xs text-foreground-subtle"
                >
                  Sin permisos asignados
                </span>
              {/each}
              {#if hiddenPermissionCount > 0}
                {#if permissions.hasAnyPermission(['permissions:read', 'permissions:manage'])}
                  <button
                    type="button"
                    class="flex items-center justify-center rounded-lg border border-primary/25 bg-primary/10 px-2.5 text-[11px] font-semibold text-primary transition-colors hover:border-primary/40 hover:bg-primary/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    aria-label={`Ver ${hiddenPermissionCount} permisos adicionales de ${role.name}`}
                    onclick={() => openPermissions(role)}>+{hiddenPermissionCount} permisos</button
                  >
                {:else}
                  <span
                    class="flex items-center justify-center rounded-lg border border-border bg-surface-muted px-2.5 text-[11px] font-semibold text-foreground-muted"
                    title={role.permissions
                      .slice(5)
                      .map((permission) => permission.code)
                      .join(', ')}>+{hiddenPermissionCount} permisos</span
                  >
                {/if}
              {/if}
            </div>
          </div>
        </Card>
      {/each}
    </div>
  {/if}

  {#if meta && meta.pages > 1}
    <div class="mt-5 flex items-center justify-between gap-4">
      <p class="text-xs text-foreground-muted">
        Página {meta.page} de {meta.pages} · {meta.total} roles
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
  title={modalMode === 'create'
    ? 'Crear rol'
    : modalMode === 'edit'
      ? 'Editar rol'
      : modalMode === 'duplicate'
        ? 'Duplicar rol'
        : modalMode === 'permission-create'
          ? 'Crear permiso'
          : modalMode === 'permission-edit'
            ? 'Editar permiso'
            : 'Asignar rol a usuario'}
  onclose={closeModal}
  size="md"
>
  {#if modalMode === 'create' || modalMode === 'edit' || modalMode === 'duplicate'}
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
      <FormField
        id="r-name"
        label="Nombre del rol"
        bind:value={fName}
        required
        placeholder="GERENTE"
      />
      <FormField id="r-desc" label="Descripción" bind:value={fDesc} placeholder="Rol de gerencia" />
      <div class="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onclick={closeModal}>Cancelar</Button><Button
          type="submit"
          disabled={formLoading}>{formLoading ? 'Guardando...' : 'Guardar'}</Button
        >
      </div>
    </form>
  {:else if modalMode === 'permission-create' || modalMode === 'permission-edit'}
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
      <FormField
        id="p-code"
        label="Código"
        bind:value={fPermissionCode}
        required
        placeholder="recurso.acción"
      />
      <FormField
        id="p-module"
        label="Módulo"
        bind:value={fPermissionModule}
        placeholder="usuarios"
      />
      <FormField
        id="p-desc"
        label="Descripción"
        bind:value={fDesc}
        placeholder="Descripción del permiso"
      />
      <div class="flex justify-end gap-2 pt-2">
        {#if modalMode === 'permission-edit' && modalPermission && !modalPermission.is_protected && permissions.hasPermission('permissions:delete')}
          <Button
            variant="ghost"
            onclick={() => deletePermission(modalPermission!)}
            class="mr-auto !text-danger">Eliminar</Button
          >
        {/if}
        <Button variant="secondary" onclick={closeModal}>Cancelar</Button>
        <Button type="submit" disabled={formLoading}
          >{formLoading ? 'Guardando...' : 'Guardar permiso'}</Button
        >
      </div>
    </form>
  {:else if modalMode === 'assign'}
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
      <SmartSelect
        id="a-user"
        label="Usuario"
        bind:value={fUserId}
        onselect={() => loadSelectedUserRoles()}
        placeholder="Buscar usuario por nombre o correo…"
        options={[
          { value: '', label: '— Seleccionar —' },
          ...users.map((u) => ({ value: u.id, label: u.username, description: u.email }))
        ]}
      />
      <fieldset class="space-y-2" disabled={!fUserId || formLoading}>
        <legend class="mb-2 text-sm font-semibold text-foreground">
          Roles asignados
          <span class="font-normal text-foreground-muted">({selectedUserRoleIds.size})</span>
        </legend>
        <input
          aria-label="Buscar roles asignables"
          placeholder="Buscar rol por nombre o descripción…"
          bind:value={assignedRoleQuery}
          class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
        />
        <div class="max-h-64 space-y-2 overflow-y-auto rounded-xl border border-border p-3">
          {#if roleCatalogue.filter((role) => `${role.name} ${role.description ?? ''}`
              .toLocaleLowerCase('es')
              .includes(assignedRoleQuery.trim().toLocaleLowerCase('es'))).length === 0}
            <p class="px-2 py-5 text-center text-xs text-foreground-muted">
              No se encontraron roles.
            </p>
          {/if}
          {#each roleCatalogue.filter((role) => `${role.name} ${role.description ?? ''}`
              .toLocaleLowerCase('es')
              .includes(assignedRoleQuery.trim().toLocaleLowerCase('es'))) as role (role.id)}
            <label
              class="flex cursor-pointer items-start gap-3 rounded-lg px-2 py-2 hover:bg-surface-muted"
            >
              <input
                type="checkbox"
                checked={selectedUserRoleIds.has(role.id)}
                onchange={() => toggleUserRole(role.id)}
                class="mt-0.5 h-4 w-4 rounded border-border text-primary focus:ring-primary"
              />
              <span>
                <span class="block text-sm font-medium text-foreground">{role.name}</span>
                <span class="block text-xs text-foreground-muted">
                  {role.description ?? 'Sin descripción'}
                </span>
              </span>
            </label>
          {/each}
        </div>
        {#if fUserId && selectedUserRoleIds.size === 0}
          <p class="text-xs text-danger">El usuario debe conservar al menos un rol.</p>
        {/if}
      </fieldset>
      <div class="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onclick={closeModal}>Cancelar</Button><Button
          type="submit"
          disabled={formLoading || !fUserId || selectedUserRoleIds.size === 0}
          >{formLoading ? 'Guardando...' : 'Guardar asignaciones'}</Button
        >
      </div>
    </form>
  {/if}
</Modal>
