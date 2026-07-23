<script lang="ts">
  /**
   * BranchMap — Mapa interactivo de sucursales en CartoDB Light Mode.
   *
   * Fijo en modo claro (CartoDB Voyager) para máxima legibilidad y estética.
   * Centra y abre automáticamente la ventana de información (Popup / InfoWindow)
   * al seleccionar cualquier sucursal desde la tabla lateral de forma ultra-rápida.
   */

  import { onMount } from 'svelte';
  import type { Branch } from '$lib/features/branches/mock-data';
  import { loadGoogleMapsScript } from '$lib/services/maps';

  interface Props {
    branches: Branch[];
    selectedId: string | null;
  }

  let { branches, selectedId }: Props = $props();

  const apiKey = (import.meta.env.PUBLIC_GOOGLE_MAPS_API_KEY as string | undefined) ?? '';

  let containerEl: HTMLDivElement | null = $state(null);
  let mapInstance = $state<any>(null);
  let markersMap = new Map<string, any>();
  let activeInfoWindow: any = null;
  let useGoogleMaps = $state(Boolean(apiKey));

  // Centro inicial del mapa: promedio de todas las sucursales
  let center = $derived.by(() => {
    if (selectedId) {
      const b = branches.find(b => b.id === selectedId);
      if (b) return { lat: b.lat, lng: b.lng, zoom: 13 };
    }
    const avgLat = branches.length ? branches.reduce((s, b) => s + b.lat, 0) / branches.length : 13.6989;
    const avgLng = branches.length ? branches.reduce((s, b) => s + b.lng, 0) / branches.length : -89.1914;
    return { lat: avgLat, lng: avgLng, zoom: 8 };
  });

  // --- Carga de Leaflet.js (CartoDB Voyager Light Tiles) ---
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

  async function initLeafletMap() {
    if (!containerEl) return;
    try {
      const L = await loadLeaflet();
      if (!containerEl) return;

      // Mapa fijo en Modo Claro (CartoDB Voyager)
      const tileUrl = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';

      mapInstance = L.map(containerEl, {
        center: [center.lat, center.lng],
        zoom: center.zoom,
        zoomControl: true,
        attributionControl: false
      });

      L.tileLayer(tileUrl, {
        subdomains: 'abcd',
        maxZoom: 19
      }).addTo(mapInstance);

      renderLeafletMarkers(L);
    } catch (err) {
      console.error('Error al cargar Leaflet / CartoDB:', err);
    }
  }

  function renderLeafletMarkers(L: any) {
    if (!mapInstance) return;

    markersMap.forEach(m => m.remove());
    markersMap.clear();

    branches.forEach(branch => {
      if (branch.status === 'inactive') return;

      const isSelected = branch.id === selectedId;
      const color = branch.status === 'maintenance' ? '#f59e0b' : isSelected ? '#0070f3' : '#10b981';
      const size = isSelected ? 32 : 24;

      const iconHtml = `
        <div style="position: relative; width: ${size}px; height: ${size}px; display: flex; align-items: center; justify-content: center;">
          ${isSelected ? `<div style="position: absolute; width: ${size + 16}px; height: ${size + 16}px; border-radius: 50%; background-color: ${color}; opacity: 0.3; filter: blur(2px); animation: markerPulse 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;"></div>` : ''}
          <div style="position: relative; width: ${size}px; height: ${size}px; border-radius: 50%; background-color: ${color}; border: 2.5px solid #ffffff; box-shadow: 0 3px 10px rgba(0, 0, 0, 0.22), 0 1px 3px rgba(0, 0, 0, 0.12); display: flex; align-items: center; justify-content: center; transition: all 0.2s ease-out;">
            <div style="width: ${isSelected ? 8 : 6}px; height: ${isSelected ? 8 : 6}px; border-radius: 50%; background-color: #ffffff; box-shadow: 0 1px 2px rgba(0,0,0,0.15);"></div>
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

      const infoContent = `
        <div style="font-family: system-ui, -apple-system, sans-serif; padding: 2px; color: #111827; min-width: 190px;">
          <h4 style="margin: 0 0 3px 0; font-size: 13px; font-weight: 600; color: #111827;">${branch.name}</h4>
          <p style="margin: 0 0 4px 0; font-size: 11px; color: #6b7280;">${branch.code} · ${branch.city}</p>
          <div style="border-top: 1px solid #e5e7eb; margin: 4px 0; padding-top: 4px;">
            <p style="margin: 0 0 2px 0; font-size: 11px;"><strong>Gerente:</strong> ${branch.manager}</p>
            <p style="margin: 0 0 4px 0; font-size: 11px;"><strong>Teléfono:</strong> ${branch.phone}</p>
            <div style="display: flex; gap: 10px; font-size: 10px; color: #6b7280; margin-top: 4px;">
              <span>👥 <strong>${branch.employees}</strong> empl.</span>
              <span>📦 <strong>${branch.warehouses}</strong> alm.</span>
            </div>
          </div>
        </div>
      `;

      marker.bindPopup(infoContent, {
        className: 'custom-leaflet-popup-light',
        autoPan: true
      });

      markersMap.set(branch.id, marker);
    });
  }

  // --- Carga de Google Maps JS API ---
  async function initGoogleMap() {
    if (!apiKey || !containerEl) return;
    try {
      await loadGoogleMapsScript(apiKey);
      if (!containerEl) return;

      mapInstance = new window.google.maps.Map(containerEl, {
        center: { lat: center.lat, lng: center.lng },
        zoom: center.zoom,
        disableDefaultUI: false,
        zoomControl: true,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true
      });

      renderGoogleMarkers();
    } catch (err) {
      console.error('Error al cargar Google Maps API:', err);
      useGoogleMaps = false;
      initLeafletMap();
    }
  }

  function renderGoogleMarkers() {
    if (!mapInstance) return;

    markersMap.forEach(m => m.setMap(null));
    markersMap.clear();

    branches.forEach(branch => {
      if (branch.status === 'inactive') return;

      const isSelected = branch.id === selectedId;
      const color = branch.status === 'maintenance' ? '#f59e0b' : isSelected ? '#0070f3' : '#10b981';

      const marker = new window.google.maps.Marker({
        position: { lat: branch.lat, lng: branch.lng },
        map: mapInstance,
        title: branch.name,
        icon: {
          url: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="${isSelected ? 36 : 28}" height="${isSelected ? 36 : 28}" viewBox="0 0 24 24" fill="${encodeURIComponent(color)}" stroke="%23ffffff" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3" fill="%23ffffff"/></svg>`,
          scaledSize: new window.google.maps.Size(isSelected ? 36 : 28, isSelected ? 36 : 28)
        }
      });

      const infoContent = `
        <div style="font-family: system-ui, sans-serif; padding: 4px; color: #111; max-width: 220px;">
          <h4 style="margin: 0 0 4px 0; font-size: 13px; font-weight: 600;">${branch.name}</h4>
          <p style="margin: 0 0 4px 0; font-size: 11px; color: #666;">${branch.code} · ${branch.city}</p>
          <p style="margin: 0 0 2px 0; font-size: 12px;"><strong>Encargado:</strong> ${branch.manager}</p>
          <p style="margin: 0 0 4px 0; font-size: 12px;"><strong>Teléfono:</strong> ${branch.phone}</p>
          <div style="display: flex; gap: 8px; font-size: 11px; color: #444; margin-top: 4px;">
            <span>👥 ${branch.employees} empl.</span>
            <span>📦 ${branch.warehouses} alm.</span>
          </div>
        </div>
      `;

      marker.addListener('click', () => {
        if (activeInfoWindow) activeInfoWindow.close();
        activeInfoWindow = new window.google.maps.InfoWindow({ content: infoContent });
        activeInfoWindow.open(mapInstance, marker);
      });

      markersMap.set(branch.id, marker);
    });
  }

  // Effect ultra-eficiente: Pan, zoom y apertura automática de InfoWindow al seleccionar
  $effect(() => {
    if (!mapInstance) return;

    if (useGoogleMaps) {
      renderGoogleMarkers();
      if (selectedId) {
        const b = branches.find(b => b.id === selectedId);
        if (b) {
          mapInstance.panTo({ lat: b.lat, lng: b.lng });
          mapInstance.setZoom(13);
          const m = markersMap.get(b.id);
          if (m) window.google.maps.event.trigger(m, 'click');
        }
      }
    } else if ((window as any).L && mapInstance.setView) {
      const L = (window as any).L;
      renderLeafletMarkers(L);

      if (selectedId) {
        const b = branches.find(b => b.id === selectedId);
        if (b) {
          mapInstance.flyTo([b.lat, b.lng], 13, { duration: 0.5 });
          const m = markersMap.get(b.id);
          if (m) {
            setTimeout(() => m.openPopup(), 150);
          }
        }
      } else {
        mapInstance.flyTo([center.lat, center.lng], 8, { duration: 0.5 });
        mapInstance.closePopup();
      }
    }
  });

  onMount(() => {
    if (useGoogleMaps) {
      initGoogleMap();
    } else {
      initLeafletMap();
    }
  });
</script>

<div class="relative h-full w-full overflow-hidden rounded-xl border border-border bg-surface-elevated">
  <div bind:this={containerEl} class="h-full w-full"></div>
</div>

<style>
  @keyframes markerPulse {
    0%, 100% {
      transform: scale(0.9);
      opacity: 0.35;
    }
    50% {
      transform: scale(1.4);
      opacity: 0.12;
    }
  }

  :global(.leaflet-popup-content-wrapper) {
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 12px !important;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.2) !important;
  }
  :global(.leaflet-popup-tip) {
    background: #ffffff !important;
  }
  :global(.custom-branch-pin) {
    background: transparent !important;
    border: none !important;
  }
</style>