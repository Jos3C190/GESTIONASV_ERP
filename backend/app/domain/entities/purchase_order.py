"""Pure domain model for supplier purchase orders."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

ISO_CURRENCY_CODE_LENGTH = 3


class PurchaseOrderStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SENT = "sent"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"
    CLOSED = "closed"


PURCHASE_ORDER_TRANSITIONS: dict[PurchaseOrderStatus, frozenset[PurchaseOrderStatus]] = {
    PurchaseOrderStatus.DRAFT: frozenset(
        {
            PurchaseOrderStatus.PENDING_APPROVAL,
            PurchaseOrderStatus.CANCELLED,
        }
    ),
    PurchaseOrderStatus.PENDING_APPROVAL: frozenset(
        {
            PurchaseOrderStatus.APPROVED,
            PurchaseOrderStatus.CANCELLED,
        }
    ),
    PurchaseOrderStatus.APPROVED: frozenset(
        {
            PurchaseOrderStatus.SENT,
            PurchaseOrderStatus.CANCELLED,
        }
    ),
    PurchaseOrderStatus.SENT: frozenset(
        {PurchaseOrderStatus.PARTIALLY_RECEIVED, PurchaseOrderStatus.RECEIVED}
    ),
    PurchaseOrderStatus.PARTIALLY_RECEIVED: frozenset({PurchaseOrderStatus.RECEIVED}),
    PurchaseOrderStatus.RECEIVED: frozenset({PurchaseOrderStatus.CLOSED}),
    PurchaseOrderStatus.CANCELLED: frozenset(),
    PurchaseOrderStatus.CLOSED: frozenset(),
}


class PurchaseOrderTransitionError(ValueError):
    """Raised when a purchase-order transition is not allowed."""

    def __init__(self, current: PurchaseOrderStatus, target: PurchaseOrderStatus) -> None:
        super().__init__(f"Transición de orden de compra no permitida: {current} -> {target}.")
        self.current = current
        self.target = target


def ensure_purchase_order_transition(
    current: PurchaseOrderStatus,
    target: PurchaseOrderStatus,
) -> None:
    if target not in PURCHASE_ORDER_TRANSITIONS[current]:
        raise PurchaseOrderTransitionError(current, target)


def _ensure_positive(value: Decimal, label: str) -> None:
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{label} debe ser mayor que cero.")


def _ensure_nonnegative(value: Decimal, label: str) -> None:
    if not value.is_finite() or value < 0:
        raise ValueError(f"{label} no puede ser negativo.")


def _ensure_timezone_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} debe incluir zona horaria.")


@dataclass(frozen=True, slots=True)
class PurchaseOrderDetail:
    id: uuid.UUID
    purchase_order_id: uuid.UUID
    purchase_quotation_detail_id: uuid.UUID
    product_id: int
    quantity: Decimal
    unit_id: int
    unit_price: Decimal
    discount: Decimal = Decimal("0")
    subtotal: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise ValueError("El producto del detalle debe ser válido.")
        if self.unit_id <= 0:
            raise ValueError("La unidad del detalle debe ser válida.")
        _ensure_positive(self.quantity, "La cantidad ordenada")
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


@dataclass(frozen=True, slots=True)
class PurchaseOrderExpense:
    id: uuid.UUID
    purchase_order_id: uuid.UUID
    expense_type_id: uuid.UUID
    amount: Decimal
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        _ensure_positive(self.amount, "El monto del gasto")


@dataclass(frozen=True, slots=True)
class PurchaseOrder:
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    supplier_id: int
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    purchase_quotation_id: uuid.UUID
    created_by_id: uuid.UUID
    order_date: datetime
    currency: str
    details: tuple[PurchaseOrderDetail, ...]
    expenses: tuple[PurchaseOrderExpense, ...] = ()
    expected_date: datetime | None = None
    payment_terms: str | None = None
    subtotal: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    additional_expenses: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    status: PurchaseOrderStatus = PurchaseOrderStatus.DRAFT
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("El código de la orden de compra es obligatorio.")
        if self.supplier_id <= 0:
            raise ValueError("El proveedor de la orden de compra debe ser válido.")
        if (
            len(self.currency) != ISO_CURRENCY_CODE_LENGTH
            or not self.currency.isalpha()
            or self.currency != self.currency.upper()
        ):
            raise ValueError("La moneda debe ser un código ISO de tres letras en mayúsculas.")
        if not self.details:
            raise ValueError("La orden de compra debe contener al menos un detalle.")
        if any(detail.purchase_order_id != self.id for detail in self.details):
            raise ValueError("Todos los detalles deben pertenecer a la orden de compra.")
        if any(expense.purchase_order_id != self.id for expense in self.expenses):
            raise ValueError("Todos los gastos deben pertenecer a la orden de compra.")
        _ensure_timezone_aware(self.order_date, "La fecha de la orden")
        if self.expected_date is not None:
            _ensure_timezone_aware(self.expected_date, "La fecha esperada")
        if self.expected_date is not None and self.expected_date < self.order_date:
            raise ValueError("La fecha esperada no puede ser anterior a la fecha de la orden.")
        _ensure_nonnegative(self.subtotal, "El subtotal")
        _ensure_nonnegative(self.discount, "El descuento")
        _ensure_nonnegative(self.tax, "El impuesto")
        _ensure_nonnegative(self.additional_expenses, "Los gastos adicionales")
        _ensure_nonnegative(self.total, "El total")
        if self.discount > self.subtotal:
            raise ValueError("El descuento no puede superar el subtotal.")
