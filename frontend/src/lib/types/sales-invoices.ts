/** Documento fiscal del pedido (bloque V3b). */

/** 01 factura, 03 crédito fiscal, 04 nota de remisión, 05 nota de crédito, 06 nota de débito. */
export type FiscalDocumentType = '01' | '03' | '04' | '05' | '06';

export type FiscalNature = 'taxed' | 'exempt' | 'not_subject';

/** Una línea del CCF con su saldo después de las notas de crédito vigentes (V4c). */
export interface CcfLineBalance {
  number: number;
  code: string | null;
  description: string;
  nature: FiscalNature;
  quantity: string;
  unit_price: string;
  net: string;
  returned: string;
  credited: string;
  remaining_quantity: string;
  remaining_amount: string;
}

export interface FiscalNoteLine {
  line_number: number;
  ccf_line_number: number | null;
  kind: 'return' | 'discount' | 'charge';
  nature: FiscalNature;
  description: string;
  quantity: string | null;
  amount: string;
}

export interface FiscalNote {
  document: FiscalDocument;
  lines: FiscalNoteLine[];
}

export interface NotesOverview {
  ccf_id: string;
  /** Último día para emitir notas: tres meses desde el CCF (Normativa 2.0, regla 2c). */
  deadline: string | null;
  withholding: boolean;
  perception: boolean;
  credit_blocker: string | null;
  debit_blocker: string | null;
  lines: CcfLineBalance[];
  notes: FiscalNote[];
}

export interface CreditLineInput {
  ccf_line_number: number;
  kind: 'return' | 'discount';
  quantity?: string;
  amount?: string;
}

export interface DebitChargeInput {
  description: string;
  quantity: string;
  unit_price: string;
  nature?: FiscalNature | null;
  ccf_line_number?: number | null;
}

export type FiscalDocumentStatus =
  'pending' | 'contingency' | 'issued' | 'simulated' | 'rejected' | 'failed' | 'invalidated';

export interface FiscalDocument {
  id: string;
  company_id: string;
  branch_id: string;
  /** El pedido; vacío en la nota de remisión (04), que pertenece a un traslado. */
  sale_id: string | null;
  transfer_id?: string | null;
  transfer_code?: string | null;
  sale_code: string | null;
  customer_name: string | null;
  customer_email: string | null;
  establishment_code: string | null;
  point_of_sale_code: string | null;
  document_type: FiscalDocumentType;
  mode: string;
  status: FiscalDocumentStatus;
  generation_code: string | null;
  control_number: string | null;
  total: string;
  seal: string | null;
  attempts: number;
  error_code: string | null;
  error_message: string | null;
  has_json: boolean;
  has_pdf: boolean;
  issued_at: string | null;
  /** Generado en contingencia (V4a): tipo de CAT-005, motivo y cuándo. */
  contingency_type?: number | null;
  contingency_reason?: string | null;
  contingency_at?: string | null;
  /** Corrección (V4b): el documento que éste reemplaza, o el que lo reemplaza. */
  replaces_document_id?: string | null;
  superseded_by_id?: string | null;
  /** Clasificación de renta del documento para los anexos del F-07. */
  renta_operation_type?: number | null;
  renta_income_type?: number | null;
  /** En una nota (05 o 06): el crédito fiscal que ajusta y el motivo (V4c). */
  related_document_id?: string | null;
  note_reason?: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface FiscalDocumentPage {
  items: FiscalDocument[];
  page: number;
  size: number;
  total: number;
  pages: number;
}

export interface InvoicePointOfSale {
  id: string;
  code: string;
  name: string;
}

export interface InvoiceOptions {
  document_type: string;
  mode: string;
  establishment_code: string | null;
  points_of_sale: InvoicePointOfSale[];
  blockers: string[];
  document: FiscalDocument | null;
  /** Sin documento vigente: el último del pedido (rechazado, fallido o invalidado). */
  previous_document?: FiscalDocument | null;
  /** Clasificación de renta sugerida por la actividad del establecimiento. */
  renta_operation_type?: number | null;
  renta_income_type?: number | null;
}

export interface FiscalDocumentFilters {
  branch_id?: string | null;
  sale_id?: string;
  status?: string;
  document_type?: string;
  q?: string;
  page?: number;
  size?: number;
}

export type FiscalEmailStatus = 'pending' | 'sent' | 'failed';

export interface FiscalEmail {
  id: string;
  document_id: string;
  recipients: string[];
  origin: 'auto' | 'manual';
  status: FiscalEmailStatus;
  attempts: number;
  error_code: string | null;
  error_message: string | null;
  requested_by_name: string | null;
  /** Aviso de una invalidación (V4b), no el documento. */
  invalidation_id?: string | null;
  sent_at: string | null;
  created_at: string | null;
}

export interface FiscalEmailHistory {
  enabled: boolean;
  customer_email: string | null;
  items: FiscalEmail[];
}

/** Invalidación y corrección de un documento (bloque V4b). */
export interface Person {
  name: string;
  document_type: string;
  document_number: string;
}

export type InvalidationStatus = 'pending' | 'accepted' | 'rejected' | 'failed';

export interface FiscalInvalidation {
  id: string;
  document_id: string;
  /** 1: error en los datos (con reemplazo); 2: rescindir la operación. */
  kind: 1 | 2;
  reason: string | null;
  requester: Person;
  responsible: Person | null;
  replacement_document_id: string | null;
  cancel_order: boolean;
  status: InvalidationStatus;
  attempts: number;
  event_generation_code: string | null;
  event_seal: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string | null;
  resolved_at: string | null;
}

export interface InvalidationOverview {
  deadline: string | null;
  expired: boolean;
  estimated: boolean;
  history: FiscalInvalidation[];
}

export interface Correction {
  replacement: FiscalDocument;
  invalidation: FiscalInvalidation;
}

/** Nota de remisión de un traslado (V4d). */
export interface TransferRemission {
  /** Si la empresa emite nota de remisión al despachar. */
  enabled: boolean;
  /** La nota vigente o, si no hay, la última. */
  document: FiscalDocument | null;
}
