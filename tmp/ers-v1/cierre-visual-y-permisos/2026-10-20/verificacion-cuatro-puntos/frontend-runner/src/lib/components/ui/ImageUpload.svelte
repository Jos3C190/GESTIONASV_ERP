<script lang="ts">
  import { api, HttpError, type MediaPurpose } from '$lib/api/client';
  import { confirmation } from '$lib/stores/confirmation.svelte';

  interface Props {
    id: string;
    label: string;
    purpose: MediaPurpose;
    companyId?: string | null;
    value: string;
    publicId?: string;
    assetId?: string | null;
    alt?: string;
    shape?: 'square' | 'wide';
    disabled?: boolean;
  }

  let {
    id,
    label,
    purpose,
    companyId = null,
    value = $bindable(),
    publicId = $bindable(''),
    assetId = $bindable(''),
    alt = '',
    shape = 'square',
    disabled = false
  }: Props = $props();
  let uploading = $state(false);
  let progress = $state(0);
  let error = $state<string | null>(null);
  let dragActive = $state(false);

  async function upload(file?: File) {
    if (!file || disabled || uploading) return;
    error = null;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      error = 'Use una imagen JPG, PNG o WebP.';
      return;
    }
    uploading = true;
    progress = 25;
    try {
      const result = await api.media.uploadImage(file, purpose, companyId);
      progress = 100;
      value = result.url;
      publicId = result.publicId;
      assetId = result.assetId;
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar la imagen.';
      progress = 0;
    } finally {
      uploading = false;
    }
  }

  function onFileChange(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    void upload(input.files?.[0]);
    input.value = '';
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    dragActive = false;
    void upload(event.dataTransfer?.files?.[0]);
  }

  function requestRemove() {
    confirmation.request({
      kind: 'delete',
      title: 'Quitar imagen',
      description:
        'La imagen se quitará del formulario. El cambio permanente se aplicará cuando guarde el registro.',
      resourceName: label,
      confirmLabel: 'Quitar imagen',
      execute: () => {
        value = '';
        publicId = '';
        assetId = '';
      }
    });
  }
</script>

<div class="space-y-2">
  <label for={id} class="block text-sm font-medium text-foreground">{label}</label>
  <div class="flex items-center gap-4">
    <div
      class="relative flex-none overflow-hidden border border-border bg-surface-muted {shape ===
      'square'
        ? 'h-24 w-24 rounded-2xl'
        : 'h-24 w-40 rounded-xl'}"
    >
      {#if value}
        <img src={value} {alt} class="h-full w-full object-cover" />
      {:else}
        <div
          class="flex h-full items-center justify-center text-foreground-subtle"
          aria-hidden="true"
        >
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            ><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="9" cy="9" r="2" /><path
              d="m21 15-5-5L5 21"
            /></svg
          >
        </div>
      {/if}
      {#if uploading}<div
          class="absolute inset-0 flex items-center justify-center bg-black/55 text-xs font-semibold text-white"
        >
          {progress}%
        </div>{/if}
    </div>
    <div
      role="group"
      aria-label={`Carga de ${label}`}
      class="min-w-0 flex-1 rounded-xl border border-dashed p-4 text-center transition-colors {dragActive
        ? 'border-primary bg-primary/5'
        : 'border-border hover:border-border-strong'}"
      ondragover={(event) => {
        event.preventDefault();
        dragActive = true;
      }}
      ondragleave={() => (dragActive = false)}
      ondrop={onDrop}
    >
      <input
        {id}
        class="sr-only"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onchange={onFileChange}
        {disabled}
      />
      <label for={id} class="cursor-pointer text-sm font-medium text-primary"
        >{value ? 'Reemplazar imagen' : 'Seleccionar imagen'}</label
      >
      <p class="mt-1 text-xs text-foreground-subtle">JPG, PNG o WebP · máximo 10 MB</p>
      {#if value}<button
          type="button"
          class="mt-2 text-xs text-danger hover:underline"
          onclick={requestRemove}>Quitar</button
        >{/if}
    </div>
  </div>
  {#if error}<p class="text-xs text-danger" role="alert">{error}</p>{/if}
</div>
