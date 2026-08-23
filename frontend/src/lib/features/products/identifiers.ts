import type { ProductIdentifierType } from '$lib/types/catalog';

export const IDENTIFIER_TYPE_OPTIONS: { value: ProductIdentifierType; label: string }[] = [
  { value: 'ean', label: 'EAN' },
  { value: 'upc', label: 'UPC' },
  { value: 'gtin', label: 'GTIN' },
  { value: 'isbn', label: 'ISBN' },
  { value: 'manufacturer', label: 'Fabricante' },
  { value: 'internal', label: 'Interno' },
  { value: 'other', label: 'Otro' }
];

function validCheckDigit(value: string): boolean {
  if (!/^\d+$/.test(value) || value.length < 2) return false;
  const digits = value.split('').map(Number);
  const check = digits.pop() as number;
  const total = digits.reduce(
    (sum, digit, index) => sum + digit * ((digits.length - index) % 2 ? 3 : 1),
    0
  );
  return (10 - (total % 10)) % 10 === check;
}

function validIsbn10(value: string): boolean {
  if (!/^\d{9}[\dX]$/.test(value)) return false;
  const total = value
    .slice(0, 9)
    .split('')
    .reduce((sum, digit, index) => sum + (10 - index) * Number(digit), 0);
  return (total + (value.endsWith('X') ? 10 : Number(value[9]))) % 11 === 0;
}

export function identifierFormat(type: ProductIdentifierType, value: string): string {
  const normalized = value.replace(/[^0-9X]/gi, '').toUpperCase();
  if (type === 'ean') {
    if (normalized.length === 8) return 'EAN-8';
    if (normalized.length === 13) return 'EAN-13';
    return 'EAN';
  }
  if (type === 'upc') return normalized.length === 12 ? 'UPC-A' : 'UPC';
  if (type === 'gtin') {
    if (normalized.length === 8) return 'GTIN-8';
    if (normalized.length === 12) return 'GTIN-12';
    if (normalized.length === 13) return 'GTIN-13';
    if (normalized.length === 14) return 'GTIN-14';
    return 'GTIN';
  }
  if (type === 'isbn')
    return normalized.length === 13 ? 'ISBN-13' : normalized.length === 10 ? 'ISBN-10' : 'ISBN';
  if (type === 'internal') return 'Code 128';
  return IDENTIFIER_TYPE_OPTIONS.find((item) => item.value === type)?.label ?? 'Identificador';
}

export function barcodeFormat(
  type: ProductIdentifierType,
  value: string
): 'EAN8' | 'EAN13' | 'UPC' | 'ITF14' | 'CODE128' | null {
  const normalized =
    type === 'internal' ? value.trim() : value.replace(/[^0-9X]/gi, '').toUpperCase();
  if (
    type === 'ean' &&
    (normalized.length === 8 || normalized.length === 13) &&
    validCheckDigit(normalized)
  ) {
    return normalized.length === 8 ? 'EAN8' : 'EAN13';
  }
  if (type === 'isbn' && normalized.length === 13 && validCheckDigit(normalized)) return 'EAN13';
  if (type === 'upc' && normalized.length === 12 && validCheckDigit(normalized)) return 'UPC';
  if (type === 'gtin' && validCheckDigit(normalized)) {
    if (normalized.length === 8) return 'EAN8';
    if (normalized.length === 12) return 'UPC';
    if (normalized.length === 13) return 'EAN13';
    if (normalized.length === 14) return 'ITF14';
  }
  if (type === 'internal' && normalized.length > 0) return 'CODE128';
  return null;
}

export function identifierFormatHint(type: ProductIdentifierType, value: string): string | null {
  if (!value.trim()) return null;
  if (barcodeFormat(type, value)) return null;
  const normalized = value.replace(/[^0-9X]/gi, '').toUpperCase();
  if (
    (type === 'ean' && [8, 13].includes(normalized.length)) ||
    (type === 'upc' && normalized.length === 12) ||
    (type === 'gtin' && [8, 12, 13, 14].includes(normalized.length)) ||
    (type === 'isbn' && normalized.length === 13) ||
    (type === 'isbn' && normalized.length === 10 && !validIsbn10(normalized))
  ) {
    return 'El valor no tiene un dígito de control válido; se mostrará como texto.';
  }
  if (type === 'ean') return 'Use 8 o 13 dígitos para generar EAN.';
  if (type === 'upc') return 'Use 12 dígitos para generar UPC-A.';
  if (type === 'gtin') return 'Use 8, 12, 13 o 14 dígitos para generar GTIN.';
  if (type === 'isbn') return 'ISBN-10 se mostrará como texto; ISBN-13 puede generar EAN-13.';
  return null;
}
