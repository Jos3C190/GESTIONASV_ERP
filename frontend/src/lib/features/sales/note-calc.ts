/**
 * Cálculo estimado de una nota de crédito o de débito (V4c). Repite la regla del servidor
 * (`sales_fiscal_notes.py`) para mostrar el total mientras se arma la nota; el servidor la
 * confirma al emitirla.
 */
import type { CcfLineBalance, FiscalNature } from '#lib/types/sales-invoices.ts';

const VAT = 0.13;
const WITHHOLDING = 0.01;

/** Redondeo a centavos, mitad hacia arriba como el servidor (4.355 → 4.36 pese al flotante). */
function cents(value: number): number {
  return Math.round(Number((value * 100).toFixed(6))) / 100;
}

/** Monto que acredita la devolución de `quantity` unidades al precio neto que queda. */
export function returnAmount(line: CcfLineBalance, quantity: number): number {
  const remainingQuantity = Number(line.remaining_quantity);
  const remainingAmount = Number(line.remaining_amount);
  if (!(quantity > 0) || remainingQuantity <= 0) return 0;
  if (quantity >= remainingQuantity) return remainingAmount;
  return cents((remainingAmount * quantity) / remainingQuantity);
}

export interface EstimatedLine {
  nature: FiscalNature;
  amount: number;
}

export interface NoteEstimate {
  subtotal: number;
  vat: number;
  withheld: number;
  perceived: number;
  total: number;
}

export function estimate(
  lines: EstimatedLine[],
  { withholding, perception }: { withholding: boolean; perception: boolean }
): NoteEstimate {
  const subtotal = cents(lines.reduce((sum, line) => sum + line.amount, 0));
  const taxed = cents(
    lines.filter((line) => line.nature === 'taxed').reduce((sum, line) => sum + line.amount, 0)
  );
  const vat = cents(taxed * VAT);
  const withheld = withholding ? cents(taxed * WITHHOLDING) : 0;
  const perceived = perception ? cents(taxed * WITHHOLDING) : 0;
  return {
    subtotal,
    vat,
    withheld,
    perceived,
    total: cents(subtotal + vat + perceived - withheld)
  };
}

/** Cantidad con hasta seis decimales, sin ceros de sobra: 3.000000 → 3. */
export function formatQuantity(value: string | number): string {
  return new Intl.NumberFormat('es-SV', { maximumFractionDigits: 6 }).format(Number(value));
}
