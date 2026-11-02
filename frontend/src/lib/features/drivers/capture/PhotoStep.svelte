<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import CameraCapture from './CameraCapture.svelte';
  import { QUALITY_MESSAGES, type QualityIssue } from './image-prep';

  let {
    side,
    preview,
    uploading,
    issue,
    canContinue,
    onphoto,
    oncontinue,
    onretry,
    onuseanyway
  }: {
    side: 'front' | 'back';
    preview: string | null;
    uploading: boolean;
    issue: QualityIssue | null;
    canContinue: boolean;
    onphoto: (photo: Blob) => void;
    oncontinue: () => void;
    onretry: () => void;
    onuseanyway: () => void;
  } = $props();

  const fileAction =
    'inline-flex h-11 cursor-pointer items-center justify-center gap-2 rounded-lg px-5 text-sm font-medium focus-within:ring-2 focus-within:ring-foreground focus-within:ring-offset-2 focus-within:ring-offset-surface';
  const fileSecondary = `${fileAction} border border-border bg-surface-elevated text-foreground shadow-soft hover:bg-surface-hover`;
  const filePrimary = `${fileAction} bg-foreground text-surface hover:bg-foreground-muted`;

  const label = $derived(side === 'front' ? 'el frente' : 'el reverso');
  const title = $derived(side === 'front' ? 'Frente de la licencia' : 'Reverso de la licencia');

  let cameraOpen = $state(false);
  let fromCamera = $state(false);
  let cameraIssue = $state<string | null>(null);
  let dragging = $state(false);
  let stage = $state<HTMLDivElement | null>(null);
  // Evaluado al abrir: en un móvil lo natural es fotografiar; en un PC, subir un archivo.
  const touchFirst = window.matchMedia?.('(pointer: coarse)').matches ?? false;
  // La cámara en vivo exige HTTPS; sin ella queda la cámara nativa del teléfono.
  const liveCamera = Boolean(navigator.mediaDevices?.getUserMedia);

  function onFile(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    fromCamera = false;
    if (file) onphoto(file);
  }

  /** Quien venía de la cámara vuelve directo a ella: es lo que estaba intentando hacer. */
  function retry() {
    onretry();
    if (fromCamera && liveCamera && !cameraIssue) cameraOpen = true;
  }

  $effect(() => {
    const element = stage;
    if (!element) return;
    const over = (event: DragEvent) => {
      event.preventDefault();
      dragging = true;
    };
    const leave = () => (dragging = false);
    const drop = (event: DragEvent) => {
      event.preventDefault();
      dragging = false;
      const file = event.dataTransfer?.files?.[0];
      if (file) onphoto(file);
    };
    element.addEventListener('dragover', over);
    element.addEventListener('dragleave', leave);
    element.addEventListener('drop', drop);
    return () => {
      element.removeEventListener('dragover', over);
      element.removeEventListener('dragleave', leave);
      element.removeEventListener('drop', drop);
    };
  });
</script>

{#if cameraOpen}
  <CameraCapture
    {label}
    oncapture={(photo) => {
      cameraOpen = false;
      fromCamera = true;
      onphoto(photo);
    }}
    onunavailable={(reason) => {
      cameraIssue = reason;
      cameraOpen = false;
    }}
    onback={() => (cameraOpen = false)}
  />
{:else}
  <div class="photo-step">
    <header>
      <h3>{title}</h3>
      <p>Carga {label} completo, con las cuatro esquinas visibles y sin reflejos.</p>
    </header>

    <div class="stage" class:dragging class:filled={!!preview} bind:this={stage}>
      {#if preview}
        <img src={preview} alt={`Foto de ${label} de la licencia`} width="856" height="540" />
      {:else}
        <div class="placeholder">
          <FleetIcon name="image" size={28} />
          <span class="drop-hint">Arrastra aquí la foto</span>
        </div>
      {/if}
      {#if uploading}
        <div class="working" role="status">
          <span class="spinner" aria-hidden="true"></span>Revisando la foto…
        </div>
      {/if}
    </div>

    {#if issue}
      <div class="notice warn" role="alert">
        <FleetIcon name="alert" size={16} />
        <div>
          <strong>{QUALITY_MESSAGES[issue].title}</strong>
          <p>{QUALITY_MESSAGES[issue].hint}</p>
        </div>
      </div>
    {/if}
    {#if cameraIssue}
      <div class="notice" role="status">
        <FleetIcon name="info" size={16} />
        <p>{cameraIssue}</p>
      </div>
    {/if}

    {#if issue}
      <div class="actions">
        <Button size="lg" onclick={retry}>Intentar de nuevo</Button>
        <button class="anyway" type="button" onclick={onuseanyway}>Usar de todos modos</button>
      </div>
    {:else}
      <div class="actions" class:reverse={!touchFirst && !preview}>
        {#if canContinue && !uploading}
          <Button size="lg" onclick={oncontinue}>Continuar con esta foto</Button>
        {/if}
        {#if liveCamera && !cameraIssue}
          <Button
            variant={preview || !touchFirst ? 'secondary' : 'primary'}
            size="lg"
            disabled={uploading}
            onclick={() => (cameraOpen = true)}
          >
            <FleetIcon name="camera" size={16} />{preview ? 'Tomar otra foto' : 'Tomar foto'}
          </Button>
        {:else if touchFirst}
          <label class={preview ? fileSecondary : filePrimary}>
            <FleetIcon name="camera" size={16} />{preview ? 'Tomar otra foto' : 'Tomar foto'}
            <input
              type="file"
              accept="image/*"
              capture="environment"
              disabled={uploading}
              onchange={onFile}
            />
          </label>
        {/if}
        <label class={!touchFirst && !preview ? filePrimary : fileSecondary}>
          <FleetIcon name="upload" size={16} />Subir archivo
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            disabled={uploading}
            onchange={onFile}
          />
        </label>
      </div>
    {/if}
  </div>
{/if}

<style>
  .photo-step {
    display: flex;
    flex-direction: column;
    gap: var(--driver-space-4);
    padding: var(--driver-space-4);
  }
  h3 {
    margin: 0;
    color: rgb(var(--foreground));
    font-size: 16px;
    font-weight: 600;
  }
  header p {
    margin: var(--driver-space-1) 0 0;
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  /* Misma proporción que la tarjeta: la foto llega al sitio que ya se le reservó. */
  .stage {
    position: relative;
    overflow: hidden;
    width: 100%;
    max-width: 560px;
    margin-inline: auto;
    aspect-ratio: 85.6 / 54;
    border: 2px dashed rgb(var(--border-strong));
    border-radius: var(--driver-radius-lg);
    background: rgb(var(--surface-muted));
  }
  .stage.filled {
    border-style: solid;
    border-color: rgb(var(--border));
  }
  .stage.dragging {
    border-color: rgb(var(--primary));
    background: rgb(var(--primary) / 8%);
  }
  .stage img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
  .placeholder {
    display: flex;
    height: 100%;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--driver-space-2);
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  .drop-hint {
    display: none;
  }
  .working {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--driver-space-2);
    color: rgb(var(--foreground));
    background: rgb(var(--surface) / 82%);
    font-size: 14px;
    font-weight: 500;
  }
  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgb(var(--border-strong));
    border-top-color: rgb(var(--foreground));
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  .notice {
    display: flex;
    gap: var(--driver-space-2);
    padding: var(--driver-space-3);
    border: 1px solid rgb(var(--border));
    border-radius: var(--driver-radius);
    color: rgb(var(--foreground));
    font-size: 14px;
  }
  .notice :global(svg) {
    flex: none;
    margin-top: 2px;
  }
  .notice.warn {
    border-color: rgb(var(--warning) / 45%);
    background: rgb(var(--warning) / 10%);
  }
  .notice p {
    margin: 0;
  }
  .notice strong {
    display: block;
    font-weight: 600;
  }
  /* Discreto a propósito: el detector puede equivocarse, pero repetir es lo recomendable. */
  .anyway {
    min-height: 44px;
    border-radius: var(--driver-radius);
    color: rgb(var(--foreground-muted));
    font-size: 14px;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .anyway:focus-visible {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 2px;
  }
  .actions {
    display: grid;
    gap: var(--driver-space-2);
  }
  .actions label {
    position: relative;
  }
  .actions input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
  }
  @media (min-width: 640px) {
    .photo-step {
      padding: var(--driver-space-5);
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
    }
    .actions.reverse {
      flex-direction: row-reverse;
    }
  }
  @media (hover: hover) and (pointer: fine) {
    .drop-hint {
      display: inline;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .spinner {
      animation-duration: 2.4s;
    }
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
