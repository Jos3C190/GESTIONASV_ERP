<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import { HttpError } from '$lib/api/client';
  import { getWarehouse } from '$lib/services/warehouses';
  import CapacityScopePath from '../../inventory/components/CapacityScopePath.svelte';
  import { inventoryApi } from '../../inventory/services';
  import type { CapacitySummary } from '../../inventory/types';
  import { listCapacityGroups } from '../../warehouses/capacity-groups.service';
  import { capacityGroupPath } from '../../warehouses/capacity-groups.logic';
  import type { WarehouseCapacityGroup } from '../../warehouses/capacity-groups.types';
  import type { Warehouse } from '../../warehouses/types';
  import { createLocation, previewLocationCode, updateLocation } from '../services';
  import { validateLocationDraft, type LocationFieldErrors } from '../schemas';
  import {
    LOCATION_STATUS_OPTIONS,
    LOCATION_TYPE_OPTIONS,
    type LocationCodePreview,
    type LocationDraft,
    type LocationOut
  } from '../types';

  interface Props {
    open: boolean;
    inline?: boolean;
    warehouseId: string;
    location?: LocationOut | null;
    canRecode?: boolean;
    canCommission?: boolean;
    canActivate?: boolean;
    canDeactivate?: boolean;
    canViewCapacity?: boolean;
    onclose: () => void;
    onsaved: (location: LocationOut, createAnother: boolean) => void;
  }

  let {
    open,
    inline = false,
    warehouseId,
    location = null,
    canRecode = false,
    canCommission = false,
    canActivate = false,
    canDeactivate = false,
    canViewCapacity = false,
    onclose,
    onsaved
  }: Props = $props();

  const CAPACITY_PROFILE_OPTIONS = [
    { value: 'general_mixed', label: 'Mixto general' },
    { value: 'rack', label: 'Rack' },
    { value: 'bulk_floor', label: 'Piso / granel' },
    { value: 'cold', label: 'Cámara fría' },
    { value: 'oversize_manual', label: 'Sobredimensionado manual' },
    { value: 'transit', label: 'Tránsito' }
  ];
  const CAPACITY_ENFORCEMENT_OPTIONS = [
    { value: 'disabled', label: 'Deshabilitado' },
    { value: 'observe', label: 'Solo observar' },
    { value: 'enforce', label: 'Bloquear excesos' }
  ];

  const emptyDraft = (): LocationDraft => ({
    capacity_group_id: '',
    area: '',
    aisle: '',
    rack: '',
    level: '',
    position: '',
    certified_max_weight_kg: '',
    operational_max_weight_kg: '',
    certified_usable_volume_m3: '',
    operational_usable_volume_m3: '',
    capacity_profile: 'general_mixed',
    capacity_enforcement_mode: 'observe',
    storage_eligible: true,
    usable_length_m: '',
    usable_width_m: '',
    usable_height_m: '',
    notes: '',
    location_type: 'standard',
    lifecycle_status: 'active',
    pick_sequence: '',
    putaway_sequence: '',
    external_id: '',
    barcode: '',
    verification_code: ''
  });

  let draft = $state<LocationDraft>(emptyDraft());
  let errors = $state<LocationFieldErrors>({});
  let preview = $state<LocationCodePreview | null>(null);
  let previewLoading = $state(false);
  let previewError = $state<string | null>(null);
  let saving = $state(false);
  let saveError = $state<string | null>(null);
  let capacityGroups = $state<WarehouseCapacityGroup[]>([]);
  let warehouse = $state<Warehouse | null>(null);
  let capacityGroupsLoading = $state(false);
  let capacityGroupsError = $state<string | null>(null);
  let capacitySummary = $state<CapacitySummary | null>(null);
  let capacitySummaryLoading = $state(false);
  let capacitySummaryError = $state<string | null>(null);
  let contextKey = $state('');

  const PHYSICAL_ROUTE_FIELDS = ['area', 'aisle', 'rack', 'level', 'position'] as const;
  const normalizeRouteComponent = (value: string | null | undefined) =>
    (value ?? '').normalize('NFKC').trim().toLocaleUpperCase('es');

  let editing = $derived(Boolean(location));
  let physicalRouteLocked = $derived(Boolean(location && !canRecode));
  let physicalRouteChanged = $derived(
    Boolean(
      location &&
      PHYSICAL_ROUTE_FIELDS.some(
        (field) =>
          normalizeRouteComponent(draft[field]) !== normalizeRouteComponent(location[field])
      )
    )
  );
  let recoding = $derived(
    Boolean(location && physicalRouteChanged && preview && preview.code !== location.code)
  );
  let previewConflicts = $derived(
    Boolean(
      preview &&
      (preview.code_exists || preview.coordinates_exist) &&
      (!location || physicalRouteChanged)
    )
  );
  let codeReady = $derived(
    !location || physicalRouteChanged
      ? Boolean(preview) && !previewLoading && !previewConflicts
      : true
  );
  let lifecycleOptions = $derived(
    LOCATION_STATUS_OPTIONS.map((option) => ({
      ...option,
      disabled: !canSelectLifecycle(option.value)
    }))
  );
  let lifecycleLocked = $derived(
    Boolean(
      location &&
      !lifecycleOptions.some(
        (option) => option.value !== location.lifecycle_status && !option.disabled
      )
    )
  );
  let capacityGroupOptions = $derived([
    {
      value: '',
      label: 'Sin estructura compartida',
      description: 'Se aplican los límites de la ubicación y directamente los del almacén'
    },
    ...capacityGroups
      .filter((group) => group.isActive || group.id === draft.capacity_group_id)
      .map((group) => ({
        value: group.id,
        label: `${capacityGroupPath(capacityGroups, group.id)} · ${group.name}`,
        description: group.isActive
          ? `Límite compartido · ${group.groupType.replaceAll('_', ' ')}`
          : 'Estructura inactiva asignada actualmente',
        disabled: !group.isActive && group.id !== draft.capacity_group_id
      }))
  ]);
  let selectedCapacityGroup = $derived(
    capacityGroups.find((group) => group.id === draft.capacity_group_id) ?? null
  );

  function validateSelectedCapacityGroup(): LocationFieldErrors {
    const parent = selectedCapacityGroup ?? warehouse;
    if (!parent) return {};
    const parentCode = parent.code;
    const comparisons: Array<{
      field: keyof LocationFieldErrors;
      value: string | number;
      parentValue: number | null;
      label: string;
    }> = [
      {
        field: 'certified_max_weight_kg',
        value: draft.certified_max_weight_kg,
        parentValue: parent.certifiedMaxWeightKg,
        label: 'peso certificado'
      },
      {
        field: 'operational_max_weight_kg',
        value: draft.operational_max_weight_kg,
        parentValue: parent.operationalMaxWeightKg,
        label: 'peso operativo'
      },
      {
        field: 'certified_usable_volume_m3',
        value: draft.certified_usable_volume_m3,
        parentValue: parent.certifiedUsableVolumeM3,
        label: 'volumen certificado'
      },
      {
        field: 'operational_usable_volume_m3',
        value: draft.operational_usable_volume_m3,
        parentValue: parent.operationalUsableVolumeM3,
        label: 'volumen operativo'
      }
    ];
    const next: LocationFieldErrors = {};
    for (const comparison of comparisons) {
      const rawValue = String(comparison.value).trim();
      const value = rawValue ? Number(rawValue) : null;
      if (value != null && comparison.parentValue != null && value > comparison.parentValue) {
        next[comparison.field] = `No puede superar el ${comparison.label} de ${parentCode}.`;
      }
    }
    return next;
  }

  function canSelectLifecycle(target: string): boolean {
    if (!location || target === location.lifecycle_status) return true;
    if (target === 'retired') return canDeactivate;
    if (location.lifecycle_status === 'retired' && target === 'active') return canActivate;
    return canCommission;
  }

  function draftFromLocation(item: LocationOut): LocationDraft {
    return {
      capacity_group_id: item.capacity_group_id ?? '',
      area: item.area ?? '',
      aisle: item.aisle,
      rack: item.rack,
      level: item.level,
      position: item.position,
      certified_max_weight_kg:
        item.certified_max_weight_kg == null ? '' : String(item.certified_max_weight_kg),
      operational_max_weight_kg:
        item.operational_max_weight_kg == null ? '' : String(item.operational_max_weight_kg),
      certified_usable_volume_m3:
        item.certified_usable_volume_m3 == null ? '' : String(item.certified_usable_volume_m3),
      operational_usable_volume_m3:
        item.operational_usable_volume_m3 == null ? '' : String(item.operational_usable_volume_m3),
      capacity_profile: item.capacity_profile,
      capacity_enforcement_mode: item.capacity_enforcement_mode,
      storage_eligible: item.storage_eligible,
      usable_length_m: item.usable_length_m == null ? '' : String(item.usable_length_m),
      usable_width_m: item.usable_width_m == null ? '' : String(item.usable_width_m),
      usable_height_m: item.usable_height_m == null ? '' : String(item.usable_height_m),
      notes: item.notes ?? '',
      location_type: item.location_type || 'standard',
      lifecycle_status: item.lifecycle_status || 'active',
      pick_sequence: item.pick_sequence == null ? '' : String(item.pick_sequence),
      putaway_sequence: item.putaway_sequence == null ? '' : String(item.putaway_sequence),
      external_id: item.external_id ?? '',
      barcode: item.barcode ?? '',
      verification_code: item.verification_code ?? ''
    };
  }

  function reset(keepContext = false) {
    const previous = draft;
    draft = keepContext
      ? {
          ...emptyDraft(),
          capacity_group_id: previous.capacity_group_id,
          area: previous.area,
          aisle: previous.aisle,
          rack: previous.rack,
          location_type: previous.location_type,
          certified_max_weight_kg: previous.certified_max_weight_kg,
          operational_max_weight_kg: previous.operational_max_weight_kg,
          certified_usable_volume_m3: previous.certified_usable_volume_m3,
          operational_usable_volume_m3: previous.operational_usable_volume_m3,
          capacity_profile: previous.capacity_profile,
          capacity_enforcement_mode: previous.capacity_enforcement_mode,
          storage_eligible: previous.storage_eligible,
          usable_length_m: previous.usable_length_m,
          usable_width_m: previous.usable_width_m,
          usable_height_m: previous.usable_height_m
        }
      : location
        ? draftFromLocation(location)
        : emptyDraft();
    errors = {};
    preview = null;
    previewError = null;
    saveError = null;
  }

  $effect(() => {
    const nextKey = open ? `${location?.id ?? 'new'}:${warehouseId}` : '';
    if (open && nextKey !== contextKey) {
      contextKey = nextKey;
      reset(false);
    }
    if (!open) contextKey = '';
  });

  $effect(() => {
    const locationId = open && canViewCapacity ? location?.id : null;
    if (!locationId) {
      capacitySummary = null;
      capacitySummaryLoading = false;
      capacitySummaryError = null;
      return;
    }
    const controller = new AbortController();
    capacitySummaryLoading = true;
    capacitySummaryError = null;
    void inventoryApi
      .getCapacitySummary(warehouseId, locationId)
      .then((summary) => {
        if (!controller.signal.aborted) capacitySummary = summary;
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        capacitySummary = null;
        capacitySummaryError =
          error instanceof HttpError
            ? error.message
            : 'No se pudo cargar la ruta de capacidad de esta ubicación.';
      })
      .finally(() => {
        if (!controller.signal.aborted) capacitySummaryLoading = false;
      });
    return () => controller.abort();
  });

  $effect(() => {
    if (!open || !warehouseId) {
      capacityGroups = [];
      warehouse = null;
      capacityGroupsLoading = false;
      capacityGroupsError = null;
      return;
    }
    const controller = new AbortController();
    capacityGroupsLoading = true;
    capacityGroupsError = null;
    void Promise.all([
      listCapacityGroups(warehouseId, controller.signal),
      getWarehouse(warehouseId)
    ])
      .then(([groups, loadedWarehouse]) => {
        if (!controller.signal.aborted) {
          capacityGroups = groups;
          warehouse = loadedWarehouse;
        }
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        capacityGroups = [];
        warehouse = null;
        capacityGroupsError =
          error instanceof HttpError
            ? error.message
            : 'No se pudieron cargar las estructuras compartidas.';
      })
      .finally(() => {
        if (!controller.signal.aborted) capacityGroupsLoading = false;
      });
    return () => controller.abort();
  });

  $effect(() => {
    const values = [draft.aisle, draft.rack, draft.level, draft.position].map((value) =>
      value.trim()
    );
    const area = draft.area.trim();
    if (location && !physicalRouteChanged) {
      preview = null;
      previewError = null;
      previewLoading = false;
      return;
    }
    if (!open || !warehouseId || values.some((value) => !value)) {
      preview = null;
      previewError = null;
      previewLoading = false;
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      previewLoading = true;
      previewError = null;
      try {
        preview = await previewLocationCode(
          warehouseId,
          {
            area: area || null,
            aisle: values[0]!,
            rack: values[1]!,
            level: values[2]!,
            position: values[3]!,
            ...(location ? { exclude_location_id: location.id } : {})
          },
          controller.signal
        );
      } catch (error) {
        if (controller.signal.aborted) return;
        preview = null;
        previewError =
          error instanceof HttpError
            ? error.message
            : 'No se pudo obtener el código. Revise la ruta e intente nuevamente.';
      } finally {
        if (!controller.signal.aborted) previewLoading = false;
      }
    }, 350);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  });

  async function save(createAnother: boolean) {
    const result = validateLocationDraft(draft);
    if (!result.success) {
      errors = result.errors;
      return;
    }
    const hierarchyErrors = validateSelectedCapacityGroup();
    if (Object.keys(hierarchyErrors).length > 0) {
      errors = hierarchyErrors;
      return;
    }
    errors = {};
    saveError = null;
    if (location && physicalRouteChanged && !canRecode) {
      saveError = 'No tiene permiso para cambiar la ruta física y recodificar esta ubicación.';
      return;
    }
    if (location && !canSelectLifecycle(result.data.lifecycle_status)) {
      saveError = 'No tiene permiso para realizar este cambio de estado operativo.';
      return;
    }
    const needsCodePreview = !location || physicalRouteChanged;
    if (needsCodePreview && (!preview || previewLoading)) {
      saveError = 'Espere a que el sistema confirme el código autogenerado.';
      return;
    }
    if (previewConflicts) {
      saveError = 'La ruta o el código ya pertenece a otra ubicación.';
      return;
    }
    saving = true;
    try {
      const payload =
        needsCodePreview && preview
          ? { ...result.data, scheme_version: preview.scheme_version }
          : result.data;
      const saved = location
        ? await updateLocation(warehouseId, location.id, {
            ...payload,
            expected_updated_at: location.updated_at
          })
        : await createLocation(warehouseId, payload);
      onsaved(saved, createAnother && !location);
      if (createAnother && !location) reset(true);
      else onclose();
    } catch (error) {
      saveError = error instanceof HttpError ? error.message : 'No se pudo guardar la ubicación.';
    } finally {
      saving = false;
    }
  }
</script>

<Modal {open} {inline} size="lg" title={editing ? 'Editar ubicación' : 'Nueva ubicación'} {onclose}>
  <form
    class="space-y-6"
    onsubmit={(event) => {
      event.preventDefault();
      void save(false);
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

    <section aria-labelledby="location-route-title">
      <div class="mb-4">
        <h3 id="location-route-title" class="text-sm font-semibold text-foreground">Ruta física</h3>
        <p class="mt-1 text-xs text-foreground-muted">
          Describa el recorrido que un bodeguero seguiría. El servidor normaliza la ruta y genera el
          código.
        </p>
        {#if physicalRouteLocked}
          <p class="mt-2 text-xs text-foreground-muted">
            La ruta y el código están protegidos. Puede actualizar capacidad, secuencias,
            referencias, escaneo y notas con su permiso de edición actual.
          </p>
        {/if}
      </div>
      <div class="grid gap-4 sm:grid-cols-2">
        <FormField
          id="location-area"
          label="Área o zona"
          bind:value={draft.area}
          error={errors.area}
          placeholder="Ej. PICKING"
          disabled={physicalRouteLocked}
        />
        <SmartSelect
          id="location-type"
          label="Tipo de ubicación"
          bind:value={draft.location_type}
          options={LOCATION_TYPE_OPTIONS.map((item) => ({ ...item }))}
          error={errors.location_type}
          required
        />
        <FormField
          id="location-aisle"
          label="Pasillo"
          bind:value={draft.aisle}
          error={errors.aisle}
          placeholder="Ej. A"
          disabled={physicalRouteLocked}
          required
        />
        <FormField
          id="location-rack"
          label="Rack"
          bind:value={draft.rack}
          error={errors.rack}
          placeholder="Ej. 03"
          disabled={physicalRouteLocked}
          required
        />
        <FormField
          id="location-level"
          label="Nivel"
          bind:value={draft.level}
          error={errors.level}
          placeholder="Ej. 02"
          disabled={physicalRouteLocked}
          required
        />
        <FormField
          id="location-position"
          label="Posición"
          bind:value={draft.position}
          error={errors.position}
          placeholder="Ej. 04"
          disabled={physicalRouteLocked}
          required
        />
      </div>

      <div class="mt-4 rounded-xl border border-border bg-surface-muted/50 p-4" aria-live="polite">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">
              {location && !physicalRouteChanged ? 'Código actual' : 'Código autogenerado'}
            </p>
            {#if location && !physicalRouteChanged}
              <p class="mt-1 font-mono text-lg font-semibold text-foreground">{location.code}</p>
              <p class="mt-1 text-xs text-foreground-muted">
                Código estable: se conserva mientras no cambie la ruta física.
              </p>
            {:else if previewLoading}
              <div class="mt-2 h-7 w-44 rounded-md skeleton"></div>
            {:else if preview}
              <p class="mt-1 font-mono text-lg font-semibold text-foreground">{preview.code}</p>
              <p class="mt-1 text-xs text-foreground-muted">Esquema v{preview.scheme_version}</p>
            {:else}
              <p class="mt-1 text-sm text-foreground-muted">
                Complete pasillo, rack, nivel y posición.
              </p>
            {/if}
          </div>
          <span
            class="rounded-full border border-border bg-surface px-2.5 py-1 text-xs text-foreground-muted"
          >
            Solo lectura
          </span>
        </div>
        {#if previewError}<p class="mt-2 text-xs text-danger">{previewError}</p>{/if}
        {#if previewConflicts}
          <p class="mt-2 text-xs font-medium text-danger">La ruta o el código ya existe.</p>
        {/if}
        {#if recoding}
          <div
            class="mt-3 rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-warning"
          >
            Al guardar, <span class="font-mono">{location?.code}</span> cambiará a
            <span class="font-mono">{preview?.code}</span>. El servidor conservará el código
            anterior como alias auditable.
          </div>
        {/if}
      </div>
    </section>

    <section class="border-t border-border pt-5" aria-labelledby="location-operation-title">
      <h3 id="location-operation-title" class="mb-4 text-sm font-semibold text-foreground">
        Operación
      </h3>
      {#if lifecycleLocked}
        <p class="mb-4 text-xs text-foreground-muted">
          El estado operativo está protegido; los demás datos de operación continúan editables.
        </p>
      {/if}
      <div class="grid gap-4 sm:grid-cols-2">
        <div class="sm:col-span-2">
          <SmartSelect
            id="location-capacity-group"
            label="Estructura con límite compartido"
            bind:value={draft.capacity_group_id}
            options={capacityGroupOptions}
            error={errors.capacity_group_id}
            disabled={capacityGroupsLoading}
            placeholder={capacityGroupsLoading
              ? 'Cargando estructuras…'
              : 'Seleccione una estructura'}
          />
          <p class="mt-1 text-xs text-foreground-muted">
            La ubicación guarda el inventario. Esta estructura solo agrega una restricción
            compartida de rack, nivel, cámara o zona de piso.
          </p>
          {#if selectedCapacityGroup}
            <div class="mt-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs">
              <p class="font-semibold text-foreground">
                Ruta: {capacityGroupPath(capacityGroups, selectedCapacityGroup.id)} → Almacén
              </p>
              <p class="mt-1 text-foreground-muted">
                Máximos operativos compartidos:
                {selectedCapacityGroup.operationalMaxWeightKg == null
                  ? 'peso no configurado'
                  : `${selectedCapacityGroup.operationalMaxWeightKg.toLocaleString('es-SV')} kg`}
                ·
                {selectedCapacityGroup.operationalUsableVolumeM3 == null
                  ? 'volumen no configurado'
                  : `${selectedCapacityGroup.operationalUsableVolumeM3.toLocaleString('es-SV')} m³`}
              </p>
            </div>
          {:else if warehouse}
            <div class="mt-2 rounded-lg border border-border bg-surface-muted/40 px-3 py-2 text-xs">
              <p class="font-semibold text-foreground">Ruta: Ubicación → {warehouse.code}</p>
              <p class="mt-1 text-foreground-muted">
                Límites operativos del almacén:
                {warehouse.operationalMaxWeightKg == null
                  ? 'peso no configurado'
                  : `${warehouse.operationalMaxWeightKg.toLocaleString('es-SV')} kg`}
                ·
                {warehouse.operationalUsableVolumeM3 == null
                  ? 'volumen no configurado'
                  : `${warehouse.operationalUsableVolumeM3.toLocaleString('es-SV')} m³`}
              </p>
            </div>
          {/if}
          {#if capacityGroupsError}
            <p class="mt-1 text-xs text-danger" role="alert">{capacityGroupsError}</p>
          {/if}
        </div>
        <SmartSelect
          id="location-capacity-profile"
          label="Perfil físico"
          bind:value={draft.capacity_profile}
          options={CAPACITY_PROFILE_OPTIONS}
          error={errors.capacity_profile}
        />
        <SmartSelect
          id="location-capacity-enforcement"
          label="Control de límites"
          bind:value={draft.capacity_enforcement_mode}
          options={CAPACITY_ENFORCEMENT_OPTIONS}
          error={errors.capacity_enforcement_mode}
        />
        <FormField
          id="location-certified-weight"
          label="Peso certificado (kg)"
          type="number"
          min="0.001"
          step="0.001"
          bind:value={draft.certified_max_weight_kg}
          error={errors.certified_max_weight_kg}
          placeholder="Opcional"
        />
        <FormField
          id="location-operational-weight"
          label="Peso operativo (kg)"
          type="number"
          min="0.001"
          step="0.001"
          bind:value={draft.operational_max_weight_kg}
          error={errors.operational_max_weight_kg}
          placeholder="Opcional"
        />
        <FormField
          id="location-certified-volume"
          label="Volumen útil certificado (m³)"
          type="number"
          min="0.001"
          step="0.001"
          bind:value={draft.certified_usable_volume_m3}
          error={errors.certified_usable_volume_m3}
          placeholder="Opcional"
        />
        <FormField
          id="location-operational-volume"
          label="Volumen útil operativo (m³)"
          type="number"
          min="0.001"
          step="0.001"
          bind:value={draft.operational_usable_volume_m3}
          error={errors.operational_usable_volume_m3}
          placeholder="Opcional"
        />
        <div class="sm:col-span-2 grid gap-4 sm:grid-cols-3">
          <FormField
            id="location-usable-length"
            label="Largo útil (m)"
            type="number"
            min="0.001"
            step="0.001"
            bind:value={draft.usable_length_m}
            error={errors.usable_length_m}
            placeholder="Opcional"
          />
          <FormField
            id="location-usable-width"
            label="Ancho útil (m)"
            type="number"
            min="0.001"
            step="0.001"
            bind:value={draft.usable_width_m}
            error={errors.usable_width_m}
            placeholder="Opcional"
          />
          <FormField
            id="location-usable-height"
            label="Altura útil (m)"
            type="number"
            min="0.001"
            step="0.001"
            bind:value={draft.usable_height_m}
            error={errors.usable_height_m}
            placeholder="Opcional"
          />
        </div>
        <label
          class="sm:col-span-2 flex items-start gap-3 rounded-lg border border-border bg-surface-muted/30 p-3 text-sm text-foreground"
        >
          <input
            type="checkbox"
            bind:checked={draft.storage_eligible}
            class="mt-0.5 h-4 w-4 rounded border-border text-primary focus:ring-primary"
          />
          <span>
            <span class="block font-medium">Elegible para almacenamiento normal</span>
            <span class="mt-0.5 block text-xs text-foreground-muted">
              Desactívelo para recepción, calidad, despacho o ubicaciones virtuales.
            </span>
          </span>
        </label>
        <SmartSelect
          id="location-status"
          label="Estado operativo"
          bind:value={draft.lifecycle_status}
          options={lifecycleOptions}
          error={errors.lifecycle_status}
          disabled={lifecycleLocked}
          required
        />
        <FormField
          id="location-pick-sequence"
          label="Secuencia de picking"
          type="number"
          min="0"
          step="1"
          bind:value={draft.pick_sequence}
          error={errors.pick_sequence}
          placeholder="Opcional"
        />
        <FormField
          id="location-putaway-sequence"
          label="Secuencia de acomodo"
          type="number"
          min="0"
          step="1"
          bind:value={draft.putaway_sequence}
          error={errors.putaway_sequence}
          placeholder="Opcional"
        />
        <div class="sm:col-span-2">
          <FormField
            id="location-external-id"
            label="Referencia externa"
            bind:value={draft.external_id}
            error={errors.external_id}
            placeholder="Opcional: código del sistema anterior"
          />
        </div>
        <div class="sm:col-span-2">
          <label for="location-notes" class="mb-1 block text-sm font-medium text-foreground"
            >Notas</label
          >
          <textarea
            id="location-notes"
            bind:value={draft.notes}
            rows="4"
            maxlength="4000"
            placeholder="Añada instrucciones operativas o contexto para el bodeguero"
            class="min-h-24 w-full resize-y rounded-lg border border-border bg-surface px-3 py-2.5 text-sm leading-5 text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            aria-invalid={errors.notes ? 'true' : undefined}
            aria-describedby={errors.notes ? 'location-notes-error' : undefined}
          ></textarea>
          {#if errors.notes}
            <p id="location-notes-error" class="mt-1 text-xs text-danger">{errors.notes}</p>
          {/if}
        </div>
      </div>
    </section>

    {#if editing && canViewCapacity}
      <section class="border-t border-border pt-5" aria-labelledby="location-capacity-path-title">
        <div class="mb-4">
          <h3 id="location-capacity-path-title" class="text-sm font-semibold text-foreground">
            Ruta y ocupación de capacidad
          </h3>
          <p class="mt-1 text-xs leading-5 text-foreground-muted">
            La mercancía ocupa esta ubicación y también consume los límites compartidos de cada
            estructura superior y del almacén.
          </p>
        </div>
        <CapacityScopePath
          summary={capacitySummary}
          loading={capacitySummaryLoading}
          error={capacitySummaryError}
        />
      </section>
    {/if}

    <section class="border-t border-border pt-5" aria-labelledby="location-scanning-title">
      <h3 id="location-scanning-title" class="mb-4 text-sm font-semibold text-foreground">
        Datos de escaneo
      </h3>
      <div class="grid gap-4 sm:grid-cols-2">
        <FormField
          id="location-barcode"
          label="Código de barras"
          bind:value={draft.barcode}
          error={errors.barcode}
          maxlength={120}
          placeholder="Opcional: EAN, UPC o identificador interno"
        />
        <FormField
          id="location-verification-code"
          label="Código de verificación"
          bind:value={draft.verification_code}
          error={errors.verification_code}
          maxlength={120}
          placeholder="Opcional: dígito o código de control"
        />
      </div>
    </section>

    <div class="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
      <Button variant="ghost" onclick={onclose} disabled={saving}>Cancelar</Button>
      {#if !editing}
        <Button variant="secondary" onclick={() => void save(true)} disabled={saving || !codeReady}>
          Guardar y crear otra
        </Button>
      {/if}
      <Button type="submit" disabled={saving || !codeReady}>
        {saving ? 'Guardando…' : editing ? 'Guardar cambios' : 'Crear ubicación'}
      </Button>
    </div>
  </form>
</Modal>
