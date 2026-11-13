import { apiFetch } from '$lib/api/client';
import type { InventoryAdjustment } from './adjustments';

export type TransferDecimal = string | number;
export type TransferStatus =
  | 'preparation'
  | 'pending_approval'
  | 'approved'
  | 'in_transit'
  | 'partially_received'
  | 'discrepancy'
  | 'received'
  | 'closed_with_adjustment'
  | 'incident'
  | 'cancelled';

/** How the two warehouses of a transfer relate; the server decides it from the pair. */
export type TransferRouteType = 'central_distribution' | 'branch_to_branch' | 'branch_to_central';

/** The company's transfer rules. */
export interface TransferPolicyFlags {
  allow_branch_to_branch: boolean;
  allow_branch_to_central: boolean;
  require_approval: boolean;
}

export interface TransferPolicy extends TransferPolicyFlags {
  updated_at: string | null;
  /** Transfers that turning a route off would freeze. */
  pending_count: number;
  approved_count: number;
}

export interface TransferWarehouseOption {
  id: string;
  code: string | null;
  name: string;
  branch_id: string;
  branch_name: string;
  is_central: boolean;
}

export interface TransferDestinationOption extends TransferWarehouseOption {
  /** The route that would join this warehouse to the chosen origin. */
  route_type: TransferRouteType;
}

export interface TransferRouteOptions {
  policy: TransferPolicyFlags;
  origins: TransferWarehouseOption[];
  destinations: TransferDestinationOption[];
}

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

/** Why the vehicle or the driver of an approved transfer was replaced at dispatch. */
export type SubstitutionCode =
  | 'vehicle_unfit'
  | 'vehicle_unavailable'
  | 'driver_unfit'
  | 'driver_unavailable'
  | 'load_change'
  | 'other';

/** Vehicle, driver and exception chosen in the dispatch panel. */
export interface DispatchSelection {
  vehicleId: string;
  driverId: string;
  overrideReason: string;
  /** Only when the approved vehicle or driver was changed. */
  substitutionCode: SubstitutionCode | '';
  substitutionReason: string;
  /** True when the server will accept the dispatch as selected. */
  ready: boolean;
  label: string;
}

export interface TransportVehicleOption {
  inventory_vehicle_id: string;
  fleet_vehicle_id: string;
  code: string;
  plate: string | null;
  kind: string;
  brand: string;
  model: string;
  compliance_state: FitnessState;
  available: boolean;
  unavailable_reason: string | null;
  /** Something to know that does not stop the choice (e.g. it is on the road now). */
  note?: string | null;
  driver_id: string | null;
  driver_name: string | null;
}

export interface TransportDriverOption {
  id: string;
  name: string;
  license_class: string;
  compliance_state: FitnessState;
  current_vehicle_code: string | null;
}

export interface DispatchOptions {
  origin_branch_id: string;
  origin_branch_name: string;
  vehicles: TransportVehicleOption[];
  drivers: TransportDriverOption[];
  /** What was saved at preparation, and what the approver authorised. */
  planned_vehicle_id?: string | null;
  planned_driver_id?: string | null;
  approved_vehicle_id?: string | null;
  approved_driver_id?: string | null;
}

/** Vehicles and drivers of the origin branch that can be chosen while preparing. */
export type AssignmentOptions = DispatchOptions;

export interface PlanningConflict {
  transfer_id: string;
  code: string;
  status: string;
  same_vehicle: boolean;
  same_driver: boolean;
  message: string;
}

/** The judgement of a transport chosen ahead of time (departure-time problems are warnings). */
export interface AssignmentCheck {
  vehicle_id: string | null;
  driver_id: string | null;
  vehicle_issues: DispatchIssue[];
  driver_issues: DispatchIssue[];
  /** The transport cannot be planned at all. */
  planning_blocked: boolean;
  warnings: number;
  conflicts: PlanningConflict[];
  load_kg: TransferDecimal | null;
  load_missing_weight: number;
}

/** What the transport picker concluded about the vehicle and driver currently chosen. */
export interface TransportJudgement {
  mode: 'planning' | 'dispatch';
  fitness: FitnessState;
  vehicleIssues: DispatchIssue[];
  driverIssues: DispatchIssue[];
  /** The transport cannot be used (planning: cannot be planned; dispatch: cannot leave as is). */
  blocked: boolean;
  /** Dispatch only: not even an authorised exception lets it leave. */
  hardBlocked: boolean;
  /** Dispatch only: an authorised user may leave with a documented exception. */
  canOverride: boolean;
  conflicts: PlanningConflict[];
  loadKg: TransferDecimal | null;
  missingWeight: number;
  /** The driver the server will use (the chosen one or the one assigned in Fleet). */
  driverId: string | null;
}

export interface AssignmentCheckInput {
  origin_warehouse_id: string;
  vehicle_id: string;
  driver_id: string | null;
  /** The saved transfer being edited, if any. */
  transfer_id?: string | null;
  /** The draft's lines give the weight; without them, the saved transfer's. */
  lines?: Array<{ handling_unit_id: string; quantity_base: string }>;
}

export interface TransferDriverReference {
  id: string;
  name: string;
  employee_code: string;
}

/** Set when the approved vehicle or driver was replaced at dispatch. */
export interface TransferAssignmentSubstitution {
  code: SubstitutionCode;
  reason: string;
  by_id: string;
  by_name?: string | null;
  at: string;
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
  quantity_damaged: TransferDecimal;
}

export type ReceiptCondition = 'good' | 'damaged';

export interface TransferReceipt {
  id: string;
  movement_id: string;
  handling_unit_id: string;
  handling_unit_code: string | null;
  quantity_received: TransferDecimal;
  condition: ReceiptCondition;
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
  /** Part of `quantity_received` that arrived damaged. */
  quantity_received_damaged: TransferDecimal;
  quantity_surplus: TransferDecimal;
  /** Declared missing when the reception was closed, still to be resolved. */
  quantity_short_open: TransferDecimal;
  /** What has not arrived yet and is still being waited for. */
  quantity_pending_reception: TransferDecimal;
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

export type DiscrepancyKind = 'shortage' | 'surplus' | 'damage';
export type DiscrepancyStatus = 'open' | 'in_claim' | 'resolved' | 'cancelled';
export type DiscrepancySource = 'receipt' | 'reception_close' | 'incident';
export type DiscrepancyResolution =
  | 'written_off'
  | 'found'
  | 'released'
  | 'regularized'
  | 'dismissed';
export type DamageType =
  | 'broken'
  | 'crushed'
  | 'wet'
  | 'contaminated'
  | 'packaging'
  | 'tampered'
  | 'temperature'
  | 'other';

export interface TransferDiscrepancy {
  id: string;
  transfer_detail_id: string;
  line_number: number | null;
  product_name: string;
  sku: string | null;
  base_unit_symbol: string | null;
  kind: DiscrepancyKind;
  status: DiscrepancyStatus;
  source: DiscrepancySource;
  quantity: TransferDecimal;
  damage_type: DamageType | null;
  notes: string;
  evidence_reference: string | null;
  location_id: string | null;
  location_code: string | null;
  handling_unit_id: string | null;
  handling_unit_code: string | null;
  receipt_id: string | null;
  incident_id: string | null;
  opened_by_id: string;
  opened_by_name: string | null;
  opened_at: string;
  claim_reference: string | null;
  claimed_by_id: string | null;
  claimed_by_name: string | null;
  claimed_at: string | null;
  resolution: DiscrepancyResolution | null;
  resolution_notes: string | null;
  resolved_by_id: string | null;
  resolved_by_name: string | null;
  resolved_at: string | null;
  origin_count_required: boolean;
  origin_counted_by_id: string | null;
  origin_counted_by_name: string | null;
  origin_counted_at: string | null;
  origin_count_notes: string | null;
  adjustment: { id: string; code: string; status: string } | null;
}

export interface InventoryTransfer {
  id: string;
  company_id: string;
  code: string;
  origin_warehouse_id: string;
  origin_warehouse_name: string;
  origin_branch_id: string | null;
  origin_branch_name: string | null;
  origin_is_central: boolean;
  destination_warehouse_id: string;
  destination_warehouse_name: string;
  destination_branch_id: string | null;
  destination_branch_name: string | null;
  destination_is_central: boolean;
  vehicle: TransferVehicleReference | null;
  driver?: TransferDriverReference | null;
  /** The transport the approver authorised; null until the transfer is approved. */
  approved_vehicle: TransferVehicleReference | null;
  approved_driver: TransferDriverReference | null;
  assignment_substitution: TransferAssignmentSubstitution | null;
  compliance_override_reason?: string | null;
  status: TransferStatus;
  route_type: TransferRouteType;
  /** Whether it must be approved before dispatch, under the rules in force. */
  requires_approval: boolean;
  /** Goes up every time the transfer is sent to approval again. */
  approval_round: number;
  submitted_by_id: string | null;
  submitted_by_name: string | null;
  submitted_at: string | null;
  /** Whoever last edited the preparation; like the author, they cannot decide on it. */
  last_edited_by_id?: string | null;
  last_edited_by_name?: string | null;
  approved_by_id: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  rejected_by_id: string | null;
  rejected_by_name: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  notes: string | null;
  created_by_id: string;
  created_at: string;
  dispatched_by_id: string | null;
  dispatched_at: string | null;
  received_by_id: string | null;
  received_at: string | null;
  /** When it reached a final status (received, closed with adjustment or cancelled). */
  closed_at: string | null;
  dispatch_movement_id: string | null;
  /** A shortage or a surplus whose count at the origin warehouse is still missing. */
  origin_count_pending: boolean;
  has_open_discrepancies: boolean;
  discrepancies: TransferDiscrepancy[];
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
  /** The update is a full replace: always send the vehicle and driver that are saved. */
  vehicle_id: string | null;
  driver_id: string | null;
  notes: string | null;
  lines: TransferLineInput[];
}

export type TransferUpdateInput = TransferCreateInput;

/** One reception line: what arrived well, damaged and extra. Only what is declared is sent. */
export interface TransferReceiptLineInput {
  transfer_detail_id: string;
  destination_location_id: string;
  /** Received in good condition (zero when everything that arrived is damaged). */
  quantity_base: string;
  damaged_quantity?: string;
  damage_type?: DamageType | null;
  damage_notes?: string | null;
  /** Where the damaged goods are kept; the receiving location by default. */
  damaged_location_id?: string | null;
  surplus_quantity?: string;
  surplus_notes?: string | null;
  surplus_location_id?: string | null;
  evidence_reference?: string | null;
}

/** A surplus enters stock as an adjustment: packaging or measures, lot and an optional cost. */
export interface DiscrepancyAdjustmentInput {
  idempotency_key: string;
  operational_date: string;
  accounting_date: string;
  reason: string;
  document_reference: string;
  notes?: string | null;
  packaging_definition_id?: string | null;
  actual_gross_weight_kg?: string | null;
  actual_volume_m3?: string | null;
  inventory_lot_detail_id?: string | null;
  documented_unit_cost?: string | null;
  documented_total_cost?: string | null;
}

const root = '/inventory/transfers';

function discrepancyRoot(transferId: string, discrepancyId: string): string {
  return `${root}/${encodeURIComponent(transferId)}/discrepancies/${encodeURIComponent(discrepancyId)}`;
}

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

  /** Vehicles and drivers of the origin branch that can be chosen while preparing. */
  assignmentOptions: (originWarehouseId: string, transferId?: string | null) => {
    const query = new URLSearchParams({ origin_warehouse_id: originWarehouseId });
    if (transferId) query.set('transfer_id', transferId);
    return apiFetch<AssignmentOptions>(`${root}/assignment-options?${query.toString()}`);
  },

  /** Judges a transport chosen for a draft that may not be saved yet. */
  assignmentCheck: (body: AssignmentCheckInput) =>
    apiFetch<AssignmentCheck>(`${root}/assignment-check`, {
      method: 'POST',
      body: JSON.stringify({
        origin_warehouse_id: body.origin_warehouse_id,
        vehicle_id: body.vehicle_id,
        driver_id: body.driver_id || null,
        transfer_id: body.transfer_id || null,
        lines: body.lines ?? []
      })
    }),

  /** What the approver needs: is the transport saved in the transfer fit to be planned? */
  transferAssignmentCheck: (transferId: string) =>
    apiFetch<AssignmentCheck>(`${root}/${encodeURIComponent(transferId)}/assignment-check`),

  dispatchCheck: (transferId: string, vehicleId: string, driverId?: string | null) =>
    apiFetch<DispatchCheck>(`${root}/${encodeURIComponent(transferId)}/dispatch-check`, {
      method: 'POST',
      body: JSON.stringify({ vehicle_id: vehicleId, driver_id: driverId || null })
    }),

  list: (
    filters: {
      status?: TransferStatus;
      routeType?: TransferRouteType;
      /** Only transfers leaving from (origin) or arriving at (destination) the user's branches. */
      side?: 'origin' | 'destination';
      /** Only what the signed-in user can decide on now. */
      awaitingMyApproval?: boolean;
      /** Only transfers with a shortage or a surplus not yet counted at the origin warehouse. */
      originCountPending?: boolean;
      /** Only transfers with differences still to be resolved. */
      withOpenDiscrepancies?: boolean;
      page?: number;
      size?: number;
    } = {}
  ) => {
    const query = new URLSearchParams({
      page: String(filters.page ?? 1),
      size: String(filters.size ?? 50)
    });
    if (filters.status) query.set('status', filters.status);
    if (filters.routeType) query.set('route_type', filters.routeType);
    if (filters.side) query.set('side', filters.side);
    if (filters.awaitingMyApproval) query.set('awaiting_my_approval', 'true');
    if (filters.originCountPending) query.set('origin_count_pending', 'true');
    if (filters.withOpenDiscrepancies) query.set('with_open_discrepancies', 'true');
    return apiFetch<InventoryTransfer[]>(`${root}?${query.toString()}`);
  },

  settings: () => apiFetch<TransferPolicy>(`${root}/settings`),

  saveSettings: (body: TransferPolicyFlags) =>
    apiFetch<TransferPolicy>(`${root}/settings`, { method: 'PUT', body: JSON.stringify(body) }),

  /** Origins the user may ship from; with an origin, also where it can go. */
  routeOptions: (originWarehouseId?: string) => {
    const query = originWarehouseId
      ? `?${new URLSearchParams({ origin_warehouse_id: originWarehouseId }).toString()}`
      : '';
    return apiFetch<TransferRouteOptions>(`${root}/route-options${query}`);
  },

  /** How many transfers wait for the signed-in user's decision. */
  pendingApprovalCount: async () =>
    (await apiFetch<{ count: number }>(`${root}/pending-approval-count`)).count,

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

  submit: (transferId: string, idempotencyKey: string) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}/submit`, {
      method: 'POST',
      body: JSON.stringify({ idempotency_key: idempotencyKey })
    }),

  withdraw: (transferId: string, idempotencyKey: string) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}/withdraw`, {
      method: 'POST',
      body: JSON.stringify({ idempotency_key: idempotencyKey })
    }),

  /** `expectedRound` is the round the person saw; a newer one makes the server refuse. */
  approve: (transferId: string, idempotencyKey: string, expectedRound: number) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}/approve`, {
      method: 'POST',
      body: JSON.stringify({ idempotency_key: idempotencyKey, expected_round: expectedRound })
    }),

  reject: (transferId: string, idempotencyKey: string, expectedRound: number, reason: string) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}/reject`, {
      method: 'POST',
      body: JSON.stringify({
        idempotency_key: idempotencyKey,
        expected_round: expectedRound,
        reason
      })
    }),

  dispatch: (
    transferId: string,
    vehicleId: string,
    idempotencyKey: string,
    options: {
      driverId?: string | null;
      overrideReason?: string | null;
      substitutionCode?: SubstitutionCode | '' | null;
      substitutionReason?: string | null;
    } = {}
  ) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}/dispatch`, {
      method: 'POST',
      body: JSON.stringify({
        vehicle_id: vehicleId,
        idempotency_key: idempotencyKey,
        driver_id: options.driverId || null,
        override_reason: options.overrideReason?.trim() || null,
        substitution_code: options.substitutionCode || null,
        substitution_reason: options.substitutionReason?.trim() || null
      })
    }),

  receive: (
    transferId: string,
    idempotencyKey: string,
    lines: TransferReceiptLineInput[]
  ) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}/receive`, {
      method: 'POST',
      body: JSON.stringify({ idempotency_key: idempotencyKey, lines })
    }),

  /** Stop waiting for what has not arrived: it becomes a shortage to resolve. */
  closeReception: (
    transferId: string,
    body: { idempotency_key: string; reason: string; evidence_reference: string | null }
  ) =>
    apiFetch<InventoryTransfer>(`${root}/${encodeURIComponent(transferId)}/close-reception`, {
      method: 'POST',
      body: JSON.stringify(body)
    }),

  /** Prepares, as a draft, the adjustment that regularises a shortage, damage or surplus. */
  prepareDiscrepancyAdjustment: (
    transferId: string,
    discrepancyId: string,
    body: DiscrepancyAdjustmentInput
  ) =>
    apiFetch<InventoryAdjustment>(`${discrepancyRoot(transferId, discrepancyId)}/adjustment`, {
      method: 'POST',
      body: JSON.stringify(body)
    }),

  /** Damage only: the goods stay as damaged while the claim runs. */
  claimDiscrepancy: (
    transferId: string,
    discrepancyId: string,
    body: { idempotency_key: string; claim_reference: string }
  ) =>
    apiFetch<InventoryTransfer>(`${discrepancyRoot(transferId, discrepancyId)}/claim`, {
      method: 'POST',
      body: JSON.stringify(body)
    }),

  /** After inspection, the damaged goods go to quarantine. */
  releaseDamage: (
    transferId: string,
    discrepancyId: string,
    body: { idempotency_key: string; notes: string; destination_location_id?: string | null }
  ) =>
    apiFetch<InventoryTransfer>(`${discrepancyRoot(transferId, discrepancyId)}/release`, {
      method: 'POST',
      body: JSON.stringify({
        idempotency_key: body.idempotency_key,
        notes: body.notes,
        destination_location_id: body.destination_location_id || null
      })
    }),

  /** The missing goods turned up: the shortage is cancelled and the transfer waits for them. */
  markShortageFound: (
    transferId: string,
    discrepancyId: string,
    body: { idempotency_key: string; notes: string }
  ) =>
    apiFetch<InventoryTransfer>(`${discrepancyRoot(transferId, discrepancyId)}/found`, {
      method: 'POST',
      body: JSON.stringify(body)
    }),

  dismissSurplus: (
    transferId: string,
    discrepancyId: string,
    body: { idempotency_key: string; notes: string }
  ) =>
    apiFetch<InventoryTransfer>(`${discrepancyRoot(transferId, discrepancyId)}/dismiss`, {
      method: 'POST',
      body: JSON.stringify(body)
    }),

  /** The origin warehouse counted its stock after a shortage or a surplus. */
  recordOriginCount: (
    transferId: string,
    discrepancyId: string,
    body: { idempotency_key: string; notes: string }
  ) =>
    apiFetch<InventoryTransfer>(`${discrepancyRoot(transferId, discrepancyId)}/origin-count`, {
      method: 'POST',
      body: JSON.stringify(body)
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
