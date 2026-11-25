import type { AgingBucket, PaymentMethod } from '#lib/types/sales-receivables.ts';

export const METHOD_LABELS: Record<PaymentMethod, string> = {
  cash: 'Efectivo',
  card: 'Tarjeta',
  transfer: 'Transferencia',
  check: 'Cheque',
  other: 'Otro'
};

export const REFERENCE_HINTS: Record<PaymentMethod, string> = {
  cash: '',
  card: 'Número de autorización',
  transfer: 'Número de transferencia',
  check: 'Número de cheque y banco',
  other: 'Referencia'
};

export const BUCKET_LABELS: Record<AgingBucket, string> = {
  current: 'Por vencer',
  '1_30': '1 a 30 días',
  '31_60': '31 a 60 días',
  '61_90': '61 a 90 días',
  over_90: 'Más de 90 días'
};

export const BUCKETS: AgingBucket[] = ['current', '1_30', '31_60', '61_90', 'over_90'];

export const DOCUMENT_LABELS: Record<string, string> = {
  '01': 'Factura',
  '03': 'Crédito fiscal',
  '06': 'Nota de débito'
};

/** Hoy en El Salvador, AAAA-MM-DD. */
export function todayLocal(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/El_Salvador',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(now);
}

/** Suma de montos en centavos para no acumular errores de punto flotante. */
export function sumCents(values: (string | number)[]): number {
  return values.reduce<number>((total, value) => total + Math.round(Number(value || 0) * 100), 0);
}

export function fromCents(cents: number): string {
  return (cents / 100).toFixed(2);
}
