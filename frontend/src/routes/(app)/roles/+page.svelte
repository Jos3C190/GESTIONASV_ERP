<script lang="ts">
  import {
    api,
    HttpError,
    type RoleWithPermissions,
    type PermissionOut,
    type UserOut
  } from '$lib/api/client';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';

  let roles = $state<RoleWithPermissions[]>([]);
  let allPermissions = $state<PermissionOut[]>([]);
  let loading = $state(false);
  let error = $state<string | null>(null);

  let modalMode = $state<
    | 'create'
    | 'edit'
    | 'duplicate'
    | 'permissions'
    | 'permission-create'
    | 'permission-edit'
    | 'assign'
    | null
  >(null);
  let modalRole = $state<RoleWithPermissions | null>(null);
  let formError = $state<string | null>(null);
  let formLoading = $state(false);
  let fName = $state('');
  let fDesc = $state('');
  let modalPermission = $state<PermissionOut | null>(null);
  let fPermissionCode = $state('');
  let fPermissionModule = $state('');
  let selectedPerms = $state<Set<string>>(new Set());
  let users = $state<UserOut[]>([]);
  let fUserId = $state('');
  let selectedUserRoleIds = $state<Set<string>>(new Set());
  let originalUserRoleIds = $state<Set<string>>(new Set());
  let success = $state<string | null>(null);

  async function loadRoles() {
    loading = true;
    error = null;
    try {
      [roles, allPermissions] = await Promise.all([api.roles.list(), api.roles.listPermissions()]);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error.';
    } finally {
      loading = false;
    }
  }

  function permsByModule(): [string, PermissionOut[]][] {
    const map: Record<string, PermissionOut[]> = {};
    for (const p of allPermissions) {
      (map[p.module ?? 'otros'] ??= []).push(p);
    }
    return Object.entries(map);
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
  function openPermissionEdit(p: PermissionOut) {
    modalMode = 'permission-edit';
    modalPermission = p;
    formError = null;
    fPermissionCode = p.code;
    fPermissionModule = p.module ?? '';
    fDesc = p.description ?? '';
  }
  function openPermissions(r: RoleWithPermissions) {
    modalMode = 'permissions';
    modalRole = r;
    formError = null;
    selectedPerms = new Set(r.permissions.map((p) => p.code));
  }
  async function openAssign() {
    modalMode = 'assign';
    formError = null;
    fUserId = '';
    selectedUserRoleIds = new Set();
    originalUserRoleIds = new Set();
    try {
      const r = await api.users.list({ size: 100 });
      users = r.items;
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
      } else if (modalMode === 'permissions' && modalRole) {
        await api.roles.setPermissions(modalRole.id, [...selectedPerms]);
        success = 'Matriz de permisos actualizada.';
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
      await loadRoles();
    } catch (err) {
      formError = err instanceof Error ? err.message : 'Error.';
    } finally {
      formLoading = false;
    }
  }

  async function deleteRole(r: RoleWithPermissions) {
    if (r.is_system) {
      alert('Los roles de sistema no pueden eliminarse.');
      return;
    }
    if (!confirm(`¿Eliminar el rol "${r.name}"?`)) return;
    try {
      await api.roles.delete(r.id);
      success = 'Rol eliminado.';
      await loadRoles();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error.';
    }
  }

  async function deletePermission(permission: PermissionOut) {
    if (!confirm(`¿Eliminar el permiso "${permission.code}"?`)) return;
    try {
      await api.roles.deletePermission(permission.id);
      success = 'Permiso eliminado.';
      closeModal();
      await loadRoles();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error al eliminar el permiso.';
    }
  }

  function togglePerm(code: string) {
    if (selectedPerms.has(code)) selectedPerms.delete(code);
    else selectedPerms.add(code);
    selectedPerms = new Set(selectedPerms);
  }

  let systemFilter = $state('');
  let moduleFilter = $state('');

  let filteredRoles = $derived.by(() => {
    const q = globalSearch.query.toLowerCase().trim();
    let result = roles;
    if (q) {
      result = result.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          r.permissions.some((p) => p.code.toLowerCase().includes(q)) ||
          (r.description ?? '').toLowerCase().includes(q)
      );
    }
    if (systemFilter === 'system') result = result.filter((r) => r.is_system);
    else if (systemFilter === 'custom') result = result.filter((r) => !r.is_system);
    if (moduleFilter)
      result = result.filter((r) => r.permissions.some((p) => (p.module ?? '') === moduleFilter));
    return result;
  });

  let permModules = $derived.by(() => {
    const s = new Set<string>();
    for (const p of allPermissions) {
      if (p.module) s.add(p.module);
    }
    return [...s].sort();
  });

  $effect(() => {
    loadRoles();
  });
</script>

<svelte:head><title>Roles — ERP System</title></svelte:head>

<div class="p-6 md:p-8">
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">
      {filteredRoles.length} rol(es) · {allPermissions.length} permisos
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
  {:else}
    <div class="grid gap-5 md:grid-cols-2">
      {#each filteredRoles as role (role.id)}
        <Card class="p-5 hover-lift">
          <!-- Header -->
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-3">
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
              <div>
                <h3 class="text-base font-bold text-foreground">{role.name}</h3>
                <p class="text-xs text-foreground-muted">{role.description ?? 'Sin descripción'}</p>
              </div>
            </div>
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
          </div>

          <!-- Permissions -->
          <div class="mt-4">
            <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
              {role.permissions.length} permiso(s)
            </p>
            <div class="flex flex-wrap gap-1.5">
              {#each role.permissions as perm (perm.code)}
                <span
                  class="rounded-lg border border-border bg-surface-muted px-2 py-1 text-xs font-mono text-foreground-muted"
                  >{perm.code}</span
                >
              {:else}
                <span class="text-xs italic text-foreground-subtle">Sin permisos asignados</span>
              {/each}
            </div>
          </div>

          <!-- Footer -->
          <div class="mt-5 flex items-center gap-2 border-t border-border pt-4">
            {#if permissions.hasPermission('permissions:manage')}
              <Button variant="secondary" size="sm" onclick={() => openPermissions(role)}>
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
                  ><path
                    d="M9 12l2 2 4-4M21 12c0 4.97-4.03 9-9 9s-9-4.03-9-9 4.03-9 9-9 9 4.03 9 9z"
                  /></svg
                >
                Permisos
              </Button>
            {/if}
            {#if !role.is_system}
              {#if permissions.hasPermission('roles:update')}
                <Button variant="ghost" size="sm" onclick={() => openEdit(role)}>Editar</Button>
              {/if}
              {#if permissions.hasPermission('roles:create')}
                <Button variant="ghost" size="sm" onclick={() => openDuplicate(role)}
                  >Duplicar</Button
                >
              {/if}
              {#if permissions.hasPermission('roles:delete')}
                <Button
                  variant="ghost"
                  size="sm"
                  onclick={() => deleteRole(role)}
                  class="!text-danger hover:!bg-danger/10">Eliminar</Button
                >
              {/if}
            {:else if permissions.hasPermission('roles:create')}
              <Button variant="ghost" size="sm" onclick={() => openDuplicate(role)}>Duplicar</Button
              >
            {/if}
          </div>
        </Card>
      {/each}
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
        : modalMode === 'permissions'
          ? 'Matriz de permisos'
          : modalMode === 'permission-create'
            ? 'Crear permiso'
            : modalMode === 'permission-edit'
              ? 'Editar permiso'
              : 'Asignar rol a usuario'}
  onclose={closeModal}
  size={modalMode === 'permissions' ? 'lg' : 'md'}
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
        {#if modalMode === 'permission-edit' && modalPermission}
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
  {:else if modalMode === 'permissions' && modalRole}
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
      <p class="text-sm text-foreground-muted">
        Permiso para el rol <strong class="text-foreground">{modalRole.name}</strong>
      </p>
      {#each permsByModule() as [mod, perms]}
        <div class="rounded-xl border border-border bg-surface-muted/50 p-3">
          <p class="mb-3 text-xs font-bold uppercase tracking-wider text-foreground-subtle">
            {mod}
          </p>
          <div class="grid grid-cols-2 gap-2">
            {#each perms as p (p.code)}
              <label
                class="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-foreground transition-colors hover:bg-surface-hover cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selectedPerms.has(p.code)}
                  onchange={() => togglePerm(p.code)}
                  class="h-4 w-4 rounded border-border text-primary focus:shadow-glow"
                />
                <span class="font-mono text-xs">{p.code}</span>
                {#if permissions.hasPermission('permissions:manage')}
                  <button
                    type="button"
                    class="ml-auto text-[11px] text-primary hover:underline"
                    onclick={(event) => {
                      event.preventDefault();
                      openPermissionEdit(p);
                    }}>Editar</button
                  >
                {/if}
              </label>
            {/each}
          </div>
        </div>
      {/each}
      <div class="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onclick={closeModal}>Cancelar</Button><Button
          type="submit"
          disabled={formLoading}>{formLoading ? 'Guardando...' : 'Guardar permisos'}</Button
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
      <FormField
        id="a-user"
        label="Usuario"
        bind:value={fUserId}
        oninput={loadSelectedUserRoles}
        options={[
          { value: '', label: '— Seleccionar —' },
          ...users.map((u) => ({ value: u.id, label: `${u.username} (${u.email})` }))
        ]}
      />
      <fieldset class="space-y-2" disabled={!fUserId || formLoading}>
        <legend class="mb-2 text-sm font-semibold text-foreground">
          Roles asignados
          <span class="font-normal text-foreground-muted">({selectedUserRoleIds.size})</span>
        </legend>
        <div class="max-h-64 space-y-2 overflow-y-auto rounded-xl border border-border p-3">
          {#each roles as role (role.id)}
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
