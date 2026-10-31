import { describe, expect, it } from 'vitest';
import { distributeByFob, otherExpenseCategory, totalAmounts } from './manual-costs';

describe('manual retaceo amounts', () => {
  it('distributes entered freight by FOB while reconciling rounding', () => {
    const result = distributeByFob('0.000002', [
      ['a', '1'],
      ['b', '1'],
      ['c', '1']
    ]);
    expect(result).toEqual({ a: '0.000001', b: '0.000001', c: '0.000000' });
    expect(totalAmounts(Object.values(result))).toBe('0.000002');
    expect(
      distributeByFob('20', [
        ['a', '10'],
        ['b', '30']
      ])
    ).toEqual({ a: '5.000000', b: '15.000000' });
  });
  it('does not distribute without a positive FOB', () => {
    expect(() => distributeByFob('2', [['a', '0']])).toThrow();
  });
  it('keeps fixed components out of other expense categories', () => {
    expect(otherExpenseCategory('Flete internacional')).toBe(false);
    expect(otherExpenseCategory('IVA de importación')).toBe(false);
    expect(otherExpenseCategory('DAI')).toBe(false);
    expect(otherExpenseCategory('Gasolina')).toBe(true);
    expect(otherExpenseCategory('Otros')).toBe(true);
  });
});
