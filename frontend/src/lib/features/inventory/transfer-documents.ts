import { apiFetch } from '$lib/api/client';

export type TransferDecimal = string | number;
export type TransferStatus =
  'preparation' | 'in_transit' | 'received' | 'closed_with_adjustment' | 'incident' | 'cancelled';

export interface TransferDemandRecord {
  purchase_request_detail_id: string;
  purchase_request_id: string;
  request_code: string;
  request_status: string;
  branch_id: string;
  branch_name: string;
  request_date: string;
  required_date: string | null;
  product_id: number;
  inventory_item_id: string | null;
  product_name: string;
  sku: string | null;
  unit_id: number;
  unit_name: string;
  unit_symbol: string | null;
  quantity_requested: TransferDecimal;
  quantity_assigned: TransferDecimal;
  quantity_dispatched: TransferDecimal;
  quantity_in_transit: TransferDecimal;
  quantity_received: TransferDecimal;
  quantity_adjusted_out: TransferDecimal;
  quantity_pending: TransferDecimal;
}

export interface TransferVehicle {
  id: string;
  company_id: string;
  code: string;
  name: string;
  status: 'active' | 'inactive';
  transit_warehouse_id: string;
  transit_warehouse_name: string;
  transit_location_id: string;
  created_at: string;
  fleet_vehicle_id: string | null;
  plate: string | null;
  kind: string | null;
  branch_id: string | null;
  branch_name: string | null;
}

export interface DispatchIssue {
  code: string;
  severity: 'blocking' | 'warning';
  message: string;
  overridable: boolean;
}

export interface DispatchCheck {
  vehicle_id: string;
  driver_id: string | null;
  vehicle_issues: DispatchIssue[];
  driver_issues: DispatchIssue[];
  blocked: boolean;
  hard_blocked: boolean;
  can_override: boolean;
}

export type FitnessState = 'ok' | 'warning' | 'blocked';

/** Vehicle, driver and exception chosen in the dispatch panel. */
export interface DispatchSelection {
  vehicleId: string;
  driverId: string;
  overrideReason: string;
  /** True when the server will accept the dispatch as selected. */
  ready: boolean;
  label: string;
}

export interface DispatchOptions {
  origin_branch_id: string;
  origin_branch_name: string;
  vehicles: Array<{
    inventory_vehicle_id: string;
    fleet_vehicle_id: string;
    code: string;
    plate: string;
    kind: string;
    brand: string;
    model: string;
    compliance_state: FitnessState;
    available: boolean;
    unavailable_reason: string | null;
    driver_id: string | null;
    driver_name: string | null;
  }>;
  drivers: Array<{
    id: string;
    name: string;
    license_class: string;
    compliance_state: FitnessState;
    current_vehicle_code: string | null;
  }>;
}

export interface TransferVehicleReference {
  id: string;
  code: string;
  name: string;
  status: string;
  transit_warehouse_id?: string | null;
  fleet_vehicle_id?: string | null;
  plate?: string | null;
}

export interface TransferDemandAllocation {
  purchase_request_detail_id: string;
  request_id: string;
  request_code: string;
  branch_id: string;
  branch_name: string;
  quantity_requested: TransferDecimal;
  allocated_quantity: TransferDecimal;
  quantity_dispatched: TransferDecimal;
  quantity_received: TransferDecimal;
  quantity_adjusted_out: TransferDecimal;
}

export interface TransferReceipt {
  id: string;
  movement_id: string;
  handling_unit_id: string;
  handling_unit_code: string | null;
  quantity_received: TransferDecimal;
  received_by_id: string;
  received_at: string;
}

export interface TransferLine {
  id: string;
  line_number: number;
  inventory_item_id: string;
  product_id: number | null;
  variant_id: string | null;
  sku: string | null;
  product_name: string;
  base_unit_id: number | null;
  base_unit_name: string | null;
  base_unit_symbol: string | null;
  presentation_name: string | null;
  inventory_lot_detail_id: string | null;
  inventory_lot_detail_code: string | null;
  source_handling_unit_id: string;
  source_handling_unit_code: string | null;
  transit_handling_unit_id: string | null;
  transit_handling_unit_code: string | null;
  quantity_planned: TransferDecimal;
  quantity_dispatched: TransferDecimal;
  quantity_received: TransferDecimal;
  quantity_in_transit: TransferDecimal;
  quantity_returned: TransferDecimal;
  quantity_adjusted_out: TransferDecimal;
  excess_reason: string | null;
  notes: string | null;
  demand_allocations: TransferDemandAllocation[];
  receipts: TransferReceipt[];
}

export interface TransferIncident {
  id: string;
  status: 'open' | 'resolved';
  reason: string;
  evidence_reference: string | null;
  opened_by_id: string;
  opened_at: string;
  resolution: string | null;
  resolution_notes: string | null;
  resolved_by_id: string | null;
  resolved_at: string | null;
}

export interface InventoryTransfer {
  id: string;
  company_id: string;
  code: string;
  origin_warehouse_id: string;
  origin_warehouse_name: string;
  origin_branch_id: string | null;
  destination_warehouse_id: string;
  destination_warehouse_name: string;
  destination_branch_id: string | null;
  vehicle: TransferVehicleReference | null;
  driver?: { id: string; name: string; employee_code: string } | null;
  compliance_override_reason?: string | null;
  status: TransferStatus;
  notes: string | null;
  created_by_id: string;
  created_at: string;
  dispatched_by_id: string | null;
  dispatched_at: string | null;
  received_by_id: string | null;
  received_at: string | null;
  dispatch_movement_id: string | null;
  lines: TransferLine[];
  incidents: TransferIncident[];
}

export interface TransferLineInput {
  handling_unit_id: string;
  quantity_base: string;
  inventory_lot_detail_id?: string | null;
  demand_allocations?: Array<{
    purchase_request_detail_id: string;
    allocated_quantity: string;
  }>;
  excess_reason?: string | null;
  notes?: string | null;
}

export interface TransferCreateInput {
  idempotency_key: string;
  origin_warehouse_id: string;
  destination_warehouse_id: string;
  vehicle_id: string | null;
  notes: string | null;
  lines: TransferLineInput[];
}

export type TransferUpdateInput = TransferCreateInput;

const root = '/inventory/transfers';

export const inventoryTransfersApi = {
  listDemand: (branchId: string, productId?: number) => {
    const query = new URLSearchParams({ branch_id: branchId, limit: '1000' });
    if (productId != null) query.set('product_id', String(productId));
    return apiFetch<TransferDemandRecord[]>(`${root}/demand?${query.toString()}`);
  },

  /** Read-only: vehicles are registered and edited in Fleet. */
  listVehicles: () => apiFetch<TransferVehicle[]>(`${root}/vehicles`),

  dispatchOptions: (transferId: string) =>
    apiFetch<DispatchOptions>(`${root}/${encodeURIComponent(transferId)}/dispatch-options`),

  dispatchCheck: (transferId: string, vehicleId: string, driverId?: string | null) =>
    apiFetch<DispatchCheck>(`${root}/${encodeURIComponent(transferId)}/dispatch-check`, {
      method: 'POST',
      body: JSON.stringify({ vehicle_id: vehicleId, driver_id: driverId || null })
    }),

  list: (filters: { status?: TransferStatus; page?: number; size?: number } = {}) => {
    const query = new URLSearchParams({
      page: String(filters.page ?? 1),
      size: String(filters.size ?? 50)
    });
    if (filters.status) query.set('status', filters.status);
    return apiFetch<InventoryTransfer[]>(`${root}?${query.toString()}`);
  },

  get: (transferId: string) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}`),

  create: (body: TransferCreateInput) =>
    apiFetch<InventoryTransfer>(root, { method: 'POST', body: JSON.stringify(body) }),

  update: (transferId: string, body: TransferUpdateInput) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}`, {
      method: 'PUT',
      body: JSON.stringify(body)
    }),

  cancel: (transferId: string, idempotencyKey: string) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ idempotency_key: idempotencyKey })
    }),

  dispatch: (
    transferId: string,
    vehicleId: string,
    idempotencyKey: string,
    options: { driverId?: string | null; overrideReason?: string | null } = {}
  ) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}/dispatch`, {
      method: 'POST',
      body: JSON.stringify({
        vehicle_id: vehicleId,
        idempotency_key: idempotencyKey,
        driver_id: options.driverId || null,
        override_reason: options.overrideReason?.trim() || null
      })
    }),

  receive: (
    transferId: string,
    idempotencyKey: string,
    lines: Array<{
      transfer_detail_id: string;
      destination_location_id: string;
      quantity_base: string;
    }>
  ) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}/receive`, {
      method: 'POST',
      body: JSON.stringify({ idempotency_key: idempotencyKey, lines })
    }),

  openIncident: (
    transferId: string,
    body: { idempotency_key: string; reason: string; evidence_reference: string | null }
  ) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}/incidents`, {
      method: 'POST',
      body: JSON.stringify(body)
    }),

  resolveIncident: (
    transferId: string,
    body: {
      idempotency_key: string;
      resolution: 'resume_transit' | 'close_received';
      resolution_notes: string;
    }
  ) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}/incidents/resolve`, {
      method: 'POST',
      body: JSON.stringify(body)
    })
};
