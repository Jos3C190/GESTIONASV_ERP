<script lang="ts">
  import { onMount } from 'svelte';
  import {
    api,
    HttpError,
    type AuditLogOut,
    type AuditLogPage,
    type UserOut
  } from '$lib/api/client';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { queryClient } from '$lib/services/query-client';

  let logs = $state<AuditLogOut[]>([]);
  let meta = $state<{ page: number; size: number; total: number; pages: number } | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let actionFilter = $state('');
  let statusFilter = $state('');
  let resourceFilter = $state('');
  let userFilter = $state('');
  let users = $state<UserOut[]>([]);
  let startDate = $state('');
  let endDate = $state('');
  let page = $state(1);
  let size = $state(20);
  let logController: AbortController | null = null;
  let logGeneration = 0;

  let modalEntry = $state<AuditLogOut | null>(null);

  async function loadLogs() {
    const generation = ++logGeneration;
    logController?.abort();
    logController = new AbortController();
    loading = true;
    error = null;
    if (startDate && endDate && startDate > endDate) {
      error = 'La fecha inicial no puede ser posterior a la fecha final.';
      loading = false;
      return;
    }
    try {
      const result: AuditLogPage = await api.audit.list({
        page,
        size,
        action: actionFilter || undefined,
        status: statusFilter || undefined,
        resource_type: resourceFilter || undefined,
        user_id: userFilter || undefined,
        start_date: startDate ? new Date(`${startDate}T00:00:00`).toISOString() : undefined,
        end_date: endDate ? new Date(`${endDate}T23:59:59`).toISOString() : undefined,
        signal: logController.signal
      });
      if (generation !== logGeneration) return;
      logs = result.items;
      meta = result.meta;
    } catch (err) {
      if (generation !== logGeneration || (err instanceof DOMException && err.name === 'AbortError'))
        return;
      error = err instanceof HttpError ? err.message : 'Error al cargar bitácora.';
    } finally {
      if (generation === logGeneration) loading = false;
    }
  }

  function applyFilters() {
    page = 1;
  }
  function goToPage(p: number) {
    if (p < 1 || (meta && p > meta.pages)) return;
    page = p;
  }
  async function openDetail(entry: AuditLogOut) {
    if (!permissions.hasPermission('logs.detail')) return;
    modalEntry = entry;
    try {
      modalEntry = await api.audit.get(entry.id);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error al cargar el detalle.';
    }
  }
  function closeDetail() {
    modalEntry = null;
  }
  async function exportCsv() {
    try {
      const blob = await api.audit.exportCsv({
        action: actionFilter || undefined,
        resource_type: resourceFilter || undefined,
        user_id: userFilter || undefined,
        start_date: startDate ? new Date(`${startDate}T00:00:00`).toISOString() : undefined,
        end_date: endDate ? new Date(`${endDate}T23:59:59`).toISOString() : undefined
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `bitacora-${new Date().toISOString().slice(0, 10)}.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo exportar la bitácora.';
    }
  }
  function formatState(state: Record<string, unknown> | null): string {
    return state ? JSON.stringify(state, null, 2) : '—';
  }
  function actionLabel(action: string): string {
    const map: Record<string, string> = {
      LOGIN_SUCCESS: 'Inicio de sesión exitoso',
      LOGIN_FAILED: 'Intento de login fallido',
      LOGOUT: 'Cierre de sesión',
      PASSWORD_CHANGE: 'Contraseña cambiada',
      PASSWORD_RESET: 'Contraseña restablecida',
      CREATE: 'Registro creado',
      UPDATE: 'Registro actualizado',
      DELETE: 'Registro eliminado',
      LOGICAL_DELETE: 'Registro enviado a la papelera',
      RESTORE: 'Registro restaurado',
      ACTIVATE: 'Registro activado',
      DEACTIVATE: 'Registro desactivado',
      DUPLICATE: 'Rol duplicado',
      SET_PERMISSIONS: 'Permisos actualizados',
      ASSIGN_ROLE: 'Rol asignado',
      REVOKE_ROLE: 'Rol revocado',
      LINK_USER: 'Usuario vinculado',
      UNLINK_USER: 'Usuario desvinculado',
      UNLOCK: 'Usuario desbloqueado'
    };
    return map[action] ?? action;
  }
  function actionBadgeClass(action: string): string {
    if (action.includes('SUCCESS')) return 'badge-success';
    if (action.includes('FAILED')) return 'badge-danger';
    if (action === 'CREATE' || action === 'DUPLICATE' || action === 'RESTORE')
      return 'badge-primary';
    if (action === 'ACTIVATE') return 'badge-success';
    if (
      [
        'UPDATE',
        'SET_PERMISSIONS',
        'ASSIGN_ROLE',
        'REVOKE_ROLE',
        'LINK_USER',
        'UNLINK_USER'
      ].includes(action)
    )
      return 'badge-warning';
    if (action.includes('DELETE') || action === 'DEACTIVATE') return 'badge-danger';
    return 'badge-neutral';
  }
  function timeAgo(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'hace un momento';
    if (mins < 60) return `hace ${mins}m`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `hace ${hours}h`;
    return `hace ${Math.floor(hours / 24)}d`;
  }

  let filteredLogs = $derived.by(() => {
    const q = globalSearch.query.toLowerCase().trim();
    if (!q) return logs;
    return logs.filter(
      (l) =>
        l.action.toLowerCase().includes(q) ||
        (l.resource_type ?? '').toLowerCase().includes(q) ||
        (l.ip_address ?? '').toLowerCase().includes(q)
    );
  });

  $effect(() => {
    void loadLogs();
    return () => logController?.abort();
  });

  onMount(async () => {
    if (!permissions.hasPermission('users:read')) return;
    try {
      users = (
        await queryClient.fetchQuery({
          queryKey: ['catalogue', 'audit-users', company.id ?? 'none', branch.id ?? 'all'],
          staleTime: 2 * 60_000,
          queryFn: ({ signal }) => api.users.list({ page: 1, size: 100, signal })
        })
      ).items;
    } catch {
      // El filtro de usuario es complementario; la bitácora sigue disponible.
    }
  });
</script>

<svelte:head><title>Bitácora — GestionaSV</title></svelte:head>

<div class="p-6 md:p-8">
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">{meta ? `${meta.total} evento(s)` : 'Cargando...'}</p>
    {#if permissions.hasPermission('logs.export')}
      <Button variant="secondary" size="sm" onclick={exportCsv}>Exportar CSV</Button>
    {/if}
  </div>

  <div class="mb-4 flex flex-wrap items-center gap-2">
    <select
      bind:value={actionFilter}
      onchange={applyFilters}
      class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
    >
      <option value="">Todas las acciones</option>
      {#each [['LOGIN_SUCCESS', 'Login exitoso'], ['LOGIN_FAILED', 'Login fallido'], ['LOGOUT', 'Cierre de sesión'], ['PASSWORD_CHANGE', 'Cambio de contraseña'], ['PASSWORD_RESET', 'Restablecimiento de contraseña'], ['CREATE', 'Creación'], ['UPDATE', 'Actualización'], ['DELETE', 'Eliminación'], ['LOGICAL_DELETE', 'Enviado a la papelera'], ['RESTORE', 'Restauración'], ['ACTIVATE', 'Activación'], ['DEACTIVATE', 'Desactivación'], ['DUPLICATE', 'Duplicación'], ['SET_PERMISSIONS', 'Cambio de permisos'], ['ASSIGN_ROLE', 'Asignación de rol'], ['REVOKE_ROLE', 'Revocación de rol'], ['LINK_USER', 'Vinculación de usuario'], ['UNLINK_USER', 'Desvinculación de usuario'], ['UNLOCK', 'Desbloqueo de usuario']] as option}
        <option value={option[0]}>{option[1]}</option>
      {/each}
    </select>
    {#if users.length > 0}
      <select
        bind:value={userFilter}
        onchange={applyFilters}
        aria-label="Usuario"
        class="h-8 max-w-56 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
      >
        <option value="">Todos los usuarios</option>
        {#each users as user (user.id)}
          <option value={user.id}>{user.username}</option>
        {/each}
      </select>
    {/if}
    <select
      bind:value={statusFilter}
      onchange={applyFilters}
      class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
    >
      <option value="">Todos los estados</option><option value="success">Éxito</option><option
        value="failure">Fallo</option
      >
    </select>
    <select
      bind:value={resourceFilter}
      onchange={applyFilters}
      class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
    >
      <option value="">Todos los recursos</option><option value="auth">Auth</option><option
        value="users">Usuarios</option
      ><option value="roles">Roles</option><option value="permissions">Permisos</option><option
        value="employees">Empleados</option
      ><option value="departments">Departamentos</option>
    </select>
    <input
      type="date"
      bind:value={startDate}
      onchange={applyFilters}
      aria-label="Fecha inicial"
      class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:outline-none"
    />
    <input
      type="date"
      bind:value={endDate}
      onchange={applyFilters}
      aria-label="Fecha final"
      class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:outline-none"
    />
  </div>

  {#if error}<div
      class="mb-4 animate-fade-scale rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>{/if}

  <Card class="overflow-hidden p-0">
    {#if loading}
      <div class="space-y-2 p-4">
        {#each Array(8) as _}<div class="flex items-center gap-3 py-3">
            <div class="h-3 w-32 rounded skeleton"></div>
            <div class="h-3 flex-1 rounded skeleton"></div>
            <div class="h-3 w-20 rounded skeleton"></div>
          </div>{/each}
      </div>
    {:else if filteredLogs.length === 0}
      <div class="flex flex-col items-center justify-center py-16">
        <p class="text-sm text-foreground-muted">No hay entradas para los filtros seleccionados.</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="border-b border-border bg-surface-muted/50">
            <tr>
              <th
                class="px-5 py-3.5 text-left text-xs font-bold uppercase tracking-wider text-foreground-subtle"
                >Fecha</th
              >
              <th
                class="px-5 py-3.5 text-left text-xs font-bold uppercase tracking-wider text-foreground-subtle"
                >Acción</th
              >
              <th
                class="px-5 py-3.5 text-left text-xs font-bold uppercase tracking-wider text-foreground-subtle"
                >Estado</th
              >
              <th
                class="px-5 py-3.5 text-left text-xs font-bold uppercase tracking-wider text-foreground-subtle"
                >Recurso</th
              >
              <th
                class="px-5 py-3.5 text-left text-xs font-bold uppercase tracking-wider text-foreground-subtle"
                >IP</th
              >
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each filteredLogs as entry (entry.id)}
              <tr
                class="group transition-colors hover:bg-surface-hover {permissions.hasPermission(
                  'logs.detail'
                )
                  ? 'cursor-pointer'
                  : ''}"
                onclick={() => openDetail(entry)}
              >
                <td class="whitespace-nowrap px-5 py-3"
                  ><p class="text-sm text-foreground">
                    {new Date(entry.created_at).toLocaleString('es-SV', {
                      timeZone: 'America/El_Salvador',
                      day: '2-digit',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </p>
                  <p class="text-xs text-foreground-subtle">{timeAgo(entry.created_at)}</p></td
                >
                <td class="px-5 py-3"
                  ><span
                    class="{actionBadgeClass(
                      entry.action
                    )} inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold"
                    >{entry.action}</span
                  ></td
                >
                <td class="px-5 py-3"
                  >{#if entry.status === 'success'}<span
                      class="badge-success inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold"
                      ><span class="h-1.5 w-1.5 rounded-full bg-success"></span> Éxito</span
                    >{:else}<span
                      class="badge-danger inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold"
                      ><span class="h-1.5 w-1.5 rounded-full bg-danger"></span> Fallo</span
                    >{/if}</td
                >
                <td class="px-5 py-3 text-foreground-muted"
                  >{entry.resource_type ?? '—'}{#if entry.resource_id}<span
                      class="font-mono text-xs text-foreground-subtle"
                    >
                      / {entry.resource_id.slice(0, 8)}</span
                    >{/if}</td
                >
                <td class="px-5 py-3 font-mono text-xs text-foreground-muted"
                  >{entry.ip_address ?? '—'}</td
                >
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </Card>

  {#if meta && meta.pages > 1}
    <div class="mt-4 flex items-center justify-between">
      <p class="text-xs text-foreground-subtle">
        Página {meta.page} de {meta.pages} · {meta.total} evento(s)
      </p>
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

<Modal open={modalEntry !== null} title="Detalle de evento" onclose={closeDetail} size="lg">
  {#if modalEntry}
    <div class="space-y-5">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div
            class="flex h-11 w-11 items-center justify-center rounded-xl {modalEntry.status ===
            'success'
              ? 'bg-success/10'
              : 'bg-danger/10'}"
          >
            {#if modalEntry.status === 'success'}<svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
                class="text-success"
                ><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline
                  points="22 4 12 14.01 9 11.01"
                /></svg
              >{:else}<svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
                class="text-danger"
                ><circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line
                  x1="9"
                  y1="9"
                  x2="15"
                  y2="15"
                /></svg
              >{/if}
          </div>
          <div>
            <p class="text-base font-bold text-foreground">{actionLabel(modalEntry.action)}</p>
            <p class="text-xs text-foreground-muted">{modalEntry.action}</p>
          </div>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4 rounded-xl border border-border bg-surface-muted/50 p-4">
        <div>
          <p class="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
            Fecha y hora
          </p>
          <p class="mt-1 text-sm text-foreground">
            {new Date(modalEntry.created_at).toLocaleString('es-ES')}
          </p>
        </div>
        <div>
          <p class="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
            Usuario ID
          </p>
          <p class="mt-1 font-mono text-xs text-foreground">{modalEntry.user_id ?? '—'}</p>
        </div>
        <div>
          <p class="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
            Recurso
          </p>
          <p class="mt-1 text-sm text-foreground">
            {modalEntry.resource_type ?? '—'}{#if modalEntry.resource_id}<span
                class="font-mono text-xs text-foreground-subtle"
              >
                / {modalEntry.resource_id.slice(0, 12)}</span
              >{/if}
          </p>
        </div>
        <div>
          <p class="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">IP</p>
          <p class="mt-1 font-mono text-sm text-foreground">{modalEntry.ip_address ?? '—'}</p>
        </div>
        {#if modalEntry.user_agent}<div class="col-span-2">
            <p class="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
              User Agent
            </p>
            <p class="mt-1 text-xs text-foreground-muted break-all">{modalEntry.user_agent}</p>
          </div>{/if}
      </div>
      {#if modalEntry.before_state || modalEntry.after_state}
        <div class="grid gap-4 md:grid-cols-2">
          <div>
            <div class="mb-2 flex items-center gap-2">
              <span class="badge-danger rounded-lg px-2 py-0.5 text-xs font-semibold">ANTES</span>
            </div>
            <pre
              class="overflow-x-auto rounded-xl border border-border bg-surface p-3 text-xs font-mono text-foreground-muted">{formatState(
                modalEntry.before_state
              )}</pre>
          </div>
          <div>
            <div class="mb-2 flex items-center gap-2">
              <span class="badge-success rounded-lg px-2 py-0.5 text-xs font-semibold">DESPUÉS</span
              >
            </div>
            <pre
              class="overflow-x-auto rounded-xl border border-border bg-surface p-3 text-xs font-mono text-foreground-muted">{formatState(
                modalEntry.after_state
              )}</pre>
          </div>
        </div>
      {/if}
      {#if modalEntry.metadata && Object.keys(modalEntry.metadata).length > 0}
        <div>
          <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
            Metadata
          </p>
          <pre
            class="overflow-x-auto rounded-xl border border-border bg-surface-muted/50 p-3 text-xs font-mono text-foreground-muted">{JSON.stringify(
              modalEntry.metadata,
              null,
              2
            )}</pre>
        </div>
      {/if}
      <div class="flex justify-end">
        <Button variant="secondary" onclick={closeDetail}>Cerrar</Button>
      </div>
    </div>
  {/if}
</Modal>
