<script lang="ts">
  import { onMount } from 'svelte';
  import { theme } from '$lib/stores/theme.svelte';
  import { DEFAULT_CENTER, loadMapLibre, MAP_STYLES, type MapLibre } from './maplibre';
  import { STATUS_LABELS, type TrackedVehicle } from './tracking';

  type LngLat = [number, number];

  let {
    vehicles,
    selectedKey = null,
    follow = false,
    trail = [],
    plannedRoute = null,
    onselect
  }: {
    vehicles: TrackedVehicle[];
    selectedKey?: string | null;
    follow?: boolean;
    trail?: LngLat[];
    plannedRoute?: LngLat[] | null;
    onselect: (key: string | null) => void;
  } = $props();

  const TRUCK_PATH =
    'M3 5h11v12H3z M14 9h4l3 4v4h-7 M7 19a2 2 0 100-4 2 2 0 000 4 M17 19a2 2 0 100-4 2 2 0 000 4';

  let container = $state<HTMLDivElement>();
  let map = $state.raw<MapLibre | null>(null);
  let loadError = $state<string | null>(null);
  let styleReady = $state(0);
  let fitted = false;
  const markers = new Map<string, { marker: MapLibre; element: HTMLDivElement }>();

  const line = (coordinates: LngLat[]) => ({
    type: 'Feature',
    properties: {},
    geometry: { type: 'LineString', coordinates }
  });

  // Las capas propias se pierden con cada setStyle (cambio de tema), así que se recrean.
  function addOverlayLayers() {
    if (!map || map.getSource('planned-route')) return;
    map.addSource('planned-route', { type: 'geojson', data: line([]) });
    map.addSource('trail', { type: 'geojson', data: line([]) });
    map.addLayer({
      id: 'planned-route',
      type: 'line',
      source: 'planned-route',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#0ea5e9', 'line-width': 3, 'line-opacity': 0.55, 'line-dasharray': [1.5, 1.5] }
    });
    map.addLayer({
      id: 'trail',
      type: 'line',
      source: 'trail',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#0284c7', 'line-width': 4, 'line-opacity': 0.9 }
    });
    styleReady++;
  }

  function createMarkerElement(vehicle: TrackedVehicle): HTMLDivElement {
    const element = document.createElement('div');
    element.className = 'tm-marker';
    element.innerHTML = `<span class="tm-heading"></span><span class="tm-pin"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${TRUCK_PATH}"/></svg></span><span class="tm-label"></span>`;
    element.setAttribute('role', 'button');
    element.tabIndex = 0;
    const select = (event: Event) => {
      event.stopPropagation();
      onselect(vehicle.key);
    };
    element.addEventListener('click', select);
    element.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') select(event);
    });
    return element;
  }

  function syncMarkers(maplibregl: MapLibre) {
    const seen = new Set<string>();
    for (const vehicle of vehicles) {
      seen.add(vehicle.key);
      let entry = markers.get(vehicle.key);
      if (!entry) {
        const element = createMarkerElement(vehicle);
        const marker = new maplibregl.Marker({ element, anchor: 'center' })
          .setLngLat([vehicle.longitude, vehicle.latitude])
          .addTo(map);
        entry = { marker, element };
        markers.set(vehicle.key, entry);
      }
      entry.marker.setLngLat([vehicle.longitude, vehicle.latitude]);
      const { element } = entry;
      element.dataset.status = vehicle.status;
      element.classList.toggle('selected', vehicle.key === selectedKey);
      element.setAttribute('aria-label', `${vehicle.name}, ${STATUS_LABELS[vehicle.status]}`);
      element.querySelector<HTMLElement>('.tm-label')!.textContent = vehicle.name;
      element.querySelector<HTMLElement>('.tm-heading')!.style.transform =
        `rotate(${vehicle.course}deg)`;
    }
    for (const [key, entry] of markers) {
      if (!seen.has(key)) {
        entry.marker.remove();
        markers.delete(key);
      }
    }
  }

  onMount(() => {
    let disposed = false;
    loadMapLibre()
      .then((maplibregl) => {
        if (disposed || !container) return;
        const instance = new maplibregl.Map({
          container,
          style: MAP_STYLES[theme.current],
          center: DEFAULT_CENTER,
          zoom: 9,
          attributionControl: { compact: true }
        });
        instance.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
        instance.addControl(new maplibregl.FullscreenControl(), 'top-right');
        instance.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');
        instance.on('style.load', addOverlayLayers);
        instance.on('click', () => onselect(null));
        (instance as MapLibre).__maplibregl = maplibregl;
        map = instance;
      })
      .catch((error: Error) => (loadError = error.message));
    return () => {
      disposed = true;
      markers.forEach((entry) => entry.marker.remove());
      markers.clear();
      map?.remove();
    };
  });

  $effect(() => {
    if (!map) return;
    const style = MAP_STYLES[theme.current];
    // setStyle conserva los marcadores HTML; las capas propias se reagregan en style.load.
    if (map.__currentStyle && map.__currentStyle !== style) map.setStyle(style);
    map.__currentStyle = style;
  });

  $effect(() => {
    if (!map) return;
    void selectedKey;
    syncMarkers(map.__maplibregl);
    if (!fitted && vehicles.length) {
      fitted = true;
      const bounds = new map.__maplibregl.LngLatBounds();
      vehicles.forEach((vehicle) => bounds.extend([vehicle.longitude, vehicle.latitude]));
      map.fitBounds(bounds, { padding: { top: 60, bottom: 60, left: 380, right: 60 }, maxZoom: 13, duration: 0 });
    }
  });

  $effect(() => {
    if (!map || !styleReady) return;
    map.getSource('trail')?.setData(line(trail));
    map.getSource('planned-route')?.setData(line(plannedRoute ?? []));
  });

  $effect(() => {
    if (!map || !follow || !selectedKey) return;
    const vehicle = vehicles.find((item) => item.key === selectedKey);
    if (vehicle) map.easeTo({ center: [vehicle.longitude, vehicle.latitude], duration: 800 });
  });

  let lastFocused: string | null = null;
  $effect(() => {
    if (!map || !selectedKey || selectedKey === lastFocused) return;
    lastFocused = selectedKey;
    const vehicle = vehicles.find((item) => item.key === selectedKey);
    if (vehicle)
      map.flyTo({
        center: [vehicle.longitude, vehicle.latitude],
        zoom: Math.max(map.getZoom(), 12),
        offset: [160, 0],
        duration: 900
      });
  });
</script>

<div class="tracking-map" bind:this={container}>
  {#if loadError}
    <div class="map-error">{loadError} Revisa tu conexión a internet.</div>
  {/if}
</div>

<style>
  .tracking-map {
    position: absolute;
    inset: 0;
    background: rgb(var(--surface-muted));
  }
  .map-error {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    padding: 24px;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
    text-align: center;
  }
  :global(.tm-marker) {
    position: relative;
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    cursor: pointer;
    --tm-color: 22 163 74;
  }
  :global(.tm-marker[data-status='stopped']) {
    --tm-color: 217 119 6;
  }
  :global(.tm-marker[data-status='offline']) {
    --tm-color: 113 113 122;
  }
  :global(.tm-marker .tm-pin) {
    position: relative;
    z-index: 1;
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border: 2px solid #fff;
    border-radius: 50%;
    background: rgb(var(--tm-color));
    color: #fff;
    box-shadow: 0 2px 8px rgb(0 0 0 / 0.35);
    transition: transform 150ms;
  }
  :global(.tm-marker .tm-heading) {
    position: absolute;
    inset: -7px;
    transition: transform 600ms ease-out;
  }
  :global(.tm-marker .tm-heading::before) {
    content: '';
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-bottom: 9px solid rgb(var(--tm-color));
  }
  :global(.tm-marker:not([data-status='moving']) .tm-heading) {
    display: none;
  }
  :global(.tm-marker .tm-label) {
    position: absolute;
    top: 36px;
    left: 50%;
    transform: translateX(-50%);
    padding: 1px 6px;
    border-radius: 4px;
    background: rgb(255 255 255 / 0.92);
    color: #18181b;
    font-size: 10px;
    font-weight: 650;
    white-space: nowrap;
    box-shadow: 0 1px 3px rgb(0 0 0 / 0.25);
  }
  :global(.tm-marker.selected) {
    z-index: 2;
  }
  :global(.tm-marker.selected .tm-pin) {
    transform: scale(1.18);
    box-shadow:
      0 0 0 4px rgb(var(--tm-color) / 0.35),
      0 2px 10px rgb(0 0 0 / 0.4);
  }
  :global(.tm-marker:focus-visible) {
    outline: none;
  }
  :global(.tm-marker:focus-visible .tm-pin) {
    box-shadow: 0 0 0 3px rgb(var(--primary));
  }
  :global(.tracking-map .maplibregl-ctrl-group) {
    border-radius: 10px;
    box-shadow: 0 2px 8px rgb(0 0 0 / 0.18);
  }
</style>
