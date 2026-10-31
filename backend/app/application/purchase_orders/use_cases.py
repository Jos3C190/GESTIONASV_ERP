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
    PurchaseOrderExpenseTypeReference,
    PurchaseOrderQuotationDetailReference,
    PurchaseOrderQuotationReference,
    PurchaseOrderRepository,
)

MONEY_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class PurchaseOrderLineDraft:
    purchase_quotation_detail_id: uuid.UUID
    quantity: Decimal
    purchase_consolidation_award_id: uuid.UUID | None = None


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
        branch_id: uuid.UUID | None = None,
        status: PurchaseOrderStatus | None = None,
        supplier_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseOrder], int]:
        if branch_id is None:
            return await self._repository.list_orders(
                company_id,
                status=status,
                supplier_id=supplier_id,
                skip=skip,
                limit=limit,
            )
        return await self._repository.list_orders(
            company_id,
            branch_id=branch_id,
            status=status,
            supplier_id=supplier_id,
            skip=skip,
            limit=limit,
        )

    async def list_active_expense_types(
        self,
        company_id: uuid.UUID,
    ) -> tuple[PurchaseOrderExpenseTypeReference, ...]:
        return await self._repository.list_active_expense_types(company_id)

    async def list_expense_type_catalog(
        self,
        company_id: uuid.UUID,
    ) -> tuple[PurchaseOrderExpenseTypeReference, ...]:
        return await self._repository.list_expense_type_catalog(company_id)

    async def create_expense_type(
        self,
        company_id: uuid.UUID,
        *,
        name: str,
        description: str | None,
    ) -> PurchaseOrderExpenseTypeReference:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("El nombre del tipo de gasto es obligatorio.")
        normalized_description = description.strip() if description else None
        return await self._repository.create_expense_type(
            company_id,
            normalized_name,
            normalized_description or None,
        )

    async def update_expense_type(
        self,
        company_id: uuid.UUID,
        expense_type_id: uuid.UUID,
        *,
        name: str,
        description: str | None,
        is_active: bool,
    ) -> PurchaseOrderExpenseTypeReference:
        current = await self._repository.get_expense_type(company_id, expense_type_id)
        if current is None:
            raise NotFoundError("Tipo de gasto no encontrado.", code="expense_type_not_found")

        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("El nombre del tipo de gasto es obligatorio.")
        if current.usage_count and normalized_name.casefold() != current.name.casefold():
            raise BusinessRuleError(
                "No se puede cambiar el nombre de un tipo de gasto usado; desactívalo para conservar su historial.",
                code="expense_type_in_use",
            )

        normalized_description = description.strip() if description else None
        updated = await self._repository.update_expense_type(
            company_id,
            expense_type_id,
            name=normalized_name,
            description=normalized_description or None,
            is_active=is_active,
        )
        if updated is None:
            raise NotFoundError("Tipo de gasto no encontrado.", code="expense_type_not_found")
        return updated

    async def get_order(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
    ) -> PurchaseOrder:
        if branch_id is None:
            order = await self._repository.get_order(company_id, order_id)
        else:
            order = await self._repository.get_order(
                company_id,
                order_id,
                branch_id=branch_id,
            )
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
        branch_id: uuid.UUID | None,
        warehouse_id: uuid.UUID,
        lines: tuple[PurchaseOrderLineDraft, ...],
        quotation_branch_id: uuid.UUID | None = None,
        expected_date: datetime | None = None,
        expenses: tuple[PurchaseOrderExpenseDraft, ...] = (),
        notes: str | None = None,
    ) -> PurchaseOrder:
        quotation = await self._get_selected_quotation_for_update(
            company_id,
            purchase_quotation_id,
            branch_id=quotation_branch_id,
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

    async def create_draft_from_consolidation_awards(
        self,
        *,
        company_id: uuid.UUID,
        created_by_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        purchase_quotation_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        warehouse_id: uuid.UUID,
        expected_date: datetime | None = None,
        expenses: tuple[PurchaseOrderExpenseDraft, ...] = (),
        notes: str | None = None,
    ) -> PurchaseOrder:
        consolidation_status = await self._repository.get_consolidation_status_for_update(
            company_id, consolidation_id
        )
        if consolidation_status is None:
            raise NotFoundError(
                "Consolidado de compra no encontrado.",
                code="purchase_consolidation_not_found",
            )
        if consolidation_status == "cancelled":
            raise BusinessRuleError(
                "No se puede crear una orden desde un consolidado cancelado.",
                code="purchase_order_consolidation_cancelled",
            )

        quotation = await self._get_quotation_reference_for_update(
            company_id, purchase_quotation_id
        )
        self._validate_award_quotation(quotation, consolidation_id)

        await self._validate_destination(company_id, branch_id, warehouse_id, require_central=True)
        awards = await self._repository.list_active_awards_for_quotation_for_update(
            company_id, consolidation_id, purchase_quotation_id
        )
        if not awards:
            raise BusinessRuleError(
                "Esta cotización todavía no tiene cantidades adjudicadas.",
                code="purchase_order_without_awards",
            )

        ordered = await self._repository.get_ordered_award_quantities(
            company_id, tuple(award.id for award in awards)
        )
        source_by_id = {detail.id: detail for detail in quotation.details}
        order_id = uuid.uuid4()
        details: list[PurchaseOrderDetail] = []
        for award in awards:
            source = source_by_id.get(award.purchase_quotation_detail_id)
            if source is None or award.supplier_id != quotation.supplier_id:
                raise BusinessRuleError(
                    "La adjudicación ya no coincide con la oferta del proveedor.",
                    code="purchase_order_award_source_invalid",
                )
            already_ordered = ordered.get(award.id, Decimal("0"))
            remaining = award.quantity - already_ordered
            if remaining < 0:
                raise BusinessRuleError(
                    "La cantidad de órdenes existentes supera la adjudicación.",
                    code="purchase_order_award_quantity_exceeded",
                )
            if remaining == 0:
                continue
            details.append(
                self._build_detail(
                    order_id,
                    source,
                    remaining,
                    purchase_consolidation_award_id=award.id,
                )
            )

        if not details:
            raise BusinessRuleError(
                "Todas las cantidades adjudicadas de esta oferta ya están en órdenes de compra.",
                code="purchase_order_awards_already_ordered",
            )

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
            details=tuple(details),
            expenses=expense_entities,
            notes=notes,
        )
        return await self._repository.add_order(order)

    async def update_draft(
        self,
        *,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        warehouse_id: uuid.UUID,
        lines: tuple[PurchaseOrderLineDraft, ...],
        quotation_branch_id: uuid.UUID | None = None,
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
        is_awarded_order = any(
            detail.purchase_consolidation_award_id is not None for detail in current.details
        )
        if is_awarded_order:
            quotation = await self._get_quotation_reference_for_update(
                company_id,
                current.purchase_quotation_id,
            )
            if quotation.consolidation_id is None:
                raise BusinessRuleError(
                    "La orden adjudicada ya no conserva su consolidado de origen.",
                    code="purchase_order_award_source_invalid",
                )
        else:
            quotation = await self._get_selected_quotation_for_update(
                company_id,
                current.purchase_quotation_id,
                branch_id=quotation_branch_id,
            )
        if is_awarded_order:
            await self._validate_destination(
                company_id, branch_id, warehouse_id, require_central=True
            )
            self._ensure_awarded_order_lines_unchanged(current, lines)
            details = current.details
        else:
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
        *,
        branch_id: uuid.UUID | None = None,
    ) -> PurchaseOrderQuotationReference:
        reference = await self._get_quotation_reference_for_update(
            company_id, quotation_id, branch_id=branch_id
        )
        if reference.consolidation_id is not None:
            raise BusinessRuleError(
                "Las ofertas de un consolidado deben ordenarse desde sus cantidades adjudicadas.",
                code="purchase_order_consolidation_requires_award",
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

    async def _get_quotation_reference_for_update(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
    ) -> PurchaseOrderQuotationReference:
        if branch_id is None:
            reference = await self._repository.get_quotation_reference_for_update(
                company_id, quotation_id
            )
        else:
            reference = await self._repository.get_quotation_reference_for_update(
                company_id, quotation_id, branch_id=branch_id
            )
        if reference is None:
            raise NotFoundError(
                "Cotización de compra no encontrada.",
                code="purchase_order_quotation_not_found",
            )
        return reference

    @staticmethod
    def _ensure_awarded_order_lines_unchanged(
        current: PurchaseOrder,
        lines: tuple[PurchaseOrderLineDraft, ...],
    ) -> None:
        expected = {
            (
                detail.purchase_quotation_detail_id,
                detail.purchase_consolidation_award_id,
            ): detail.quantity
            for detail in current.details
        }
        received: dict[tuple[uuid.UUID, uuid.UUID | None], Decimal] = {}
        for line in lines:
            if line.purchase_consolidation_award_id is None:
                raise BusinessRuleError(
                    "Las líneas adjudicadas no se pueden quitar ni reemplazar desde la orden.",
                    code="purchase_order_awarded_lines_locked",
                )
            key = (line.purchase_quotation_detail_id, line.purchase_consolidation_award_id)
            if key in received:
                raise ValidationError(
                    "La misma adjudicación no puede repetirse en una orden.",
                    code="purchase_order_duplicate_award",
                )
            received[key] = line.quantity
        if received != expected:
            raise BusinessRuleError(
                "Las cantidades adjudicadas están protegidas. Para modificarlas, cancela la orden y corrige la adjudicación.",
                code="purchase_order_awarded_lines_locked",
            )

    async def _validate_destination(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        warehouse_id: uuid.UUID,
        *,
        require_central: bool = False,
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
        if require_central and not destination.warehouse_is_central:
            raise BusinessRuleError(
                "Las órdenes de un consolidado deben recibirse en una bodega madre activa.",
                code="purchase_order_central_warehouse_required",
            )

    @staticmethod
    def _ensure_destination_available(destination: PurchaseOrderDestinationReference) -> None:
        if destination.branch_id is not None and (
            not destination.branch_is_active or destination.branch_operational_status != "active"
        ):
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
            if line.purchase_consolidation_award_id is not None:
                raise ValidationError(
                    "Una orden normal no puede incluir una adjudicación de consolidado.",
                    code="purchase_order_award_reference_invalid",
                )
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
        *,
        purchase_consolidation_award_id: uuid.UUID | None = None,
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
                purchase_quotation_detail_id=source.id,
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
                purchase_consolidation_award_id=purchase_consolidation_award_id,
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
        branch_id: uuid.UUID | None,
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

    @staticmethod
    def _validate_award_quotation(
        quotation: PurchaseOrderQuotationReference, consolidation_id: uuid.UUID
    ) -> None:
        if quotation.consolidation_id != consolidation_id:
            raise BusinessRuleError(
                "La cotización no pertenece al consolidado indicado.",
                code="purchase_order_consolidation_quotation_mismatch",
            )
        if quotation.status not in {
            PurchaseQuotationStatus.UNDER_EVALUATION,
            PurchaseQuotationStatus.SELECTED,
        }:
            raise BusinessRuleError(
                "La oferta debe estar en evaluación para convertir sus adjudicaciones en orden.",
                code="purchase_order_consolidation_quotation_unavailable",
            )
        if not quotation.details:
            raise BusinessRuleError(
                "La oferta no contiene productos para ordenar.",
                code="purchase_order_quotation_without_details",
            )
