import type { PurchaseOrderStatus } from '$lib/types/purchase-order';

export type PurchaseStatus = 'draft' | 'received' | 'verified' | 'cancelled' | 'closed';

export interface PurchaseLineInput {
  purchase_order_detail_id: string;
  quantity_received: number;
}

export interface PurchaseCreateInput {
  purchase_order_id: string;
  supplier_invoice_number: string | null;
  supplier_invoice_date: string | null;
  lines: PurchaseLineInput[];
  notes: string | null;
}

export interface PurchaseUpdateInput {
  supplier_invoice_number: string | null;
  supplier_invoice_date: string | null;
  lines: PurchaseLineInput[];
  notes: string | null;
}

export interface PurchaseDetail {
  id: string;
  purchase_id: string;
  purchase_order_detail_id: string;
  product_id: number;
  quantity_ordered: string;
  quantity_received: string;
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

export interface Purchase {
  id: string;
  company_id: string;
  code: string;
  purchase_order_id: string;
  supplier_id: number;
  branch_id: string;
  warehouse_id: string;
  created_by_id: string;
  purchase_date: string;
  supplier_invoice_number: string | null;
  supplier_invoice_date: string | null;
  currency: string;
  details: PurchaseDetail[];
  subtotal: string;
  discount: string;
  tax: string;
  total: string;
  status: PurchaseStatus;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PurchaseListParams {
  status?: PurchaseStatus;
  supplier_id?: number;
  purchase_order_id?: string;
  branch_id?: string;
  page?: number;
  size?: number;
}

export interface PurchaseReceivableLine {
  purchase_order_detail_id: string;
  product_id: number;
  unit_id: number;
  quantity_ordered: string;
  quantity_received: string;
  quantity_pending: string;
  unit_price: string;
  discount: string;
  tax_rate: string;
  notes: string | null;
}

export interface PurchaseReceivable {
  purchase_order_id: string;
  code: string;
  status: PurchaseOrderStatus;
  supplier_id: number;
  branch_id: string;
  warehouse_id: string;
  currency: string;
  lines: PurchaseReceivableLine[];
}
