<script lang="ts">
  /**
   * BranchMiniMap — Mapa de ubicación única de una sucursal (Leaflet + CartoDB).
   * Muestra un solo marcador con popup. Se centra automáticamente en la ubicación.
   */

  import { onMount } from 'svelte';
  import type { Branch } from '$lib/features/branches/mock-data';
  import { theme } from '$lib/stores/theme.svelte';

  interface Props {
    branch: Branch;
    height?: number;
    fillHeight?: boolean;
  }

  let { branch, height = 280, fillHeight = false }: Props = $props();

  let containerEl: HTMLDivElement | null = $state(null);
  let mapInstance = $state<any>(null);
  let tileLayerInstance: any = null;

  let markerColor = $derived.by(() => {
    if (branch.status === 'active') return '#10B981';
    if (branch.status === 'maintenance') return '#F59E0B';
    return '#64748B';
  });

  function loadLeaflet(): Promise<any> {
    return new Promise((resolve, reject) => {
      if ((window as any).L) return resolve((window as any).L);

      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(link);

      const script = document.createElement('script');
      script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      script.async = true;
      script.onload = () => resolve((window as any).L);
      script.onerror = (err) => reject(err);
      document.head.appendChild(script);
    });
  }

  async function initMap() {
    if (!containerEl) return;
    try {
      const L = await loadLeaflet();
      if (!containerEl) return;

      const tileUrl = theme.current === 'dark'
        ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
        : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';

      mapInstance = L.map(containerEl, {
        center: [branch.lat, branch.lng],
        zoom: 15,
        zoomControl: true,
        attributionControl: false,
        scrollWheelZoom: false
      });

      tileLayerInstance = L.tileLayer(tileUrl, {
        subdomains: 'abcd',
        maxZoom: 19
      }).addTo(mapInstance);

      const size = 36;

      const iconHtml = `
        <div style="position: relative; width: ${size}px; height: ${size}px; display: flex; align-items: center; justify-content: center; cursor: pointer;">
          <div style="position: absolute; width: ${size + 18}px; height: ${size + 18}px; border-radius: 50%; background-color: ${markerColor}; opacity: 0.35; filter: blur(2px); animation: markerPulse 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;"></div>
          <div style="position: relative; width: ${size}px; height: ${size}px; border-radius: 50%; background-color: ${markerColor}; border: 2.5px solid #ffffff; box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25), 0 1px 3px rgba(0, 0, 0, 0.12); display: flex; align-items: center; justify-content: center;">
            <div style="width: 10px; height: 10px; border-radius: 50%; background-color: #ffffff;"></div>
          </div>
        </div>
      `;

      const customIcon = L.divIcon({
        className: 'custom-branch-pin',
        html: iconHtml,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2]
      });

      const marker = L.marker([branch.lat, branch.lng], { icon: customIcon }).addTo(mapInstance);

      const statusLabel = branch.status === 'active' ? 'Activa' : branch.status === 'maintenance' ? 'Mantenimiento' : 'Inactiva';

      marker.bindPopup(`
        <div style="font-family: system-ui, -apple-system, sans-serif; width: 220px; border-radius: 8px; overflow: hidden; margin: -1px;">
          <div style="padding: 10px 12px 8px;">
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
              <strong style="font-size: 13px; color: #111827;">${branch.name}</strong>
              <span style="background: ${markerColor}; color: #fff; font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 999px; letter-spacing: 0.04em; text-transform: uppercase;">${statusLabel}</span>
            </div>
            <p style="margin: 0; font-size: 11px; color: #6b7280;">${branch.code} &middot; ${branch.city}</p>
            <p style="margin: 4px 0 0 0; font-size: 11px; color: #6b7280;">${branch.address}</p>
          </div>
        </div>
      `, { className: 'custom-leaflet-popup-light' });

      setTimeout(() => marker.openPopup(), 300);
    } catch (err) {
      console.error('Error al cargar mapa:', err);
    }
  }

  $effect(() => {
    const currentTheme = theme.current;
    if (mapInstance && tileLayerInstance) {
      const newUrl = currentTheme === 'dark'
        ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
        : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
      tileLayerInstance.setUrl(newUrl);
    }
  });

  onMount(() => { initMap(); });
</script>

<div class="relative {fillHeight ? 'flex-1 min-h-[300px]' : 'w-full'} overflow-hidden rounded-xl border border-border bg-surface-elevated" style={fillHeight ? '' : `height: ${height}px`}>
  <div bind:this={containerEl} class="h-full w-full"></div>
</div>

<style>
  @keyframes markerPulse {
    0%, 100% { transform: scale(0.9); opacity: 0.35; }
    50% { transform: scale(1.4); opacity: 0.12; }
  }

  :global(.leaflet-popup-content-wrapper) {
    background: var(--bg-surface-elevated, #ffffff) !important;
    border: 1px solid var(--border, #e5e7eb) !important;
    border-radius: 12px !important;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.2) !important;
  }
  :global(.leaflet-popup-tip) {
    background: var(--bg-surface-elevated, #ffffff) !important;
    border: 1px solid var(--border, #e5e7eb) !important;
  }
  :global(.custom-branch-pin) {
    background: transparent !important;
    border: none !important;
  }
  :global([data-theme="dark"] .leaflet-tile) {
    filter: brightness(1.45) contrast(0.9) saturate(0.85);
  }
  :global(.leaflet-container) {
    font-family: inherit;
  }
</style>