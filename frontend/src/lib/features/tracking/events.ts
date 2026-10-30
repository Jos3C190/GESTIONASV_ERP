import type { TrackedVehicleOut, TrackingEventOut } from '$lib/api/client';

export type EventGroup = 'geofence' | 'speed' | 'engine' | 'alarm' | 'stop';
export type EventTone = 'info' | 'success' | 'warning' | 'danger';

export interface TrackingEvent {
  id: string;
  type: string;
  group: EventGroup;
  tone: EventTone;
  time: Date;
  vehicleName: string;
  vehicle: TrackedVehicleOut | null;
  title: string;
  detail: string | null;
  latitude: number | null;
  longitude: number | null;
}

export const EVENT_GROUPS: { id: 'all' | EventGroup; label: string }[] = [
  { id: 'all', label: 'Todos' },
  { id: 'geofence', label: 'Geocercas' },
  { id: 'speed', label: 'Velocidad' },
  { id: 'engine', label: 'Motor' },
  { id: 'alarm', label: 'Alarmas' }
];

const ALARMS: Record<string, string> = {
  sos: 'Botón de pánico',
  powerCut: 'Corte de energía',
  tampering: 'Manipulación del equipo',
  lowBattery: 'Batería baja',
  accident: 'Posible accidente',
  hardBraking: 'Frenado brusco',
  hardAcceleration: 'Aceleración brusca'
};

interface RawEvent {
  type: string;
  geofence_name: string | null;
  alarm: string | null;
  speed_kmh: number | null;
}

/** Título, detalle y estilo legibles para un tipo de evento de Traccar. */
export function describeEvent(
  event: RawEvent
): Pick<TrackingEvent, 'group' | 'tone' | 'title' | 'detail'> {
  const zone = event.geofence_name ?? 'geocerca';
  switch (event.type) {
    case 'geofenceEnter':
      return { group: 'geofence', tone: 'info', title: `Entró a ${zone}`, detail: null };
    case 'geofenceExit':
      return { group: 'geofence', tone: 'info', title: `Salió de ${zone}`, detail: null };
    case 'deviceOverspeed':
      return {
        group: 'speed',
        tone: 'danger',
        title: 'Exceso de velocidad',
        detail:
          [
            event.speed_kmh != null ? `${Math.round(event.speed_kmh)} km/h` : null,
            event.geofence_name
          ]
            .filter(Boolean)
            .join(' · ') || null
      };
    case 'ignitionOn':
      return { group: 'engine', tone: 'success', title: 'Motor encendido', detail: null };
    case 'ignitionOff':
      return { group: 'engine', tone: 'info', title: 'Motor apagado', detail: null };
    case 'deviceStopped':
      return { group: 'stop', tone: 'warning', title: 'Unidad detenida', detail: null };
    case 'maintenance':
      return { group: 'alarm', tone: 'warning', title: 'Mantenimiento requerido', detail: null };
    default:
      return {
        group: 'alarm',
        tone: 'danger',
        title: event.alarm ? (ALARMS[event.alarm] ?? `Alarma: ${event.alarm}`) : 'Alarma',
        detail: null
      };
  }
}

/** `vehicles` relaciona el id del dispositivo en Traccar con su vehículo de Flota. */
export function fromTraccarEvents(
  events: TrackingEventOut[],
  vehicles: ReadonlyMap<number, TrackedVehicleOut> = new Map()
): TrackingEvent[] {
  return events.map((event) => {
    const vehicle = vehicles.get(event.device_id) ?? null;
    return {
      id: `traccar-${event.id}`,
      type: event.type,
      ...describeEvent(event),
      time: event.event_time ? new Date(event.event_time) : new Date(0),
      vehicleName: vehicle?.code ?? event.device_name,
      vehicle,
      latitude: event.latitude,
      longitude: event.longitude
    };
  });
}
