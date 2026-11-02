<script lang="ts">
  import { untrack } from 'svelte';
  import { api, HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import {
    driversApi,
    type CaptureSide,
    type Driver,
    type LicenseCapture,
    type LicenseIssue,
    type LicenseValues
  } from '../api';
  import CameraCapture from './CameraCapture.svelte';
  import { checksumOf, prepareForUpload } from './upload';
  import { qualityMessages } from './image-prep';
  import {
    EMPTY_VALUES,
    FIELD_LABELS,
    issuesFor,
    isWaiting,
    mergeExtracted,
    warningCodes
  } from './review';

  const POLL_MS = 1200;
  const MANUAL_OFFER_MS = 60000;
  const CHECK_DEBOUNCE_MS = 350;

  let {
    open = $bindable(false),
    driver,
    onconfirmed
  }: { open?: boolean; driver: Driver; onconfirmed: (driver: Driver) => void } = $props();

  type Mode = 'choose' | 'camera';
  let step = $state<CaptureSide | 'review'>('front');
  let mode = $state<Mode>('choose');
  let capture = $state<LicenseCapture | null>(null);
  let busy = $state(false);
  let uploading = $state<CaptureSide | null>(null);
  let error = $state<string | null>(null);
  let cameraIssue = $state<string | null>(null);
  let photoWarnings = $state<string[]>([]);
  let previews = $state<Record<CaptureSide, string | null>>({ front: null, back: null });
  let values = $state<LicenseValues>({ ...EMPTY_VALUES });
  let touched = $state(new Set<keyof LicenseValues>());
  let acknowledged = $state(false);
  let overrideReason = $state('');
  let serverIssues = $state<LicenseIssue[]>([]);
  let waitedTooLong = $state(false);
  let generation = 0;

  const canOverride = $derived(permissions.hasPermission('drivers:license_override'));
  const mismatches = $derived(serverIssues.filter((issue) => issue.severity === 'mismatch'));
  const warnings = $derived(serverIssues.filter((issue) => issue.severity === 'warning'));
  const errors = $derived(serverIssues.filter((issue) => issue.severity === 'error'));
  const analyzing = $derived(capture !== null && isWaiting(capture.status));
  const canConfirm = $derived(
    !busy &&
      capture?.front.status === 'active' &&
      capture?.back.status === 'active' &&
      (warnings.length === 0 || acknowledged) &&
      (mismatches.length === 0 || (canOverride && overrideReason.trim().length >= 3))
  );
  const sideLabel = $derived(step === 'back' ? 'el reverso' : 'el frente');
  const fieldKeys = Object.keys(FIELD_LABELS) as (keyof LicenseValues)[];

  function reset() {
    step = 'front';
    mode = 'choose';
    capture = null;
    busy = false;
    uploading = null;
    error = null;
    cameraIssue = null;
    photoWarnings = [];
    revokePreviews();
    values = { ...EMPTY_VALUES };
    touched = new Set();
    acknowledged = false;
    overrideReason = '';
    serverIssues = [];
    waitedTooLong = false;
  }

  // Lo escrito se valida en el servidor mientras se edita: confirmar no da sorpresas.
  $effect(() => {
    if (!open || step !== 'review' || !capture) return;
    const id = capture.id;
    const snapshot = { ...values };
    const timer = setTimeout(() => {
      driversApi
        .checkCapture(driver.id, id, snapshot)
        .then((issues) => {
          if (open) serverIssues = issues;
        })
        .catch(() => undefined);
    }, CHECK_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  });

  function revokePreviews() {
    for (const url of Object.values(previews)) if (url) URL.revokeObjectURL(url);
    previews = { front: null, back: null };
  }

  function apply(next: LicenseCapture) {
    capture = next;
    values = mergeExtracted(values, next.values, touched);
    if (step !== 'review') serverIssues = next.issues;
  }

  $effect(() => {
    if (!open) {
      generation++;
      return;
    }
    const current = ++generation;
    untrack(() => {
      reset();
      driversApi
        .openCapture(driver.id)
        .then((opened) => {
          if (current === generation) apply(opened);
        })
        .catch((err: unknown) => {
          if (current === generation)
            error = err instanceof HttpError ? err.message : 'No se pudo iniciar la captura.';
        });
    });
  });

  // Consulta mientras el modelo analiza: la extracción nunca bloquea el asistente.
  $effect(() => {
    if (!open || !analyzing || !capture) return;
    const id = capture.id;
    const timer = setInterval(() => {
      driversApi
        .getCapture(driver.id, id)
        .then((next) => {
          if (open && capture?.id === next.id) apply(next);
        })
        .catch(() => undefined);
    }, POLL_MS);
    const patience = setTimeout(() => (waitedTooLong = true), MANUAL_OFFER_MS);
    return () => {
      clearInterval(timer);
      clearTimeout(patience);
      waitedTooLong = false;
    };
  });

  async function usePhoto(source: Blob) {
    if (!capture || step === 'review' || busy) return;
    const side = step;
    busy = true;
    uploading = side;
    error = null;
    photoWarnings = [];
    try {
      const prepared = await prepareForUpload(source, side);
      const ticket = await driversApi.startCaptureUpload(driver.id, capture.id, side, {
        content_type: prepared.file.type,
        size_bytes: prepared.file.size,
        checksum_sha256: await checksumOf(prepared.file)
      });
      await api.documents.uploadDirect(ticket, prepared.file);
      apply(await driversApi.completeCaptureUpload(driver.id, capture.id, side));
      if (previews[side]) URL.revokeObjectURL(previews[side]);
      previews = { ...previews, [side]: URL.createObjectURL(prepared.file) };
      photoWarnings = qualityMessages(prepared.quality);
      mode = 'choose';
      if (photoWarnings.length === 0) advance();
    } catch (err) {
      error =
        err instanceof HttpError
          ? err.message
          : 'No se pudo procesar la foto. Prueba con otra imagen en JPG o PNG.';
    } finally {
      busy = false;
      uploading = null;
    }
  }

  function advance() {
    photoWarnings = [];
    cameraIssue = null;
    mode = 'choose';
    step = step === 'front' ? 'back' : 'review';
  }

  function onFile(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (file) void usePhoto(file);
  }

  function edit(key: keyof LicenseValues, value: string) {
    values[key] = value.trim() ? value : null;
    touched = new Set(touched).add(key);
    acknowledged = false;
  }

  async function confirm() {
    if (!capture || !canConfirm) return;
    busy = true;
    error = null;
    try {
      const saved = await driversApi.confirmCapture(driver.id, capture.id, {
        values,
        acknowledged_warnings: warningCodes(serverIssues),
        override_reason: overrideReason.trim() || null
      });
      revokePreviews();
      open = false;
      onconfirmed(saved);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo confirmar la licencia.';
    } finally {
      busy = false;
    }
  }

  async function cancel() {
    const id = capture?.id;
    open = false;
    revokePreviews();
    if (id) await driversApi.cancelCapture(driver.id, id).catch(() => undefined);
  }
</script>

<Modal
  {open}
  title="Capturar licencia de conducir"
  size="lg"
  mobileFullScreen
  preventClose={busy}
  onclose={() => {
    if (!busy) open = false;
  }}
>
  <div class="capture">
    <ol class="steps" aria-label="Pasos">
      <li class:current={step === 'front'} class:done={!!capture?.front.document_id}>Frente</li>
      <li class:current={step === 'back'} class:done={!!capture?.back.document_id}>Reverso</li>
      <li class:current={step === 'review'}>Revisión</li>
    </ol>

    {#if error}<p class="alert" role="alert">{error}</p>{/if}

    {#if step !== 'review'}
      {#if uploading}
        <div class="progress" role="status">Preparando y revisando la foto…</div>
      {:else if mode === 'camera'}
        <CameraCapture
          label={sideLabel}
          oncapture={(photo) => void usePhoto(photo)}
          onunavailable={(reason) => {
            cameraIssue = reason;
            mode = 'choose';
          }}
        />
        <Button variant="ghost" onclick={() => (mode = 'choose')}>Volver</Button>
      {:else}
        <p class="lead">Carga {sideLabel} de la licencia completa y bien iluminada.</p>
        {#if previews[step]}
          <img class="photo" src={previews[step]} alt={`Foto de ${sideLabel} de la licencia`} />
        {/if}
        {#if photoWarnings.length > 0}
          <div class="warning-box" role="status">
            {#each photoWarnings as message (message)}<p>{message}</p>{/each}
            <Button variant="secondary" size="sm" onclick={advance}
              >Usar esta foto de todos modos</Button
            >
          </div>
        {/if}
        {#if cameraIssue}<p class="hint" role="status">{cameraIssue}</p>{/if}
        <div class="sources">
          <Button onclick={() => (mode = 'camera')}>Usar cámara</Button>
          <label class="file-button">
            Tomar con el teléfono
            <input type="file" accept="image/*" capture="environment" onchange={onFile} />
          </label>
          <label class="file-button">
            Subir archivo
            <input type="file" accept="image/jpeg,image/png,image/webp" onchange={onFile} />
          </label>
        </div>
      {/if}
    {:else}
      <div class="review">
        <div class="images">
          {#each ['front', 'back'] as const as side (side)}
            {#if previews[side]}
              <img src={previews[side]} alt={side === 'front' ? 'Frente' : 'Reverso'} />
            {/if}
          {/each}
          <Button variant="ghost" size="sm" onclick={() => (step = 'front')}>Repetir fotos</Button>
        </div>
        <div class="fields">
          {#if analyzing}
            <p class="status" role="status">
              Analizando la licencia. Puedes escribir los datos mientras tanto.
              {#if waitedTooLong}<br />Está tardando más de lo normal; continúa manualmente si lo
                prefieres.{/if}
            </p>
          {:else if capture?.status === 'failed'}
            <p class="status" role="status">
              No se pudieron leer los datos. Escríbelos revisando la foto.
            </p>
          {:else if capture && !capture.extraction_available && !capture.front.extracted}
            <p class="status" role="status">
              La lectura automática no está disponible. Escribe los datos revisando la foto.
            </p>
          {:else}
            <p class="status" role="status">Revisa cada dato contra la foto antes de confirmar.</p>
          {/if}

          {#each fieldKeys as key (key)}
            {@const fieldIssues = issuesFor(serverIssues, key)}
            <label>
              <span
                >{FIELD_LABELS[key].label}{#if FIELD_LABELS[key].hint}<small
                    >{FIELD_LABELS[key].hint}</small
                  >{/if}</span
              >
              <input
                value={values[key] ?? ''}
                autocomplete="off"
                aria-invalid={fieldIssues.some((issue) => issue.severity !== 'warning')}
                oninput={(event) => edit(key, event.currentTarget.value)}
              />
              {#each fieldIssues as issue (issue.code)}
                <small class={`issue ${issue.severity}`}>{issue.message}</small>
              {/each}
            </label>
          {/each}

          {#if errors.length > 0}
            <p class="hint">Corrige los campos marcados para poder confirmar.</p>
          {/if}

          {#if mismatches.length > 0}
            {#if canOverride}
              <label>
                <span>Motivo de la excepción</span>
                <textarea rows="2" bind:value={overrideReason} maxlength="500"></textarea>
              </label>
            {:else}
              <p class="alert" role="alert">
                Estos datos no coinciden con el empleado. Corrígelos o pide autorización a un
                administrador.
              </p>
            {/if}
          {/if}

          {#if warnings.length > 0}
            <label class="check">
              <input type="checkbox" bind:checked={acknowledged} />
              <span>Revisé los avisos y los datos coinciden con la licencia.</span>
            </label>
          {/if}

          <p class="hint">
            Estas comprobaciones revisan que los datos sean coherentes; no certifican que el
            documento sea auténtico.
          </p>
        </div>
      </div>
    {/if}
  </div>

  {#snippet footer()}
    <Button variant="ghost" disabled={busy} onclick={() => void cancel()}>Descartar captura</Button>
    {#if step === 'review'}
      <Button disabled={!canConfirm} onclick={() => void confirm()}>
        {busy ? 'Confirmando…' : 'Confirmar licencia'}
      </Button>
    {/if}
  {/snippet}
</Modal>

<style>
  .capture {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .steps {
    display: flex;
    gap: 6px;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 12px;
  }
  .steps li {
    flex: 1;
    padding: 6px 8px;
    border-radius: 8px;
    text-align: center;
    color: rgb(var(--foreground-muted));
    background: rgb(var(--surface-muted, var(--surface)));
  }
  .steps li.done {
    color: rgb(var(--foreground));
  }
  .steps li.current {
    color: rgb(var(--primary-foreground, 255 255 255));
    background: rgb(var(--primary));
  }
  .lead,
  .hint,
  .status {
    margin: 0;
    font-size: 13px;
    color: rgb(var(--foreground-muted));
  }
  .status {
    padding: 8px 10px;
    border-radius: 8px;
    background: rgb(var(--surface-muted, var(--surface)));
  }
  .alert {
    margin: 0;
    padding: 8px 10px;
    border-radius: 8px;
    font-size: 13px;
    color: rgb(var(--danger, 185 28 28));
    background: rgb(var(--danger, 185 28 28) / 10%);
  }
  .warning-box {
    display: flex;
    flex-direction: column;
    gap: 6px;
    align-items: flex-start;
    padding: 8px 10px;
    border-radius: 8px;
    font-size: 13px;
    background: rgb(var(--warning, 180 83 9) / 12%);
  }
  .warning-box p {
    margin: 0;
  }
  .progress {
    padding: 32px 12px;
    text-align: center;
    color: rgb(var(--foreground-muted));
  }
  .photo {
    width: 100%;
    max-height: 40dvh;
    object-fit: contain;
    border-radius: 10px;
  }
  .sources {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .file-button {
    display: inline-flex;
    align-items: center;
    padding: 8px 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    font-size: 14px;
    cursor: pointer;
  }
  .file-button:focus-within {
    outline: 2px solid rgb(var(--primary));
  }
  .file-button input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
  }
  .review {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 16px;
  }
  .images {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .images img {
    width: 100%;
    border-radius: 8px;
  }
  .fields {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .fields label {
    display: flex;
    flex-direction: column;
    gap: 3px;
    font-size: 13px;
  }
  .fields label span small {
    margin-left: 6px;
    color: rgb(var(--foreground-muted));
  }
  .fields input:not([type='checkbox']),
  .fields textarea {
    width: 100%;
    padding: 7px 9px;
    border: 1px solid rgb(var(--border));
    border-radius: 7px;
    color: rgb(var(--foreground));
    background: rgb(var(--surface));
  }
  .fields input[aria-invalid='true'] {
    border-color: rgb(var(--danger, 185 28 28));
  }
  .fields .check {
    flex-direction: row;
    align-items: flex-start;
    gap: 8px;
  }
  .issue {
    font-size: 12px;
  }
  .issue.error,
  .issue.mismatch {
    color: rgb(var(--danger, 185 28 28));
  }
  .issue.warning {
    color: rgb(var(--warning, 180 83 9));
  }
  @media (max-width: 640px) {
    .review {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
