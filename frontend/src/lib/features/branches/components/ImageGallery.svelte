<script lang="ts">
  /**
   * ImageGallery — galería de imágenes con controles (estilo Vercel/Geist).
   * Imagen principal grande + flechas laterales + contador + thumbnails.
   * Soporte de teclado: ← → para navegar, Esc para cerrar lightbox.
   */

  import type { BranchImage } from '$lib/features/branches/mock-data';

  interface Props {
    images: BranchImage[];
  }

  let { images }: Props = $props();

  let activeIndex = $state(0);
  let lightboxOpen = $state(false);

  let active = $derived(images[activeIndex]);
  let count = $derived(images.length);

  function next() {
    activeIndex = (activeIndex + 1) % count;
  }

  function prev() {
    activeIndex = (activeIndex - 1 + count) % count;
  }

  function select(i: number) {
    activeIndex = i;
  }

  function openLightbox() {
    lightboxOpen = true;
  }

  function closeLightbox() {
    lightboxOpen = false;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (lightboxOpen) {
      if (e.key === 'Escape') { e.preventDefault(); closeLightbox(); return; }
      if (e.key === 'ArrowRight') { e.preventDefault(); next(); return; }
      if (e.key === 'ArrowLeft') { e.preventDefault(); prev(); return; }
    } else {
      if (e.key === 'ArrowRight') { e.preventDefault(); next(); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); prev(); }
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if count > 0 && active}
  <div class="space-y-3">
    <!-- Imagen principal -->
    <div class="relative group aspect-[16/10] overflow-hidden rounded-2xl border border-border bg-surface-muted shadow-soft">
      <img
        src={active.url}
        alt={active.caption}
        class="h-full w-full object-cover transition-all duration-500 {lightboxOpen ? '' : 'group-hover:scale-[1.02]'} cursor-zoom-in"
        loading="lazy"
        onclick={openLightbox}
        role="button"
        tabindex="0"
        onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openLightbox(); } }}
      />

      <!-- Gradiente inferior con caption -->
      <div class="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/70 via-black/30 to-transparent"></div>
      <div class="absolute bottom-0 inset-x-0 flex items-end justify-between gap-3 p-4">
        <p class="text-sm font-medium text-white drop-shadow-sm">{active.caption}</p>
        {#if count > 1}
          <button
            type="button"
            onclick={openLightbox}
            class="pointer-events-auto flex h-7 w-7 flex-none items-center justify-center rounded-lg bg-white/15 text-white backdrop-blur-md transition-colors hover:bg-white/25"
            aria-label="Ver imagen en pantalla completa"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>
          </button>
        {/if}
      </div>

      <!-- Contador de imágenes -->
      <div class="absolute top-3 right-3 flex items-center gap-1.5 rounded-lg bg-black/50 px-2.5 py-1 text-xs font-mono font-medium text-white backdrop-blur-md">
        {#if count > 1}
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>
        {/if}
        {activeIndex + 1} / {count}
      </div>

      <!-- Flechas de navegación -->
      {#if count > 1}
        <button
          type="button"
          onclick={prev}
          class="absolute left-3 top-1/2 -translate-y-1/2 flex h-9 w-9 items-center justify-center rounded-xl bg-black/50 text-white backdrop-blur-md transition-all hover:bg-black/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50 opacity-0 group-hover:opacity-100"
          aria-label="Imagen anterior"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
        </button>
        <button
          type="button"
          onclick={next}
          class="absolute right-3 top-1/2 -translate-y-1/2 flex h-9 w-9 items-center justify-center rounded-xl bg-black/50 text-white backdrop-blur-md transition-all hover:bg-black/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50 opacity-0 group-hover:opacity-100"
          aria-label="Imagen siguiente"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
      {/if}
    </div>

    <!-- Thumbnails -->
    {#if count > 1}
      <div class="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Seleccionar imagen">
        {#each images as img, i (img.url)}
          <button
            type="button"
            onclick={() => select(i)}
            class="relative flex-none overflow-hidden rounded-lg border-2 transition-all {i === activeIndex ? 'border-primary ring-1 ring-primary/30' : 'border-border hover:border-border-strong'} aspect-[4/3] w-20 sm:w-24"
            role="tab"
            aria-selected={i === activeIndex}
            aria-label={img.caption}
          >
            <img src={img.url} alt={img.caption} class="h-full w-full object-cover" loading="lazy" />
            {#if i === activeIndex}
              <div class="absolute inset-0 bg-primary/10"></div>
            {/if}
          </button>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<!-- Lightbox (pantalla completa) -->
{#if lightboxOpen && active}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm"
    role="dialog"
    aria-modal="true"
    aria-label="Visor de imágenes"
    onclick={closeLightbox}
    onkeydown={(e) => { if (e.key === 'Escape') { e.preventDefault(); closeLightbox(); } }}
    tabindex="-1"
  >
    <button
      type="button"
      onclick={closeLightbox}
      class="absolute top-4 right-4 flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-white transition-colors hover:bg-white/20 z-10"
      aria-label="Cerrar"
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
    </button>

    <img
      src={active.url}
      alt={active.caption}
      class="max-h-[85vh] max-w-[90vw] rounded-xl object-contain shadow-floating"
      onclick={(e) => e.stopPropagation()}
    />

    {#if count > 1}
      <button
        type="button"
        onclick={(e) => { e.stopPropagation(); prev(); }}
        class="absolute left-4 top-1/2 -translate-y-1/2 flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 text-white transition-colors hover:bg-white/20"
        aria-label="Imagen anterior"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      </button>
      <button
        type="button"
        onclick={(e) => { e.stopPropagation(); next(); }}
        class="absolute right-4 top-1/2 -translate-y-1/2 flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 text-white transition-colors hover:bg-white/20"
        aria-label="Imagen siguiente"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
      </button>
    {/if}

    <div class="absolute bottom-0 inset-x-0 p-6 bg-gradient-to-t from-black/80 to-transparent">
      <p class="text-center text-sm font-medium text-white">{active.caption} — {activeIndex + 1}/{count}</p>
    </div>
  </div>
{/if}