"""Pure domain model for supplier purchase quotations and RFQ coverage."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

ISO_CURRENCY_CODE_LENGTH = 3


class PurchaseQuotationStatus(StrEnum):
    DRAFT = "draft"
    REQUESTED = "requested"
    RECEIVED = "received"
    UNDER_EVALUATION = "under_evaluation"
    SELECTED = "selected"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


PURCHASE_QUOTATION_TRANSITIONS: dict[
    PurchaseQuotationStatus, frozenset[PurchaseQuotationStatus]
] = {
    PurchaseQuotationStatus.DRAFT: frozenset(
        {PurchaseQuotationStatus.REQUESTED, PurchaseQuotationStatus.CANCELLED}
    ),
    PurchaseQuotationStatus.REQUESTED: frozenset(
        {
            PurchaseQuotationStatus.RECEIVED,
            PurchaseQuotationStatus.EXPIRED,
            PurchaseQuotationStatus.CANCELLED,
        }
    ),
    PurchaseQuotationStatus.RECEIVED: frozenset(
        {
            PurchaseQuotationStatus.UNDER_EVALUATION,
            PurchaseQuotationStatus.SELECTED,
            PurchaseQuotationStatus.REJECTED,
            PurchaseQuotationStatus.EXPIRED,
        }
    ),
    PurchaseQuotationStatus.UNDER_EVALUATION: frozenset(
        {
            PurchaseQuotationStatus.SELECTED,
            PurchaseQuotationStatus.REJECTED,
            PurchaseQuotationStatus.EXPIRED,
        }
    ),
    PurchaseQuotationStatus.SELECTED: frozenset(),
    PurchaseQuotationStatus.REJECTED: frozenset(),
    PurchaseQuotationStatus.EXPIRED: frozenset(),
    PurchaseQuotationStatus.CANCELLED: frozenset(),
}


class PurchaseQuotationTransitionError(ValueError):
    """Raised when a purchase-quotation transition is not allowed."""

    def __init__(
        self,
        current: PurchaseQuotationStatus,
        target: PurchaseQuotationStatus,
    ) -> None:
        super().__init__(f"Transición de cotización no permitida: {current} -> {target}.")
        self.current = current
        self.target = target


def ensure_purchase_quotation_transition(
    current: PurchaseQuotationStatus,
    target: PurchaseQuotationStatus,
) -> None:
    if target not in PURCHASE_QUOTATION_TRANSITIONS[current]:
        raise PurchaseQuotationTransitionError(current, target)


def _ensure_positive(value: Decimal, label: str) -> None:
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{label} debe ser mayor que cero.")


def _ensure_nonnegative(value: Decimal, label: str) -> None:
    if not value.is_finite() or value < 0:
        raise ValueError(f"{label} no puede ser negativo.")


@dataclass(frozen=True, slots=True)
class ExpenseType:
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    is_active: bool = True
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("El nombre del tipo de gasto es obligatorio.")


@dataclass(frozen=True, slots=True)
class PurchaseQuotationRequestDetail:
    id: uuid.UUID
    purchase_quotation_request_id: uuid.UUID
    purchase_request_detail_id: uuid.UUID
    quantity: Decimal
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        _ensure_positive(self.quantity, "La cantidad solicitada para cotizar")


@dataclass(frozen=True, slots=True)
class PurchaseQuotationRequest:
    id: uuid.UUID
    purchase_quotation_id: uuid.UUID
    purchase_request_id: uuid.UUID
    details: tuple[PurchaseQuotationRequestDetail, ...]
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.details:
            raise ValueError("La vinculación con la solicitud debe contener al menos un detalle.")
        if any(detail.purchase_quotation_request_id != self.id for detail in self.details):
            raise ValueError("Todos los detalles deben pertenecer a la vinculación de cotización.")


@dataclass(frozen=True, slots=True)
class PurchaseQuotationDetail:
    id: uuid.UUID
    purchase_quotation_id: uuid.UUID
    product_id: int
    unit_id: int
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal = Decimal("0")
    subtotal: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    delivery_days: int | None = None
    available_quantity: Decimal | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        _ensure_positive(self.quantity, "La cantidad cotizada")
        _ensure_nonnegative(self.unit_price, "El precio unitario")
        _ensure_nonnegative(self.discount, "El descuento")
        _ensure_nonnegative(self.subtotal, "El subtotal")
        _ensure_nonnegative(self.tax_rate, "La tasa de impuesto")
        _ensure_nonnegative(self.tax_amount, "El impuesto")
        _ensure_nonnegative(self.total, "El total")
        if self.tax_rate > Decimal("100"):
            raise ValueError("La tasa de impuesto no puede superar 100%.")
        if self.discount > self.subtotal:
            raise ValueError("El descuento no puede superar el subtotal.")
        if self.delivery_days is not None and self.delivery_days < 0:
            raise ValueError("Los días de entrega no pueden ser negativos.")
        if self.available_quantity is not None:
            _ensure_nonnegative(self.available_quantity, "La cantidad disponible")
            if self.available_quantity > self.quantity:
                raise ValueError("La cantidad disponible no puede superar la cantidad cotizada.")


@dataclass(frozen=True, slots=True)
class PurchaseQuotationExpense:
    id: uuid.UUID
    purchase_quotation_id: uuid.UUID
    expense_type_id: uuid.UUID
    amount: Decimal
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        _ensure_positive(self.amount, "El monto del gasto")


def _ensure_status_has_supplier_details(
    status: PurchaseQuotationStatus,
    details: tuple[PurchaseQuotationDetail, ...],
) -> None:
    if (
        status
        in {
            PurchaseQuotationStatus.RECEIVED,
            PurchaseQuotationStatus.UNDER_EVALUATION,
            PurchaseQuotationStatus.SELECTED,
            PurchaseQuotationStatus.REJECTED,
        }
        and not details
    ):
        raise ValueError("Una cotización recibida o evaluada debe contener al menos un detalle.")


@dataclass(frozen=True, slots=True)
class PurchaseQuotation:
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    supplier_id: int
    quotation_date: datetime
    currency: str
    created_by_id: uuid.UUID
    request_links: tuple[PurchaseQuotationRequest, ...]
    details: tuple[PurchaseQuotationDetail, ...] = ()
    expenses: tuple[PurchaseQuotationExpense, ...] = ()
    valid_until: datetime | None = None
    payment_terms: str | None = None
    delivery_days: int | None = None
    subtotal: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    status: PurchaseQuotationStatus = PurchaseQuotationStatus.DRAFT
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("El código de la cotización es obligatorio.")
        if (
            len(self.currency) != ISO_CURRENCY_CODE_LENGTH
            or not self.currency.isalpha()
            or self.currency != self.currency.upper()
        ):
            raise ValueError("La moneda debe ser un código ISO de tres letras en mayúsculas.")
        if not self.request_links:
            raise ValueError("La cotización debe cubrir al menos una solicitud de compra.")
        if any(link.purchase_quotation_id != self.id for link in self.request_links):
            raise ValueError("Todas las solicitudes vinculadas deben pertenecer a la cotización.")
        if any(detail.purchase_quotation_id != self.id for detail in self.details):
            raise ValueError("Todos los detalles deben pertenecer a la cotización.")
        if any(expense.purchase_quotation_id != self.id for expense in self.expenses):
            raise ValueError("Todos los gastos deben pertenecer a la cotización.")
        if self.valid_until is not None and self.valid_until < self.quotation_date:
            raise ValueError("La vigencia de la cotización no puede terminar antes de su fecha.")
        if self.delivery_days is not None and self.delivery_days < 0:
            raise ValueError("Los días de entrega no pueden ser negativos.")
        _ensure_nonnegative(self.subtotal, "El subtotal")
        _ensure_nonnegative(self.discount, "El descuento")
        _ensure_nonnegative(self.tax, "El impuesto")
        _ensure_nonnegative(self.total, "El total")
        if self.discount > self.subtotal:
            raise ValueError("El descuento no puede superar el subtotal.")
        _ensure_status_has_supplier_details(self.status, self.details)
