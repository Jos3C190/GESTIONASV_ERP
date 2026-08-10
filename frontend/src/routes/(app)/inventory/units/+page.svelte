<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { session } from '$lib/stores/session.svelte';
  import type { Unit } from '$lib/types/catalog';

  type ScopeFilter = 'all' | 'standard' | 'custom';
  const UNIT_TYPES = ['Cantidad', 'Empaque', 'Masa', 'Volumen', 'Longitud', 'Área', 'Tiempo'];

  let units = $state<Unit[]>([]);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let filter = $state<ScopeFilter>('all');
  let showInactive = $state(false);
  let modalOpen = $state(false);
  let editing = $state<Unit | null>(null);
  let globalMode = $state(false);
  let name = $state('');
  let code = $state('');
  let symbol = $state('');
  let type = $state(UNIT_TYPES[0] ?? 'Cantidad');
  let description = $state('');

  let filtered = $derived.by(() => {
    const query = globalSearch.query.trim().toLocaleLowerCase('es-SV');
    return units.filter((unit) => {
      if (!showInactive && !unit.is_enabled) return false;
      if (filter === 'standard' && !unit.is_standard) return false;
      if (filter === 'custom' && unit.is_standard) return false;
      if (!query) return true;
      return [unit.name, unit.alias, unit.code, unit.symbol, unit.type]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase('es-SV').includes(query));
    });
  });

  async function load() {
    loading = true;
    error = null;
    try {
      units = await catalogApi.listUnits(false);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudieron cargar las unidades de medida.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  function openCreate(asGlobal = false) {
    editing = null;
    globalMode = asGlobal;
    name = '';
    code = '';
    symbol = '';
    type = UNIT_TYPES[0] ?? 'Cantidad';
    description = '';
    modalOpen = true;
  }

  function openEdit(unit: Unit) {
    editing = unit;
    globalMode = unit.is_standard;
    name = unit.name;
    code = unit.code;
    symbol = unit.symbol;
    type = unit.type;
    description = unit.description ?? '';
    modalOpen = true;
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    saving = true;
    error = null;
    const payload = { name: name.trim(), code: code.trim(), symbol: symbol.trim(), type, description: description.trim() || undefined };
    try {
      if (editing) {
        const updatePayload = { ...payload, description: payload.description ?? '', version: editing.version };
        if (globalMode) await catalogApi.updateGlobalUnit(editing.id_unit, updatePayload);
        else await catalogApi.updateUnit(editing.id_unit, updatePayload);
      } else if (globalMode) {
        await catalogApi.createGlobalUnit(payload);
      } else {
        await catalogApi.createUnit(payload);
      }
      modalOpen = false;
      await load();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo guardar la unidad.';
    } finally {
      saving = false;
    }
  }

  async function toggle(unit: Unit) {
    const enabling = !unit.is_enabled;
    if (enabling) {
      error = null;
      try {
        await catalogApi.activateUnit(unit.id_unit, unit.configuration_version, unit.alias);
        await load();
      } catch (err) {
        error = err instanceof HttpError ? err.message : 'No se pudo activar la unidad.';
      }
      return;
    }
    confirmation.request({
      kind: 'deactivate',
      title: 'Desactivar unidad',
      description: unit.usage_count > 0
          ? `Esta unidad está vinculada a ${unit.usage_count} producto(s) y no puede desactivarse mientras siga en uso.`
          : 'La unidad dejará de aparecer en nuevas asignaciones. No se eliminará su historial.',
      resourceName: unit.alias || unit.name,
      confirmLabel: 'Desactivar unidad',
      execute: async () => {
        await catalogApi.deactivateUnit(unit.id_unit, unit.configuration_version, unit.alias);
        await load();
      }
    });
  }

  function menuItems(unit: Unit): KebabItem[] {
    const items: KebabItem[] = [];
    const canEdit = unit.is_standard
      ? Boolean(session.user?.is_superuser && permissions.hasPermission('units:manage_global'))
      : permissions.hasPermission('units:update');
    if (canEdit) items.push({ id: 'edit', label: 'Editar', icon: 'edit', onClick: () => openEdit(unit) });
    const permission = unit.is_enabled ? 'units:deactivate' : 'units:activate';
    if (permissions.hasPermission(permission)) {
      items.push({
        id: 'state',
        label: unit.is_enabled ? 'Desactivar' : 'Activar',
        icon: 'power',
        variant: unit.is_enabled ? 'danger' : 'default',
        onClick: () => void toggle(unit)
      });
    }
    return items;
  }
</script>

<svelte:head><title>Unidades de medida — GestionaSV</title></svelte:head>

<div class="space-y-5 p-4 sm:p-6 md:p-8">
  <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
    <div>
      <p class="text-sm text-foreground-muted">
        {units.length} unidad(es) disponibles · Catálogo estándar y personalizado de la empresa
      </p>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <select bind:value={filter} class="h-9 rounded-md border border-border bg-surface px-3 text-sm text-foreground" aria-label="Filtrar por alcance">
        <option value="all">Todas</option><option value="standard">Estándares</option><option value="custom">Personalizadas</option>
      </select>
      <label class="flex h-9 items-center gap-2 rounded-md border border-border px-3 text-xs text-foreground-muted">
        <input type="checkbox" bind:checked={showInactive} /> Mostrar inactivas
      </label>
      {#if permissions.hasPermission('units:create')}
        <Button size="sm" onclick={() => openCreate(false)}>+ Nueva unidad</Button>
      {/if}
      {#if session.user?.is_superuser && permissions.hasPermission('units:manage_global')}
        <Button size="sm" variant="secondary" onclick={() => openCreate(true)}>+ Unidad estándar</Button>
      {/if}
    </div>
  </div>

  {#if error}
    <p class="rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger" role="alert">{error}</p>
  {/if}

  {#if loading}
    <div class="h-72 rounded-xl skeleton"></div>
  {:else if filtered.length === 0}
    <div class="rounded-xl border border-dashed border-border bg-surface-elevated px-6 py-14 text-center">
      <p class="text-sm font-semibold text-foreground">Sin unidades coincidentes</p>
      <p class="mt-1 text-xs text-foreground-muted">Ajuste la búsqueda o los filtros seleccionados.</p>
    </div>
  {:else}
    <div class="overflow-x-auto rounded-xl border border-border bg-surface-elevated">
      <table class="w-full min-w-[820px] text-sm">
        <thead class="bg-surface-muted text-xs text-foreground-muted">
          <tr><th class="p-3 text-left">Unidad</th><th class="p-3 text-left">Código</th><th class="p-3 text-left">Magnitud</th><th class="p-3 text-left">Alcance</th><th class="p-3 text-left">Uso</th><th class="p-3 text-left">Estado</th><th class="w-12 p-3"></th></tr>
        </thead>
        <tbody>
          {#each filtered as unit (unit.id_unit)}
            <tr class="border-t border-border transition-colors hover:bg-surface-muted/40">
              <td class="p-3"><p class="font-semibold text-foreground">{unit.alias || unit.name}</p><p class="text-xs text-foreground-muted">{unit.symbol}{unit.alias ? ` · ${unit.name}` : ''}</p></td>
              <td class="p-3 font-mono text-xs text-foreground-muted">{unit.code}</td>
              <td class="p-3 text-foreground-muted">{unit.type}</td>
              <td class="p-3"><Badge variant={unit.is_standard ? 'primary' : 'neutral'}>{unit.is_standard ? 'Estándar' : 'Personalizada'}</Badge></td>
              <td class="p-3 text-foreground-muted">{unit.usage_count} producto(s)</td>
              <td class="p-3"><Badge variant={unit.is_enabled ? 'success' : 'neutral'}>{unit.is_enabled ? 'Activa' : 'Inactiva'}</Badge></td>
              <td class="p-3"><KebabMenu items={menuItems(unit)} /></td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<Modal open={modalOpen} title={editing ? 'Editar unidad' : globalMode ? 'Nueva unidad estándar' : 'Nueva unidad personalizada'} onclose={() => (modalOpen = false)}>
  <form class="space-y-4" onsubmit={save}>
    {#if globalMode}
      <p class="rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-foreground-muted">Los cambios en una unidad estándar afectan su definición global. La disponibilidad continúa controlándose por empresa.</p>
    {/if}
    <div class="grid gap-4 sm:grid-cols-2">
      <FormField id="unit-name" label="Nombre" bind:value={name} required />
      <FormField id="unit-code" label="Código" bind:value={code} required />
      <FormField id="unit-symbol" label="Símbolo" bind:value={symbol} required />
      <div><label for="unit-type" class="mb-1 block text-xs font-medium text-foreground-muted">Magnitud *</label><select id="unit-type" bind:value={type} class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground">{#each UNIT_TYPES as option}<option value={option}>{option}</option>{/each}</select></div>
    </div>
    <FormField id="unit-description" label="Descripción" bind:value={description} />
    <div class="flex justify-end gap-2 border-t border-border pt-4"><Button type="button" variant="ghost" onclick={() => (modalOpen = false)}>Cancelar</Button><Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</Button></div>
  </form>
</Modal>
