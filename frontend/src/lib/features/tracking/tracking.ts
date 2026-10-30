import type { TrackedDeviceOut, TrackedVehicleOut } from '$lib/api/client';

export type TrackingStatus = 'moving' | 'stopped' | 'offline';

export interface TrackedVehicle {
  key: string;
  /** Código de flota (FL-001) del vehículo vinculado al dispositivo. */
  name: string;
  vehicle: TrackedVehicleOut | null;
  status: TrackingStatus;
  latitude: number;
  longitude: number;
  speedKmh: number;
  course: number;
  fixTime: Date | null;
  address: string | null;
  ignition: boolean | null;
  battery: number | null;
}

/** Velocidad mínima para considerar que la unidad está en movimiento. */
export const MOVING_THRESHOLD_KMH = 3;

export const STATUS_LABELS: Record<TrackingStatus, string> = {
  moving: 'En movimiento',
  stopped: 'Detenido',
  offline: 'Sin señal'
};

export function statusFor(online: boolean, speedKmh: number): TrackingStatus {
  if (!online) return 'offline';
  return speedKmh > MOVING_THRESHOLD_KMH ? 'moving' : 'stopped';
}

/** Convierte la respuesta del backend en vehículos para el mapa; omite los que aún no reportan posición. */
export function fromTraccar(devices: TrackedDeviceOut[]): TrackedVehicle[] {
  return devices.flatMap((device) => {
    const position = device.position;
    if (!position) return [];
    return [
      {
        key: `traccar-${device.id}`,
        name: device.vehicle?.code ?? device.name,
        vehicle: device.vehicle,
        status: statusFor(device.status === 'online', position.speed_kmh),
        latitude: position.latitude,
        longitude: position.longitude,
        speedKmh: position.speed_kmh,
        course: position.course,
        fixTime: position.fix_time ? new Date(position.fix_time) : null,
        address: position.address,
        ignition: position.ignition,
        battery: position.battery_level
      }
    ];
  });
}

const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO'];

export const compassPoint = (course: number) =>
  COMPASS[Math.round((((course % 360) + 360) % 360) / 45) % 8]!;

export function timeAgo(date: Date | null, now: number): string {
  if (!date) return 'Sin datos';
  const seconds = Math.max(0, Math.round((now - date.getTime()) / 1000));
  if (seconds < 60) return `hace ${seconds} s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  return `hace ${Math.round(hours / 24)} d`;
}
