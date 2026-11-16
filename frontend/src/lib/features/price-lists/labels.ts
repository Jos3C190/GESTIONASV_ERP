import type { PriceStatus } from '#lib/types/price-list.ts';

export const STATUS_LABELS: Record<PriceStatus, string> = {
  scheduled: 'Programado',
  current: 'Vigente',
  expired: 'Vencido'
};

export const STATUS_TONES: Record<PriceStatus, 'primary' | 'success' | 'neutral'> = {
  scheduled: 'primary',
  current: 'success',
  expired: 'neutral'
};

const MONEY = new Intl.NumberFormat('es-SV', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4
});

/** Un precio con hasta 4 decimales (se guardan 8): $1.13, $0.8850. */
export function formatPrice(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return MONEY.format(Number(value));
}

/** `YYYY-MM-DD` a `DD/MM/YYYY`. */
export function formatDay(value: string | null): string {
  if (!value) return '—';
  const [year, month, day] = value.slice(0, 10).split('-');
  return `${day}/${month}/${year}`;
}

export function todayInElSalvador(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/El_Salvador',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(now);
}

/** Texto del rango de vigencia: «desde 16/11/2026» o «16/11/2026 al 30/11/2026». */
export function validityText(from: string, to: string | null): string {
  return to ? `${formatDay(from)} al ${formatDay(to)}` : `desde ${formatDay(from)}`;
}

/** Precio equivalente con o sin IVA, para mostrar la otra forma junto al precio de la lista. */
export function counterpartPrice(value: string, includesVat: boolean): string {
  const amount = Number(value);
  const other = includesVat ? amount / 1.13 : amount * 1.13;
  return formatPrice(other.toFixed(4));
}
