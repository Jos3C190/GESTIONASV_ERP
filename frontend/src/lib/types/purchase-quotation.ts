export type PurchaseQuotationStatus =
  | 'draft'
  | 'requested'
  | 'received'
  | 'under_evaluation'
  | 'selected'
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

export interface PurchaseQuotationResponseLineInput {
  product_id: number;
  unit_id: number;
  quantity: number;
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
  created_at: string | null;
  updated_at: string | null;
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
  page?: number;
  size?: number;
}
