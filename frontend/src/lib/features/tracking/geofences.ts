import type { GeofenceOut, GeofenceShape } from '$lib/api/client';

type LngLat = [number, number];

export type DraftKind = 'polygon' | 'circle';

/** Geocerca en dibujo: vértices del polígono o el centro del círculo y su radio. */
export interface GeofenceDraft {
  kind: DraftKind;
  vertices: LngLat[];
  radiusM: number;
}

export function draftRing(draft: GeofenceDraft): LngLat[] {
  if (draft.kind === 'circle')
    return draft.vertices.length ? circleRing(draft.vertices[0]!, draft.radiusM) : [];
  return draft.vertices.length >= 3 ? [...draft.vertices, draft.vertices[0]!] : draft.vertices;
}

export function draftShape(draft: GeofenceDraft): GeofenceShape | null {
  if (draft.kind === 'circle')
    return draft.vertices.length
      ? { type: 'circle', center: draft.vertices[0]!, radius_m: Math.round(draft.radiusM) }
      : null;
  return draft.vertices.length >= 3 ? { type: 'polygon', coordinates: draft.vertices } : null;
}

const EARTH_RADIUS_M = 6_371_000;

/** Aproxima un círculo geográfico con un polígono para dibujarlo en el mapa. */
export function circleRing([lng, lat]: LngLat, radiusM: number, steps = 64): LngLat[] {
  const angular = radiusM / EARTH_RADIUS_M;
  const latRad = (lat * Math.PI) / 180;
  const lngRad = (lng * Math.PI) / 180;
  const ring: LngLat[] = [];
  for (let i = 0; i <= steps; i++) {
    const bearing = (i / steps) * 2 * Math.PI;
    const pointLat = Math.asin(
      Math.sin(latRad) * Math.cos(angular) +
        Math.cos(latRad) * Math.sin(angular) * Math.cos(bearing)
    );
    const pointLng =
      lngRad +
      Math.atan2(
        Math.sin(bearing) * Math.sin(angular) * Math.cos(latRad),
        Math.cos(angular) - Math.sin(latRad) * Math.sin(pointLat)
      );
    ring.push([(pointLng * 180) / Math.PI, (pointLat * 180) / Math.PI]);
  }
  return ring;
}

export function shapeRing(shape: GeofenceShape): LngLat[] {
  if (shape.type === 'circle') return circleRing(shape.center, shape.radius_m);
  return [...shape.coordinates, shape.coordinates[0]!];
}

/** Distancia en metros entre dos puntos (haversine). */
export function distanceM([aLng, aLat]: LngLat, [bLng, bLat]: LngLat): number {
  const toRad = Math.PI / 180;
  const dLat = (bLat - aLat) * toRad;
  const dLng = (bLng - aLng) * toRad;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(aLat * toRad) * Math.cos(bLat * toRad) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h));
}

/** Área aproximada en m² (proyección equirectangular local; suficiente para mostrar). */
export function shapeAreaM2(shape: GeofenceShape): number {
  if (shape.type === 'circle') return Math.PI * shape.radius_m ** 2;
  const ring = shape.coordinates;
  const lat0 = (ring.reduce((sum, [, lat]) => sum + lat, 0) / ring.length) * (Math.PI / 180);
  const mPerDeg = (Math.PI / 180) * EARTH_RADIUS_M;
  let area = 0;
  ring.forEach(([lng, lat], i) => {
    const [nextLng, nextLat] = ring[(i + 1) % ring.length]!;
    area +=
      lng * Math.cos(lat0) * mPerDeg * (nextLat * mPerDeg) -
      nextLng * Math.cos(lat0) * mPerDeg * (lat * mPerDeg);
  });
  return Math.abs(area / 2);
}

export function describeShape(shape: GeofenceShape): string {
  if (shape.type === 'circle') {
    const radius =
      shape.radius_m >= 1000
        ? `${(shape.radius_m / 1000).toFixed(1)} km`
        : `${Math.round(shape.radius_m)} m`;
    return `Círculo · radio ${radius}`;
  }
  const km2 = shapeAreaM2(shape) / 1_000_000;
  const area =
    km2 >= 1
      ? `${km2.toFixed(1)} km²`
      : `${Math.round(km2 * 1_000_000).toLocaleString('es-SV')} m²`;
  return `Polígono · ${shape.coordinates.length} vértices · ${area}`;
}

export function geofenceCollection(geofences: Pick<GeofenceOut, 'id' | 'name' | 'shape'>[]) {
  return {
    type: 'FeatureCollection',
    features: geofences.map((geofence) => ({
      type: 'Feature',
      // MapLibre solo admite ids no negativos; las geocercas demo usan ids negativos.
      id: Math.abs(geofence.id),
      properties: { name: geofence.name },
      geometry: { type: 'Polygon', coordinates: [shapeRing(geofence.shape)] }
    }))
  };
}
