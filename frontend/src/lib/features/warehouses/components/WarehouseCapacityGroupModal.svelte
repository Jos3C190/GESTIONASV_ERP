<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import {
    availableCapacityGroupParents,
    capacityGroupDraftToInput,
    capacityGroupPath,
    capacityGroupToDraft,
    emptyCapacityGroupDraft,
    validateCapacityGroupDraft
  } from '../capacity-groups.logic';
  import { createCapacityGroup, updateCapacityGroup } from '../capacity-groups.service';
  import {
    CAPACITY_GROUP_TYPE_OPTIONS,
    type CapacityGroupFieldErrors,
    type WarehouseCapacityGroup,
    type WarehouseCapacityGroupDraft
  } from '../capacity-groups.types';
  import type { Warehouse } from '../types';

  interface Props {
    open: boolean;
    warehouseId: string;
    groups: WarehouseCapacityGroup[];
    warehouse: Warehouse;
    group?: WarehouseCapacityGroup | null;
    initialParentId?: string | null;
    onclose: () => void;
    onsaved: (group: WarehouseCapacityGroup) => void;
  }

  let {
    open,
    warehouseId,
    groups,
    warehouse,
    group = null,
    initialParentId = null,
    onclose,
    onsaved
  }: Props = $props();

  const PROFILE_OPTIONS = [
    { value: 'general_mixed', label: 'Mixto general' },
    { value: 'rack', label: 'Rack' },
    { value: 'bulk_floor', label: 'Piso / granel' },
    { value: 'cold', label: 'Cámara fría' },
    { value: 'oversize_manual', label: 'Sobredimensionado manual' },
    { value: 'transit', label: 'Tránsito' }
  ];
  const ENFORCEMENT_OPTIONS = [
    { value: 'disabled', label: 'Deshabilitado' },
    { value: 'observe', label: 'Solo observar' },
    { value: 'enforce', label: 'Bloquear excesos' }
  ];

  let draft = $state<WarehouseCapacityGroupDraft>(emptyCapacityGroupDraft());
  let errors = $state<CapacityGroupFieldErrors>({});
  let saveError = $state<string | null>(null);
  let saving = $state(false);
  let contextKey = $state('');

  let editing = $derived(Boolean(group));
  const parentLimits = (candidate: WarehouseCapacityGroup) => {
    const weight =
      candidate.operationalMaxWeightKg == null
        ? 'peso sin límite'
        : `${candidate.operationalMaxWeightKg.toLocaleString('es-SV')} kg operativos`;
    const volume =
      candidate.operationalUsableVolumeM3 == null
        ? 'volumen sin límite'
        : `${candidate.operationalUsableVolumeM3.toLocaleString('es-SV')} m³ operativos`;
    return `${weight} · ${volume}`;
  };
  let parentOptions = $derived(
    availableCapacityGroupParents(groups, group?.id ?? null).map((candidate) => ({
      value: candidate.id,
      label: `${capacityGroupPath(groups, candidate.id)} · ${candidate.name}`,
      description: `${
        CAPACITY_GROUP_TYPE_OPTIONS.find((option) => option.value === candidate.groupType)?.label ??
        'Estructura'
      } · ${parentLimits(candidate)}`
    }))
  );

  $effect(() => {
    const nextKey = open
      ? `${group?.id ?? 'new'}:${initialParentId ?? ''}:${group?.updatedAt ?? ''}`
      : 'closed';
    if (contextKey === nextKey) return;
    contextKey = nextKey;
    draft = group ? capacityGroupToDraft(group) : emptyCapacityGroupDraft();
    if (!group && initialParentId) draft.parent_id = initialParentId;
    errors = {};
    saveError = null;
    saving = false;
  });

  async function save() {
    const nextErrors = validateCapacityGroupDraft(draft, groups, group?.id ?? null, warehouse);
    errors = nextErrors;
    saveError = null;
    if (Object.keys(nextErrors).length > 0) return;

    saving = true;
    try {
      const input = capacityGroupDraftToInput(draft);
      const saved = group
        ? await updateCapacityGroup(warehouseId, group.id, input)
        : await createCapacityGroup(warehouseId, input);
      onsaved(saved);
    } catch (error) {
      saveError =
        error instanceof HttpError
          ? error.message
          : 'No se pudo guardar la estructura de capacidad. Intente nuevamente.';
    } finally {
      saving = false;
    }
  }

  function updateStorageEligibility(event: Event) {
    draft.storage_eligible = (event.currentTarget as HTMLInputElement).checked;
    if (!draft.storage_eligible) draft.capacity_enforcement_mode = 'disabled';
  }
</script>

<Modal
  {open}
  size="lg"
  title={editing ? 'Editar estructura de capacidad' : 'Nueva estructura de capacidad'}
  {onclose}
>
  <form
    class="space-y-6"
    onsubmit={(event) => {
      event.preventDefault();
      void save();
    }}
  >
    {#if saveError}
      <div
        class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        role="alert"
      >
        {saveError}
      </div>
    {/if}
    {#if errors.form}
      <div
        class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        role="alert"
      >
        {errors.form}
      </div>
    {/if}

    <section aria-labelledby="capacity-group-identity-title">
      <div class="mb-4">
        <h3 id="capacity-group-identity-title" class="text-sm font-semibold text-foreground">
          Identidad y relación física
        </h3>
        <p class="mt-1 text-xs leading-5 text-foreground-muted">
          Represente únicamente estructuras o zonas que agrupan ubicaciones y comparten límites.
        </p>
      </div>
      <div class="grid gap-4 sm:grid-cols-2">
        <FormField
          id="capacity-group-code"
          label="Código"
          bind:value={draft.code}
          error={errors.code}
          maxlength={64}
          placeholder="Ej. RACK-A"
          required
        />
        <FormField
          id="capacity-group-name"
          label="Nombre"
          bind:value={draft.name}
          error={errors.name}
          maxlength={160}
          placeholder="Ej. Rack principal A"
          required
        />
        <FormField
          id="capacity-group-type"
          label="Tipo de estructura o zona"
          bind:value={draft.group_type}
          error={errors.group_type}
          options={CAPACITY_GROUP_TYPE_OPTIONS.map((option) => ({
            value: option.value,
            label: option.label
          }))}
          required
        />
        <SmartSelect
          id="capacity-group-parent"
          label="Estructura superior"
          bind:value={draft.parent_id}
          options={parentOptions}
          error={errors.parent_id}
          placeholder="Sin estructura superior"
        />
      </div>
      <p class="mt-3 text-xs text-foreground-muted">
        La estructura superior es opcional. Úsela, por ejemplo, para colocar una bahía o un nivel
        dentro de un rack. Sin estructura superior, se aplican directamente los límites del almacén
        {warehouse.code}: {warehouse.operationalMaxWeightKg == null
          ? 'peso no configurado'
          : `${warehouse.operationalMaxWeightKg.toLocaleString('es-SV')} kg`}
        y {warehouse.operationalUsableVolumeM3 == null
          ? 'volumen no configurado'
          : `${warehouse.operationalUsableVolumeM3.toLocaleString('es-SV')} m³`} operativos.
      </p>
    </section>

    <section class="border-t border-border pt-5" aria-labelledby="capacity-group-limits-title">
      <div class="mb-4">
        <h3 id="capacity-group-limits-title" class="text-sm font-semibold text-foreground">
          Límites físicos
        </h3>
        <p class="mt-1 text-xs leading-5 text-foreground-muted">
          Estos límites se aplican al consumo combinado de todas las ubicaciones vinculadas. El
          certificado es el máximo seguro y el operativo es el máximo de trabajo diario.
        </p>
      </div>
      <div class="grid gap-4 sm:grid-cols-2">
        <FormField
          id="capacity-group-certified-weight"
          type="number"
          label="Peso certificado (kg)"
          bind:value={draft.certified_max_weight_kg}
          error={errors.certified_max_weight_kg}
          min="0.000001"
          step="0.001"
          placeholder="No registrado"
        />
        <FormField
          id="capacity-group-operational-weight"
          type="number"
          label="Peso operativo (kg)"
          bind:value={draft.operational_max_weight_kg}
          error={errors.operational_max_weight_kg}
          min="0.000001"
          step="0.001"
          placeholder="No registrado"
        />
        <FormField
          id="capacity-group-certified-volume"
          type="number"
          label="Volumen útil certificado (m³)"
          bind:value={draft.certified_usable_volume_m3}
          error={errors.certified_usable_volume_m3}
          min="0.000001"
          step="0.001"
          placeholder="No registrado"
        />
        <FormField
          id="capacity-group-operational-volume"
          type="number"
          label="Volumen útil operativo (m³)"
          bind:value={draft.operational_usable_volume_m3}
          error={errors.operational_usable_volume_m3}
          min="0.000001"
          step="0.001"
          placeholder="No registrado"
        />
      </div>
    </section>

    <section class="border-t border-border pt-5" aria-labelledby="capacity-group-dimensions-title">
      <div class="mb-4">
        <h3 id="capacity-group-dimensions-title" class="text-sm font-semibold text-foreground">
          Dimensiones útiles
        </h3>
        <p class="mt-1 text-xs text-foreground-muted">
          Si registra una dimensión debe completar las tres. Son medidas útiles, no dimensiones
          exteriores.
        </p>
      </div>
      <div class="grid gap-4 sm:grid-cols-3">
        <FormField
          id="capacity-group-length"
          type="number"
          label="Largo (m)"
          bind:value={draft.usable_length_m}
          error={errors.usable_length_m}
          min="0.000001"
          step="0.001"
          placeholder="No registrado"
        />
        <FormField
          id="capacity-group-width"
          type="number"
          label="Ancho (m)"
          bind:value={draft.usable_width_m}
          error={errors.usable_width_m}
          min="0.000001"
          step="0.001"
          placeholder="No registrado"
        />
        <FormField
          id="capacity-group-height"
          type="number"
          label="Alto (m)"
          bind:value={draft.usable_height_m}
          error={errors.usable_height_m}
          min="0.000001"
          step="0.001"
          placeholder="No registrado"
        />
      </div>
    </section>

    <section class="border-t border-border pt-5" aria-labelledby="capacity-group-control-title">
      <div class="mb-4">
        <h3 id="capacity-group-control-title" class="text-sm font-semibold text-foreground">
          Perfil y control
        </h3>
      </div>
      <div class="grid gap-4 sm:grid-cols-2">
        <FormField
          id="capacity-group-profile"
          label="Perfil de capacidad"
          bind:value={draft.capacity_profile}
          options={PROFILE_OPTIONS}
          error={errors.capacity_profile}
          required
        />
        <FormField
          id="capacity-group-enforcement"
          label="Control de capacidad"
          bind:value={draft.capacity_enforcement_mode}
          options={ENFORCEMENT_OPTIONS}
          error={errors.capacity_enforcement_mode}
          disabled={!draft.storage_eligible}
          required
        />
      </div>
      <label
        class="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-border bg-surface-muted/30 p-4"
      >
        <input
          type="checkbox"
          checked={draft.storage_eligible}
          onchange={updateStorageEligibility}
          class="mt-0.5 h-4 w-4 rounded border-border text-primary focus:ring-primary"
        />
        <span>
          <span class="block text-sm font-medium text-foreground"
            >Apto para almacenar mercancía</span
          >
          <span class="mt-0.5 block text-xs leading-5 text-foreground-muted">
            Indica que sus ubicaciones pueden recibir mercancía normal. La estructura en sí nunca es
            una dirección de inventario.
          </span>
        </span>
      </label>
    </section>

    <div class="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
      <Button variant="ghost" onclick={onclose} disabled={saving}>Cancelar</Button>
      <Button type="submit" disabled={saving}>
        {saving ? 'Guardando…' : editing ? 'Guardar cambios' : 'Crear estructura'}
      </Button>
    </div>
  </form>
</Modal>
