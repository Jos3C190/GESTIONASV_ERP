<script lang="ts">
  import { onMount } from 'svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import Callout from '$lib/components/ui/Callout.svelte';
  import { catalogApi } from '$lib/api/catalog';
  import type { Unit } from '$lib/types/catalog';

  // Svelte 5 Runes State
  let units = $state<Unit[]>([]);
  let loading = $state<boolean>(true);
  let errorMsg = $state<string | null>(null);

  // Modal State
  let showModal = $state<boolean>(false);
  let isEditing = $state<boolean>(false);
  let editingId = $state<number | null>(null);
  let formName = $state<string>('');
  let formType = $state<string>('');
  let formIsActive = $state<boolean>(true);
  let saving = $state<boolean>(false);

  const UNIT_TYPES = ['Cantidad', 'Empaque', 'Masa', 'Volumen', 'Longitud', 'Área', 'Tiempo'];

  async function loadData() {
    loading = true;
    errorMsg = null;
    try {
      units = await catalogApi.listUnits(false);
    } catch (err: any) {
      errorMsg = err.message || 'Error al cargar unidades de medida';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadData();
  });

  function openCreateModal() {
    isEditing = false;
    editingId = null;
    formName = '';
    formType = UNIT_TYPES[0] ?? 'Cantidad';
    formIsActive = true;
    showModal = true;
  }

  function openEditModal(u: Unit) {
    isEditing = true;
    editingId = u.id_unit;
    formName = u.name;
    formType = u.type;
    formIsActive = u.is_active;
    showModal = true;
  }

  async function handleSave(e: SubmitEvent) {
    e.preventDefault();
    saving = true;
    try {
      if (isEditing && editingId) {
        await catalogApi.updateUnit(editingId, {
          name: formName,
          type: formType,
          is_active: formIsActive,
        });
      } else {
        await catalogApi.createUnit({
          name: formName,
          type: formType,
        });
      }
      showModal = false;
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Error al guardar la unidad de medida');
    } finally {
      saving = false;
    }
  }
</script>

<svelte:head><title>Unidades de Medida — ERP System</title></svelte:head>

<div class="flex flex-col gap-6 p-6 animate-fade-scale">
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold text-foreground">Unidades de Medida</h1>
      <p class="mt-1 text-sm text-foreground-muted">Catálogo de unidades físicas y empaques comerciales para compras y ventas.</p>
    </div>
    <Button variant="primary" onclick={openCreateModal}>Nueva Unidad</Button>
  </div>

  {#if errorMsg}
    <Callout variant="warning">{errorMsg}</Callout>
  {/if}

  <Card class="overflow-hidden p-0">
    {#if loading}
      <div class="p-8 space-y-4">
        {#each Array(4) as _}
          <div class="h-8 bg-surface-muted rounded animate-pulse"></div>
        {/each}
      </div>
    {:else if units.length === 0}
      <div class="p-12 text-center text-foreground-muted">No hay unidades de medida registradas.</div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm text-foreground">
          <thead class="bg-surface-muted text-xs uppercase text-foreground-muted border-b border-border">
            <tr>
              <th class="px-4 py-3">Unidad de Medida</th>
              <th class="px-4 py-3">Tipo / Magnitud</th>
              <th class="px-4 py-3">Estado</th>
              <th class="px-4 py-3 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each units as unit}
              <tr class="hover:bg-surface-muted/50 transition-colors">
                <td class="px-4 py-3 font-medium">{unit.name}</td>
                <td class="px-4 py-3 text-foreground-muted">
                  <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-surface-muted border border-border">
                    {unit.type}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <Badge variant={unit.is_active ? 'success' : 'neutral'}>{unit.is_active ? 'Activa' : 'Inactiva'}</Badge>
                </td>
                <td class="px-4 py-3 text-right">
                  <Button variant="ghost" size="sm" onclick={() => openEditModal(unit)}>Editar</Button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </Card>

  {#if showModal}
    <Modal open={showModal} title={isEditing ? 'Editar Unidad de Medida' : 'Nueva Unidad de Medida'} onclose={() => (showModal = false)}>
      <form onsubmit={handleSave} class="space-y-4">
        <div>
          <label for="uname" class="block text-xs font-medium text-foreground-muted mb-1">Nombre / Símbolo *</label>
          <input id="uname" type="text" required bind:value={formName} placeholder="Ej: Kilogramo (kg)" class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" />
        </div>
        <div>
          <label for="utype" class="block text-xs font-medium text-foreground-muted mb-1">Tipo *</label>
          <select id="utype" required bind:value={formType} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
            {#each UNIT_TYPES as type}
              <option value={type}>{type}</option>
            {/each}
          </select>
        </div>
        {#if isEditing}
          <div class="flex items-center gap-2">
            <input type="checkbox" id="uactive" bind:checked={formIsActive} />
            <label for="uactive" class="text-sm text-foreground">Unidad Activa</label>
          </div>
        {/if}
        <div class="flex justify-end gap-2 pt-4 border-t border-border">
          <Button type="button" variant="secondary" onclick={() => (showModal = false)}>Cancelar</Button>
          <Button type="submit" variant="primary" disabled={saving}>{saving ? 'Guardando...' : 'Guardar'}</Button>
        </div>
      </form>
    </Modal>
  {/if}
</div>
