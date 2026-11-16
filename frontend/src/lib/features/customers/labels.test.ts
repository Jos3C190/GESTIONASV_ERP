import { describe, expect, it } from 'vitest';
import { emptyCustomerInput, formatDocument, formatNrc, switchCustomerType } from './labels';

describe('customer labels', () => {
  it('formats NIT, DUI and NRC with their dashes', () => {
    expect(formatDocument('36', '06140101011011')).toBe('0614-010101-101-1');
    expect(formatDocument('13', '012345678')).toBe('01234567-8');
    expect(formatDocument('03', 'AB12345')).toBe('AB12345');
    expect(formatDocument(null, null)).toBe('—');
    expect(formatNrc('1234567')).toBe('123456-7');
  });

  it('switching type keeps only what the new type admits', () => {
    const taxpayer = {
      ...emptyCustomerInput('taxpayer'),
      document_type: '36' as const,
      document_number: '06140101011011',
      geography: { department_id: 'd', municipality_id: 'm', district_id: 'x' }
    };
    expect(taxpayer.taxpayer_category).toBe('other');
    const foreign = switchCustomerType(taxpayer, 'foreign');
    expect(foreign.taxpayer_category).toBeNull();
    expect(foreign.document_type).toBeNull();
    expect(foreign.geography).toBeNull();
    const consumer = switchCustomerType(taxpayer, 'final_consumer');
    expect(consumer.document_type).toBe('36');
    expect(consumer.geography).not.toBeNull();
  });
});
