import { describe, expect, it } from 'vitest';
import { formatUnitLabel } from './unit-label';

describe('formatUnitLabel', () => {
  it('removes only a repeated trailing unit symbol', () => {
    expect(formatUnitLabel('Unidad (u) (u)')).toBe('Unidad (u)');
    expect(formatUnitLabel('Caja (cj)')).toBe('Caja (cj)');
    expect(formatUnitLabel('Caja (cj) (caja)')).toBe('Caja (cj) (caja)');
  });

  it('provides a readable fallback for absent unit labels', () => {
    expect(formatUnitLabel(null)).toBe('unidad base');
    expect(formatUnitLabel('  ')).toBe('unidad base');
  });
});
