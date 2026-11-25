import type {
  FiscalBookMode,
  PurchaseDocumentClass,
  PurchaseDocumentType,
  SupplierIdType
} from '#lib/types/fiscal-books.ts';

export const MODE_LABELS: Record<FiscalBookMode, string> = {
  production: 'Producción',
  test: 'Pruebas',
  simulated: 'Simulado'
};

export const DOCUMENT_TYPES: Record<string, string> = {
  '01': 'Factura',
  '03': 'Crédito fiscal',
  '05': 'Nota de crédito',
  '06': 'Nota de débito',
  '12': 'Declaración de mercancías',
  '13': 'Mandamiento de ingreso'
};

/** Clase del documento del proveedor y los tipos que admite (manual F-07 V14, anexo de compras). */
export const PURCHASE_CLASSES: {
  value: PurchaseDocumentClass;
  label: string;
  types: PurchaseDocumentType[];
}[] = [
  { value: 4, label: 'Documento tributario electrónico (DTE)', types: ['03', '05', '06'] },
  { value: 1, label: 'Impreso por imprenta', types: ['03', '05', '06'] },
  { value: 3, label: 'Otros (importación)', types: ['12', '13'] }
];

export const SUPPLIER_ID_LABELS: Record<SupplierIdType, string> = {
  nit: 'NIT (14 dígitos)',
  nrc: 'NRC',
  dui: 'DUI (9 dígitos)'
};

export const RENTA_OPERATIONS: Record<number, string> = {
  1: 'Gravada',
  2: 'No gravada o exenta',
  3: 'Excluido o no constituye renta',
  4: 'Mixta',
  8: 'Informada en más de un anexo',
  9: 'Excepciones'
};

export const RENTA_CLASSIFICATIONS: Record<number, string> = {
  1: 'Costo',
  2: 'Gasto',
  8: 'Informada en más de un anexo',
  9: 'Excepciones'
};

export const RENTA_SECTORS: Record<number, string> = {
  1: 'Industria',
  2: 'Comercio',
  3: 'Agropecuaria',
  4: 'Servicios, profesiones, artes y oficios',
  8: 'Informada en más de un anexo',
  9: 'Excepciones'
};

export const RENTA_COST_TYPES: Record<number, string> = {
  1: 'Gastos de venta sin donación',
  2: 'Gastos de administración sin donación',
  3: 'Gastos financieros sin donación',
  4: 'Costo de artículos importados o internados',
  5: 'Costo de artículos comprados en el país',
  6: 'Costos indirectos de fabricación',
  7: 'Mano de obra',
  8: 'Informada en más de un anexo',
  9: 'Excepciones'
};

export const RENTA_FIELDS = [
  { key: 'operation', label: 'Tipo de operación', options: RENTA_OPERATIONS },
  { key: 'classification', label: 'Clasificación', options: RENTA_CLASSIFICATIONS },
  { key: 'sector', label: 'Sector', options: RENTA_SECTORS },
  { key: 'cost_type', label: 'Tipo de costo o gasto', options: RENTA_COST_TYPES }
] as const;

/** Mes anterior al de hoy en El Salvador, el que normalmente se declara: «2026-10». */
export function previousPeriod(today: Date = new Date()): string {
  const local = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/El_Salvador',
    year: 'numeric',
    month: '2-digit'
  }).format(today);
  const [year = 1970, month = 1] = local.split('-').map(Number);
  const previous = month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };
  return `${previous.year}-${String(previous.month).padStart(2, '0')}`;
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
