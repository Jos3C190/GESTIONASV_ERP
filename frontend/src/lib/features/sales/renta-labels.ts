/**
 * Clasificación de renta de una venta (anexos de ventas del F-07, desde enero de 2025).
 * Fuente: Manual de anexos del F-07 V14 (DGII). No es una clasificación de IVA.
 */

export const RENTA_OPERATION_LABELS: Record<number, string> = {
  1: 'Gravada',
  2: 'No gravada o exenta',
  3: 'Excluido o no constituye renta',
  4: 'Mixta (gravada y exenta en el mismo documento)',
  12: 'Ingresos ya retenidos en el F910',
  13: 'Sujetos pasivos excluidos (art. 6 LISR)'
};

export const RENTA_INCOME_LABELS: Record<number, string> = {
  1: 'Profesiones, artes y oficios',
  2: 'Actividades de servicios',
  3: 'Actividades comerciales',
  4: 'Actividades industriales',
  5: 'Actividades agropecuarias',
  6: 'Utilidades y dividendos',
  7: 'Exportaciones de bienes',
  8: 'Servicios del exterior utilizados en El Salvador',
  9: 'Exportaciones de servicios',
  10: 'Otras rentas gravables',
  12: 'Ingresos ya retenidos en el F910',
  13: 'Sujetos pasivos excluidos (art. 6 LISR)'
};

/** 12 y 13 están en los dos catálogos y van con el mismo código en las dos columnas. */
const SHARED = new Set([12, 13]);

export function rentaComplete(operation: number | null, income: number | null): boolean {
  if (operation === null || income === null) return false;
  if (SHARED.has(operation) || SHARED.has(income)) return operation === income;
  return true;
}

export function rentaLabel(
  operation: number | null | undefined,
  income: number | null | undefined
) {
  if (operation == null || income == null) return 'Sin clasificar';
  return `${RENTA_OPERATION_LABELS[operation] ?? operation} · ${RENTA_INCOME_LABELS[income] ?? income}`;
}
