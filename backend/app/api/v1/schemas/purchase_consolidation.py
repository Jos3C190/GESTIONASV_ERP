"""HTTP schemas for purchase consolidation and demand work items."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.common import ORMOut
from app.domain.entities.purchase_consolidation import (
    BranchDemandLevel,
    PurchaseConsolidationStatus,
)
from app.domain.entities.purchase_quotation import PurchaseQuotationStatus


class PurchaseWorkItemResponse(ORMOut):
    id: uuid.UUID
    code: str
    item_type: str
    status: str
    request_date: datetime
    requester_name: str | None
    required_date: datetime | None
    branch_id: uuid.UUID | None
    branch_name: str | None
    warehouse_id: uuid.UUID | None
    warehouse_name: str | None
    line_count: int
    source_count: int


class ApprovedRequestCandidateDetail(ORMOut):
    id: uuid.UUID
    product_id: int
    product_sku: str
    product_name: str
    unit_id: int
    unit_name: str
    quantity: Decimal
    request_count: int


class ApprovedRequestCandidate(ORMOut):
    id: uuid.UUID
    code: str
    request_date: datetime
    requester_name: str | None
    required_date: datetime | None
    branch_id: uuid.UUID
    branch_name: str | None
    warehouse_id: uuid.UUID
    warehouse_name: str | None
    line_count: int
    details: list[ApprovedRequestCandidateDetail]


class SelectedRequestConsolidationReference(BaseModel):
    id: uuid.UUID
    code: str
    status: PurchaseConsolidationStatus


class SelectedPurchaseRequestResolution(BaseModel):
    id: uuid.UUID
    code: str
    eligibility: Literal["eligible", "already_consolidated", "not_eligible", "unavailable"]
    consolidations: tuple[SelectedRequestConsolidationReference, ...] = ()


class BranchDemandLevelAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: uuid.UUID
    product_id: int = Field(gt=0)
    level: BranchDemandLevel


class PurchaseConsolidationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_ids: tuple[uuid.UUID, ...] = Field(min_length=1, max_length=100)
    demand_levels: tuple[BranchDemandLevelAssignment, ...] = Field(default=(), max_length=1000)
    period_start: date
    period_end: date
    central_warehouse_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=4000)


class PurchaseConsolidationSourceChange(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_id: uuid.UUID
    included_quantity: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    reason: str = Field(default="", max_length=2000)
    demand_level: BranchDemandLevel | None = None


class CentralDemandChange(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: int = Field(gt=0)
    line_id: uuid.UUID | None = None
    quantity: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    reason: str = Field(min_length=1, max_length=2000)


class PurchaseConsolidationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    change_reason: str = Field(min_length=1, max_length=2000)
    source_changes: tuple[PurchaseConsolidationSourceChange, ...] = Field(default=(), max_length=500)
    central_demands: tuple[CentralDemandChange, ...] = Field(default=(), max_length=100)
    notes: str | None = Field(default=None, max_length=4000)
    central_warehouse_id: uuid.UUID | None = None


class PurchaseConsolidationAddRequests(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_ids: tuple[uuid.UUID, ...] = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=2000)


class PurchaseConsolidationCancel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=2000)


class PurchaseConsolidationClose(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=2000)
    covered_outside_consolidation: bool = False


class ConsolidationSourceResponse(ORMOut):
    id: uuid.UUID
    purchase_request_id: uuid.UUID
    purchase_request_detail_id: uuid.UUID
    request_code: str
    branch_id: uuid.UUID
    branch_name: str | None
    warehouse_id: uuid.UUID
    warehouse_name: str | None
    requester_name: str | None
    required_date: datetime | None
    requested_quantity: Decimal
    included_quantity: Decimal
    reason: str | None
    demand_level: BranchDemandLevel | None = None


class ConsolidationLineResponse(ORMOut):
    id: uuid.UUID
    product_id: int
    product_sku: str
    product_name: str
    unit_id: int
    unit_name: str
    branch_quantity: Decimal
    central_quantity: Decimal
    central_reason: str | None
    total_quantity: Decimal
    sources: tuple[ConsolidationSourceResponse, ...]


class ConsolidationEventResponse(ORMOut):
    id: uuid.UUID
    actor_id: uuid.UUID
    action: str
    reason: str
    changes: dict[str, object]
    created_at: datetime


class ProductStockSnapshotResponse(ORMOut):
    product_id: int
    inventory_item_id: uuid.UUID | None
    base_unit_id: int | None
    base_unit_name: str | None
    is_active: bool | None
    available_quantity: Decimal
    in_transit_quantity: Decimal
    quarantine_quantity: Decimal
    blocked_quantity: Decimal
    damaged_quantity: Decimal


class PurchaseConsolidationInventorySnapshotResponse(ORMOut):
    warehouse_id: uuid.UUID
    checked_at: datetime
    reservation_data_available: bool = False
    items: tuple[ProductStockSnapshotResponse, ...]


class PurchaseConsolidationAwardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    consolidation_line_id: uuid.UUID
    quotation_id: uuid.UUID
    quotation_detail_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    reason: str = Field(min_length=1, max_length=2000)


class PurchaseConsolidationAwardRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=2000)


class PurchaseConsolidationAwardOfferResponse(ORMOut):
    quotation_id: uuid.UUID
    quotation_code: str
    quotation_version: int
    supplier_id: int
    quotation_status: PurchaseQuotationStatus
    currency: str
    valid_until: datetime | None
    delivery_days: int | None
    payment_terms: str | None
    quotation_total: Decimal
    quotation_expenses_total: Decimal
    quotation_detail_id: uuid.UUID
    requested_quantity: Decimal
    offered_quantity: Decimal | None
    available_quantity: Decimal | None
    awarded_quantity: Decimal
    remaining_offer_quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    line_total: Decimal
    line_delivery_days: int | None
    notes: str | None
    can_award: bool
    blocked_reason: str | None


class PurchaseConsolidationAwardDecisionResponse(ORMOut):
    id: uuid.UUID
    quotation_id: uuid.UUID
    quotation_code: str
    supplier_id: int
    quantity: Decimal
    reason: str
    decided_by_id: uuid.UUID
    created_at: datetime | None
    revoked_at: datetime | None
    revoked_by_id: uuid.UUID | None
    revocation_reason: str | None
    ordered_quantity: Decimal
    remaining_to_order_quantity: Decimal


class PurchaseConsolidationAwardLineResponse(ORMOut):
    id: uuid.UUID
    product_id: int
    product_sku: str
    product_name: str
    unit_id: int
    unit_name: str
    demand_quantity: Decimal
    awarded_quantity: Decimal
    remaining_quantity: Decimal
    offers: tuple[PurchaseConsolidationAwardOfferResponse, ...]
    decisions: tuple[PurchaseConsolidationAwardDecisionResponse, ...]


class PurchaseConsolidationAwardBoardResponse(ORMOut):
    consolidation_id: uuid.UUID
    consolidation_code: str
    lines: tuple[PurchaseConsolidationAwardLineResponse, ...]
    currencies: tuple[str, ...]


class PurchaseConsolidationResponse(ORMOut):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    period_start: date
    period_end: date
    status: PurchaseConsolidationStatus
    created_by_id: uuid.UUID
    created_at: datetime | None
    updated_at: datetime | None
    central_warehouse_id: uuid.UUID | None
    central_warehouse_name: str | None
    notes: str | None
    lines: tuple[ConsolidationLineResponse, ...]
    events: tuple[ConsolidationEventResponse, ...]


__all__ = [
    "ApprovedRequestCandidate",
    "PurchaseConsolidationAddRequests",
    "PurchaseConsolidationAwardBoardResponse",
    "PurchaseConsolidationAwardCreate",
    "PurchaseConsolidationAwardDecisionResponse",
    "PurchaseConsolidationAwardLineResponse",
    "PurchaseConsolidationAwardOfferResponse",
    "PurchaseConsolidationAwardRevoke",
    "PurchaseConsolidationCancel",
    "PurchaseConsolidationClose",
    "PurchaseConsolidationCreate",
    "PurchaseConsolidationInventorySnapshotResponse",
    "PurchaseConsolidationResponse",
    "PurchaseConsolidationUpdate",
    "PurchaseWorkItemResponse",
]
