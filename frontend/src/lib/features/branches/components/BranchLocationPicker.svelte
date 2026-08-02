<script lang="ts">
  import { onMount } from 'svelte';
  import { loadLeaflet } from '$lib/services/maps';
  import { theme } from '$lib/stores/theme.svelte';

  interface Position {
    latitude: number;
    longitude: number;
  }

  interface Props {
    latitude: string;
    longitude: string;
    onpositionchange?: (position: Position) => void;
  }

  let { latitude, longitude, onpositionchange }: Props = $props();
  let containerEl: HTMLDivElement | null = $state(null);
  let mapInstance: any = $state(null);
  let tileLayer: any = null;
  let marker: any = null;
  let resizeObserver: ResizeObserver | null = null;
  let ready = $state(false);
  let loadError = $state(false);
  let mounted = true;

  const FALLBACK = { latitude: 13.6989, longitude: -89.1914 };

  function currentPosition(): Position {
    const parsedLatitude = Number(latitude);
    const parsedLongitude = Number(longitude);
    return {
      latitude:
        Number.isFinite(parsedLatitude) && parsedLatitude >= -90 && parsedLatitude <= 90
          ? parsedLatitude
          : FALLBACK.latitude,
      longitude:
        Number.isFinite(parsedLongitude) && parsedLongitude >= -180 && parsedLongitude <= 180
          ? parsedLongitude
          : FALLBACK.longitude
    };
  }

  function tileUrl(currentTheme: 'light' | 'dark') {
    return currentTheme === 'dark'
      ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
      : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
  }

  function emitPosition(lat: number, lng: number) {
    onpositionchange?.({
      latitude: Number(lat.toFixed(6)),
      longitude: Number(lng.toFixed(6))
    });
  }

  async function initializeMap() {
    if (!containerEl) return;
    try {
      const L = await loadLeaflet();
      if (!mounted || !containerEl) return;

      const position = currentPosition();
      mapInstance = L.map(containerEl, {
        center: [position.latitude, position.longitude],
        zoom: 15,
        zoomControl: true,
        attributionControl: false,
        scrollWheelZoom: false,
        preferCanvas: true,
        zoomAnimation: true,
        fadeAnimation: true,
        markerZoomAnimation: true,
        inertia: true
      });

      tileLayer = L.tileLayer(tileUrl(theme.current), {
        subdomains: 'abcd',
        maxZoom: 19,
        updateWhenIdle: true,
        keepBuffer: 3
      }).addTo(mapInstance);

      const icon = L.divIcon({
        className: 'branch-location-marker',
        html: '<span class="branch-location-marker__pulse"></span><span class="branch-location-marker__pin"><span></span></span>',
        iconSize: [36, 36],
        iconAnchor: [18, 18]
      });

      marker = L.marker([position.latitude, position.longitude], {
        icon,
        draggable: true,
        autoPan: true,
        keyboard: true,
        title: 'Ubicación de la sucursal'
      }).addTo(mapInstance);

      marker.on('dragend', () => {
        const next = marker.getLatLng();
        emitPosition(next.lat, next.lng);
      });
      mapInstance.on('click', (event: { latlng: { lat: number; lng: number } }) => {
        marker.setLatLng(event.latlng);
        emitPosition(event.latlng.lat, event.latlng.lng);
      });

      resizeObserver = new ResizeObserver(() => mapInstance?.invalidateSize({ pan: false }));
      resizeObserver.observe(containerEl);
      ready = true;
      requestAnimationFrame(() => mapInstance?.invalidateSize({ pan: false }));
    } catch {
      loadError = true;
    }
  }

  $effect(() => {
    const currentTheme = theme.current;
    tileLayer?.setUrl(tileUrl(currentTheme));
  });

  $effect(() => {
    const position = currentPosition();
    if (!mapInstance || !marker) return;

    const timer = window.setTimeout(() => {
      const markerPosition = marker.getLatLng();
      if (
        Math.abs(markerPosition.lat - position.latitude) < 0.000001 &&
        Math.abs(markerPosition.lng - position.longitude) < 0.000001
      )
        return;

      const next = [position.latitude, position.longitude] as [number, number];
      marker.setLatLng(next);
      if (!mapInstance.getBounds().pad(-0.2).contains(next)) {
        mapInstance.panTo(next, { animate: true, duration: 0.25 });
      }
    }, 140);

    return () => window.clearTimeout(timer);
  });

  onMount(() => {
    void initializeMap();
    return () => {
      mounted = false;
      resizeObserver?.disconnect();
      mapInstance?.remove();
      mapInstance = null;
      marker = null;
      tileLayer = null;
    };
  });
</script>

<div class="overflow-hidden rounded-xl border border-border bg-surface-muted">
  <div class="relative h-72 w-full sm:h-80">
    <div
      bind:this={containerEl}
      class="h-full w-full"
      role="application"
      aria-label="Selector de ubicación de la sucursal"
    ></div>
    {#if !ready && !loadError}
      <div class="pointer-events-none absolute inset-0 grid place-items-center bg-surface-muted">
        <div class="flex items-center gap-2 text-sm text-foreground-muted">
          <span class="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-primary"
          ></span>
          Cargando mapa…
        </div>
      </div>
    {:else if loadError}
      <div class="absolute inset-0 grid place-items-center bg-surface-muted p-6 text-center">
        <p class="text-sm text-danger">
          No se pudo cargar el mapa. Las coordenadas aún pueden ingresarse manualmente.
        </p>
      </div>
    {/if}
  </div>
  <div
    class="flex flex-wrap items-center justify-between gap-2 border-t border-border bg-surface-elevated px-3 py-2"
  >
    <p class="text-xs text-foreground-muted">
      Haga clic en el mapa o arrastre el marcador para precisar la ubicación.
    </p>
    <span class="font-mono text-[11px] text-foreground-subtle"
      >{latitude || '—'}, {longitude || '—'}</span
    >
  </div>
</div>

<style>
  :global(.branch-location-marker) {
    background: transparent !important;
    border: 0 !important;
  }
  :global(.branch-location-marker__pulse) {
    position: absolute;
    inset: -7px;
    border-radius: 999px;
    background: rgb(var(--primary) / 0.28);
    animation: locationPulse 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  }
  :global(.branch-location-marker__pin) {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    border: 2.5px solid white;
    border-radius: 999px;
    background: rgb(var(--primary));
    box-shadow:
      0 3px 10px rgb(0 0 0 / 0.3),
      0 1px 3px rgb(0 0 0 / 0.16);
  }
  :global(.branch-location-marker__pin > span) {
    width: 9px;
    height: 9px;
    border-radius: 999px;
    background: white;
  }
  :global([data-theme='dark'] .leaflet-tile) {
    filter: brightness(1.45) contrast(0.9) saturate(0.85);
  }
  :global(.leaflet-container) {
    font-family: inherit;
    background: rgb(var(--surface-muted));
  }
  @keyframes locationPulse {
    0%,
    100% {
      transform: scale(0.9);
      opacity: 0.4;
    }
    50% {
      transform: scale(1.25);
      opacity: 0.12;
    }
  }
</style>
