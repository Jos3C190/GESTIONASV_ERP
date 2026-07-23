<script lang="ts">
  /** BranchMap — mapa de OpenStreetMap embebido con markers de sucursales.
   * Usa un iframe con la API de embed de OSM. Las sucursales son seleccionables
   * desde la tabla y se resaltan en el mapa centrando la vista.
   * MOCKUP: no hay interacción real con el mapa, solo embed + centrado. */

  import type { Branch } from '$lib/features/branches/mock-data';

  interface Props {
    branches: Branch[];
    selectedId: string | null;
  }

  let { branches, selectedId }: Props = $props();

  // Centro del mapa: promedio de todas las sucursales, o la seleccionada
  let center = $derived.by(() => {
    if (selectedId) {
      const b = branches.find(b => b.id === selectedId);
      if (b) return { lat: b.lat, lng: b.lng, zoom: 13 };
    }
    const avgLat = branches.reduce((s, b) => s + b.lat, 0) / branches.length;
    const avgLng = branches.reduce((s, b) => s + b.lng, 0) / branches.length;
    return { lat: avgLat, lng: avgLng, zoom: 8 };
  });

  // URL de embed de OSM con bbox centrado
  let mapUrl = $derived.by(() => {
    const delta = 0.15 / center.zoom * 8;
    const bbox = `${center.lng - delta}%2C${center.lat - delta}%2C${center.lng + delta}%2C${center.lat + delta}`;
    // Marker para cada sucursal
    const markers = branches
      .filter(b => b.status !== 'inactive')
      .map(b => {
        const isSelected = b.id === selectedId;
        const color = b.status === 'maintenance' ? 'f59e0b' : isSelected ? '0070f3' : '16a34a';
        return `marker=${b.lat}%2C${b.lng}%2C${color}`;
      })
      .join('&');
    return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&${markers}&layer=mapnik`;
  });
</script>

<div class="h-full w-full overflow-hidden rounded-xl border border-border">
  <iframe
    src={mapUrl}
    class="h-full w-full"
    style="border: 0;"
    loading="lazy"
    title="Mapa de sucursales"
    aria-label="Mapa de OpenStreetMap mostrando la ubicación de las sucursales"
  ></iframe>
</div>