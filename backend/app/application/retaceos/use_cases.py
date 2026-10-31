"""Application use cases for retaceo landed-cost allocations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.application.retaceos.manual_entry import fixed_allocations, protected_invoice
from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.actual_expense import ActualPurchaseExpense, is_fixed_retaceo_category
from app.domain.entities.purchase import (
    Purchase,
    PurchaseDetail,
    PurchaseInventoryWorkflow,
    PurchaseStatus,
)
from app.domain.entities.retaceo import (
    FOB_CORRECTION_REASON_MIN_LENGTH,
    ManualRetaceoAllocation,
    Retaceo,
    RetaceoCost,
    RetaceoCostAllocation,
    RetaceoCostClass,
    RetaceoCostDocument,
    RetaceoDetail,
    RetaceoImportData,
    RetaceoSourceLine,
    RetaceoStatus,
    RetaceoTransitionError,
    calculate_manual_retaceo_allocation,
    calculate_retaceo_allocation,
    ensure_retaceo_transition,
)
from app.domain.entities.retaceo_calculation import CalculationMode, calculate_import_taxes
from app.domain.ports.inventory_valuation import RetaceoAverageComparison, RetaceoValuationGateway
from app.domain.ports.purchase_order_expense_document_repository import (
    PurchaseOrderExpenseDocumentRepository,
)
from app.domain.ports.purchase_order_repository import (
    PurchaseOrderExpenseTypeReference,
    PurchaseOrderRepository,
)
from app.domain.ports.purchase_repository import PurchaseRepository
from app.domain.ports.retaceo_repository import RetaceoRepository

MONEY_QUANTUM = Decimal("0.000001")
RETACEO_PURCHASE_STATUSES = frozenset(
    {
        PurchaseStatus.VERIFIED,
        PurchaseStatus.CLOSED,
    }
)


@dataclass(frozen=True, slots=True)
class RetaceoCostDraft:
    id: uuid.UUID | None
    classification: RetaceoCostClass
    title: str
    amount: Decimal
    allocations: tuple[RetaceoCostAllocation, ...] = ()
    description: str | None = None
    expense_type_id: uuid.UUID | None = None
    source_purchase_order_expense_id: uuid.UUID | None = None
    incurred_on: date | None = None


@dataclass(frozen=True, slots=True)
class RetaceoFobDraft:
    purchase_detail_id: uuid.UUID
    amount: Decimal


class RetaceoUseCases:
    def __init__(
        self,
        repository: RetaceoRepository,
        purchases: PurchaseRepository,
        orders: PurchaseOrderRepository | None = None,
        expense_documents: PurchaseOrderExpenseDocumentRepository | None = None,
        valuation: RetaceoValuationGateway | None = None,
    ) -> None:
        self._repository = repository
        self._purchases = purchases
        self._orders = orders
        self._expense_documents = expense_documents
        self._valuation = valuation

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

    async def inventory_after_retaceo(self, company_id: uuid.UUID, purchase_id: uuid.UUID) -> bool:
        purchase = await self._purchases.get_purchase(company_id, purchase_id)
        if purchase is None:
            raise NotFoundError("Compra no encontrada.", code="purchase_not_found")
        return purchase.inventory_workflow is not PurchaseInventoryWorkflow.LEGACY

    async def cost_categories(
        self, company_id: uuid.UUID
    ) -> tuple[PurchaseOrderExpenseTypeReference, ...]:
        if self._orders is None:
            return ()
        return tuple(
            row
            for row in await self._orders.list_active_expense_types(company_id)
            if not is_fixed_retaceo_category(row.name)
        )

    async def average_comparison(
        self, company_id: uuid.UUID, retaceo_id: uuid.UUID
    ) -> RetaceoAverageComparison:
        if self._valuation is None:
            raise BusinessRuleError("Valoración no configurada.", code="valuation_unavailable")
        retaceo = await self.get_retaceo(company_id, retaceo_id)
        await self._valuation.lock(company_id)
        return await self._valuation.average_comparison(retaceo)

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
        fob_lines: tuple[RetaceoFobDraft, ...] | None = None,
        import_data: RetaceoImportData | None = None,
        manual_entry: bool = True,
        calculation_mode: CalculationMode | None = None,
        dai_rate: Decimal | None = None,
        vat_rate: Decimal | None = None,
    ) -> Retaceo:
        purchase = await self._get_purchase_for_update(company_id, purchase_id)
        self._ensure_purchase_eligible(purchase)
        calculation_mode = calculation_mode or "manual"
        if calculation_mode == "automatic":
            if fob_lines is not None:
                raise ValidationError(
                    "El FOB automático proviene de la compra.", code="retaceo_automatic_fob_locked"
                )
            total_dai, import_vat = self._automatic_amounts(
                purchase, total_freight, dai_rate, vat_rate
            )
        else:
            dai_rate = vat_rate = None
        after_retaceo = purchase.inventory_workflow is not PurchaseInventoryWorkflow.LEGACY
        if after_retaceo or manual_entry:
            existing, _ = await self._repository.list_retaceos(
                company_id, purchase_id=purchase.id, limit=200
            )
            if any(item.status is not RetaceoStatus.CANCELLED for item in existing):
                raise BusinessRuleError(
                    "Esta compra ya tiene un retaceo activo. Continúe desde ese documento.",
                    code="retaceo_purchase_already_exists",
                )
        if (after_retaceo or manual_entry) and fob_lines is None and calculation_mode == "manual":
            raise ValidationError(
                "Registre manualmente el FOB de cada producto.", code="retaceo_fob_required"
            )
        if self._valuation is not None and not after_retaceo:
            await self._valuation.lock(company_id)
            if await self._valuation.enabled(
                company_id
            ) and not await self._valuation.receipt_is_valued(company_id, purchase_id):
                raise BusinessRuleError(
                    "Esta recepción pertenece al saldo inicial. Su costo debe quedar documentado en ese corte; no puede aplicarse otra vez como una recepción nueva.",
                    code="retaceo_receipt_before_valuation_opening",
                )

        retaceo_id = uuid.uuid4()
        if manual_entry and total_expenses != 0:
            raise ValidationError(
                "Desglose los otros gastos por categoría en el borrador.",
                code="retaceo_expense_breakdown_required",
            )
        source_costs = (
            ()
            if after_retaceo or manual_entry
            else await self._source_costs(company_id, purchase, retaceo_id)
        )
        if (self._orders is not None or manual_entry) and self._has_legacy_amounts(
            total_freight, total_expenses, total_dai, import_vat
        ):
            source_costs += self._legacy_costs(
                retaceo_id=retaceo_id,
                total_freight=total_freight,
                total_expenses=total_expenses,
                total_dai=total_dai,
                import_vat=import_vat,
            )

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
            costs=source_costs if self._orders is not None or manual_entry else None,
            fob_lines=fob_lines,
            import_data=import_data,
            manual_entry=manual_entry,
            calculation_mode=calculation_mode,
            dai_rate=dai_rate,
            vat_rate=vat_rate,
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
        costs: tuple[RetaceoCostDraft, ...] | None = None,
        fob_lines: tuple[RetaceoFobDraft, ...] | None = None,
        import_data: RetaceoImportData | None = None,
        calculation_mode: CalculationMode | None = None,
        dai_rate: Decimal | None = None,
        vat_rate: Decimal | None = None,
    ) -> Retaceo:
        current = await self._get_for_update(company_id, retaceo_id)
        if current.status is not RetaceoStatus.DRAFT:
            raise BusinessRuleError(
                "Solo un retaceo en borrador puede modificarse.",
                code="retaceo_not_editable",
            )

        purchase = await self._get_purchase_for_update(company_id, current.purchase_id)
        self._ensure_purchase_eligible(purchase)
        calculation_mode = calculation_mode or current.calculation_mode
        if calculation_mode == "automatic":
            if fob_lines is not None:
                raise ValidationError(
                    "El FOB automático proviene de la compra.", code="retaceo_automatic_fob_locked"
                )
            dai_rate = dai_rate if dai_rate is not None else current.dai_rate
            vat_rate = vat_rate if vat_rate is not None else current.vat_rate
            total_dai, import_vat = self._automatic_amounts(
                purchase, total_freight, dai_rate, vat_rate
            )
        else:
            dai_rate = vat_rate = None
        if (
            purchase.inventory_workflow is not PurchaseInventoryWorkflow.LEGACY
            and fob_lines is None
            and calculation_mode == "manual"
        ):
            fob_lines = tuple(
                RetaceoFobDraft(detail.purchase_detail_id, detail.cost_fob)
                for detail in current.details
            )
        merged_costs = current.costs or None
        if costs is not None:
            merged_costs = self._merge_costs(current, costs)
        if calculation_mode == "automatic":
            merged_costs = self._automatic_costs(
                purchase, current.id, merged_costs or (), total_freight, total_dai, import_vat
            )
        if current.manual_entry:
            merged_costs = await self._validate_manual_expenses(
                purchase, current, merged_costs or ()
            )
            if fob_lines is None and calculation_mode == "manual":
                fob_lines = tuple(
                    RetaceoFobDraft(line.purchase_detail_id, line.cost_fob)
                    for line in current.details
                )
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
            costs=merged_costs,
            fob_lines=fob_lines,
            import_data=import_data
            or RetaceoImportData(
                origin_country=current.origin_country,
                import_invoice_number=current.import_invoice_number,
                import_invoice_date=current.import_invoice_date,
                import_policy_number=current.import_policy_number,
                import_policy_date=current.import_policy_date,
            ),
            manual_entry=current.manual_entry,
            calculation_mode=calculation_mode,
            dai_rate=dai_rate,
            vat_rate=vat_rate,
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

    async def apply_retaceo(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> Retaceo:
        if self._valuation is None:
            raise BusinessRuleError("Valoración no configurada.", code="valuation_unavailable")
        await self._valuation.lock(company_id)
        current = await self._get_for_update(company_id, retaceo_id)
        purchase = await self._purchases.get_purchase(company_id, current.purchase_id)
        if (
            purchase is not None
            and purchase.inventory_workflow is not PurchaseInventoryWorkflow.LEGACY
        ):
            raise BusinessRuleError(
                "Este retaceo se incorpora al registrar la recepción después de su cierre.",
                code="retaceo_applied_with_receipt",
            )
        if current.applied_at is not None:
            return current
        if current.status is not RetaceoStatus.VERIFIED:
            raise BusinessRuleError(
                "Verifique el retaceo antes de aplicar su costo al inventario.",
                code="retaceo_apply_requires_verified",
            )
        await self._valuation.apply_retaceo(current, actor_id)
        return await self.get_retaceo(company_id, retaceo_id)

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
        eligible = purchase.status in RETACEO_PURCHASE_STATUSES or (
            purchase.inventory_workflow is not PurchaseInventoryWorkflow.LEGACY
            and purchase.status is PurchaseStatus.RECEIVED
        )
        if not eligible:
            raise BusinessRuleError(
                "Confirme el documento de recepción antes de crear el retaceo.",
                code="retaceo_purchase_not_eligible",
            )

    async def _transition(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        target: RetaceoStatus,
    ) -> Retaceo:
        if self._valuation is not None:
            await self._valuation.lock(company_id)
        current = await self._get_for_update(company_id, retaceo_id)
        purchase = await self._purchases.get_purchase(company_id, current.purchase_id)
        after_retaceo = (
            purchase is not None
            and purchase.inventory_workflow is not PurchaseInventoryWorkflow.LEGACY
        )
        if (
            target is RetaceoStatus.CLOSED
            and not after_retaceo
            and current.applied_at is None
            and self._valuation is not None
            and await self._valuation.enabled(company_id)
        ):
            raise BusinessRuleError(
                "Aplique el costo al inventario antes de cerrar el retaceo.",
                code="retaceo_application_required",
            )
        if target is RetaceoStatus.CALCULATED:
            if current.manual_entry and purchase is not None:
                await self._validate_manual_expenses(purchase, current, current.costs)
            self._ensure_costs_calculable(current)
        try:
            ensure_retaceo_transition(current.status, target)
        except RetaceoTransitionError as exc:
            raise BusinessRuleError(
                "La transición solicitada no es válida para el estado actual del retaceo.",
                code="retaceo_invalid_transition",
            ) from exc

        if target is RetaceoStatus.CLOSED and self._orders is not None and purchase is not None:
            # Serialize closure with actual-expense creation on the same order.
            await self._orders.get_order_for_update(company_id, purchase.purchase_order_id)

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
        costs: tuple[RetaceoCost, ...] | None = None,
        fob_lines: tuple[RetaceoFobDraft, ...] | None = None,
        import_data: RetaceoImportData | None = None,
        manual_entry: bool = False,
        calculation_mode: CalculationMode = "manual",
        dai_rate: Decimal | None = None,
        vat_rate: Decimal | None = None,
    ) -> Retaceo:
        if not import_vat.is_finite() or import_vat < 0:
            raise ValidationError(
                "El IVA de importación no puede ser negativo ni no finito.",
                code="retaceo_import_vat_invalid",
            )
        normalized_import_vat = import_vat.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        customs = (
            protected_invoice(purchase, import_data)
            if manual_entry
            else (import_data or RetaceoImportData())
        )

        sources = self._receipt_sources(purchase)
        if fob_lines is not None:
            amounts = {line.purchase_detail_id: line.amount for line in fob_lines}
            if len(amounts) != len(fob_lines) or set(amounts) != {
                line.purchase_detail_id for line in sources
            }:
                raise ValidationError(
                    "Indique un FOB por cada línea de la compra, sin repetir productos.",
                    code="retaceo_fob_lines_invalid",
                )
            if any(not value.is_finite() or value <= 0 for value in amounts.values()):
                raise ValidationError(
                    "El FOB de cada línea debe ser mayor que cero.", code="retaceo_fob_invalid"
                )
            if (
                purchase.inventory_workflow is PurchaseInventoryWorkflow.LEGACY
                and any(amounts[line.purchase_detail_id] != line.cost_fob for line in sources)
                and (
                    not manual_entry
                    or len((notes or "").strip()) < FOB_CORRECTION_REASON_MIN_LENGTH
                )
            ):
                raise BusinessRuleError(
                    "Esta recepción ya tiene un valor histórico. Para regularizar su FOB, capture el importe documentado y un motivo de al menos 20 caracteres en Notas. La recepción original se conserva; al aplicar se registra un ajuste de valor separado.",
                    code="retaceo_historical_fob_locked",
                )
            sources = tuple(
                RetaceoSourceLine(
                    purchase_detail_id=line.purchase_detail_id,
                    product_id=line.product_id,
                    unit_id=line.unit_id,
                    quantity=line.quantity,
                    cost_fob=amounts[line.purchase_detail_id],
                )
                for line in sources
            )
        if not sources:
            raise BusinessRuleError(
                "No se puede crear un retaceo: la recepción no tiene cantidades aceptadas.",
                code="retaceo_without_accepted_quantity",
            )
        try:
            if manual_entry:
                if self._money(total_expenses) != self._money(
                    sum(
                        (
                            cost.amount
                            for cost in (costs or ())
                            if cost.is_active and cost.classification is RetaceoCostClass.EXPENSE
                        ),
                        Decimal("0"),
                    )
                ):
                    raise ValidationError(
                        "El total de otros gastos debe coincidir con su desglose.",
                        code="retaceo_expense_total_mismatch",
                    )
                costs = fixed_allocations(
                    sources,
                    costs or (),
                    freight=total_freight,
                    dai=total_dai,
                    vat=normalized_import_vat,
                )
            allocation = (
                calculate_manual_retaceo_allocation(sources, costs)
                if costs is not None
                else calculate_retaceo_allocation(
                    sources,
                    total_freight=total_freight,
                    total_expenses=total_expenses,
                    total_dai=total_dai,
                )
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
                import_vat=(
                    allocation.import_vat
                    if isinstance(allocation, ManualRetaceoAllocation)
                    else normalized_import_vat
                ),
                total_cost=allocation.total_cost,
                status=RetaceoStatus.DRAFT,
                notes=notes,
                created_at=created_at,
                costs=costs or (),
                manual_entry=manual_entry,
                calculation_mode=calculation_mode,
                dai_rate=dai_rate,
                vat_rate=vat_rate,
                origin_country=customs.origin_country,
                import_invoice_number=customs.import_invoice_number,
                import_invoice_date=customs.import_invoice_date,
                import_policy_number=customs.import_policy_number,
                import_policy_date=customs.import_policy_date,
            )
        except ValueError as exc:
            raise ValidationError(
                str(exc),
                code="retaceo_allocation_invalid",
            ) from exc

    def _accepted_quantity(self, detail: PurchaseDetail) -> Decimal:
        return (
            detail.quantity_accepted
            if detail.quantity_accepted is not None
            else detail.quantity_received
        )

    def _accepted_fob(self, detail: PurchaseDetail) -> Decimal:
        received_fob = detail.subtotal - detail.discount
        if detail.quantity_accepted is None:
            # Legacy verified rows predate accepted quantities; preserve their
            # historical received quantity until the receipt is otherwise changed.
            return received_fob
        if detail.quantity_accepted == 0:
            return Decimal("0")
        return self._money(received_fob * detail.quantity_accepted / detail.quantity_received)

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)

    async def _source_costs(
        self,
        company_id: uuid.UUID,
        purchase: Purchase,
        retaceo_id: uuid.UUID,
    ) -> tuple[RetaceoCost, ...]:
        if self._orders is None:
            return ()
        order = await self._orders.get_order(company_id, purchase.purchase_order_id)
        if order is None:
            raise NotFoundError("Orden de compra no encontrada.", code="purchase_order_not_found")
        expense_types = await self._orders.list_expense_type_catalog(company_id)
        type_names = {item.id: item.name for item in expense_types}
        costs: list[RetaceoCost] = []
        for expense in order.expenses:
            cost_id = uuid.uuid4()
            documents: tuple[RetaceoCostDocument, ...] = ()
            if self._expense_documents is not None:
                source_documents = await self._expense_documents.list_documents(
                    company_id,
                    order.id,
                    expense.id,
                )
                documents = tuple(
                    RetaceoCostDocument(
                        id=uuid.uuid4(),
                        retaceo_cost_id=cost_id,
                        document_id=document.document_id,
                        file_name=document.file_name,
                        file_type=document.file_type,
                        uploaded_at=document.uploaded_at,
                        created_at=document.created_at,
                        updated_at=document.updated_at,
                    )
                    for document in source_documents
                )
            costs.append(
                RetaceoCost(
                    id=cost_id,
                    retaceo_id=retaceo_id,
                    classification=RetaceoCostClass.EXPENSE,
                    title=type_names.get(expense.expense_type_id, "Gasto de orden"),
                    amount=expense.amount,
                    documents=documents,
                    source_purchase_order_expense_id=expense.id,
                    expense_type_id=expense.expense_type_id,
                    description=expense.description,
                )
            )
        return tuple(costs)

    @staticmethod
    def _has_legacy_amounts(*amounts: Decimal) -> bool:
        return any(amount > 0 for amount in amounts)

    @staticmethod
    def _legacy_costs(
        *,
        retaceo_id: uuid.UUID,
        total_freight: Decimal,
        total_expenses: Decimal,
        total_dai: Decimal,
        import_vat: Decimal,
    ) -> tuple[RetaceoCost, ...]:
        rows = (
            (RetaceoCostClass.FREIGHT, "Flete", total_freight),
            (RetaceoCostClass.EXPENSE, "Gastos adicionales", total_expenses),
            (RetaceoCostClass.DAI, "DAI", total_dai),
            (RetaceoCostClass.IMPORT_VAT, "IVA de importación", import_vat),
        )
        return tuple(
            RetaceoCost(
                id=uuid.uuid4(),
                retaceo_id=retaceo_id,
                classification=kind,
                title=label,
                amount=amount,
            )
            for kind, label, amount in rows
            if amount > 0
        )

    @staticmethod
    def _merge_costs(
        current: Retaceo,
        drafts: tuple[RetaceoCostDraft, ...],
    ) -> tuple[RetaceoCost, ...]:
        current_by_id = {cost.id: cost for cost in current.costs}
        seen_ids: set[uuid.UUID] = set()
        output: list[RetaceoCost] = []
        for draft in drafts:
            reusable = (
                next(
                    (
                        row
                        for row in current.costs
                        if not row.is_active
                        and row.source_purchase_order_expense_id
                        == draft.source_purchase_order_expense_id
                    ),
                    None,
                )
                if current.manual_entry and draft.source_purchase_order_expense_id is not None
                else None
            )
            cost_id = draft.id or (reusable.id if reusable is not None else uuid.uuid4())
            if cost_id in seen_ids:
                raise ValidationError("Un gasto no puede repetirse.", code="retaceo_cost_duplicate")
            seen_ids.add(cost_id)
            previous = current_by_id.get(cost_id)
            if draft.id is not None and previous is None:
                raise NotFoundError(
                    "Gasto de retaceo no encontrado.", code="retaceo_cost_not_found"
                )
            if (
                current.manual_entry
                and previous is not None
                and draft.source_purchase_order_expense_id
                != previous.source_purchase_order_expense_id
            ):
                raise BusinessRuleError(
                    "Conserve la referencia del gasto guardado. Para corregirla, retire la línea y registre otra.",
                    code="retaceo_cost_source_locked",
                )
            output.append(
                RetaceoCost(
                    id=cost_id,
                    retaceo_id=current.id,
                    classification=draft.classification,
                    title=draft.title,
                    amount=draft.amount,
                    allocations=draft.allocations,
                    documents=previous.documents if previous else (),
                    source_purchase_order_expense_id=(
                        previous.source_purchase_order_expense_id
                        if previous
                        else draft.source_purchase_order_expense_id
                    ),
                    expense_type_id=draft.expense_type_id
                    if current.manual_entry
                    else (previous.expense_type_id if previous else None),
                    incurred_on=draft.incurred_on
                    if current.manual_entry
                    else (previous.incurred_on if previous else None),
                    description=draft.description,
                    is_active=True,
                    created_at=previous.created_at if previous else None,
                    updated_at=previous.updated_at if previous else None,
                )
            )

        for previous in current.costs:
            if (
                previous.source_purchase_order_expense_id is not None
                and previous.id not in seen_ids
                and not current.manual_entry
            ):
                raise BusinessRuleError(
                    "Los gastos heredados de la orden no se pueden quitar del retaceo.",
                    code="retaceo_source_cost_required",
                )
            if previous.id not in seen_ids and previous.is_active:
                output.append(
                    RetaceoCost(
                        id=previous.id,
                        retaceo_id=current.id,
                        classification=previous.classification,
                        title=previous.title,
                        amount=previous.amount,
                        allocations=previous.allocations,
                        documents=previous.documents,
                        source_purchase_order_expense_id=previous.source_purchase_order_expense_id,
                        expense_type_id=previous.expense_type_id,
                        description=previous.description,
                        is_active=False,
                        incurred_on=previous.incurred_on,
                        created_at=previous.created_at,
                        updated_at=previous.updated_at,
                    )
                )
            elif previous.id not in seen_ids:
                output.append(previous)
        return tuple(output)

    async def _validate_manual_expenses(
        self, purchase: Purchase, current: Retaceo, costs: tuple[RetaceoCost, ...]
    ) -> tuple[RetaceoCost, ...]:
        if self._orders is None:
            if any(
                cost.is_active and cost.classification is RetaceoCostClass.EXPENSE for cost in costs
            ):
                raise BusinessRuleError(
                    "El catálogo de gastos no está disponible.",
                    code="retaceo_expense_catalog_unavailable",
                )
            return costs
        # Serializes reservations of actual expenses across partial receipts.
        order = await self._orders.get_order_for_update(
            purchase.company_id, purchase.purchase_order_id
        )
        if order is None:
            raise NotFoundError("Orden no encontrada.", code="purchase_order_not_found")
        actuals = {
            row.id: row
            for row in await self._orders.list_actual_expenses(purchase.company_id, order.id)
        }
        usage = await self._orders.actual_expense_usage(
            purchase.company_id, tuple(actuals), exclude_retaceo_id=current.id
        )
        seen_sources: set[uuid.UUID] = set()
        output = []
        for cost in costs:
            if not cost.is_active:
                output.append(cost)
                continue
            if cost.classification is not RetaceoCostClass.EXPENSE:
                if (
                    cost.source_purchase_order_expense_id is not None
                    or cost.expense_type_id is not None
                ):
                    raise ValidationError(
                        "Registre flete, DAI e IVA solo en su componente fijo.",
                        code="retaceo_fixed_category_invalid",
                    )
                output.append(cost)
                continue
            await self._validate_extra_category(purchase.company_id, cost)
            source_id = cost.source_purchase_order_expense_id
            if source_id is not None:
                self._validate_actual_source(
                    cost, actuals.get(source_id), usage.get(source_id, Decimal("0")), seen_sources
                )
                seen_sources.add(source_id)
            output.append(await self._copy_actual_documents(purchase, current, cost))
        return tuple(output)

    async def _validate_extra_category(self, company_id: uuid.UUID, cost: RetaceoCost) -> None:
        category = (
            await self._orders.get_expense_type(company_id, cost.expense_type_id)
            if self._orders is not None and cost.expense_type_id
            else None
        )
        if category is None or not category.is_active or is_fixed_retaceo_category(category.name):
            raise ValidationError(
                "Seleccione una categoría activa de otros gastos; flete, DAI e IVA tienen campos propios.",
                code="retaceo_expense_category_invalid",
            )
        if not cost.description or not cost.description.strip() or cost.incurred_on is None:
            raise ValidationError(
                "Cada otro gasto requiere fecha y descripción.",
                code="retaceo_expense_detail_required",
            )

    @staticmethod
    def _validate_actual_source(
        cost: RetaceoCost,
        source: ActualPurchaseExpense | None,
        allocated: Decimal,
        seen_sources: set[uuid.UUID],
    ) -> None:
        if source is None or source.id in seen_sources:
            raise ValidationError(
                "Seleccione un gasto real de esta orden, sin repetirlo.",
                code="retaceo_actual_expense_invalid",
            )
        if source.expense_type_id != cost.expense_type_id or source.incurred_on != cost.incurred_on:
            raise ValidationError(
                "La categoría y fecha deben corresponder al gasto real relacionado.",
                code="retaceo_actual_expense_identity_mismatch",
            )
        if cost.amount + allocated > source.amount:
            raise BusinessRuleError(
                "El monto supera el saldo del gasto real; revise lo asignado a otras recepciones.",
                code="retaceo_actual_expense_exceeded",
            )

    async def _copy_actual_documents(
        self, purchase: Purchase, current: Retaceo, cost: RetaceoCost
    ) -> RetaceoCost:
        if (
            cost.source_purchase_order_expense_id is None
            or self._expense_documents is None
            or cost.documents
        ):
            return cost
        if any(row.id == cost.id for row in current.costs):
            return cost
        documents = await self._expense_documents.list_documents(
            purchase.company_id, purchase.purchase_order_id, cost.source_purchase_order_expense_id
        )
        return replace(
            cost,
            documents=tuple(
                RetaceoCostDocument(
                    id=uuid.uuid4(),
                    retaceo_cost_id=cost.id,
                    document_id=doc.document_id,
                    file_name=doc.file_name,
                    file_type=doc.file_type,
                    uploaded_at=doc.uploaded_at,
                )
                for doc in documents
                if doc.uploaded_at is not None
            ),
        )

    @staticmethod
    def _ensure_costs_calculable(retaceo: Retaceo) -> None:
        for cost in retaceo.costs:
            if not cost.is_active:
                continue
            if any(document.uploaded_at is None for document in cost.documents):
                raise BusinessRuleError(
                    f"Completa la carga del comprobante de «{cost.title}» o quítalo para calcular sin adjuntos.",
                    code="retaceo_cost_document_incomplete",
                )
            if cost.classification is RetaceoCostClass.IMPORT_VAT:
                if cost.allocations:
                    raise BusinessRuleError(
                        "El IVA de importación se conserva como dato informativo y no se distribuye.",
                        code="retaceo_import_vat_not_allocated",
                    )
                continue
            allocated = sum((allocation.amount for allocation in cost.allocations), Decimal("0"))
            if RetaceoUseCases._money(allocated) != RetaceoUseCases._money(cost.amount):
                raise BusinessRuleError(
                    f"La distribución manual de «{cost.title}» debe sumar exactamente su monto.",
                    code="retaceo_cost_allocation_incomplete",
                )

    def _receipt_sources(self, purchase: Purchase) -> tuple[RetaceoSourceLine, ...]:
        return tuple(
            RetaceoSourceLine(
                purchase_detail_id=detail.id,
                product_id=detail.product_id,
                unit_id=detail.unit_id,
                quantity=self._accepted_quantity(detail),
                cost_fob=self._accepted_fob(detail),
            )
            for detail in purchase.details
            if self._accepted_quantity(detail) > 0
        )

    def _automatic_amounts(
        self,
        purchase: Purchase,
        freight: Decimal,
        dai_rate: Decimal | None,
        vat_rate: Decimal | None,
    ) -> tuple[Decimal, Decimal]:
        try:
            return calculate_import_taxes(
                sum((row.cost_fob for row in self._receipt_sources(purchase)), Decimal("0")),
                freight,
                dai_rate,
                vat_rate,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), code="retaceo_calculation_invalid") from exc

    def _automatic_costs(
        self,
        purchase: Purchase,
        retaceo_id: uuid.UUID,
        costs: tuple[RetaceoCost, ...],
        freight: Decimal,
        dai: Decimal,
        vat: Decimal,
    ) -> tuple[RetaceoCost, ...]:
        fixed = {
            RetaceoCostClass.FREIGHT: freight,
            RetaceoCostClass.DAI: dai,
            RetaceoCostClass.IMPORT_VAT: vat,
        }
        output = [cost for cost in costs if cost.classification not in fixed or not cost.is_active]
        for generated in self._legacy_costs(
            retaceo_id=retaceo_id,
            total_freight=freight,
            total_expenses=Decimal("0"),
            total_dai=dai,
            import_vat=vat,
        ):
            matches = [
                cost
                for cost in costs
                if cost.classification is generated.classification and cost.is_active
            ]
            if len(matches) > 1:
                raise ValidationError(
                    "Evite duplicar los componentes fijos.", code="retaceo_fixed_amount_mismatch"
                )
            output.append(
                replace(matches[0], amount=generated.amount, allocations=())
                if matches
                else generated
            )
        for cost in costs:
            if cost.is_active and cost.classification in fixed and fixed[cost.classification] == 0:
                output.append(replace(cost, is_active=False))
        sources = self._receipt_sources(purchase)
        return tuple(self._distribute_automatic_expense(cost, sources) for cost in output)

    @staticmethod
    def _distribute_automatic_expense(
        cost: RetaceoCost, sources: tuple[RetaceoSourceLine, ...]
    ) -> RetaceoCost:
        if not cost.is_active or cost.classification is not RetaceoCostClass.EXPENSE:
            return cost
        allocation = calculate_retaceo_allocation(
            sources, total_freight=Decimal("0"), total_expenses=cost.amount, total_dai=Decimal("0")
        )
        return replace(
            cost,
            allocations=tuple(
                RetaceoCostAllocation(row.purchase_detail_id, row.expenses)
                for row in allocation.lines
            ),
        )
