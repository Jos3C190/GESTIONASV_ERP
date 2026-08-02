<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import {
    api,
    HttpError,
    type EmployeeOut,
    type DepartmentOut,
    type EmployeeBranchAssignmentOut,
    type BranchOut
  } from '$lib/api/client';
  import { resolvePhotoUrl, initialsOf } from '$lib/features/employees/avatar';
  import Avatar from '$lib/components/ui/Avatar.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';

  let emp = $state<EmployeeOut | null>(null);
  let departments = $state<DepartmentOut[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let actionLoading = $state(false);
  let assignments = $state<EmployeeBranchAssignmentOut[]>([]);
  let branches = $state<BranchOut[]>([]);
  let showAssignmentModal = $state(false);
  let fBranchId = $state('');
  let fPrimary = $state(true);
  let fShift = $state('');
  let assignmentError = $state<string | null>(null);

  let empId = $derived(page.params.id);

  async function loadData() {
    if (!empId) return;
    loading = true;
    error = null;
    try {
      const [empResult, deptResult] = await Promise.all([
        api.employees.get(empId),
        api.departments.catalogue()
      ]);
      emp = empResult;
      departments = deptResult;
      const [assignmentResult, branchResult] = await Promise.allSettled([
        api.workforce.employeeAssignments(empId),
        api.branches.list()
      ]);
      assignments = assignmentResult.status === 'fulfilled' ? assignmentResult.value : [];
      branches = branchResult.status === 'fulfilled' ? branchResult.value : [];
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error al cargar el empleado.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (empId) loadData();
  });

  let initials = $derived.by(() => {
    if (!emp) return '??';
    return initialsOf(emp.first_name, emp.last_name);
  });

  function deptName(id: string | null): string {
    if (!id) return '—';
    return departments.find((d) => d.id === id)?.name ?? '—';
  }

  function statusBadge(s: string): string {
    const m: Record<string, string> = {
      activo: 'badge-success',
      inactivo: 'badge-neutral',
      vacaciones: 'badge-warning',
      baja: 'badge-danger'
    };
    return m[s] ?? 'badge-neutral';
  }

  function fmtDate(d: string | null): string {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('es-SV');
  }

  function branchName(id: string): string {
    return branches.find((branch) => branch.id === id)?.name ?? 'Sucursal no disponible';
  }

  async function assignBranch() {
    if (!emp || !fBranchId) return;
    actionLoading = true;
    assignmentError = null;
    try {
      await api.workforce.assignEmployee({
        employee_id: emp.id,
        branch_id: fBranchId,
        is_primary: fPrimary,
        position: emp.position ?? undefined,
        shift: fShift || undefined
      });
      showAssignmentModal = false;
      await loadData();
    } catch (err) {
      assignmentError = err instanceof HttpError ? err.message : 'No se pudo asignar la sucursal.';
    } finally {
      actionLoading = false;
    }
  }

  function endAssignment(id: string) {
    confirmation.request({
      kind: 'end-assignment',
      title: 'Finalizar asignación',
      description:
        'El empleado dejará de estar asignado a esta sucursal. El historial de la asignación se conservará.',
      resourceName: emp ? `${emp.first_name} ${emp.last_name}` : undefined,
      confirmLabel: 'Finalizar asignación',
      execute: async () => {
        await api.workforce.endEmployeeAssignment(id);
        await loadData();
      }
    });
  }

  function deleteEmp() {
    if (!emp) return;
    const employee = emp;
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar empleado',
      description:
        'El empleado dejará de estar disponible en los procesos operativos. Esta acción puede estar bloqueada por relaciones activas.',
      resourceName: `${employee.first_name} ${employee.last_name}`,
      confirmLabel: 'Eliminar empleado',
      execute: async () => {
        actionLoading = true;
        try {
          await api.employees.delete(employee.id);
          await goto('/employees');
        } finally {
          actionLoading = false;
        }
      }
    });
  }
</script>

<svelte:head
  ><title>{emp ? `${emp.first_name} ${emp.last_name} — Empleados` : 'Empleado — ERP System'}</title
  ></svelte:head
>

<div class="p-6 md:p-8">
  <!-- Header con back -->
  <div class="mb-6 flex items-center gap-3">
    <a
      href="/employees"
      class="flex h-8 w-8 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground"
      aria-label="Volver"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
        ><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg
      >
    </a>
    <div class="flex-1">
      <h1 class="text-xl font-bold text-foreground">Detalle del empleado</h1>
      <p class="text-sm text-foreground-muted">Información completa del empleado.</p>
    </div>
    {#if emp}
      <div class="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onclick={() => emp && goto(`/employees/${emp.id}/edit`)}
        >
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
            ><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path
              d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"
            /></svg
          >
          Editar
        </Button>
        <Button variant="ghost" size="sm" onclick={deleteEmp} disabled={actionLoading}
          >Eliminar</Button
        >
      </div>
    {/if}
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-16">
      <div class="flex flex-col items-center gap-3">
        <svg class="animate-spin h-5 w-5 text-primary" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"
          ></circle>
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          ></path>
        </svg>
        <p class="text-xs text-foreground-subtle">Cargando empleado...</p>
      </div>
    </div>
  {:else if error}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {:else if emp}
    <!-- Tarjeta de cabecera con avatar -->
    <Card class="mb-5 p-6">
      <div class="flex flex-col sm:flex-row items-start sm:items-center gap-5">
        <Avatar
          {initials}
          size={88}
          src={emp ? resolvePhotoUrl(emp.photo_url, emp.id) : null}
          alt={`${emp.first_name} ${emp.last_name}`}
        />
        <div class="flex-1">
          <h2 class="text-lg font-bold text-foreground">{emp.first_name} {emp.last_name}</h2>
          <p class="text-sm text-foreground-muted">{emp.position ?? 'Sin cargo'}</p>
          <div class="mt-2 flex flex-wrap items-center gap-3">
            <span class="font-mono text-xs text-foreground-subtle">{emp.employee_code}</span>
            <span
              class="{statusBadge(
                emp.status
              )} inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"
            >
              <span class="h-1.5 w-1.5 rounded-full bg-current"></span>
              {emp.status}
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
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Departamento</dt>
            <dd class="text-foreground text-right">{deptName(emp.department_id)}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Cargo</dt>
            <dd class="text-foreground text-right">{emp.position ?? '—'}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Fecha contratación</dt>
            <dd class="text-foreground text-right">{fmtDate(emp.hire_date)}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Fecha terminación</dt>
            <dd class="text-foreground text-right">{fmtDate(emp.termination_date)}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Estado</dt>
            <dd class="text-foreground text-right">{emp.status}</dd>
          </div>
        </dl>
      </Card>

      <Card class="p-6">
        <h3 class="mb-4 text-sm font-semibold text-foreground">Datos personales</h3>
        <dl class="space-y-3 text-sm">
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Documento</dt>
            <dd class="text-foreground text-right">{emp.document_id ?? '—'}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Fecha nacimiento</dt>
            <dd class="text-foreground text-right">{fmtDate(emp.birth_date)}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Teléfono</dt>
            <dd class="text-foreground text-right">{emp.phone ?? '—'}</dd>
          </div>
          <div>
            <dt class="text-foreground-muted">Dirección</dt>
            <dd class="text-foreground mt-1">{emp.address ?? '—'}</dd>
          </div>
        </dl>
      </Card>
    </div>

    <Card class="mt-5 p-6">
      <div class="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 class="text-sm font-semibold text-foreground">Asignaciones a sucursales</h3>
          <p class="mt-1 text-xs text-foreground-muted">
            Historial operativo y sucursal principal.
          </p>
        </div>
        <Button
          size="sm"
          onclick={() => {
            assignmentError = null;
            fBranchId = '';
            showAssignmentModal = true;
          }}>Asignar sucursal</Button
        >
      </div>
      {#if assignments.length === 0}
        <p class="rounded-lg bg-surface-muted p-4 text-sm text-foreground-muted">
          Este empleado todavía no tiene sucursales asignadas.
        </p>
      {:else}
        <div class="divide-y divide-border rounded-lg border border-border">
          {#each assignments as item (item.id)}
            <div class="flex flex-wrap items-center justify-between gap-3 p-3">
              <div>
                <p class="text-sm font-medium text-foreground">
                  {branchName(item.branch_id)}
                  {item.is_primary ? '· Principal' : ''}
                </p>
                <p class="text-xs text-foreground-muted">
                  Desde {fmtDate(item.assigned_from)}{item.assigned_until
                    ? ` hasta ${fmtDate(item.assigned_until)}`
                    : ''}{item.shift ? ` · Turno ${item.shift}` : ''}
                </p>
              </div>
              {#if item.is_active}<Button
                  variant="ghost"
                  size="sm"
                  onclick={() => endAssignment(item.id)}>Finalizar</Button
                >{:else}<span class="text-xs text-foreground-subtle">Finalizada</span>{/if}
            </div>
          {/each}
        </div>
      {/if}
    </Card>
  {/if}
</div>

<Modal
  open={showAssignmentModal}
  title="Asignar sucursal"
  onclose={() => (showAssignmentModal = false)}
>
  <form
    class="space-y-4"
    onsubmit={(e) => {
      e.preventDefault();
      assignBranch();
    }}
  >
    {#if assignmentError}<div class="rounded-lg bg-danger/10 p-3 text-sm text-danger">
        {assignmentError}
      </div>{/if}
    <SmartSelect
      id="employee-branch"
      label="Sucursal"
      bind:value={fBranchId}
      required
      placeholder="Buscar sucursal disponible…"
      options={[
        { value: '', label: '— Seleccionar —' },
        ...branches
          .filter(
            (b) =>
              b.operational_status === 'active' &&
              !assignments.some((a) => a.branch_id === b.id && a.is_active)
          )
          .map((b) => ({ value: b.id, label: b.name, description: b.code }))
      ]}
    />
    <FormField
      id="employee-shift"
      label="Turno"
      bind:value={fShift}
      options={[
        { value: '', label: 'Sin especificar' },
        { value: 'mañana', label: 'Mañana' },
        { value: 'tarde', label: 'Tarde' },
        { value: 'noche', label: 'Noche' }
      ]}
    />
    <label class="flex items-center gap-2 text-sm text-foreground"
      ><input type="checkbox" bind:checked={fPrimary} /> Sucursal principal</label
    >
    <p class="text-xs text-foreground-muted">
      El departamento del empleado debe estar habilitado previamente en la sucursal.
    </p>
    <div class="flex justify-end gap-2">
      <Button variant="secondary" onclick={() => (showAssignmentModal = false)}>Cancelar</Button
      ><Button type="submit" disabled={actionLoading || !fBranchId}>Asignar</Button>
    </div>
  </form>
</Modal>
