import { apiFetch } from '$lib/api/client';

export interface KardexItemOption {
  inventory_item_id: string;
  product_name: string;
  sku: string | null;
  base_unit_symbol: string;
}

export interface PhysicalKardexRow {
  id: string;
  movement_id: string;
  movement_type: string;
  source_reference: string | null;
  posted_at: string;
  product_name: string;
  product_sku: string | null;
  base_unit_symbol: string;
  lot_code: string | null;
  inventory_lot_detail_id?: string | null;
  receipt_lot_code?: string | null;
  receipt_lot_header_code?: string | null;
  handling_unit_id: string | null;
  handling_unit_code: string | null;
  from_warehouse_id: string | null;
  from_warehouse_external: boolean;
  from_warehouse_code: string | null;
  from_warehouse_name: string | null;
  from_location_id: string | null;
  from_location_code: string | null;
  from_stock_status: string | null;
  to_warehouse_id: string | null;
  to_warehouse_external: boolean;
  to_warehouse_code: string | null;
  to_warehouse_name: string | null;
  to_location_id: string | null;
  to_location_code: string | null;
  to_stock_status: string | null;
  quantity_base: string;
  incoming_quantity: string;
  outgoing_quantity: string;
  net_quantity: string;
  balance_after: string | null;
  is_internal: boolean;
}

export interface PhysicalKardex {
  warehouse_id: string;
  inventory_item_id: string;
  period_from: string;
  period_to: string;
  balance_basis: string;
  opening_known: boolean;
  opening_quantity: string | null;
  incoming_quantity: string;
  outgoing_quantity: string;
  closing_known: boolean;
  closing_quantity: string | null;
  items: PhysicalKardexRow[];
  page: number;
  page_size: number;
  total: number;
}

export interface ReconciliationRow {
  inventory_item_id: string;
  product_name: string;
  sku: string | null;
  base_unit_symbol: string;
  physical_quantity: string;
  valued_quantity: string | null;
  quantity_difference: string | null;
  inventory_value: string | null;
  average_unit_cost: string | null;
}

export interface Reconciliation {
  valuation_enabled: boolean;
  currency: string | null;
  items: ReconciliationRow[];
  page: number;
  page_size: number;
  total: number;
}

export interface ValuationCostBreakdown {
  event_id?: string;
  kind?: string;
  source_reference?: string;
  sequence?: string;
  ledger_page?: string;
  cost_delta?: string;
  credit_net?: string;
  inventory_cost?: string;
  cost_difference?: string;
  cost_adjustment?: string;
  value_delta?: string;
  inventory_delta?: string;
  amount?: string;
}

export interface ValuedKardexEntry {
  id: string;
  sequence: number;
  kind: string;
  quantity_base: string;
  source_value: string;
  original_entry_id: string | null;
  movement_line_id: string | null;
  purchase_detail_id: string | null;
  retaceo_id: string | null;
  source_reference: string;
  operational_date: string;
  accounting_date: string;
  posted_at: string;
  posted_by: string;
  inventory_delta: string;
  balance_quantity: string;
  balance_value: string;
  average_unit_cost: string;
  cost_breakdown: ValuationCostBreakdown[];
}

export interface ValuedKardex {
  inventory_item_id: string;
  setting: { currency: string; opened_at: string; opening_reference: string } | null;
  period_from: string;
  period_to: string;
  opening_known: boolean;
  opening_quantity: string | null;
  opening_value: string | null;
  closing_known: boolean;
  closing_quantity: string | null;
  closing_value: string | null;
  period_value_change: string | null;
  entries: ValuedKardexEntry[];
  page: number;
  page_size: number;
  total: number;
}

export interface KardexPeriod {
  period_from: string;
  period_to: string;
  page?: number;
  page_size?: number;
}

function params(values: Record<string, string | number | undefined>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && String(value).trim() !== '') query.set(key, String(value));
  }
  return query;
}

export const kardexApi = {
  searchItems: (warehouseId: string, query: string) =>
    apiFetch<KardexItemOption[]>(
      `/inventory/kardex/items?${params({ warehouse_id: warehouseId, q: query })}`
    ),
  physical: (filters: {
    warehouse_id: string;
    inventory_item_id: string;
    period_from: string;
    period_to: string;
    movement_type?: string;
    lot_code?: string;
    source_reference?: string;
    page?: number;
    page_size?: number;
  }) => apiFetch<PhysicalKardex>(`/inventory/kardex/physical?${params(filters)}`),
  reconciliation: (page = 1, pageSize = 50) =>
    apiFetch<Reconciliation>(
      `/inventory/kardex/reconciliation?${params({ page, page_size: pageSize })}`
    ),
  valued: (itemId: string, period: KardexPeriod) =>
    apiFetch<ValuedKardex>(
      `/inventory/kardex/valuation?${params({ inventory_item_id: itemId, ...period })}`
    )
};
