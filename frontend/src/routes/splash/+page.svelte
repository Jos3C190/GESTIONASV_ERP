<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { session } from '$lib/stores/session.svelte';

  let videoEl = $state<HTMLVideoElement | null>(null);
  let visible = $state(true);

  /**
   * Navega al selector de empresas con un fade-out suave.
   * Si por algún motivo se llama más de una vez, el guard `visible` lo previene.
   */
  function navigateAway() {
    if (!visible) return;
    visible = false;
    setTimeout(() => {
      goto('/companies', { replaceState: true });
    }, 400);
  }

  onMount(() => {
    if (!session.isAuthenticated) {
      goto('/login', { replaceState: true });
      return;
    }

    // Fallback de seguridad: si el video no carga o tarda demasiado,
    // navegamos después de 8 segundos.
    const fallbackTimer = setTimeout(navigateAway, 8000);

    return () => clearTimeout(fallbackTimer);
  });
</script>

<svelte:head>
  <title>Cargando — GestionaSV</title>
</svelte:head>

<div
  class="splash-root"
  class:splash-fade-out={!visible}
  role="status"
  aria-label="Cargando aplicación"
>
  <!-- svelte-ignore a11y_media_has_caption -->
  <video
    bind:this={videoEl}
    class="splash-video"
    src="/splash-logo.mp4"
    autoplay
    muted
    playsinline
    disablepictureinpicture
    onended={navigateAway}
    onerror={navigateAway}
  ></video>
</div>

<style>
  .splash-root {
    position: fixed;
    inset: 0;
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: #000;
    opacity: 1;
    transition: opacity 0.4s ease-out;
  }

  .splash-fade-out {
    opacity: 0;
    pointer-events: none;
  }

  .splash-video {
    display: block;
    max-width: 28vw;
    max-height: 28vh;
    width: auto;
    height: auto;
    object-fit: contain;

    /* Ocultar controles nativos completamente */
    pointer-events: none;
    user-select: none;
    -webkit-user-select: none;
  }

  /* Ocultar la barra de controles en navegadores WebKit/Blink */
  .splash-video::-webkit-media-controls {
    display: none !important;
  }
  .splash-video::-webkit-media-controls-enclosure {
    display: none !important;
  }
  .splash-video::-webkit-media-controls-panel {
    display: none !important;
  }
</style>
