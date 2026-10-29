import type { PageResponse } from '$lib/api/catalog';

export type PurchaseConsolidationStatus = 'draft' | 'frozen' | 'closed' | 'cancelled';
export type PurchaseWorkItemType = 'individual' | 'consolidated';
export type BranchDemandLevel = 'low' | 'medium' | 'high';

export interface PurchaseWorkItem {
  id: string;
  code: string;
  item_type: PurchaseWorkItemType;
  status: string;
  request_date: string;
  requester_name: string | null;
  required_date: string | null;
  branch_id: string | null;
  branch_name: string | null;
  warehouse_id: string | null;
  warehouse_name: string | null;
  line_count: number;
  source_count: number;
}

export interface ApprovedRequestCandidate {
  id: string;
  code: string;
  request_date: string;
  requester_name: string | null;
  required_date: string | null;
  branch_id: string;
  branch_name: string | null;
  warehouse_id: string;
  warehouse_name: string | null;
  line_count: number;
  details: ApprovedRequestCandidateDetail[];
}

export interface ApprovedRequestCandidateDetail {
  id: string;
  product_id: number;
  product_sku?: string;
  product_name?: string;
  unit_id: number;
  unit_name?: string;
  quantity: string;
  request_count?: number;
}

export type SelectedRequestEligibility =
  | 'eligible'
  | 'already_consolidated'
  | 'not_eligible'
  | 'unavailable';

export interface SelectedRequestConsolidationReference {
  id: string;
  code: string;
  status: PurchaseConsolidationStatus;
}

export interface SelectedPurchaseRequestResolution {
  id: string;
  code: string;
  eligibility: SelectedRequestEligibility;
  consolidations: SelectedRequestConsolidationReference[];
}

export interface ConsolidationSource {
  id: string;
  purchase_request_id: string;
  purchase_request_detail_id: string;
  request_code: string;
  branch_id: string;
  branch_name: string | null;
  warehouse_id: string;
  warehouse_name: string | null;
  requester_name: string | null;
  required_date: string | null;
  requested_quantity: string;
  included_quantity: string;
  reason: string | null;
  demand_level?: BranchDemandLevel | null;
}

export interface ConsolidationLine {
  id: string;
  product_id: number;
  product_sku: string;
  product_name: string;
  unit_id: number;
  unit_name: string;
  branch_quantity: string;
  central_quantity: string;
  central_reason: string | null;
  total_quantity: string;
  sources: ConsolidationSource[];
}

export interface ConsolidationEvent {
  id: string;
  actor_id: string;
  action: string;
  reason: string;
  changes: Record<string, unknown>;
  created_at: string;
}

export interface ProductStockSnapshot {
  product_id: number;
  inventory_item_id: string | null;
  base_unit_id: number | null;
  base_unit_name: string | null;
  is_active: boolean | null;
  available_quantity: string;
  in_transit_quantity: string;
  quarantine_quantity: string;
  blocked_quantity: string;
  damaged_quantity: string;
}

export interface PurchaseConsolidationInventorySnapshot {
  warehouse_id: string;
  checked_at: string;
  reservation_data_available: boolean;
  items: ProductStockSnapshot[];
}

export interface PurchaseConsolidationAwardOffer {
  quotation_id: string;
  quotation_code: string;
  quotation_version: number;
  supplier_id: number;
  quotation_status: string;
  currency: string;
  valid_until: string | null;
  delivery_days: number | null;
  payment_terms: string | null;
  quotation_total: string;
  quotation_expenses_total: string;
  quotation_detail_id: string;
  requested_quantity: string;
  offered_quantity: string | null;
  available_quantity: string | null;
  awarded_quantity: string;
  remaining_offer_quantity: string;
  unit_price: string;
  discount: string;
  subtotal: string;
  tax_rate: string;
  tax_amount: string;
  line_total: string;
  line_delivery_days: number | null;
  notes: string | null;
  can_award: boolean;
  blocked_reason: string | null;
}

export interface PurchaseConsolidationAwardDecision {
  id: string;
  quotation_id: string;
  quotation_code: string;
  supplier_id: number;
  quantity: string;
  reason: string;
  decided_by_id: string;
  created_at: string | null;
  revoked_at: string | null;
  revoked_by_id: string | null;
  revocation_reason: string | null;
  ordered_quantity: string;
  remaining_to_order_quantity: string;
}

export interface PurchaseConsolidationAwardLine {
  id: string;
  product_id: number;
  product_sku: string;
  product_name: string;
  unit_id: number;
  unit_name: string;
  demand_quantity: string;
  awarded_quantity: string;
  remaining_quantity: string;
  offers: PurchaseConsolidationAwardOffer[];
  decisions: PurchaseConsolidationAwardDecision[];
}

export interface PurchaseConsolidationAwardBoard {
  consolidation_id: string;
  consolidation_code: string;
  lines: PurchaseConsolidationAwardLine[];
  currencies: string[];
}

export interface PurchaseConsolidation {
  id: string;
  company_id: string;
  code: string;
  period_start: string;
  period_end: string;
  status: PurchaseConsolidationStatus;
  created_by_id: string;
  created_at: string | null;
  updated_at: string | null;
  central_warehouse_id: string | null;
  central_warehouse_name: string | null;
  notes: string | null;
  lines: ConsolidationLine[];
  events: ConsolidationEvent[];
}

export type PurchaseWorkItemPage = PageResponse<PurchaseWorkItem>;
export type ApprovedRequestCandidatePage = PageResponse<ApprovedRequestCandidate>;
