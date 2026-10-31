<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import ImageUpload from '$lib/components/ui/ImageUpload.svelte';
  import type { ProductImageDraft } from '$lib/types/catalog';

  interface Props {
    images: ProductImageDraft[];
    companyId: string;
    editable?: boolean;
    canUpload?: boolean;
  }

  let { images = $bindable(), companyId, editable = true, canUpload = true }: Props = $props();
  let previewErrors = $state<Record<number, boolean>>({});

  function add(source_type: 'cloudinary' | 'external' = 'external') {
    if (!editable || images.length >= 20 || (source_type === 'cloudinary' && !canUpload)) return;
    images = [
      ...images,
      {
        source_type,
        url: '',
        media_asset_id: null,
        alt_text: '',
        position: images.length,
        is_cover: images.length === 0
      }
    ];
  }

  function remove(index: number) {
    if (!editable) return;
    const next = images.filter((_, itemIndex) => itemIndex !== index);
    images = normalize(next);
  }

  function changeSource(index: number, source_type: 'cloudinary' | 'external') {
    if (!editable || (source_type === 'cloudinary' && !canUpload)) return;
    const next = [...images];
    const image = next[index];
    if (!image) return;
    next[index] = {
      ...image,
      source_type,
      url: '',
      media_asset_id: null,
      is_cover: index === 0 && images.length === 1 ? image.is_cover : false
    };
    images = next;
  }

  function move(index: number, direction: -1 | 1) {
    if (!editable) return;
    const target = index + direction;
    if (target < 0 || target >= images.length) return;
    const next = [...images];
    [next[index], next[target]] = [next[target]!, next[index]!];
    images = normalize(next);
  }

  function makeCover(index: number) {
    if (!editable) return;
    images = images.map((image, imageIndex) => ({ ...image, is_cover: imageIndex === index }));
  }

  function normalize(next: ProductImageDraft[]): ProductImageDraft[] {
    const hasCover = next.some((image) => image.is_cover);
    return next.map((image, position) => ({
      ...image,
      position,
      is_cover: hasCover ? image.is_cover : position === 0
    }));
  }

  function updateImage(index: number, changes: Partial<ProductImageDraft>) {
    if (!editable) return;
    images = images.map((image, imageIndex) =>
      imageIndex === index ? { ...image, ...changes } : image
    );
  }

  function isExternalUrlValid(url: string): boolean {
    if (!url.trim()) return false;
    try {
      const parsed = new URL(url.trim());
      return parsed.protocol === 'https:' && !parsed.username && !parsed.password;
    } catch {
      return false;
    }
  }
</script>

<section
  class="space-y-3 rounded-xl border border-border bg-surface-muted/30 p-4"
  aria-labelledby="product-gallery-title"
>
  <div class="flex items-start justify-between gap-3">
    <div>
      <h3 id="product-gallery-title" class="text-sm font-semibold text-foreground">
        Galería del producto
      </h3>
      <p class="mt-1 text-xs text-foreground-muted">
        La portada aparece en el listado. Puede ordenar hasta 20 imágenes.
      </p>
    </div>
    {#if editable}
      <div class="flex gap-2">
        <Button
          size="sm"
          variant="secondary"
          onclick={() => add('external')}
          disabled={images.length >= 20}>Agregar URL</Button
        >
        <Button
          size="sm"
          variant="secondary"
          onclick={() => add('cloudinary')}
          disabled={images.length >= 20 || !canUpload}>Subir archivo</Button
        >
      </div>
    {/if}
  </div>

  {#if images.length === 0}
    <div
      class="rounded-xl border border-dashed border-border p-6 text-center text-xs text-foreground-muted"
    >
      No hay imágenes registradas.
    </div>
  {/if}

  {#each images as image, index (image.id ?? `new-${index}`)}
    <article class="rounded-xl border border-border bg-surface-elevated p-3">
      <div class="mb-3 flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <span class="text-xs font-semibold text-foreground">Imagen {index + 1}</span>
          {#if image.is_cover}
            <span class="badge-success rounded-md px-2 py-0.5 text-[11px] font-medium">Portada</span
            >
          {/if}
        </div>
        {#if editable}
          <button
            type="button"
            class="text-xs text-danger hover:underline"
            onclick={() => remove(index)}>Eliminar</button
          >
        {/if}
      </div>

      <div class="mb-3 flex gap-2" role="group" aria-label={`Origen de imagen ${index + 1}`}>
        <button
          type="button"
          class="rounded-md border px-2.5 py-1.5 text-xs {image.source_type === 'external'
            ? 'border-primary text-primary'
            : 'border-border text-foreground-muted'}"
          onclick={() => changeSource(index, 'external')}
          disabled={!editable}>URL externa</button
        >
        <button
          type="button"
          class="rounded-md border px-2.5 py-1.5 text-xs {image.source_type === 'cloudinary'
            ? 'border-primary text-primary'
            : 'border-border text-foreground-muted'}"
          onclick={() => changeSource(index, 'cloudinary')}
          disabled={!editable || !canUpload}>Archivo Cloudinary</button
        >
      </div>

      {#if image.source_type === 'cloudinary'}
        <ImageUpload
          id={`product-image-${index}`}
          label={image.is_cover ? 'Portada' : `Imagen ${index + 1}`}
          purpose="product_image"
          {companyId}
          bind:value={image.url}
          bind:assetId={image.media_asset_id}
          alt={image.alt_text ?? 'Producto'}
          shape="wide"
          disabled={!editable || !canUpload}
        />
      {:else}
        <div class="grid gap-2 md:grid-cols-[9rem_1fr] md:items-start">
          <div class="h-24 overflow-hidden rounded-xl border border-border bg-surface-muted">
            {#if image.url && !previewErrors[index]}
              <img
                src={image.url}
                alt={image.alt_text || 'Vista previa del producto'}
                class="h-full w-full object-cover"
                loading="lazy"
                referrerpolicy="no-referrer"
                onerror={() => (previewErrors[index] = true)}
              />
            {:else}
              <div
                class="flex h-full items-center justify-center px-2 text-center text-[11px] text-foreground-subtle"
              >
                {previewErrors[index] ? 'No se pudo cargar la vista previa' : 'Vista previa'}
              </div>
            {/if}
          </div>
          <div>
            <label
              for={`product-image-url-${index}`}
              class="block text-xs font-medium text-foreground">URL HTTPS</label
            >
            <input
              id={`product-image-url-${index}`}
              type="url"
              value={image.url}
              disabled={!editable}
              placeholder="https://..."
              class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
              oninput={(event) => {
                updateImage(index, { url: (event.currentTarget as HTMLInputElement).value });
                previewErrors[index] = false;
              }}
            />
            {#if image.url && !isExternalUrlValid(image.url)}
              <p class="mt-1 text-xs text-danger" role="alert">
                Use una URL HTTPS válida sin credenciales.
              </p>
            {/if}
          </div>
        </div>
      {/if}

      <label
        for={`product-image-alt-${index}`}
        class="mt-3 block text-xs font-medium text-foreground">Texto alternativo</label
      >
      <input
        id={`product-image-alt-${index}`}
        type="text"
        value={image.alt_text ?? ''}
        maxlength="160"
        disabled={!editable}
        placeholder="Ej. Presentación frontal del producto"
        class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
        oninput={(event) =>
          updateImage(index, { alt_text: (event.currentTarget as HTMLInputElement).value })}
      />

      {#if editable}
        <div class="mt-3 flex flex-wrap justify-end gap-3 text-xs">
          <button
            type="button"
            class="text-foreground-muted hover:text-foreground disabled:opacity-40"
            disabled={index === 0}
            onclick={() => move(index, -1)}>Mover arriba</button
          >
          <button
            type="button"
            class="text-foreground-muted hover:text-foreground disabled:opacity-40"
            disabled={index === images.length - 1}
            onclick={() => move(index, 1)}>Mover abajo</button
          >
          <button
            type="button"
            class="text-primary hover:underline"
            onclick={() => makeCover(index)}>Usar como portada</button
          >
        </div>
      {/if}
    </article>
  {/each}

  <p class="text-right text-[11px] text-foreground-subtle">{images.length}/20 imágenes</p>
</section>
