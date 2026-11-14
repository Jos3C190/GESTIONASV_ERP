import { describe, expect, it } from 'vitest';
import {
  isCustomerReturnReference,
  movementTypeFilterLabel,
  movementTypeLabel
} from './movement-presentation';
import { valuationKind } from './valuation';

describe('movement labels by operation', () => {
  it('names a purchase receipt and a sales shipment by their operation', () => {
    expect(movementTypeLabel('receipt', 'purchase-receipt:1').label).toBe(
      'Entrada por compra (recepción)'
    );
    expect(movementTypeLabel('shipment', 'sales_delivery:1').label).toBe(
      'Salida por venta (despacho)'
    );
  });

  it('tells a customer return apart from a purchase receipt', () => {
    expect(isCustomerReturnReference('customer-return:DEV-00001')).toBe(true);
    expect(isCustomerReturnReference('customer_return:DEV-00001')).toBe(true);
    expect(isCustomerReturnReference('purchase-receipt:1')).toBe(false);
    expect(isCustomerReturnReference(null)).toBe(false);
    expect(movementTypeLabel('receipt', 'customer-return:DEV-00001').label).toBe(
      'Entrada por devolución de cliente'
    );
  });

  it('uses one filter label for every receipt source', () => {
    expect(movementTypeFilterLabel('receipt')).toBe('Entradas por compra o devolución (recepción)');
    expect(movementTypeFilterLabel('shipment')).toBe('Salida por venta (despacho)');
  });

  it('names valued Kardex events as purchases and sales', () => {
    expect(valuationKind.receipt).toBe('Compra');
    expect(valuationKind.issue).toBe('Venta');
  });
});
