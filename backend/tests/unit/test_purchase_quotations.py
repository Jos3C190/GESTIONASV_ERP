from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.domain.entities.purchase_quotation import (
    ExpenseType,
    PurchaseQuotation,
    PurchaseQuotationDetail,
    PurchaseQuotationExpense,
    PurchaseQuotationRequest,
    PurchaseQuotationRequestDetail,
    PurchaseQuotationStatus,
    PurchaseQuotationTransitionError,
    ensure_purchase_quotation_transition,
)


def _ids() -> dict[str, uuid.UUID]:
    return {
        name: uuid.uuid4()
        for name in (
            "company",
            "quotation",
            "request_link",
            "purchase_request",
            "request_detail",
            "quote_detail",
            "expense",
            "expense_type",
            "user",
        )
    }


def _request_link(ids: dict[str, uuid.UUID]) -> PurchaseQuotationRequest:
    detail = PurchaseQuotationRequestDetail(
        id=uuid.uuid4(),
        purchase_quotation_request_id=ids["request_link"],
        purchase_request_detail_id=ids["request_detail"],
        quantity=Decimal("5"),
    )
    return PurchaseQuotationRequest(
        id=ids["request_link"],
        purchase_quotation_id=ids["quotation"],
        purchase_request_id=ids["purchase_request"],
        details=(detail,),
    )


def _quote_detail(ids: dict[str, uuid.UUID]) -> PurchaseQuotationDetail:
    return PurchaseQuotationDetail(
        id=ids["quote_detail"],
        purchase_quotation_id=ids["quotation"],
        product_id=10,
        unit_id=2,
        quantity=Decimal("5"),
        unit_price=Decimal("10"),
        subtotal=Decimal("50"),
        tax_rate=Decimal("13"),
        tax_amount=Decimal("6.50"),
        total=Decimal("56.50"),
        available_quantity=Decimal("5"),
        delivery_days=3,
    )


def _quotation(
    ids: dict[str, uuid.UUID],
    *,
    status: PurchaseQuotationStatus = PurchaseQuotationStatus.DRAFT,
    details: tuple[PurchaseQuotationDetail, ...] = (),
) -> PurchaseQuotation:
    return PurchaseQuotation(
        id=ids["quotation"],
        company_id=ids["company"],
        code="COT-00001",
        supplier_id=7,
        quotation_date=datetime.now(UTC),
        currency="USD",
        created_by_id=ids["user"],
        request_links=(_request_link(ids),),
        details=details,
        status=status,
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (PurchaseQuotationStatus.DRAFT, PurchaseQuotationStatus.REQUESTED),
        (PurchaseQuotationStatus.REQUESTED, PurchaseQuotationStatus.RECEIVED),
        (PurchaseQuotationStatus.RECEIVED, PurchaseQuotationStatus.UNDER_EVALUATION),
        (PurchaseQuotationStatus.RECEIVED, PurchaseQuotationStatus.SELECTED),
        (PurchaseQuotationStatus.UNDER_EVALUATION, PurchaseQuotationStatus.REJECTED),
    ],
)
def test_allowed_purchase_quotation_transitions(
    current: PurchaseQuotationStatus,
    target: PurchaseQuotationStatus,
) -> None:
    ensure_purchase_quotation_transition(current, target)


def test_invalid_purchase_quotation_transition_raises() -> None:
    with pytest.raises(PurchaseQuotationTransitionError):
        ensure_purchase_quotation_transition(
            PurchaseQuotationStatus.DRAFT,
            PurchaseQuotationStatus.SELECTED,
        )


def test_expense_type_requires_name() -> None:
    with pytest.raises(ValueError, match="nombre"):
        ExpenseType(id=uuid.uuid4(), company_id=uuid.uuid4(), name="   ")


@pytest.mark.parametrize("quantity", [Decimal("0"), Decimal("-1"), Decimal("NaN")])
def test_request_detail_requires_positive_quantity(quantity: Decimal) -> None:
    with pytest.raises(ValueError, match="mayor que cero"):
        PurchaseQuotationRequestDetail(
            id=uuid.uuid4(),
            purchase_quotation_request_id=uuid.uuid4(),
            purchase_request_detail_id=uuid.uuid4(),
            quantity=quantity,
        )


def test_request_link_requires_details() -> None:
    with pytest.raises(ValueError, match="al menos un detalle"):
        PurchaseQuotationRequest(
            id=uuid.uuid4(),
            purchase_quotation_id=uuid.uuid4(),
            purchase_request_id=uuid.uuid4(),
            details=(),
        )


def test_request_link_rejects_foreign_detail() -> None:
    with pytest.raises(ValueError, match="pertenecer"):
        PurchaseQuotationRequest(
            id=uuid.uuid4(),
            purchase_quotation_id=uuid.uuid4(),
            purchase_request_id=uuid.uuid4(),
            details=(
                PurchaseQuotationRequestDetail(
                    id=uuid.uuid4(),
                    purchase_quotation_request_id=uuid.uuid4(),
                    purchase_request_detail_id=uuid.uuid4(),
                    quantity=Decimal("1"),
                ),
            ),
        )


def test_quote_detail_validates_commercial_values() -> None:
    quotation_id = uuid.uuid4()
    with pytest.raises(ValueError, match="precio unitario"):
        PurchaseQuotationDetail(
            id=uuid.uuid4(),
            purchase_quotation_id=quotation_id,
            product_id=1,
            unit_id=1,
            quantity=Decimal("1"),
            unit_price=Decimal("-0.01"),
        )
    with pytest.raises(ValueError, match="superar 100"):
        PurchaseQuotationDetail(
            id=uuid.uuid4(),
            purchase_quotation_id=quotation_id,
            product_id=1,
            unit_id=1,
            quantity=Decimal("1"),
            unit_price=Decimal("1"),
            tax_rate=Decimal("100.01"),
        )


def test_quote_detail_rejects_available_quantity_above_quote() -> None:
    with pytest.raises(ValueError, match="cantidad disponible"):
        PurchaseQuotationDetail(
            id=uuid.uuid4(),
            purchase_quotation_id=uuid.uuid4(),
            product_id=1,
            unit_id=1,
            quantity=Decimal("5"),
            unit_price=Decimal("2"),
            available_quantity=Decimal("6"),
        )


def test_quote_detail_rejects_discount_above_subtotal() -> None:
    with pytest.raises(ValueError, match="descuento"):
        PurchaseQuotationDetail(
            id=uuid.uuid4(),
            purchase_quotation_id=uuid.uuid4(),
            product_id=1,
            unit_id=1,
            quantity=Decimal("1"),
            unit_price=Decimal("10"),
            subtotal=Decimal("10"),
            discount=Decimal("11"),
        )


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1")])
def test_expense_requires_positive_amount(amount: Decimal) -> None:
    with pytest.raises(ValueError, match="monto del gasto"):
        PurchaseQuotationExpense(
            id=uuid.uuid4(),
            purchase_quotation_id=uuid.uuid4(),
            expense_type_id=uuid.uuid4(),
            amount=amount,
        )


def test_draft_quotation_can_exist_before_supplier_response() -> None:
    ids = _ids()
    quotation = _quotation(ids)
    assert quotation.status is PurchaseQuotationStatus.DRAFT
    assert quotation.details == ()


def test_received_quotation_requires_supplier_lines() -> None:
    ids = _ids()
    with pytest.raises(ValueError, match="al menos un detalle"):
        _quotation(ids, status=PurchaseQuotationStatus.RECEIVED)


def test_received_quotation_accepts_supplier_lines() -> None:
    ids = _ids()
    detail = _quote_detail(ids)
    quotation = _quotation(
        ids,
        status=PurchaseQuotationStatus.RECEIVED,
        details=(detail,),
    )
    assert quotation.details == (detail,)


@pytest.mark.parametrize("currency", ["usd", "US", "US1", "USDD"])
def test_quotation_requires_iso_currency(currency: str) -> None:
    ids = _ids()
    with pytest.raises(ValueError, match="moneda"):
        PurchaseQuotation(
            id=ids["quotation"],
            company_id=ids["company"],
            code="COT-00001",
            supplier_id=7,
            quotation_date=datetime.now(UTC),
            currency=currency,
            created_by_id=ids["user"],
            request_links=(_request_link(ids),),
        )


def test_quotation_rejects_expired_validity_range() -> None:
    ids = _ids()
    quotation_date = datetime.now(UTC)
    with pytest.raises(ValueError, match="vigencia"):
        PurchaseQuotation(
            id=ids["quotation"],
            company_id=ids["company"],
            code="COT-00001",
            supplier_id=7,
            quotation_date=quotation_date,
            valid_until=quotation_date - timedelta(days=1),
            currency="USD",
            created_by_id=ids["user"],
            request_links=(_request_link(ids),),
        )


def test_quotation_rejects_foreign_children() -> None:
    ids = _ids()
    foreign_link = PurchaseQuotationRequest(
        id=ids["request_link"],
        purchase_quotation_id=uuid.uuid4(),
        purchase_request_id=ids["purchase_request"],
        details=(
            PurchaseQuotationRequestDetail(
                id=uuid.uuid4(),
                purchase_quotation_request_id=ids["request_link"],
                purchase_request_detail_id=ids["request_detail"],
                quantity=Decimal("1"),
            ),
        ),
    )
    with pytest.raises(ValueError, match="solicitudes vinculadas"):
        PurchaseQuotation(
            id=ids["quotation"],
            company_id=ids["company"],
            code="COT-00001",
            supplier_id=7,
            quotation_date=datetime.now(UTC),
            currency="USD",
            created_by_id=ids["user"],
            request_links=(foreign_link,),
        )
