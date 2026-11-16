import { describe, expect, it } from 'vitest';
import {
  isEstablishmentCode,
  isPointOfSaleCode,
  nextEstablishmentCode,
  nextPointOfSaleCode
} from './labels';

describe('fiscal codes', () => {
  it('suggests the next free establishment code for the type', () => {
    expect(nextEstablishmentCode('01', ['M001', 'S001', 'S002'])).toBe('S003');
    expect(nextEstablishmentCode('02', [])).toBe('M001');
    expect(nextEstablishmentCode('04', ['s001'])).toBe('B001');
  });

  it('validates the letter of the type and three digits', () => {
    expect(isEstablishmentCode('01', 's001')).toBe(true);
    expect(isEstablishmentCode('01', 'M001')).toBe(false);
    expect(isEstablishmentCode('02', 'M000')).toBe(false);
    expect(isEstablishmentCode('07', 'P12')).toBe(false);
  });

  it('handles point of sale codes', () => {
    expect(nextPointOfSaleCode(['P001'])).toBe('P002');
    expect(isPointOfSaleCode('p010')).toBe(true);
    expect(isPointOfSaleCode('P000')).toBe(false);
    expect(isPointOfSaleCode('C001')).toBe(false);
  });
});
