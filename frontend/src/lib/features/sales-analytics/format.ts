import { formatMoney } from '#lib/features/sales/quotation-labels.ts';

export { formatMoney };

/** Fecha local AAAA-MM-DD (America/El_Salvador). */
export function localDay(date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/El_Salvador',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(date);
}

export function monthStart(day: string): string {
  return `${day.slice(0, 7)}-01`;
}

export function formatPercent(value: string | null): string {
  if (value === null) return '—';
  return `${Number(value).toLocaleString('es-SV', { maximumFractionDigits: 2 })} %`;
}
