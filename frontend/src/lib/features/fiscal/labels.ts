import type {
  CertificationStatus,
  EstablishmentType,
  OperatingMode,
  PersonType,
  TaxpayerCategory
} from '$lib/types/fiscal';

export const OPERATING_MODE_LABELS: Record<OperatingMode, string> = {
  simulated: 'Simulado',
  test: 'Pruebas de Hacienda',
  production: 'Producción'
};

export const OPERATING_MODE_HINTS: Record<OperatingMode, string> = {
  simulated: 'Documentos sin validez fiscal, para capacitación y demostraciones.',
  test: 'Documentos enviados al ambiente de pruebas de Hacienda para la certificación.',
  production: 'Documentos con validez fiscal ante Hacienda.'
};

export const TAXPAYER_CATEGORY_LABELS: Record<TaxpayerCategory, string> = {
  large: 'Gran contribuyente',
  medium: 'Mediano contribuyente',
  other: 'Otro contribuyente'
};

export const PERSON_TYPE_LABELS: Record<PersonType, string> = {
  '1': 'Persona natural',
  '2': 'Persona jurídica'
};

export const ESTABLISHMENT_TYPE_LABELS: Record<EstablishmentType, string> = {
  '02': 'Casa matriz',
  '01': 'Sucursal',
  '04': 'Bodega',
  '07': 'Patio'
};

/** Letra del código de establecimiento en el número de control, según su tipo. */
export const ESTABLISHMENT_PREFIX: Record<EstablishmentType, string> = {
  '02': 'M',
  '01': 'S',
  '04': 'B',
  '07': 'P'
};

export const CERTIFICATION_LABELS: Record<CertificationStatus, string> = {
  pending: 'Sin iniciar',
  in_progress: 'En pruebas',
  approved: 'Aprobado'
};

export const CERTIFICATION_TONES: Record<CertificationStatus, 'neutral' | 'warning' | 'success'> = {
  pending: 'neutral',
  in_progress: 'warning',
  approved: 'success'
};

/** Códigos de CAT-002 que son eventos y no documentos de venta. */
export const EVENT_DOCUMENT_TYPES = new Set(['17', '18']);

/** Sugiere el siguiente código libre para un tipo (`S003` si ya existen S001 y S002). */
export function nextEstablishmentCode(type: EstablishmentType, taken: string[]): string {
  const prefix = ESTABLISHMENT_PREFIX[type];
  const used = new Set(taken.map((code) => code.toUpperCase()));
  for (let n = 1; n <= 999; n += 1) {
    const code = `${prefix}${String(n).padStart(3, '0')}`;
    if (!used.has(code)) return code;
  }
  return `${prefix}001`;
}

export function nextPointOfSaleCode(taken: string[]): string {
  const used = new Set(taken.map((code) => code.toUpperCase()));
  for (let n = 1; n <= 999; n += 1) {
    const code = `P${String(n).padStart(3, '0')}`;
    if (!used.has(code)) return code;
  }
  return 'P001';
}

export function isEstablishmentCode(type: EstablishmentType, code: string): boolean {
  return new RegExp(`^${ESTABLISHMENT_PREFIX[type]}(?!000)[0-9]{3}$`).test(
    code.trim().toUpperCase()
  );
}

export function isPointOfSaleCode(code: string): boolean {
  return /^P(?!000)[0-9]{3}$/.test(code.trim().toUpperCase());
}

/** Fecha en `DD/MM/YYYY`, en la hora de El Salvador. */
export function formatFiscalDate(value: string | null): string {
  if (!value) return '—';
  return new Intl.DateTimeFormat('es-SV', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: 'America/El_Salvador'
  }).format(new Date(value));
}
