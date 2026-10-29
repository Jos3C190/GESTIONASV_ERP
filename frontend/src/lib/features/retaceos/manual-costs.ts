import { decimalMicros, fromMicros } from '$lib/features/inventory/valuation';

export type FixedAmounts = { freight: string; dai: string; vat: string };

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
