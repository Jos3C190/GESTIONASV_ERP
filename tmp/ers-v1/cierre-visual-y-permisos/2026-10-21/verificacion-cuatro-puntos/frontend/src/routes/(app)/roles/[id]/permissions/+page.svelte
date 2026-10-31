<script lang="ts">
  import { beforeNavigate, goto } from '$app/navigation';
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { api, HttpError, type PermissionOut, type RoleWithPermissions } from '$lib/api/client';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  let roleId = $derived(page.params.id ?? '');
  let role = $state<RoleWithPermissions | null>(null);
  let allPermissions = $state<PermissionOut[]>([]);
  let selectedPerms = $state<Set<string>>(new Set());
  let initialSnapshot = $state('');
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let search = $state('');
  let moduleFilter = $state('');
  let pendingTarget = $state<string | null>(null);
  let bypassNavigationGuard = $state(false);
  let editingPermission = $state<PermissionOut | null>(null);
  let permissionModalOpen = $state(false);
  let permissionSaving = $state(false);
  let permissionError = $state<string | null>(null);
  let permissionCode = $state('');
  let permissionModule = $state('');
  let permissionDescription = $state('');

  let canManage = $derived(permissions.hasPermission('permissions:manage'));
  let dirty = $derived(!loading && initialSnapshot !== snapshot(selectedPerms));
  let selectedCount = $derived(selectedPerms.size);
  let totalCount = $derived(allPermissions.length);
  let progress = $derived(totalCount ? Math.round((selectedCount / totalCount) * 100) : 0);
  let moduleOptions = $derived(
    [
      ...new Set(allPermissions.map((permission) => permission.module).filter(Boolean) as string[])
    ].sort((a, b) => a.localeCompare(b, 'es'))
  );
  let filteredPermissions = $derived.by(() => {
    const query = search.trim().toLocaleLowerCase('es');
    return allPermissions.filter((permission) => {
      const module = permission.module ?? 'otros';
      const matchesModule = !moduleFilter || module === moduleFilter;
      const text = `${permission.code} ${module} ${permission.description ?? ''}`.toLocaleLowerCase(
        'es'
      );
      return matchesModule && (!query || text.includes(query));
    });
  });
  let groupedPermissions = $derived.by(() => {
    const groups: Record<string, PermissionOut[]> = {};
    for (const permission of filteredPermissions) {
      (groups[permission.module ?? 'otros'] ??= []).push(permission);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b, 'es'));
  });
  let visibleCodes = $derived(filteredPermissions.map((permission) => permission.code));

  function snapshot(values: Set<string>) {
    return JSON.stringify([...values].sort());
  }

  async function load() {
    if (!roleId) {
      error = 'El rol solicitado no es válido.';
      loading = false;
      return;
    }
    loading = true;
    error = null;
    try {
      const [loadedRole, permissionsCatalogue] = await Promise.all([
        api.roles.get(roleId),
        api.roles.listPermissions()
      ]);
      role = loadedRole;
      allPermissions = permissionsCatalogue;
      selectedPerms = new Set(loadedRole.permissions.map((permission) => permission.code));
      initialSnapshot = snapshot(selectedPerms);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar la matriz de permisos.';
    } finally {
      loading = false;
    }
  }

  function togglePermission(code: string) {
    if (!canManage) return;
    const next = new Set(selectedPerms);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    selectedPerms = next;
    success = null;
  }

  function setVisible(value: boolean) {
    if (!canManage) return;
    const next = new Set(selectedPerms);
    for (const code of visibleCodes) {
      if (value) next.add(code);
      else next.delete(code);
    }
    selectedPerms = next;
    success = null;
  }

  async function save() {
    if (!role || !canManage || saving || !dirty) return;
    saving = true;
    error = null;
    success = null;
    try {
      const updated = await api.roles.setPermissions(role.id, [...selectedPerms]);
      role = updated;
      selectedPerms = new Set(updated.permissions.map((permission) => permission.code));
      initialSnapshot = snapshot(selectedPerms);
      success = 'Matriz de permisos actualizada correctamente.';
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo guardar la matriz de permisos.';
    } finally {
      saving = false;
    }
  }

  function requestLeave(target: string) {
    if (!dirty || saving) {
      void goto(target);
      return;
    }
    pendingTarget = target;
  }

  function discardAndLeave() {
    const target = pendingTarget ?? '/roles';
    pendingTarget = null;
    bypassNavigationGuard = true;
    void goto(target);
  }

  function openPermissionEdit(permission: PermissionOut) {
    if (!canManage || permission.is_protected) return;
    editingPermission = permission;
    permissionCode = permission.code;
    permissionModule = permission.module ?? '';
    permissionDescription = permission.description ?? '';
    permissionError = null;
    permissionModalOpen = true;
  }

  function closePermissionEdit() {
    if (permissionSaving) return;
    permissionModalOpen = false;
    editingPermission = null;
    permissionError = null;
  }

  async function savePermissionEdit() {
    if (!editingPermission || permissionSaving) return;
    permissionSaving = true;
    permissionError = null;
    try {
      const updated = await api.roles.updatePermission(editingPermission.id, {
        code: permissionCode.trim(),
        module: permissionModule.trim() || undefined,
        description: permissionDescription.trim() || undefined
      });
      allPermissions = allPermissions.map((permission) =>
        permission.id === updated.id ? updated : permission
      );
      role = role
        ? {
            ...role,
            permissions: role.permissions.map((permission) =>
              permission.id === updated.id ? updated : permission
            )
          }
        : role;
      if (selectedPerms.has(editingPermission.code) && updated.code !== editingPermission.code) {
        const next = new Set(selectedPerms);
        next.delete(editingPermission.code);
        next.add(updated.code);
        selectedPerms = next;
        initialSnapshot = snapshot(selectedPerms);
      }
      success = 'Permiso actualizado correctamente.';
      permissionModalOpen = false;
      editingPermission = null;
    } catch (err) {
      permissionError =
        err instanceof HttpError ? err.message : 'No se pudo actualizar el permiso.';
    } finally {
      permissionSaving = false;
    }
  }

  beforeNavigate((navigation) => {
    if (bypassNavigationGuard) {
      bypassNavigationGuard = false;
      return;
    }
    if (dirty && !saving) {
      navigation.cancel();
      pendingTarget = navigation.to?.url.pathname ?? '/roles';
    }
  });

  onMount(() => {
    void load();
  });
</script>

<svelte:head>
  <title>{role ? `Permisos de ${role.name} — Roles` : 'Matriz de permisos — Roles'}</title>
</svelte:head>

<div class="min-h-full p-6 md:p-8">
  <div class="mx-auto max-w-[1440px]">
    <header class="mb-7 flex flex-wrap items-start justify-between gap-4">
      <div class="flex min-w-0 items-start gap-3">
        <button
          type="button"
          class="mt-1 flex h-9 w-9 flex-none items-center justify-center rounded-lg text-foreground-muted transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          aria-label="Volver a roles"
          onclick={() => requestLeave('/roles')}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
          </svg>
        </button>
        <div class="min-w-0">
          <p class="text-xs font-medium uppercase tracking-[0.12em] text-foreground-subtle">
            Roles y permisos
          </p>
          <h1 class="mt-1 text-2xl font-bold tracking-tight text-foreground md:text-3xl">
            Matriz de permisos
          </h1>
          <p class="mt-1 text-sm text-foreground-muted">
            Asigna el acceso de forma clara y auditable para cada rol.
          </p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        {#if dirty}<Badge variant="warning">Cambios sin guardar</Badge>{/if}
        <Button variant="secondary" onclick={() => requestLeave('/roles')}>Cancelar</Button>
        {#if canManage}
          <Button disabled={saving || !dirty} onclick={save}>
            {saving ? 'Guardando…' : 'Guardar cambios'}
          </Button>
        {/if}
      </div>
    </header>

    {#if loading}
      <div class="space-y-5" aria-label="Cargando matriz">
        <div class="h-48 rounded-2xl border border-border skeleton"></div>
        <div class="h-28 rounded-2xl border border-border skeleton"></div>
        <div class="grid gap-5 md:grid-cols-2">
          <div class="h-64 rounded-2xl border border-border skeleton"></div>
          <div class="h-64 rounded-2xl border border-border skeleton"></div>
        </div>
      </div>
    {:else if error && !role}
      <Card class="p-10">
        <div class="mx-auto max-w-lg text-center">
          <div
            class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-danger/10 text-danger"
          >
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></svg
            >
          </div>
          <h2 class="text-lg font-semibold text-foreground">No se pudo cargar la matriz</h2>
          <p class="mt-2 text-sm text-foreground-muted">{error}</p>
          <Button class="mt-6" variant="secondary" onclick={() => requestLeave('/roles')}
            >Volver a roles</Button
          >
        </div>
      </Card>
    {:else if role}
      {#if error}<div
          class="mb-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
          role="alert"
        >
          {error}
        </div>{/if}
      {#if success}<div
          class="mb-4 rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-success"
          role="status"
        >
          {success}
        </div>{/if}

      {#if pendingTarget}
        <div
          class="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
          role="alert"
        >
          <span>Hay cambios sin guardar. ¿Deseas descartarlos?</span>
          <div class="flex gap-2">
            <Button size="sm" variant="secondary" onclick={() => (pendingTarget = null)}
              >Continuar editando</Button
            >
            <Button size="sm" variant="warning" onclick={discardAndLeave}>Descartar cambios</Button>
          </div>
        </div>
      {/if}

      <Card class="mb-5 overflow-hidden p-0">
        <div class="flex flex-wrap items-start justify-between gap-6 p-6 md:p-7">
          <div class="flex min-w-0 items-start gap-4">
            <div
              class="flex h-14 w-14 flex-none items-center justify-center rounded-2xl bg-primary/10 text-primary"
            >
              <svg
                width="26"
                height="26"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                aria-hidden="true"
                ><path d="M12 3 5 6v5c0 4.5 2.9 8.5 7 10 4.1-1.5 7-5.5 7-10V6l-7-3Z" /><path
                  d="m9 12 2 2 4-4"
                /></svg
              >
            </div>
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <h2 class="text-xl font-bold text-foreground">{role.name}</h2>
                {#if role.is_system}<Badge variant="primary">Rol del sistema</Badge>{:else}<Badge
                    variant="neutral">Personalizado</Badge
                  >{/if}
              </div>
              <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
                {role.description ?? 'Este rol no tiene descripción.'}
              </p>
              <p class="mt-4 text-xs text-foreground-subtle">
                {canManage
                  ? 'Puedes ajustar los permisos y guardar la matriz en una sola operación.'
                  : 'Tienes acceso de lectura. Solicita permissions:manage para modificarla.'}
              </p>
            </div>
          </div>
          <div class="min-w-[180px] text-right">
            <p class="text-xs font-semibold uppercase tracking-[0.1em] text-foreground-subtle">
              Cobertura
            </p>
            <p class="mt-1 text-3xl font-bold tabular-nums text-foreground">
              {selectedCount}<span class="text-base font-normal text-foreground-muted">
                / {totalCount}</span
              >
            </p>
            <p class="text-xs text-foreground-muted">{progress}% del catálogo asignado</p>
          </div>
        </div>
        <div class="h-1.5 bg-surface-muted">
          <div
            class="h-full bg-primary transition-all duration-300"
            style={`width: ${progress}%`}
          ></div>
        </div>
      </Card>

      {#if !canManage}
        <div
          class="mb-5 flex items-start gap-3 rounded-xl border border-primary/25 bg-primary/10 px-4 py-3 text-sm text-primary"
          role="status"
        >
          <svg
            class="mt-0.5 flex-none"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg
          >
          <span
            ><strong>Modo lectura.</strong> Puedes consultar la matriz, pero no modificar permisos.</span
          >
        </div>
      {/if}

      <Card class="mb-5 p-4 md:p-5">
        <div class="flex flex-col gap-3 lg:flex-row lg:items-center">
          <label class="relative min-w-0 flex-1">
            <span class="sr-only">Buscar permisos</span>
            <svg
              class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle"
              width="17"
              height="17"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg
            >
            <input
              bind:value={search}
              placeholder="Buscar por código, módulo o descripción…"
              class="h-10 w-full rounded-lg border border-border bg-surface px-3 pl-10 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </label>
          <select
            bind:value={moduleFilter}
            aria-label="Filtrar por módulo"
            class="h-10 rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary lg:w-56"
          >
            <option value="">Todos los módulos</option>
            {#each moduleOptions as module (module)}<option value={module}>{module}</option>{/each}
          </select>
          {#if canManage}
            <div class="flex gap-2">
              <Button
                size="sm"
                variant="secondary"
                disabled={!visibleCodes.length}
                onclick={() => setVisible(true)}>Seleccionar visibles</Button
              >
              <Button
                size="sm"
                variant="ghost"
                disabled={!visibleCodes.length}
                onclick={() => setVisible(false)}>Quitar visibles</Button
              >
            </div>
          {/if}
        </div>
        <div class="mt-3 flex items-center justify-between text-xs text-foreground-muted">
          <span>{filteredPermissions.length} permiso(s) visibles</span>
          <span>{selectedCount} seleccionado(s)</span>
        </div>
      </Card>

      {#if groupedPermissions.length === 0}
        <Card class="p-12 text-center"
          ><p class="text-sm text-foreground-muted">
            No se encontraron permisos con esos filtros.
          </p></Card
        >
      {:else}
        <div class="grid gap-5 xl:grid-cols-2">
          {#each groupedPermissions as [module, modulePermissions] (module)}
            {@const moduleSelected = modulePermissions.filter((permission) =>
              selectedPerms.has(permission.code)
            ).length}
            <Card class="p-0">
              <div class="flex items-center justify-between border-b border-border px-5 py-4">
                <div>
                  <h3 class="text-sm font-bold uppercase tracking-[0.1em] text-foreground">
                    {module}
                  </h3>
                  <p class="mt-1 text-xs text-foreground-muted">
                    {moduleSelected} de {modulePermissions.length} asignados
                  </p>
                </div>
                <span
                  class="inline-flex min-w-8 items-center justify-center rounded-full border border-border bg-surface-muted px-2 py-1 text-xs font-semibold tabular-nums text-foreground-muted"
                  >{modulePermissions.length}</span
                >
              </div>
              <div class="grid gap-1 p-3 sm:grid-cols-2">
                {#each modulePermissions as permission (permission.id)}
                  <div
                    class={`group flex min-w-0 items-start gap-3 rounded-xl px-3 py-3 transition-colors ${canManage ? 'cursor-pointer hover:bg-surface-hover' : 'cursor-default'} ${selectedPerms.has(permission.code) ? 'bg-primary/5' : ''}`}
                  >
                    <label
                      class={`flex min-w-0 flex-1 items-start gap-3 ${canManage ? 'cursor-pointer' : 'cursor-default'}`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedPerms.has(permission.code)}
                        disabled={!canManage}
                        onchange={() => togglePermission(permission.code)}
                        aria-label={permission.code}
                        class="mt-0.5 h-4 w-4 rounded border-border text-primary focus:ring-primary disabled:opacity-50"
                      />
                      <span class="min-w-0 flex-1">
                        <span
                          class="block truncate font-mono text-xs font-medium text-foreground"
                          title={permission.code}>{permission.code}</span
                        >
                        {#if permission.description}<span
                            class="mt-1 block line-clamp-2 text-xs leading-5 text-foreground-muted"
                            >{permission.description}</span
                          >{/if}
                      </span>
                    </label>
                    {#if permission.is_protected}<span
                        class="mt-0.5 rounded-md bg-surface-muted px-1.5 py-0.5 text-[10px] text-foreground-subtle"
                        >Sistema</span
                      >{:else if canManage}<button
                        type="button"
                        class="invisible rounded-md px-1.5 py-0.5 text-[11px] text-primary hover:bg-primary/10 group-hover:visible focus-visible:visible"
                        onclick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          openPermissionEdit(permission);
                        }}>Editar</button
                      >{/if}
                  </div>
                {/each}
              </div>
            </Card>
          {/each}
        </div>
      {/if}

      {#if canManage}
        <div
          class="sticky bottom-4 z-10 mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-surface-elevated/95 px-4 py-3 shadow-lg backdrop-blur md:px-5"
        >
          <p class="text-sm text-foreground-muted">
            <strong class="text-foreground">{selectedCount}</strong> de {totalCount} permisos seleccionados
          </p>
          <div class="flex items-center gap-2">
            <Button
              variant="secondary"
              disabled={!dirty || saving}
              onclick={() => (selectedPerms = new Set(JSON.parse(initialSnapshot) as string[]))}
              >Descartar</Button
            ><Button disabled={saving || !dirty} onclick={save}
              >{saving ? 'Guardando…' : 'Guardar cambios'}</Button
            >
          </div>
        </div>
      {/if}
    {/if}
  </div>
</div>

<Modal open={permissionModalOpen} title="Editar permiso" onclose={closePermissionEdit} size="md">
  <form
    class="space-y-4"
    onsubmit={(event) => {
      event.preventDefault();
      void savePermissionEdit();
    }}
  >
    {#if permissionError}<div
        class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-2.5 text-sm text-danger"
        role="alert"
      >
        {permissionError}
      </div>{/if}
    <FormField
      id="matrix-permission-code"
      label="Código"
      bind:value={permissionCode}
      required
      placeholder="recurso.acción"
    />
    <FormField
      id="matrix-permission-module"
      label="Módulo"
      bind:value={permissionModule}
      placeholder="inventario"
    />
    <FormField
      id="matrix-permission-description"
      label="Descripción"
      bind:value={permissionDescription}
      placeholder="Qué permite realizar"
    />
    <div class="flex justify-end gap-2 pt-2">
      <Button variant="secondary" onclick={closePermissionEdit}>Cancelar</Button><Button
        type="submit"
        disabled={permissionSaving}>{permissionSaving ? 'Guardando…' : 'Guardar permiso'}</Button
      >
    </div>
  </form>
</Modal>
