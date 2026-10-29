import type { TrackingEventOut } from '$lib/api/client';
import { DEMO_VEHICLES, type FleetVehicle } from '$lib/features/fleet/mock-data';
import { matchFleetVehicle } from './tracking';

export type EventGroup = 'geofence' | 'speed' | 'engine' | 'alarm' | 'stop';
export type EventTone = 'info' | 'success' | 'warning' | 'danger';

export interface TrackingEvent {
  id: string;
  type: string;
  group: EventGroup;
  tone: EventTone;
  time: Date;
  vehicleName: string;
  vehicle: FleetVehicle | null;
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

export function fromTraccarEvents(events: TrackingEventOut[]): TrackingEvent[] {
  return events.map((event) => {
    const vehicle = matchFleetVehicle({
      name: event.device_name,
      unique_id: event.device_unique_id
    });
    return {
      id: `traccar-${event.id}`,
      type: event.type,
      ...describeEvent(event),
      time: event.event_time ? new Date(event.event_time) : new Date(0),
      vehicleName: vehicle?.id ?? event.device_name,
      vehicle,
      latitude: event.latitude,
      longitude: event.longitude
    };
  });
}

type DemoScript = [
  vehicleId: string,
  type: string,
  minutesAgo: number,
  extra?: Partial<RawEvent> & { at?: [number, number] }
];

const DEMO_SCRIPT: DemoScript[] = [
  ['FL-012', 'deviceOverspeed', 4, { speed_kmh: 96, at: [-88.62, 13.58] }],
  [
    'FL-002',
    'geofenceEnter',
    11,
    { geofence_name: 'Centro de distribución', at: [-88.177, 13.4795] }
  ],
  ['FL-003', 'geofenceExit', 23, { geofence_name: 'Zona urbana San Miguel', at: [-88.146, 13.47] }],
  ['FL-004', 'deviceStopped', 37, { at: [-88.35, 13.38] }],
  ['FL-011', 'ignitionOn', 52, { at: [-88.1833, 13.4833] }],
  [
    'FL-007',
    'deviceOverspeed',
    68,
    { speed_kmh: 58, geofence_name: 'Zona urbana San Miguel', at: [-88.2, 13.48] }
  ],
  ['FL-005', 'geofenceEnter', 95, { geofence_name: 'Taller central', at: [-88.17, 13.49] }],
  ['FL-005', 'ignitionOff', 97, { at: [-88.17, 13.49] }],
  ['FL-013', 'alarm', 140, { alarm: 'lowBattery', at: [-88.17, 13.49] }],
  [
    'FL-001',
    'geofenceExit',
    180,
    { geofence_name: 'Centro de distribución', at: [-88.172, 13.483] }
  ]
];

/** Eventos de la vista de demostración, relativos a `now`. */
export function demoEvents(now: number): TrackingEvent[] {
  return DEMO_SCRIPT.map(([vehicleId, type, minutesAgo, extra = {}], index) => {
    const vehicle = DEMO_VEHICLES.find((item) => item.id === vehicleId) ?? null;
    return {
      id: `demo-${index}`,
      type,
      ...describeEvent({
        type,
        geofence_name: extra.geofence_name ?? null,
        alarm: extra.alarm ?? null,
        speed_kmh: extra.speed_kmh ?? null
      }),
      time: new Date(now - minutesAgo * 60_000),
      vehicleName: vehicleId,
      vehicle,
      longitude: extra.at?.[0] ?? null,
      latitude: extra.at?.[1] ?? null
    };
  });
}

/** Eventos que aparecen “en vivo” durante la demostración, en rotación. */
const DEMO_LIVE: DemoScript[] = [
  ['FL-009', 'deviceOverspeed', 0, { speed_kmh: 88, at: [-88.3, 13.38] }],
  ['FL-006', 'geofenceExit', 0, { geofence_name: 'Centro de distribución', at: [-88.17, 13.483] }],
  [
    'FL-003',
    'geofenceEnter',
    0,
    { geofence_name: 'Cliente · Puerto de La Unión', at: [-87.8439, 13.3369] }
  ],
  ['FL-008', 'ignitionOn', 0, { at: [-88.177, 13.4795] }]
];

export function demoLiveEvent(sequence: number, now: number): TrackingEvent {
  const [vehicleId, type, , extra = {}] = DEMO_LIVE[sequence % DEMO_LIVE.length]!;
  return {
    ...demoEvents(now)[0]!,
    id: `demo-live-${sequence}`,
    type,
    ...describeEvent({
      type,
      geofence_name: extra.geofence_name ?? null,
      alarm: extra.alarm ?? null,
      speed_kmh: extra.speed_kmh ?? null
    }),
    time: new Date(now),
    vehicleName: vehicleId,
    vehicle: DEMO_VEHICLES.find((item) => item.id === vehicleId) ?? null,
    longitude: extra.at?.[0] ?? null,
    latitude: extra.at?.[1] ?? null
  };
}
