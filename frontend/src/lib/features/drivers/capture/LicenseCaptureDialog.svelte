<script lang="ts">
  import { untrack } from 'svelte';
  import { api, HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import {
    driversApi,
    type CaptureSide,
    type Driver,
    type LicenseCapture,
    type LicenseIssue,
    type LicenseValues
  } from '../api';
  import LicenseReviewForm from './LicenseReviewForm.svelte';
  import PhotoStep from './PhotoStep.svelte';
  import { checksumOf, prepareForUpload } from './upload';
  import { qualityMessages } from './image-prep';
  import { confirmBlocker, EMPTY_VALUES, isWaiting, mergeExtracted, warningCodes } from './review';

  const POLL_MS = 1200;
  const MANUAL_OFFER_MS = 60000;
  const CHECK_DEBOUNCE_MS = 350;
  const STEPS: { key: CaptureSide | 'review'; label: string }[] = [
    { key: 'front', label: 'Frente' },
    { key: 'back', label: 'Reverso' },
    { key: 'review', label: 'Revisión' }
  ];

  let {
    open = $bindable(false),
    driver,
    onconfirmed
  }: { open?: boolean; driver: Driver; onconfirmed: (driver: Driver) => void } = $props();

  let step = $state<CaptureSide | 'review'>('front');
  let capture = $state<LicenseCapture | null>(null);
  let busy = $state(false);
  let uploading = $state<CaptureSide | null>(null);
  let error = $state<string | null>(null);
  let photoWarnings = $state<string[]>([]);
  let previews = $state<Record<CaptureSide, string | null>>({ front: null, back: null });
  let values = $state<LicenseValues>({ ...EMPTY_VALUES });
  let touched = $state(new Set<keyof LicenseValues>());
  let acknowledged = $state(false);
  let overrideReason = $state('');
  let serverIssues = $state<LicenseIssue[]>([]);
  let waitedTooLong = $state(false);
  let discarding = $state(false);
  let generation = 0;

  const canOverride = $derived(permissions.hasPermission('drivers:license_override'));
  const analyzing = $derived(capture !== null && isWaiting(capture.status));
  const hasPhotos = $derived(!!capture?.front.document_id || !!capture?.back.document_id);
  const blocker = $derived(
    confirmBlocker({
      photosReady: capture?.front.status === 'active' && capture?.back.status === 'active',
      issues: serverIssues,
      acknowledged,
      canOverride,
      overrideReason
    })
  );
  const reading = $derived.by(() => {
    if (analyzing) return waitedTooLong ? 'slow' : 'analyzing';
    if (capture?.status === 'failed') return 'failed';
    if (capture && !capture.extraction_available && !capture.front.extracted) return 'unavailable';
    return 'done';
  });

  function isDone(key: CaptureSide | 'review'): boolean {
    return key !== 'review' && step !== key && !!capture?.[key].document_id;
  }

  function reset() {
    step = 'front';
    capture = null;
    busy = false;
    uploading = null;
    error = null;
    photoWarnings = [];
    revokePreviews();
    values = { ...EMPTY_VALUES };
    touched = new Set();
    acknowledged = false;
    overrideReason = '';
    serverIssues = [];
    waitedTooLong = false;
    discarding = false;
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

  // Reabrir una captura sin terminar recupera sus fotos en vez de pedirlas otra vez.
  async function resume(opened: LicenseCapture, current: number) {
    for (const side of ['front', 'back'] as const) {
      if (opened[side].status !== 'active') continue;
      const signed = await driversApi.capturePreview(driver.id, opened.id, side).catch(() => null);
      if (signed && current === generation) previews = { ...previews, [side]: signed.url };
    }
    if (current !== generation) return;
    if (opened.front.status === 'active') {
      step = opened.back.status === 'active' ? 'review' : 'back';
    }
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
          if (current !== generation) return;
          apply(opened);
          void resume(opened, current);
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
    const previous = previews[side];
    busy = true;
    uploading = side;
    error = null;
    photoWarnings = [];
    let shown: string | null = null;
    try {
      const prepared = await prepareForUpload(source, side);
      shown = URL.createObjectURL(prepared.file);
      previews = { ...previews, [side]: shown };
      const ticket = await driversApi.startCaptureUpload(driver.id, capture.id, side, {
        content_type: prepared.file.type,
        size_bytes: prepared.file.size,
        checksum_sha256: await checksumOf(prepared.file)
      });
      await api.documents.uploadDirect(ticket, prepared.file);
      apply(await driversApi.completeCaptureUpload(driver.id, capture.id, side));
      if (previous) URL.revokeObjectURL(previous);
      photoWarnings = qualityMessages(prepared.quality);
      if (photoWarnings.length === 0) advance();
    } catch (err) {
      if (shown) URL.revokeObjectURL(shown);
      previews = { ...previews, [side]: previous };
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
    step = step === 'front' ? 'back' : 'review';
  }

  function goBack() {
    photoWarnings = [];
    error = null;
    step = 'front';
  }

  function edit(key: keyof LicenseValues, value: string) {
    values[key] = value.trim() ? value : null;
    touched = new Set(touched).add(key);
    acknowledged = false;
  }

  async function confirm() {
    if (!capture || blocker || busy) return;
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
  size={step === 'review' ? 'xl' : 'lg'}
  mobileFullScreen
  flush
  preventClose={busy}
  onclose={() => {
    if (!busy) open = false;
  }}
>
  <div class="license-capture">
    <ol class="steps">
      {#each STEPS as item, index (item.key)}
        <li
          class:current={step === item.key}
          class:done={isDone(item.key)}
          aria-current={step === item.key ? 'step' : undefined}
        >
          <span class="dot" aria-hidden="true">
            {#if isDone(item.key)}<FleetIcon name="check" size={12} />{:else}{index + 1}{/if}
          </span>
          {item.label}
        </li>
      {/each}
    </ol>

    {#if error}<p class="alert" role="alert">{error}</p>{/if}

    {#if step !== 'review'}
      {#key step}
        <PhotoStep
          side={step}
          preview={previews[step]}
          uploading={uploading === step}
          warnings={photoWarnings}
          canContinue={capture?.[step].status === 'active'}
          onphoto={(photo) => void usePhoto(photo)}
          oncontinue={advance}
        />
      {/key}
    {:else}
      <LicenseReviewForm
        {values}
        issues={serverIssues}
        {previews}
        {reading}
        {touched}
        {canOverride}
        bind:acknowledged
        bind:overrideReason
        onedit={edit}
        onretake={() => (step = 'front')}
      />
    {/if}
  </div>

  {#snippet footer()}
    <div class="license-capture footer">
      {#if discarding}
        <p class="hint" role="status">¿Descartar las fotos y los datos de esta captura?</p>
        <div class="buttons">
          <Button variant="secondary" size="lg" class="grow" onclick={() => (discarding = false)}>
            Conservar
          </Button>
          <Button variant="danger" size="lg" class="grow" onclick={() => void cancel()}>
            Sí, descartar
          </Button>
        </div>
      {:else}
        {#if step === 'review'}
          <p class="hint" role="status">{blocker ?? 'Todo listo para confirmar.'}</p>
        {/if}
        <div class="buttons">
          {#if hasPhotos}
            <Button variant="ghost" size="lg" disabled={busy} onclick={() => (discarding = true)}>
              <FleetIcon name="trash" size={16} /><span class="discard-label"
                >Descartar captura</span
              >
            </Button>
          {:else}
            <Button variant="ghost" size="lg" disabled={busy} onclick={() => (open = false)}>
              Cancelar
            </Button>
          {/if}
          <span class="spacer"></span>
          {#if step === 'back'}
            <Button variant="secondary" size="lg" disabled={busy} onclick={goBack}>Atrás</Button>
          {/if}
          {#if step === 'review'}
            <Button
              size="lg"
              class="grow sm:grow-0"
              disabled={!!blocker || busy}
              onclick={() => void confirm()}
            >
              {busy ? 'Confirmando…' : 'Confirmar licencia'}
            </Button>
          {/if}
        </div>
      {/if}
    </div>
  {/snippet}
</Modal>

<style>
  .steps {
    display: flex;
    gap: var(--driver-space-1);
    margin: 0;
    padding: var(--driver-space-3) var(--driver-space-4);
    border-bottom: 1px solid rgb(var(--border));
    list-style: none;
  }
  .steps li {
    display: flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    gap: var(--driver-space-2);
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .steps li.done {
    color: rgb(var(--foreground));
  }
  .steps li.current {
    color: rgb(var(--foreground));
    font-weight: 600;
  }
  .dot {
    display: inline-flex;
    width: 22px;
    height: 22px;
    flex: none;
    align-items: center;
    justify-content: center;
    border: 1px solid rgb(var(--border-strong));
    border-radius: 50%;
    font-size: 12px;
  }
  .current .dot {
    border-color: rgb(var(--foreground));
    color: rgb(var(--surface));
    background: rgb(var(--foreground));
  }
  .done .dot {
    border-color: rgb(var(--success));
    color: rgb(var(--success));
  }
  .alert {
    margin: var(--driver-space-3) var(--driver-space-4) 0;
    padding: var(--driver-space-2) var(--driver-space-3);
    border-left: 3px solid rgb(var(--danger));
    border-radius: var(--driver-radius);
    color: rgb(var(--foreground));
    background: rgb(var(--danger) / 10%);
    font-size: 14px;
  }
  .footer {
    display: flex;
    width: 100%;
    flex-direction: column;
    gap: var(--driver-space-2);
  }
  .hint {
    margin: 0;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .buttons {
    display: flex;
    align-items: center;
    gap: var(--driver-space-2);
  }
  .spacer {
    flex: 1;
  }
  /* En móvil queda como icono para dar todo el ancho a la acción principal; sigue teniendo nombre. */
  .discard-label {
    position: absolute;
    overflow: hidden;
    width: 1px;
    height: 1px;
    clip-path: inset(50%);
    white-space: nowrap;
  }
  .footer :global(.grow) {
    flex: 1 1 auto;
  }
  @media (min-width: 640px) {
    .footer {
      flex-direction: row;
      align-items: center;
      gap: var(--driver-space-4);
    }
    .hint {
      flex: 1;
    }
    .buttons {
      flex: 1;
    }
    .hint + .buttons {
      flex: none;
    }
    .discard-label {
      position: static;
      width: auto;
      height: auto;
      clip-path: none;
    }
    .footer :global(.sm\:grow-0),
    .footer :global(.grow) {
      flex: 0 0 auto;
    }
  }
</style>
