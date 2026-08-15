<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import { HttpError } from '$lib/api/client';
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
    warehouseId: string;
    location?: LocationOut | null;
    canRecode?: boolean;
    canCommission?: boolean;
    canActivate?: boolean;
    canDeactivate?: boolean;
    onclose: () => void;
    onsaved: (location: LocationOut, createAnother: boolean) => void;
  }

  let {
    open,
    warehouseId,
    location = null,
    canRecode = false,
    canCommission = false,
    canActivate = false,
    canDeactivate = false,
    onclose,
    onsaved
  }: Props = $props();

  const emptyDraft = (): LocationDraft => ({
    area: '',
    aisle: '',
    rack: '',
    level: '',
    position: '',
    capacity: '1',
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

  function canSelectLifecycle(target: string): boolean {
    if (!location || target === location.lifecycle_status) return true;
    if (target === 'retired') return canDeactivate;
    if (location.lifecycle_status === 'retired' && target === 'active') return canActivate;
    return canCommission;
  }

  function draftFromLocation(item: LocationOut): LocationDraft {
    return {
      area: item.area ?? '',
      aisle: item.aisle,
      rack: item.rack,
      level: item.level,
      position: item.position,
      capacity: String(item.capacity),
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
          area: previous.area,
          aisle: previous.aisle,
          rack: previous.rack,
          location_type: previous.location_type,
          capacity: previous.capacity
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

<Modal {open} size="lg" title={editing ? 'Editar ubicación' : 'Nueva ubicación'} {onclose}>
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
        <FormField
          id="location-capacity"
          label="Capacidad operativa"
          type="number"
          min="1"
          step="1"
          bind:value={draft.capacity}
          error={errors.capacity}
          required
        />
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
