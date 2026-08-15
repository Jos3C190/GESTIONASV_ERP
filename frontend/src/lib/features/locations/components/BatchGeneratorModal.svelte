<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import { HttpError } from '$lib/api/client';
  import { batchCardinality, createIdempotencyKey } from '../schemas';
  import { previewGeneratedLocations, publishLocationBatch } from '../services';
  import {
    LOCATION_TYPE_OPTIONS,
    locationBatchRequiredPermissions,
    locationPermissionLabel,
    type LocationBatchAxis,
    type LocationBatchJob,
    type LocationCodeScheme
  } from '../types';
  import BatchJobReview from './BatchJobReview.svelte';

  interface Props {
    open: boolean;
    warehouseId: string;
    scheme?: LocationCodeScheme | null;
    hasPermission?: (permission: string) => boolean;
    onclose: () => void;
    onpublished: (job: LocationBatchJob) => void;
  }

  let {
    open,
    warehouseId,
    scheme = null,
    hasPermission = () => true,
    onclose,
    onpublished
  }: Props = $props();

  type RangeDraft = { start: string; end: string };
  let step = $state<1 | 2 | 3>(1);
  let ranges = $state<Record<string, RangeDraft>>({
    aisle: { start: '1', end: '1' },
    rack: { start: '1', end: '10' },
    level: { start: '1', end: '4' },
    position: { start: '1', end: '2' }
  });
  let area = $state('');
  let capacity = $state('1');
  let locationType = $state('standard');
  let job = $state<LocationBatchJob | null>(null);
  let loading = $state(false);
  let publishing = $state(false);
  let confirmed = $state(false);
  let error = $state<string | null>(null);
  let contextOpen = $state(false);

  const AXES = [
    { key: 'aisle', label: 'Pasillos', example: '1–4', placeholder: '01' },
    { key: 'rack', label: 'Racks', example: '1–10', placeholder: '01' },
    { key: 'level', label: 'Niveles', example: '1–4', placeholder: '01' },
    { key: 'position', label: 'Posiciones', example: '1–2', placeholder: '01' }
  ] as const;

  let axes = $derived(
    AXES.map((axis): LocationBatchAxis => ({
      key: axis.key,
      start: ranges[axis.key]?.start,
      end: ranges[axis.key]?.end,
      step: 1
    }))
  );
  let cardinality = $derived(batchCardinality(axes));
  let valid = $derived(
    cardinality > 0 &&
      cardinality <= 50_000 &&
      Number.isInteger(Number(capacity)) &&
      Number(capacity) > 0
  );
  let requiredPermissions = $derived(job ? locationBatchRequiredPermissions(job) : []);
  let missingPermissions = $derived(
    requiredPermissions.filter((permission) => !hasPermission(permission))
  );
  let canPublish = $derived(
    Boolean(
      job &&
        job.error_count === 0 &&
        job.conflict_count === 0 &&
        missingPermissions.length === 0 &&
        confirmed
    )
  );

  $effect(() => {
    if (open && !contextOpen) {
      step = 1;
      job = null;
      confirmed = false;
      error = null;
      contextOpen = true;
    }
    if (!open) contextOpen = false;
  });

  function setRange(key: string, field: keyof RangeDraft, value: string) {
    ranges = { ...ranges, [key]: { ...ranges[key]!, [field]: value } };
    job = null;
  }

  async function preview() {
    if (!valid) return;
    loading = true;
    error = null;
    try {
      job = await previewGeneratedLocations(warehouseId, {
        idempotency_key: createIdempotencyKey('generate'),
        scheme_version: scheme?.version,
        axes,
        defaults: {
          area: area.trim() || null,
          capacity: Number(capacity),
          location_type: locationType,
          lifecycle_status: 'active'
        }
      });
      confirmed = false;
      step = 2;
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo generar la vista previa.';
    } finally {
      loading = false;
    }
  }

  async function publish() {
    if (!job || !canPublish) return;
    publishing = true;
    error = null;
    try {
      job = await publishLocationBatch(job.id);
      step = 3;
      onpublished(job);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo publicar el lote.';
    } finally {
      publishing = false;
    }
  }
</script>

<Modal {open} size="lg" title="Generar ubicaciones por rangos" {onclose}>
  <div class="mb-6 flex items-center gap-2" aria-label={`Paso ${step} de 3`}>
    {#each [1, 2, 3] as number}
      <div class="flex flex-1 items-center gap-2">
        <span
          class="flex h-7 w-7 flex-none items-center justify-center rounded-full border text-xs font-semibold {number <=
          step
            ? 'border-primary bg-primary text-primary-foreground'
            : 'border-border bg-surface-muted text-foreground-muted'}"
        >
          {number}
        </span>
        {#if number < 3}<span class="h-px flex-1 {number < step ? 'bg-primary' : 'bg-border'}"
          ></span>{/if}
      </div>
    {/each}
  </div>

  {#if error}
    <div
      class="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {/if}

  {#if step === 1}
    <div class="space-y-5">
      <div>
        <h3 class="text-sm font-semibold text-foreground">1. Diseñe la matriz física</h3>
        <p class="mt-1 text-xs text-foreground-muted">
          Cada combinación de pasillo, rack, nivel y posición producirá una ubicación. Límite por
          lote: 50,000.
        </p>
        <p class="mt-1 text-xs text-foreground-subtle">
          El esquema inicial A/R/N/P usa valores numéricos (1, 2, 3…) y aplica el relleno, por
          ejemplo 01. Para pasillos A, B, C configure ese segmento con ancho 0 y prefijo vacío.
        </p>
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        {#each AXES as axis (axis.key)}
          <fieldset class="rounded-xl border border-border bg-surface-muted/30 p-4">
            <legend class="px-1 text-sm font-medium text-foreground">{axis.label}</legend>
            <div class="mt-2 grid grid-cols-2 gap-3">
              <FormField
                id={`batch-${axis.key}-start`}
                label="Desde"
                value={ranges[axis.key]?.start ?? ''}
                placeholder={axis.placeholder}
                oninput={(event) =>
                  setRange(axis.key, 'start', (event.currentTarget as HTMLInputElement).value)}
                required
              />
              <FormField
                id={`batch-${axis.key}-end`}
                label="Hasta"
                value={ranges[axis.key]?.end ?? ''}
                placeholder={axis.placeholder}
                oninput={(event) =>
                  setRange(axis.key, 'end', (event.currentTarget as HTMLInputElement).value)}
                required
              />
            </div>
            <p class="mt-2 text-xs text-foreground-subtle">Ejemplo: {axis.example}</p>
          </fieldset>
        {/each}
      </div>

      <div class="grid gap-4 border-t border-border pt-5 sm:grid-cols-3">
        <FormField
          id="batch-area"
          label="Área o zona"
          bind:value={area}
          placeholder="Ej. RESERVA"
        />
        <SmartSelect
          id="batch-location-type"
          label="Tipo"
          bind:value={locationType}
          options={LOCATION_TYPE_OPTIONS.map((item) => ({ ...item }))}
          required
        />
        <FormField
          id="batch-capacity"
          label="Capacidad por ubicación"
          type="number"
          min="1"
          step="1"
          bind:value={capacity}
          required
        />
      </div>

      <div class="rounded-xl border border-primary/20 bg-primary/5 p-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p class="text-xs text-foreground-muted">Cardinalidad calculada</p>
            <p
              class="mt-1 font-mono text-2xl font-semibold {cardinality > 50_000
                ? 'text-danger'
                : 'text-foreground'}"
            >
              {cardinality.toLocaleString('es-SV')} ubicaciones
            </p>
          </div>
          <div class="text-right text-xs text-foreground-muted">
            <p>{axes.map((axis) => `${axis.key}: ${axis.start}–${axis.end}`).join(' · ')}</p>
            <p class="mt-1">Códigos bajo esquema {scheme ? `v${scheme.version}` : 'activo'}</p>
          </div>
        </div>
        {#if cardinality > 50_000}<p class="mt-2 text-xs text-danger">
            Divida la operación en lotes de hasta 50,000 ubicaciones.
          </p>{/if}
      </div>
    </div>
  {:else if step === 2 && job}
    <div>
      <h3 class="text-sm font-semibold text-foreground">2. Revise el impacto antes de publicar</h3>
      <p class="mb-4 mt-1 text-xs text-foreground-muted">
        La vista previa no cambia datos. Conflictos y errores deben resolverse antes de publicar.
      </p>
      <BatchJobReview {job} />
      {#if missingPermissions.length > 0}
        <div
          class="mt-4 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
          role="alert"
        >
          <p class="font-medium">No puede publicar este impacto con sus permisos actuales.</p>
          <p class="mt-1 text-xs">
            Faltan: {missingPermissions.map(locationPermissionLabel).join(', ')}. Solicite estos permisos
            o vuelva a configurar un lote que no requiera esas operaciones.
          </p>
        </div>
      {/if}
      <label
        class="mt-4 flex items-start gap-3 rounded-xl border border-border bg-surface-muted/40 p-4 text-sm {missingPermissions.length >
        0
          ? 'cursor-not-allowed opacity-60'
          : 'cursor-pointer'}"
      >
        <input
          type="checkbox"
          bind:checked={confirmed}
          disabled={missingPermissions.length > 0}
          class="mt-0.5 h-4 w-4 rounded border-border accent-primary"
        />
        <span>
          <span class="font-medium text-foreground">Confirmo la publicación de este lote</span>
          <span class="mt-1 block text-xs text-foreground-muted">
            El sistema creará {job.create_count.toLocaleString('es-SV')} ubicaciones bajo el esquema validado.
          </span>
        </span>
      </label>
    </div>
  {:else if step === 3 && job}
    <div class="py-8 text-center">
      <div
        class="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-success/10 text-success"
      >
        <svg
          width="26"
          height="26"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          aria-hidden="true"><polyline points="20 6 9 17 4 12" /></svg
        >
      </div>
      <h3 class="mt-4 text-lg font-semibold text-foreground">Lote publicado</h3>
      <p class="mt-2 text-sm text-foreground-muted">
        Se procesaron {job.total_rows.toLocaleString('es-SV')} filas. La tabla principal ya puede actualizarse.
      </p>
      <p class="mt-2 font-mono text-xs text-foreground-subtle">Trabajo {job.id}</p>
    </div>
  {/if}

  <div
    class="mt-6 flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-between"
  >
    <Button variant="ghost" onclick={onclose}>{step === 3 ? 'Cerrar' : 'Cancelar'}</Button>
    <div class="flex flex-col-reverse gap-2 sm:flex-row">
      {#if step === 2}<Button variant="secondary" onclick={() => (step = 1)} disabled={publishing}
          >Volver a configurar</Button
        >{/if}
      {#if step === 1}<Button onclick={() => void preview()} disabled={!valid || loading}
          >{loading ? 'Validando…' : 'Generar vista previa'}</Button
        >{/if}
      {#if step === 2}<Button onclick={() => void publish()} disabled={!canPublish || publishing}
          >{publishing ? 'Publicando…' : 'Publicar lote'}</Button
        >{/if}
    </div>
  </div>
</Modal>
