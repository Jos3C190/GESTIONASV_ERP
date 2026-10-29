import { SvelteMap } from 'svelte/reactivity';

export interface GalleryPhoto {
  id: string;
  src: string;
  name: string;
}

export const GALLERY_ACCEPT = ['image/jpeg', 'image/png', 'image/webp'];

/**
 * Galería por vehículo, aparte de la portada (imagen base con la marca de la empresa).
 * En la maqueta las fotos viven solo en memoria como object URLs; no se suben a ningún servidor.
 */
function createVehicleGallery() {
  const photos = new SvelteMap<string, GalleryPhoto[]>();
  let sequence = 0;

  return {
    list(vehicleId: string): GalleryPhoto[] {
      return photos.get(vehicleId) ?? [];
    },
    add(vehicleId: string, files: Iterable<File>): number {
      const added = [...files]
        .filter((file) => GALLERY_ACCEPT.includes(file.type))
        .map((file) => ({
          id: `${vehicleId}-${++sequence}`,
          src: URL.createObjectURL(file),
          name: file.name
        }));
      if (added.length) photos.set(vehicleId, [...this.list(vehicleId), ...added]);
      return added.length;
    },
    remove(vehicleId: string, photoId: string) {
      const current = this.list(vehicleId);
      const photo = current.find((item) => item.id === photoId);
      if (!photo) return;
      URL.revokeObjectURL(photo.src);
      photos.set(
        vehicleId,
        current.filter((item) => item.id !== photoId)
      );
    }
  };
}

export const vehicleGallery = createVehicleGallery();
