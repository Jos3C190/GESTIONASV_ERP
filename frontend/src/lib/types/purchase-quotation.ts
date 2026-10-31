export type PurchaseQuotationStatus =
  | 'draft'
  | 'requested'
  | 'received'
  | 'under_evaluation'
  | 'selected'
  | 'not_selected'
  | 'rejected'
  | 'expired'
  | 'cancelled';

export interface PurchaseQuotationRequestLineInput {
  purchase_request_detail_id: string;
  quantity: number;
}

export interface PurchaseQuotationRequestInput {
  purchase_request_id: string;
  lines: PurchaseQuotationRequestLineInput[];
}

export interface PurchaseQuotationCreateInput {
  supplier_id: number;
  currency: string;
  requests: PurchaseQuotationRequestInput[];
  notes: string | null;
}

export interface PurchaseQuotationFromConsolidationInput {
  supplier_id: number;
  currency: string;
  consolidation_line_ids: string[];
  notes: string | null;
}

export interface PurchaseQuotationResponseLineInput {
  product_id: number;
  unit_id: number;
  offered_quantity: number;
  unit_price: number;
  discount: number;
  tax_rate: number;
  delivery_days: number | null;
  available_quantity: number | null;
  notes: string | null;
}

export interface PurchaseQuotationExpenseInput {
  expense_type_id: string;
  amount: number;
  description: string | null;
}

export interface PurchaseQuotationRecordResponseInput {
  quotation_date: string;
  valid_until: string | null;
  payment_terms: string | null;
  delivery_days: number | null;
  lines: PurchaseQuotationResponseLineInput[];
  expenses: PurchaseQuotationExpenseInput[];
  notes: string | null;
}

export interface PurchaseQuotationRequestDetail {
  id: string;
  purchase_quotation_request_id: string;
  purchase_quotation_detail_id: string;
  purchase_request_detail_id: string;
  quantity: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface PurchaseQuotationRequestLink {
  id: string;
  purchase_quotation_id: string;
  purchase_request_id: string;
  details: PurchaseQuotationRequestDetail[];
  created_at: string | null;
  updated_at: string | null;
}

export interface PurchaseQuotationDetail {
  id: string;
  purchase_quotation_id: string;
  product_id: number;
  unit_id: number;
  quantity: string;
  unit_price: string;
  discount: string;
  subtotal: string;
  tax_rate: string;
  tax_amount: string;
  total: string;
  delivery_days: number | null;
  available_quantity: string | null;
  notes: string | null;
  offered_quantity: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PurchaseQuotationSourceSnapshot {
  purchase_request_id: string;
  purchase_request_detail_id: string;
  request_code: string;
  branch_name: string | null;
  warehouse_name: string | null;
  requester_name: string | null;
  required_date: string | null;
  included_quantity: string;
}

export interface PurchaseQuotationLineSnapshot {
  purchase_quotation_detail_id: string;
  consolidation_line_id: string;
  product_sku: string;
  product_name: string;
  unit_name: string;
  branch_quantity: string;
  central_quantity: string;
  sources: PurchaseQuotationSourceSnapshot[];
}

export interface PurchaseQuotationDocumentInitiateInput {
  file_name: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256: string;
}

export interface PurchaseQuotationDocument {
  id: string;
  purchase_quotation_id: string;
  document_id: string;
  file_name: string;
  file_type: string;
  size_bytes: number;
  status: string;
  failure_code: string | null;
  uploaded_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PurchaseQuotationDocumentUpload {
  document: PurchaseQuotationDocument;
  upload_url: string;
  method: 'PUT';
  required_headers: Record<string, string>;
  expires_at: string;
}

export interface PurchaseQuotationDocumentDownloadUrl {
  url: string;
  expires_at: string;
}

export interface PurchaseQuotationExpense {
  id: string;
  purchase_quotation_id: string;
  expense_type_id: string;
  amount: string;
  description: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PurchaseQuotation {
  id: string;
  company_id: string;
  code: string;
  supplier_id: number;
  quotation_date: string;
  currency: string;
  created_by_id: string;
  request_links: PurchaseQuotationRequestLink[];
  details: PurchaseQuotationDetail[];
  expenses: PurchaseQuotationExpense[];
  valid_until: string | null;
  payment_terms: string | null;
  delivery_days: number | null;
  subtotal: string;
  discount: string;
  tax: string;
  total: string;
  status: PurchaseQuotationStatus;
  notes: string | null;
  response_notes: string | null;
  consolidation_id: string | null;
  consolidation_code: string | null;
  version_number: number;
  sent_at: string | null;
  snapshots: PurchaseQuotationLineSnapshot[];
  created_at: string | null;
  updated_at: string | null;
}

export interface PurchaseQuotationComparison {
  quotation_id: string;
  code: string;
  supplier_id: number;
  currency: string;
  total: string;
  delivery_days: number | null;
  valid_until: string | null;
  status: PurchaseQuotationStatus;
}

export interface PurchaseQuotationListParams {
  status?: PurchaseQuotationStatus;
  supplier_id?: number;
  branch_id?: string | null;
  page?: number;
  size?: number;
}
