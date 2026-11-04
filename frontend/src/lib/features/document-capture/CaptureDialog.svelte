<script lang="ts" generics="R">
  import { tick, untrack } from 'svelte';
  import { api, HttpError } from '$lib/api/client';
  import './capture-theme.css';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import CaptureReviewForm from './CaptureReviewForm.svelte';
  import PhotoStep from './PhotoStep.svelte';
  import { checksumOf, prepareForUpload } from './upload';
  import type { QualityIssue } from './image-prep';
  import {
    ACKNOWLEDGE_BLOCKER,
    confirmBlocker,
    emptyValues,
    issuesToShow,
    isWaiting,
    mergeExtracted,
    unreadFields,
    warningCodes
  } from './review';
  import type {
    CaptureConfig,
    CaptureIssue,
    CaptureSide,
    CaptureState,
    CaptureValues
  } from './types';

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
    config,
    onconfirmed
  }: { open?: boolean; config: CaptureConfig<R>; onconfirmed: (result: R) => void } = $props();

  let step = $state<CaptureSide | 'review'>('front');
  let capture = $state<CaptureState | null>(null);
  let busy = $state(false);
  let uploading = $state<CaptureSide | null>(null);
  let error = $state<string | null>(null);
  /** Foto con un problema: aún no se sube, a la espera de que el usuario decida. */
  let held = $state<{
    side: CaptureSide;
    file: File;
    issue: QualityIssue;
    previous: string | null;
  } | null>(null);
  let previews = $state<Record<CaptureSide, string | null>>({ front: null, back: null });
  let values = $state<CaptureValues>({});
  let touched = $state(new Set<string>());
  let acknowledged = $state(false);
  let overrideReason = $state('');
  let serverIssues = $state<CaptureIssue[]>([]);
  let serverFills = $state<readonly string[]>([]);
  let waitedTooLong = $state(false);
  let discarding = $state(false);
  let resumed = $state(false);
  let openFailed = $state(false);
  let cameraActive = $state(false);
  let generation = 0;
  let checkRound = 0;
  let acknowledgedWarnings = '';
  let shownStep: CaptureSide | 'review' = 'front';
  let root = $state<HTMLDivElement | null>(null);
  let footerRoot = $state<HTMLDivElement | null>(null);

  const canOverride = $derived(
    !!config.overridePermission && permissions.hasPermission(config.overridePermission)
  );
  const analyzing = $derived(capture !== null && isWaiting(capture.status));
  const hasPhotos = $derived(!!capture?.front.document_id || !!capture?.back.document_id);
  const blocker = $derived(
    confirmBlocker(
      {
        photosReady: capture?.front.status === 'active' && capture?.back.status === 'active',
        issues: serverIssues,
        acknowledged,
        canOverride,
        overrideReason
      },
      config
    )
  );
  const unread = $derived(
    capture ? unreadFields(values, serverIssues, capture, touched, config) : []
  );
  const reading = $derived.by(() => {
    if (analyzing) return waitedTooLong ? 'slow' : 'analyzing';
    if (capture?.status === 'failed') return 'failed';
    if (capture && !capture.extraction_available && !capture.front.extracted) return 'unavailable';
    return 'done';
  });

  const visibleIssues = $derived(issuesToShow(serverIssues, values, touched, analyzing));
  const hint = $derived(
    visibleIssues.length < serverIssues.length
      ? `Leyendo ${config.documentName}…`
      : (blocker ?? 'Todo listo para confirmar.')
  );

  function isDone(key: CaptureSide | 'review'): boolean {
    return key !== 'review' && step !== key && !!capture?.[key].document_id;
  }

  function reset() {
    step = 'front';
    resumed = false;
    openFailed = false;
    capture = null;
    busy = false;
    uploading = null;
    error = null;
    held = null;
    revokePreviews();
    values = emptyValues(config.fields);
    touched = new Set();
    acknowledged = false;
    overrideReason = '';
    serverIssues = [];
    serverFills = [];
    waitedTooLong = false;
    discarding = false;
  }

  // Marcar la casilla vale para los avisos que se veían: uno nuevo pide revisarlo otra vez.
  $effect(() => {
    const key = warningCodes(serverIssues).join('|');
    if (key === acknowledgedWarnings) return;
    acknowledgedWarnings = key;
    acknowledged = false;
  });

  // Al cambiar de paso desaparece el botón pulsado: el foco no debe caer al vacío.
  $effect(() => {
    if (step === shownStep) return;
    shownStep = step;
    resumed = false;
    void tick().then(() =>
      root?.querySelector<HTMLElement>('[data-step-title]')?.focus({ preventScroll: true })
    );
  });

  /** The checkbox sits below every field: this takes the user straight to it. */
  function goToAcknowledge() {
    const box = root?.querySelector<HTMLInputElement>('[data-acknowledge]');
    box?.focus({ preventScroll: true });
    box?.scrollIntoView({ block: 'center' });
  }

  function setDiscarding(next: boolean) {
    discarding = next;
    void tick().then(() => footerRoot?.querySelector('button')?.focus());
  }

  // Lo escrito se valida en el servidor mientras se edita: confirmar no da sorpresas.
  $effect(() => {
    if (!open || step !== 'review' || !capture) return;
    const id = capture.id;
    const snapshot = { ...values };
    const timer = setTimeout(() => {
      // Una respuesta lenta no debe pisar la de lo último que se escribió.
      const round = ++checkRound;
      config.api
        .check(id, snapshot)
        .then((checked) => {
          if (!open || round !== checkRound) return;
          serverIssues = checked.issues;
          serverFills = checked.fills ?? [];
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
  async function resume(opened: CaptureState, current: number) {
    for (const side of ['front', 'back'] as const) {
      if (opened[side].status !== 'active') continue;
      const signed = await config.api.preview(opened.id, side).catch(() => null);
      if (signed && current === generation) previews = { ...previews, [side]: signed.url };
    }
    if (current !== generation) return;
    if (opened.front.status === 'active') {
      step = opened.back.status === 'active' ? 'review' : 'back';
    }
  }

  function apply(next: CaptureState) {
    capture = next;
    values = mergeExtracted(values, next.values, touched);
    if (step !== 'review') {
      serverIssues = next.issues;
      serverFills = next.fills ?? [];
    }
  }

  $effect(() => {
    if (!open) {
      generation++;
      return;
    }
    const current = ++generation;
    untrack(() => {
      reset();
      begin(current);
    });
  });

  function begin(current: number) {
    error = null;
    openFailed = false;
    config.api
      .open()
      .then((opened) => {
        if (current !== generation) return;
        apply(opened);
        resumed = !!opened.front.document_id || !!opened.back.document_id;
        void resume(opened, current);
      })
      .catch((err: unknown) => {
        if (current !== generation) return;
        openFailed = true;
        error = err instanceof HttpError ? err.message : 'No se pudo iniciar la captura.';
      });
  }

  // Consulta mientras el modelo analiza: la extracción nunca bloquea el asistente.
  $effect(() => {
    if (!open || !analyzing || !capture) return;
    const id = capture.id;
    const timer = setInterval(() => {
      config.api
        .get(id)
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

  // La calidad se revisa antes de subir: el aviso es inmediato y no se escanea ni se
  // guarda una foto que el usuario probablemente va a repetir.
  async function usePhoto(source: Blob) {
    if (!capture || step === 'review' || busy) return;
    const side = step;
    const previous = previews[side];
    busy = true;
    error = null;
    held = null;
    try {
      const prepared = await prepareForUpload(source, side, config.filePrefix);
      previews = { ...previews, [side]: URL.createObjectURL(prepared.file) };
      const ignored = config.ignoredQuality?.[side] ?? [];
      const [issue] = prepared.issues.filter((item) => !ignored.includes(item));
      if (issue) {
        held = { side, file: prepared.file, issue, previous };
        return;
      }
      await upload(side, prepared.file, previous);
    } catch {
      error = 'No se pudo procesar la foto. Prueba con otra imagen en JPG o PNG.';
    } finally {
      busy = false;
    }
  }

  async function upload(side: CaptureSide, file: File, previous: string | null) {
    if (!capture) return;
    uploading = side;
    error = null;
    try {
      const ticket = await config.api.startUpload(capture.id, side, {
        content_type: file.type,
        size_bytes: file.size,
        checksum_sha256: await checksumOf(file)
      });
      await api.documents.uploadDirect(ticket, file);
      apply(await config.api.completeUpload(capture.id, side));
      if (previous) URL.revokeObjectURL(previous);
      advance();
    } catch (err) {
      restorePreview(side, previous);
      error =
        err instanceof HttpError
          ? err.message
          : 'No se pudo cargar la foto. Revisa tu conexión e inténtalo de nuevo.';
    } finally {
      uploading = null;
    }
  }

  function restorePreview(side: CaptureSide, previous: string | null) {
    const shown = previews[side];
    if (shown && shown !== previous) URL.revokeObjectURL(shown);
    previews = { ...previews, [side]: previous };
  }

  function retryPhoto() {
    if (!held) return;
    restorePreview(held.side, held.previous);
    held = null;
  }

  async function useHeldPhoto() {
    if (!held || busy) return;
    const { side, file, previous } = held;
    held = null;
    busy = true;
    try {
      await upload(side, file, previous);
    } finally {
      busy = false;
    }
  }

  function advance() {
    step = step === 'front' ? 'back' : 'review';
  }

  function goBack() {
    retryPhoto();
    error = null;
    step = 'front';
  }

  function edit(key: string, value: string) {
    values[key] = value.trim() ? value : null;
    touched = new Set(touched).add(key);
    acknowledged = false;
  }

  async function confirm() {
    if (!capture || blocker || busy) return;
    busy = true;
    error = null;
    try {
      const saved = await config.api.confirm(capture.id, {
        values,
        acknowledged_warnings: warningCodes(serverIssues),
        override_reason: overrideReason.trim() || null
      });
      revokePreviews();
      open = false;
      onconfirmed(saved);
    } catch (err) {
      error = err instanceof HttpError ? err.message : config.confirmError;
    } finally {
      busy = false;
    }
  }

  async function cancel() {
    const id = capture?.id;
    open = false;
    revokePreviews();
    if (id) await config.api.cancel(id).catch(() => undefined);
  }
</script>

<Modal
  {open}
  title={config.dialogTitle}
  size="xl"
  mobileFullScreen
  flush
  preventClose={busy}
  onclose={() => {
    if (!busy) open = false;
  }}
>
  <div class="document-capture" bind:this={root}>
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
          {item.label}{#if isDone(item.key)}<span class="done-label">, completado</span>{/if}
        </li>
      {/each}
    </ol>

    {#if resumed}
      <p class="resumed" role="status">Retomamos la captura que dejaste sin terminar.</p>
    {/if}
    {#if error && step !== 'review'}<p class="alert" role="alert">{error}</p>{/if}
    {#if openFailed}
      <div class="retry">
        <Button variant="secondary" onclick={() => begin(generation)}>Reintentar</Button>
      </div>
    {/if}

    {#if step !== 'review'}
      {#key step}
        <PhotoStep
          side={step}
          documentName={config.documentName}
          ignoredQuality={config.ignoredQuality?.[step]}
          preview={previews[step]}
          uploading={busy || uploading === step}
          ready={!!capture}
          issue={held?.side === step ? held.issue : null}
          canContinue={capture?.[step].status === 'active'}
          oncamera={(active) => (cameraActive = active)}
          onphoto={(photo) => void usePhoto(photo)}
          oncontinue={advance}
          onretry={retryPhoto}
          onuseanyway={() => void useHeldPhoto()}
        />
      {/key}
    {:else}
      <CaptureReviewForm
        {config}
        {values}
        issues={visibleIssues}
        fills={serverFills}
        {previews}
        {reading}
        {unread}
        {touched}
        {canOverride}
        bind:acknowledged
        bind:overrideReason
        onedit={edit}
        onretake={(side) => (step = side)}
      />
    {/if}
  </div>

  {#snippet footer()}
    <div class="document-capture footer" bind:this={footerRoot}>
      <!-- Junto al botón: quien bajó hasta aquí no vería un error en lo alto del formulario. -->
      {#if error && step === 'review'}<p class="alert footer-alert" role="alert">{error}</p>{/if}
      {#if cameraActive}
        <!-- La cámara tiene su propio botón para volver: aquí solo estorbaría. -->
      {:else if discarding}
        <p class="hint" role="status">¿Descartar las fotos y los datos de esta captura?</p>
        <div class="buttons">
          <Button variant="secondary" size="lg" class="grow" onclick={() => setDiscarding(false)}>
            Conservar
          </Button>
          <Button variant="danger" size="lg" class="grow" onclick={() => void cancel()}>
            Sí, descartar
          </Button>
        </div>
      {:else}
        {#if step === 'review'}
          <p class="hint" role="status">
            {#if hint === ACKNOWLEDGE_BLOCKER}
              <button type="button" class="hint-link" onclick={goToAcknowledge}>{hint}</button>
            {:else}
              {hint}
            {/if}
          </p>
        {/if}
        <div class="buttons">
          {#if hasPhotos}
            <Button variant="ghost" size="lg" disabled={busy} onclick={() => setDiscarding(true)}>
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
              {busy ? 'Confirmando…' : config.confirmLabel}
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
    gap: var(--capture-space-1);
    margin: 0;
    padding: var(--capture-space-3) var(--capture-space-4);
    border-bottom: 1px solid rgb(var(--border));
    list-style: none;
  }
  .steps li {
    display: flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    gap: var(--capture-space-2);
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
    margin: var(--capture-space-3) var(--capture-space-4) 0;
    padding: var(--capture-space-2) var(--capture-space-3);
    border-left: 3px solid rgb(var(--danger));
    border-radius: var(--capture-radius);
    color: rgb(var(--foreground));
    background: rgb(var(--danger) / 10%);
    font-size: 14px;
  }
  .footer {
    display: flex;
    width: 100%;
    flex-direction: column;
    gap: var(--capture-space-2);
  }
  .footer-alert {
    margin: 0;
  }
  .retry {
    margin: var(--capture-space-2) var(--capture-space-4) 0;
  }
  .resumed {
    margin: var(--capture-space-3) var(--capture-space-4) 0;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .hint-link {
    min-height: 44px;
    color: rgb(var(--foreground));
    font-size: 13px;
    text-align: left;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .done-label {
    position: absolute;
    overflow: hidden;
    width: 1px;
    height: 1px;
    clip-path: inset(50%);
    white-space: nowrap;
  }
  .hint {
    margin: 0;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .buttons {
    display: flex;
    align-items: center;
    gap: var(--capture-space-2);
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
      flex-wrap: wrap;
      align-items: center;
      gap: var(--capture-space-4);
    }
    .footer-alert {
      flex-basis: 100%;
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
