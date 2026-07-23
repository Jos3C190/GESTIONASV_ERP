/**
 * Google Maps service helper.
 *
 * Provides script loading, marker utilities, and route calculation (Directions API)
 * prepared for the Branches module and future Fleet/Logistics modules.
 */

let mapsPromise: Promise<void> | null = null;

export function loadGoogleMapsScript(apiKey: string): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('Window not defined'));
  if (window.google?.maps) return Promise.resolve();

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
export async function calculateRoute(
  request: RouteRequest
): Promise<google.maps.DirectionsResult | null> {
  if (typeof window === 'undefined' || !window.google?.maps) {
    console.warn('Google Maps SDK not loaded');
    return null;
  }

  const directionsService = new window.google.maps.DirectionsService();

  return new Promise((resolve, reject) => {
    directionsService.route(
      {
        origin: request.origin,
        destination: request.destination,
        travelMode: (window.google.maps.TravelMode[request.travelMode ?? 'DRIVING'])
      },
      (result, status) => {
        if (status === window.google.maps.DirectionsStatus.OK && result) {
          resolve(result);
        } else {
          reject(new Error(`Directions request failed: ${status}`));
        }
      }
    );
  });
}
