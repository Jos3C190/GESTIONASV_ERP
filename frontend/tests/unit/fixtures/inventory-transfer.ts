import type { InventoryTransfer } from '../../../src/lib/features/inventory/transfer-documents';

/** Fields every transfer carries; spread them first and override what a test cares about. */
export const transferDefaults = {
  origin_branch_name: 'Casa matriz',
  origin_is_central: true,
  destination_branch_name: 'Sucursal Centro',
  destination_is_central: false,
  route_type: 'central_distribution',
  requires_approval: false,
  approval_round: 0,
  submitted_by_id: null,
  submitted_by_name: null,
  submitted_at: null,
  last_edited_by_id: null,
  last_edited_by_name: null,
  approved_by_id: null,
  approved_by_name: null,
  approved_at: null,
  rejected_by_id: null,
  rejected_by_name: null,
  rejected_at: null,
  rejection_reason: null,
  approved_vehicle: null,
  approved_driver: null,
  assignment_substitution: null,
  closed_at: null,
  origin_count_pending: false,
  has_open_discrepancies: false,
  valuation_ready: true,
  discrepancies: []
} as const satisfies Partial<InventoryTransfer>;

/** A transfer line with the quantities of a dispatched, untouched line. */
export function makeLine(
  overrides: Partial<InventoryTransfer['lines'][number]> = {}
): InventoryTransfer['lines'][number] {
  return {
    id: 'line-1',
    line_number: 1,
    inventory_item_id: 'item-1',
    product_id: 1,
    variant_id: null,
    sku: 'SKU-DEMO',
    product_name: 'Producto de prueba',
    base_unit_id: 1,
    base_unit_name: 'Unidad',
    base_unit_symbol: 'u',
    presentation_name: null,
    inventory_lot_detail_id: null,
    inventory_lot_detail_code: null,
    source_handling_unit_id: 'hu-source',
    source_handling_unit_code: 'HU-SOURCE',
    transit_handling_unit_id: 'hu-transit',
    transit_handling_unit_code: 'HU-TRANSIT',
    quantity_planned: '3',
    quantity_dispatched: '3',
    quantity_received: '0',
    quantity_in_transit: '3',
    quantity_returned: '0',
    quantity_adjusted_out: '0',
    quantity_received_damaged: '0',
    quantity_surplus: '0',
    quantity_short_open: '0',
    quantity_pending_reception: '3',
    excess_reason: null,
    notes: null,
    demand_allocations: [],
    receipts: [],
    ...overrides
  };
}

export function makeTransfer(overrides: Partial<InventoryTransfer> = {}): InventoryTransfer {
  return {
    ...transferDefaults,
    id: 'transfer-a',
    company_id: 'company-1',
    code: 'TR-DEMO-A',
    origin_warehouse_id: 'origin',
    origin_warehouse_name: 'Central',
    origin_branch_id: 'matrix',
    destination_warehouse_id: 'destination',
    destination_warehouse_name: 'Sucursal',
    destination_branch_id: 'branch',
    vehicle: null,
    status: 'preparation',
    notes: null,
    created_by_id: 'user-1',
    created_at: '2026-10-19T12:00:00Z',
    dispatched_by_id: null,
    dispatched_at: null,
    received_by_id: null,
    received_at: null,
    dispatch_movement_id: null,
    lines: [],
    incidents: [],
    ...overrides
  };
}

/** An open damage difference; override the kind, status and quantities a test cares about. */
export function makeDiscrepancy(
  overrides: Partial<InventoryTransfer['discrepancies'][number]> = {}
): InventoryTransfer['discrepancies'][number] {
  return {
    id: 'disc-1',
    transfer_detail_id: 'line-1',
    line_number: 1,
    product_name: 'Producto de prueba',
    sku: 'SKU-DEMO',
    base_unit_symbol: 'u',
    kind: 'damage',
    status: 'open',
    source: 'receipt',
    quantity: '2',
    damage_type: 'broken',
    notes: 'Cajas rotas al descargar',
    evidence_reference: null,
    location_id: 'loc-1',
    location_code: 'QUA-01',
    handling_unit_id: 'hu-1',
    handling_unit_code: 'HU-DAMAGED',
    receipt_id: 'receipt-1',
    incident_id: null,
    opened_by_id: 'user-1',
    opened_by_name: 'Ana Receptora',
    opened_at: '2026-10-20T12:00:00Z',
    claim_reference: null,
    claimed_by_id: null,
    claimed_by_name: null,
    claimed_at: null,
    resolution: null,
    resolution_notes: null,
    resolved_by_id: null,
    resolved_by_name: null,
    resolved_at: null,
    origin_count_required: false,
    origin_counted_by_id: null,
    origin_counted_by_name: null,
    origin_counted_at: null,
    origin_count_notes: null,
    adjustment: null,
    ...overrides
  };
}
