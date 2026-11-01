<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import ImageUpload from '$lib/components/ui/ImageUpload.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { fleetApi, type VehiclePhoto } from './api';
  import FleetIcon from './FleetIcon.svelte';
  import ImageLightbox from './ImageLightbox.svelte';

  let { vehicleId, title, canManage }: { vehicleId: string; title: string; canManage: boolean } =
    $props();

  let photos = $state<VehiclePhoto[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let uploadUrl = $state('');
  let viewerIndex = $state<number | null>(null);

  async function load() {
    loading = true;
    error = null;
    try {
      photos = await fleetApi.photos(vehicleId);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar la galería.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void vehicleId;
    void load();
  });

  // ImageUpload firma y sube a Cloudinary; aquí se vincula la imagen al vehículo.
  $effect(() => {
    const url = uploadUrl;
    if (!url) return;
    uploadUrl = '';
    fleetApi
      .addPhoto(vehicleId, url)
      .then((photo) => (photos = [...photos, photo]))
      .catch((err) => {
        error = err instanceof HttpError ? err.message : 'No se pudo agregar la foto.';
      });
  });

  function remove(photo: VehiclePhoto) {
    confirmation.request({
      kind: 'delete',
      title: 'Quitar foto de la galería',
      description: 'La foto dejará de mostrarse en la ficha del vehículo.',
      resourceName: photo.caption ?? 'Foto del vehículo',
      confirmLabel: 'Quitar foto',
      requireReason: false,
      execute: async () => {
        await fleetApi.deletePhoto(vehicleId, photo.id);
        photos = photos.filter((item) => item.id !== photo.id);
      }
    });
  }
</script>

<section class="gallery">
  <header>
    <div>
      <h3>Galería</h3>
      <p>Fotos reales de la unidad. La portada se mantiene con el modelo base y tu marca.</p>
    </div>
  </header>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if canManage}
    <div class="uploader">
      <ImageUpload
        id={`vehicle-photo-${vehicleId}`}
        label="Agregar foto"
        purpose="vehicle_image"
        companyId={company.id}
        bind:value={uploadUrl}
        shape="wide"
      />
    </div>
  {/if}
  {#if loading}
    <p class="muted">Cargando fotos…</p>
  {:else if photos.length === 0}
    <p class="muted">Aún no hay fotos de esta unidad.</p>
  {:else}
    <ul class="grid" aria-label="Fotos del vehículo">
      {#each photos as photo, index (photo.id)}
        <li>
          <button
            type="button"
            class="thumb"
            aria-label={`Ampliar foto ${index + 1}`}
            onclick={() => (viewerIndex = index)}><img src={photo.url} alt="" /></button
          >
          {#if canManage}
            <button
              type="button"
              class="remove"
              aria-label={`Quitar foto ${index + 1}`}
              onclick={() => remove(photo)}><FleetIcon name="trash" size={13} /></button
            >
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

{#if viewerIndex !== null && photos.length}
  <ImageLightbox
    images={photos.map((photo, index) => ({
      src: photo.url,
      alt: `${title}, foto ${index + 1} de ${photos.length}`
    }))}
    bind:index={viewerIndex}
    {title}
    onclose={() => (viewerIndex = null)}
  />
{/if}

<style>
  .gallery {
    display: grid;
    gap: 14px;
  }
  h3 {
    font-size: 14px;
    font-weight: 600;
  }
  header p,
  .muted {
    margin-top: 4px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .uploader {
    max-width: 360px;
  }
  .error {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 10px;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  li {
    position: relative;
  }
  .thumb {
    display: block;
    width: 100%;
    aspect-ratio: 4 / 3;
    overflow: hidden;
    border: 1px solid rgb(var(--border));
    border-radius: 10px;
    cursor: zoom-in;
  }
  .thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 200ms;
  }
  .thumb:hover img {
    transform: scale(1.05);
  }
  .remove {
    position: absolute;
    top: 6px;
    right: 6px;
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: rgb(0 0 0 / 0.6);
    color: #fff;
    opacity: 0;
    transition: opacity 120ms;
  }
  li:hover .remove,
  .remove:focus-visible {
    opacity: 1;
  }
  @media (hover: none) {
    .remove {
      opacity: 1;
    }
  }
</style>
