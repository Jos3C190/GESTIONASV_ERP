"""HTTP contracts for company-scoped inventory transfer documents."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from app.api.v1.schemas.common import ORMOut
from app.api.v1.schemas.inventory import StrictModel

TransferRouteType = Literal["central_distribution", "branch_to_branch", "branch_to_central"]
TransferStatusValue = Literal[
    "preparation",
    "pending_approval",
    "approved",
    "in_transit",
    "partially_received",
    "discrepancy",
    "received",
    "closed_with_adjustment",
    "incident",
    "cancelled",
]
DiscrepancyKindValue = Literal["shortage", "surplus", "damage"]
DiscrepancyStatusValue = Literal["open", "in_claim", "resolved", "cancelled"]
DiscrepancySourceValue = Literal["receipt", "reception_close", "incident"]
DiscrepancyResolutionValue = Literal["written_off", "found", "released", "regularized", "dismissed"]
DamageTypeValue = Literal[
    "broken",
    "crushed",
    "wet",
    "contaminated",
    "packaging",
    "tampered",
    "temperature",
    "other",
]
SubstitutionCodeValue = Literal[
    "vehicle_unfit",
    "vehicle_unavailable",
    "driver_unfit",
    "driver_unavailable",
    "load_change",
    "other",
]


class TransferDemandAllocationIn(StrictModel):
    purchase_request_detail_id: uuid.UUID
    allocated_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


class TransferLineIn(StrictModel):
    handling_unit_id: uuid.UUID
    quantity_base: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    inventory_lot_detail_id: uuid.UUID | None = None
    demand_allocations: list[TransferDemandAllocationIn] = Field(
        default_factory=list, max_length=100
    )
    excess_reason: str | None = Field(None, max_length=2000)
    notes: str | None = Field(None, max_length=2000)


class TransferCreateIn(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    origin_warehouse_id: uuid.UUID
    destination_warehouse_id: uuid.UUID
    vehicle_id: uuid.UUID | None = None
    #: Chosen at preparation; both are required to send the transfer for approval.
    driver_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=4000)
    lines: list[TransferLineIn] = Field(min_length=1, max_length=500)


class TransferUpdateIn(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    origin_warehouse_id: uuid.UUID
    destination_warehouse_id: uuid.UUID
    vehicle_id: uuid.UUID | None
    driver_id: uuid.UUID | None = None
    notes: str | None = Field(max_length=4000)
    lines: list[TransferLineIn] = Field(min_length=1, max_length=500)


class TransferCommandIn(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=120)


class TransferApproveIn(TransferCommandIn):
    #: The approval round the person saw; it changes every time the transfer is sent again.
    expected_round: int = Field(ge=1)


class TransferRejectIn(TransferApproveIn):
    reason: str = Field(min_length=5, max_length=1000)


class TransferPolicyIn(StrictModel):
    allow_branch_to_branch: bool
    allow_branch_to_central: bool
    require_approval: bool


class TransferPolicyFlagsOut(StrictModel):
    allow_branch_to_branch: bool
    allow_branch_to_central: bool
    require_approval: bool


class TransferPolicyOut(TransferPolicyFlagsOut):
    updated_at: datetime | None = None
    #: Transfers that a rule change would freeze.
    pending_count: int = 0
    approved_count: int = 0


class TransferWarehouseOptionOut(StrictModel):
    id: uuid.UUID
    code: str | None
    name: str
    branch_id: uuid.UUID
    branch_name: str
    is_central: bool


class TransferDestinationOptionOut(TransferWarehouseOptionOut):
    #: The route that would join this warehouse to the chosen origin.
    route_type: TransferRouteType


class TransferRouteOptionsOut(StrictModel):
    policy: TransferPolicyFlagsOut
    origins: list[TransferWarehouseOptionOut]
    destinations: list[TransferDestinationOptionOut] = Field(default_factory=list)


class PendingApprovalCountOut(StrictModel):
    count: int


class TransferDispatchIn(TransferCommandIn):
    vehicle_id: uuid.UUID
    #: Defaults to the driver assigned to the vehicle in Fleet.
    driver_id: uuid.UUID | None = None
    #: Required to dispatch despite expired documents or license class (audited).
    override_reason: str | None = Field(None, min_length=5, max_length=500)
    #: Required when the vehicle or the driver differs from the approved ones (audited).
    substitution_code: SubstitutionCodeValue | None = None
    substitution_reason: str | None = Field(None, max_length=500)


class DispatchCheckIn(StrictModel):
    vehicle_id: uuid.UUID
    driver_id: uuid.UUID | None = None


class AssignmentLineIn(StrictModel):
    handling_unit_id: uuid.UUID
    quantity_base: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


class AssignmentCheckIn(StrictModel):
    """A transport chosen while the transfer is still being prepared."""

    origin_warehouse_id: uuid.UUID
    vehicle_id: uuid.UUID
    driver_id: uuid.UUID | None = None
    #: The saved transfer being edited, if any (its own reservations do not count).
    transfer_id: uuid.UUID | None = None
    #: The lines of the draft; they give the weight. Without them, the saved transfer's.
    lines: list[AssignmentLineIn] = Field(default_factory=list, max_length=500)


class DispatchIssueOut(StrictModel):
    code: str
    severity: Literal["blocking", "warning"]
    message: str
    overridable: bool


class DispatchCheckOut(StrictModel):
    vehicle_id: uuid.UUID
    driver_id: uuid.UUID | None
    vehicle_issues: list[DispatchIssueOut]
    driver_issues: list[DispatchIssueOut]
    blocked: bool
    hard_blocked: bool
    can_override: bool


class DispatchVehicleOptionOut(StrictModel):
    inventory_vehicle_id: uuid.UUID
    fleet_vehicle_id: uuid.UUID
    code: str
    plate: str | None
    kind: str
    brand: str
    model: str
    compliance_state: Literal["ok", "warning", "blocked"]
    available: bool
    unavailable_reason: str | None
    #: Something to know that does not stop the choice (e.g. it is on the road now).
    note: str | None = None
    driver_id: uuid.UUID | None
    driver_name: str | None


class DispatchDriverOptionOut(StrictModel):
    id: uuid.UUID
    name: str
    license_class: str
    compliance_state: Literal["ok", "warning", "blocked"]
    current_vehicle_code: str | None


class DispatchOptionsOut(StrictModel):
    origin_branch_id: uuid.UUID
    origin_branch_name: str
    vehicles: list[DispatchVehicleOptionOut]
    drivers: list[DispatchDriverOptionOut]
    #: What was saved at preparation, and what the approver authorised.
    planned_vehicle_id: uuid.UUID | None = None
    planned_driver_id: uuid.UUID | None = None
    approved_vehicle_id: uuid.UUID | None = None
    approved_driver_id: uuid.UUID | None = None


class AssignmentOptionsOut(DispatchOptionsOut):
    """Vehicles and drivers of the origin branch that can be chosen while preparing."""


class PlanningConflictOut(StrictModel):
    transfer_id: uuid.UUID
    code: str
    status: str
    same_vehicle: bool
    same_driver: bool
    message: str


class AssignmentCheckOut(StrictModel):
    vehicle_id: uuid.UUID | None
    driver_id: uuid.UUID | None
    vehicle_issues: list[DispatchIssueOut]
    driver_issues: list[DispatchIssueOut]
    #: The transport cannot be planned at all (departure-time problems are only warnings).
    planning_blocked: bool
    warnings: int
    conflicts: list[PlanningConflictOut]
    load_kg: Decimal | None = None
    load_missing_weight: int = 0


class TransferReceiptLineIn(StrictModel):
    """One detail: what arrived well, what arrived damaged and what arrived extra."""

    transfer_detail_id: uuid.UUID
    destination_location_id: uuid.UUID
    #: Received in good condition (zero when everything that arrived is damaged).
    quantity_base: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    damaged_quantity: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=6)
    damage_type: DamageTypeValue | None = None
    damage_notes: str | None = Field(None, max_length=2000)
    #: Where the damaged goods are kept; the receiving location by default.
    damaged_location_id: uuid.UUID | None = None
    surplus_quantity: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=6)
    surplus_notes: str | None = Field(None, max_length=2000)
    surplus_location_id: uuid.UUID | None = None
    evidence_reference: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_condition_fields(self) -> TransferReceiptLineIn:
        if self.damaged_quantity == 0 and (
            self.damage_type or self.damage_notes or self.damaged_location_id
        ):
            raise ValueError("Los datos de avería requieren una cantidad con avería.")
        if self.surplus_quantity == 0 and (self.surplus_notes or self.surplus_location_id):
            raise ValueError("Los datos del sobrante requieren una cantidad sobrante.")
        return self


class TransferReceiveIn(TransferCommandIn):
    lines: list[TransferReceiptLineIn] = Field(min_length=1, max_length=500)


class TransferCloseReceptionIn(TransferCommandIn):
    reason: str = Field(min_length=5, max_length=4000)
    evidence_reference: str | None = Field(None, max_length=500)


class TransferDiscrepancyClaimIn(TransferCommandIn):
    claim_reference: str = Field(min_length=3, max_length=500)


class TransferDiscrepancyNotesIn(TransferCommandIn):
    notes: str = Field(min_length=5, max_length=4000)


class TransferDiscrepancyReleaseIn(TransferDiscrepancyNotesIn):
    #: Quarantine location for the released goods; the one they are in by default.
    destination_location_id: uuid.UUID | None = None


class TransferDiscrepancyAdjustmentIn(TransferCommandIn):
    operational_date: date
    accounting_date: date
    reason: str = Field(min_length=5, max_length=4000)
    document_reference: str = Field(min_length=1, max_length=240)
    notes: str | None = Field(None, max_length=4000)
    # Only a surplus, which enters stock, needs these:
    packaging_definition_id: uuid.UUID | None = None
    actual_gross_weight_kg: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)
    actual_volume_m3: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)
    inventory_lot_detail_id: uuid.UUID | None = None
    documented_unit_cost: Decimal | None = Field(None, ge=0, max_digits=24, decimal_places=6)
    documented_total_cost: Decimal | None = Field(None, ge=0, max_digits=24, decimal_places=6)


class TransferIncidentIn(TransferCommandIn):
    reason: str = Field(min_length=5, max_length=4000)
    evidence_reference: str | None = Field(None, max_length=500)


class TransferIncidentResolveIn(TransferCommandIn):
    resolution: Literal["resume_transit", "close_received"]
    resolution_notes: str = Field(min_length=5, max_length=4000)


class InventoryVehicleOut(ORMOut):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    name: str
    status: Literal["active", "inactive"]
    transit_warehouse_id: uuid.UUID
    transit_warehouse_name: str
    transit_location_id: uuid.UUID
    created_at: datetime
    fleet_vehicle_id: uuid.UUID | None = None
    plate: str | None = None
    kind: str | None = None
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None


class TransferVehicleReferenceOut(StrictModel):
    id: uuid.UUID
    code: str
    name: str
    status: str
    transit_warehouse_id: uuid.UUID | None = None
    fleet_vehicle_id: uuid.UUID | None = None
    plate: str | None = None


class TransferDriverReferenceOut(StrictModel):
    id: uuid.UUID
    name: str
    employee_code: str


class TransferDemandAllocationOut(StrictModel):
    purchase_request_detail_id: uuid.UUID
    request_id: uuid.UUID
    request_code: str
    branch_id: uuid.UUID
    branch_name: str
    quantity_requested: Decimal
    allocated_quantity: Decimal
    quantity_dispatched: Decimal
    quantity_received: Decimal
    quantity_adjusted_out: Decimal
    quantity_damaged: Decimal = Decimal("0")


class TransferReceiptOut(StrictModel):
    id: uuid.UUID
    movement_id: uuid.UUID
    handling_unit_id: uuid.UUID
    handling_unit_code: str | None
    quantity_received: Decimal
    condition: Literal["good", "damaged"] = "good"
    received_by_id: uuid.UUID
    received_at: datetime


class TransferLineOut(StrictModel):
    id: uuid.UUID
    line_number: int
    inventory_item_id: uuid.UUID
    product_id: int | None
    variant_id: uuid.UUID | None
    sku: str | None
    product_name: str
    base_unit_id: int | None
    base_unit_name: str | None
    base_unit_symbol: str | None
    presentation_name: str | None
    inventory_lot_detail_id: uuid.UUID | None
    inventory_lot_detail_code: str | None
    source_handling_unit_id: uuid.UUID
    source_handling_unit_code: str | None
    transit_handling_unit_id: uuid.UUID | None
    transit_handling_unit_code: str | None
    quantity_planned: Decimal
    quantity_dispatched: Decimal
    quantity_received: Decimal
    quantity_in_transit: Decimal
    quantity_returned: Decimal
    quantity_adjusted_out: Decimal
    #: Part of ``quantity_received`` that arrived damaged.
    quantity_received_damaged: Decimal = Decimal("0")
    quantity_surplus: Decimal = Decimal("0")
    #: Declared missing when the reception was closed, still to be resolved.
    quantity_short_open: Decimal = Decimal("0")
    #: What has not arrived yet and is still being waited for.
    quantity_pending_reception: Decimal = Decimal("0")
    excess_reason: str | None
    notes: str | None
    demand_allocations: list[TransferDemandAllocationOut]
    receipts: list[TransferReceiptOut]


class TransferIncidentOut(StrictModel):
    id: uuid.UUID
    status: Literal["open", "resolved"]
    reason: str
    evidence_reference: str | None
    opened_by_id: uuid.UUID
    opened_at: datetime
    resolution: str | None
    resolution_notes: str | None
    resolved_by_id: uuid.UUID | None
    resolved_at: datetime | None


class TransferAssignmentSubstitutionOut(StrictModel):
    code: SubstitutionCodeValue
    reason: str
    by_id: uuid.UUID
    by_name: str | None = None
    at: datetime


class TransferDiscrepancyAdjustmentRefOut(StrictModel):
    id: uuid.UUID
    code: str
    status: str


class TransferDiscrepancyOut(StrictModel):
    id: uuid.UUID
    transfer_detail_id: uuid.UUID
    line_number: int | None
    product_name: str
    sku: str | None
    base_unit_symbol: str | None
    kind: DiscrepancyKindValue
    status: DiscrepancyStatusValue
    source: DiscrepancySourceValue
    quantity: Decimal
    damage_type: DamageTypeValue | None
    notes: str
    evidence_reference: str | None
    location_id: uuid.UUID | None
    location_code: str | None
    handling_unit_id: uuid.UUID | None
    handling_unit_code: str | None
    receipt_id: uuid.UUID | None
    incident_id: uuid.UUID | None
    opened_by_id: uuid.UUID
    opened_by_name: str | None
    opened_at: datetime
    claim_reference: str | None
    claimed_by_id: uuid.UUID | None
    claimed_by_name: str | None
    claimed_at: datetime | None
    resolution: DiscrepancyResolutionValue | None
    resolution_notes: str | None
    resolved_by_id: uuid.UUID | None
    resolved_by_name: str | None
    resolved_at: datetime | None
    origin_count_required: bool
    origin_counted_by_id: uuid.UUID | None
    origin_counted_by_name: str | None
    origin_counted_at: datetime | None
    origin_count_notes: str | None
    adjustment: TransferDiscrepancyAdjustmentRefOut | None = None


class InventoryTransferOut(ORMOut):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    origin_warehouse_id: uuid.UUID
    origin_warehouse_name: str
    origin_branch_id: uuid.UUID | None
    origin_branch_name: str | None = None
    origin_is_central: bool = False
    destination_warehouse_id: uuid.UUID
    destination_warehouse_name: str
    destination_branch_id: uuid.UUID | None
    destination_branch_name: str | None = None
    destination_is_central: bool = False
    vehicle: TransferVehicleReferenceOut | None
    driver: TransferDriverReferenceOut | None = None
    #: The transport the approver authorised, and who replaced it at dispatch (if anyone).
    approved_vehicle: TransferVehicleReferenceOut | None = None
    approved_driver: TransferDriverReferenceOut | None = None
    assignment_substitution: TransferAssignmentSubstitutionOut | None = None
    compliance_override_reason: str | None = None
    status: TransferStatusValue
    route_type: TransferRouteType = "central_distribution"
    requires_approval: bool = False
    approval_round: int = 0
    submitted_by_id: uuid.UUID | None = None
    submitted_by_name: str | None = None
    submitted_at: datetime | None = None
    last_edited_by_id: uuid.UUID | None = None
    last_edited_by_name: str | None = None
    approved_by_id: uuid.UUID | None = None
    approved_by_name: str | None = None
    approved_at: datetime | None = None
    rejected_by_id: uuid.UUID | None = None
    rejected_by_name: str | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    notes: str | None
    created_by_id: uuid.UUID
    created_at: datetime
    dispatched_by_id: uuid.UUID | None
    dispatched_at: datetime | None
    received_by_id: uuid.UUID | None
    received_at: datetime | None
    closed_at: datetime | None = None
    dispatch_movement_id: uuid.UUID | None
    #: A shortage or a surplus whose origin count has not been recorded yet.
    origin_count_pending: bool = False
    has_open_discrepancies: bool = False
    discrepancies: list[TransferDiscrepancyOut] = Field(default_factory=list)
    lines: list[TransferLineOut]
    incidents: list[TransferIncidentOut]


class TransferDemandOut(StrictModel):
    purchase_request_detail_id: uuid.UUID
    purchase_request_id: uuid.UUID
    request_code: str
    request_status: str
    branch_id: uuid.UUID
    branch_name: str
    request_date: datetime
    required_date: datetime | None
    product_id: int
    inventory_item_id: uuid.UUID | None
    product_name: str
    sku: str | None
    unit_id: int
    unit_name: str
    unit_symbol: str | None
    quantity_requested: Decimal
    quantity_assigned: Decimal
    quantity_dispatched: Decimal
    quantity_in_transit: Decimal
    quantity_received: Decimal
    quantity_adjusted_out: Decimal
    quantity_pending: Decimal
