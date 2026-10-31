export interface SalesCustomer {
  id: string;
  company_id: string;
  code: string;
  name: string;
  phone: string | null;
  email: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SalesUnit {
  unit_id: number;
  name: string;
  factor: string;
  packaging_definition_id: string | null;
  packaging_version: number | null;
}

export interface SalesCatalogItem {
  product_id: number;
  variant_id: string | null;
  inventory_item_id: string;
  sku: string;
  name: string;
  base_unit_id: number;
  base_unit_name: string;
  units: SalesUnit[];
}

export interface SalesLineInput {
  product_id: number;
  variant_id: string | null;
  unit_id: number;
  quantity: string;
  unit_price: string;
}

export interface SalesLine {
  id: string;
  source_quotation_line_id: string;
  product_id: number;
  variant_id: string | null;
  inventory_item_id: string;
  product_sku: string;
  product_name: string;
  unit_id: number;
  unit_name: string;
  base_unit_id: number;
  base_unit_name: string;
  unit_factor: string;
  quantity: string;
  quantity_base: string;
  unit_price: string;
  line_total: string;
  quantity_delivered_base: string;
  quantity_pending_base: string;
}

export interface SalesQuotation {
  id: string;
  company_id: string;
  branch_id: string;
  customer_id: string;
  customer_code: string;
  customer_name: string;
  code: string;
  quotation_date: string;
  valid_until: string;
  currency: 'USD';
  subtotal: string;
  total: string;
  status: 'draft' | 'confirmed' | 'cancelled' | 'expired';
  stored_status: 'draft' | 'confirmed' | 'cancelled';
  version: number;
  notes: string | null;
  converted: boolean;
  sale_id: string | null;
  sale_code: string | null;
  lines: SalesLine[];
  created_at: string;
  updated_at: string;
}

export interface Sale {
  id: string;
  company_id: string;
  branch_id: string;
  customer_id: string;
  customer_code: string;
  customer_name: string;
  quotation_id: string;
  quotation_code: string;
  code: string;
  currency: 'USD';
  subtotal: string;
  total: string;
  status: 'draft' | 'confirmed' | 'cancelled';
  version: number;
  notes: string | null;
  delivery_progress: 'pending' | 'partial' | 'complete';
  lines: SalesLine[];
  created_at: string;
  updated_at: string;
}

export interface SalesDeliveryStockUnit {
  handling_unit_id: string;
  code: string;
  inventory_item_id: string;
  quantity_base: string;
  base_unit_name: string;
  lot_code: string | null;
  expiry_date: string | null;
  warehouse_id: string;
  warehouse_name: string;
  location_id: string;
  location_code: string;
  packaging_snapshot: Record<string, unknown> | null;
}

export interface SalesDeliveryStockLine {
  sale_line_id: string;
  product_sku: string;
  product_name: string;
  unit_name: string;
  base_unit_name: string;
  quantity_pending_base: string;
  units: SalesDeliveryStockUnit[];
}

export interface SalesDeliveryAllocation {
  id: string;
  handling_unit_id: string;
  handling_unit_code: string | null;
  warehouse_id: string;
  location_id: string;
  inventory_lot_detail_id: string | null;
  lot_code: string | null;
  expiry_date: string | null;
  quantity_base: string;
  movement_id: string | null;
  movement_line_id: string | null;
  valuation_entry_id: string | null;
}

export interface SalesDeliveryLine {
  id: string;
  sale_line_id: string;
  product_sku: string;
  product_name: string;
  unit_name: string;
  base_unit_name: string;
  quantity_base: string;
  quantity_in_sale_unit: string;
  unit_factor: string;
  allocations: SalesDeliveryAllocation[];
}

export interface SalesDelivery {
  id: string;
  company_id: string;
  branch_id: string;
  sale_id: string;
  code: string;
  status: 'draft' | 'confirmed' | 'cancelled';
  version: number;
  notes: string | null;
  created_by_id: string;
  confirmed_by_id: string | null;
  confirmed_at: string | null;
  cancelled_by_id: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
  lines: SalesDeliveryLine[];
}

export type SalesReturnStatus = 'draft' | 'received' | 'under_review' | 'accepted' | 'rejected' | 'mixed' | 'cancelled';
export type SalesReturnCondition = 'resalable' | 'damaged' | 'wrong_item' | 'other';

export interface SalesReturnEvent {
  id: string;
  decision: 'accepted' | 'rejected';
  quantity_base: string;
  condition: SalesReturnCondition;
  reason: string;
  destination_location_id: string | null;
  movement_id: string | null;
  movement_line_id: string | null;
  valuation_entry_id: string | null;
  actor_id: string;
  created_at: string;
}

export interface SalesReturnLine {
  id: string;
  delivery_id: string;
  delivery_code: string;
  delivery_allocation_id: string;
  source_handling_unit_id: string;
  inventory_item_id: string;
  product_sku: string;
  product_name: string;
  unit_name: string;
  base_unit_name: string;
  lot_code: string | null;
  quantity_received_base: string;
  quantity_accepted_base: string;
  quantity_rejected_base: string;
  quantity_pending_base: string;
  quantity_returnable_base: string;
  reason: string;
  declared_condition: SalesReturnCondition;
  events: SalesReturnEvent[];
}

export interface SalesReturnEvidence {
  document_id: string;
  title: string;
  file_name: string;
}

export interface SalesReturn {
  id: string;
  company_id: string;
  branch_id: string;
  sale_id: string;
  code: string;
  status: SalesReturnStatus;
  notes: string | null;
  created_by_id: string;
  received_by_id: string | null;
  received_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
  evidence: SalesReturnEvidence[];
  lines: SalesReturnLine[];
}

export interface SalesReturnableAllocation {
  delivery_id: string;
  delivery_code: string;
  delivery_line_id: string;
  delivery_allocation_id: string;
  delivery_date: string;
  handling_unit_code: string | null;
  inventory_item_id: string;
  product_sku: string;
  product_name: string;
  unit_name: string;
  base_unit_name: string;
  lot_code: string | null;
  quantity_delivered_base: string;
  quantity_returned_base: string;
  quantity_reserved_base: string;
  quantity_returnable_base: string;
}

export interface SalesFilters {
  branch_id?: string | null;
  customer_id?: string;
  status?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  size?: number;
}

export interface SalesPage<T> {
  items: T[];
  meta: { page: number; size: number; total: number; pages: number };
}
