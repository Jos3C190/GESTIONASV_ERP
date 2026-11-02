<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';

  let {
    label,
    oncapture,
    onunavailable
  }: {
    label: string;
    oncapture: (photo: Blob) => void;
    onunavailable: (reason: string) => void;
  } = $props();

  let video = $state<HTMLVideoElement | null>(null);
  let ready = $state(false);

  function denied(error: unknown): string {
    const name = error instanceof DOMException ? error.name : '';
    if (name === 'NotAllowedError') return 'No se dio permiso para usar la cámara.';
    if (name === 'NotFoundError') return 'No se encontró una cámara en este equipo.';
    return 'No se pudo abrir la cámara.';
  }

  $effect(() => {
    const element = video;
    if (!element) return;
    let stream: MediaStream | null = null;
    let closed = false;
    if (!navigator.mediaDevices?.getUserMedia) {
      onunavailable('La cámara en vivo requiere una conexión segura (HTTPS).');
      return;
    }
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
  <video bind:this={video} autoplay playsinline muted onloadedmetadata={() => (ready = true)}
  ></video>
  <div class="guide" aria-hidden="true"></div>
  <p>Encuadra {label} dentro del marco, sin reflejos.</p>
</div>
<div class="actions">
  <Button onclick={shoot} disabled={!ready}>Tomar foto</Button>
</div>

<style>
  .camera {
    position: relative;
    overflow: hidden;
    aspect-ratio: 4 / 3;
    max-height: 60dvh;
    width: 100%;
    border-radius: 12px;
    background: #000;
  }
  video {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .guide {
    position: absolute;
    inset: 12% 7%;
    border: 2px solid rgb(255 255 255 / 90%);
    border-radius: 14px;
    box-shadow: 0 0 0 100vmax rgb(0 0 0 / 38%);
  }
  p {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 8px;
    margin: 0;
    padding: 0 12px;
    color: #fff;
    font-size: 13px;
    text-align: center;
  }
  .actions {
    display: flex;
    justify-content: center;
    margin-top: 12px;
  }
</style>
