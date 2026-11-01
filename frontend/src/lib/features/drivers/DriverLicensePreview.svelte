<script lang="ts">
  import type { OwnedDocumentsApi } from '$lib/api/owned-documents';
  import ImageLightbox from '$lib/features/fleet/ImageLightbox.svelte';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';

  let { owner, documentId, name }: { owner: OwnedDocumentsApi; documentId: string; name: string } =
    $props();
  let previewState = $state<'loading' | 'image' | 'other' | 'unavailable' | 'error'>('loading');
  let url = $state<string | null>(null);
  let expiresAt = 0;
  let loaded = $state(false);
  let viewerOpen = $state(false);
  let opening = $state(false);
  let attempt = $state(0);
  let retryButton = $state<HTMLButtonElement>();
  function failedImage() {
    const restoreFocus = viewerOpen;
    previewState = 'error';
    viewerOpen = false;
    if (restoreFocus) requestAnimationFrame(() => retryButton?.focus());
  }
  const imageTypes = new Set([
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
    'image/avif',
    'image/svg+xml',
    'image/bmp'
  ]);

  $effect(() => {
    const api = owner;
    const id = documentId;
    void attempt;
    let disposed = false;
    previewState = 'loading';
    url = null;
    loaded = false;
    viewerOpen = false;
    async function load() {
      try {
        const record = await api.get(id);
        if (disposed) return;
        if (record.technical_status !== 'active') {
          previewState = 'unavailable';
          return;
        }
        if (!imageTypes.has(record.content_type.toLowerCase().split(';')[0]!.trim())) {
          previewState = 'other';
          return;
        }
        const signed = await api.previewUrl(id);
        if (disposed) return;
        url = signed.url;
        expiresAt = Date.parse(signed.expires_at);
        previewState = 'image';
      } catch {
        if (!disposed) previewState = 'error';
      }
    }
    void load();
    return () => {
      disposed = true;
    };
  });

  async function openViewer() {
    if (!url || opening || previewState !== 'image') return;
    const api = owner;
    const id = documentId;
    opening = true;
    try {
      if (!Number.isFinite(expiresAt) || expiresAt <= Date.now() + 30000) {
        const fresh = await api.previewUrl(id);
        if (api !== owner || id !== documentId) return;
        url = fresh.url;
        expiresAt = Date.parse(fresh.expires_at);
      }
      viewerOpen = true;
    } catch {
      if (api === owner && id === documentId) previewState = 'error';
    } finally {
      opening = false;
    }
  }
</script>

{#if previewState === 'loading'}
  <div class="preview-state skeleton" role="status"><span>Cargando licencia…</span></div>
{:else if previewState === 'image' && url}
  <button
    class="thumbnail"
    type="button"
    aria-label="Ampliar licencia de conducir"
    aria-busy={!loaded || opening}
    disabled={!loaded || opening}
    onclick={openViewer}
  >
    <img
      src={url}
      alt={`Licencia de conducir de ${name}`}
      width="480"
      height="300"
      loading="lazy"
      decoding="async"
      onload={() => (loaded = true)}
      onerror={failedImage}
    />
    {#if loaded}<span class="expand"><FleetIcon name="zoomIn" size={14} />Ampliar</span>{:else}<span
        class="loading"
        role="status">Cargando imagen…</span
      >{/if}
  </button>
{:else if previewState === 'error'}
  <div class="preview-error" role="status">
    <p>No se pudo mostrar la imagen de la licencia.</p>
    <button bind:this={retryButton} type="button" onclick={() => attempt++}
      >Reintentar vista previa</button
    >
  </div>
{:else if previewState === 'unavailable'}
  <p class="hint">Vista previa no disponible. Consulta el estado en Documentos.</p>
{:else}
  <p class="hint"><FleetIcon name="file" size={16} />Consulta este formato desde Documentos.</p>
{/if}

{#if viewerOpen && url}
  <ImageLightbox
    images={[{ src: url, alt: `Licencia de conducir de ${name}` }]}
    title={`Licencia de conducir · ${name}`}
    layer={1100}
    onimageerror={failedImage}
    onclose={() => (viewerOpen = false)}
  />
{/if}

<style>
  .preview-state,
  .thumbnail {
    margin-top: var(--driver-space-4, 16px);
    width: 100%;
    aspect-ratio: 1.6;
    border-radius: var(--driver-radius, 8px);
  }
  .preview-state {
    display: grid;
    place-items: center;
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  .thumbnail {
    position: relative;
    display: block;
    border: 1px solid rgb(var(--border));
    overflow: hidden;
    background: rgb(var(--surface-muted));
  }
  .thumbnail img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
  .expand {
    position: absolute;
    right: var(--driver-space-2, 8px);
    bottom: var(--driver-space-2, 8px);
    display: flex;
    align-items: center;
    gap: var(--driver-space-1, 4px);
    padding: var(--driver-space-1, 4px) var(--driver-space-2, 8px);
    border: 1px solid rgb(var(--border));
    border-radius: var(--driver-radius-sm, 6px);
    background: rgb(var(--surface) / 0.96);
    color: rgb(var(--foreground));
    font-size: 11px;
  }
  .thumbnail:hover .expand {
    background: rgb(var(--surface-hover));
  }
  .loading {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    background: rgb(var(--surface-muted));
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  .preview-error {
    margin-top: var(--driver-space-3, 12px);
    padding: var(--driver-space-3, 12px);
    border: 1px solid rgb(var(--border));
    border-radius: var(--driver-radius, 8px);
  }
  .preview-error p,
  .hint {
    font-size: 12px;
    line-height: 1.5;
    color: rgb(var(--foreground-muted));
  }
  .preview-error button {
    min-height: 36px;
    margin-top: var(--driver-space-1, 4px);
    font-size: 12px;
    font-weight: 550;
    color: rgb(var(--foreground));
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .hint {
    display: flex;
    align-items: center;
    gap: var(--driver-space-2, 8px);
    margin-top: var(--driver-space-3, 12px);
  }
  button:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 3px;
  }
  @media (prefers-reduced-motion: reduce) {
    .skeleton {
      animation: none;
    }
  }
</style>
