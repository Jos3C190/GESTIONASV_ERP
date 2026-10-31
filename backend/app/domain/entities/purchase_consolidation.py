"""Purchase-demand consolidations and their immutable source lineage."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from app.domain.entities.purchase_quotation import PurchaseQuotationStatus


class PurchaseConsolidationStatus(StrEnum):
    DRAFT = "draft"
    FROZEN = "frozen"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class BranchDemandLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class ConsolidationSource:
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
    reason: str | None = None
    demand_level: BranchDemandLevel | None = None


@dataclass(frozen=True, slots=True)
class ConsolidationLine:
    id: uuid.UUID
    product_id: int
    product_sku: str
    product_name: str
    unit_id: int
    unit_name: str
    central_quantity: Decimal
    central_reason: str | None
    sources: tuple[ConsolidationSource, ...]

    @property
    def branch_quantity(self) -> Decimal:
        return sum((source.included_quantity for source in self.sources), Decimal("0"))

    @property
    def total_quantity(self) -> Decimal:
        return self.branch_quantity + self.central_quantity


@dataclass(frozen=True, slots=True)
class PurchaseConsolidation:
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
    lines: tuple[ConsolidationLine, ...]
    events: tuple[ConsolidationEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class ConsolidationWorkItem:
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
    source_count: int = 0


@dataclass(frozen=True, slots=True)
class ConsolidationEvent:
    id: uuid.UUID
    actor_id: uuid.UUID
    action: str
    reason: str
    changes: dict[str, object]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PurchaseConsolidationAward:
    """An auditable allocation of part of a consolidated line to one supplier offer."""

    id: uuid.UUID
    company_id: uuid.UUID
    consolidation_id: uuid.UUID
    consolidation_line_id: uuid.UUID
    purchase_quotation_id: uuid.UUID
    purchase_quotation_detail_id: uuid.UUID
    supplier_id: int
    quantity: Decimal
    reason: str
    decided_by_id: uuid.UUID
    created_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by_id: uuid.UUID | None = None
    revocation_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.quantity.is_finite() or self.quantity <= 0:
            raise ValueError("La cantidad adjudicada debe ser mayor que cero.")
        if not self.reason.strip():
            raise ValueError("El motivo de adjudicación es obligatorio.")
        if self.revoked_at is None:
            if self.revoked_by_id is not None or self.revocation_reason is not None:
                raise ValueError("La reversión necesita fecha, usuario y motivo.")
        elif self.revoked_by_id is None or not (self.revocation_reason or "").strip():
            raise ValueError("La reversión necesita usuario y motivo.")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


@dataclass(frozen=True, slots=True)
class ConsolidationQuotationStatusChange:
    quotation_id: uuid.UUID
    expected_status: PurchaseQuotationStatus
    target_status: PurchaseQuotationStatus
