<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import ImageUpload from '$lib/components/ui/ImageUpload.svelte';
  import type { WarehouseImage } from '../types';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  interface Props {
    images: WarehouseImage[];
    companyId: string;
  }
  let { images = $bindable(), companyId }: Props = $props();
  function add() {
    if (images.length < 20) images = [...images, { url: '', caption: '', public_id: '' }];
  }
  function remove(index: number) {
    images = images.filter((_, i) => i !== index);
  }
  function requestRemove(index: number) {
    const image = images[index];
    if (!image?.url) {
      remove(index);
      return;
    }
    confirmation.request({
      kind: 'delete',
      title: 'Quitar imagen del almacén',
      description: 'La imagen se marcará para eliminarse cuando guarde los cambios del almacén.',
      resourceName: image.caption || (index === 0 ? 'Portada' : `Imagen ${index + 1}`),
      confirmLabel: 'Quitar imagen',
      execute: () => remove(index)
    });
  }
  function move(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= images.length) return;
    const next = [...images];
    [next[index], next[target]] = [next[target]!, next[index]!];
    images = next;
  }
</script>

<section class="space-y-3 rounded-xl border border-border bg-surface-muted/30 p-4">
  <div class="flex items-start justify-between gap-3">
    <div>
      <h3 class="text-sm font-semibold text-foreground">Galería del almacén</h3>
      <p class="mt-1 text-xs text-foreground-muted">La primera imagen se utiliza como portada.</p>
    </div>
    <Button size="sm" variant="secondary" onclick={add} disabled={images.length >= 20}
      >Agregar</Button
    >
  </div>
  {#if images.length === 0}<div
      class="rounded-xl border border-dashed border-border p-6 text-center text-xs text-foreground-muted"
    >
      No hay imágenes registradas.
    </div>{/if}
  {#each images as image, index (index)}<div
      class="rounded-xl border border-border bg-surface-elevated p-3"
    >
      <ImageUpload
        id={`warehouse-image-${index}`}
        label={index === 0 ? 'Portada' : `Imagen ${index + 1}`}
        purpose="warehouse_image"
        {companyId}
        bind:value={image.url}
        bind:publicId={image.public_id}
        alt={image.caption || 'Almacén'}
        shape="wide"
      />
      <label
        for={`warehouse-caption-${index}`}
        class="mt-3 block text-xs font-medium text-foreground">Descripción accesible</label
      ><input
        id={`warehouse-caption-${index}`}
        bind:value={image.caption}
        maxlength="160"
        placeholder="Ej. Entrada principal"
        class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      />
      <div class="mt-3 flex justify-end gap-2">
        <button
          type="button"
          class="text-xs text-foreground-muted disabled:opacity-40"
          disabled={index === 0}
          onclick={() => move(index, -1)}>Mover arriba</button
        ><button
          type="button"
          class="text-xs text-foreground-muted disabled:opacity-40"
          disabled={index === images.length - 1}
          onclick={() => move(index, 1)}>Mover abajo</button
        ><button type="button" class="text-xs text-danger" onclick={() => requestRemove(index)}
          >Eliminar</button
        >
      </div>
    </div>{/each}
</section>
