import type {
  FiscalDocument,
  FiscalDocumentStatus,
  FiscalDocumentType,
  FiscalEmailStatus,
  FiscalNature
} from '#lib/types/sales-invoices.ts';

export const FISCAL_DOCUMENT_LABELS: Record<FiscalDocumentType, string> = {
  '01': 'Factura',
  '03': 'Crédito fiscal',
  '05': 'Nota de crédito',
  '06': 'Nota de débito'
};

export const NATURE_LABELS: Record<FiscalNature, string> = {
  taxed: 'Gravado',
  exempt: 'Exento',
  not_subject: 'No sujeto'
};

export const NOTE_LINE_KIND_LABELS: Record<string, string> = {
  return: 'Devolución',
  discount: 'Rebaja',
  charge: 'Cargo'
};

/** Una nota que se puede anular (tipo 2) pero no corregir. */
export function isNote(document: Pick<FiscalDocument, 'document_type'>): boolean {
  return document.document_type === '05' || document.document_type === '06';
}

/** Estados de una nota que cuentan para el saldo del CCF y bloquean anularlo. */
export function isVigent(document: Pick<FiscalDocument, 'status'>): boolean {
  return ['pending', 'contingency', 'issued', 'simulated'].includes(document.status);
}

export const FISCAL_STATUS_LABELS: Record<FiscalDocumentStatus, string> = {
  pending: 'Emitiendo',
  contingency: 'En contingencia',
  issued: 'Emitido',
  simulated: 'Simulado',
  rejected: 'Rechazado',
  failed: 'Falló',
  invalidated: 'Invalidado'
};

export const FISCAL_STATUS_BADGES: Record<FiscalDocumentStatus, string> = {
  pending: 'bg-warning/10 text-warning',
  contingency: 'bg-warning/10 text-warning',
  issued: 'bg-success/10 text-success',
  simulated: 'bg-primary/10 text-primary',
  rejected: 'bg-danger/10 text-danger',
  failed: 'bg-danger/10 text-danger',
  invalidated: 'bg-surface-muted text-foreground-muted'
};

export const FISCAL_STATUS_FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'Todos' },
  { value: 'pending', label: 'Emitiendo' },
  { value: 'contingency', label: 'En contingencia' },
  { value: 'issued', label: 'Emitidos' },
  { value: 'simulated', label: 'Simulados' },
  { value: 'rejected', label: 'Rechazados' },
  { value: 'failed', label: 'Fallidos' },
  { value: 'invalidated', label: 'Invalidados' }
];

export const FISCAL_MODE_LABELS: Record<string, string> = {
  simulated: 'Simulado (sin validez fiscal)',
  'hacienda-test': 'Pruebas de Hacienda',
  production: 'Producción'
};

/** Un documento que se puede volver a enviar con la misma clave. */
export function canRetry(document: Pick<FiscalDocument, 'status'>): boolean {
  return document.status === 'failed' || document.status === 'pending';
}

/** Un documento con resultado definitivo del servicio. */
export function isFinal(document: Pick<FiscalDocument, 'status'>): boolean {
  return document.status !== 'pending';
}

export const EMAIL_STATUS_LABELS: Record<FiscalEmailStatus, string> = {
  pending: 'Enviando',
  sent: 'Enviado',
  failed: 'No se envió'
};

export const EMAIL_STATUS_BADGES: Record<FiscalEmailStatus, string> = {
  pending: 'bg-warning/10 text-warning',
  sent: 'bg-success/10 text-success',
  failed: 'bg-danger/10 text-danger'
};

/** Separa los correos escritos con comas, punto y coma o espacios. */
export function splitRecipients(value: string): string[] {
  return value
    .split(/[\s,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

/** CAT-005, tipo de contingencia. */
export const CONTINGENCY_TYPE_LABELS: Record<number, string> = {
  1: 'No disponibilidad del sistema de Hacienda',
  2: 'No disponibilidad del sistema del emisor',
  3: 'Falla del servicio de internet del emisor',
  4: 'Falla del suministro de energía eléctrica del emisor',
  5: 'Otro (describe el motivo)'
};

export const CONTINGENCY_STATUS_LABELS: Record<string, string> = {
  ACTIVA: 'Activa',
  CERRADA: 'Cerrada: falta informar el evento',
  REPORTADA: 'Evento informado: transmitiendo',
  COMPLETADA: 'Completada'
};

export const CONTINGENCY_STATUS_BADGES: Record<string, string> = {
  ACTIVA: 'bg-warning/10 text-warning',
  CERRADA: 'bg-danger/10 text-danger',
  REPORTADA: 'bg-primary/10 text-primary',
  COMPLETADA: 'bg-success/10 text-success'
};

/** CAT-022, documento del responsable del evento. */
export const RESPONSIBLE_DOCUMENT_LABELS: Record<string, string> = {
  '13': 'DUI',
  '36': 'NIT',
  '03': 'Pasaporte',
  '02': 'Carné de residente',
  '37': 'Otro'
};

/** Fecha y hora de El Salvador: 17/11/2026 10:05. */
export function formatMoment(value: string | null | undefined): string {
  if (!value) return '—';
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-GB', {
      timeZone: 'America/El_Salvador',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23'
    })
      .formatToParts(new Date(value))
      .map((part) => [part.type, part.value])
  );
  return `${parts.day}/${parts.month}/${parts.year} ${parts.hour}:${parts.minute}`;
}

/** Tipo de invalidación (CAT-024) que ofrece el ERP. */
export const INVALIDATION_KIND_LABELS: Record<number, string> = {
  1: 'Corrección: error en los datos',
  2: 'Anulación: se rescinde la operación'
};

export const INVALIDATION_STATUS_LABELS: Record<string, string> = {
  pending: 'En proceso',
  accepted: 'Aceptada',
  rejected: 'Rechazada',
  failed: 'No se completó'
};

export const INVALIDATION_STATUS_BADGES: Record<string, string> = {
  pending: 'bg-warning/10 text-warning',
  accepted: 'bg-success/10 text-success',
  rejected: 'bg-danger/10 text-danger',
  failed: 'bg-danger/10 text-danger'
};

/** Un documento sellado que se puede anular o corregir. */
export function isSealed(document: Pick<FiscalDocument, 'status'>): boolean {
  return document.status === 'issued' || document.status === 'simulated';
}
