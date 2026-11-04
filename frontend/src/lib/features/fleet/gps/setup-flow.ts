import type { GpsReadings, GpsStatus } from '../api';

export type DeviceKind = 'phone' | 'tracker';
export type SetupStep =
  'kind' | 'install' | 'scan' | 'permissions' | 'model' | 'identifier' | 'configure' | 'signal';

const PATHS: Record<DeviceKind, SetupStep[]> = {
  phone: ['kind', 'install', 'scan', 'permissions', 'signal'],
  tracker: ['kind', 'model', 'identifier', 'configure', 'signal']
};

export const TOTAL_STEPS = 5;
export const OTHER_MODEL = 'other';
/** Tras este tiempo sin señal se ofrece la lista de qué revisar. */
export const HELP_AFTER_MS = 120_000;
export const WIZARD_POLL_MS = 5_000;
export const CARD_POLL_MS = 30_000;

export const ANDROID_APP = 'https://play.google.com/store/apps/details?id=org.traccar.client';
export const IOS_APP = 'https://itunes.apple.com/us/app/traccar-client/id843156974';
export const SUPPORTED_DEVICES = 'https://www.traccar.org/devices/';

export function stepNumber(kind: DeviceKind | null, step: SetupStep): number {
  return kind ? PATHS[kind].indexOf(step) + 1 : 1;
}

export function nextStep(kind: DeviceKind, step: SetupStep): SetupStep {
  const path = PATHS[kind];
  return path[path.indexOf(step) + 1] ?? step;
}

export function previousStep(kind: DeviceKind, step: SetupStep): SetupStep {
  const path = PATHS[kind];
  return path[path.indexOf(step) - 1] ?? step;
}

/** Dónde retomar: lo ya hecho no se repite, y de un GPS no se guarda el modelo. */
export function resumeStep(kind: DeviceKind): SetupStep {
  return kind === 'phone' ? 'scan' : 'model';
}

/** El IMEI suele copiarse con espacios; el equipo lo envía sin ellos. */
export function cleanIdentifier(value: string): string {
  return value.replace(/\s/g, '');
}

export function validIdentifier(value: string): boolean {
  return /^[A-Za-z0-9._-]{3,64}$/.test(cleanIdentifier(value));
}

/** El backend genera estos para los teléfonos; no se escriben a mano. */
export function isPhoneIdentifier(value: string | null): boolean {
  return Boolean(value?.startsWith('GS-'));
}

export function detectPlatform(userAgent: string): 'android' | 'ios' | 'other' {
  if (/android/i.test(userAgent)) return 'android';
  if (/iphone|ipad|ipod/i.test(userAgent)) return 'ios';
  return 'other';
}

export function timeAgo(iso: string, now: number): string {
  const minutes = Math.floor((now - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return 'hace un momento';
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.floor(hours / 24);
  return days === 1 ? 'hace 1 día' : `hace ${days} días`;
}

export type CardTone = 'neutral' | 'waiting' | 'good' | 'warning';
export type CardAction = 'connect' | 'resume' | 'track' | 'help' | 'retry' | null;

export interface CardView {
  tone: CardTone;
  title: string;
  detail: string;
  action: CardAction;
}

function unlinkedView(status: GpsStatus, canManage: boolean, retired: boolean): CardView {
  const base = { tone: 'neutral', title: 'Este vehículo no tiene GPS', action: null } as const;
  if (retired) return { ...base, detail: 'El vehículo está dado de baja.' };
  if (!status.server_configured) {
    return {
      ...base,
      title: 'Falta configurar el servidor GPS',
      detail: 'Pídele al administrador que configure la dirección del servidor.'
    };
  }
  return canManage
    ? {
        ...base,
        detail: 'Conecta el teléfono del conductor o un GPS instalado para verlo en Seguimiento.',
        action: 'connect'
      }
    : { ...base, detail: 'Pídele a quien administra la flota que lo conecte.' };
}

export function cardView(
  status: GpsStatus | null,
  now: number,
  canManage = true,
  retired = false
): CardView {
  const seen = status?.last_update ? timeAgo(status.last_update, now) : null;
  if (!status) {
    return {
      tone: 'warning',
      title: 'No pudimos consultar el estado',
      detail: 'Revisa tu conexión y vuelve a intentarlo.',
      action: 'retry'
    };
  }
  switch (status.state) {
    case 'unlinked':
      return unlinkedView(status, canManage, retired);
    case 'waiting':
      return {
        tone: 'waiting',
        title: 'Esperando la primera señal',
        detail: 'Ya está registrado, pero aún no recibimos su ubicación.',
        action: 'resume'
      };
    case 'reporting':
      return {
        tone: 'good',
        title: 'GPS activo',
        detail: `Última señal ${seen}.`,
        action: 'track'
      };
    case 'silent':
      return {
        tone: 'warning',
        title: 'Sin señal reciente',
        detail: `Última señal ${seen}.`,
        action: 'help'
      };
    default:
      return {
        tone: 'warning',
        title: 'No pudimos comprobar la señal',
        detail: 'El servidor GPS no responde ahora. Vuelve a intentarlo en un momento.',
        action: 'retry'
      };
  }
}

export function troubleshooting(kind: DeviceKind, privateNetwork: boolean): string[] {
  const network = privateNetwork
    ? ['Debe estar dentro de la red de la empresa: con datos móviles no llegará la ubicación.']
    : [];
  return kind === 'phone'
    ? [
        'En Traccar Client, el interruptor de seguimiento está encendido.',
        'La app puede usar la ubicación todo el tiempo.',
        'En Android, la batería de la app está sin restricciones.',
        'El teléfono tiene internet.',
        ...network
      ]
    : [
        'El GPS está encendido, y su chip activo y con datos.',
        'El servidor y el puerto son los de “Revisar datos”.',
        'El identificador es el de su etiqueta. Corrígelo en “Revisar datos”.',
        ...network
      ];
}

function formatReading(value: number, digits = 1): string {
  return value.toLocaleString('es-SV', { maximumFractionDigits: digits });
}

/** Solo lo que el equipo envió, en el orden en que más importa al leerlo. */
export function readingRows(readings: GpsReadings | undefined): { label: string; value: string }[] {
  if (!readings) return [];
  const { ignition, voltage, temperature, engine_hours: hours, satellites } = readings;
  return [
    ignition === undefined ? null : { label: 'Motor', value: ignition ? 'Encendido' : 'Apagado' },
    temperature === undefined
      ? null
      : { label: 'Temperatura', value: `${formatReading(temperature)} °C` },
    voltage === undefined
      ? null
      : { label: 'Voltaje del vehículo', value: `${formatReading(voltage)} V` },
    hours === undefined ? null : { label: 'Horas de motor', value: `${formatReading(hours, 0)} h` },
    satellites === undefined ? null : { label: 'Satélites', value: formatReading(satellites, 0) }
  ].filter((row) => row !== null);
}
