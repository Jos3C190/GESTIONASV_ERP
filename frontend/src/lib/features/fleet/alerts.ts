import {
  FLEET_TODAY,
  VEHICLE_DOCUMENTS,
  type FleetVehicle,
  type VehicleDocument
} from './mock-data';

export type AlertTone = 'danger' | 'warning';

export interface VehicleAlert {
  tone: AlertTone;
  label: string;
  /** Días hasta el vencimiento; negativo si ya venció. */
  days: number;
}

/** Ventanas de aviso antes del vencimiento. */
export const DOCUMENT_WARNING_DAYS = 30;
export const SERVICE_WARNING_DAYS = 7;

const DAY_MS = 86_400_000;

export const daysUntil = (iso: string, today = FLEET_TODAY) =>
  Math.round((Date.parse(iso) - Date.parse(today)) / DAY_MS);

const inDays = (days: number) =>
  days === 0 ? 'hoy' : days === 1 ? 'mañana' : `en ${days} días`;

function documentAlert(document: VehicleDocument, today: string): VehicleAlert | null {
  const { short, feminine } = VEHICLE_DOCUMENTS[document.kind];
  const days = daysUntil(document.expires, today);
  if (days < 0) return { tone: 'danger', label: `${short} ${feminine ? 'vencida' : 'vencido'}`, days };
  if (days <= DOCUMENT_WARNING_DAYS) return { tone: 'warning', label: `${short} vence ${inDays(days)}`, days };
  return null;
}

function serviceAlert(serviceDue: string | null, today: string): VehicleAlert | null {
  if (!serviceDue) return null;
  const days = daysUntil(serviceDue, today);
  if (days < 0) return { tone: 'danger', label: 'Servicio vencido', days };
  if (days <= SERVICE_WARNING_DAYS) return { tone: 'warning', label: `Servicio ${inDays(days)}`, days };
  return null;
}

/** Alertas del vehículo, primero las vencidas y luego las más próximas. */
export function vehicleAlerts(vehicle: FleetVehicle, today = FLEET_TODAY): VehicleAlert[] {
  return [
    serviceAlert(vehicle.serviceDue, today),
    ...vehicle.documents.map((document) => documentAlert(document, today))
  ]
    .filter((alert): alert is VehicleAlert => alert !== null)
    .sort((a, b) => (a.tone === b.tone ? a.days - b.days : a.tone === 'danger' ? -1 : 1));
}

export type DocumentState = { tone: AlertTone | 'ok'; label: string };

export function documentState(document: VehicleDocument, today = FLEET_TODAY): DocumentState {
  const days = daysUntil(document.expires, today);
  if (days < 0) return { tone: 'danger', label: 'Vencido' };
  if (days <= DOCUMENT_WARNING_DAYS) return { tone: 'warning', label: `Vence ${inDays(days)}` };
  return { tone: 'ok', label: 'Vigente' };
}
