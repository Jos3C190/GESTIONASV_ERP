import { describe, expect, it } from 'vitest';
import { barcodeFormat, identifierFormatHint } from './identifiers';

describe('product identifier formats', () => {
  it('maps validated identifiers to the explicit barcode format', () => {
    expect(barcodeFormat('ean', '4006381333931')).toBe('EAN13');
    expect(barcodeFormat('upc', '036000291452')).toBe('UPC');
    expect(barcodeFormat('gtin', '00012345600012')).toBe('ITF14');
    expect(barcodeFormat('internal', 'LORENA-001')).toBe('CODE128');
  });

  it('never draws a barcode for an invalid check digit', () => {
    expect(barcodeFormat('ean', '4006381333932')).toBeNull();
    expect(identifierFormatHint('ean', '4006381333932')).toContain('dígito de control');
  });

  it('keeps ISBN-10 readable as text', () => {
    expect(barcodeFormat('isbn', '0306406152')).toBeNull();
    expect(identifierFormatHint('isbn', '0306406152')).toContain('texto');
  });
});
