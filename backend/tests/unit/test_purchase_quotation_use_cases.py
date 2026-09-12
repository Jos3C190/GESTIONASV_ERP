from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.application.purchase_quotations.use_cases import (
    PurchaseQuotationExpenseDraft,
    PurchaseQuotationRequestDraft,
    PurchaseQuotationRequestLineDraft,
    PurchaseQuotationResponseLineDraft,
    PurchaseQuotationUseCases,
)
from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.purchase_quotation import (
    PurchaseQuotation,
    PurchaseQuotationDetail,
    PurchaseQuotationRequest,
    PurchaseQuotationRequestDetail,
    PurchaseQuotationStatus,
)
from app.domain.entities.purchase_request import PurchaseRequestStatus
from app.domain.ports.purchase_quotation_repository import (
    PurchaseQuotationCoverageReference,
    PurchaseQuotationRequestDetailReference,
    PurchaseQuotationRequestReference,
    PurchaseQuotationSupplierReference,
)


class FakePurchaseQuotationRepository:
    def __init__(self) -> None:
        self.quotations: dict[tuple[uuid.UUID, uuid.UUID], PurchaseQuotation] = {}
        self.suppliers: dict[tuple[uuid.UUID, int], PurchaseQuotationSupplierReference] = {}
        self.currencies = {"USD"}
        self.requests: dict[tuple[uuid.UUID, uuid.UUID], PurchaseQuotationRequestReference] = {}
        self.coverage: dict[
            tuple[uuid.UUID, uuid.UUID], tuple[PurchaseQuotationCoverageReference, ...]
        ] = {}
        self.active_expense_types: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.advanced: list[tuple[uuid.UUID, tuple[uuid.UUID, ...]]] = []
        self.comparable: dict[tuple[uuid.UUID, uuid.UUID], list[PurchaseQuotation]] = {}
        self.next_number = 1

    async def list_quotations(self, company_id, *, status=None, supplier_id=None, skip=0, limit=50):
        values = [
            quotation
            for (tenant, _), quotation in self.quotations.items()
            if tenant == company_id
            and (status is None or quotation.status is status)
            and (supplier_id is None or quotation.supplier_id == supplier_id)
        ]
        return values[skip : skip + limit], len(values)

    async def get_quotation(self, company_id, quotation_id):
        return self.quotations.get((company_id, quotation_id))

    async def get_quotation_for_update(self, company_id, quotation_id):
        return self.quotations.get((company_id, quotation_id))

    async def allocate_next_code(self, company_id):
        code = f"COT-{self.next_number:05d}"
        self.next_number += 1
        return code

    async def get_supplier_reference(self, company_id, supplier_id):
        return self.suppliers.get((company_id, supplier_id))

    async def is_currency_active(self, currency):
        return currency in self.currencies

    async def get_request_reference(self, company_id, request_id):
        return self.requests.get((company_id, request_id))

    async def is_expense_type_active(self, company_id, expense_type_id):
        return (company_id, expense_type_id) in self.active_expense_types

    async def get_coverage_references(self, company_id, quotation_id):
        return self.coverage.get((company_id, quotation_id), ())

    async def add_quotation(self, quotation):
        self.quotations[(quotation.company_id, quotation.id)] = quotation
        return quotation

    async def replace_response(self, quotation):
        key = (quotation.company_id, quotation.id)
        if key not in self.quotations:
            return None
        self.quotations[key] = quotation
        return quotation

    async def update_status(self, company_id, quotation_id, status):
        current = self.quotations.get((company_id, quotation_id))
        if current is None:
            return None
        updated = replace(current, status=status)
        self.quotations[(company_id, quotation_id)] = updated
        return updated

    async def list_comparable(self, company_id, purchase_request_id):
        return self.comparable.get((company_id, purchase_request_id), [])

    async def advance_purchase_request_quotation_statuses(self, company_id, request_ids):
        self.advanced.append((company_id, request_ids))


def _setup_repository() -> tuple[
    FakePurchaseQuotationRepository,
    uuid.UUID,
    uuid.UUID,
    uuid.UUID,
    uuid.UUID,
]:
    repository = FakePurchaseQuotationRepository()
    company_id = uuid.uuid4()
    request_id = uuid.uuid4()
    request_detail_id = uuid.uuid4()
    expense_type_id = uuid.uuid4()
    repository.suppliers[(company_id, 7)] = PurchaseQuotationSupplierReference(
        supplier_id=7,
        is_active=True,
        supplier_status="approved",
    )
    repository.requests[(company_id, request_id)] = PurchaseQuotationRequestReference(
        id=request_id,
        status=PurchaseRequestStatus.APPROVED,
        details=(
            PurchaseQuotationRequestDetailReference(
                id=request_detail_id,
                product_id=11,
                unit_id=3,
                quantity=Decimal("5"),
            ),
        ),
    )
    repository.active_expense_types.add((company_id, expense_type_id))
    return repository, company_id, request_id, request_detail_id, expense_type_id


async def _create_requested(
    repository: FakePurchaseQuotationRepository,
    company_id: uuid.UUID,
    request_id: uuid.UUID,
    request_detail_id: uuid.UUID,
) -> PurchaseQuotation:
    use_cases = PurchaseQuotationUseCases(repository)
    quotation = await use_cases.create_draft(
        company_id=company_id,
        created_by_id=uuid.uuid4(),
        supplier_id=7,
        currency="usd",
        requests=(
            PurchaseQuotationRequestDraft(
                purchase_request_id=request_id,
                lines=(
                    PurchaseQuotationRequestLineDraft(
                        purchase_request_detail_id=request_detail_id,
                        quantity=Decimal("5"),
                    ),
                ),
            ),
        ),
    )
    quotation_detail_id = quotation.request_links[0].details[0].purchase_quotation_detail_id
    assert quotation_detail_id is not None
    repository.coverage[(company_id, quotation.id)] = (
        PurchaseQuotationCoverageReference(
            purchase_request_id=request_id,
            purchase_quotation_detail_id=quotation_detail_id,
            purchase_request_detail_id=request_detail_id,
            product_id=11,
            unit_id=3,
            quantity=Decimal("5"),
        ),
    )
    return await use_cases.send_request(company_id, quotation.id)


@pytest.mark.asyncio
async def test_create_draft_validates_scope_and_normalizes_currency() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()
    use_cases = PurchaseQuotationUseCases(repository)

    quotation = await use_cases.create_draft(
        company_id=company_id,
        created_by_id=uuid.uuid4(),
        supplier_id=7,
        currency=" usd ",
        requests=(
            PurchaseQuotationRequestDraft(
                purchase_request_id=request_id,
                lines=(
                    PurchaseQuotationRequestLineDraft(
                        purchase_request_detail_id=request_detail_id,
                        quantity=Decimal("2"),
                    ),
                ),
            ),
        ),
    )

    assert quotation.code == "COT-00001"
    assert quotation.currency == "USD"
    assert quotation.status is PurchaseQuotationStatus.DRAFT
    assert quotation.request_links[0].details[0].quantity == Decimal("2")
    assert len(quotation.details) == 1
    trace = quotation.request_links[0].details[0]
    assert trace.purchase_quotation_detail_id == quotation.details[0].id
    assert quotation.details[0].quantity == Decimal("2")


@pytest.mark.asyncio
async def test_create_draft_rejects_unavailable_supplier() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()
    repository.suppliers[(company_id, 7)] = PurchaseQuotationSupplierReference(
        supplier_id=7,
        is_active=True,
        supplier_status="on_hold",
    )

    with pytest.raises(BusinessRuleError, match="proveedor") as exc_info:
        await PurchaseQuotationUseCases(repository).create_draft(
            company_id=company_id,
            created_by_id=uuid.uuid4(),
            supplier_id=7,
            currency="USD",
            requests=(
                PurchaseQuotationRequestDraft(
                    purchase_request_id=request_id,
                    lines=(
                        PurchaseQuotationRequestLineDraft(
                            purchase_request_detail_id=request_detail_id,
                            quantity=Decimal("1"),
                        ),
                    ),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_quotation_supplier_unavailable"


@pytest.mark.asyncio
async def test_create_draft_rejects_unknown_supplier() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()
    repository.suppliers.clear()

    with pytest.raises(NotFoundError) as exc_info:
        await PurchaseQuotationUseCases(repository).create_draft(
            company_id=company_id,
            created_by_id=uuid.uuid4(),
            supplier_id=99,
            currency="USD",
            requests=(
                PurchaseQuotationRequestDraft(
                    purchase_request_id=request_id,
                    lines=(
                        PurchaseQuotationRequestLineDraft(
                            purchase_request_detail_id=request_detail_id,
                            quantity=Decimal("1"),
                        ),
                    ),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_quotation_supplier_not_found"


@pytest.mark.asyncio
async def test_create_draft_rejects_inactive_currency() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()
    repository.currencies.clear()

    with pytest.raises(ValidationError) as exc_info:
        await PurchaseQuotationUseCases(repository).create_draft(
            company_id=company_id,
            created_by_id=uuid.uuid4(),
            supplier_id=7,
            currency="USD",
            requests=(
                PurchaseQuotationRequestDraft(
                    purchase_request_id=request_id,
                    lines=(
                        PurchaseQuotationRequestLineDraft(
                            purchase_request_detail_id=request_detail_id,
                            quantity=Decimal("1"),
                        ),
                    ),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_quotation_currency_invalid"


@pytest.mark.asyncio
async def test_create_draft_requires_approved_request() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()
    current = repository.requests[(company_id, request_id)]
    repository.requests[(company_id, request_id)] = replace(
        current,
        status=PurchaseRequestStatus.SUBMITTED,
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        await PurchaseQuotationUseCases(repository).create_draft(
            company_id=company_id,
            created_by_id=uuid.uuid4(),
            supplier_id=7,
            currency="USD",
            requests=(
                PurchaseQuotationRequestDraft(
                    purchase_request_id=request_id,
                    lines=(
                        PurchaseQuotationRequestLineDraft(
                            purchase_request_detail_id=request_detail_id,
                            quantity=Decimal("1"),
                        ),
                    ),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_quotation_request_not_quotable"


@pytest.mark.asyncio
async def test_create_draft_rejects_excess_request_quantity() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()

    with pytest.raises(ValidationError) as exc_info:
        await PurchaseQuotationUseCases(repository).create_draft(
            company_id=company_id,
            created_by_id=uuid.uuid4(),
            supplier_id=7,
            currency="USD",
            requests=(
                PurchaseQuotationRequestDraft(
                    purchase_request_id=request_id,
                    lines=(
                        PurchaseQuotationRequestLineDraft(
                            purchase_request_detail_id=request_detail_id,
                            quantity=Decimal("6"),
                        ),
                    ),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_quotation_request_quantity_exceeded"


@pytest.mark.asyncio
async def test_send_request_moves_draft_to_requested() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()
    requested = await _create_requested(repository, company_id, request_id, request_detail_id)

    assert requested.status is PurchaseQuotationStatus.REQUESTED


@pytest.mark.asyncio
async def test_record_response_calculates_totals_and_advances_requests() -> None:
    repository, company_id, request_id, request_detail_id, expense_type_id = _setup_repository()
    requested = await _create_requested(repository, company_id, request_id, request_detail_id)
    use_cases = PurchaseQuotationUseCases(repository)

    received = await use_cases.record_response(
        company_id=company_id,
        quotation_id=requested.id,
        quotation_date=datetime.now(UTC),
        valid_until=datetime.now(UTC) + timedelta(days=10),
        payment_terms="30 días",
        delivery_days=4,
        lines=(
            PurchaseQuotationResponseLineDraft(
                product_id=11,
                unit_id=3,
                quantity=Decimal("5"),
                unit_price=Decimal("10"),
                discount=Decimal("5"),
                tax_rate=Decimal("13"),
            ),
        ),
        expenses=(
            PurchaseQuotationExpenseDraft(
                expense_type_id=expense_type_id,
                amount=Decimal("2.5"),
                description="Flete",
            ),
        ),
    )

    assert received.status is PurchaseQuotationStatus.RECEIVED
    assert received.subtotal == Decimal("50.000000")
    assert received.discount == Decimal("5.000000")
    assert received.tax == Decimal("5.850000")
    assert received.total == Decimal("53.350000")
    assert repository.advanced == [(company_id, (request_id,))]


@pytest.mark.asyncio
async def test_record_response_rejects_out_of_scope_product() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()
    requested = await _create_requested(repository, company_id, request_id, request_detail_id)

    with pytest.raises(ValidationError) as exc_info:
        await PurchaseQuotationUseCases(repository).record_response(
            company_id=company_id,
            quotation_id=requested.id,
            quotation_date=datetime.now(UTC),
            lines=(
                PurchaseQuotationResponseLineDraft(
                    product_id=999,
                    unit_id=3,
                    quantity=Decimal("1"),
                    unit_price=Decimal("1"),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_quotation_response_out_of_scope"


@pytest.mark.asyncio
async def test_record_response_rejects_reducing_scope_quantity() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()
    requested = await _create_requested(repository, company_id, request_id, request_detail_id)

    with pytest.raises(ValidationError) as exc_info:
        await PurchaseQuotationUseCases(repository).record_response(
            company_id=company_id,
            quotation_id=requested.id,
            quotation_date=datetime.now(UTC),
            lines=(
                PurchaseQuotationResponseLineDraft(
                    product_id=11,
                    unit_id=3,
                    quantity=Decimal("1"),
                    unit_price=Decimal("1"),
                    available_quantity=Decimal("1"),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_quotation_response_quantity_incomplete"


@pytest.mark.asyncio
async def test_record_response_accepts_partial_available_quantity() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()
    requested = await _create_requested(repository, company_id, request_id, request_detail_id)

    received = await PurchaseQuotationUseCases(repository).record_response(
        company_id=company_id,
        quotation_id=requested.id,
        quotation_date=datetime.now(UTC),
        lines=(
            PurchaseQuotationResponseLineDraft(
                product_id=11,
                unit_id=3,
                quantity=Decimal("5"),
                unit_price=Decimal("1"),
                available_quantity=Decimal("1"),
            ),
        ),
    )

    assert received.details[0].quantity == Decimal("5")
    assert received.details[0].available_quantity == Decimal("1")


@pytest.mark.asyncio
async def test_record_response_rejects_inactive_expense_type() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()
    requested = await _create_requested(repository, company_id, request_id, request_detail_id)

    with pytest.raises(ValidationError) as exc_info:
        await PurchaseQuotationUseCases(repository).record_response(
            company_id=company_id,
            quotation_id=requested.id,
            quotation_date=datetime.now(UTC),
            lines=(
                PurchaseQuotationResponseLineDraft(
                    product_id=11,
                    unit_id=3,
                    quantity=Decimal("5"),
                    unit_price=Decimal("1"),
                ),
            ),
            expenses=(
                PurchaseQuotationExpenseDraft(
                    expense_type_id=uuid.uuid4(),
                    amount=Decimal("1"),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_quotation_expense_type_invalid"


@pytest.mark.asyncio
async def test_start_evaluation_and_select_offer_follow_workflow() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()
    requested = await _create_requested(repository, company_id, request_id, request_detail_id)
    use_cases = PurchaseQuotationUseCases(repository)
    received = await use_cases.record_response(
        company_id=company_id,
        quotation_id=requested.id,
        quotation_date=datetime.now(UTC),
        valid_until=datetime.now(UTC) + timedelta(days=5),
        lines=(
            PurchaseQuotationResponseLineDraft(
                product_id=11,
                unit_id=3,
                quantity=Decimal("5"),
                unit_price=Decimal("20"),
            ),
        ),
    )

    evaluating = await use_cases.start_evaluation(company_id, received.id)
    selected = await use_cases.select_offer(company_id, evaluating.id)

    assert evaluating.status is PurchaseQuotationStatus.UNDER_EVALUATION
    assert selected.status is PurchaseQuotationStatus.SELECTED


@pytest.mark.asyncio
async def test_select_offer_rejects_expired_quote() -> None:
    repository, company_id, request_id, request_detail_id, _ = _setup_repository()
    requested = await _create_requested(repository, company_id, request_id, request_detail_id)
    use_cases = PurchaseQuotationUseCases(repository)
    quotation_date = datetime.now(UTC) - timedelta(days=10)
    received = await use_cases.record_response(
        company_id=company_id,
        quotation_id=requested.id,
        quotation_date=quotation_date,
        valid_until=quotation_date + timedelta(days=1),
        lines=(
            PurchaseQuotationResponseLineDraft(
                product_id=11,
                unit_id=3,
                quantity=Decimal("5"),
                unit_price=Decimal("20"),
            ),
        ),
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        await use_cases.select_offer(company_id, received.id, now=datetime.now(UTC))
    assert exc_info.value.code == "purchase_quotation_expired"


def _comparison_quote(
    *,
    company_id: uuid.UUID,
    request_id: uuid.UUID,
    supplier_id: int,
    code: str,
    total: str,
    currency: str = "USD",
    delivery_days: int | None = None,
    valid_until: datetime | None = None,
) -> PurchaseQuotation:
    quotation_id = uuid.uuid4()
    link_id = uuid.uuid4()
    quotation_date = (
        valid_until - timedelta(days=1) if valid_until is not None else datetime.now(UTC)
    )
    return PurchaseQuotation(
        id=quotation_id,
        company_id=company_id,
        code=code,
        supplier_id=supplier_id,
        quotation_date=quotation_date,
        currency=currency,
        created_by_id=uuid.uuid4(),
        request_links=(
            PurchaseQuotationRequest(
                id=link_id,
                purchase_quotation_id=quotation_id,
                purchase_request_id=request_id,
                details=(
                    PurchaseQuotationRequestDetail(
                        id=uuid.uuid4(),
                        purchase_quotation_request_id=link_id,
                        purchase_request_detail_id=uuid.uuid4(),
                        quantity=Decimal("1"),
                    ),
                ),
            ),
        ),
        details=(
            PurchaseQuotationDetail(
                id=uuid.uuid4(),
                purchase_quotation_id=quotation_id,
                product_id=11,
                unit_id=3,
                quantity=Decimal("1"),
                unit_price=Decimal(total),
                subtotal=Decimal(total),
                total=Decimal(total),
            ),
        ),
        subtotal=Decimal(total),
        total=Decimal(total),
        delivery_days=delivery_days,
        valid_until=valid_until,
        status=PurchaseQuotationStatus.RECEIVED,
    )


@pytest.mark.asyncio
async def test_compare_offers_orders_by_total_then_delivery() -> None:
    repository, company_id, request_id, _, _ = _setup_repository()
    first = _comparison_quote(
        company_id=company_id,
        request_id=request_id,
        supplier_id=1,
        code="COT-00001",
        total="100",
        delivery_days=8,
    )
    second = _comparison_quote(
        company_id=company_id,
        request_id=request_id,
        supplier_id=2,
        code="COT-00002",
        total="90",
        delivery_days=10,
    )
    repository.comparable[(company_id, request_id)] = [first, second]

    rows = await PurchaseQuotationUseCases(repository).compare_offers(company_id, request_id)

    assert [row.code for row in rows] == ["COT-00002", "COT-00001"]


@pytest.mark.asyncio
async def test_compare_offers_requires_same_currency_without_filter() -> None:
    repository, company_id, request_id, _, _ = _setup_repository()
    repository.comparable[(company_id, request_id)] = [
        _comparison_quote(
            company_id=company_id,
            request_id=request_id,
            supplier_id=1,
            code="COT-00001",
            total="100",
            currency="USD",
        ),
        _comparison_quote(
            company_id=company_id,
            request_id=request_id,
            supplier_id=2,
            code="COT-00002",
            total="95",
            currency="EUR",
        ),
    ]

    with pytest.raises(BusinessRuleError) as exc_info:
        await PurchaseQuotationUseCases(repository).compare_offers(company_id, request_id)
    assert exc_info.value.code == "purchase_quotation_currency_mismatch"


@pytest.mark.asyncio
async def test_compare_offers_excludes_expired_quotes() -> None:
    repository, company_id, request_id, _, _ = _setup_repository()
    now = datetime.now(UTC)
    repository.comparable[(company_id, request_id)] = [
        _comparison_quote(
            company_id=company_id,
            request_id=request_id,
            supplier_id=1,
            code="COT-00001",
            total="100",
            valid_until=now - timedelta(seconds=1),
        ),
        _comparison_quote(
            company_id=company_id,
            request_id=request_id,
            supplier_id=2,
            code="COT-00002",
            total="120",
            valid_until=now + timedelta(days=1),
        ),
    ]

    rows = await PurchaseQuotationUseCases(repository).compare_offers(
        company_id,
        request_id,
        now=now,
    )

    assert [row.code for row in rows] == ["COT-00002"]
