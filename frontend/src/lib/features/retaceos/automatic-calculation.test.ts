import { describe, expect, it } from 'vitest';
import { calculateImportAmounts, receiptFob } from './manual-costs';

describe('automatic import calculation', () => {
  it('applies DAI to FOB and freight/insurance, then IVA to that base plus DAI', () => {
    expect(calculateImportAmounts('1000', '100', '10', '13')).toEqual({
      freight: '100.000000',
      dai: '110.000000',
      vat: '157.300000'
    });
  });
  it('uses the accepted net receipt value without purchase IVA', () => {
    expect(
      receiptFob({
        subtotal: '30000',
        discount: '1000',
        quantity_received: '100',
        quantity_accepted: '25'
      })
    ).toBe('7250.000000');
    expect(
      receiptFob({
        subtotal: '30000',
        discount: '1000',
        quantity_received: '100',
        quantity_accepted: '0'
      })
    ).toBe('0.000000');
  });
  it('preserves explicit zero taxes and deterministic six-decimal rounding', () => {
    expect(calculateImportAmounts('1', '0', '0', '0').dai).toBe('0.000000');
    expect(calculateImportAmounts('1.000001', '0', '0.00005', '13')).toEqual({
      freight: '0.000000',
      dai: '0.000001',
      vat: '0.130000'
    });
  });
  it('rejects missing and out-of-range rates', () => {
    expect(() => calculateImportAmounts('1000', '100', '', '13')).toThrow();
    expect(() => calculateImportAmounts('1000', '100', '1001', '13')).toThrow();
    expect(() => calculateImportAmounts('999999999999.999999', '0', '1000', '13')).toThrow();
  });
});
