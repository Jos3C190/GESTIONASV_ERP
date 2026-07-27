<script lang="ts">
  import { api, HttpError, type UserOut, type Page } from '$lib/api/client';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import KebabMenu from '$lib/components/ui/KebabMenu.svelte';
  import Avatar from '$lib/components/ui/Avatar.svelte';

  let users = $state<UserOut[]>([]);
  let meta = $state<{ page: number; size: number; total: number; pages: number } | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let page = $state(1);
  let size = $state(10);
  let actionLoading = $state<string | null>(null);
  let statusFilter = $state('');

  // Modal state
  let modalMode = $state<'create' | 'edit' | 'reset' | 'detail' | null>(null);
  let modalUser = $state<UserOut | null>(null);
  let formError = $state<string | null>(null);
  let formLoading = $state(false);

  // Form fields
  let fUsername = $state('');
  let fEmail = $state('');
  let fPassword = $state('');
  let fIsSuperuser = $state(false);
  let fIsActive = $state(true);

  async function loadUsers() {
    loading = true;
    error = null;
    try {
      const result = await api.users.list({ page, size, search: globalSearch.query || undefined });
      let items = result.items;
      // Filtro por estado en cliente
      if (statusFilter === 'active') items = items.filter(u => u.is_active && !u.locked_until);
      else if (statusFilter === 'inactive') items = items.filter(u => !u.is_active);
      else if (statusFilter === 'superuser') items = items.filter(u => u.is_superuser);
      users = items;
      meta = result.meta;
    } catch (err) {
      if (err instanceof HttpError) error = err.message;
      else error = 'Error al cargar usuarios.';
    } finally { loading = false; }
  }

  function goToPage(p: number) {
    if (p < 1 || (meta && p > meta.pages)) return;
    page = p; loadUsers();
  }

  function openCreate() {
    modalMode = 'create'; modalUser = null; formError = null;
    fUsername = ''; fEmail = ''; fPassword = ''; fIsSuperuser = false; fIsActive = true;
  }

  function openEdit(user: UserOut) {
    modalMode = 'edit'; modalUser = user; formError = null;
    fIsActive = user.is_active; fIsSuperuser = user.is_superuser;
  }

  function openReset(user: UserOut) {
    modalMode = 'reset'; modalUser = user; formError = null; fPassword = '';
  }

  function openDetail(user: UserOut) {
    modalMode = 'detail'; modalUser = user; formError = null;
  }

  function closeModal() { modalMode = null; modalUser = null; formError = null; }

  async function handleSubmit() {
    formLoading = true; formError = null;
    try {
      if (modalMode === 'create') {
        await api.users.create({ username: fUsername, email: fEmail, password: fPassword, is_superuser: fIsSuperuser });
      } else if (modalMode === 'edit' && modalUser) {
        await api.users.update(modalUser.id, { is_active: fIsActive, is_superuser: fIsSuperuser });
      } else if (modalMode === 'reset' && modalUser) {
        await api.users.forcePasswordReset(modalUser.id, fPassword);
      }
      closeModal();
      await loadUsers();
    } catch (err) {
      formError = err instanceof HttpError ? err.message : 'Error inesperado.';
    } finally { formLoading = false; }
  }

  async function toggleActive(user: UserOut) {
    if (actionLoading) return;
    actionLoading = user.id;
    try { await api.users.update(user.id, { is_active: !user.is_active }); await loadUsers(); }
    catch (err) { error = err instanceof HttpError ? err.message : 'Error.'; }
    finally { actionLoading = null; }
  }

  async function unlockUser(user: UserOut) {
    if (actionLoading) return;
    actionLoading = user.id;
    try { await api.users.unlock(user.id); await loadUsers(); }
    catch (err) { error = err instanceof HttpError ? err.message : 'Error.'; }
    finally { actionLoading = null; }
  }

  async function deactivateUser(user: UserOut) {
    if (actionLoading) return;
    if (!confirm(`¿Desactivar a "${user.username}"?`)) return;
    actionLoading = user.id;
    try { await api.users.deactivate(user.id); await loadUsers(); }
    catch (err) { error = err instanceof HttpError ? err.message : 'Error.'; }
    finally { actionLoading = null; }
  }

  $effect(() => { page = 1; loadUsers(); globalSearch.query; });
</script>

<svelte:head><title>Usuarios — ERP System</title></svelte:head>

<div class="p-6 md:p-8">
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">{meta ? `${meta.total} usuario(s)` : 'Cargando...'}</p>
    <div class="flex items-center gap-2">
      <select bind:value={statusFilter} onchange={() => { page = 1; loadUsers(); }}
        class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none">
        <option value="">Todos</option>
        <option value="active">Activos</option>
        <option value="inactive">Inactivos</option>
        <option value="superuser">Super admins</option>
      </select>
      <Button size="sm" onclick={openCreate}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        Crear
      </Button>
    </div>
  </div>

  {#if error}
    <div class="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}</div>
  {/if}

  <Card class="overflow-hidden p-0">
    {#if loading}
      <div class="flex items-center justify-center py-16"><p class="text-sm text-foreground-muted">Cargando...</p></div>
    {:else if users.length === 0}
      <div class="flex flex-col items-center justify-center py-16"><p class="text-sm text-foreground-muted">No se encontraron usuarios.</p></div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="border-b border-border bg-surface-muted">
            <tr>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Usuario</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Correo</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Estado</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Rol</th>
              <th class="px-2 py-3 text-center font-semibold text-foreground w-11"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each users as user (user.id)}
              <tr class="hover:bg-surface-muted">
                <td class="px-4 py-3">
                  <button class="flex items-center gap-2.5 font-medium text-foreground hover:text-primary" onclick={() => openDetail(user)}>
                    <Avatar initials={user.username.substring(0, 2)} size={24} />
                    {user.username}
                  </button>
                </td>
                <td class="px-4 py-3 text-foreground-muted">{user.email}</td>
                <td class="px-4 py-3">
                  {#if user.locked_until}
                    <span class="badge-warning inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"><span class="h-1.5 w-1.5 rounded-full bg-warning"></span> Bloqueado</span>
                  {:else if user.is_active}
                    <span class="badge-success inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"><span class="h-1.5 w-1.5 rounded-full bg-success"></span> Activo</span>
                  {:else}
                    <span class="badge-neutral inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"><span class="h-1.5 w-1.5 rounded-full bg-foreground-muted"></span> Inactivo</span>
                  {/if}
                </td>
                <td class="px-4 py-3 text-foreground-muted">{user.is_superuser ? 'Super Admin' : 'Usuario'}</td>
                <td class="px-2 py-3 text-center">
                  <KebabMenu
                    items={[
                      { id: 'detail', label: 'Ver detalle', icon: 'detail', onClick: () => openDetail(user) },
                      { id: 'edit', label: 'Editar', icon: 'edit', onClick: () => openEdit(user) },
                      { id: 'reset', label: 'Resetear contraseña', icon: 'key', onClick: () => openReset(user) },
                      ...(user.locked_until ? [{ id: 'unlock', label: 'Desbloquear', icon: 'unlock' as const, onClick: () => unlockUser(user) }] : []),
                      { id: 'toggle', label: user.is_active ? 'Desactivar' : 'Activar', icon: 'power', variant: user.is_active ? 'danger' : 'default', onClick: () => toggleActive(user) },
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
        <Button variant="secondary" size="sm" onclick={() => goToPage(meta!.page - 1)} disabled={meta!.page <= 1}>Anterior</Button>
        <Button variant="secondary" size="sm" onclick={() => goToPage(meta!.page + 1)} disabled={meta!.page >= meta!.pages}>Siguiente</Button>
      </div>
    </div>
  {/if}
</div>

<!-- Modal: Crear / Editar / Resetear / Detalle -->
<Modal open={modalMode !== null} title={modalMode === 'create' ? 'Crear usuario' : modalMode === 'edit' ? 'Editar usuario' : modalMode === 'reset' ? 'Resetear contraseña' : 'Detalle del usuario'} onclose={closeModal} size={modalMode === 'detail' ? 'lg' : 'md'}>
  {#if modalMode === 'create'}
    <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
      {#if formError}<div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2 text-sm text-danger">{formError}</div>{/if}
      <FormField id="f-username" label="Nombre de usuario" bind:value={fUsername} required placeholder="usuario123" />
      <FormField id="f-email" label="Correo electrónico" type="email" bind:value={fEmail} required placeholder="usuario@ejemplo.com" />
      <FormField id="f-password" label="Contraseña" type="password" bind:value={fPassword} required placeholder="Mínimo 12 caracteres" min="12" />
      <label class="flex items-center gap-2 text-sm text-foreground"><input type="checkbox" bind:checked={fIsSuperuser} class="rounded" /> Super administrador</label>
      <div class="flex justify-end gap-2 pt-2"><Button variant="secondary" onclick={closeModal}>Cancelar</Button><Button type="submit" disabled={formLoading}>{formLoading ? 'Guardando...' : 'Crear'}</Button></div>
    </form>
  {:else if modalMode === 'edit' && modalUser}
    <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
      {#if formError}<div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2 text-sm text-danger">{formError}</div>{/if}
      <div><p class="mb-1 text-sm font-medium text-foreground">Usuario</p><p class="text-sm text-foreground-muted">{modalUser.username} · {modalUser.email}</p></div>
      <label class="flex items-center gap-2 text-sm text-foreground"><input type="checkbox" bind:checked={fIsActive} class="rounded" /> Activo</label>
      <label class="flex items-center gap-2 text-sm text-foreground"><input type="checkbox" bind:checked={fIsSuperuser} class="rounded" /> Super administrador</label>
      <div class="flex justify-end gap-2 pt-2"><Button variant="secondary" onclick={closeModal}>Cancelar</Button><Button type="submit" disabled={formLoading}>{formLoading ? 'Guardando...' : 'Guardar'}</Button></div>
    </form>
  {:else if modalMode === 'reset' && modalUser}
    <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
      {#if formError}<div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2 text-sm text-danger">{formError}</div>{/if}
      <p class="text-sm text-foreground-muted">Nueva contraseña para <strong>{modalUser.username}</strong></p>
      <FormField id="f-newpass" label="Nueva contraseña" type="password" bind:value={fPassword} required min="12" placeholder="Mínimo 12 caracteres" />
      <div class="flex justify-end gap-2 pt-2"><Button variant="secondary" onclick={closeModal}>Cancelar</Button><Button type="submit" disabled={formLoading}>{formLoading ? 'Guardando...' : 'Resetear'}</Button></div>
    </form>
  {:else if modalMode === 'detail' && modalUser}
    <dl class="space-y-3 text-sm">
      <div class="flex justify-between"><dt class="text-foreground-muted">ID</dt><dd class="font-mono text-xs text-foreground">{modalUser.id}</dd></div>
      <div class="flex justify-between"><dt class="text-foreground-muted">Usuario</dt><dd class="text-foreground">{modalUser.username}</dd></div>
      <div class="flex justify-between"><dt class="text-foreground-muted">Correo</dt><dd class="text-foreground">{modalUser.email}</dd></div>
      <div class="flex justify-between"><dt class="text-foreground-muted">Estado</dt><dd class="text-foreground">{modalUser.is_active ? 'Activo' : 'Inactivo'}</dd></div>
      <div class="flex justify-between"><dt class="text-foreground-muted">Rol</dt><dd class="text-foreground">{modalUser.is_superuser ? 'Super Admin' : 'Usuario'}</dd></div>
      <div class="flex justify-between"><dt class="text-foreground-muted">Intentos fallidos</dt><dd class="text-foreground">{modalUser.failed_login_attempts}</dd></div>
      <div class="flex justify-between"><dt class="text-foreground-muted">Bloqueado hasta</dt><dd class="text-foreground">{modalUser.locked_until ? new Date(modalUser.locked_until).toLocaleString('es-ES') : '—'}</dd></div>
      <div class="flex justify-between"><dt class="text-foreground-muted">Último login</dt><dd class="text-foreground">{modalUser.last_login_at ? new Date(modalUser.last_login_at).toLocaleString('es-ES') : '—'}</dd></div>
      <div class="flex justify-between"><dt class="text-foreground-muted">Creado</dt><dd class="text-foreground">{new Date(modalUser.created_at).toLocaleString('es-ES')}</dd></div>
    </dl>
    <div class="mt-4 flex justify-end"><Button variant="secondary" onclick={closeModal}>Cerrar</Button></div>
  {/if}
</Modal>