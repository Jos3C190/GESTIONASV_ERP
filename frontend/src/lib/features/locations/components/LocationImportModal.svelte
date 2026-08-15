<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { HttpError } from '$lib/api/client';
  import { createIdempotencyKey } from '../schemas';
  import { previewLocationImport, publishLocationBatch } from '../services';
  import {
    locationBatchRequiredPermissions,
    locationPermissionLabel,
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
  let step = $state<1 | 2 | 3>(1);
  let file = $state<File | null>(null);
  let job = $state<LocationBatchJob | null>(null);
  let loading = $state(false);
  let publishing = $state(false);
  let confirmed = $state(false);
  let error = $state<string | null>(null);
  let dragActive = $state(false);
  let contextOpen = $state(false);

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
      file = null;
      job = null;
      confirmed = false;
      error = null;
      contextOpen = true;
    }
    if (!open) contextOpen = false;
  });

  function accept(candidate: File | null) {
    if (!candidate) return;
    const extension = candidate.name.split('.').pop()?.toLocaleLowerCase('es');
    if (!extension || !['csv', 'xlsx'].includes(extension)) {
      error = 'Seleccione un archivo CSV o XLSX.';
      file = null;
      return;
    }
    if (candidate.size > 20 * 1024 * 1024) {
      error = 'El archivo supera el límite de 20 MB.';
      file = null;
      return;
    }
    error = null;
    file = candidate;
    job = null;
  }

  async function preview() {
    if (!file) return;
    loading = true;
    error = null;
    try {
      job = await previewLocationImport(warehouseId, {
        file,
        idempotency_key: createIdempotencyKey('import'),
        scheme_version: scheme?.version
      });
      confirmed = false;
      step = 2;
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo analizar el archivo.';
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
      error = cause instanceof HttpError ? cause.message : 'No se pudo publicar la importación.';
    } finally {
      publishing = false;
    }
  }
</script>

<Modal {open} size="lg" title="Importar ubicaciones" {onclose}>
  <div class="mb-6 flex items-center gap-2" aria-label={`Paso ${step} de 3`}>
    {#each [1, 2, 3] as number}
      <div class="flex flex-1 items-center gap-2">
        <span
          class="flex h-7 w-7 flex-none items-center justify-center rounded-full border text-xs font-semibold {number <=
          step
            ? 'border-primary bg-primary text-primary-foreground'
            : 'border-border bg-surface-muted text-foreground-muted'}">{number}</span
        >
        {#if number < 3}<span class="h-px flex-1 {number < step ? 'bg-primary' : 'bg-border'}"
          ></span>{/if}
      </div>
    {/each}
  </div>

  {#if error}<div
      class="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>{/if}

  {#if step === 1}
    <div>
      <h3 class="text-sm font-semibold text-foreground">
        1. Cargue el inventario maestro existente
      </h3>
      <p class="mt-1 text-xs text-foreground-muted">
        Formatos admitidos: CSV UTF-8 y XLSX, hasta 20 MB. El servidor valida cada fila sin
        modificar datos.
      </p>
      <label
        class="mt-5 flex min-h-52 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors {dragActive
          ? 'border-primary bg-primary/5'
          : 'border-border bg-surface-muted/30 hover:border-border-strong hover:bg-surface-muted/60'}"
        ondragover={(event) => {
          event.preventDefault();
          dragActive = true;
        }}
        ondragleave={() => (dragActive = false)}
        ondrop={(event) => {
          event.preventDefault();
          dragActive = false;
          accept(event.dataTransfer?.files[0] ?? null);
        }}
      >
        <input
          class="sr-only"
          type="file"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onchange={(event) => accept(event.currentTarget.files?.[0] ?? null)}
        />
        <div
          class="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-surface text-foreground-muted shadow-soft"
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
            ><path d="M12 3v12m0-12 4 4m-4-4L8 7" /><path
              d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"
            /></svg
          >
        </div>
        {#if file}
          <p class="mt-4 font-medium text-foreground">{file.name}</p>
          <p class="mt-1 text-xs text-foreground-muted">
            {(file.size / 1024).toLocaleString('es-SV', { maximumFractionDigits: 1 })} KB · Listo para
            validar
          </p>
        {:else}
          <p class="mt-4 font-medium text-foreground">
            Arrastre el archivo o haga clic para seleccionarlo
          </p>
          <p class="mt-1 text-xs text-foreground-muted">
            El código no se importa: se obtiene de la ruta bajo el esquema {scheme
              ? `v${scheme.version}`
              : 'activo'}.
          </p>
        {/if}
      </label>
      <div
        class="mt-4 rounded-xl border border-border bg-surface-muted/40 p-4 text-xs text-foreground-muted"
      >
        <p class="font-medium text-foreground">Columnas admitidas</p>
        <div class="mt-2 space-y-2">
          <p>
            <span class="font-medium text-foreground">Obligatorias:</span>
            <span class="font-mono">aisle, rack, level, position</span>
          </p>
          <p>
            <span class="font-medium text-foreground">Opcionales:</span>
            <span class="font-mono"
              >area, capacity, location_type, lifecycle_status, barcode, verification_code,
              pick_sequence, putaway_sequence, external_id, notes</span
            >
          </p>
        </div>
        <div class="mt-3 border-t border-border pt-3">
          <p>
            Al actualizar, una columna omitida del archivo conserva el valor existente. Una celda
            vacía limpia los campos anulables: <span class="font-mono"
              >area, barcode, verification_code, pick_sequence, putaway_sequence, external_id, notes</span
            >.
          </p>
          <p class="mt-2">
            Si incluye <span class="font-mono">capacity, location_type</span> o
            <span class="font-mono">lifecycle_status</span>, cada fila debe contener un valor
            válido. El código siempre se autogenera y nunca se toma del archivo.
          </p>
        </div>
      </div>
    </div>
  {:else if step === 2 && job}
    <div>
      <h3 class="text-sm font-semibold text-foreground">2. Revise filas, cambios y conflictos</h3>
      <p class="mb-4 mt-1 text-xs text-foreground-muted">
        Nada se publicará mientras existan errores o conflictos.
      </p>
      <BatchJobReview {job} />
      {#if missingPermissions.length > 0}
        <div
          class="mt-4 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
          role="alert"
        >
          <p class="font-medium">No puede publicar este impacto con sus permisos actuales.</p>
          <p class="mt-1 text-xs">
            Faltan: {missingPermissions.map(locationPermissionLabel).join(', ')}. Solicite estos
            permisos o corrija el archivo para evitar esas operaciones.
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
          <span class="font-medium text-foreground">Confirmo los cambios validados</span>
          <span class="mt-1 block text-xs text-foreground-muted">
            Se crearán {job.create_count.toLocaleString('es-SV')} y se actualizarán
            {job.update_count.toLocaleString('es-SV')} ubicaciones.
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
      <h3 class="mt-4 text-lg font-semibold text-foreground">Importación publicada</h3>
      <p class="mt-2 text-sm text-foreground-muted">
        Se procesaron {job.total_rows.toLocaleString('es-SV')} filas con trazabilidad de lote.
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
          >Elegir otro archivo</Button
        >{/if}
      {#if step === 1}<Button onclick={() => void preview()} disabled={!file || loading}
          >{loading ? 'Analizando…' : 'Validar archivo'}</Button
        >{/if}
      {#if step === 2}<Button onclick={() => void publish()} disabled={!canPublish || publishing}
          >{publishing ? 'Publicando…' : 'Publicar importación'}</Button
        >{/if}
    </div>
  </div>
</Modal>
