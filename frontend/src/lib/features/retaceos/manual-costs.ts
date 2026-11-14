import { decimalMicros, fromMicros } from '$lib/features/inventory/valuation';
import type { PurchaseDetail } from '$lib/types/purchase';

export type FixedAmounts = { freight: string; dai: string };

function roundRatio(numerator: bigint, denominator: bigint): bigint {
  if (denominator <= 0n) throw new Error('La cantidad recibida debe ser mayor que cero.');
  return (numerator + denominator / 2n) / denominator;
}

/** Net invoice value, proportionate to the accepted quantity, excluding purchase tax. */
export function receiptFob(
  line: Pick<PurchaseDetail, 'subtotal' | 'discount' | 'quantity_received' | 'quantity_accepted'>
): string {
  const net = decimalMicros(line.subtotal) - decimalMicros(line.discount);
  if (net < 0n) throw new Error('El descuento supera el subtotal de la compra.');
  if (line.quantity_accepted == null) return fromMicros(net);
  const accepted = decimalMicros(line.quantity_accepted);
  if (accepted === 0n) return fromMicros(0n);
  return fromMicros(roundRatio(net * accepted, decimalMicros(line.quantity_received)));
}

const INVALID_AMOUNT = 'Escribe un importe válido con hasta 6 decimales.';

/**
 * Validates a typed freight or DAI amount. Zero is a valid amount; an empty field is not.
 * Returns the message to show under the field, or null when the value can be sent.
 */
export function validateImportAmount(value: string): string | null {
  const text = value.trim();
  if (!text) return 'Escribe un importe; usa 0 si no aplica.';
  const match = /^(-?)(\d+)(?:\.(\d*))?$/.exec(text);
  if (!match) return INVALID_AMOUNT;
  if (match[1]) return 'El importe no puede ser negativo.';
  // The API stores amounts as NUMERIC(18, 6): twelve integer digits and six decimals.
  if ((match[3] ?? '').length > 6 || match[2]!.replace(/^0+(?=\d)/, '').length > 12)
    return INVALID_AMOUNT;
  return null;
}

export function otherExpenseCategory(name: string): boolean {
  const value = name
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
  return (
    !value.startsWith('flete') &&
    !['fob', 'dai', 'aranceles', 'aranceles de importacion', 'iva de importacion'].includes(value)
  );
}

/** Categories that can be an additional expense of a retaceo: also excludes insurance. */
export function retaceoExpenseCategory(name: string): boolean {
  const value = name
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
  return otherExpenseCategory(name) && !value.startsWith('seguro');
}

export function totalAmounts(values: string[]): string {
  return fromMicros(values.reduce((sum, value) => sum + decimalMicros(value || '0'), 0n));
}

/** Largest remainder at six decimals: distribution arithmetic, never source amounts. */
export function distributeByFob(
  amount: string,
  weights: Array<[string, string]>
): Record<string, string> {
  const total = decimalMicros(amount);
  const rows = weights.map(([id, value], index) => ({
    id,
    index,
    weight: decimalMicros(value),
    value: 0n,
    remainder: 0n
  }));
  const base = rows.reduce((sum, row) => sum + row.weight, 0n);
  if (base <= 0n || total < 0n) throw new Error('Completa el FOB y el monto antes de distribuir.');
  for (const row of rows) {
    row.value = (total * row.weight) / base;
    row.remainder = (total * row.weight) % base;
  }
  let residual = total - rows.reduce((sum, row) => sum + row.value, 0n);
  // Same tie-break as the backend: larger fraction, then larger weight, then earlier line.
  const ranked = [...rows].sort((a, b) => {
    if (a.remainder !== b.remainder) return a.remainder > b.remainder ? -1 : 1;
    if (a.weight !== b.weight) return a.weight > b.weight ? -1 : 1;
    return a.index - b.index;
  });
  for (const row of ranked) {
    if (residual <= 0n) break;
    row.value++;
    residual--;
  }
  return Object.fromEntries(rows.map((row) => [row.id, fromMicros(row.value)]));
}
