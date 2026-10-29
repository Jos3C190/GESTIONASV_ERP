import type { TrackedTransferOut, TransferTrackOut } from '$lib/api/client';
import { demoRoute } from './demo';
import { distanceM } from './geofences';
import type { TrackedVehicle } from './tracking';

type LngLat = [number, number];

export interface TransferPlace {
  warehouse: string;
  branch: string;
  point: LngLat | null;
}

export interface TransferSummary {
  id: string;
  code: string;
  status: string;
  dispatchedAt: Date | null;
  vehicleCode: string | null;
  vehicleName: string | null;
  origin: TransferPlace;
  destination: TransferPlace;
}

export interface TransferTrack extends TransferSummary {
  gpsConfigured: boolean;
  deviceFound: boolean;
  route: LngLat[];
  routeSource: 'osrm' | 'straight' | 'demo';
  distanceM: number;
  trail: LngLat[];
  position: {
    latitude: number;
    longitude: number;
    speedKmh: number;
    course: number;
    fixTime: Date | null;
  } | null;
  progress: number;
  remainingM: number | null;
  eta: Date | null;
  arrived: boolean;
  offRoute: boolean;
}

const place = (value: TrackedTransferOut['origin']): TransferPlace => ({
  warehouse: value.warehouse_name,
  branch: value.branch_name,
  point:
    value.latitude !== null && value.longitude !== null ? [value.longitude, value.latitude] : null
});

const date = (value: string | null) => (value ? new Date(value) : null);

export function fromApiSummary(transfer: TrackedTransferOut): TransferSummary {
  return {
    id: transfer.id,
    code: transfer.code,
    status: transfer.status,
    dispatchedAt: date(transfer.dispatched_at),
    vehicleCode: transfer.vehicle_code,
    vehicleName: transfer.vehicle_name,
    origin: place(transfer.origin),
    destination: place(transfer.destination)
  };
}

export function fromApiTrack(track: TransferTrackOut): TransferTrack {
  return {
    ...fromApiSummary(track),
    gpsConfigured: track.gps_configured,
    deviceFound: track.device_found,
    route: track.route?.coordinates ?? [],
    routeSource: track.route?.source ?? 'straight',
    distanceM: track.route?.distance_m ?? 0,
    trail: track.trail,
    position: track.position
      ? {
          latitude: track.position.latitude,
          longitude: track.position.longitude,
          speedKmh: track.position.speed_kmh,
          course: track.position.course,
          fixTime: date(track.position.fix_time)
        }
      : null,
    progress: track.progress,
    remainingM: track.remaining_m,
    eta: date(track.eta),
    arrived: track.arrived,
    offRoute: track.off_route
  };
}

/** Distancia recorrida a lo largo de la ruta hasta el punto más cercano a `point`. */
export function travelledAlong(
  route: LngLat[],
  point: LngLat
): { along: LngLat[]; meters: number } {
  let best = { distance: Infinity, index: 0, projected: route[0] ?? point, meters: 0 };
  let travelled = 0;
  for (let i = 0; i < route.length - 1; i++) {
    const start = route[i]!;
    const end = route[i + 1]!;
    const scale = Math.cos((point[1] * Math.PI) / 180);
    const dx = (end[0] - start[0]) * scale;
    const dy = end[1] - start[1];
    const length2 = dx * dx + dy * dy;
    const t =
      length2 === 0
        ? 0
        : Math.max(
            0,
            Math.min(1, ((point[0] - start[0]) * scale * dx + (point[1] - start[1]) * dy) / length2)
          );
    const projected: LngLat = [
      start[0] + (end[0] - start[0]) * t,
      start[1] + (end[1] - start[1]) * t
    ];
    const segment = distanceM(start, end);
    const distance = distanceM(point, projected);
    if (distance < best.distance)
      best = { distance, index: i, projected, meters: travelled + segment * t };
    travelled += segment;
  }
  return { along: [...route.slice(0, best.index + 1), best.projected], meters: best.meters };
}

const routeLength = (route: LngLat[]) =>
  route.slice(1).reduce((sum, point, i) => sum + distanceM(route[i]!, point), 0);

const ROOSEVELT: TransferPlace = {
  warehouse: 'Bodega central Roosevelt',
  branch: 'Pastelería Lorena Roosevelt',
  point: [-88.185666, 13.483663]
};

const DEMO_TRANSFERS: {
  id: string;
  code: string;
  vehicle: string;
  destination: TransferPlace;
  minutesAgo: number;
}[] = [
  {
    id: 'demo-tr-1',
    code: 'TR-2026-0141',
    vehicle: 'FL-001',
    destination: {
      warehouse: 'Bodega Santa Rosa',
      branch: 'Pastelería Lorena Santa Rosa de Lima',
      point: [-87.89288, 13.62781]
    },
    minutesAgo: 38
  },
  {
    id: 'demo-tr-2',
    code: 'TR-2026-0142',
    vehicle: 'FL-003',
    destination: {
      warehouse: 'Bodega La Unión',
      branch: 'Pastelería Lorena La Unión',
      point: [-87.841365, 13.337231]
    },
    minutesAgo: 22
  },
  {
    id: 'demo-tr-3',
    code: 'TR-2026-0143',
    vehicle: 'FL-004',
    destination: {
      warehouse: 'Bodega Usulután',
      branch: 'Pastelería Lorena Usulután',
      point: [-88.435998, 13.343138]
    },
    minutesAgo: 51
  }
];

const DESTINATION_ROUTE: Record<string, string> = {
  'FL-001': 'Santa Rosa de Lima',
  'FL-003': 'La Unión',
  'FL-004': 'Usulután'
};

/** Traslados simulados que siguen a las unidades de la demostración. */
export function demoTransferTracks(vehicles: TrackedVehicle[], now: number): TransferTrack[] {
  return DEMO_TRANSFERS.map((demo) => {
    const vehicle = vehicles.find((item) => item.name === demo.vehicle);
    const route = demoRoute(DESTINATION_ROUTE[demo.vehicle]!) ?? [];
    const total = routeLength(route);
    const point: LngLat | null = vehicle ? [vehicle.longitude, vehicle.latitude] : null;
    const travelled = point ? travelledAlong(route, point) : { along: [], meters: 0 };
    const remaining = Math.max(total - travelled.meters, 0);
    const speed = vehicle?.speedKmh || 50;
    return {
      id: demo.id,
      code: demo.code,
      status: 'in_transit',
      dispatchedAt: new Date(now - demo.minutesAgo * 60_000),
      vehicleCode: demo.vehicle,
      vehicleName: vehicle?.vehicle?.model ?? null,
      origin: ROOSEVELT,
      destination: demo.destination,
      gpsConfigured: false,
      deviceFound: !!vehicle,
      route,
      routeSource: 'demo',
      distanceM: total,
      trail: travelled.along,
      position: vehicle
        ? {
            latitude: vehicle.latitude,
            longitude: vehicle.longitude,
            speedKmh: vehicle.speedKmh,
            course: vehicle.course,
            fixTime: vehicle.fixTime
          }
        : null,
      progress: total ? Math.min(travelled.meters / total, 1) : 0,
      remainingM: remaining,
      eta: new Date(now + (remaining / 1000 / speed) * 3_600_000),
      arrived: false,
      offRoute: false
    };
  });
}

export function formatDistance(meters: number | null): string {
  if (meters === null) return '—';
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

export function formatClock(value: Date | null): string {
  if (!value) return '—';
  return new Intl.DateTimeFormat('es-SV', { hour: '2-digit', minute: '2-digit' }).format(value);
}
