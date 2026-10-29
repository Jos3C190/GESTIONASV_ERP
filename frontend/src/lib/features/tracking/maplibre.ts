/**
 * MapLibre GL loader for the tracking module.
 *
 * Mirrors `loadLeaflet` in `$lib/services/maps`: the library is pulled once from a
 * pinned CDN build so the rest of the ERP does not pay for it. Basemaps come from
 * OpenFreeMap (vector tiles, no API key), the same family Traccar uses.
 */

const MAPLIBRE_VERSION = '5.24.0';
const MAPLIBRE_BASE = `https://unpkg.com/maplibre-gl@${MAPLIBRE_VERSION}/dist`;

/** Estilo claro en ambos temas del ERP: es el que mejor se lee, como en Traccar. */
export const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty';

/** San Miguel, El Salvador: punto de partida de la operación demo. */
export const DEFAULT_CENTER: [number, number] = [-88.1833, 13.4833];

// MapLibre is loaded at runtime from the CDN, so its types are not bundled.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type MapLibre = any;

let maplibrePromise: Promise<MapLibre> | null = null;

export function loadMapLibre(): Promise<MapLibre> {
  if (typeof window === 'undefined') return Promise.reject(new Error('Window not defined'));
  const existing = (window as typeof window & { maplibregl?: MapLibre }).maplibregl;
  if (existing) return Promise.resolve(existing);
  if (maplibrePromise) return maplibrePromise;

  maplibrePromise = new Promise((resolve, reject) => {
    if (!document.getElementById('maplibre-stylesheet')) {
      const stylesheet = document.createElement('link');
      stylesheet.id = 'maplibre-stylesheet';
      stylesheet.rel = 'stylesheet';
      stylesheet.href = `${MAPLIBRE_BASE}/maplibre-gl.css`;
      document.head.appendChild(stylesheet);
    }
    const script = document.createElement('script');
    script.id = 'maplibre-script';
    script.src = `${MAPLIBRE_BASE}/maplibre-gl.js`;
    script.async = true;
    script.onload = () => resolve((window as typeof window & { maplibregl: MapLibre }).maplibregl);
    script.onerror = () => {
      maplibrePromise = null;
      script.remove();
      reject(new Error('No se pudo cargar el mapa.'));
    };
    document.head.appendChild(script);
  });
  return maplibrePromise;
}
