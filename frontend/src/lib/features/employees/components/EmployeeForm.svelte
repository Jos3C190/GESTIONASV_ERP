<script lang="ts">
  /** EmployeeForm — formulario reutilizable para crear/editar empleado (Vercel/Geist). */

  import { goto } from '$app/navigation';
  import { api, HttpError, type DepartmentOut } from '$lib/api/client';
  import Avatar from '$lib/components/ui/Avatar.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';

  interface Props {
    mode: 'create' | 'edit';
    employeeId?: string;
    initial?: {
      employee_code?: string;
      first_name?: string;
      last_name?: string;
      document_id?: string | null;
      birth_date?: string | null;
      phone?: string | null;
      address?: string | null;
      department_id?: string | null;
      position?: string | null;
      hire_date?: string | null;
      status?: string;
      photo_url?: string | null;
      termination_date?: string | null;
    };
    departments: DepartmentOut[];
  }

  let {
    mode,
    employeeId,
    initial = {},
    departments
  }: Props = $props();

  let fCode = $state(initial.employee_code ?? '');
  let fFirst = $state(initial.first_name ?? '');
  let fLast = $state(initial.last_name ?? '');
  let fDocId = $state(initial.document_id ?? '');
  let fBirthDate = $state(initial.birth_date ?? '');
  let fPhone = $state(initial.phone ?? '');
  let fAddress = $state(initial.address ?? '');
  let fDept = $state(initial.department_id ?? '');
  let fPosition = $state(initial.position ?? '');
  let fHireDate = $state(initial.hire_date ?? '');
  let fStatus = $state(initial.status ?? 'activo');
  let fTerminationDate = $state(initial.termination_date ?? '');
  let fPhotoUrl = $state(initial.photo_url ?? '');

  let formError = $state<string | null>(null);
  let formLoading = $state(false);

  let initials = $derived.by(() => {
    const a = fFirst.trim()[0] ?? '';
    const b = fLast.trim()[0] ?? '';
    return (a + b).toUpperCase() || '??';
  });

  const STATUS_OPTIONS = [
    { value: 'activo', label: 'Activo' },
    { value: 'inactivo', label: 'Inactivo' },
    { value: 'vacaciones', label: 'Vacaciones' },
    { value: 'baja', label: 'Baja' }
  ];

  let canSubmit = $derived(
    fCode.trim().length >= 2 &&
    fFirst.trim().length >= 2 &&
    fLast.trim().length >= 2 &&
    !formLoading
  );

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    formLoading = true;
    formError = null;
    try {
      const payload: Record<string, unknown> = {
        first_name: fFirst.trim(),
        last_name: fLast.trim(),
        document_id: fDocId.trim() || undefined,
        birth_date: fBirthDate || undefined,
        phone: fPhone.trim() || undefined,
        address: fAddress.trim() || undefined,
        department_id: fDept || undefined,
        position: fPosition.trim() || undefined,
        hire_date: fHireDate || undefined,
        status: fStatus,
        photo_url: fPhotoUrl.trim() || undefined
      };
      if (mode === 'create') {
        payload.employee_code = fCode.trim();
        await api.employees.create(payload);
        await goto('/employees');
      } else if (mode === 'edit' && employeeId) {
        payload.termination_date = fTerminationDate || undefined;
        await api.employees.update(employeeId, payload);
        await goto(`/employees/${employeeId}`);
      }
    } catch (err) {
      formError = err instanceof HttpError ? err.message : 'Error inesperado.';
    } finally {
      formLoading = false;
    }
  }

  function handleCancel() {
    history.back();
  }
</script>

<div class="max-w-3xl">
  {#if formError}
    <div class="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">
      {formError}
    </div>
  {/if}

  <form onsubmit={handleSubmit} class="space-y-6">
    <!-- Sección: Foto + Datos básicos -->
    <Card class="p-6">
      <div class="flex flex-col sm:flex-row items-start gap-6">
        <!-- Avatar preview -->
        <div class="flex flex-col items-center gap-2 flex-none">
          <Avatar {initials} size={96} src={fPhotoUrl || null} alt={`${fFirst} ${fLast}`} />
          <span class="text-[11px] text-foreground-subtle">Vista previa</span>
        </div>
        <div class="flex-1 w-full grid grid-cols-1 sm:grid-cols-2 gap-4">
          {#if mode === 'create'}
            <FormField id="e-code" label="Código de empleado" bind:value={fCode} required placeholder="EMP001" />
          {:else}
            <div>
              <label for="e-code-readonly" class="mb-1 block text-sm font-medium text-foreground">Código de empleado</label>
              <div id="e-code-readonly" class="flex h-[42px] items-center rounded-lg border border-border bg-surface-muted px-3 font-mono text-sm text-foreground-muted">
                {fCode || '—'}
              </div>
            </div>
          {/if}
          <FormField id="e-status" label="Estado" bind:value={fStatus} options={STATUS_OPTIONS} />
          <FormField id="e-first" label="Nombre" bind:value={fFirst} required />
          <FormField id="e-last" label="Apellido" bind:value={fLast} required />
        </div>
      </div>
    </Card>

    <!-- Sección: Foto URL -->
    <Card class="p-6">
      <h3 class="mb-1 text-sm font-semibold text-foreground">Foto del empleado</h3>
      <p class="mb-4 text-xs text-foreground-muted">Pega la URL de una imagen (opcional). Se mostrará como avatar circular.</p>
      <FormField id="e-photo" label="URL de la foto" bind:value={fPhotoUrl} placeholder="https://i.pravatar.cc/300?u=..." />
    </Card>

    <!-- Sección: Datos laborales -->
    <Card class="p-6">
      <h3 class="mb-4 text-sm font-semibold text-foreground">Datos laborales</h3>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <FormField
          id="e-dept"
          label="Departamento"
          bind:value={fDept}
          options={[{ value: '', label: '— Ninguno —' }, ...departments.map((d) => ({ value: d.id, label: d.name }))]}
        />
        <FormField id="e-position" label="Cargo" bind:value={fPosition} placeholder="Desarrollador" />
        <FormField id="e-hire" label="Fecha de contratación" type="date" bind:value={fHireDate} />
        {#if mode === 'edit'}
          <FormField id="e-termination" label="Fecha de terminación" type="date" bind:value={fTerminationDate} />
        {/if}
      </div>
    </Card>

    <!-- Sección: Datos personales -->
    <Card class="p-6">
      <h3 class="mb-4 text-sm font-semibold text-foreground">Datos personales</h3>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <FormField id="e-doc" label="Documento de identidad" bind:value={fDocId} placeholder="DUI / Pasaporte" />
        <FormField id="e-birth" label="Fecha de nacimiento" type="date" bind:value={fBirthDate} />
        <FormField id="e-phone" label="Teléfono" bind:value={fPhone} placeholder="+503 0000-0000" />
        <div class="sm:col-span-2">
          <FormField id="e-address" label="Dirección" bind:value={fAddress} placeholder="Calle, ciudad" />
        </div>
      </div>
    </Card>

    <!-- Acciones -->
    <div class="flex justify-end gap-2 pb-8">
      <Button variant="secondary" onclick={handleCancel} disabled={formLoading}>Cancelar</Button>
      <Button type="submit" disabled={!canSubmit}>
        {formLoading ? 'Guardando...' : mode === 'create' ? 'Crear empleado' : 'Guardar cambios'}
      </Button>
    </div>
  </form>
</div>