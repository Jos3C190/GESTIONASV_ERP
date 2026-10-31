"""Application use cases for supplier purchase quotations and RFQ comparison."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.purchase_consolidation import (
    ConsolidationLine,
    PurchaseConsolidation,
    PurchaseConsolidationStatus,
)
from app.domain.entities.purchase_quotation import (
    PurchaseQuotation,
    PurchaseQuotationDetail,
    PurchaseQuotationExpense,
    PurchaseQuotationLineSnapshot,
    PurchaseQuotationRequest,
    PurchaseQuotationRequestDetail,
    PurchaseQuotationSourceSnapshot,
    PurchaseQuotationStatus,
    PurchaseQuotationTransitionError,
    ensure_purchase_quotation_transition,
)
from app.domain.entities.purchase_request import PurchaseRequestStatus
from app.domain.ports.purchase_quotation_repository import (
    PurchaseQuotationRepository,
    PurchaseQuotationRequestReference,
    PurchaseQuotationSupplierReference,
)

MONEY_QUANTUM = Decimal("0.000001")
QUOTABLE_REQUEST_STATUSES = frozenset(
    {
        PurchaseRequestStatus.APPROVED,
        PurchaseRequestStatus.PARTIALLY_QUOTED,
        PurchaseRequestStatus.QUOTED,
    }
)
COMPARABLE_QUOTATION_STATUSES = frozenset(
    {
        PurchaseQuotationStatus.RECEIVED,
        PurchaseQuotationStatus.UNDER_EVALUATION,
        PurchaseQuotationStatus.SELECTED,
    }
)


@dataclass(frozen=True, slots=True)
class PurchaseQuotationRequestLineDraft:
    purchase_request_detail_id: uuid.UUID
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class PurchaseQuotationRequestDraft:
    purchase_request_id: uuid.UUID
    lines: tuple[PurchaseQuotationRequestLineDraft, ...]


@dataclass(frozen=True, slots=True)
class PurchaseQuotationResponseLineDraft:
    product_id: int
    unit_id: int
    offered_quantity: Decimal
    unit_price: Decimal
    discount: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")
    delivery_days: int | None = None
    available_quantity: Decimal | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class PurchaseQuotationExpenseDraft:
    expense_type_id: uuid.UUID
    amount: Decimal
    description: str | None = None


@dataclass(frozen=True, slots=True)
class PurchaseQuotationComparisonRow:
    quotation_id: uuid.UUID
    code: str
    supplier_id: int
    currency: str
    total: Decimal
    delivery_days: int | None
    valid_until: datetime | None
    status: PurchaseQuotationStatus


class PurchaseQuotationUseCases:
    def __init__(self, repository: PurchaseQuotationRepository) -> None:
        self._repository = repository

    async def list_quotations(
        self,
        company_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
        status: PurchaseQuotationStatus | None = None,
        supplier_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseQuotation], int]:
        if branch_id is None:
            return await self._repository.list_quotations(
                company_id,
                status=status,
                supplier_id=supplier_id,
                skip=skip,
                limit=limit,
            )
        return await self._repository.list_quotations(
            company_id,
            branch_id=branch_id,
            status=status,
            supplier_id=supplier_id,
            skip=skip,
            limit=limit,
        )

    async def get_quotation(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
    ) -> PurchaseQuotation:
        if branch_id is None:
            quotation = await self._repository.get_quotation(company_id, quotation_id)
        else:
            quotation = await self._repository.get_quotation(
                company_id,
                quotation_id,
                branch_id=branch_id,
            )
        if quotation is None:
            raise NotFoundError(
                "Cotización de compra no encontrada.",
                code="purchase_quotation_not_found",
            )
        return quotation

    async def list_consolidation_quotations(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
    ) -> tuple[PurchaseQuotation, ...]:
        return await self._repository.list_consolidation_quotations(
            company_id,
            consolidation_id,
        )

    async def create_draft(
        self,
        *,
        company_id: uuid.UUID,
        created_by_id: uuid.UUID,
        supplier_id: int,
        currency: str,
        requests: tuple[PurchaseQuotationRequestDraft, ...],
        branch_id: uuid.UUID | None = None,
        notes: str | None = None,
    ) -> PurchaseQuotation:
        await self._validate_supplier(company_id, supplier_id)
        normalized_currency = currency.strip().upper()
        await self._validate_currency(normalized_currency)
        quotation_id = uuid.uuid4()
        request_links, quotation_details = await self._build_request_links(
            company_id,
            quotation_id,
            requests,
            branch_id=branch_id,
        )
        code = await self._repository.allocate_next_code(company_id)
        quotation = self._build_quotation(
            quotation_id=quotation_id,
            company_id=company_id,
            code=code,
            supplier_id=supplier_id,
            currency=normalized_currency,
            created_by_id=created_by_id,
            request_links=request_links,
            details=quotation_details,
            notes=notes,
        )
        return await self._repository.add_quotation(quotation)

    async def create_from_consolidation(
        self,
        *,
        company_id: uuid.UUID,
        created_by_id: uuid.UUID,
        consolidation: PurchaseConsolidation,
        supplier_id: int,
        currency: str,
        line_ids: tuple[uuid.UUID, ...],
        notes: str | None = None,
    ) -> PurchaseQuotation:
        if consolidation.company_id != company_id:
            raise NotFoundError(
                "Consolidado de compra no encontrado.",
                code="purchase_consolidation_not_found",
            )
        if consolidation.status is PurchaseConsolidationStatus.CANCELLED:
            raise BusinessRuleError(
                "No se puede preparar una RFQ desde un consolidado cancelado.",
                code="purchase_quotation_consolidation_cancelled",
            )
        if consolidation.status is PurchaseConsolidationStatus.CLOSED:
            raise BusinessRuleError(
                "No se puede preparar una RFQ desde un consolidado cerrado.",
                code="purchase_quotation_consolidation_closed",
            )
        await self._validate_supplier(company_id, supplier_id)
        normalized_currency = currency.strip().upper()
        await self._validate_currency(normalized_currency)
        selected_lines = self._select_consolidation_lines(consolidation, line_ids)
        requests = self._build_consolidation_request_drafts(selected_lines)

        quotation_id = uuid.uuid4()
        request_links: tuple[PurchaseQuotationRequest, ...] = ()
        branch_details: tuple[PurchaseQuotationDetail, ...] = ()
        if requests:
            request_links, branch_details = await self._build_request_links(
                company_id,
                quotation_id,
                requests,
            )
        details, snapshots = self._build_consolidation_quote_lines(
            quotation_id,
            selected_lines,
            branch_details,
        )

        code = await self._repository.allocate_next_code(company_id)
        version_number = await self._repository.allocate_next_consolidation_version(
            company_id,
            consolidation.id,
            supplier_id,
        )
        quotation = self._build_quotation(
            quotation_id=quotation_id,
            company_id=company_id,
            code=code,
            supplier_id=supplier_id,
            currency=normalized_currency,
            created_by_id=created_by_id,
            request_links=request_links,
            details=details,
            notes=notes,
            consolidation_id=consolidation.id,
            consolidation_code=consolidation.code,
            version_number=version_number,
            snapshots=snapshots,
        )
        return await self._repository.add_quotation(quotation)

    @staticmethod
    def _select_consolidation_lines(
        consolidation: PurchaseConsolidation,
        line_ids: tuple[uuid.UUID, ...],
    ) -> tuple[ConsolidationLine, ...]:
        if not line_ids:
            raise ValidationError(
                "Selecciona al menos un producto para solicitar precio.",
                code="purchase_quotation_consolidation_lines_required",
            )
        if len(line_ids) != len(set(line_ids)):
            raise ValidationError(
                "No repitas productos en la misma RFQ.",
                code="purchase_quotation_consolidation_duplicate_line",
            )

        line_map = {line.id: line for line in consolidation.lines}
        selected: list[ConsolidationLine] = []
        for line_id in line_ids:
            line = line_map.get(line_id)
            if line is None:
                raise NotFoundError(
                    "Una línea seleccionada no pertenece al consolidado.",
                    code="purchase_quotation_consolidation_line_not_found",
                )
            if line.total_quantity <= 0:
                raise ValidationError(
                    f"{line.product_name} no tiene cantidad vigente para solicitar precio.",
                    code="purchase_quotation_consolidation_line_empty",
                )
            selected.append(line)
        return tuple(selected)

    @staticmethod
    def _build_consolidation_request_drafts(
        selected_lines: tuple[ConsolidationLine, ...],
    ) -> tuple[PurchaseQuotationRequestDraft, ...]:
        request_lines: dict[uuid.UUID, list[PurchaseQuotationRequestLineDraft]] = {}
        for line in selected_lines:
            for source in line.sources:
                if source.included_quantity > 0:
                    request_lines.setdefault(source.purchase_request_id, []).append(
                        PurchaseQuotationRequestLineDraft(
                            purchase_request_detail_id=source.purchase_request_detail_id,
                            quantity=source.included_quantity,
                        )
                    )
        return tuple(
            PurchaseQuotationRequestDraft(purchase_request_id=request_id, lines=tuple(lines))
            for request_id, lines in request_lines.items()
        )

    @staticmethod
    def _build_consolidation_quote_lines(
        quotation_id: uuid.UUID,
        selected_lines: tuple[ConsolidationLine, ...],
        branch_details: tuple[PurchaseQuotationDetail, ...],
    ) -> tuple[tuple[PurchaseQuotationDetail, ...], tuple[PurchaseQuotationLineSnapshot, ...]]:
        detail_ids_by_product_unit = {
            (detail.product_id, detail.unit_id): detail.id for detail in branch_details
        }
        details: list[PurchaseQuotationDetail] = []
        snapshots: list[PurchaseQuotationLineSnapshot] = []
        for line in selected_lines:
            detail_id = detail_ids_by_product_unit.get((line.product_id, line.unit_id))
            if detail_id is None:
                detail_id = uuid.uuid4()
            details.append(
                PurchaseQuotationDetail(
                    id=detail_id,
                    purchase_quotation_id=quotation_id,
                    product_id=line.product_id,
                    unit_id=line.unit_id,
                    quantity=line.total_quantity,
                    unit_price=Decimal("0"),
                )
            )
            snapshots.append(
                PurchaseQuotationLineSnapshot(
                    purchase_quotation_detail_id=detail_id,
                    consolidation_line_id=line.id,
                    product_sku=line.product_sku,
                    product_name=line.product_name,
                    unit_name=line.unit_name,
                    branch_quantity=line.branch_quantity,
                    central_quantity=line.central_quantity,
                    sources=tuple(
                        PurchaseQuotationSourceSnapshot(
                            purchase_request_id=source.purchase_request_id,
                            purchase_request_detail_id=source.purchase_request_detail_id,
                            request_code=source.request_code,
                            branch_name=source.branch_name,
                            warehouse_name=source.warehouse_name,
                            requester_name=source.requester_name,
                            required_date=source.required_date,
                            included_quantity=source.included_quantity,
                        )
                        for source in line.sources
                        if source.included_quantity > 0
                    ),
                )
            )
        return tuple(details), tuple(snapshots)

    async def send_request(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> PurchaseQuotation:
        return await self._transition(company_id, quotation_id, PurchaseQuotationStatus.REQUESTED)

    async def start_evaluation(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> PurchaseQuotation:
        return await self._transition(
            company_id,
            quotation_id,
            PurchaseQuotationStatus.UNDER_EVALUATION,
        )

    async def reject_offer(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> PurchaseQuotation:
        return await self._transition(company_id, quotation_id, PurchaseQuotationStatus.REJECTED)

    async def cancel_quotation(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> PurchaseQuotation:
        return await self._transition(company_id, quotation_id, PurchaseQuotationStatus.CANCELLED)

    async def record_response(
        self,
        *,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        quotation_date: datetime,
        lines: tuple[PurchaseQuotationResponseLineDraft, ...],
        valid_until: datetime | None = None,
        payment_terms: str | None = None,
        delivery_days: int | None = None,
        expenses: tuple[PurchaseQuotationExpenseDraft, ...] = (),
        notes: str | None = None,
    ) -> PurchaseQuotation:
        current = await self._get_for_update(company_id, quotation_id)
        self._ensure_transition(current.status, PurchaseQuotationStatus.RECEIVED)
        details = self._build_response_details(quotation_id, current.details, lines)
        expense_entities = await self._build_expenses(company_id, quotation_id, expenses)
        subtotal = self._money(sum((detail.subtotal for detail in details), Decimal("0")))
        discount = self._money(sum((detail.discount for detail in details), Decimal("0")))
        tax = self._money(sum((detail.tax_amount for detail in details), Decimal("0")))
        expenses_total = self._money(
            sum((expense.amount for expense in expense_entities), Decimal("0"))
        )
        total = self._money(
            sum((detail.total for detail in details), Decimal("0")) + expenses_total
        )
        replacement = self._build_received_quotation(
            current=current,
            quotation_date=quotation_date,
            valid_until=valid_until,
            payment_terms=payment_terms,
            delivery_days=delivery_days,
            details=details,
            expenses=expense_entities,
            subtotal=subtotal,
            discount=discount,
            tax=tax,
            total=total,
            response_notes=notes,
        )
        saved = await self._repository.replace_response(replacement)
        if saved is None:
            raise NotFoundError(
                "Cotización de compra no encontrada.",
                code="purchase_quotation_not_found",
            )
        if saved.consolidation_id is None:
            request_ids = tuple(link.purchase_request_id for link in saved.request_links)
            await self._repository.advance_purchase_request_quotation_statuses(
                company_id,
                request_ids,
            )
        return saved

    async def compare_offers(
        self,
        company_id: uuid.UUID,
        purchase_request_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
        currency: str | None = None,
        now: datetime | None = None,
    ) -> tuple[PurchaseQuotationComparisonRow, ...]:
        if branch_id is None:
            quotations = await self._repository.list_comparable(company_id, purchase_request_id)
        else:
            quotations = await self._repository.list_comparable(
                company_id,
                purchase_request_id,
                branch_id=branch_id,
            )
        instant = now or datetime.now(UTC)
        active = [quotation for quotation in quotations if self._is_comparable(quotation, instant)]
        active = [quotation for quotation in active if quotation.consolidation_id is None]
        active = [
            quotation
            for quotation in active
            if any(
                detail.offered_quantity is None or detail.offered_quantity > 0
                for detail in quotation.details
            )
        ]
        filtered = self._filter_comparison_currency(active, currency)
        return tuple(
            PurchaseQuotationComparisonRow(
                quotation_id=quotation.id,
                code=quotation.code,
                supplier_id=quotation.supplier_id,
                currency=quotation.currency,
                total=quotation.total,
                delivery_days=quotation.delivery_days,
                valid_until=quotation.valid_until,
                status=quotation.status,
            )
            for quotation in sorted(filtered, key=self._comparison_key)
        )

    async def select_offer(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> PurchaseQuotation:
        current = await self._get_for_update(company_id, quotation_id)
        if current.consolidation_id is not None:
            raise BusinessRuleError(
                "Las RFQ de un consolidado se adjudican por producto en el flujo de compras.",
                code="purchase_quotation_requires_line_adjudication",
            )
        instant = now or datetime.now(UTC)
        if not any(
            detail.offered_quantity is None or detail.offered_quantity > 0
            for detail in current.details
        ):
            raise BusinessRuleError(
                "No se puede seleccionar una cotización sin cantidades ofrecidas.",
                code="purchase_quotation_offer_empty",
            )
        if current.valid_until is not None and current.valid_until < instant:
            raise BusinessRuleError(
                "No se puede seleccionar una cotización vencida.",
                code="purchase_quotation_expired",
            )
        return await self._transition_loaded(
            company_id,
            current,
            PurchaseQuotationStatus.SELECTED,
        )

    async def _validate_supplier(self, company_id: uuid.UUID, supplier_id: int) -> None:
        reference = await self._repository.get_supplier_reference(company_id, supplier_id)
        reference = self._require_supplier(reference)
        if not reference.is_active or reference.supplier_status != "approved":
            raise BusinessRuleError(
                "El proveedor no está habilitado para recibir solicitudes de cotización.",
                code="purchase_quotation_supplier_unavailable",
            )

    async def _validate_currency(self, currency: str) -> None:
        if not await self._repository.is_currency_active(currency):
            raise ValidationError(
                "La moneda indicada no existe o está inactiva.",
                code="purchase_quotation_currency_invalid",
            )

    async def _build_request_links(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        requests: tuple[PurchaseQuotationRequestDraft, ...],
        *,
        branch_id: uuid.UUID | None = None,
    ) -> tuple[tuple[PurchaseQuotationRequest, ...], tuple[PurchaseQuotationDetail, ...]]:
        if not requests:
            raise ValidationError(
                "La cotización debe vincular al menos una solicitud de compra.",
                code="purchase_quotation_requests_required",
            )
        request_ids = [item.purchase_request_id for item in requests]
        if len(request_ids) != len(set(request_ids)):
            raise ValidationError(
                "Una solicitud de compra no puede repetirse en la misma cotización.",
                code="purchase_quotation_duplicate_request",
            )
        links: list[PurchaseQuotationRequest] = []
        quotation_detail_ids: dict[tuple[int, int], uuid.UUID] = {}
        quotation_detail_quantities: dict[tuple[int, int], Decimal] = {}
        for draft in requests:
            reference = await self._repository.get_request_reference(
                company_id,
                draft.purchase_request_id,
            )
            reference = self._require_request(reference)
            if branch_id is not None and reference.branch_id != branch_id:
                raise NotFoundError(
                    "Solicitud de compra no encontrada.",
                    code="purchase_quotation_request_not_found",
                )
            self._ensure_request_quotable(reference)
            links.append(
                self._build_request_link(
                    quotation_id,
                    reference,
                    draft,
                    quotation_detail_ids,
                    quotation_detail_quantities,
                )
            )
        details = tuple(
            PurchaseQuotationDetail(
                id=quotation_detail_ids[key],
                purchase_quotation_id=quotation_id,
                product_id=key[0],
                unit_id=key[1],
                quantity=quantity,
                unit_price=Decimal("0"),
            )
            for key, quantity in quotation_detail_quantities.items()
        )
        return tuple(links), details

    @staticmethod
    def _build_request_link(
        quotation_id: uuid.UUID,
        reference: PurchaseQuotationRequestReference,
        draft: PurchaseQuotationRequestDraft,
        quotation_detail_ids: dict[tuple[int, int], uuid.UUID],
        quotation_detail_quantities: dict[tuple[int, int], Decimal],
    ) -> PurchaseQuotationRequest:
        if not draft.lines:
            raise ValidationError(
                "Cada solicitud vinculada debe incluir al menos un detalle para cotizar.",
                code="purchase_quotation_request_details_required",
            )
        detail_map = {detail.id: detail for detail in reference.details}
        detail_ids = [line.purchase_request_detail_id for line in draft.lines]
        if len(detail_ids) != len(set(detail_ids)):
            raise ValidationError(
                "Un detalle de solicitud no puede repetirse en la misma cotización.",
                code="purchase_quotation_duplicate_request_detail",
            )
        link_id = uuid.uuid4()
        details: list[PurchaseQuotationRequestDetail] = []
        for line in draft.lines:
            source = detail_map.get(line.purchase_request_detail_id)
            if source is None:
                raise ValidationError(
                    "El detalle indicado no pertenece a la solicitud de compra.",
                    code="purchase_quotation_request_detail_invalid",
                )
            if line.quantity > source.quantity:
                raise ValidationError(
                    "La cantidad solicitada para cotizar supera la cantidad de la solicitud.",
                    code="purchase_quotation_request_quantity_exceeded",
                )
            key = (source.product_id, source.unit_id)
            purchase_quotation_detail_id = quotation_detail_ids.setdefault(key, uuid.uuid4())
            quotation_detail_quantities[key] = (
                quotation_detail_quantities.get(key, Decimal("0")) + line.quantity
            )
            try:
                details.append(
                    PurchaseQuotationRequestDetail(
                        id=uuid.uuid4(),
                        purchase_quotation_request_id=link_id,
                        purchase_request_detail_id=source.id,
                        quantity=line.quantity,
                        purchase_quotation_detail_id=purchase_quotation_detail_id,
                    )
                )
            except ValueError as exc:
                raise ValidationError(
                    str(exc),
                    code="purchase_quotation_request_quantity_invalid",
                ) from exc
        return PurchaseQuotationRequest(
            id=link_id,
            purchase_quotation_id=quotation_id,
            purchase_request_id=reference.id,
            details=tuple(details),
        )

    def _build_response_details(
        self,
        quotation_id: uuid.UUID,
        requested_details: tuple[PurchaseQuotationDetail, ...],
        lines: tuple[PurchaseQuotationResponseLineDraft, ...],
    ) -> tuple[PurchaseQuotationDetail, ...]:
        allowed = {(detail.product_id, detail.unit_id): detail for detail in requested_details}
        keys = [(line.product_id, line.unit_id) for line in lines]
        if len(keys) != len(set(keys)):
            raise ValidationError(
                "Un producto y unidad no pueden repetirse en la respuesta.",
                code="purchase_quotation_duplicate_response_detail",
            )
        for key in keys:
            if key not in allowed:
                raise ValidationError(
                    "La respuesta contiene un producto o unidad fuera del alcance solicitado.",
                    code="purchase_quotation_response_out_of_scope",
                )
        received_by_key = {(line.product_id, line.unit_id): line for line in lines}
        details: list[PurchaseQuotationDetail] = []
        for requested in requested_details:
            key = (requested.product_id, requested.unit_id)
            response = received_by_key.get(key)
            offered_quantity = response.offered_quantity if response is not None else Decimal("0")
            if offered_quantity > requested.quantity:
                raise ValidationError(
                    "La cantidad cotizada supera la cantidad solicitada al proveedor.",
                    code="purchase_quotation_response_quantity_exceeded",
                )
            details.append(
                self._build_response_detail(
                    quotation_id,
                    requested,
                    response,
                )
            )
        return tuple(details)

    def _build_response_detail(
        self,
        quotation_id: uuid.UUID,
        requested: PurchaseQuotationDetail,
        response: PurchaseQuotationResponseLineDraft | None,
    ) -> PurchaseQuotationDetail:
        offered_quantity = response.offered_quantity if response is not None else Decimal("0")
        unit_price = response.unit_price if response is not None else Decimal("0")
        discount = response.discount if response is not None else Decimal("0")
        tax_rate = response.tax_rate if response is not None else Decimal("0")
        subtotal = self._money(offered_quantity * unit_price)
        discounted_base = subtotal - discount
        tax_amount = self._money(discounted_base * tax_rate / Decimal("100"))
        total = self._money(discounted_base + tax_amount)
        try:
            return PurchaseQuotationDetail(
                id=requested.id,
                purchase_quotation_id=quotation_id,
                product_id=requested.product_id,
                unit_id=requested.unit_id,
                quantity=requested.quantity,
                unit_price=self._money(unit_price),
                discount=self._money(discount),
                subtotal=subtotal,
                tax_rate=self._money(tax_rate),
                tax_amount=tax_amount,
                total=total,
                delivery_days=response.delivery_days if response is not None else None,
                available_quantity=(response.available_quantity if response is not None else None),
                notes=response.notes if response is not None else None,
                offered_quantity=offered_quantity,
            )
        except ValueError as exc:
            raise ValidationError(
                str(exc),
                code="purchase_quotation_response_detail_invalid",
            ) from exc

    async def _build_expenses(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        expenses: tuple[PurchaseQuotationExpenseDraft, ...],
    ) -> tuple[PurchaseQuotationExpense, ...]:
        expense_type_ids = [expense.expense_type_id for expense in expenses]
        if len(expense_type_ids) != len(set(expense_type_ids)):
            raise ValidationError(
                "Un tipo de gasto no puede repetirse en la misma cotización.",
                code="purchase_quotation_duplicate_expense_type",
            )
        built: list[PurchaseQuotationExpense] = []
        for expense in expenses:
            if not await self._repository.is_expense_type_active(
                company_id,
                expense.expense_type_id,
            ):
                raise ValidationError(
                    "El tipo de gasto indicado no existe o está inactivo.",
                    code="purchase_quotation_expense_type_invalid",
                )
            try:
                built.append(
                    PurchaseQuotationExpense(
                        id=uuid.uuid4(),
                        purchase_quotation_id=quotation_id,
                        expense_type_id=expense.expense_type_id,
                        amount=self._money(expense.amount),
                        description=expense.description,
                    )
                )
            except ValueError as exc:
                raise ValidationError(
                    str(exc),
                    code="purchase_quotation_expense_invalid",
                ) from exc
        return tuple(built)

    async def _get_for_update(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> PurchaseQuotation:
        quotation = await self._repository.get_quotation_for_update(company_id, quotation_id)
        if quotation is None:
            raise NotFoundError(
                "Cotización de compra no encontrada.",
                code="purchase_quotation_not_found",
            )
        return quotation

    async def _transition(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        target: PurchaseQuotationStatus,
    ) -> PurchaseQuotation:
        current = await self._get_for_update(company_id, quotation_id)
        return await self._transition_loaded(company_id, current, target)

    async def _transition_loaded(
        self,
        company_id: uuid.UUID,
        current: PurchaseQuotation,
        target: PurchaseQuotationStatus,
    ) -> PurchaseQuotation:
        self._ensure_transition(current.status, target)
        updated = await self._repository.update_status(company_id, current.id, target)
        if updated is None:
            raise NotFoundError(
                "Cotización de compra no encontrada.",
                code="purchase_quotation_not_found",
            )
        return updated

    @staticmethod
    def _ensure_transition(
        current: PurchaseQuotationStatus,
        target: PurchaseQuotationStatus,
    ) -> None:
        try:
            ensure_purchase_quotation_transition(current, target)
        except PurchaseQuotationTransitionError as exc:
            raise BusinessRuleError(
                "La transición solicitada no es válida para el estado actual de la cotización.",
                code="purchase_quotation_invalid_transition",
            ) from exc

    @staticmethod
    def _require_supplier(
        reference: PurchaseQuotationSupplierReference | None,
    ) -> PurchaseQuotationSupplierReference:
        if reference is None:
            raise NotFoundError(
                "Proveedor no encontrado.",
                code="purchase_quotation_supplier_not_found",
            )
        return reference

    @staticmethod
    def _require_request(
        reference: PurchaseQuotationRequestReference | None,
    ) -> PurchaseQuotationRequestReference:
        if reference is None:
            raise NotFoundError(
                "Solicitud de compra no encontrada.",
                code="purchase_quotation_request_not_found",
            )
        return reference

    @staticmethod
    def _ensure_request_quotable(reference: PurchaseQuotationRequestReference) -> None:
        if reference.status not in QUOTABLE_REQUEST_STATUSES:
            raise BusinessRuleError(
                "Solo las solicitudes aprobadas pueden enviarse a cotización.",
                code="purchase_quotation_request_not_quotable",
            )

    @staticmethod
    def _build_quotation(
        *,
        quotation_id: uuid.UUID,
        company_id: uuid.UUID,
        code: str,
        supplier_id: int,
        currency: str,
        created_by_id: uuid.UUID,
        request_links: tuple[PurchaseQuotationRequest, ...],
        details: tuple[PurchaseQuotationDetail, ...],
        notes: str | None,
        consolidation_id: uuid.UUID | None = None,
        consolidation_code: str | None = None,
        version_number: int = 1,
        snapshots: tuple[PurchaseQuotationLineSnapshot, ...] = (),
    ) -> PurchaseQuotation:
        try:
            return PurchaseQuotation(
                id=quotation_id,
                company_id=company_id,
                code=code,
                supplier_id=supplier_id,
                quotation_date=datetime.now(UTC),
                currency=currency,
                created_by_id=created_by_id,
                request_links=request_links,
                details=details,
                notes=notes,
                consolidation_id=consolidation_id,
                consolidation_code=consolidation_code,
                version_number=version_number,
                snapshots=snapshots,
            )
        except ValueError as exc:
            raise ValidationError(
                str(exc),
                code="purchase_quotation_invalid",
            ) from exc

    @staticmethod
    def _build_received_quotation(
        *,
        current: PurchaseQuotation,
        quotation_date: datetime,
        valid_until: datetime | None,
        payment_terms: str | None,
        delivery_days: int | None,
        details: tuple[PurchaseQuotationDetail, ...],
        expenses: tuple[PurchaseQuotationExpense, ...],
        subtotal: Decimal,
        discount: Decimal,
        tax: Decimal,
        total: Decimal,
        response_notes: str | None,
    ) -> PurchaseQuotation:
        try:
            return PurchaseQuotation(
                id=current.id,
                company_id=current.company_id,
                code=current.code,
                supplier_id=current.supplier_id,
                quotation_date=quotation_date,
                currency=current.currency,
                created_by_id=current.created_by_id,
                request_links=current.request_links,
                details=details,
                expenses=expenses,
                valid_until=valid_until,
                payment_terms=payment_terms,
                delivery_days=delivery_days,
                subtotal=subtotal,
                discount=discount,
                tax=tax,
                total=total,
                status=PurchaseQuotationStatus.RECEIVED,
                notes=current.notes,
                created_at=current.created_at,
                updated_at=current.updated_at,
                consolidation_id=current.consolidation_id,
                consolidation_code=current.consolidation_code,
                version_number=current.version_number,
                sent_at=current.sent_at,
                response_notes=response_notes,
                snapshots=current.snapshots,
            )
        except ValueError as exc:
            raise ValidationError(
                str(exc),
                code="purchase_quotation_response_invalid",
            ) from exc

    @staticmethod
    def _is_comparable(quotation: PurchaseQuotation, now: datetime) -> bool:
        if quotation.status not in COMPARABLE_QUOTATION_STATUSES:
            return False
        return quotation.valid_until is None or quotation.valid_until >= now

    @staticmethod
    def _filter_comparison_currency(
        quotations: list[PurchaseQuotation],
        currency: str | None,
    ) -> list[PurchaseQuotation]:
        if currency is not None:
            normalized = currency.strip().upper()
            return [quotation for quotation in quotations if quotation.currency == normalized]
        currencies = {quotation.currency for quotation in quotations}
        if len(currencies) > 1:
            raise BusinessRuleError(
                "No se pueden comparar importes de cotizaciones en monedas distintas "
                "sin conversión.",
                code="purchase_quotation_currency_mismatch",
            )
        return quotations

    @staticmethod
    def _comparison_key(quotation: PurchaseQuotation) -> tuple[Decimal, int, str]:
        delivery_days = quotation.delivery_days if quotation.delivery_days is not None else 10**9
        return quotation.total, delivery_days, quotation.code

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValidationError(
                "Los importes de la cotización deben ser números finitos.",
                code="purchase_quotation_amount_invalid",
            )
        return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
