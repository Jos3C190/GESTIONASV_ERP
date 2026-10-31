import { describe, expect, it, vi } from 'vitest';
import {
  decimalMicros,
  displayDecimal,
  fromMicros,
  openingQuantities,
  type ValuationOverview
} from '$lib/features/inventory/valuation';

vi.mock('$lib/api/client', () => ({ apiFetch: vi.fn() }));

describe('inventory valuation exact amounts', () => {
  it('adds fractional values without floating point rounding', () => {
    expect(fromMicros(decimalMicros('0.1') + decimalMicros('0,2'))).toBe('0.300000');
    expect(fromMicros(decimalMicros('999999999999999999.999999'))).toBe(
      '999999999999999999.999999'
    );
  });

  it('displays large amounts without losing digits and rounds signed fractions exactly', () => {
    expect(displayDecimal('9007199254740993.123456')).toBe('9,007,199,254,740,993.123456');
    expect(displayDecimal('-1234.005000', 2)).toBe('-1,234.01');
    expect(displayDecimal('999999999999999999.999999', 2)).toBe('1,000,000,000,000,000,000');
    expect(displayDecimal('-0.000001', 2)).toBe('0');
  });

  it.each(['', '-1', 'NaN', 'Infinity', '1e6', '1.0000001', '1,000.25', '1000000000000000000'])(
    'rejects invalid or out of range input: %s',
    (value) => {
      expect(() => decimalMicros(value)).toThrow();
    }
  );

  it('aggregates all warehouses and quarantine without merging different products', () => {
    const row = {
      inventory_item_id: 'product-a',
      quantity_base: '0.100000',
      stock_status: 'available',
      warehouse_id: 'central',
      location_id: 'location',
      lot_code: null,
      expiry_date: null
    };
    const data: ValuationOverview = {
      setting: null,
      snapshot_fingerprint: 'snapshot',
      items: [],
      balances: [],
      physical_stock: [
        row,
        { ...row, quantity_base: '0.200000', warehouse_id: 'branch', stock_status: 'quarantine' },
        { ...row, inventory_item_id: 'product-b', quantity_base: '2.000000' }
      ]
    };
    expect([...openingQuantities(data)]).toEqual([
      ['product-a', '0.300000'],
      ['product-b', '2.000000']
    ]);
  });
});
