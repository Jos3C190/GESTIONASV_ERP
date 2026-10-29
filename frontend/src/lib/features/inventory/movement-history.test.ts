import { describe, expect, it } from 'vitest';
import { localMovementDate, localMovementPeriod, movementDirection } from './movement-history';
import type { InventoryMovementHistory } from './types';
import { formatMovementDate } from './movement-presentation';

describe('historial físico local', () => {
  it('usa el día de El Salvador antes de medianoche UTC y cruza meses', () => {
    expect(localMovementPeriod(7, new Date('2026-11-01T02:00:00Z'))).toEqual({
      period_from: '2026-10-25',
      period_to: '2026-10-31'
    });
    expect(localMovementPeriod(1, new Date('2026-10-28T06:00:00Z'))).toEqual({
      period_from: '2026-10-28',
      period_to: '2026-10-28'
    });
    expect(localMovementDate('2026-10-29T05:59:00Z')).toContain('28/10/26');
    expect(formatMovementDate('2026-10-29T05:59:00Z')).toContain('28/10/26');
  });
  it('distingue entradas, salidas y movimientos internos sin sumar dos veces', () => {
    const row = (from: string | null, to: string | null) =>
      ({
        from_warehouse_id: from,
        to_warehouse_id: to
      }) as InventoryMovementHistory;
    expect(movementDirection(row(null, 'matrix'), 'matrix').label).toBe('Entrada');
    expect(movementDirection(row('matrix', 'branch'), 'matrix').label).toBe('Salida');
    expect(movementDirection(row('matrix', 'matrix'), 'matrix').label).toBe('Interno');
  });
});
