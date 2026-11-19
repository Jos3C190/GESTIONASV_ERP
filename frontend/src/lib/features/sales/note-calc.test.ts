import { expect, it } from 'vitest';
import type { CcfLineBalance } from '#lib/types/sales-invoices.ts';
import { estimate, formatQuantity, returnAmount } from './note-calc.ts';

const LINE: CcfLineBalance = {
  number: 1,
  code: 'CAM-1',
  description: 'Camiseta',
  nature: 'taxed',
  quantity: '4',
  unit_price: '30',
  net: '114.00',
  returned: '1',
  credited: '38.51',
  remaining_quantity: '3.000000',
  remaining_amount: '75.49'
};

it('devuelve al precio neto que queda y las últimas unidades toman el saldo exacto', () => {
  expect(returnAmount(LINE, 1)).toBe(25.16);
  expect(returnAmount(LINE, 3)).toBe(75.49);
  expect(returnAmount(LINE, 0)).toBe(0);
});

it('estima IVA, retención y percepción del 1 % sobre lo gravado', () => {
  const lines = [
    { nature: 'taxed' as const, amount: 28.5 },
    { nature: 'taxed' as const, amount: 5 },
    { nature: 'exempt' as const, amount: 50 }
  ];
  expect(estimate(lines, { withholding: true, perception: false })).toEqual({
    subtotal: 83.5,
    vat: 4.36,
    withheld: 0.34,
    perceived: 0,
    total: 87.52
  });
  expect(estimate(lines, { withholding: false, perception: true }).total).toBe(88.2);
});

it('muestra cantidades sin ceros de sobra', () => {
  expect(formatQuantity('3.000000')).toBe('3');
  expect(formatQuantity('2.500000')).toBe('2.5');
});
