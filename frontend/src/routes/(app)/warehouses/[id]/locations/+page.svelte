<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { api, HttpError } from '$lib/api/client';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
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
    try {
      const [w, list] = await Promise.all([api.warehouses.get(id), api.locations.list(id)]);
      warehouseName = w.name;
      items = list as unknown as Location[];
    } catch (e) {
      error = e instanceof HttpError ? e.message : 'No se pudieron cargar las ubicaciones.';
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
      error = e instanceof HttpError ? e.message : 'No se pudo guardar.';
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
</script>

<svelte:head><title>Ubicaciones — ERP System</title></svelte:head>
<div class="p-4 sm:p-6 md:p-8">
  <header class="mb-6 flex items-center justify-between">
    <div>
      <a href="/warehouses/{id}" class="text-xs text-primary">← Volver al almacén</a>
      <h1 class="mt-2 text-2xl font-bold">Ubicaciones físicas</h1>
      <p class="text-sm text-foreground-muted">{warehouseName}</p>
    </div>
    {#if permissions.hasPermission('locations.create')}<Button onclick={create}
        >Nueva ubicación</Button
      >{/if}
  </header>
  {#if error}<p class="mb-4 rounded-xl bg-danger/10 p-3 text-sm text-danger">{error}</p>{/if}
  <div class="overflow-hidden rounded-xl border border-border bg-surface-elevated">
    <table class="w-full text-sm">
      <thead class="bg-surface-muted"
        ><tr
          >{#each ['Código', 'Pasillo', 'Rack', 'Nivel', 'Posición', 'Capacidad', 'Estado', ''] as h}<th
              class="p-3 text-left">{h}</th
            >{/each}</tr
        ></thead
      ><tbody
        >{#each items as x (x.id)}<tr class="border-t border-border"
            ><td class="p-3 font-mono font-semibold">{x.code}</td><td class="p-3">{x.aisle}</td><td
              class="p-3">{x.rack}</td
            ><td class="p-3">{x.level}</td><td class="p-3">{x.position}</td><td class="p-3"
              >{x.capacity}</td
            ><td class="p-3">{x.is_active ? 'Activa' : 'Inactiva'}</td><td class="p-3"
              ><div class="flex gap-1">
                {#if permissions.hasPermission('locations.update')}<Button
                    size="sm"
                    variant="ghost"
                    onclick={() => edit(x)}>Editar</Button
                  >{/if}{#if permissions.hasAnyPermission( ['locations.activate', 'locations.deactivate'] )}<Button
                    size="sm"
                    variant="ghost"
                    onclick={() => toggle(x)}>{x.is_active ? 'Desactivar' : 'Activar'}</Button
                  >{/if}
              </div></td
            ></tr
          >{/each}</tbody
      >
    </table>
  </div>
</div>
<Modal
  {open}
  title={editing ? 'Editar ubicación' : 'Nueva ubicación'}
  onclose={() => (open = false)}
  ><form class="grid grid-cols-2 gap-4" onsubmit={save}>
    <FormField id="loc-code" label="Código" bind:value={f.code} required /><FormField
      id="loc-aisle"
      label="Pasillo"
      bind:value={f.aisle}
      required
    /><FormField id="loc-rack" label="Rack" bind:value={f.rack} required /><FormField
      id="loc-level"
      label="Nivel"
      bind:value={f.level}
      required
    /><FormField id="loc-position" label="Posición" bind:value={f.position} required /><FormField
      id="loc-capacity"
      label="Capacidad"
      type="number"
      bind:value={f.capacity}
      required
    />
    <div class="col-span-2"><FormField id="loc-notes" label="Notas" bind:value={f.notes} /></div>
    <div class="col-span-2 flex justify-end gap-2">
      <Button variant="ghost" onclick={() => (open = false)}>Cancelar</Button><Button
        type="submit"
        disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</Button
      >
    </div>
  </form></Modal
>
