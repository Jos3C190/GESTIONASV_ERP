<script lang="ts">
  /**
   * BranchMap — Mapa interactivo de sucursales en CartoDB Light Mode.
   *
   * Renderiza marcadores para TODAS las sucursales. La sucursal seleccionada se destaca
   * con tamaño ampliado y brillo en color de acento primario. Hacer clic en cualquier
   * pin selecciona automáticamente la sucursal.
   */

  import { onMount, untrack } from 'svelte';
  import type { Branch } from '$lib/features/branches/types';
  import { loadGoogleMapsScript, loadLeaflet } from '$lib/services/maps';
  import { theme } from '$lib/stores/theme.svelte';

  interface Props {
    branches: Branch[];
    selectedId: string | null;
    onSelect?: (id: string) => void;
  }

  let { branches, selectedId, onSelect }: Props = $props();

  const apiKey = (import.meta.env.PUBLIC_GOOGLE_MAPS_API_KEY as string | undefined) ?? '';

  let containerEl: HTMLDivElement | null = $state(null);
  let mapInstance = $state<any>(null);
  let tileLayerInstance: any = null;
  let markersMap = new Map<string, any>();
  let activeInfoWindow: any = null;
  let popupTimer: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;
  let useGoogleMaps = $state(Boolean(apiKey));

  function escapeHtml(value: string | number | null | undefined): string {
    return String(value ?? '').replace(
      /[&<>"']/g,
      (char) =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char] ?? char
    );
  }

  function coverUrl(branch: Branch): string {
    const url = branch.images[0]?.url;
    return url?.startsWith('https://res.cloudinary.com/') ? url : '/branch-mockup.png';
  }

  // Centro inicial del mapa: promedio de todas las sucursales
  let center = $derived.by(() => {
    if (selectedId) {
      const b = branches.find((b) => b.id === selectedId);
      if (b) return { lat: b.lat, lng: b.lng, zoom: 13 };
    }
    const avgLat = branches.length
      ? branches.reduce((s, b) => s + b.lat, 0) / branches.length
      : 13.6989;
    const avgLng = branches.length
      ? branches.reduce((s, b) => s + b.lng, 0) / branches.length
      : -89.1914;
    return { lat: avgLat, lng: avgLng, zoom: 8 };
  });

  async function initLeafletMap() {
    if (!containerEl || destroyed) return;
    try {
      const L = await loadLeaflet();
      if (!containerEl || destroyed) return;

      // CartoDB Positron (light grey) for light mode, Dark Matter for dark mode
      const tileUrl =
        theme.current === 'dark'
          ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
          : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';

      mapInstance = L.map(containerEl, {
        center: [center.lat, center.lng],
        zoom: center.zoom,
        zoomControl: true,
        attributionControl: false
      });

      tileLayerInstance = L.tileLayer(tileUrl, {
        subdomains: 'abcd',
        maxZoom: 19
      }).addTo(mapInstance);

      renderLeafletMarkers(L);
    } catch (err) {
      console.error('Error al cargar Leaflet / CartoDB:', err);
    }
  }

  // Reactive effect to change tile layer style when system theme changes
  $effect(() => {
    const currentTheme = theme.current;
    if (mapInstance && tileLayerInstance) {
      const newUrl =
        currentTheme === 'dark'
          ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
          : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
      tileLayerInstance.setUrl(newUrl);
    }
  });

  function renderLeafletMarkers(L: any) {
    if (!mapInstance) return;

    markersMap.forEach((m) => m.remove());
    markersMap.clear();

    branches.forEach((branch) => {
      const isSelected = branch.id === selectedId;
      const color = isSelected
        ? '#0070F3'
        : branch.status === 'active'
          ? '#10B981'
          : branch.status === 'maintenance'
            ? '#F59E0B'
            : '#64748B';

      const size = isSelected ? 34 : 24;

      const iconHtml = `
        <div style="position: relative; width: ${size}px; height: ${size}px; display: flex; align-items: center; justify-content: center; cursor: pointer;">
          ${isSelected ? `<div style="position: absolute; width: ${size + 18}px; height: ${size + 18}px; border-radius: 50%; background-color: ${color}; opacity: 0.35; filter: blur(2px); animation: markerPulse 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;"></div>` : ''}
          <div style="position: relative; width: ${size}px; height: ${size}px; border-radius: 50%; background-color: ${color}; border: 2.5px solid #ffffff; box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25), 0 1px 3px rgba(0, 0, 0, 0.12); display: flex; align-items: center; justify-content: center; transition: all 0.2s ease-out;">
            <div style="width: ${isSelected ? 9 : 6}px; height: ${isSelected ? 9 : 6}px; border-radius: 50%; background-color: #ffffff; box-shadow: 0 1px 2px rgba(0,0,0,0.15);"></div>
          </div>
        </div>
      `;

      const customIcon = L.divIcon({
        className: 'custom-branch-pin',
        html: iconHtml,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2]
      });

      const statusColor =
        branch.status === 'active'
          ? '#10B981'
          : branch.status === 'maintenance'
            ? '#F59E0B'
            : '#64748B';
      const statusLabel =
        branch.status === 'active'
          ? 'Activa'
          : branch.status === 'maintenance'
            ? 'Mantenimiento'
            : 'Inactiva';

      const marker = L.marker([branch.lat, branch.lng], { icon: customIcon }).addTo(mapInstance);

      const infoContent = `
        <div style="font-family: Geist, ui-sans-serif, system-ui, -apple-system, sans-serif; color: var(--text-foreground, #111827); width: 248px; overflow: hidden;">
          <div style="position: relative; width: 100%; height: 112px; background: #e5e7eb; overflow: hidden;">
            <img src="${escapeHtml(coverUrl(branch))}" alt="Sucursal" style="width: 100%; height: 100%; object-fit: cover; display: block;" loading="lazy" />
            <div style="position: absolute; bottom: 8px; left: 10px; background: ${statusColor}; color: #fff; font-size: 9.5px; font-weight: 700; padding: 2px 7px; border-radius: 999px; letter-spacing: 0.04em; text-transform: uppercase; box-shadow: 0 1px 2px rgb(0 0 0 / 18%);">${statusLabel}</div>
          </div>
          <div style="padding: 10px 12px 11px;">
            <h4 style="margin: 0 0 2px 0; font-size: 13px; font-weight: 700; color: var(--text-foreground, #111827); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${branch.name}</h4>
            <p style="margin: 0 0 8px 0; font-size: 10.5px; color: var(--text-foreground-muted, #6b7280);">${branch.code} &middot; ${branch.city}</p>
            <div style="border-top: 1px solid var(--border, #e5e7eb); padding-top: 7px; display: flex; flex-direction: column; gap: 2px;">
              <p style="margin: 0; font-size: 11px;"><strong>Gerente:</strong> ${branch.manager}</p>
              <p style="margin: 0; font-size: 11px;"><strong>Tel&eacute;fono:</strong> ${escapeHtml(branch.phone || 'Sin teléfono')}</p>
              <div style="display: flex; gap: 12px; font-size: 10.5px; color: var(--text-foreground-muted, #6b7280); margin-top: 4px;">
                <span>&#128101; <strong>${branch.employees}</strong> empl.</span>
                <span>&#128230; <strong>${branch.warehouses}</strong> alm.</span>
              </div>
            </div>
          </div>
        </div>
      `;

      marker.bindPopup(infoContent, {
        className: 'custom-leaflet-popup-light',
        autoPan: true
      });

      marker.on('click', () => {
        if (onSelect) onSelect(branch.id);
      });

      markersMap.set(branch.id, marker);
    });
  }

  // --- Carga de Google Maps JS API ---
  async function initGoogleMap() {
    if (!apiKey || !containerEl || destroyed) return;
    try {
      await loadGoogleMapsScript(apiKey);
      if (!containerEl || destroyed) return;

      mapInstance = new (window as any).google.maps.Map(containerEl, {
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
      if (destroyed) return;
      console.error('Error al cargar Google Maps API:', err);
      useGoogleMaps = false;
      void initLeafletMap();
    }
  }

  function renderGoogleMarkers() {
    if (!mapInstance) return;

    markersMap.forEach((m) => m.setMap(null));
    markersMap.clear();

    branches.forEach((branch) => {
      const isSelected = branch.id === selectedId;
      const color = isSelected
        ? '#0070F3'
        : branch.status === 'active'
          ? '#10B981'
          : branch.status === 'maintenance'
            ? '#F59E0B'
            : '#64748B';

      const marker = new (window as any).google.maps.Marker({
        position: { lat: branch.lat, lng: branch.lng },
        map: mapInstance,
        title: branch.name,
        icon: {
          url: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="${isSelected ? 36 : 28}" height="${isSelected ? 36 : 28}" viewBox="0 0 24 24" fill="${encodeURIComponent(color)}" stroke="%23ffffff" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3" fill="%23ffffff"/></svg>`,
          scaledSize: new (window as any).google.maps.Size(
            isSelected ? 36 : 28,
            isSelected ? 36 : 28
          )
        }
      });

      const statusColorG =
        branch.status === 'active'
          ? '#10B981'
          : branch.status === 'maintenance'
            ? '#F59E0B'
            : '#64748B';
      const statusLabelG =
        branch.status === 'active'
          ? 'Activa'
          : branch.status === 'maintenance'
            ? 'Mantenimiento'
            : 'Inactiva';

      const infoContent = `
        <div style="font-family: Geist, ui-sans-serif, system-ui, -apple-system, sans-serif; color: #111; width: 248px; overflow: hidden;">
          <div style="position: relative; width: 100%; height: 112px; background: #e5e7eb; overflow: hidden;">
            <img src="${escapeHtml(coverUrl(branch))}" alt="Sucursal" style="width: 100%; height: 100%; object-fit: cover; display: block;" loading="lazy" />
            <div style="position: absolute; bottom: 8px; left: 10px; background: ${statusColorG}; color: #fff; font-size: 9.5px; font-weight: 700; padding: 2px 7px; border-radius: 999px; letter-spacing: 0.04em; text-transform: uppercase; box-shadow: 0 1px 2px rgb(0 0 0 / 18%);">${statusLabelG}</div>
          </div>
          <div style="padding: 10px 12px 11px;">
            <h4 style="margin: 0 0 2px 0; font-size: 13px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${branch.name}</h4>
            <p style="margin: 0 0 8px 0; font-size: 10.5px; color: #6b7280;">${branch.code} &middot; ${branch.city}</p>
            <div style="border-top: 1px solid #e5e7eb; padding-top: 7px; display: flex; flex-direction: column; gap: 2px;">
              <p style="margin: 0; font-size: 11px;"><strong>Encargado:</strong> ${branch.manager}</p>
              <p style="margin: 0; font-size: 11px;"><strong>Tel&eacute;fono:</strong> ${escapeHtml(branch.phone || 'Sin teléfono')}</p>
              <div style="display: flex; gap: 12px; font-size: 10.5px; color: #6b7280; margin-top: 4px;">
                <span>&#128101; ${branch.employees} empl.</span>
                <span>&#128230; ${branch.warehouses} alm.</span>
              </div>
            </div>
          </div>
        </div>
      `;

      marker.addListener('click', () => {
        if (onSelect) onSelect(branch.id);
        if (activeInfoWindow) activeInfoWindow.close();
        activeInfoWindow = new (window as any).google.maps.InfoWindow({ content: infoContent });
        activeInfoWindow.open(mapInstance, marker);
      });

      markersMap.set(branch.id, marker);
    });
  }

  // Effect ultra-eficiente: Pan, zoom y apertura automática de InfoWindow al seleccionar
  $effect(() => {
    const id = selectedId;
    if (!mapInstance) return;

    untrack(() => {
      if (useGoogleMaps) {
        renderGoogleMarkers();
        if (id) {
          const b = branches.find((b) => b.id === id);
          if (b) {
            mapInstance.panTo({ lat: b.lat, lng: b.lng });
            mapInstance.setZoom(13);
            const m = markersMap.get(b.id);
            if (m) (window as any).google.maps.event.trigger(m, 'click');
          }
        }
      } else if ((window as any).L && mapInstance.setView) {
        const L = (window as any).L;
        renderLeafletMarkers(L);

        if (id) {
          const b = branches.find((b) => b.id === id);
          if (b) {
            mapInstance.flyTo([b.lat, b.lng], 15, { duration: 0.5 });
            const m = markersMap.get(b.id);
            if (m) {
              if (popupTimer) clearTimeout(popupTimer);
              popupTimer = setTimeout(() => {
                if (!destroyed && mapInstance && markersMap.get(b.id) === m) m.openPopup();
              }, 150);
            }
          }
        } else {
          mapInstance.flyTo([center.lat, center.lng], 8, { duration: 0.5 });
          mapInstance.closePopup();
        }
      }
    });
  });

  onMount(() => {
    destroyed = false;
    if (useGoogleMaps) {
      void initGoogleMap();
    } else {
      void initLeafletMap();
    }

    return () => {
      destroyed = true;
      if (popupTimer) clearTimeout(popupTimer);
      popupTimer = null;

      if (activeInfoWindow) activeInfoWindow.close?.();
      activeInfoWindow = null;

      const google = (window as any).google;
      markersMap.forEach((marker) => {
        if (google?.maps?.event) google.maps.event.clearInstanceListeners(marker);
        marker.setMap?.(null);
        marker.remove?.();
      });
      markersMap.clear();

      if (mapInstance) {
        if (google?.maps?.event && useGoogleMaps) {
          google.maps.event.clearInstanceListeners(mapInstance);
        } else {
          mapInstance.off?.();
          mapInstance.remove?.();
        }
      }
      tileLayerInstance = null;
      mapInstance = null;
      containerEl = null;
    };
  });
</script>

<div
  class="relative h-full w-full overflow-hidden rounded-xl border border-border bg-surface-elevated shadow-sm"
>
  <div bind:this={containerEl} class="h-full w-full min-h-0"></div>
</div>

<style>
  @keyframes markerPulse {
    0%,
    100% {
      transform: scale(0.9);
      opacity: 0.35;
    }
    50% {
      transform: scale(1.4);
      opacity: 0.12;
    }
  }

  :global(.custom-leaflet-popup-light .leaflet-popup-content-wrapper) {
    background: var(--bg-surface-elevated, #ffffff) !important;
    padding: 0 !important;
    overflow: hidden;
    border: 0 !important;
    border-radius: 14px !important;
    box-shadow: 0 12px 28px -8px rgba(0, 0, 0, 0.28) !important;
  }
  :global(.custom-leaflet-popup-light .leaflet-popup-content) {
    width: 248px !important;
    margin: 0 !important;
  }
  :global(.custom-leaflet-popup-light .leaflet-popup-tip) {
    background: var(--bg-surface-elevated, #ffffff) !important;
    box-shadow: 3px 3px 8px rgb(0 0 0 / 12%);
  }
  :global(.custom-branch-pin) {
    background: transparent !important;
    border: none !important;
  }
  /* Hacer el mapa de modo oscuro un poco más claro (gris medio) para encajar con el diseño Geist */
  :global([data-theme='dark'] .leaflet-tile) {
    filter: brightness(1.45) contrast(0.9) saturate(0.85);
  }
</style>
