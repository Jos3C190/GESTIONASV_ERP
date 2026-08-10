<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { api, HttpError } from '$lib/api/client';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';

  type Location = {
    id: string;
    code: string;
    aisle: string;
    rack: string;
    level: string;
    position: string;
    capacity: number;
    notes: string | null;
    is_active: boolean;
  };

  let items = $state<Location[]>([]);
  let warehouseName = $state('');
  let loading = $state(true);
  let error = $state<string | null>(null);
  let open = $state(false);
  let editing = $state<Location | null>(null);
  let saving = $state(false);
  let f = $state({
    code: '',
    aisle: '',
    rack: '',
    level: '',
    position: '',
    capacity: '',
    notes: ''
  });

  const id = $derived(page.params.id ?? '');

  async function load() {
    loading = true;
    error = null;
    try {
      const [w, list] = await Promise.all([api.warehouses.get(id), api.locations.list(id)]);
      warehouseName = w.name;
      items = list as unknown as Location[];
    } catch (e) {
      error = e instanceof HttpError ? e.message : 'No se pudieron cargar las ubicaciones.';
    } finally {
      loading = false;
    }
  }

  onMount(load);

  function create() {
    editing = null;
    f = { code: '', aisle: '', rack: '', level: '', position: '', capacity: '', notes: '' };
    open = true;
  }

  function edit(x: Location) {
    editing = x;
    f = {
      code: x.code,
      aisle: x.aisle,
      rack: x.rack,
      level: x.level,
      position: x.position,
      capacity: String(x.capacity),
      notes: x.notes ?? ''
    };
    open = true;
  }

  async function save(e: SubmitEvent) {
    e.preventDefault();
    saving = true;
    try {
      const p = { ...f, warehouse_id: id, capacity: Number(f.capacity), notes: f.notes || null };
      if (editing) await api.locations.update(editing.id, p);
      else await api.locations.create(p);
      open = false;
      await load();
    } catch (e) {
      error = e instanceof HttpError ? e.message : 'No se pudo guardar la ubicación.';
    } finally {
      saving = false;
    }
  }

  async function toggle(x: Location) {
    if (x.is_active) {
      confirmation.request({
        kind: 'deactivate',
        title: 'Desactivar ubicación física',
        description:
          'La ubicación dejará de estar disponible para nuevas operaciones de inventario. Sus datos históricos se conservarán.',
        resourceName: x.code,
        confirmLabel: 'Desactivar ubicación',
        execute: async () => {
          await api.locations.deactivate(x.id);
          await load();
        }
      });
      return;
    }
    try {
      await api.locations.activate(x.id);
      await load();
    } catch (e) {
      error = e instanceof HttpError ? e.message : 'No se pudo activar la ubicación.';
    }
  }

  function menuItems(x: Location): KebabItem[] {
    const res: KebabItem[] = [];
    if (permissions.hasPermission('locations.update')) {
      res.push({
        id: 'edit',
        label: 'Editar',
        icon: 'edit',
        onClick: () => edit(x)
      });
    }
    if (permissions.hasAnyPermission(['locations.activate', 'locations.deactivate'])) {
      res.push({
        id: 'toggle-status',
        label: x.is_active ? 'Desactivar' : 'Activar',
        icon: x.is_active ? 'delete' : 'edit',
        variant: x.is_active ? 'danger' : 'default',
        onClick: () => toggle(x)
      });
    }
    return res;
  }
</script>

<svelte:head><title>Ubicaciones físicas — GestionaSV</title></svelte:head>

<div class="p-6 md:p-8">
  <!-- Header con botón back (Homologado con detalle de almacén) -->
  <div class="mb-6 flex items-center gap-3">
    <a
      href="/warehouses/{id}"
      class="flex h-8 w-8 flex-none items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground"
      aria-label="Volver al almacén"
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
    <div class="flex-1 min-w-0">
      <h1 class="text-xl font-bold text-foreground">Ubicaciones físicas</h1>
      <p class="text-sm text-foreground-muted truncate">
        {warehouseName ? `Organización y capacidad física de ${warehouseName}.` : 'Cargando información del almacén...'}
      </p>
    </div>
    {#if permissions.hasPermission('locations.create')}
      <Button size="sm" onclick={create}>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
          ><path d="M12 5v14M5 12h14" /></svg
        >
        Nueva ubicación
      </Button>
    {/if}
  </div>

  {#if error}
    <div class="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">
      {error}
    </div>
  {/if}

  <Card class="overflow-hidden p-0">
    {#if loading}
      <div class="flex items-center justify-center py-16">
        <p class="text-sm text-foreground-muted">Cargando ubicaciones...</p>
      </div>
    {:else if items.length === 0}
      <div class="flex flex-col items-center justify-center py-16">
        <p class="text-sm text-foreground-muted">No se encontraron ubicaciones físicas en este almacén.</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="border-b border-border bg-surface-muted">
            <tr>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Código</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Pasillo</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Rack</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Nivel</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Posición</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Capacidad</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Estado</th>
              <th class="px-2 py-3 text-center font-semibold text-foreground w-11"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each items as x (x.id)}
              <tr class="hover:bg-surface-muted">
                <td class="px-4 py-3 font-mono font-semibold text-foreground">{x.code}</td>
                <td class="px-4 py-3 text-foreground-muted">{x.aisle}</td>
                <td class="px-4 py-3 text-foreground-muted">{x.rack}</td>
                <td class="px-4 py-3 text-foreground-muted">{x.level}</td>
                <td class="px-4 py-3 text-foreground-muted">{x.position}</td>
                <td class="px-4 py-3 font-mono text-foreground">{x.capacity}</td>
                <td class="px-4 py-3">
                  <span
                    class="{x.is_active ? 'badge-success' : 'badge-neutral'} inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"
                  >
                    <span class="h-1.5 w-1.5 rounded-full bg-current"></span>
                    {x.is_active ? 'Activa' : 'Inactiva'}
                  </span>
                </td>
                <td class="px-2 py-3 text-center">
                  <KebabMenu items={menuItems(x)} />
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </Card>
</div>

<Modal
  {open}
  title={editing ? 'Editar ubicación' : 'Nueva ubicación'}
  onclose={() => (open = false)}
>
  <form class="grid grid-cols-2 gap-4" onsubmit={save}>
    <FormField id="loc-code" label="Código" bind:value={f.code} required />
    <FormField id="loc-aisle" label="Pasillo" bind:value={f.aisle} required />
    <FormField id="loc-rack" label="Rack" bind:value={f.rack} required />
    <FormField id="loc-level" label="Nivel" bind:value={f.level} required />
    <FormField id="loc-position" label="Posición" bind:value={f.position} required />
    <FormField
      id="loc-capacity"
      label="Capacidad"
      type="number"
      bind:value={f.capacity}
      required
    />
    <div class="col-span-2"><FormField id="loc-notes" label="Notas" bind:value={f.notes} /></div>
    <div class="col-span-2 flex justify-end gap-2 pt-2 border-t border-border">
      <Button variant="ghost" onclick={() => (open = false)}>Cancelar</Button>
      <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</Button>
    </div>
  </form>
</Modal>
