<script lang="ts">
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';

  let {
    label,
    oncapture,
    onunavailable,
    onback
  }: {
    label: string;
    oncapture: (photo: Blob) => void;
    onunavailable: (reason: string) => void;
    onback: () => void;
  } = $props();

  let video = $state<HTMLVideoElement | null>(null);
  let ready = $state(false);

  function denied(error: unknown): string {
    const name = error instanceof DOMException ? error.name : '';
    if (name === 'NotAllowedError')
      return 'No se dio permiso para usar la cámara. Actívalo en el navegador o sube un archivo.';
    if (name === 'NotFoundError')
      return 'No se encontró una cámara en este equipo. Sube un archivo.';
    return 'No se pudo abrir la cámara. Sube un archivo.';
  }

  $effect(() => {
    const element = video;
    if (!element) return;
    let stream: MediaStream | null = null;
    let closed = false;
    navigator.mediaDevices
      .getUserMedia({
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 } },
        audio: false
      })
      .then((opened) => {
        if (closed) {
          opened.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = opened;
        element.srcObject = opened;
      })
      .catch((error: unknown) => {
        if (!closed) onunavailable(denied(error));
      });
    return () => {
      closed = true;
      ready = false;
      stream?.getTracks().forEach((track) => track.stop());
      element.srcObject = null;
    };
  });

  function shoot() {
    if (!video || !video.videoWidth) return;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d')?.drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (blob) oncapture(blob);
      },
      'image/jpeg',
      0.95
    );
  }
</script>

<div class="camera">
  <div class="viewfinder">
    <video bind:this={video} autoplay playsinline muted onloadedmetadata={() => (ready = true)}
    ></video>
    <div class="guide" aria-hidden="true"></div>
    <p role="status">
      {ready ? `Encuadra ${label} dentro del marco, sin reflejos.` : 'Abriendo la cámara…'}
    </p>
  </div>
  <div class="controls">
    <button class="back" type="button" onclick={onback}>
      <FleetIcon name="chevronLeft" size={18} />Volver
    </button>
    <button class="shutter" type="button" aria-label="Tomar foto" disabled={!ready} onclick={shoot}
    ></button>
    <span class="balance" aria-hidden="true"></span>
  </div>
</div>

<style>
  .camera {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: #000;
    color: #fff;
  }
  .viewfinder {
    position: relative;
    height: min(62dvh, 560px);
  }
  video {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  /* Proporción real de una licencia: así la tarjeta llena el marco y se lee mejor. */
  .guide {
    position: absolute;
    top: 50%;
    left: 50%;
    width: min(86%, 560px);
    max-height: 76%;
    aspect-ratio: 85.6 / 54;
    transform: translate(-50%, -50%);
    border: 2px solid rgb(255 255 255 / 92%);
    border-radius: var(--driver-radius-lg);
    box-shadow: 0 0 0 100vmax rgb(0 0 0 / 45%);
  }
  p {
    position: absolute;
    right: 0;
    bottom: var(--driver-space-3);
    left: 0;
    margin: 0;
    padding: 0 var(--driver-space-4);
    font-size: 14px;
    text-align: center;
    text-shadow: 0 1px 2px rgb(0 0 0 / 70%);
  }
  .controls {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    padding: var(--driver-space-3) var(--driver-space-4);
  }
  .back {
    display: inline-flex;
    align-items: center;
    justify-self: start;
    gap: var(--driver-space-1);
    min-height: 44px;
    padding: 0 var(--driver-space-2);
    border-radius: var(--driver-radius);
    color: inherit;
    font-size: 14px;
  }
  .shutter {
    width: 68px;
    height: 68px;
    border: 4px solid #fff;
    border-radius: 50%;
    background: rgb(255 255 255 / 92%);
    box-shadow: inset 0 0 0 3px #000;
  }
  .shutter:disabled {
    opacity: 0.4;
  }
  .shutter:active:not(:disabled) {
    background: rgb(255 255 255 / 60%);
  }
  .back:focus-visible,
  .shutter:focus-visible {
    outline: 2px solid #fff;
    outline-offset: 3px;
  }
</style>
