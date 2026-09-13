export type PurchaseRequestStatus =
  | 'draft'
  | 'submitted'
  | 'approved'
  | 'rejected'
  | 'partially_quoted'
  | 'quoted'
  | 'partially_ordered'
  | 'completed'
  | 'cancelled';

export interface PurchaseRequestDetailInput {
  product_id: number;
  quantity: number;
  description?: string | null;
  notes?: string | null;
}

export interface PurchaseRequestWrite {
  branch_id: string;
  warehouse_id: string;
  required_date?: string | null;
  justification: string;
  notes?: string | null;
  details: PurchaseRequestDetailInput[];
}

export interface PurchaseRequestDetail {
  id: string;
  purchase_request_id: string;
  product_id: number;
  unit_id: number;
  quantity: string;
  description: string | null;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PurchaseRequest {
  id: string;
  company_id: string;
  code: string;
  branch_id: string;
  warehouse_id: string;
  requested_by_id: string;
  request_date: string;
  required_date: string | null;
  justification: string;
  status: PurchaseRequestStatus;
  notes: string | null;
  details: PurchaseRequestDetail[];
  created_at: string | null;
  updated_at: string | null;
}
