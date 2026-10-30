/**
 * Herramientas de simulación de Seguimiento (solo cuando el servidor las habilita).
 *
 * El navegador no inventa posiciones para el mapa: maneja un GPS virtual que el
 * backend reporta a Traccar como la app de un conductor. Aquí vive lo puro: la
 * física del joystick, el teclado y los textos del estado de una sesión.
 */
import type { SimulationOut } from '$lib/api/client';

type LngLat = [number, number];

const EARTH_RADIUS_M = 6_371_000;
/** Aceleración, freno y desaceleración sin acelerar (km/h por segundo). */
export const ACCEL_KMH_S = 14;
export const BRAKE_KMH_S = 32;
export const COAST_KMH_S = 5;
/** Giro máximo (°/s) y velocidad a la que se alcanza: a baja velocidad se gira menos. */
export const MAX_YAW_DEG_S = 70;
const FULL_YAW_KMH = 25;
/** Cada cuánto se envía la posición manejada al servidor (Traccar Client usa ~1 s). */
export const DRIVE_SEND_MS = 1000;

export const SPEED_PRESETS = [20, 40, 60, 90, 120] as const;
export const STOP_PRESETS = [5, 25] as const;
export const SIGNAL_PRESETS = [3, 12] as const;

export interface DriveState {
  lngLat: LngLat;
  course: number;
  speedKmh: number;
}

export interface DriveInput {
  /** -1 (freno) … 1 (acelerador). */
  throttle: number;
  /** -1 (izquierda) … 1 (derecha). */
  steer: number;
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export function offsetPoint(point: LngLat, course: number, meters: number): LngLat {
  const angular = meters / EARTH_RADIUS_M;
  const heading = (course * Math.PI) / 180;
  const lat1 = (point[1] * Math.PI) / 180;
  const lng1 = (point[0] * Math.PI) / 180;
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(angular) + Math.cos(lat1) * Math.sin(angular) * Math.cos(heading)
  );
  const lng2 =
    lng1 +
    Math.atan2(
      Math.sin(heading) * Math.sin(angular) * Math.cos(lat1),
      Math.cos(angular) - Math.sin(lat1) * Math.sin(lat2)
    );
  return [((((lng2 * 180) / Math.PI + 540) % 360) - 180) as number, (lat2 * 180) / Math.PI];
}

/** Avanza el vehículo `dt` segundos: acelera hasta `maxKmh`, frena y gira como un auto. */
export function driveStep(state: DriveState, input: DriveInput, dt: number, maxKmh: number) {
  const throttle = clamp(input.throttle, -1, 1);
  const steer = clamp(input.steer, -1, 1);
  let speed = state.speedKmh;
  if (throttle > 0) {
    const target = maxKmh * throttle;
    speed =
      speed < target
        ? Math.min(target, speed + ACCEL_KMH_S * dt)
        : Math.max(target, speed - COAST_KMH_S * dt);
  } else if (throttle < 0) {
    speed = Math.max(0, speed + BRAKE_KMH_S * throttle * dt);
  } else {
    speed = Math.max(0, speed - COAST_KMH_S * dt);
  }
  const yaw = steer * MAX_YAW_DEG_S * Math.min(1, speed / FULL_YAW_KMH);
  const course = (((state.course + yaw * dt) % 360) + 360) % 360;
  const meters = (((state.speedKmh + speed) / 2) * dt) / 3.6;
  return {
    lngLat: meters > 0 ? offsetPoint(state.lngLat, course, meters) : state.lngLat,
    course,
    speedKmh: speed
  } satisfies DriveState;
}

/** Teclas de manejo: WASD o flechas; espacio frena. */
export function inputFromKeys(pressed: ReadonlySet<string>): DriveInput {
  const has = (...keys: string[]) => keys.some((key) => pressed.has(key));
  const brake = has(' ', 's', 'arrowdown');
  return {
    throttle: brake ? -1 : has('w', 'arrowup') ? 1 : 0,
    steer: (has('d', 'arrowright') ? 1 : 0) - (has('a', 'arrowleft') ? 1 : 0)
  };
}

export const DRIVE_KEYS = new Set([
  'w',
  'a',
  's',
  'd',
  ' ',
  'arrowup',
  'arrowdown',
  'arrowleft',
  'arrowright'
]);

/** El atajo no debe robar teclas mientras se escribe en un campo. */
export function typingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (!element) return false;
  return (
    element.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(element.tagName ?? '')
  );
}

/** Estado legible de una sesión y su tono para la interfaz. */
export function sessionStatus(
  session: SimulationOut,
  now: number
): { label: string; tone: 'live' | 'hold' | 'lost' | 'done' } {
  const until = (value: string | null) => (value ? new Date(value).getTime() - now : 0);
  if (until(session.signal_lost_until) > 0)
    return { label: `Sin señal · ${countdown(until(session.signal_lost_until))}`, tone: 'lost' };
  const returning = session.leg === 'return';
  if (session.state === 'arrived')
    return { label: returning ? 'De vuelta en el inicio' : 'Llegó al destino', tone: 'done' };
  if (session.state === 'paused') return { label: 'En pausa', tone: 'hold' };
  if (until(session.stop_until) > 0)
    return { label: `Detenida · ${countdown(until(session.stop_until))}`, tone: 'hold' };
  if (session.mode === 'joystick') return { label: 'Manejo manual', tone: 'live' };
  const speed = `${Math.round(session.current_speed_kmh)} km/h`;
  return { label: returning ? `Regresando · ${speed}` : `En ruta · ${speed}`, tone: 'live' };
}

export function countdown(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

/** Botones de ida y vuelta que tienen sentido en el estado actual de la sesión. */
export function roundTripActions(
  session: SimulationOut
): ('return' | 'outbound' | 'take_control')[] {
  const hasOutbound = session.stops.length >= 2;
  if (session.mode === 'joystick') return ['return'];
  const actions: ('return' | 'outbound' | 'take_control')[] = [];
  if (session.leg === 'outbound') actions.push('return');
  else if (hasOutbound) actions.push('outbound');
  // Una sesión que empezó con joystick vuelve a él al terminar de regresar.
  if (!hasOutbound) actions.push('take_control');
  return actions;
}

export const ROUND_TRIP_LABELS = {
  return: 'Regresar al inicio',
  outbound: 'Salir de nuevo',
  take_control: 'Tomar el control'
} as const;

export function progressOf(session: SimulationOut): number {
  if (session.mode !== 'route' || session.route_length_m <= 0) return 0;
  return clamp(session.progress_m / session.route_length_m, 0, 1);
}

export function formatDistance(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

/** Clave del marcador del mapa para el GPS virtual de una sesión. */
export const sessionKey = (session: Pick<SimulationOut, 'traccar_device_id'>) =>
  `traccar-${session.traccar_device_id}`;
