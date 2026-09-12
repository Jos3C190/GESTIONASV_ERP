"""Application use cases for purchase orders generated from selected quotations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.purchase_order import (
    PurchaseOrder,
    PurchaseOrderDetail,
    PurchaseOrderExpense,
    PurchaseOrderStatus,
    PurchaseOrderTransitionError,
    ensure_purchase_order_transition,
)
from app.domain.entities.purchase_quotation import PurchaseQuotationStatus
from app.domain.ports.purchase_order_repository import (
    PurchaseOrderDestinationReference,
    PurchaseOrderQuotationDetailReference,
    PurchaseOrderQuotationReference,
    PurchaseOrderRepository,
)

MONEY_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class PurchaseOrderLineDraft:
    purchase_quotation_detail_id: uuid.UUID
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class PurchaseOrderExpenseDraft:
    expense_type_id: uuid.UUID
    amount: Decimal
    description: str | None = None


class PurchaseOrderUseCases:
    def __init__(self, repository: PurchaseOrderRepository) -> None:
        self._repository = repository

    async def list_orders(
        self,
        company_id: uuid.UUID,
        *,
        status: PurchaseOrderStatus | None = None,
        supplier_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseOrder], int]:
        return await self._repository.list_orders(
            company_id,
            status=status,
            supplier_id=supplier_id,
            skip=skip,
            limit=limit,
        )

    async def get_order(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> PurchaseOrder:
        order = await self._repository.get_order(company_id, order_id)
        if order is None:
            raise NotFoundError(
                "Orden de compra no encontrada.",
                code="purchase_order_not_found",
            )
        return order

    async def create_draft(
        self,
        *,
        company_id: uuid.UUID,
        created_by_id: uuid.UUID,
        purchase_quotation_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        lines: tuple[PurchaseOrderLineDraft, ...],
        expected_date: datetime | None = None,
        expenses: tuple[PurchaseOrderExpenseDraft, ...] = (),
        notes: str | None = None,
    ) -> PurchaseOrder:
        quotation = await self._get_selected_quotation_for_update(
            company_id,
            purchase_quotation_id,
        )
        await self._validate_destination(company_id, branch_id, warehouse_id)
        ordered = await self._repository.get_ordered_quantities(
            company_id,
            purchase_quotation_id,
        )
        order_id = uuid.uuid4()
        details = self._build_details(order_id, quotation, lines, ordered)
        expense_entities = await self._build_expenses(company_id, order_id, expenses)
        code = await self._repository.allocate_next_code(company_id)
        order = self._build_order(
            order_id=order_id,
            company_id=company_id,
            code=code,
            created_by_id=created_by_id,
            quotation=quotation,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            order_date=datetime.now(UTC),
            expected_date=expected_date,
            details=details,
            expenses=expense_entities,
            notes=notes,
        )
        return await self._repository.add_order(order)

    async def update_draft(
        self,
        *,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        lines: tuple[PurchaseOrderLineDraft, ...],
        expected_date: datetime | None = None,
        expenses: tuple[PurchaseOrderExpenseDraft, ...] = (),
        notes: str | None = None,
    ) -> PurchaseOrder:
        current = await self._get_for_update(company_id, order_id)
        if current.status is not PurchaseOrderStatus.DRAFT:
            raise BusinessRuleError(
                "Solo una orden en borrador puede modificarse.",
                code="purchase_order_not_editable",
            )
        quotation = await self._get_selected_quotation_for_update(
            company_id,
            current.purchase_quotation_id,
        )
        await self._validate_destination(company_id, branch_id, warehouse_id)
        ordered = await self._repository.get_ordered_quantities(
            company_id,
            current.purchase_quotation_id,
            exclude_order_id=current.id,
        )
        details = self._build_details(current.id, quotation, lines, ordered)
        expense_entities = await self._build_expenses(
            company_id,
            current.id,
            expenses,
        )
        replacement = self._build_order(
            order_id=current.id,
            company_id=current.company_id,
            code=current.code,
            created_by_id=current.created_by_id,
            quotation=quotation,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            order_date=current.order_date,
            expected_date=expected_date,
            details=details,
            expenses=expense_entities,
            notes=notes,
            created_at=current.created_at,
        )
        saved = await self._repository.replace_draft(replacement)
        if saved is None:
            raise NotFoundError(
                "Orden de compra no encontrada.",
                code="purchase_order_not_found",
            )
        return saved

    async def submit_order(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> PurchaseOrder:
        return await self._transition(
            company_id,
            order_id,
            PurchaseOrderStatus.PENDING_APPROVAL,
        )

    async def approve_order(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> PurchaseOrder:
        return await self._transition(
            company_id,
            order_id,
            PurchaseOrderStatus.APPROVED,
        )

    async def send_order(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> PurchaseOrder:
        saved = await self._transition(
            company_id,
            order_id,
            PurchaseOrderStatus.SENT,
        )
        await self._repository.advance_purchase_request_order_statuses(
            company_id,
            saved.purchase_quotation_id,
        )
        return saved

    async def cancel_order(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> PurchaseOrder:
        return await self._transition(
            company_id,
            order_id,
            PurchaseOrderStatus.CANCELLED,
        )

    async def _get_selected_quotation_for_update(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> PurchaseOrderQuotationReference:
        reference = await self._repository.get_quotation_reference_for_update(
            company_id,
            quotation_id,
        )
        if reference is None:
            raise NotFoundError(
                "Cotización de compra no encontrada.",
                code="purchase_order_quotation_not_found",
            )
        if reference.status is not PurchaseQuotationStatus.SELECTED:
            raise BusinessRuleError(
                "La orden de compra debe generarse desde una cotización seleccionada.",
                code="purchase_order_quotation_not_selected",
            )
        if not reference.details:
            raise BusinessRuleError(
                "La cotización seleccionada no contiene productos ordenables.",
                code="purchase_order_quotation_without_details",
            )
        return reference

    async def _validate_destination(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> None:
        destination = await self._repository.get_destination_reference(
            company_id,
            branch_id,
            warehouse_id,
        )
        if destination is None:
            raise ValidationError(
                "La sucursal o almacén de destino no pertenece a la empresa indicada.",
                code="purchase_order_destination_invalid",
            )
        self._ensure_destination_available(destination)

    @staticmethod
    def _ensure_destination_available(destination: PurchaseOrderDestinationReference) -> None:
        if not destination.branch_is_active or destination.branch_operational_status != "active":
            raise BusinessRuleError(
                "La sucursal de destino no está operativa.",
                code="purchase_order_branch_unavailable",
            )
        if (
            not destination.warehouse_is_active
            or destination.warehouse_operational_status != "active"
            or not destination.warehouse_storage_eligible
        ):
            raise BusinessRuleError(
                "El almacén de destino no está disponible para recibir inventario.",
                code="purchase_order_warehouse_unavailable",
            )

    def _build_details(
        self,
        order_id: uuid.UUID,
        quotation: PurchaseOrderQuotationReference,
        lines: tuple[PurchaseOrderLineDraft, ...],
        ordered: dict[uuid.UUID, Decimal],
    ) -> tuple[PurchaseOrderDetail, ...]:
        if not lines:
            raise ValidationError(
                "La orden de compra debe incluir al menos un detalle.",
                code="purchase_order_details_required",
            )
        detail_ids = [line.purchase_quotation_detail_id for line in lines]
        if len(detail_ids) != len(set(detail_ids)):
            raise ValidationError(
                "Un detalle de cotización no puede repetirse en la orden.",
                code="purchase_order_duplicate_quotation_detail",
            )
        sources = {detail.id: detail for detail in quotation.details}
        details: list[PurchaseOrderDetail] = []
        for line in lines:
            source = sources.get(line.purchase_quotation_detail_id)
            if source is None:
                raise ValidationError(
                    "El detalle indicado no pertenece a la cotización seleccionada.",
                    code="purchase_order_quotation_detail_invalid",
                )
            maximum = (
                source.available_quantity
                if source.available_quantity is not None
                else source.quantity
            )
            already_ordered = ordered.get(source.id, Decimal("0"))
            remaining = maximum - already_ordered
            if not line.quantity.is_finite() or line.quantity <= 0:
                raise ValidationError(
                    "La cantidad ordenada debe ser mayor que cero.",
                    code="purchase_order_quantity_invalid",
                )
            if line.quantity > remaining:
                raise BusinessRuleError(
                    "La cantidad ordenada supera la disponibilidad restante de la cotización.",
                    code="purchase_order_quantity_exceeded",
                )
            details.append(self._build_detail(order_id, source, line.quantity))
        return tuple(details)

    def _build_detail(
        self,
        order_id: uuid.UUID,
        source: PurchaseOrderQuotationDetailReference,
        quantity: Decimal,
    ) -> PurchaseOrderDetail:
        subtotal = self._money(quantity * source.unit_price)
        discount = Decimal("0")
        if source.subtotal > 0 and source.discount > 0:
            discount = self._money(subtotal * source.discount / source.subtotal)
        taxable = subtotal - discount
        tax_amount = self._money(taxable * source.tax_rate / Decimal("100"))
        total = self._money(taxable + tax_amount)
        try:
            return PurchaseOrderDetail(
                id=uuid.uuid4(),
                purchase_order_id=order_id,
                product_id=source.product_id,
                quantity=quantity,
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
            raise ValidationError(
                str(exc),
                code="purchase_order_detail_invalid",
            ) from exc

    async def _build_expenses(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expenses: tuple[PurchaseOrderExpenseDraft, ...],
    ) -> tuple[PurchaseOrderExpense, ...]:
        entities: list[PurchaseOrderExpense] = []
        for draft in expenses:
            if not await self._repository.is_expense_type_active(
                company_id,
                draft.expense_type_id,
            ):
                raise ValidationError(
                    "El tipo de gasto indicado no existe o está inactivo.",
                    code="purchase_order_expense_type_invalid",
                )
            try:
                entities.append(
                    PurchaseOrderExpense(
                        id=uuid.uuid4(),
                        purchase_order_id=order_id,
                        expense_type_id=draft.expense_type_id,
                        amount=draft.amount,
                        description=draft.description,
                    )
                )
            except ValueError as exc:
                raise ValidationError(
                    str(exc),
                    code="purchase_order_expense_invalid",
                ) from exc
        return tuple(entities)

    def _build_order(
        self,
        *,
        order_id: uuid.UUID,
        company_id: uuid.UUID,
        code: str,
        created_by_id: uuid.UUID,
        quotation: PurchaseOrderQuotationReference,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        order_date: datetime,
        expected_date: datetime | None,
        details: tuple[PurchaseOrderDetail, ...],
        expenses: tuple[PurchaseOrderExpense, ...],
        notes: str | None,
        created_at: datetime | None = None,
    ) -> PurchaseOrder:
        subtotal = self._money(sum((detail.subtotal for detail in details), Decimal("0")))
        discount = self._money(sum((detail.discount for detail in details), Decimal("0")))
        tax = self._money(sum((detail.tax_amount for detail in details), Decimal("0")))
        additional_expenses = self._money(
            sum((expense.amount for expense in expenses), Decimal("0"))
        )
        total = self._money(
            sum((detail.total for detail in details), Decimal("0")) + additional_expenses
        )
        try:
            return PurchaseOrder(
                id=order_id,
                company_id=company_id,
                code=code,
                supplier_id=quotation.supplier_id,
                branch_id=branch_id,
                warehouse_id=warehouse_id,
                purchase_quotation_id=quotation.id,
                created_by_id=created_by_id,
                order_date=order_date,
                expected_date=expected_date,
                currency=quotation.currency,
                payment_terms=quotation.payment_terms,
                details=details,
                expenses=expenses,
                subtotal=subtotal,
                discount=discount,
                tax=tax,
                additional_expenses=additional_expenses,
                total=total,
                status=PurchaseOrderStatus.DRAFT,
                notes=notes,
                created_at=created_at,
            )
        except ValueError as exc:
            raise ValidationError(
                str(exc),
                code="purchase_order_invalid",
            ) from exc

    async def _get_for_update(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> PurchaseOrder:
        order = await self._repository.get_order_for_update(company_id, order_id)
        if order is None:
            raise NotFoundError(
                "Orden de compra no encontrada.",
                code="purchase_order_not_found",
            )
        return order

    async def _transition(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        target: PurchaseOrderStatus,
    ) -> PurchaseOrder:
        current = await self._get_for_update(company_id, order_id)
        try:
            ensure_purchase_order_transition(current.status, target)
        except PurchaseOrderTransitionError as exc:
            raise BusinessRuleError(
                str(exc),
                code="purchase_order_invalid_transition",
            ) from exc
        saved = await self._repository.update_status(company_id, order_id, target)
        if saved is None:
            raise NotFoundError(
                "Orden de compra no encontrada.",
                code="purchase_order_not_found",
            )
        return saved

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
