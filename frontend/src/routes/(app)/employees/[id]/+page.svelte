<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { api, HttpError, type EmployeeOut, type DepartmentOut } from '$lib/api/client';
  import { resolvePhotoUrl, initialsOf } from '$lib/features/employees/avatar';
  import Avatar from '$lib/components/ui/Avatar.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';

  let emp = $state<EmployeeOut | null>(null);
  let departments = $state<DepartmentOut[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let actionLoading = $state(false);

  // Modal de vincular usuario
  let showLinkModal = $state(false);
  let users = $state<{ id: string; username: string; email: string }[]>([]);
  let fLinkUserId = $state('');
  let linkError = $state<string | null>(null);
  let linkLoading = $state(false);

  let empId = $derived(page.params.id);

  async function loadData() {
    if (!empId) return;
    loading = true;
    error = null;
    try {
      const [empResult, deptResult] = await Promise.all([
        api.employees.get(empId),
        api.departments.list()
      ]);
      emp = empResult;
      departments = deptResult;
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error al cargar el empleado.';
    } finally {
      loading = false;
    }
  }

  $effect(() => { if (empId) loadData(); });

  let initials = $derived.by(() => {
    if (!emp) return '??';
    return initialsOf(emp.first_name, emp.last_name);
  });

  function deptName(id: string | null): string {
    if (!id) return '—';
    return departments.find((d) => d.id === id)?.name ?? '—';
  }

  function statusBadge(s: string): string {
    const m: Record<string, string> = { activo: 'badge-success', inactivo: 'badge-neutral', vacaciones: 'badge-warning', baja: 'badge-danger' };
    return m[s] ?? 'badge-neutral';
  }

  function fmtDate(d: string | null): string {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('es-SV');
  }

  async function deleteEmp() {
    if (!emp) return;
    if (!confirm(`¿Eliminar al empleado "${emp.first_name} ${emp.last_name}"?`)) return;
    actionLoading = true;
    try {
      await api.employees.delete(emp.id);
      await goto('/employees');
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error al eliminar.';
    } finally {
      actionLoading = false;
    }
  }

  async function openLinkModal() {
    if (!emp) return;
    showLinkModal = true;
    linkError = null;
    fLinkUserId = '';
    try {
      const r = await api.users.list({ size: 100 });
      users = r.items;
    } catch {
      users = [];
    }
  }

  async function handleLink() {
    if (!emp || !fLinkUserId) return;
    linkLoading = true;
    linkError = null;
    try {
      await api.employees.linkUser(emp.id, fLinkUserId);
      showLinkModal = false;
      await loadData();
    } catch (err) {
      linkError = err instanceof HttpError ? err.message : 'Error al vincular.';
    } finally {
      linkLoading = false;
    }
  }

  async function unlinkEmp() {
    if (!emp) return;
    if (!confirm('¿Desvincular la cuenta de usuario de este empleado?')) return;
    actionLoading = true;
    try {
      await api.employees.unlinkUser(emp.id);
      await loadData();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error al desvincular.';
    } finally {
      actionLoading = false;
    }
  }
</script>

<svelte:head><title>{emp ? `${emp.first_name} ${emp.last_name} — Empleados` : 'Empleado — ERP System'}</title></svelte:head>

<div class="p-6 md:p-8">
  <!-- Header con back -->
  <div class="mb-6 flex items-center gap-3">
    <a href="/employees" class="flex h-8 w-8 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground" aria-label="Volver">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
    </a>
    <div class="flex-1">
      <h1 class="text-xl font-bold text-foreground">Detalle del empleado</h1>
      <p class="text-sm text-foreground-muted">Información completa del empleado.</p>
    </div>
    {#if emp}
      <div class="flex items-center gap-2">
        <Button variant="secondary" size="sm" onclick={() => emp && goto(`/employees/${emp.id}/edit`)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          Editar
        </Button>
        {#if !emp.user_id}
          <Button variant="secondary" size="sm" onclick={openLinkModal}>Vincular usuario</Button>
        {:else}
          <Button variant="ghost" size="sm" onclick={unlinkEmp} disabled={actionLoading}>Desvincular</Button>
        {/if}
        <Button variant="ghost" size="sm" onclick={deleteEmp} disabled={actionLoading}>Eliminar</Button>
      </div>
    {/if}
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-16">
      <div class="flex flex-col items-center gap-3">
        <svg class="animate-spin h-5 w-5 text-primary" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <p class="text-xs text-foreground-subtle">Cargando empleado...</p>
      </div>
    </div>
  {:else if error}
    <div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}</div>
  {:else if emp}
    <!-- Tarjeta de cabecera con avatar -->
    <Card class="mb-5 p-6">
      <div class="flex flex-col sm:flex-row items-start sm:items-center gap-5">
        <Avatar {initials} size={88} src={emp ? resolvePhotoUrl(emp.photo_url, emp.id) : null} alt={`${emp.first_name} ${emp.last_name}`} />
        <div class="flex-1">
          <h2 class="text-lg font-bold text-foreground">{emp.first_name} {emp.last_name}</h2>
          <p class="text-sm text-foreground-muted">{emp.position ?? 'Sin cargo'}</p>
          <div class="mt-2 flex flex-wrap items-center gap-3">
            <span class="font-mono text-xs text-foreground-subtle">{emp.employee_code}</span>
            <span class="{statusBadge(emp.status)} inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium">
              <span class="h-1.5 w-1.5 rounded-full bg-current"></span> {emp.status}
            </span>
            {#if emp.user_id}
              <span class="text-xs text-success">Usuario vinculado</span>
            {/if}
          </div>
        </div>
      </div>
    </Card>

    <!-- Grid de datos -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Card class="p-6">
        <h3 class="mb-4 text-sm font-semibold text-foreground">Datos laborales</h3>
        <dl class="space-y-3 text-sm">
          <div class="flex justify-between"><dt class="text-foreground-muted">Departamento</dt><dd class="text-foreground text-right">{deptName(emp.department_id)}</dd></div>
          <div class="flex justify-between"><dt class="text-foreground-muted">Cargo</dt><dd class="text-foreground text-right">{emp.position ?? '—'}</dd></div>
          <div class="flex justify-between"><dt class="text-foreground-muted">Fecha contratación</dt><dd class="text-foreground text-right">{fmtDate(emp.hire_date)}</dd></div>
          <div class="flex justify-between"><dt class="text-foreground-muted">Fecha terminación</dt><dd class="text-foreground text-right">{fmtDate(emp.termination_date)}</dd></div>
          <div class="flex justify-between"><dt class="text-foreground-muted">Estado</dt><dd class="text-foreground text-right">{emp.status}</dd></div>
        </dl>
      </Card>

      <Card class="p-6">
        <h3 class="mb-4 text-sm font-semibold text-foreground">Datos personales</h3>
        <dl class="space-y-3 text-sm">
          <div class="flex justify-between"><dt class="text-foreground-muted">Documento</dt><dd class="text-foreground text-right">{emp.document_id ?? '—'}</dd></div>
          <div class="flex justify-between"><dt class="text-foreground-muted">Fecha nacimiento</dt><dd class="text-foreground text-right">{fmtDate(emp.birth_date)}</dd></div>
          <div class="flex justify-between"><dt class="text-foreground-muted">Teléfono</dt><dd class="text-foreground text-right">{emp.phone ?? '—'}</dd></div>
          <div><dt class="text-foreground-muted">Dirección</dt><dd class="text-foreground mt-1">{emp.address ?? '—'}</dd></div>
        </dl>
      </Card>
    </div>
  {/if}
</div>

<Modal open={showLinkModal} title="Vincular usuario" onclose={() => (showLinkModal = false)}>
  <form onsubmit={(e) => { e.preventDefault(); handleLink(); }} class="space-y-4">
    {#if linkError}<div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2 text-sm text-danger">{linkError}</div>{/if}
    <p class="text-sm text-foreground-muted">Selecciona el usuario a vincular con <strong>{emp?.first_name} {emp?.last_name}</strong></p>
    <FormField id="e-link-user" label="Usuario" bind:value={fLinkUserId} options={[{value:'',label:'— Seleccionar —'},...users.map(u=>({value:u.id,label:`${u.username} (${u.email})`}))]} />
    <div class="flex justify-end gap-2 pt-2">
      <Button variant="secondary" onclick={() => (showLinkModal = false)}>Cancelar</Button>
      <Button type="submit" disabled={linkLoading || !fLinkUserId}>{linkLoading ? 'Vinculando...' : 'Vincular'}</Button>
    </div>
  </form>
</Modal>