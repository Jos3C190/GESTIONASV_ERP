import { decimalMicros, fromMicros } from '$lib/features/inventory/valuation';
import type { PurchaseDetail } from '$lib/types/purchase';

export type FixedAmounts = { freight: string; dai: string; vat: string };

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

/** Freight includes insurance. Match the backend's six-decimal half-up arithmetic. */
export function calculateImportAmounts(
  fob: string,
  freight: string,
  daiRate: string,
  vatRate: string
): FixedAmounts {
  const baseFob = decimalMicros(fob);
  const transport = decimalMicros(freight);
  const daiPercent = decimalMicros(daiRate);
  const vatPercent = decimalMicros(vatRate);
  if (baseFob <= 0n || daiPercent > 1000000000n || vatPercent > 1000000000n)
    throw new Error('Completa el FOB y porcentajes válidos de DAI e IVA.');
  const basis = baseFob + transport;
  const dai = roundRatio(basis * daiPercent, 100000000n);
  const vat = roundRatio((basis + dai) * vatPercent, 100000000n);
  if ([dai, vat, basis + dai].some((amount) => amount > 999999999999999999n))
    throw new Error('Los importes calculados superan el máximo permitido para el retaceo.');
  return { freight: fromMicros(transport), dai: fromMicros(dai), vat: fromMicros(vat) };
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
  const ranked = [...rows].sort((a, b) =>
    a.remainder === b.remainder ? a.index - b.index : a.remainder > b.remainder ? -1 : 1
  );
  for (const row of ranked) {
    if (residual <= 0n) break;
    row.value++;
    residual--;
  }
  return Object.fromEntries(rows.map((row) => [row.id, fromMicros(row.value)]));
}
