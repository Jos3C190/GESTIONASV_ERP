"""Application use cases for retaceo landed-cost allocations."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.purchase import Purchase, PurchaseStatus
from app.domain.entities.retaceo import (
    Retaceo,
    RetaceoDetail,
    RetaceoSourceLine,
    RetaceoStatus,
    RetaceoTransitionError,
    calculate_retaceo_allocation,
    ensure_retaceo_transition,
)
from app.domain.ports.purchase_repository import PurchaseRepository
from app.domain.ports.retaceo_repository import RetaceoRepository

MONEY_QUANTUM = Decimal("0.000001")
RETACEO_PURCHASE_STATUSES = frozenset(
    {
        PurchaseStatus.RECEIVED,
        PurchaseStatus.VERIFIED,
        PurchaseStatus.CLOSED,
    }
)


class RetaceoUseCases:
    def __init__(
        self,
        repository: RetaceoRepository,
        purchases: PurchaseRepository,
    ) -> None:
        self._repository = repository
        self._purchases = purchases

    async def list_retaceos(
        self,
        company_id: uuid.UUID,
        *,
        status: RetaceoStatus | None = None,
        purchase_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Retaceo], int]:
        return await self._repository.list_retaceos(
            company_id,
            status=status,
            purchase_id=purchase_id,
            branch_id=branch_id,
            skip=skip,
            limit=limit,
        )

    async def get_retaceo(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo:
        item = await self._repository.get_retaceo(company_id, retaceo_id)
        if item is None:
            raise NotFoundError("Retaceo no encontrado.", code="retaceo_not_found")
        return item

    async def create_draft(
        self,
        *,
        company_id: uuid.UUID,
        created_by_id: uuid.UUID,
        purchase_id: uuid.UUID,
        total_freight: Decimal,
        total_expenses: Decimal,
        total_dai: Decimal,
        import_vat: Decimal,
        notes: str | None = None,
    ) -> Retaceo:
        purchase = await self._get_purchase_for_update(company_id, purchase_id)
        self._ensure_purchase_eligible(purchase)

        retaceo_id = uuid.uuid4()
        code = await self._repository.allocate_next_code(company_id)
        draft = self._build_from_purchase(
            retaceo_id=retaceo_id,
            code=code,
            purchase=purchase,
            created_by_id=created_by_id,
            total_freight=total_freight,
            total_expenses=total_expenses,
            total_dai=total_dai,
            import_vat=import_vat,
            notes=notes,
        )
        return await self._repository.add_retaceo(draft)

    async def update_draft(
        self,
        *,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        total_freight: Decimal,
        total_expenses: Decimal,
        total_dai: Decimal,
        import_vat: Decimal,
        notes: str | None = None,
    ) -> Retaceo:
        current = await self._get_for_update(company_id, retaceo_id)
        if current.status is not RetaceoStatus.DRAFT:
            raise BusinessRuleError(
                "Solo un retaceo en borrador puede modificarse.",
                code="retaceo_not_editable",
            )

        purchase = await self._get_purchase_for_update(company_id, current.purchase_id)
        self._ensure_purchase_eligible(purchase)
        replacement = self._build_from_purchase(
            retaceo_id=current.id,
            code=current.code,
            purchase=purchase,
            created_by_id=current.created_by_id,
            total_freight=total_freight,
            total_expenses=total_expenses,
            total_dai=total_dai,
            import_vat=import_vat,
            notes=notes,
            created_at=current.created_at,
        )
        saved = await self._repository.replace_draft(replacement)
        if saved is None:
            raise NotFoundError("Retaceo no encontrado.", code="retaceo_not_found")
        return saved

    async def calculate_retaceo(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo:
        return await self._transition(company_id, retaceo_id, RetaceoStatus.CALCULATED)

    async def verify_retaceo(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo:
        return await self._transition(company_id, retaceo_id, RetaceoStatus.VERIFIED)

    async def cancel_retaceo(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo:
        return await self._transition(company_id, retaceo_id, RetaceoStatus.CANCELLED)

    async def close_retaceo(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo:
        return await self._transition(company_id, retaceo_id, RetaceoStatus.CLOSED)

    async def _get_for_update(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo:
        item = await self._repository.get_retaceo_for_update(company_id, retaceo_id)
        if item is None:
            raise NotFoundError("Retaceo no encontrado.", code="retaceo_not_found")
        return item

    async def _get_purchase_for_update(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> Purchase:
        purchase = await self._purchases.get_purchase_for_update(company_id, purchase_id)
        if purchase is None:
            raise NotFoundError("Compra no encontrada.", code="purchase_not_found")
        return purchase

    @staticmethod
    def _ensure_purchase_eligible(purchase: Purchase) -> None:
        if purchase.status not in RETACEO_PURCHASE_STATUSES:
            raise BusinessRuleError(
                "El retaceo requiere una compra recibida, verificada o cerrada.",
                code="retaceo_purchase_not_eligible",
            )

    async def _transition(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        target: RetaceoStatus,
    ) -> Retaceo:
        current = await self._get_for_update(company_id, retaceo_id)
        try:
            ensure_retaceo_transition(current.status, target)
        except RetaceoTransitionError as exc:
            raise BusinessRuleError(
                "La transición solicitada no es válida para el estado actual del retaceo.",
                code="retaceo_invalid_transition",
            ) from exc

        updated = await self._repository.update_status(company_id, retaceo_id, target)
        if updated is None:
            raise NotFoundError("Retaceo no encontrado.", code="retaceo_not_found")
        return updated

    def _build_from_purchase(
        self,
        *,
        retaceo_id: uuid.UUID,
        code: str,
        purchase: Purchase,
        created_by_id: uuid.UUID,
        total_freight: Decimal,
        total_expenses: Decimal,
        total_dai: Decimal,
        import_vat: Decimal,
        notes: str | None,
        created_at: datetime | None = None,
    ) -> Retaceo:
        if not import_vat.is_finite() or import_vat < 0:
            raise ValidationError(
                "El IVA de importación no puede ser negativo ni no finito.",
                code="retaceo_import_vat_invalid",
            )
        normalized_import_vat = import_vat.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)

        sources = tuple(
            RetaceoSourceLine(
                purchase_detail_id=detail.id,
                product_id=detail.product_id,
                unit_id=detail.unit_id,
                quantity=detail.quantity_received,
                cost_fob=detail.subtotal - detail.discount,
            )
            for detail in purchase.details
        )
        try:
            allocation = calculate_retaceo_allocation(
                sources,
                total_freight=total_freight,
                total_expenses=total_expenses,
                total_dai=total_dai,
            )
            details = tuple(
                RetaceoDetail(
                    id=uuid.uuid4(),
                    retaceo_id=retaceo_id,
                    purchase_detail_id=line.purchase_detail_id,
                    product_id=line.product_id,
                    unit_id=line.unit_id,
                    quantity=line.quantity,
                    cost_fob=line.cost_fob,
                    freight=line.freight,
                    expenses=line.expenses,
                    dai=line.dai,
                    total_cost=line.total_cost,
                    unit_cost=line.unit_cost,
                )
                for line in allocation.lines
            )
            return Retaceo(
                id=retaceo_id,
                company_id=purchase.company_id,
                code=code,
                purchase_id=purchase.id,
                branch_id=purchase.branch_id,
                created_by_id=created_by_id,
                currency=purchase.currency,
                details=details,
                total_fob=allocation.total_fob,
                total_freight=allocation.total_freight,
                total_expenses=allocation.total_expenses,
                total_dai=allocation.total_dai,
                import_vat=normalized_import_vat,
                total_cost=allocation.total_cost,
                status=RetaceoStatus.DRAFT,
                notes=notes,
                created_at=created_at,
            )
        except ValueError as exc:
            raise ValidationError(
                str(exc),
                code="retaceo_allocation_invalid",
            ) from exc
