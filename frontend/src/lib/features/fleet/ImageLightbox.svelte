<script lang="ts">
  import { onMount } from 'svelte';
  import FleetIcon from './FleetIcon.svelte';

  let {
    images,
    index = $bindable(0),
    title,
    layer = 100,
    onimageerror,
    onclose
  }: {
    images: { src: string; alt: string }[];
    index?: number;
    title: string;
    layer?: number;
    onimageerror?: () => void;
    onclose: () => void;
  } = $props();

  const MIN_ZOOM = 1;
  const MAX_ZOOM = 4;
  const STEP = 0.5;

  const instructionsId = $props.id();
  let imageLoading = $state(true);
  let imageError = $state(false);
  let imageAttempt = $state(0);
  let zoom = $state(1);
  let pan = $state({ x: 0, y: 0 });
  let drag = $state<{ pointer: number; x: number; y: number } | null>(null);
  let dialog = $state<HTMLDivElement>();
  let stage = $state<HTMLDivElement>();
  let closeButton = $state<HTMLButtonElement>();

  const current = $derived(images[index]);
  const multiple = $derived(images.length > 1);

  $effect(() => {
    void index;
    void current?.src;
    imageLoading = true;
    imageError = false;
    zoom = 1;
    pan = { x: 0, y: 0 };
  });

  function go(delta: number) {
    if (!multiple) return;
    index = (index + delta + images.length) % images.length;
  }

  function setZoom(next: number) {
    zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next));
    if (zoom === 1) pan = { x: 0, y: 0 };
  }

  function onkeydown(event: KeyboardEvent) {
    const actions: Record<string, () => void> = {
      Escape: onclose,
      ArrowLeft: () => (zoom > 1 ? (pan.x += 60) : go(-1)),
      ArrowRight: () => (zoom > 1 ? (pan.x -= 60) : go(1)),
      ArrowUp: () => {
        if (zoom > 1) pan.y += 60;
      },
      ArrowDown: () => {
        if (zoom > 1) pan.y -= 60;
      },
      '+': () => setZoom(zoom + STEP),
      '=': () => setZoom(zoom + STEP),
      '-': () => setZoom(zoom - STEP),
      '0': () => setZoom(1)
    };
    const action = actions[event.key];
    if (action) {
      // Evita que el panel de detalle también reaccione (p. ej. Escape lo cerraría).
      event.preventDefault();
      event.stopPropagation();
      action();
      return;
    }
    if (event.key !== 'Tab' || !dialog) return;
    const focusable = [...dialog.querySelectorAll<HTMLElement>('button:not([disabled])')];
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }

  function onpointerdown(event: PointerEvent) {
    if (zoom === 1) return;
    drag = { pointer: event.pointerId, x: event.clientX - pan.x, y: event.clientY - pan.y };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }

  function onpointermove(event: PointerEvent) {
    if (!drag || drag.pointer !== event.pointerId) return;
    pan = { x: event.clientX - drag.x, y: event.clientY - drag.y };
  }

  function portal(node: HTMLElement) {
    document.body.appendChild(node);
    return { destroy: () => node.remove() };
  }

  onMount(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeButton?.focus();
    // La rueda necesita un listener no pasivo para poder evitar el scroll de la página.
    const onwheel = (event: WheelEvent) => {
      event.preventDefault();
      setZoom(zoom + (event.deltaY < 0 ? STEP : -STEP));
    };
    stage?.addEventListener('wheel', onwheel, { passive: false });
    return () => {
      stage?.removeEventListener('wheel', onwheel);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus?.();
    };
  });
</script>

<div
  use:portal
  bind:this={dialog}
  class="lightbox"
  style:z-index={layer}
  role="dialog"
  aria-modal="true"
  aria-label={title}
  aria-describedby={instructionsId}
  tabindex="-1"
  {onkeydown}
  onclick={(event) => {
    if (event.target === stage && zoom === 1) onclose();
  }}
>
  <header class="toolbar">
    <div class="caption">
      <strong>{title}</strong>
      {#if multiple}<span aria-live="polite">{index + 1} / {images.length}</span>{/if}
    </div>
    <div class="tools">
      <button
        type="button"
        aria-label="Alejar"
        disabled={zoom <= MIN_ZOOM}
        onclick={() => setZoom(zoom - STEP)}><FleetIcon name="zoomOut" size={18} /></button
      >
      <span class="zoom-value">{Math.round(zoom * 100)}%</span>
      <button
        type="button"
        aria-label="Acercar"
        disabled={zoom >= MAX_ZOOM}
        onclick={() => setZoom(zoom + STEP)}><FleetIcon name="zoomIn" size={18} /></button
      >
      <button
        type="button"
        aria-label="Restablecer zoom"
        disabled={zoom === 1}
        onclick={() => setZoom(1)}><FleetIcon name="fit" size={18} /></button
      >
      <span class="divider"></span>
      <button bind:this={closeButton} type="button" aria-label="Cerrar visor" onclick={onclose}
        ><FleetIcon name="close" size={18} /></button
      >
    </div>
  </header>

  <div bind:this={stage} class="stage" class:zoomed={zoom > 1}>
    {#if current}
      {#key `${current.src}:${imageAttempt}`}
        <img
          src={current.src}
          alt={current.alt}
          draggable="false"
          class:failed={imageError}
          onload={() => {
            imageLoading = false;
            imageError = false;
          }}
          onerror={() => {
            imageLoading = false;
            imageError = true;
            onimageerror?.();
          }}
          style:transform="translate({pan.x}px, {pan.y}px) scale({zoom})"
          class:dragging={drag !== null}
          ondblclick={() => setZoom(zoom > 1 ? 1 : 2)}
          {onpointerdown}
          {onpointermove}
          onpointerup={() => (drag = null)}
          onpointercancel={() => (drag = null)}
        />
      {/key}
      {#if imageError}<div class="image-status" role="alert">
          <p>No se pudo cargar la imagen.</p>
          <button
            type="button"
            onclick={() => {
              imageError = false;
              imageLoading = true;
              imageAttempt++;
            }}>Reintentar imagen</button
          >
        </div>
      {:else if imageLoading}<p class="image-status" role="status">Cargando imagen…</p>{/if}
    {/if}
    {#if multiple}
      <button type="button" class="nav prev" aria-label="Imagen anterior" onclick={() => go(-1)}
        ><FleetIcon name="chevronLeft" size={22} /></button
      >
      <button type="button" class="nav next" aria-label="Imagen siguiente" onclick={() => go(1)}
        ><FleetIcon name="chevron" size={22} /></button
      >
    {/if}
  </div>

  {#if multiple}
    <div class="thumbnails">
      {#each images as image, i (image.src)}
        <button
          type="button"
          class:active={i === index}
          aria-label={`Ver imagen ${i + 1}`}
          aria-current={i === index}
          onclick={() => (index = i)}><img src={image.src} alt="" /></button
        >
      {/each}
    </div>
  {/if}
  <p class="viewer-help" id={instructionsId}>
    Con zoom, usa las flechas para mover la imagen. + / − para acercar o alejar. Esc para cerrar.
  </p>
</div>

<style>
  .lightbox {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: grid;
    grid-template-rows: auto 1fr auto auto;
    grid-template-columns: minmax(0, 1fr);
    overflow: hidden;
    background: rgb(9 9 11 / 0.94);
    color: #fafafa;
    animation: fade-in 150ms ease-out;
  }
  .image-status {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    font-size: 13px;
    color: #e4e4e7;
    background: rgb(9 9 11 / 0.85);
  }
  .image-status button {
    min-height: 40px;
    padding: 0 16px;
    border: 1px solid #71717a;
    border-radius: 8px;
  }
  .stage img.failed {
    display: none;
  }
  .viewer-help {
    padding: 8px 16px;
    text-align: center;
    font-size: 11px;
    line-height: 1.5;
    color: #a1a1aa;
  }
  .lightbox:focus {
    outline: none;
  }
  .toolbar {
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 16px;
  }
  .caption {
    flex: 1;
    display: flex;
    align-items: baseline;
    gap: 10px;
    min-width: 0;
    font-size: 13px;
  }
  .caption strong {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 600;
  }
  .caption span {
    color: #a1a1aa;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }
  .tools {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .tools button,
  .nav {
    display: grid;
    place-items: center;
    width: 38px;
    height: 38px;
    border-radius: 50%;
    color: #e4e4e7;
    transition: background 120ms;
  }
  .tools button:hover:not(:disabled),
  .nav:hover {
    background: rgb(255 255 255 / 0.12);
  }
  .tools button:disabled {
    opacity: 0.35;
  }
  button:focus-visible {
    outline: 2px solid #fafafa;
    outline-offset: 2px;
  }
  .zoom-value {
    min-width: 44px;
    text-align: center;
    font-size: 12px;
    color: #a1a1aa;
    font-variant-numeric: tabular-nums;
  }
  .divider {
    width: 1px;
    height: 20px;
    margin: 0 6px;
    background: rgb(255 255 255 / 0.18);
  }
  .stage {
    min-width: 0;
    position: relative;
    display: grid;
    place-items: center;
    overflow: hidden;
    min-height: 0;
    padding: 8px 72px;
    touch-action: none;
  }
  .stage img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    user-select: none;
    transition: transform 160ms ease-out;
    cursor: zoom-in;
  }
  .stage.zoomed img {
    cursor: grab;
  }
  .stage img.dragging {
    cursor: grabbing;
    transition: none;
  }
  .nav {
    position: absolute;
    top: 50%;
    width: 46px;
    height: 46px;
    transform: translateY(-50%);
    background: rgb(255 255 255 / 0.06);
  }
  .prev {
    left: 14px;
  }
  .next {
    right: 14px;
  }
  .thumbnails {
    display: flex;
    justify-content: center;
    gap: 8px;
    overflow-x: auto;
    padding: 10px 16px 16px;
  }
  .thumbnails button {
    flex-shrink: 0;
    width: 64px;
    height: 46px;
    overflow: hidden;
    border: 2px solid transparent;
    border-radius: 6px;
    opacity: 0.55;
    transition: opacity 120ms;
  }
  .thumbnails button:hover,
  .thumbnails button.active {
    opacity: 1;
  }
  .thumbnails button.active {
    border-color: #fafafa;
  }
  .thumbnails img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  @keyframes fade-in {
    from {
      opacity: 0;
    }
  }
  @media (max-width: 640px) {
    .stage {
      padding: 8px 12px;
    }
    .nav {
      top: auto;
      bottom: 12px;
      transform: none;
      background: rgb(0 0 0 / 0.5);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .lightbox,
    .stage img {
      animation: none;
      transition: none;
    }
  }
</style>
