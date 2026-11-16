import type {
  Channel,
  ConsentPurpose,
  RequestAction,
  RequestStatus,
  RightType
} from '$lib/types/privacy';

export const RIGHT_LABELS: Record<RightType, string> = {
  access: 'Acceso',
  rectification: 'Rectificación',
  cancellation: 'Cancelación',
  opposition: 'Oposición',
  portability: 'Portabilidad',
  erasure: 'Olvido',
  restriction: 'Limitación'
};

export const STATUS_LABELS: Record<RequestStatus, string> = {
  received: 'Recibida',
  in_progress: 'En trámite',
  awaiting_correction: 'Esperando corrección',
  extended: 'Prorrogada',
  resolved: 'Atendida',
  denied: 'Denegada',
  returned: 'Devuelta',
  archived: 'Archivada'
};

export const STATUS_TONES: Record<RequestStatus, 'neutral' | 'warning' | 'success' | 'danger'> = {
  received: 'neutral',
  in_progress: 'neutral',
  awaiting_correction: 'warning',
  extended: 'warning',
  resolved: 'success',
  denied: 'danger',
  returned: 'neutral',
  archived: 'neutral'
};

export const PURPOSE_LABELS: Record<ConsentPurpose, string> = {
  marketing: 'Promociones y novedades',
  profiling: 'Análisis de preferencias de compra',
  third_party_sharing: 'Compartir datos con terceros'
};

export const CHANNEL_LABELS: Record<Channel, string> = {
  in_person: 'En persona',
  phone: 'Teléfono',
  email: 'Correo',
  web: 'Sitio web',
  written: 'Por escrito'
};

/** Acciones que ofrece la bandeja según el estado, en orden de uso habitual. */
export const ACTIONS_BY_STATUS: Record<RequestStatus, RequestAction[]> = {
  received: ['start', 'request_correction', 'extend', 'resolve', 'deny', 'return'],
  in_progress: ['request_correction', 'extend', 'resolve', 'deny', 'return'],
  awaiting_correction: ['correction_received', 'archive'],
  extended: ['resolve', 'deny'],
  resolved: [],
  denied: [],
  returned: [],
  archived: []
};

export const ACTION_LABELS: Record<RequestAction, string> = {
  start: 'Iniciar trámite',
  request_correction: 'Pedir corrección al titular',
  correction_received: 'El titular corrigió',
  extend: 'Prorrogar 20 días hábiles',
  resolve: 'Responder y cerrar',
  deny: 'Denegar',
  return: 'Devolver',
  archive: 'Archivar'
};

/** Qué texto pide cada acción, o `null` si no necesita. */
export const ACTION_TEXT: Record<RequestAction, string | null> = {
  start: null,
  request_correction: 'Qué debe corregir o completar el titular',
  correction_received: null,
  extend: 'Causa justificada de la prórroga',
  resolve: 'Respuesta que se comunica al titular',
  deny: 'Motivo de la negativa (resolución motivada)',
  return: 'Motivo de la devolución',
  archive: 'Motivo del archivo'
};

const DATE = new Intl.DateTimeFormat('es-SV', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: 'America/El_Salvador'
});
const DATE_TIME = new Intl.DateTimeFormat('es-SV', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'America/El_Salvador'
});

/** `YYYY-MM-DD` (fecha sin hora) a `DD/MM/YYYY`. */
export function formatDay(value: string | null): string {
  if (!value) return '—';
  const [year, month, day] = value.slice(0, 10).split('-');
  return `${day}/${month}/${year}`;
}

export function formatMoment(value: string | null): string {
  if (!value) return '—';
  return DATE_TIME.format(new Date(value));
}

export function formatDateOnly(value: string | null): string {
  if (!value) return '—';
  return DATE.format(new Date(value));
}

/** Hoy en El Salvador como `YYYY-MM-DD`. */
export function todayInElSalvador(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/El_Salvador',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(now);
  return parts;
}

/** Valor de `<input type="datetime-local">` en hora de El Salvador (UTC-6, sin horario de verano). */
export function toLocalInput(value: string | null): string {
  if (!value) return '';
  const shifted = new Date(new Date(value).getTime() - 6 * 60 * 60 * 1000);
  return shifted.toISOString().slice(0, 16);
}

export function fromLocalInput(value: string): string | null {
  if (!value) return null;
  return new Date(`${value}:00-06:00`).toISOString();
}
