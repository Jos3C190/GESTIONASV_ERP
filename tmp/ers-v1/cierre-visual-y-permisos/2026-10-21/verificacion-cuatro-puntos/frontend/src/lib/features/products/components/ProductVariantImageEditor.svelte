<script lang="ts">
  import ImageUpload from '$lib/components/ui/ImageUpload.svelte';
  import type { ProductVariantImageDraft } from '$lib/types/catalog';

  interface Props {
    image: ProductVariantImageDraft | null | undefined;
    id: string;
    companyId: string;
    editable?: boolean;
    canUpload?: boolean;
    onChange?: (image: ProductVariantImageDraft | null) => void;
  }

  let {
    image = $bindable(),
    id,
    companyId,
    editable = true,
    canUpload = true,
    onChange
  }: Props = $props();
  let previewError = $state(false);

  $effect(() => {
    const snapshot = JSON.stringify(image ?? null);
    if (snapshot !== lastEmittedSnapshot) {
      lastEmittedSnapshot = snapshot;
      onChange?.(image ?? null);
    }
  });

  let lastEmittedSnapshot = '';

  function setSource(sourceType: 'external' | 'cloudinary') {
    if (!editable || (sourceType === 'cloudinary' && !canUpload)) return;
    image =
      image?.source_type === sourceType
        ? image
        : { source_type: sourceType, url: '', media_asset_id: null, alt_text: null };
    previewError = false;
  }

  function remove() {
    if (editable) image = null;
  }
</script>

<div class="space-y-2">
  <div class="flex flex-wrap gap-2" role="group" aria-label="Origen de imagen de variante">
    <button
      type="button"
      class="rounded-md border px-2.5 py-1.5 text-xs {image?.source_type === 'external' || !image
        ? 'border-primary text-primary'
        : 'border-border text-foreground-muted'}"
      onclick={() => setSource('external')}
      disabled={!editable}>URL externa</button
    >
    <button
      type="button"
      class="rounded-md border px-2.5 py-1.5 text-xs {image?.source_type === 'cloudinary'
        ? 'border-primary text-primary'
        : 'border-border text-foreground-muted'}"
      onclick={() => setSource('cloudinary')}
      disabled={!editable || !canUpload}>Archivo Cloudinary</button
    >
    {#if image && editable}<button type="button" class="text-xs text-danger" onclick={remove}
        >Quitar</button
      >{/if}
  </div>
  {#if image?.source_type === 'cloudinary'}
    <ImageUpload
      {id}
      label="Imagen principal"
      purpose="product_image"
      {companyId}
      bind:value={image.url}
      bind:assetId={image.media_asset_id}
      alt={image.alt_text ?? 'Variante'}
      shape="square"
      disabled={!editable || !canUpload}
    />
    {#if image}
      <label class="block text-xs font-medium text-foreground" for={`${id}-alt`}
        >Texto alternativo</label
      >
      <input
        id={`${id}-alt`}
        type="text"
        value={image.alt_text ?? ''}
        disabled={!editable}
        maxlength="160"
        placeholder="Descripción accesible"
        class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground"
        oninput={(event) =>
          (image = {
            ...image!,
            alt_text: (event.currentTarget as HTMLInputElement).value || null
          })}
      />
    {/if}
  {:else if image}
    <div class="mb-2 h-20 w-20 overflow-hidden rounded-lg border border-border bg-surface-muted">
      {#if image.url && !previewError}
        <img
          src={image.url}
          alt={image.alt_text || 'Vista previa de variante'}
          loading="lazy"
          referrerpolicy="no-referrer"
          class="h-full w-full object-cover"
          onerror={() => (previewError = true)}
        />
      {:else}
        <div
          class="flex h-full items-center justify-center px-1 text-center text-[10px] text-foreground-subtle"
        >
          {previewError ? 'No se pudo cargar' : 'Vista previa'}
        </div>
      {/if}
    </div>
    <label class="block text-xs font-medium text-foreground" for={`${id}-url`}>URL HTTPS</label>
    <input
      id={`${id}-url`}
      type="url"
      value={image.url}
      disabled={!editable}
      placeholder="https://..."
      class="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground"
      oninput={(event) => {
        previewError = false;
        image = { ...image!, url: (event.currentTarget as HTMLInputElement).value };
      }}
    />
    <label class="block text-xs font-medium text-foreground" for={`${id}-alt`}
      >Texto alternativo</label
    >
    <input
      id={`${id}-alt`}
      type="text"
      value={image.alt_text ?? ''}
      disabled={!editable}
      maxlength="160"
      placeholder="Texto alternativo"
      class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground"
      oninput={(event) =>
        (image = { ...image!, alt_text: (event.currentTarget as HTMLInputElement).value || null })}
    />
  {/if}
</div>
