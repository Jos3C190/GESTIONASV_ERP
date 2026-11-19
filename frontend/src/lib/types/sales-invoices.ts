/** Documento fiscal del pedido (bloque V3b). */

export type FiscalDocumentStatus =
  'pending' | 'contingency' | 'issued' | 'simulated' | 'rejected' | 'failed' | 'invalidated';

export interface FiscalDocument {
  id: string;
  company_id: string;
  branch_id: string;
  sale_id: string;
  sale_code: string | null;
  customer_name: string | null;
  customer_email: string | null;
  establishment_code: string | null;
  point_of_sale_code: string | null;
  document_type: '01' | '03';
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
