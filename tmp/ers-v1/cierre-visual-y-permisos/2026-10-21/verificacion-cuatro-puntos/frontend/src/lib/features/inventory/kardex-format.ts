import { displayDecimal } from '$lib/features/inventory/valuation';

export function kardexNumber(value: string | null | undefined): string {
  return value == null ? '—' : displayDecimal(value, 3);
}

export function kardexMoney(value: string | null | undefined, currency = 'USD'): string {
  if (value == null) return '—';
  const formatted = displayDecimal(value, 2);
  if (formatted === '—') return formatted;
  const [whole = '—', fraction = ''] = formatted.split('.');
  return `${currency} ${whole}.${fraction.padEnd(2, '0')}`;
}

export function formatKardexDateTime(value: string): string {
  return new Intl.DateTimeFormat('es-SV', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/El_Salvador'
  }).format(new Date(value));
}

export function formatKardexDate(value: string): string {
  const [year, month, day] = value.split('-').map(Number);
  return new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium', timeZone: 'UTC' }).format(
    new Date(Date.UTC(year!, month! - 1, day!))
  );
}
