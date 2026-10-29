<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import ImageUpload from '$lib/components/ui/ImageUpload.svelte';
  import type { MediaPurpose } from '$lib/api/client';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import type { SupplierImageDraft } from '$lib/types/supplier';

  interface Props {
    image: SupplierImageDraft | null;
    companyId: string;
    purpose: Extract<MediaPurpose, 'supplier_logo' | 'supplier_contact_avatar'>;
    label: string;
    emptyLabel: string;
    altFallback: string;
    editable?: boolean;
    canUpload?: boolean;
  }

  let {
    image = $bindable(),
    companyId,
    purpose,
    label,
    emptyLabel,
    altFallback,
    editable = true,
    canUpload = true
  }: Props = $props();

  let previewError = $state(false);

  function add(sourceType: 'cloudinary' | 'external') {
    if (!editable || (sourceType === 'cloudinary' && !canUpload)) return;
    image = {
      source_type: sourceType,
      url: '',
      media_asset_id: null,
      alt_text: altFallback
    };
    previewError = false;
  }

  function switchSource(sourceType: 'cloudinary' | 'external') {
    if (!image || !editable || (sourceType === 'cloudinary' && !canUpload)) return;
    image = {
      ...image,
      source_type: sourceType,
      url: '',
      media_asset_id: null
    };
    previewError = false;
  }

  function remove() {
    if (!editable || !image) return;
    if (!image.url) {
      image = null;
      return;
    }
    confirmation.request({
      kind: 'delete',
      title: `Quitar ${label.toLowerCase()}`,
      description: 'La imagen se quitará al guardar los cambios.',
      resourceName: label,
      confirmLabel: 'Quitar imagen',
      execute: () => {
        image = null;
      }
    });
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

  function updateUrl(value: string) {
    if (!image) return;
    image = { ...image, url: value };
    previewError = false;
  }

  function updateAlt(value: string) {
    if (!image) return;
    image = { ...image, alt_text: value };
  }
</script>

<section class="space-y-3 rounded-xl border border-border bg-surface-muted/30 p-4" aria-label={label}>
  <div class="flex items-start justify-between gap-3">
    <div>
      <h3 class="text-sm font-semibold text-foreground">{label}</h3>
      <p class="mt-1 text-xs text-foreground-muted">{emptyLabel}</p>
    </div>
    {#if editable && !image}
      <div class="flex flex-wrap justify-end gap-2">
        <Button size="sm" variant="secondary" onclick={() => add('external')}>Usar URL</Button>
        <Button size="sm" variant="secondary" onclick={() => add('cloudinary')} disabled={!canUpload}
          >Subir archivo</Button
        >
      </div>
    {/if}
  </div>

  {#if !image}
    <div class="rounded-xl border border-dashed border-border p-5 text-center text-xs text-foreground-muted">
      No hay imagen registrada.
      {#if editable && !canUpload}<span class="block mt-1">Puede agregar una URL HTTPS externa.</span>{/if}
    </div>
  {:else}
    <div class="flex flex-wrap gap-2" role="group" aria-label="Origen de imagen">
      <button
        type="button"
        class="rounded-md border px-2.5 py-1.5 text-xs {image.source_type === 'external'
          ? 'border-primary text-primary'
          : 'border-border text-foreground-muted'}"
        onclick={() => switchSource('external')}
        disabled={!editable}
      >URL externa</button>
      <button
        type="button"
        class="rounded-md border px-2.5 py-1.5 text-xs {image.source_type === 'cloudinary'
          ? 'border-primary text-primary'
          : 'border-border text-foreground-muted'}"
        onclick={() => switchSource('cloudinary')}
        disabled={!editable || !canUpload}
      >Archivo Cloudinary</button>
    </div>

    {#if image.source_type === 'cloudinary'}
      <ImageUpload
        id={`single-image-${purpose}`}
        {label}
        {purpose}
        {companyId}
        bind:value={image.url}
        bind:assetId={image.media_asset_id}
        alt={image.alt_text || altFallback}
        shape="wide"
        disabled={!editable || !canUpload}
      />
    {:else}
      <div class="grid gap-3 md:grid-cols-[10rem_1fr] md:items-start">
        <div class="h-24 overflow-hidden rounded-xl border border-border bg-surface-muted">
          {#if image.url && !previewError}
            <img
              src={image.url}
              alt={image.alt_text || altFallback}
              class="h-full w-full object-cover"
              loading="lazy"
              referrerpolicy="no-referrer"
              onerror={() => (previewError = true)}
            />
          {:else}
            <div class="flex h-full items-center justify-center px-2 text-center text-[11px] text-foreground-subtle">
              {previewError ? 'No se pudo cargar la vista previa' : 'Vista previa'}
            </div>
          {/if}
        </div>
        <div>
          <label for={`single-image-url-${purpose}`} class="block text-xs font-medium text-foreground"
            >URL HTTPS</label
          >
          <input
            id={`single-image-url-${purpose}`}
            type="url"
            value={image.url}
            disabled={!editable}
            placeholder="https://..."
            class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
            oninput={(event) => updateUrl((event.currentTarget as HTMLInputElement).value)}
          />
          {#if image.url && !isExternalUrlValid(image.url)}
            <p class="mt-1 text-xs text-danger" role="alert">Use una URL HTTPS válida sin credenciales.</p>
          {/if}
        </div>
      </div>
    {/if}

    <div>
      <label for={`single-image-alt-${purpose}`} class="block text-xs font-medium text-foreground"
        >Texto alternativo</label
      >
      <input
        id={`single-image-alt-${purpose}`}
        type="text"
        value={image.alt_text ?? ''}
        maxlength="160"
        disabled={!editable}
        placeholder={altFallback}
        class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
        oninput={(event) => updateAlt((event.currentTarget as HTMLInputElement).value)}
      />
    </div>

    {#if editable}
      <div class="flex justify-end border-t border-border pt-2">
        <button type="button" class="text-xs text-danger hover:underline" onclick={remove}>Eliminar imagen</button>
      </div>
    {/if}
  {/if}
</section>
