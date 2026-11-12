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
  approved_by_id: null,
  approved_by_name: null,
  approved_at: null,
  rejected_by_id: null,
  rejected_by_name: null,
  rejected_at: null,
  rejection_reason: null
} as const satisfies Partial<InventoryTransfer>;

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
