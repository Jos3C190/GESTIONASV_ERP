import type { TrackedTransferOut, TransferTrackOut } from '$lib/api/client';

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
  vehiclePlate: string | null;
  driverName: string | null;
  origin: TransferPlace;
  destination: TransferPlace;
}

export interface TransferTrack extends TransferSummary {
  gpsConfigured: boolean;
  deviceFound: boolean;
  route: LngLat[];
  routeSource: 'osrm' | 'straight';
  distanceM: number;
  trail: LngLat[];
  /** El recorrido está ajustado a las calles (map matching). */
  trailMatched: boolean;
  /** Ruta que falta, desde la unidad hasta el destino (planeada o recalculada). */
  remainingRoute: LngLat[];
  /** La unidad se desvió y la ruta se recalculó desde su posición. */
  rerouted: boolean;
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
    vehiclePlate: transfer.vehicle_plate ?? null,
    driverName: transfer.driver_name ?? null,
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
    trailMatched: track.trail_matched,
    remainingRoute: track.remaining_route,
    rerouted: track.rerouted,
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

export function formatDistance(meters: number | null): string {
  if (meters === null) return '—';
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

export function formatClock(value: Date | null): string {
  if (!value) return '—';
  return new Intl.DateTimeFormat('es-SV', { hour: '2-digit', minute: '2-digit' }).format(value);
}
