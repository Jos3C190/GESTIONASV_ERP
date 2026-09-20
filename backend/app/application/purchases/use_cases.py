"""Application use cases for supplier purchase receipts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.purchase import (
    Purchase,
    PurchaseDetail,
    PurchaseStatus,
    PurchaseTransitionError,
    ensure_purchase_transition,
)
from app.domain.entities.purchase_order import (
    PurchaseOrder,
    PurchaseOrderDetail,
    PurchaseOrderStatus,
)
from app.domain.ports.purchase_repository import (
    PurchaseOrderReceivingRepository,
    PurchaseRepository,
)

MONEY_QUANTUM = Decimal("0.000001")
RECEIVABLE_ORDER_STATUSES = frozenset(
    {PurchaseOrderStatus.SENT, PurchaseOrderStatus.PARTIALLY_RECEIVED}
)


@dataclass(frozen=True, slots=True)
class PurchaseLineDraft:
    purchase_order_detail_id: uuid.UUID
    quantity_received: Decimal


@dataclass(frozen=True, slots=True)
class PurchaseReceivableLine:
    purchase_order_detail_id: uuid.UUID
    product_id: int
    unit_id: int
    quantity_ordered: Decimal
    quantity_received: Decimal
    quantity_pending: Decimal
    unit_price: Decimal
    discount: Decimal
    tax_rate: Decimal
    notes: str | None = None


class PurchaseUseCases:
    def __init__(
        self,
        repository: PurchaseRepository,
        order_repository: PurchaseOrderReceivingRepository,
    ) -> None:
        self._repository = repository
        self._orders = order_repository

    async def list_purchases(
        self,
        company_id: uuid.UUID,
        *,
        status: PurchaseStatus | None = None,
        supplier_id: int | None = None,
        purchase_order_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Purchase], int]:
        return await self._repository.list_purchases(
            company_id,
            status=status,
            supplier_id=supplier_id,
            purchase_order_id=purchase_order_id,
            branch_id=branch_id,
            skip=skip,
            limit=limit,
        )

    async def get_purchase(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> Purchase:
        purchase = await self._repository.get_purchase(company_id, purchase_id)
        if purchase is None:
            raise NotFoundError("Compra no encontrada.", code="purchase_not_found")
        return purchase

    async def get_receivable_lines(
        self,
        company_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
    ) -> tuple[PurchaseReceivableLine, ...]:
        order = await self._get_order(company_id, purchase_order_id)
        self._ensure_order_receivable(order)
        received = await self._repository.get_received_quantities(company_id, order.id)
        return tuple(
            PurchaseReceivableLine(
                purchase_order_detail_id=detail.id,
                product_id=detail.product_id,
                unit_id=detail.unit_id,
                quantity_ordered=detail.quantity,
                quantity_received=min(received.get(detail.id, Decimal("0")), detail.quantity),
                quantity_pending=max(
                    detail.quantity - received.get(detail.id, Decimal("0")),
                    Decimal("0"),
                ),
                unit_price=detail.unit_price,
                discount=detail.discount,
                tax_rate=detail.tax_rate,
                notes=detail.notes,
            )
            for detail in order.details
        )

    async def create_draft(
        self,
        *,
        company_id: uuid.UUID,
        created_by_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        lines: tuple[PurchaseLineDraft, ...],
        supplier_invoice_number: str | None = None,
        supplier_invoice_date: date | None = None,
        notes: str | None = None,
    ) -> Purchase:
        order = await self._get_order_for_update(company_id, purchase_order_id)
        self._ensure_order_receivable(order)
        received = await self._repository.get_received_quantities(company_id, order.id)
        purchase_id = uuid.uuid4()
        details = self._build_details(purchase_id, order, lines, received)
        code = await self._repository.allocate_next_code(company_id)
        purchase = self._build_purchase(
            purchase_id=purchase_id,
            company_id=company_id,
            code=code,
            created_by_id=created_by_id,
            order=order,
            purchase_date=datetime.now(UTC),
            details=details,
            supplier_invoice_number=supplier_invoice_number,
            supplier_invoice_date=supplier_invoice_date,
            notes=notes,
        )
        return await self._repository.add_purchase(purchase)

    async def update_draft(
        self,
        *,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
        lines: tuple[PurchaseLineDraft, ...],
        supplier_invoice_number: str | None = None,
        supplier_invoice_date: date | None = None,
        notes: str | None = None,
    ) -> Purchase:
        current = await self._get_purchase_for_update(company_id, purchase_id)
        if current.status is not PurchaseStatus.DRAFT:
            raise BusinessRuleError(
                "Solo una compra en borrador puede modificarse.",
                code="purchase_not_editable",
            )
        order = await self._get_order_for_update(company_id, current.purchase_order_id)
        self._ensure_order_receivable(order)
        received = await self._repository.get_received_quantities(
            company_id,
            order.id,
            exclude_purchase_id=current.id,
        )
        details = self._build_details(current.id, order, lines, received)
        replacement = self._build_purchase(
            purchase_id=current.id,
            company_id=current.company_id,
            code=current.code,
            created_by_id=current.created_by_id,
            order=order,
            purchase_date=current.purchase_date,
            details=details,
            supplier_invoice_number=supplier_invoice_number,
            supplier_invoice_date=supplier_invoice_date,
            notes=notes,
            created_at=current.created_at,
        )
        saved = await self._repository.replace_draft(replacement)
        if saved is None:
            raise NotFoundError("Compra no encontrada.", code="purchase_not_found")
        return saved

    async def receive_purchase(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> Purchase:
        current = await self._get_purchase_for_update(company_id, purchase_id)
        if current.status is not PurchaseStatus.DRAFT:
            raise BusinessRuleError(
                "Solo una compra en borrador puede confirmarse como recibida.",
                code="purchase_not_receivable",
            )
        order = await self._get_order_for_update(company_id, current.purchase_order_id)
        self._ensure_order_receivable(order)
        previously_received = await self._repository.get_received_quantities(
            company_id,
            order.id,
            exclude_purchase_id=current.id,
        )
        self._ensure_details_within_pending(order, current.details, previously_received)

        received_after = dict(previously_received)
        for detail in current.details:
            received_after[detail.purchase_order_detail_id] = (
                received_after.get(detail.purchase_order_detail_id, Decimal("0"))
                + detail.quantity_received
            )
        target_order_status = self._receipt_order_status(order, received_after)

        saved = await self._transition_purchase(
            company_id,
            purchase_id,
            PurchaseStatus.RECEIVED,
            current=current,
        )
        if target_order_status is not order.status:
            updated_order = await self._orders.update_status(
                company_id,
                order.id,
                target_order_status,
            )
            if updated_order is None:
                raise RuntimeError("La orden de compra bloqueada desapareció durante la recepción.")
        return saved

    async def verify_purchase(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> Purchase:
        return await self._transition_purchase(
            company_id,
            purchase_id,
            PurchaseStatus.VERIFIED,
        )

    async def cancel_purchase(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> Purchase:
        return await self._transition_purchase(
            company_id,
            purchase_id,
            PurchaseStatus.CANCELLED,
        )

    async def close_purchase(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> Purchase:
        return await self._transition_purchase(
            company_id,
            purchase_id,
            PurchaseStatus.CLOSED,
        )

    async def _get_order(
        self,
        company_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
    ) -> PurchaseOrder:
        order = await self._orders.get_order(company_id, purchase_order_id)
        if order is None:
            raise NotFoundError(
                "Orden de compra no encontrada.",
                code="purchase_order_not_found",
            )
        return order

    async def _get_order_for_update(
        self,
        company_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
    ) -> PurchaseOrder:
        order = await self._orders.get_order_for_update(company_id, purchase_order_id)
        if order is None:
            raise NotFoundError(
                "Orden de compra no encontrada.",
                code="purchase_order_not_found",
            )
        return order

    async def _get_purchase_for_update(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> Purchase:
        purchase = await self._repository.get_purchase_for_update(company_id, purchase_id)
        if purchase is None:
            raise NotFoundError("Compra no encontrada.", code="purchase_not_found")
        return purchase

    @staticmethod
    def _ensure_order_receivable(order: PurchaseOrder) -> None:
        if order.status not in RECEIVABLE_ORDER_STATUSES:
            raise BusinessRuleError(
                "La orden de compra debe estar enviada o parcialmente recibida.",
                code="purchase_order_not_receivable",
            )

    def _build_details(
        self,
        purchase_id: uuid.UUID,
        order: PurchaseOrder,
        lines: tuple[PurchaseLineDraft, ...],
        received: dict[uuid.UUID, Decimal],
    ) -> tuple[PurchaseDetail, ...]:
        if not lines:
            raise ValidationError(
                "La compra debe incluir al menos un detalle recibido.",
                code="purchase_details_required",
            )
        detail_ids = [line.purchase_order_detail_id for line in lines]
        if len(detail_ids) != len(set(detail_ids)):
            raise ValidationError(
                "Un detalle de orden no puede repetirse en la compra.",
                code="purchase_duplicate_order_detail",
            )
        sources = {detail.id: detail for detail in order.details}
        details: list[PurchaseDetail] = []
        for line in lines:
            source = sources.get(line.purchase_order_detail_id)
            if source is None:
                raise ValidationError(
                    "El detalle indicado no pertenece a la orden de compra.",
                    code="purchase_order_detail_invalid",
                )
            pending = source.quantity - received.get(source.id, Decimal("0"))
            if not line.quantity_received.is_finite() or line.quantity_received <= 0:
                raise ValidationError(
                    "La cantidad recibida debe ser mayor que cero.",
                    code="purchase_quantity_invalid",
                )
            if line.quantity_received > pending:
                raise BusinessRuleError(
                    "La cantidad recibida supera la cantidad pendiente de la orden.",
                    code="purchase_quantity_exceeded",
                )
            details.append(
                self._build_detail(
                    purchase_id,
                    source,
                    line.quantity_received,
                )
            )
        return tuple(details)

    def _build_detail(
        self,
        purchase_id: uuid.UUID,
        source: PurchaseOrderDetail,
        quantity_received: Decimal,
    ) -> PurchaseDetail:
        subtotal = self._money(quantity_received * source.unit_price)
        discount = Decimal("0")
        if source.subtotal > 0 and source.discount > 0:
            discount = self._money(subtotal * source.discount / source.subtotal)
        taxable = subtotal - discount
        tax_amount = self._money(taxable * source.tax_rate / Decimal("100"))
        total = self._money(taxable + tax_amount)
        try:
            return PurchaseDetail(
                id=uuid.uuid4(),
                purchase_id=purchase_id,
                purchase_order_detail_id=source.id,
                product_id=source.product_id,
                quantity_ordered=source.quantity,
                quantity_received=quantity_received,
                unit_id=source.unit_id,
                unit_price=source.unit_price,
                discount=discount,
                subtotal=subtotal,
                tax_rate=source.tax_rate,
                tax_amount=tax_amount,
                total=total,
                notes=source.notes,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), code="purchase_detail_invalid") from exc

    def _build_purchase(
        self,
        *,
        purchase_id: uuid.UUID,
        company_id: uuid.UUID,
        code: str,
        created_by_id: uuid.UUID,
        order: PurchaseOrder,
        purchase_date: datetime,
        details: tuple[PurchaseDetail, ...],
        supplier_invoice_number: str | None,
        supplier_invoice_date: date | None,
        notes: str | None,
        created_at: datetime | None = None,
    ) -> Purchase:
        subtotal = self._money(sum((detail.subtotal for detail in details), Decimal("0")))
        discount = self._money(sum((detail.discount for detail in details), Decimal("0")))
        tax = self._money(sum((detail.tax_amount for detail in details), Decimal("0")))
        total = self._money(sum((detail.total for detail in details), Decimal("0")))
        try:
            return Purchase(
                id=purchase_id,
                company_id=company_id,
                code=code,
                purchase_order_id=order.id,
                supplier_id=order.supplier_id,
                branch_id=order.branch_id,
                warehouse_id=order.warehouse_id,
                created_by_id=created_by_id,
                purchase_date=purchase_date,
                supplier_invoice_number=supplier_invoice_number,
                supplier_invoice_date=supplier_invoice_date,
                currency=order.currency,
                details=details,
                subtotal=subtotal,
                discount=discount,
                tax=tax,
                total=total,
                status=PurchaseStatus.DRAFT,
                notes=notes,
                created_at=created_at,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), code="purchase_invalid") from exc

    def _ensure_details_within_pending(
        self,
        order: PurchaseOrder,
        details: tuple[PurchaseDetail, ...],
        received: dict[uuid.UUID, Decimal],
    ) -> None:
        sources = {detail.id: detail for detail in order.details}
        for detail in details:
            source = sources.get(detail.purchase_order_detail_id)
            if source is None:
                raise ValidationError(
                    "El detalle recibido ya no pertenece a la orden de compra.",
                    code="purchase_order_detail_invalid",
                )
            pending = source.quantity - received.get(source.id, Decimal("0"))
            if detail.quantity_received > pending:
                raise BusinessRuleError(
                    "La cantidad recibida supera la cantidad pendiente de la orden.",
                    code="purchase_quantity_exceeded",
                )

    @staticmethod
    def _receipt_order_status(
        order: PurchaseOrder,
        received: dict[uuid.UUID, Decimal],
    ) -> PurchaseOrderStatus:
        fully_received = all(
            received.get(detail.id, Decimal("0")) >= detail.quantity for detail in order.details
        )
        if fully_received:
            return PurchaseOrderStatus.RECEIVED
        return PurchaseOrderStatus.PARTIALLY_RECEIVED

    async def _transition_purchase(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
        target: PurchaseStatus,
        *,
        current: Purchase | None = None,
    ) -> Purchase:
        item = current or await self._get_purchase_for_update(company_id, purchase_id)
        try:
            ensure_purchase_transition(item.status, target)
        except PurchaseTransitionError as exc:
            raise BusinessRuleError(str(exc), code="purchase_invalid_transition") from exc
        saved = await self._repository.update_status(company_id, purchase_id, target)
        if saved is None:
            raise NotFoundError("Compra no encontrada.", code="purchase_not_found")
        return saved

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
