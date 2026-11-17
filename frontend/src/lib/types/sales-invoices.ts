/** Documento fiscal del pedido (bloque V3b). */

export type FiscalDocumentStatus = 'pending' | 'issued' | 'simulated' | 'rejected' | 'failed';

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
  sent_at: string | null;
  created_at: string | null;
}

export interface FiscalEmailHistory {
  enabled: boolean;
  customer_email: string | null;
  items: FiscalEmail[];
}
