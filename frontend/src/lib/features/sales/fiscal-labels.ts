import type { FiscalDocument, FiscalDocumentStatus } from '#lib/types/sales-invoices.ts';

export const FISCAL_STATUS_LABELS: Record<FiscalDocumentStatus, string> = {
  pending: 'Emitiendo',
  issued: 'Emitido',
  simulated: 'Simulado',
  rejected: 'Rechazado',
  failed: 'Falló'
};

export const FISCAL_STATUS_BADGES: Record<FiscalDocumentStatus, string> = {
  pending: 'bg-warning/10 text-warning',
  issued: 'bg-success/10 text-success',
  simulated: 'bg-primary/10 text-primary',
  rejected: 'bg-danger/10 text-danger',
  failed: 'bg-danger/10 text-danger'
};

export const FISCAL_STATUS_FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'Todos' },
  { value: 'pending', label: 'Emitiendo' },
  { value: 'issued', label: 'Emitidos' },
  { value: 'simulated', label: 'Simulados' },
  { value: 'rejected', label: 'Rechazados' },
  { value: 'failed', label: 'Fallidos' }
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
