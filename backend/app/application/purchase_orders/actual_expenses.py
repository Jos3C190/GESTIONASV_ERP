"""Actual expense log available during the shipment's wait, without changing budgets."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.actual_expense import (
    ActualExpenseAvailability,
    ActualPurchaseExpense,
    is_fixed_retaceo_category,
)
from app.domain.entities.purchase_order import PurchaseOrder, PurchaseOrderStatus
from app.domain.ports.purchase_order_repository import PurchaseOrderRepository


class ActualExpenseUseCases:
    def __init__(self, repository: PurchaseOrderRepository) -> None:
        self.repository = repository

    async def availability(
        self, company_id: uuid.UUID, order: PurchaseOrder
    ) -> ActualExpenseAvailability:
        closure = await self.repository.get_actual_expense_closure(company_id, order.id)
        if closure is not None:
            return ActualExpenseAvailability(
                can_record=False,
                reason=f"{closure.retaceo_code} está cerrado. Ya no se pueden registrar otros gastos reales para esta orden.",
                closed_retaceo_id=closure.retaceo_id,
                closed_retaceo_code=closure.retaceo_code,
            )
        if order.status not in {
            PurchaseOrderStatus.APPROVED,
            PurchaseOrderStatus.SENT,
            PurchaseOrderStatus.PARTIALLY_RECEIVED,
            PurchaseOrderStatus.RECEIVED,
        }:
            return ActualExpenseAvailability(
                False, "Registre gastos reales desde la aprobación y antes del cierre de la orden."
            )
        return ActualExpenseAvailability(True)

    async def create(
        self,
        *,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_type_id: uuid.UUID,
        amount: Decimal,
        incurred_on: date,
        reference: str,
        description: str,
    ) -> ActualPurchaseExpense:
        order = await self.repository.get_order_for_update(company_id, order_id)
        if order is None:
            raise NotFoundError("Orden no encontrada.", code="purchase_order_not_found")
        available = await self.availability(company_id, order)
        if not available.can_record:
            raise BusinessRuleError(
                available.reason or "El registro de gastos está cerrado.",
                code="actual_expense_retaceo_closed"
                if available.closed_retaceo_id
                else "actual_expense_order_not_editable",
            )
        category = await self.repository.get_expense_type(company_id, expense_type_id)
        if category is None or not category.is_active:
            raise ValidationError(
                "Seleccione un tipo de gasto activo de esta empresa.",
                code="actual_expense_category_invalid",
            )
        if is_fixed_retaceo_category(category.name):
            raise ValidationError(
                "FOB, flete, DAI e IVA tienen campos propios en retaceo. Seleccione la categoría del otro gasto.",
                code="actual_expense_fixed_category",
            )
        expense = ActualPurchaseExpense(
            id=uuid.uuid4(),
            company_id=company_id,
            purchase_order_id=order_id,
            expense_type_id=expense_type_id,
            amount=amount,
            incurred_on=incurred_on,
            reference=reference.strip(),
            description=description.strip(),
        )
        return await self.repository.add_actual_expense(expense)
