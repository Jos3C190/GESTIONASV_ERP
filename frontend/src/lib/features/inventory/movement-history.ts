import type { InventoryMovementHistory } from './types';
import { formatMovementDate } from './movement-presentation';

export function localMovementPeriod(days: number, now = new Date()) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/El_Salvador',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    })
      .formatToParts(now)
      .map((p) => [p.type, p.value])
  );
  const end = `${parts.year}-${parts.month}-${parts.day}`;
  const start = new Date(`${end}T12:00:00Z`);
  start.setUTCDate(start.getUTCDate() - Math.max(0, days - 1));
  return { period_from: start.toISOString().slice(0, 10), period_to: end };
}

export function movementDirection(row: InventoryMovementHistory, warehouseId: string) {
  if (row.from_warehouse_id === warehouseId && row.to_warehouse_id === warehouseId)
    return { label: 'Interno', sign: '↔', className: 'text-foreground-muted' };
  return row.to_warehouse_id === warehouseId
    ? { label: 'Entrada', sign: '+', className: 'text-success' }
    : { label: 'Salida', sign: '−', className: 'text-danger' };
}

export const localMovementDate = formatMovementDate;
