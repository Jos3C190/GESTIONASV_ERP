import { DEMO_VEHICLES } from '$lib/features/fleet/mock-data';
import { statusFor, type TrackedVehicle } from './tracking';

type LngLat = [number, number];

/** Sucursal Roosevelt (San Miguel): origen de los recorridos de la demostración. */
const SAN_MIGUEL: LngLat = [-88.185666, 13.483663];
const DISTRIBUTION_CENTER: LngLat = [-88.177, 13.4795];
const WORKSHOP: LngLat = [-88.17, 13.49];

/**
 * Recorridos de la demostración desde San Miguel. Estos trazos aproximados son el respaldo;
 * `loadDemoRoutes` los reemplaza por rutas reales por calles (OSRM) en cuanto el backend responde.
 */
const ROUTES: Record<string, LngLat[]> = {
  'Santa Rosa de Lima': [
    SAN_MIGUEL,
    [-88.1, 13.53],
    [-88.02, 13.57],
    [-87.95, 13.6],
    [-87.8936, 13.6247]
  ],
  'La Unión': [SAN_MIGUEL, [-88.1, 13.45], [-88.0, 13.4], [-87.92, 13.37], [-87.8439, 13.3369]],
  Usulután: [SAN_MIGUEL, [-88.26, 13.43], [-88.35, 13.38], [-88.42, 13.36], [-88.44, 13.344]],
  Jiquilisco: [
    SAN_MIGUEL,
    [-88.26, 13.43],
    [-88.35, 13.38],
    [-88.44, 13.344],
    [-88.52, 13.33],
    [-88.573, 13.3189]
  ],
  'El Tránsito': [SAN_MIGUEL, [-88.26, 13.4], [-88.33, 13.36], [-88.353, 13.35]],
  'San Salvador': [
    SAN_MIGUEL,
    [-88.3, 13.52],
    [-88.48, 13.55],
    [-88.7, 13.6],
    [-88.9, 13.66],
    [-89.05, 13.7],
    [-89.2182, 13.6929]
  ],
  'Santa Ana': [
    SAN_MIGUEL,
    [-88.48, 13.55],
    [-88.9, 13.66],
    [-89.2182, 13.6929],
    [-89.35, 13.75],
    [-89.45, 13.88],
    [-89.5597, 13.9946]
  ]
};

/** Un recorrido completo dura ~25 minutos en la simulación. */
const LOOP_SECONDS = 1500;

const segmentLength = ([ax, ay]: LngLat, [bx, by]: LngLat) =>
  Math.hypot((bx - ax) * Math.cos((ay * Math.PI) / 180), by - ay);

function bearing([ax, ay]: LngLat, [bx, by]: LngLat): number {
  const toRad = Math.PI / 180;
  const y = Math.sin((bx - ax) * toRad) * Math.cos(by * toRad);
  const x =
    Math.cos(ay * toRad) * Math.sin(by * toRad) -
    Math.sin(ay * toRad) * Math.cos(by * toRad) * Math.cos((bx - ax) * toRad);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

/** Punto y rumbo a una fracción (0–1) del recorrido. */
export function pointAlong(route: LngLat[], fraction: number): { point: LngLat; course: number } {
  const lengths = route.slice(1).map((point, i) => segmentLength(route[i]!, point));
  let remaining =
    Math.min(Math.max(fraction, 0), 1) * lengths.reduce((sum, value) => sum + value, 0);
  for (let i = 0; i < lengths.length; i++) {
    const start = route[i]!;
    const end = route[i + 1]!;
    const length = lengths[i]!;
    if (remaining <= length || i === lengths.length - 1) {
      const t = length === 0 ? 0 : Math.min(remaining / length, 1);
      return {
        point: [start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t],
        course: bearing(start, end)
      };
    }
    remaining -= length;
  }
  return { point: route[0]!, course: 0 };
}

const jitter = (seed: number, amount: number) => Math.sin(seed * 12.9898) * amount;

/** Posiciones simuladas de la flota de demostración en el instante `now`. */
export function demoSnapshot(now: number): TrackedVehicle[] {
  const seconds = now / 1000;
  return DEMO_VEHICLES.map((vehicle, index) => {
    const route = ROUTES[vehicle.destination];
    const base = {
      key: `demo-${vehicle.id}`,
      name: vehicle.id,
      vehicle,
      fixTime: new Date(now - ((index * 7) % 20) * 1000),
      address: null,
      battery: null
    };
    if (vehicle.status === 'En ruta' && route) {
      const fraction = (vehicle.progress / 100 + seconds / LOOP_SECONDS) % 1;
      const { point, course } = pointAlong(route, fraction);
      const speedKmh = Math.round(52 + jitter(index + Math.floor(seconds / 5), 14));
      return {
        ...base,
        status: statusFor(true, speedKmh),
        longitude: point[0],
        latitude: point[1],
        speedKmh,
        course,
        ignition: true
      };
    }
    const parked = vehicle.status === 'Mantenimiento' ? WORKSHOP : DISTRIBUTION_CENTER;
    return {
      ...base,
      status: vehicle.status === 'Mantenimiento' ? 'offline' : 'stopped',
      longitude: parked[0] + jitter(index, 0.0012),
      latitude: parked[1] + jitter(index + 3, 0.0009),
      speedKmh: 0,
      course: 0,
      ignition: false,
      fixTime: vehicle.status === 'Mantenimiento' ? new Date(now - 3 * 3600_000) : base.fixTime
    };
  });
}

export const demoRoute = (destination: string): LngLat[] | null => ROUTES[destination] ?? null;

/** Destinos que coinciden con sucursales reales, para que la ruta termine en el pin B. */
const BRANCH_DESTINATIONS: Record<string, LngLat> = {
  'Santa Rosa de Lima': [-87.89288, 13.62781],
  'La Unión': [-87.841365, 13.337231],
  Usulután: [-88.435998, 13.343138],
  Jiquilisco: [-88.57038, 13.32605],
  'El Tránsito': [-88.348507, 13.354792]
};

let demoRoutesRequested = false;

/**
 * Sustituye los trazos aproximados por rutas reales por calles. Se pide una sola vez
 * por sesión; si el servicio de rutas falla se conservan los trazos aproximados.
 */
export async function loadDemoRoutes(
  fetchRoute: (from: LngLat, to: LngLat) => Promise<{ coordinates: LngLat[]; source: string }>
): Promise<void> {
  if (demoRoutesRequested) return;
  demoRoutesRequested = true;
  await Promise.all(
    Object.entries(ROUTES).map(async ([destination, route]) => {
      const to = BRANCH_DESTINATIONS[destination] ?? route[route.length - 1]!;
      try {
        const real = await fetchRoute(SAN_MIGUEL, to);
        if (real.source === 'osrm' && real.coordinates.length > 1)
          ROUTES[destination] = real.coordinates;
      } catch {
        // Se queda el trazo aproximado.
      }
    })
  );
}
