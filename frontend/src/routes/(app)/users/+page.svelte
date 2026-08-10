<script lang="ts">
  import { untrack } from 'svelte';
  import {
    api,
    HttpError,
    type BranchOut,
    type EmployeeOut,
    type RoleOut,
    type RoleWithPermissions,
    type UserOut
  } from '$lib/api/client';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import KebabMenu from '$lib/components/ui/KebabMenu.svelte';
  import Avatar from '$lib/components/ui/Avatar.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { queryClient } from '$lib/services/query-client';

  let users = $state<UserOut[]>([]);
  let meta = $state<{ page: number; size: number; total: number; pages: number } | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let page = $state(1);
  let size = $state(10);
  let actionLoading = $state<string | null>(null);
  let statusFilter = $state('');
  let roles = $state<RoleWithPermissions[]>([]);
  let rolesByUser = $state<Record<string, RoleOut[]>>({});
  let employees = $state<EmployeeOut[]>([]);
  let employeeByUser = $state<Record<string, EmployeeOut>>({});
  let success = $state<string | null>(null);
  let loadGeneration = 0;

  // Modal state
  let modalMode = $state<'create' | 'edit' | 'reset' | 'detail' | 'access' | null>(null);
  let modalUser = $state<UserOut | null>(null);
  let formError = $state<string | null>(null);
  let formLoading = $state(false);

  // Form fields
  let fUsername = $state('');
  let fEmail = $state('');
  let fPassword = $state('');
  let fIsSuperuser = $state(false);
  let fIsActive = $state(true);
  let fRoleIds = $state<Set<string>>(new Set());
  let originalRoleIds = $state<Set<string>>(new Set());
  let fEmployeeId = $state('');
  let accessBranches = $state<BranchOut[]>([]);
  let fAccessAllBranches = $state(false);
  let fBranchIds = $state<Set<string>>(new Set());
  let fDefaultBranchId = $state('');
  let roleQuery = $state('');
  let branchQuery = $state('');

  async function loadUsers(options: { force?: boolean } = {}) {
    const generation = ++loadGeneration;
    loading = true;
    error = null;
    try {
      await queryClient.cancelQueries({
        queryKey: ['users', 'list', company.id ?? 'all'],
        exact: false
      });
      const listKey = [
        'users',
        'list',
        company.id ?? 'all',
        branch.id ?? 'all',
        page,
        size,
        globalSearch.query,
        statusFilter
      ] as const;
      if (options.force) {
        await queryClient.invalidateQueries({
          queryKey: ['users', 'list', company.id ?? 'all'],
          exact: false
        });
      }
      const [result, roleCatalogue, employeePage] = await Promise.all([
        queryClient.fetchQuery({
          queryKey: listKey,
          staleTime: options.force ? 0 : 30_000,
          queryFn: ({ signal }) =>
            api.users.list({
              page,
              size,
              search: globalSearch.query || undefined,
              status: (statusFilter || undefined) as
                | 'active'
                | 'inactive'
                | 'superuser'
                | undefined,
              signal
            })
        }),
        permissions.hasPermission('roles:read')
          ? queryClient.fetchQuery({
              queryKey: ['catalogue', 'roles'],
              staleTime: 5 * 60_000,
              queryFn: () => api.roles.catalogue()
            })
          : Promise.resolve([]),
        permissions.hasPermission('employees:read')
          ? queryClient.fetchQuery({
              queryKey: [
                'catalogue',
                'employees',
                company.id ?? 'all',
                branch.id ?? 'all'
              ],
              staleTime: 2 * 60_000,
              queryFn: ({ signal }) => api.employees.list({ size: 100, signal })
            })
          : Promise.resolve({ items: [], meta: { page: 1, size: 100, total: 0, pages: 1 } })
      ]);
      const items = result.items;
      const batchRoles = permissions.hasPermission('roles:read') && items.length > 0
        ? await queryClient.fetchQuery({
            queryKey: [
              'users',
              'roles',
              company.id ?? 'all',
              branch.id ?? 'all',
              ...items.map((item) => item.id)
            ],
            staleTime: options.force ? 0 : 30_000,
            queryFn: ({ signal }) => api.users.rolesBatch(items.map((item) => item.id), signal)
          })
        : {};
      if (generation !== loadGeneration) return;
      users = items;
      roles = roleCatalogue;
      employees = employeePage.items;
      employeeByUser = Object.fromEntries(
        employeePage.items
          .filter((employee) => employee.user_id)
          .map((employee) => [employee.user_id!, employee])
      );
      rolesByUser = batchRoles;
      meta = result.meta;
    } catch (err) {
      if (generation !== loadGeneration || (err instanceof DOMException && err.name === 'AbortError'))
        return;
      if (err instanceof HttpError) error = err.message;
      else error = 'Error al cargar usuarios.';
    } finally {
      if (generation === loadGeneration) loading = false;
    }
  }

  function goToPage(p: number) {
    if (p < 1 || (meta && p > meta.pages)) return;
    page = p;
    loadUsers();
  }

  function openCreate() {
    modalMode = 'create';
    modalUser = null;
    formError = null;
    fUsername = '';
    fEmail = '';
    fPassword = '';
    fIsSuperuser = false;
    fIsActive = true;
    const defaultRole = roles.find((role) => role.name === 'EMPLEADO');
    fRoleIds = new Set(defaultRole ? [defaultRole.id] : []);
    originalRoleIds = new Set();
    fEmployeeId = '';
    roleQuery = '';
  }

  function openEdit(user: UserOut) {
    modalMode = 'edit';
    modalUser = user;
    formError = null;
    fIsActive = user.is_active;
    fIsSuperuser = user.is_superuser;
    const assigned = rolesByUser[user.id] ?? [];
    fRoleIds = new Set(assigned.map((role) => role.id));
    originalRoleIds = new Set(fRoleIds);
  }

  function openReset(user: UserOut) {
    modalMode = 'reset';
    modalUser = user;
    formError = null;
    fPassword = '';
  }

  function openDetail(user: UserOut) {
    modalMode = 'detail';
    modalUser = user;
    formError = null;
  }

  async function openBranchAccess(user: UserOut) {
    modalMode = 'access';
    modalUser = user;
    formError = null;
    branchQuery = '';
    formLoading = true;
    try {
      const [scope, catalogue] = await Promise.all([
        api.users.branchAccess(user.id),
        api.branches.list()
      ]);
      accessBranches = catalogue;
      fAccessAllBranches = scope.access_all_branches;
      fBranchIds = new Set(scope.access_all_branches ? [] : scope.branches.map((item) => item.id));
      fDefaultBranchId = scope.last_branch_id ?? '';
    } catch (err) {
      formError =
        err instanceof HttpError ? err.message : 'No se pudo cargar el acceso por sucursal.';
    } finally {
      formLoading = false;
    }
  }

  function toggleBranchAccess(branchId: string) {
    if (fBranchIds.has(branchId)) fBranchIds.delete(branchId);
    else fBranchIds.add(branchId);
    if (fDefaultBranchId && !fBranchIds.has(fDefaultBranchId)) fDefaultBranchId = '';
    fBranchIds = new Set(fBranchIds);
  }

  function closeModal() {
    modalMode = null;
    modalUser = null;
    formError = null;
  }

  async function handleSubmit() {
    formLoading = true;
    formError = null;
    try {
      if (modalMode === 'create') {
        await api.users.create({
          username: fUsername,
          email: fEmail,
          password: fPassword,
          is_superuser: fIsSuperuser,
          employee_id: fEmployeeId || undefined,
          role_ids: [...fRoleIds]
        });
        success = 'Usuario creado correctamente.';
      } else if (modalMode === 'edit' && modalUser) {
        await api.users.update(modalUser.id, { is_active: fIsActive, is_superuser: fIsSuperuser });
        if (
          permissions.hasPermission('roles:assign') ||
          permissions.hasPermission('roles:revoke')
        ) {
          const toAssign = [...fRoleIds].filter((roleId) => !originalRoleIds.has(roleId));
          const toRevoke = [...originalRoleIds].filter((roleId) => !fRoleIds.has(roleId));
          for (const roleId of toAssign) await api.roles.assign(modalUser.id, roleId);
          for (const roleId of toRevoke) await api.roles.revoke(modalUser.id, roleId);
        }
        success = 'Usuario actualizado correctamente.';
      } else if (modalMode === 'reset' && modalUser) {
        await api.users.forcePasswordReset(modalUser.id, fPassword);
        success = 'Contraseña restablecida correctamente.';
      } else if (modalMode === 'access' && modalUser) {
        await api.users.setBranchAccess(modalUser.id, {
          access_all_branches: fAccessAllBranches,
          branch_ids: fAccessAllBranches ? [] : [...fBranchIds],
          default_branch_id: fDefaultBranchId || null
        });
        success = 'Acceso por sucursal actualizado correctamente.';
      }
      closeModal();
      await loadUsers({ force: true });
    } catch (err) {
      formError = err instanceof HttpError ? err.message : 'Error inesperado.';
    } finally {
      formLoading = false;
    }
  }

  async function toggleActive(user: UserOut) {
    if (actionLoading) return;
    if (user.is_active) {
      confirmation.request({
        kind: 'deactivate',
        title: 'Desactivar usuario',
        description:
          'El usuario perderá el acceso al ERP hasta que vuelva a activarse. Sus datos y asignaciones se conservarán.',
        resourceName: user.username,
        confirmLabel: 'Desactivar usuario',
        execute: async () => {
          actionLoading = user.id;
          try {
            await api.users.update(user.id, { is_active: false });
            success = 'Usuario desactivado.';
            await loadUsers({ force: true });
          } finally {
            actionLoading = null;
          }
        }
      });
      return;
    }
    actionLoading = user.id;
    try {
      await api.users.update(user.id, { is_active: true });
      success = 'Usuario activado.';
      await loadUsers({ force: true });
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error.';
    } finally {
      actionLoading = null;
    }
  }

  async function unlockUser(user: UserOut) {
    if (actionLoading) return;
    actionLoading = user.id;
    try {
      await api.users.unlock(user.id);
      success = 'Usuario desbloqueado.';
      await loadUsers({ force: true });
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error.';
    } finally {
      actionLoading = null;
    }
  }

  function toggleCreateRole(roleId: string) {
    if (fRoleIds.has(roleId)) fRoleIds.delete(roleId);
    else fRoleIds.add(roleId);
    fRoleIds = new Set(fRoleIds);
  }

  function employeeName(userId: string): string {
    const employee = employeeByUser[userId];
    return employee ? `${employee.first_name} ${employee.last_name}` : 'Sin empleado vinculado';
  }

  let availableEmployees = $derived(employees.filter((employee) => !employee.user_id));
  let filteredRoles = $derived(
    roles.filter((role) =>
      `${role.name} ${role.description ?? ''}`.toLocaleLowerCase('es').includes(roleQuery.trim().toLocaleLowerCase('es'))
    )
  );
  let filteredAccessBranches = $derived(
    accessBranches.filter((item) =>
      `${item.name} ${item.code}`.toLocaleLowerCase('es').includes(branchQuery.trim().toLocaleLowerCase('es'))
    )
  );

  $effect(() => {
    // La búsqueda es la única dependencia reactiva de este efecto. Sin
    // `untrack`, las lecturas de `page` dentro de loadUsers() hacen que cada
    // intento de paginar vuelva a ejecutar el efecto y restablezca la página 1.
    globalSearch.query;
    untrack(() => {
      page = 1;
      void loadUsers();
    });
  });
</script>

<svelte:head><title>Usuarios — GestionaSV</title></svelte:head>

<div class="p-6 md:p-8">
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">{meta ? `${meta.total} usuario(s)` : 'Cargando...'}</p>
    <div class="flex items-center gap-2">
      <select
        bind:value={statusFilter}
        onchange={() => {
          page = 1;
          loadUsers();
        }}
        class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
      >
        <option value="">Todos</option>
        <option value="active">Activos</option>
        <option value="inactive">Inactivos</option>
        <option value="superuser">Super admins</option>
      </select>
      {#if permissions.hasPermission('users:create')}
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
      class="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {/if}
  {#if success}
    <div
      class="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success"
      role="status"
    >
      {success}
    </div>
  {/if}

  <Card class="overflow-hidden p-0">
    {#if loading}
      <div class="flex items-center justify-center py-16">
        <p class="text-sm text-foreground-muted">Cargando...</p>
      </div>
    {:else if users.length === 0}
      <div class="flex flex-col items-center justify-center py-16">
        <p class="text-sm text-foreground-muted">No se encontraron usuarios.</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="border-b border-border bg-surface-muted">
            <tr>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Usuario</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Correo</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Estado</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Rol</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Empleado</th>
              <th class="px-2 py-3 text-center font-semibold text-foreground w-11"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each users as user (user.id)}
              <tr class="hover:bg-surface-muted">
                <td class="px-4 py-3">
                  <button
                    class="flex items-center gap-2.5 font-medium text-foreground hover:text-primary"
                    onclick={() => openDetail(user)}
                  >
                    <Avatar initials={user.username.substring(0, 2)} size={24} />
                    {user.username}
                  </button>
                </td>
                <td class="px-4 py-3 text-foreground-muted">{user.email}</td>
                <td class="px-4 py-3">
                  {#if user.locked_until}
                    <span
                      class="badge-warning inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"
                      ><span class="h-1.5 w-1.5 rounded-full bg-warning"></span> Bloqueado</span
                    >
                  {:else if user.is_active}
                    <span
                      class="badge-success inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"
                      ><span class="h-1.5 w-1.5 rounded-full bg-success"></span> Activo</span
                    >
                  {:else}
                    <span
                      class="badge-neutral inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"
                      ><span class="h-1.5 w-1.5 rounded-full bg-foreground-muted"></span> Inactivo</span
                    >
                  {/if}
                </td>
                <td class="px-4 py-3 text-foreground-muted"
                  >{user.is_superuser
                    ? 'Super Admin'
                    : (rolesByUser[user.id] ?? []).map((role) => role.name).join(', ') ||
                      'Sin rol'}</td
                >
                <td class="px-4 py-3 text-foreground-muted">{employeeName(user.id)}</td>
                <td class="px-2 py-3 text-center">
                  <KebabMenu
                    items={[
                      {
                        id: 'detail',
                        label: 'Ver detalle',
                        icon: 'detail',
                        onClick: () => openDetail(user)
                      },
                      ...(permissions.hasPermission('users:update')
                        ? [
                            {
                              id: 'edit',
                              label: 'Editar',
                              icon: 'edit' as const,
                              onClick: () => openEdit(user)
                            },
                            {
                              id: 'branch-access',
                              label: 'Acceso a sucursales',
                              icon: 'detail' as const,
                              onClick: () => openBranchAccess(user)
                            }
                          ]
                        : []),
                      ...(permissions.hasPermission('users:force_password_reset')
                        ? [
                            {
                              id: 'reset',
                              label: 'Resetear contraseña',
                              icon: 'key',
                              onClick: () => openReset(user)
                            } as const
                          ]
                        : []),
                      ...(user.locked_until && permissions.hasPermission('users:unlock')
                        ? [
                            {
                              id: 'unlock',
                              label: 'Desbloquear',
                              icon: 'unlock' as const,
                              onClick: () => unlockUser(user)
                            }
                          ]
                        : []),
                      ...(permissions.hasPermission('users:update')
                        ? [
                            {
                              id: 'toggle',
                              label: user.is_active ? 'Desactivar' : 'Activar',
                              icon: 'power',
                              variant: user.is_active ? 'danger' : 'default',
                              onClick: () => toggleActive(user)
                            } as const
                          ]
                        : [])
                    ]}
                  />
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </Card>

  {#if meta && meta.pages > 1}
    <div class="mt-4 flex items-center justify-between">
      <p class="text-xs text-foreground-muted">Página {meta.page} de {meta.pages}</p>
      <div class="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          onclick={() => goToPage(meta!.page - 1)}
          disabled={meta!.page <= 1}>Anterior</Button
        >
        <Button
          variant="secondary"
          size="sm"
          onclick={() => goToPage(meta!.page + 1)}
          disabled={meta!.page >= meta!.pages}>Siguiente</Button
        >
      </div>
    </div>
  {/if}
</div>

<!-- Modal: Crear / Editar / Resetear / Detalle -->
<Modal
  open={modalMode !== null}
  title={modalMode === 'create'
    ? 'Crear usuario'
    : modalMode === 'edit'
      ? 'Editar usuario'
      : modalMode === 'reset'
        ? 'Resetear contraseña'
        : modalMode === 'access'
          ? 'Acceso a sucursales'
          : 'Detalle del usuario'}
  onclose={closeModal}
  size={modalMode === 'detail' || modalMode === 'access' ? 'lg' : 'md'}
>
  {#if modalMode === 'create'}
    <form
      onsubmit={(e) => {
        e.preventDefault();
        handleSubmit();
      }}
      class="space-y-4"
    >
      {#if formError}<div
          class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2 text-sm text-danger"
        >
          {formError}
        </div>{/if}
      <FormField
        id="f-username"
        label="Nombre de usuario"
        bind:value={fUsername}
        required
        placeholder="usuario123"
      />
      <FormField
        id="f-email"
        label="Correo electrónico"
        type="email"
        bind:value={fEmail}
        required
        placeholder="usuario@ejemplo.com"
      />
      <FormField
        id="f-password"
        label="Contraseña"
        type="password"
        bind:value={fPassword}
        required
        placeholder="Mínimo 12 caracteres"
        min="12"
      />
      <label class="flex items-center gap-2 text-sm text-foreground"
        ><input type="checkbox" bind:checked={fIsSuperuser} class="rounded" /> Super administrador</label
      >
      {#if permissions.hasAnyPermission(['roles:assign', 'roles:revoke'])}
        <fieldset class="rounded-xl border border-border bg-surface-muted/40 p-3">
          <legend class="px-1 text-xs font-semibold text-foreground-muted">Roles asignados</legend>
          <input
            aria-label="Buscar roles"
            placeholder="Buscar rol por nombre o descripción…"
            bind:value={roleQuery}
            class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <div class="mt-1 grid gap-2 sm:grid-cols-2">
            {#if filteredRoles.length === 0}
              <p class="col-span-2 px-2 py-4 text-center text-xs text-foreground-muted">No se encontraron roles.</p>
            {/if}
            {#each filteredRoles as role (role.id)}
              <label
                class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-hover"
              >
                <input
                  type="checkbox"
                  checked={fRoleIds.has(role.id)}
                  onchange={() => toggleCreateRole(role.id)}
                />
                <span>{role.name}</span>
              </label>
            {/each}
          </div>
          {#if fRoleIds.size === 0}<p class="mt-2 text-xs text-danger">
              El usuario debe conservar al menos un rol.
            </p>{/if}
        </fieldset>
      {/if}
      {#if permissions.hasPermission('employees:update')}
        <SmartSelect
          id="f-employee"
          label="Empleado vinculado"
          bind:value={fEmployeeId}
          placeholder="Buscar empleado por código o nombre…"
          options={[
            { value: '', label: 'Crear ficha de empleado automáticamente' },
            ...availableEmployees.map((employee) => ({
              value: employee.id,
              label: `${employee.first_name} ${employee.last_name}`,
              description: employee.employee_code
            }))
          ]}
        />
        <p class="-mt-2 text-xs leading-relaxed text-foreground-muted">
          Si no selecciona un empleado existente, el sistema creará y vinculará una ficha
          provisional usando los datos del usuario.
        </p>
      {/if}
      <div class="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onclick={closeModal}>Cancelar</Button><Button
          type="submit"
          disabled={formLoading}>{formLoading ? 'Guardando...' : 'Crear'}</Button
        >
      </div>
    </form>
  {:else if modalMode === 'edit' && modalUser}
    <form
      onsubmit={(e) => {
        e.preventDefault();
        handleSubmit();
      }}
      class="space-y-4"
    >
      {#if formError}<div
          class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2 text-sm text-danger"
        >
          {formError}
        </div>{/if}
      <div>
        <p class="mb-1 text-sm font-medium text-foreground">Usuario</p>
        <p class="text-sm text-foreground-muted">{modalUser.username} · {modalUser.email}</p>
      </div>
      <label class="flex items-center gap-2 text-sm text-foreground"
        ><input type="checkbox" bind:checked={fIsActive} class="rounded" /> Activo</label
      >
      <label class="flex items-center gap-2 text-sm text-foreground"
        ><input type="checkbox" bind:checked={fIsSuperuser} class="rounded" /> Super administrador</label
      >
      <div class="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onclick={closeModal}>Cancelar</Button><Button
          type="submit"
          disabled={formLoading || (!fIsSuperuser && fRoleIds.size === 0)}
          >{formLoading ? 'Guardando...' : 'Guardar'}</Button
        >
      </div>
    </form>
  {:else if modalMode === 'access' && modalUser}
    <form
      onsubmit={(e) => {
        e.preventDefault();
        handleSubmit();
      }}
      class="space-y-4"
    >
      <div>
        <p class="text-sm font-semibold text-foreground">{modalUser.username}</p>
        <p class="mt-1 text-xs text-foreground-muted">
          Este alcance controla los datos administrativos que puede consultar. No modifica la
          sucursal laboral de su empleado.
        </p>
      </div>
      {#if formError}<div
          class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
          role="alert"
        >
          {formError}
        </div>{/if}
      {#if formLoading}
        <div class="h-28 rounded-xl border border-border skeleton"></div>
      {:else if modalUser.is_superuser}
        <div class="rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm text-foreground">
          Los superadministradores tienen acceso automático a todas las sucursales.
        </div>
      {:else}
        <label
          class="flex cursor-pointer items-start gap-3 rounded-xl border border-border p-4 hover:bg-surface-hover"
        >
          <input type="checkbox" bind:checked={fAccessAllBranches} class="mt-0.5 rounded" />
          <span
            ><span class="block text-sm font-semibold text-foreground">Todas las sucursales</span
            ><span class="mt-1 block text-xs text-foreground-muted"
              >Incluye automáticamente las sucursales que se creen en el futuro.</span
            ></span
          >
        </label>
        {#if !fAccessAllBranches}
          <fieldset class="rounded-xl border border-border p-3">
            <legend class="px-1 text-xs font-semibold text-foreground-muted"
              >Sucursales autorizadas</legend
            >
            <input
              aria-label="Buscar sucursales autorizadas"
              placeholder="Buscar por nombre o código…"
              bind:value={branchQuery}
              class="mb-2 mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <div class="mt-1 grid max-h-64 gap-1 overflow-y-auto sm:grid-cols-2">
              {#if filteredAccessBranches.length === 0}
                <p class="col-span-2 px-2 py-4 text-center text-xs text-foreground-muted">No se encontraron sucursales.</p>
              {/if}
              {#each filteredAccessBranches as item (item.id)}
                <label
                  class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-surface-hover"
                >
                  <input
                    type="checkbox"
                    checked={fBranchIds.has(item.id)}
                    onchange={() => toggleBranchAccess(item.id)}
                  />
                  <span class="min-w-0"
                    ><span class="block truncate font-medium">{item.name}</span><span
                      class="block truncate text-xs text-foreground-muted">{item.code}</span
                    ></span
                  >
                </label>
              {/each}
            </div>
            {#if fBranchIds.size === 0}<p class="mt-2 text-xs text-danger">
                Seleccione al menos una sucursal.
              </p>{/if}
          </fieldset>
        {/if}
        <SmartSelect
          id="default-branch"
          label="Sucursal predeterminada"
          bind:value={fDefaultBranchId}
          placeholder="Buscar sucursal predeterminada…"
          options={[
            { value: '', label: fAccessAllBranches ? 'Todas las sucursales' : 'Seleccione…' },
            ...accessBranches
              .filter((item) => fAccessAllBranches || fBranchIds.has(item.id))
              .map((item) => ({ value: item.id, label: item.name, description: item.code }))
          ]}
        />
      {/if}
      <div class="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onclick={closeModal}>Cancelar</Button>
        {#if !modalUser.is_superuser}<Button
            type="submit"
            disabled={formLoading || (!fAccessAllBranches && fBranchIds.size === 0)}
            >{formLoading ? 'Guardando…' : 'Guardar acceso'}</Button
          >{/if}
      </div>
    </form>
  {:else if modalMode === 'reset' && modalUser}
    <form
      onsubmit={(e) => {
        e.preventDefault();
        handleSubmit();
      }}
      class="space-y-4"
    >
      {#if formError}<div
          class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2 text-sm text-danger"
        >
          {formError}
        </div>{/if}
      <p class="text-sm text-foreground-muted">
        Nueva contraseña para <strong>{modalUser.username}</strong>
      </p>
      <FormField
        id="f-newpass"
        label="Nueva contraseña"
        type="password"
        bind:value={fPassword}
        required
        min="12"
        placeholder="Mínimo 12 caracteres"
      />
      <div class="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onclick={closeModal}>Cancelar</Button><Button
          type="submit"
          disabled={formLoading}>{formLoading ? 'Guardando...' : 'Resetear'}</Button
        >
      </div>
    </form>
  {:else if modalMode === 'detail' && modalUser}
    <dl class="space-y-3 text-sm">
      <div class="flex justify-between">
        <dt class="text-foreground-muted">ID</dt>
        <dd class="font-mono text-xs text-foreground">{modalUser.id}</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-foreground-muted">Usuario</dt>
        <dd class="text-foreground">{modalUser.username}</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-foreground-muted">Correo</dt>
        <dd class="text-foreground">{modalUser.email}</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-foreground-muted">Estado</dt>
        <dd class="text-foreground">{modalUser.is_active ? 'Activo' : 'Inactivo'}</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-foreground-muted">Roles</dt>
        <dd class="text-foreground">
          {modalUser.is_superuser
            ? 'Super Admin'
            : (rolesByUser[modalUser.id] ?? []).map((role) => role.name).join(', ') || 'Sin rol'}
        </dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-foreground-muted">Empleado</dt>
        <dd class="text-foreground">{employeeName(modalUser.id)}</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-foreground-muted">Intentos fallidos</dt>
        <dd class="text-foreground">{modalUser.failed_login_attempts}</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-foreground-muted">Bloqueado hasta</dt>
        <dd class="text-foreground">
          {modalUser.locked_until ? new Date(modalUser.locked_until).toLocaleString('es-ES') : '—'}
        </dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-foreground-muted">Último login</dt>
        <dd class="text-foreground">
          {modalUser.last_login_at
            ? new Date(modalUser.last_login_at).toLocaleString('es-ES')
            : '—'}
        </dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-foreground-muted">Creado</dt>
        <dd class="text-foreground">{new Date(modalUser.created_at).toLocaleString('es-ES')}</dd>
      </div>
    </dl>
    <div class="mt-4 flex justify-end">
      <Button variant="secondary" onclick={closeModal}>Cerrar</Button>
    </div>
  {/if}
</Modal>
