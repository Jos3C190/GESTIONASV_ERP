<script lang="ts">
  import { api, HttpError, type DepartmentOut } from '$lib/api/client';
  import EmployeeForm from '$lib/features/employees/components/EmployeeForm.svelte';

  let departments = $state<DepartmentOut[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  async function loadDepartments() {
    loading = true;
    error = null;
    try {
      departments = await api.departments.list();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error al cargar departamentos.';
    } finally {
      loading = false;
    }
  }

  $effect(() => { loadDepartments(); });
</script>

<svelte:head><title>Crear empleado — ERP System</title></svelte:head>

<div class="p-6 md:p-8">
  <div class="mb-6 flex items-center gap-3">
    <a href="/employees" class="flex h-8 w-8 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground" aria-label="Volver">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
    </a>
    <div>
      <h1 class="text-xl font-bold text-foreground">Crear empleado</h1>
      <p class="text-sm text-foreground-muted">Registra un nuevo empleado en el sistema.</p>
    </div>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-16">
      <div class="flex flex-col items-center gap-3">
        <svg class="animate-spin h-5 w-5 text-primary" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <p class="text-xs text-foreground-subtle">Cargando...</p>
      </div>
    </div>
  {:else if error}
    <div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}</div>
  {:else}
    <EmployeeForm mode="create" {departments} />
  {/if}
</div>