/**
 * Google Maps service helper.
 *
 * Provides script loading, marker utilities, and route calculation (Directions API)
 * prepared for the Branches module and future Fleet/Logistics modules.
 */

let mapsPromise: Promise<void> | null = null;
let leafletPromise: Promise<any> | null = null;
type MapsSdk = {
  maps: {
    DirectionsService: new () => {
      route: (request: unknown, callback: (result: unknown, status: string) => void) => void;
    };
    TravelMode: Record<string, string>;
    DirectionsStatus: { OK: string };
  };
};
const mapsSdk = () => (window as typeof window & { google?: MapsSdk }).google;

/** Loads Leaflet only once for every map in the ERP. */
export function loadLeaflet(): Promise<any> {
  if (typeof window === 'undefined') return Promise.reject(new Error('Window not defined'));
  if ((window as any).L) return Promise.resolve((window as any).L);
  if (leafletPromise) return leafletPromise;

  leafletPromise = new Promise((resolve, reject) => {
    let stylesheet = document.getElementById('leaflet-stylesheet') as HTMLLinkElement | null;
    if (!stylesheet) {
      stylesheet = document.createElement('link');
      stylesheet.id = 'leaflet-stylesheet';
      stylesheet.rel = 'stylesheet';
      stylesheet.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(stylesheet);
    }

    const existingScript = document.getElementById('leaflet-script') as HTMLScriptElement | null;
    if (existingScript) {
      existingScript.addEventListener('load', () => resolve((window as any).L), { once: true });
      existingScript.addEventListener(
        'error',
        (error) => {
          leafletPromise = null;
          reject(error);
        },
        { once: true }
      );
      return;
    }

    const script = document.createElement('script');
    script.id = 'leaflet-script';
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.async = true;
    script.onload = () => resolve((window as any).L);
    script.onerror = (error) => {
      leafletPromise = null;
      reject(error);
    };
    document.head.appendChild(script);
  });

  return leafletPromise;
}

export function loadGoogleMapsScript(apiKey: string): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('Window not defined'));
  if (mapsSdk()?.maps) return Promise.resolve();

  if (mapsPromise) return mapsPromise;

  mapsPromise = new Promise((resolve, reject) => {
    const existingScript = document.getElementById('google-maps-script');
    if (existingScript) {
      existingScript.addEventListener('load', () => resolve());
      existingScript.addEventListener('error', (err) => reject(err));
      return;
    }

    const script = document.createElement('script');
    script.id = 'google-maps-script';
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=places,geometry`;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = (err) => {
      mapsPromise = null;
      reject(err);
    };

    document.head.appendChild(script);
  });

  return mapsPromise;
}

export interface RouteRequest {
  origin: { lat: number; lng: number };
  destination: { lat: number; lng: number };
  travelMode?: 'DRIVING' | 'WALKING' | 'BICYCLING' | 'TRANSIT';
}

/**
 * Calculates a route between two points using Google Maps DirectionsService.
 * Ready for the Fleet and Drivers (Flota y Conductores) module.
 */
export async function calculateRoute(request: RouteRequest): Promise<unknown | null> {
  if (typeof window === 'undefined' || !mapsSdk()?.maps) {
    console.warn('Google Maps SDK not loaded');
    return null;
  }

  const sdk = mapsSdk();
  if (!sdk) return null;
  const directionsService = new sdk.maps.DirectionsService();

  return new Promise((resolve, reject) => {
    directionsService.route(
      {
        origin: request.origin,
        destination: request.destination,
        travelMode: sdk.maps.TravelMode[request.travelMode ?? 'DRIVING']
      },
      (result, status) => {
        if (status === sdk.maps.DirectionsStatus.OK && result) {
          resolve(result);
        } else {
          reject(new Error(`Directions request failed: ${status}`));
        }
      }
    );
  });
}
