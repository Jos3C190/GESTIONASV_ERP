import { describe, expect, it } from 'vitest';
import {
  calculateProductVolume,
  DIMENSION_UNITS,
  formatProductDimensions,
  WEIGHT_UNITS
} from './measurements';

describe('product measurements', () => {
  it('keeps fixed measurement lists separate from commercial units', () => {
    expect(DIMENSION_UNITS.map((item) => item.value)).toEqual(['mm', 'cm', 'm', 'in', 'ft']);
    expect(WEIGHT_UNITS.map((item) => item.value)).toEqual(['mg', 'g', 'kg', 't', 'oz', 'lb']);
  });

  it('calculates volume in cubic metres', () => {
    expect(calculateProductVolume(20, 30, 10, 'cm')).toBeCloseTo(0.006);
    expect(calculateProductVolume(1, 1, 1, 'm')).toBe(1);
    expect(calculateProductVolume(20, null, 10, 'cm')).toBeNull();
  });

  it('formats partial dimensions without pretending volume is known', () => {
    expect(formatProductDimensions(20, null, null, 'cm')).toBe('20 × — × — cm');
    expect(formatProductDimensions(null, null, null, 'cm')).toBeNull();
  });
});
