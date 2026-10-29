export type RetaceoStatus = 'draft' | 'calculated' | 'verified' | 'closed' | 'cancelled';
export interface RetaceoImportData {
  origin_country: string | null;
  import_invoice_number: string | null;
  import_invoice_date: string | null;
  import_policy_number: string | null;
  import_policy_date: string | null;
}
export type RetaceoCostClass = 'freight' | 'expense' | 'dai' | 'import_vat';

export interface RetaceoAverageComparison {
  value_only?: boolean;
  currency: string;
  mode: 'preview' | 'posted';
  lines: Array<{
    product_id: number;
    inventory_item_id: string;
    base_unit_id: number;
    previous_quantity: string;
    previous_value: string;
    previous_average: string;
    incoming_quantity: string;
    incoming_value: string;
    resulting_quantity: string;
    resulting_value: string;
    resulting_average: string;
  }>;
}

export interface RetaceoCostAllocation {
  purchase_detail_id: string;
  amount: string;
}

export interface RetaceoCostDocument {
  id: string;
  retaceo_cost_id: string;
  document_id: string;
  file_name: string;
  file_type: string;
  size_bytes?: number | null;
  status?: string | null;
  failure_code?: string | null;
  uploaded_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface RetaceoCost {
  incurred_on?: string | null;
  id: string;
  retaceo_id: string;
  source_purchase_order_expense_id: string | null;
  expense_type_id: string | null;
  classification: RetaceoCostClass;
  title: string;
  description: string | null;
  amount: string;
  is_active: boolean;
  allocations: RetaceoCostAllocation[];
  documents: RetaceoCostDocument[];
  created_at: string | null;
  updated_at: string | null;
}

export interface RetaceoCostDraftInput {
  expense_type_id?: string | null;
  source_purchase_order_expense_id?: string | null;
  incurred_on?: string | null;
  id?: string;
  classification: RetaceoCostClass;
  title: string;
  description: string | null;
  amount: string;
  allocations: RetaceoCostAllocation[];
}

export interface RetaceoCostDocumentUpload {
  document: RetaceoCostDocument;
  upload_url: string;
  method: 'PUT';
  required_headers: Record<string, string>;
  expires_at: string;
}

export interface RetaceoCostDocumentDownloadUrl {
  url: string;
  expires_at: string;
}

export interface RetaceoDetail {
  id: string;
  retaceo_id: string;
  purchase_detail_id: string;
  product_id: number;
  unit_id: number;
  quantity: string;
  cost_fob: string;
  freight: string;
  expenses: string;
  dai: string;
  total_cost: string;
  unit_cost: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface Retaceo extends Partial<RetaceoImportData> {
  manual_entry?: boolean;
  id: string;
  company_id: string;
  code: string;
  purchase_id: string;
  branch_id: string | null;
  created_by_id: string;
  currency: string;
  details: RetaceoDetail[];
  costs?: RetaceoCost[];
  total_fob: string;
  total_freight: string;
  total_expenses: string;
  total_dai: string;
  import_vat: string;
  total_cost: string;
  freight_percentage: string;
  expense_percentage: string;
  dai_percentage: string;
  status: RetaceoStatus;
  applied_at?: string | null;
  applied_by?: string | null;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface RetaceoCreateInput {
  import_data?: RetaceoImportData;
  fob_lines?: Array<{ purchase_detail_id: string; amount: string }>;
  purchase_id: string;
  total_freight: string;
  total_expenses: string;
  total_dai: string;
  import_vat: string;
  notes: string | null;
}

export interface RetaceoUpdateInput {
  import_data?: RetaceoImportData;
  fob_lines?: Array<{ purchase_detail_id: string; amount: string }>;
  total_freight: string;
  total_expenses: string;
  total_dai: string;
  import_vat: string;
  notes: string | null;
  costs?: RetaceoCostDraftInput[];
}

export interface RetaceoListParams {
  status?: RetaceoStatus;
  purchase_id?: string;
  branch_id?: string;
  page?: number;
  size?: number;
}
