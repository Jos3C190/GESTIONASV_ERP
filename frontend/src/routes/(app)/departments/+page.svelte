<script lang="ts">
  import { api, HttpError, type DepartmentOut } from '$lib/api/client';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';

  let departments = $state<DepartmentOut[]>([]);
  let loading = $state(false);
  let error = $state<string | null>(null);

  let modalMode = $state<'create' | 'edit' | null>(null);
  let modalDept = $state<DepartmentOut | null>(null);
  let formError = $state<string | null>(null);
  let formLoading = $state(false);
  let fName = $state('');
  let fDescription = $state('');
  let fParentId = $state('');

  async function loadDepartments() {
    loading = true; error = null;
    try { departments = await api.departments.list(); }
    catch (err) { error = err instanceof HttpError ? err.message : 'Error.'; }
    finally { loading = false; }
  }

  function parentName(id: string | null): string {
    if (!id) return 'Sin padre (raíz)';
    return departments.find((d) => d.id === id)?.name ?? '—';
  }

  function openCreate() { modalMode = 'create'; modalDept = null; formError = null; fName = ''; fDescription = ''; fParentId = ''; }
  function openEdit(d: DepartmentOut) { modalMode = 'edit'; modalDept = d; formError = null; fName = d.name; fDescription = d.description ?? ''; fParentId = d.parent_department_id ?? ''; }
  function closeModal() { modalMode = null; modalDept = null; formError = null; }

  async function handleSubmit() {
    formLoading = true; formError = null;
    try {
      const data = { name: fName, description: fDescription || undefined, parent_department_id: fParentId || undefined };
      if (modalMode === 'create') { await api.departments.create(data); }
      else if (modalMode === 'edit' && modalDept) { await api.departments.update(modalDept.id, data); }
      closeModal(); await loadDepartments();
    } catch (err) { formError = err instanceof HttpError ? err.message : 'Error.'; }
    finally { formLoading = false; }
  }

  async function deleteDept(d: DepartmentOut) {
    if (!confirm(`¿Eliminar el departamento "${d.name}"?`)) return;
    try { await api.departments.delete(d.id); await loadDepartments(); }
    catch (err) { error = err instanceof HttpError ? err.message : 'Error.'; }
  }

  let levelFilter = $state('');

  let filteredDepartments = $derived.by(() => {
    const q = globalSearch.query.toLowerCase().trim();
    let result = departments;
    if (q) {
      result = result.filter(d =>
        d.name.toLowerCase().includes(q) ||
        (d.description ?? '').toLowerCase().includes(q)
      );
    }
    if (levelFilter === 'root') result = result.filter(d => !d.parent_department_id);
    else if (levelFilter === 'child') result = result.filter(d => !!d.parent_department_id);
    return result;
  });

  $effect(() => { loadDepartments(); });
</script>

<svelte:head><title>Departamentos — ERP System</title></svelte:head>

<div class="p-6 md:p-8">
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">{filteredDepartments.length} departamento(s)</p>
    <div class="flex items-center gap-2">
      <select bind:value={levelFilter} class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none">
        <option value="">Todos</option>
        <option value="root">Raíz</option>
        <option value="child">Con padre</option>
      </select>
      <Button size="sm" onclick={openCreate}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        Crear
      </Button>
    </div>
  </div>

  {#if error}
    <div class="mb-4 animate-fade-scale rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}</div>
  {/if}

  {#if loading}
    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {#each Array(6) as _}
        <div class="h-36 rounded-2xl border border-border skeleton"></div>
      {/each}
    </div>
  {:else if departments.length === 0}
    <Card class="p-12">
      <div class="flex flex-col items-center text-center">
        <div class="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-muted">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="text-foreground-subtle"><path d="M19 21V5a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5" /></svg>
        </div>
        <p class="text-sm text-foreground-muted">No hay departamentos. Cree uno para empezar.</p>
        <div class="mt-4"><Button onclick={openCreate}>Crear departamento</Button></div>
      </div>
    </Card>
  {:else}
    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {#each filteredDepartments as dept (dept.id)}
        <Card class="p-5 hover-lift">
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-3">
              <div class="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-accent/10">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="text-accent"><path d="M19 21V5a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5" /></svg>
              </div>
              <div>
                <h3 class="text-base font-bold text-foreground">{dept.name}</h3>
                <p class="text-xs text-foreground-muted">{dept.description ?? 'Sin descripción'}</p>
              </div>
            </div>
          </div>

          <div class="mt-4 flex items-center gap-2 rounded-lg bg-surface-muted/50 px-3 py-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="text-foreground-subtle"><path d="M15 18l-6-6 6-6" /></svg>
            <span class="text-xs text-foreground-subtle">{parentName(dept.parent_department_id)}</span>
          </div>

          <div class="mt-4 flex items-center gap-2 border-t border-border pt-3">
            <Button variant="ghost" size="sm" onclick={() => openEdit(dept)}>Editar</Button>
            <Button variant="ghost" size="sm" onclick={() => deleteDept(dept)} class="!text-danger hover:!bg-danger/10">Eliminar</Button>
          </div>
        </Card>
      {/each}
    </div>
  {/if}
</div>

<Modal open={modalMode !== null} title={modalMode === 'create' ? 'Crear departamento' : 'Editar departamento'} onclose={closeModal}>
  <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
    {#if formError}<div class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-2.5 text-sm text-danger">{formError}</div>{/if}
    <FormField id="d-name" label="Nombre" bind:value={fName} required placeholder="Ventas" />
    <FormField id="d-desc" label="Descripción" bind:value={fDescription} placeholder="Departamento de ventas" />
    <FormField id="d-parent" label="Departamento padre" bind:value={fParentId} options={[{ value: '', label: '— Ninguno (raíz) —' }, ...departments.filter(d => d.id !== modalDept?.id).map(d => ({ value: d.id, label: d.name }))]} />
    <div class="flex justify-end gap-2 pt-2"><Button variant="secondary" onclick={closeModal}>Cancelar</Button><Button type="submit" disabled={formLoading}>{formLoading ? 'Guardando...' : 'Guardar'}</Button></div>
  </form>
</Modal>