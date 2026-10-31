import { describe, expect, it } from 'vitest';
import { supplierDisplayName } from './supplier-display';

describe('supplierDisplayName', () => {
  it('uses the commercial supplier name when available', () => {
    expect(supplierDisplayName({ supplier_id: 1, supplier_name: 'Proveedor Lorena' })).toBe(
      'Proveedor Lorena'
    );
  });

  it('keeps the technical id only in the unavailable fallback', () => {
    expect(supplierDisplayName({ supplier_id: 3, supplier_name: null })).toBe(
      'Proveedor no disponible (#3)'
    );
    expect(supplierDisplayName({ supplier_id: 7 })).toBe('Proveedor no disponible (#7)');
  });

  it('treats whitespace-only names as unavailable', () => {
    expect(supplierDisplayName({ supplier_id: 9, supplier_name: '   ' })).toBe(
      'Proveedor no disponible (#9)'
    );
  });
});
