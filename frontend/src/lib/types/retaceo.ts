export type RetaceoStatus = 'draft' | 'calculated' | 'verified' | 'closed' | 'cancelled';

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

export interface Retaceo {
  id: string;
  company_id: string;
  code: string;
  purchase_id: string;
  branch_id: string;
  created_by_id: string;
  currency: string;
  details: RetaceoDetail[];
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
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface RetaceoCreateInput {
  purchase_id: string;
  total_freight: string;
  total_expenses: string;
  total_dai: string;
  import_vat: string;
  notes: string | null;
}

export interface RetaceoUpdateInput {
  total_freight: string;
  total_expenses: string;
  total_dai: string;
  import_vat: string;
  notes: string | null;
}

export interface RetaceoListParams {
  status?: RetaceoStatus;
  purchase_id?: string;
  branch_id?: string;
  page?: number;
  size?: number;
}
