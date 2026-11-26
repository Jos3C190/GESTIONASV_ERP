import { formatMoney } from '#lib/features/sales/quotation-labels.ts';
import type {
  DenominationForm,
  DenominationLine,
  MovementKind,
  ShiftStatus
} from '#lib/types/pos.ts';

export { formatMoney };

const TZ = 'America/El_Salvador';

/** 22/07/2026 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00`) : new Date(value);
  return new Intl.DateTimeFormat('es-SV', {
    timeZone: TZ,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  }).format(date);
}

/** 22/07/2026 14:05 */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const parts = new Intl.DateTimeFormat('es-SV', {
    timeZone: TZ,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).formatToParts(new Date(value));
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? '';
  return `${get('day')}/${get('month')}/${get('year')} ${get('hour')}:${get('minute')}`;
}

/** Fecha de hoy en El Salvador, AAAA-MM-DD. */
export function today(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(new Date());
}

export function idempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

/** Denominaciones en circulación (USD), de mayor a menor, como las cuenta el cajero. */
export const DENOMINATIONS: { form: DenominationForm; denomination: string; label: string }[] = [
  { form: 'bill', denomination: '100.00', label: '$100' },
  { form: 'bill', denomination: '50.00', label: '$50' },
  { form: 'bill', denomination: '20.00', label: '$20' },
  { form: 'bill', denomination: '10.00', label: '$10' },
  { form: 'bill', denomination: '5.00', label: '$5' },
  { form: 'bill', denomination: '2.00', label: '$2' },
  { form: 'bill', denomination: '1.00', label: '$1' },
  { form: 'coin', denomination: '1.00', label: '$1' },
  { form: 'coin', denomination: '0.50', label: '50¢' },
  { form: 'coin', denomination: '0.25', label: '25¢' },
  { form: 'coin', denomination: '0.10', label: '10¢' },
  { form: 'coin', denomination: '0.05', label: '5¢' },
  { form: 'coin', denomination: '0.01', label: '1¢' }
];

export function emptyCount(): DenominationLine[] {
  return DENOMINATIONS.map(({ form, denomination }) => ({ form, denomination, quantity: 0 }));
}

/** Suma en centavos para no arrastrar errores de punto flotante. */
export function countTotalCents(lines: DenominationLine[]): number {
  return lines.reduce(
    (sum, line) => sum + Math.round(Number(line.denomination) * 100) * (line.quantity || 0),
    0
  );
}

export function centsToAmount(cents: number): string {
  const sign = cents < 0 ? '-' : '';
  const abs = Math.abs(cents);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`;
}

export function toCents(value: string): number | null {
  const text = value.trim().replace(',', '.');
  if (!/^\d+(\.\d{1,2})?$/.test(text)) return null;
  const [whole, fraction = ''] = text.split('.');
  return Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
}

export function countedLines(lines: DenominationLine[]): DenominationLine[] {
  return lines.filter((line) => line.quantity > 0);
}

export const SHIFT_STATUS: Record<
  ShiftStatus,
  { label: string; variant: 'success' | 'warning' | 'danger' | 'neutral' | 'primary' }
> = {
  open: { label: 'Abierto', variant: 'success' },
  counted: { label: 'Por aprobar', variant: 'warning' },
  recount: { label: 'Recontar', variant: 'danger' },
  closed: { label: 'Cerrado', variant: 'neutral' }
};

export const MOVEMENT_KIND: Record<MovementKind, { label: string; sign: 1 | -1; hint: string }> = {
  cash_in: {
    label: 'Entrada de efectivo',
    sign: 1,
    hint: 'Cambio o efectivo que ingresa sin venta.'
  },
  cash_out: {
    label: 'Salida de efectivo',
    sign: -1,
    hint: 'Pago menor desde la gaveta, con su comprobante.'
  },
  safe_drop: {
    label: 'Retiro a caja fuerte',
    sign: -1,
    hint: 'Efectivo que sale de la gaveta hacia la caja fuerte; se deposita con el turno.'
  }
};
