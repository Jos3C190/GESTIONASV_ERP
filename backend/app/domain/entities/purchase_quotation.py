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
    NOT_SELECTED = "not_selected"
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
            PurchaseQuotationStatus.NOT_SELECTED,
            PurchaseQuotationStatus.EXPIRED,
            PurchaseQuotationStatus.CANCELLED,
        }
    ),
    PurchaseQuotationStatus.RECEIVED: frozenset(
        {
            PurchaseQuotationStatus.UNDER_EVALUATION,
            PurchaseQuotationStatus.SELECTED,
            PurchaseQuotationStatus.NOT_SELECTED,
            PurchaseQuotationStatus.REJECTED,
            PurchaseQuotationStatus.EXPIRED,
        }
    ),
    PurchaseQuotationStatus.UNDER_EVALUATION: frozenset(
        {
            PurchaseQuotationStatus.SELECTED,
            PurchaseQuotationStatus.NOT_SELECTED,
            PurchaseQuotationStatus.REJECTED,
            PurchaseQuotationStatus.EXPIRED,
        }
    ),
    PurchaseQuotationStatus.SELECTED: frozenset(),
    PurchaseQuotationStatus.NOT_SELECTED: frozenset(),
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
    purchase_quotation_detail_id: uuid.UUID | None = None
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
    offered_quantity: Decimal | None = None
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
            maximum_available = (
                self.offered_quantity if self.offered_quantity is not None else self.quantity
            )
            if self.available_quantity > maximum_available:
                raise ValueError("La cantidad disponible no puede superar la cantidad ofrecida.")
        if self.offered_quantity is not None:
            _ensure_nonnegative(self.offered_quantity, "La cantidad ofrecida")
            if self.offered_quantity > self.quantity:
                raise ValueError("La cantidad ofrecida no puede superar la cantidad solicitada.")


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


@dataclass(frozen=True, slots=True)
class PurchaseQuotationSourceSnapshot:
    """Immutable source context copied from a demand consolidation."""

    purchase_request_id: uuid.UUID
    purchase_request_detail_id: uuid.UUID
    request_code: str
    branch_name: str | None
    warehouse_name: str | None
    requester_name: str | None
    required_date: datetime | None
    included_quantity: Decimal

    def __post_init__(self) -> None:
        _ensure_positive(self.included_quantity, "La cantidad de origen incluida")


@dataclass(frozen=True, slots=True)
class PurchaseQuotationLineSnapshot:
    """The exact product labels and demand composition copied into an RFQ version."""

    purchase_quotation_detail_id: uuid.UUID
    consolidation_line_id: uuid.UUID
    product_sku: str
    product_name: str
    unit_name: str
    branch_quantity: Decimal
    central_quantity: Decimal
    sources: tuple[PurchaseQuotationSourceSnapshot, ...]

    def __post_init__(self) -> None:
        if not self.product_sku.strip() or not self.product_name.strip() or not self.unit_name.strip():
            raise ValueError("La copia de RFQ debe conservar SKU, producto y unidad.")
        _ensure_nonnegative(self.branch_quantity, "La demanda de sucursales")
        _ensure_nonnegative(self.central_quantity, "La demanda central")
        if (
            sum((source.included_quantity for source in self.sources), Decimal("0"))
            != self.branch_quantity
        ):
            raise ValueError("Las fuentes copiadas no coinciden con la cantidad de sucursales.")


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
            PurchaseQuotationStatus.NOT_SELECTED,
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
    consolidation_id: uuid.UUID | None = None
    consolidation_code: str | None = None
    version_number: int = 1
    sent_at: datetime | None = None
    response_notes: str | None = None
    snapshots: tuple[PurchaseQuotationLineSnapshot, ...] = ()

    def __post_init__(self) -> None:
        self._ensure_identity_fields()
        self._ensure_snapshot_consistency()
        self._ensure_child_ownership()
        self._ensure_financial_terms()
        _ensure_status_has_supplier_details(self.status, self.details)

    def _ensure_identity_fields(self) -> None:
        if not self.code.strip():
            raise ValueError("El código de la cotización es obligatorio.")
        if (
            len(self.currency) != ISO_CURRENCY_CODE_LENGTH
            or not self.currency.isalpha()
            or self.currency != self.currency.upper()
        ):
            raise ValueError("La moneda debe ser un código ISO de tres letras en mayúsculas.")
        if not self.request_links and self.consolidation_id is None:
            raise ValueError("La cotización debe cubrir al menos una solicitud de compra.")
        if self.version_number < 1:
            raise ValueError("La versión de RFQ debe ser mayor que cero.")

    def _ensure_snapshot_consistency(self) -> None:
        if self.consolidation_id is None:
            if self.consolidation_code is not None or self.snapshots:
                raise ValueError("La copia de demanda requiere un consolidado de origen.")
        else:
            if not self.consolidation_code or not self.consolidation_code.strip():
                raise ValueError("La RFQ de un consolidado debe conservar su código de origen.")
            if not self.details or len(self.snapshots) != len(self.details):
                raise ValueError("La copia de RFQ debe conservar todas las líneas enviadas.")
            snapshot_ids = {snapshot.purchase_quotation_detail_id for snapshot in self.snapshots}
            detail_ids = {detail.id for detail in self.details}
            if snapshot_ids != detail_ids:
                raise ValueError("Las líneas copiadas no coinciden con las líneas de la RFQ.")
            detail_by_id = {detail.id: detail for detail in self.details}
            for snapshot in self.snapshots:
                detail = detail_by_id[snapshot.purchase_quotation_detail_id]
                if snapshot.branch_quantity + snapshot.central_quantity != detail.quantity:
                    raise ValueError("La cantidad enviada no coincide con la demanda copiada.")

    def _ensure_child_ownership(self) -> None:
        if any(link.purchase_quotation_id != self.id for link in self.request_links):
            raise ValueError("Todas las solicitudes vinculadas deben pertenecer a la cotización.")
        if any(detail.purchase_quotation_id != self.id for detail in self.details):
            raise ValueError("Todos los detalles deben pertenecer a la cotización.")
        if any(expense.purchase_quotation_id != self.id for expense in self.expenses):
            raise ValueError("Todos los gastos deben pertenecer a la cotización.")

    def _ensure_financial_terms(self) -> None:
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
