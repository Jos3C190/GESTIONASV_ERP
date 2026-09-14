export type PurchaseOrderStatus =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'sent'
  | 'partially_received'
  | 'received'
  | 'cancelled'
  | 'closed';

export interface PurchaseOrderExpenseType {
  id: string;
  name: string;
  description: string | null;
}

export interface PurchaseOrderLineInput {
  purchase_quotation_detail_id: string;
  quantity: number;
}

export interface PurchaseOrderExpenseInput {
  expense_type_id: string;
  amount: number;
  description: string | null;
}

export interface PurchaseOrderCreateInput {
  purchase_quotation_id: string;
  branch_id: string;
  warehouse_id: string;
  expected_date: string | null;
  lines: PurchaseOrderLineInput[];
  expenses: PurchaseOrderExpenseInput[];
  notes: string | null;
}

export interface PurchaseOrderUpdateInput {
  branch_id: string;
  warehouse_id: string;
  expected_date: string | null;
  lines: PurchaseOrderLineInput[];
  expenses: PurchaseOrderExpenseInput[];
  notes: string | null;
}

export interface PurchaseOrderDetail {
  id: string;
  purchase_order_id: string;
  purchase_quotation_detail_id: string;
  product_id: number;
  quantity: string;
  unit_id: number;
  unit_price: string;
  discount: string;
  subtotal: string;
  tax_rate: string;
  tax_amount: string;
  total: string;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PurchaseOrderExpense {
  id: string;
  purchase_order_id: string;
  expense_type_id: string;
  amount: string;
  description: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PurchaseOrder {
  id: string;
  company_id: string;
  code: string;
  supplier_id: number;
  branch_id: string;
  warehouse_id: string;
  purchase_quotation_id: string;
  created_by_id: string;
  order_date: string;
  expected_date: string | null;
  currency: string;
  payment_terms: string | null;
  details: PurchaseOrderDetail[];
  expenses: PurchaseOrderExpense[];
  subtotal: string;
  discount: string;
  tax: string;
  additional_expenses: string;
  total: string;
  status: PurchaseOrderStatus;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PurchaseOrderListParams {
  status?: PurchaseOrderStatus;
  supplier_id?: number;
  page?: number;
  size?: number;
}

export interface PurchaseOrderExpenseDocumentInitiateInput {
  file_name: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256: string;
}

export interface PurchaseOrderExpenseDocument {
  id: string;
  purchase_order_expense_id: string;
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

export interface PurchaseOrderExpenseDocumentUpload {
  document: PurchaseOrderExpenseDocument;
  upload_url: string;
  method: 'PUT';
  required_headers: Record<string, string>;
  expires_at: string;
}

export interface PurchaseOrderExpenseDocumentDownloadUrl {
  url: string;
  expires_at: string;
}
