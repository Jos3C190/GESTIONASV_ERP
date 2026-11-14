import { describe, expect, it } from 'vitest';
import {
  distributeByFob,
  otherExpenseCategory,
  retaceoExpenseCategory,
  receiptFob,
  totalAmounts,
  validateImportAmount
} from './manual-costs';

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
  it('breaks equal fractions by the larger weight, as the backend does', () => {
    // 0.000002 over weights 1 and 3 leaves a 0.5 fraction on both lines.
    expect(
      distributeByFob('0.000002', [
        ['a', '1'],
        ['b', '3']
      ])
    ).toEqual({ a: '0.000000', b: '0.000002' });
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
  it('uses the accepted net receipt value without purchase tax', () => {
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
    expect(
      receiptFob({
        subtotal: '30000',
        discount: '1000',
        quantity_received: '100',
        quantity_accepted: null
      })
    ).toBe('29000.000000');
  });
  it('rejects a discount above the subtotal', () => {
    expect(() =>
      receiptFob({
        subtotal: '10',
        discount: '11',
        quantity_received: '1',
        quantity_accepted: null
      })
    ).toThrow();
  });
  it('validates typed freight and DAI amounts and accepts zero', () => {
    expect(validateImportAmount('')).toBe('Escribe un importe; usa 0 si no aplica.');
    expect(validateImportAmount('  ')).toBe('Escribe un importe; usa 0 si no aplica.');
    expect(validateImportAmount('-1')).toBe('El importe no puede ser negativo.');
    expect(validateImportAmount('1.1234567')).toBe(
      'Escribe un importe válido con hasta 6 decimales.'
    );
    expect(validateImportAmount('abc')).toBe('Escribe un importe válido con hasta 6 decimales.');
    expect(validateImportAmount('1e3')).toBe('Escribe un importe válido con hasta 6 decimales.');
    expect(validateImportAmount('9999999999999')).toBe(
      'Escribe un importe válido con hasta 6 decimales.'
    );
    for (const valid of ['0', '0.000000', '12', '12.5', '999999999999.999999'])
      expect(validateImportAmount(valid)).toBeNull();
  });
  it('also keeps insurance out of the retaceo additional expenses but not out of the order log', () => {
    for (const name of ['Seguro', 'seguro de carga', 'SEGURO', 'Flete', 'DAI'])
      expect(retaceoExpenseCategory(name)).toBe(false);
    for (const name of ['Agente aduanal', 'Almacenamiento', 'Manejo y descarga', 'Otros'])
      expect(retaceoExpenseCategory(name)).toBe(true);
    // The order's actual-expense log keeps accepting insurance.
    expect(otherExpenseCategory('Seguro')).toBe(true);
  });
});
