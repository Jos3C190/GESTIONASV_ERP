"""Pure domain model for internal purchase requests.

The procurement workflow starts here and is intentionally independent from
FastAPI, SQLAlchemy and Pydantic. Quotation and purchase-order modules will
advance the later states; the purchase-request API owns only the transitions
that belong to this aggregate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class PurchaseRequestStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    PARTIALLY_QUOTED = "partially_quoted"
    QUOTED = "quoted"
    PARTIALLY_ORDERED = "partially_ordered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


PURCHASE_REQUEST_TRANSITIONS: dict[PurchaseRequestStatus, frozenset[PurchaseRequestStatus]] = {
    PurchaseRequestStatus.DRAFT: frozenset(
        {PurchaseRequestStatus.SUBMITTED, PurchaseRequestStatus.CANCELLED}
    ),
    PurchaseRequestStatus.SUBMITTED: frozenset(
        {
            PurchaseRequestStatus.APPROVED,
            PurchaseRequestStatus.REJECTED,
            PurchaseRequestStatus.CANCELLED,
        }
    ),
    PurchaseRequestStatus.APPROVED: frozenset(
        {
            PurchaseRequestStatus.PARTIALLY_QUOTED,
            PurchaseRequestStatus.QUOTED,
        }
    ),
    PurchaseRequestStatus.REJECTED: frozenset(),
    PurchaseRequestStatus.PARTIALLY_QUOTED: frozenset({PurchaseRequestStatus.QUOTED}),
    PurchaseRequestStatus.QUOTED: frozenset(
        {
            PurchaseRequestStatus.PARTIALLY_ORDERED,
            PurchaseRequestStatus.COMPLETED,
        }
    ),
    PurchaseRequestStatus.PARTIALLY_ORDERED: frozenset({PurchaseRequestStatus.COMPLETED}),
    PurchaseRequestStatus.COMPLETED: frozenset(),
    PurchaseRequestStatus.CANCELLED: frozenset(),
}


class PurchaseRequestTransitionError(ValueError):
    """Raised when a workflow transition is not allowed."""

    def __init__(
        self,
        current: PurchaseRequestStatus,
        target: PurchaseRequestStatus,
    ) -> None:
        super().__init__(f"Transición de solicitud de compra no permitida: {current} -> {target}.")
        self.current = current
        self.target = target


def ensure_purchase_request_transition(
    current: PurchaseRequestStatus,
    target: PurchaseRequestStatus,
) -> None:
    if target not in PURCHASE_REQUEST_TRANSITIONS[current]:
        raise PurchaseRequestTransitionError(current, target)


@dataclass(frozen=True, slots=True)
class PurchaseRequestDetail:
    id: uuid.UUID
    purchase_request_id: uuid.UUID
    product_id: int
    unit_id: int
    quantity: Decimal
    description: str | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise ValueError("El producto del detalle debe ser válido.")
        if self.unit_id <= 0:
            raise ValueError("La unidad del detalle debe ser válida.")
        if not self.quantity.is_finite() or self.quantity <= 0:
            raise ValueError("La cantidad solicitada debe ser mayor que cero.")


@dataclass(frozen=True, slots=True)
class PurchaseRequest:
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    requested_by_id: uuid.UUID
    request_date: datetime
    justification: str
    details: tuple[PurchaseRequestDetail, ...]
    status: PurchaseRequestStatus = PurchaseRequestStatus.DRAFT
    required_date: datetime | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("El código de la solicitud de compra es obligatorio.")
        if not self.justification.strip():
            raise ValueError("La justificación de la solicitud de compra es obligatoria.")
        if not self.details:
            raise ValueError("La solicitud de compra debe contener al menos un detalle.")
        if any(detail.purchase_request_id != self.id for detail in self.details):
            raise ValueError("Todos los detalles deben pertenecer a la solicitud de compra.")
