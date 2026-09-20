"""Pure domain model for supplier purchase receipts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

ISO_CURRENCY_CODE_LENGTH = 3


class PurchaseStatus(StrEnum):
    """Lifecycle for a supplier receipt."""

    DRAFT = "draft"
    RECEIVED = "received"
    VERIFIED = "verified"
    CANCELLED = "cancelled"
    CLOSED = "closed"


PURCHASE_TRANSITIONS: dict[PurchaseStatus, frozenset[PurchaseStatus]] = {
    PurchaseStatus.DRAFT: frozenset({PurchaseStatus.RECEIVED, PurchaseStatus.CANCELLED}),
    PurchaseStatus.RECEIVED: frozenset({PurchaseStatus.VERIFIED}),
    PurchaseStatus.VERIFIED: frozenset({PurchaseStatus.CLOSED}),
    PurchaseStatus.CANCELLED: frozenset(),
    PurchaseStatus.CLOSED: frozenset(),
}


class PurchaseTransitionError(ValueError):
    """Raised when a purchase transition is not allowed."""

    def __init__(self, current: PurchaseStatus, target: PurchaseStatus) -> None:
        super().__init__(f"Transición de compra no permitida: {current} -> {target}.")
        self.current = current
        self.target = target


def ensure_purchase_transition(current: PurchaseStatus, target: PurchaseStatus) -> None:
    if target not in PURCHASE_TRANSITIONS[current]:
        raise PurchaseTransitionError(current, target)


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
class PurchaseDetail:
    id: uuid.UUID
    purchase_id: uuid.UUID
    purchase_order_detail_id: uuid.UUID
    product_id: int
    quantity_ordered: Decimal
    quantity_received: Decimal
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
        _ensure_positive(self.quantity_ordered, "La cantidad ordenada")
        _ensure_positive(self.quantity_received, "La cantidad recibida")
        if self.quantity_received > self.quantity_ordered:
            raise ValueError("La cantidad recibida no puede superar la cantidad ordenada.")
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
class Purchase:
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    purchase_order_id: uuid.UUID
    supplier_id: int
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    created_by_id: uuid.UUID
    purchase_date: datetime
    currency: str
    details: tuple[PurchaseDetail, ...]
    supplier_invoice_number: str | None = None
    supplier_invoice_date: date | None = None
    subtotal: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    status: PurchaseStatus = PurchaseStatus.DRAFT
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("El código de la compra es obligatorio.")
        if self.supplier_id <= 0:
            raise ValueError("El proveedor de la compra debe ser válido.")
        if (
            len(self.currency) != ISO_CURRENCY_CODE_LENGTH
            or not self.currency.isalpha()
            or self.currency != self.currency.upper()
        ):
            raise ValueError("La moneda debe ser un código ISO de tres letras en mayúsculas.")
        if not self.details:
            raise ValueError("La compra debe contener al menos un detalle.")
        if any(detail.purchase_id != self.id for detail in self.details):
            raise ValueError("Todos los detalles deben pertenecer a la compra.")
        _ensure_timezone_aware(self.purchase_date, "La fecha de compra")
        _ensure_nonnegative(self.subtotal, "El subtotal")
        _ensure_nonnegative(self.discount, "El descuento")
        _ensure_nonnegative(self.tax, "El impuesto")
        _ensure_nonnegative(self.total, "El total")
        if self.discount > self.subtotal:
            raise ValueError("El descuento no puede superar el subtotal.")
