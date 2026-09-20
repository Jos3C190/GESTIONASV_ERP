"""Unit tests for supplier purchase receipt domain rules."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.domain.entities.purchase import (
    Purchase,
    PurchaseDetail,
    PurchaseStatus,
    PurchaseTransitionError,
    ensure_purchase_transition,
)


def _ids() -> dict[str, uuid.UUID]:
    return {
        "purchase": uuid.uuid4(),
        "company": uuid.uuid4(),
        "order": uuid.uuid4(),
        "branch": uuid.uuid4(),
        "warehouse": uuid.uuid4(),
        "user": uuid.uuid4(),
    }


def _detail(purchase_id: uuid.UUID, *, received: Decimal = Decimal("2")) -> PurchaseDetail:
    return PurchaseDetail(
        id=uuid.uuid4(),
        purchase_id=purchase_id,
        purchase_order_detail_id=uuid.uuid4(),
        product_id=1,
        quantity_ordered=Decimal("5"),
        quantity_received=received,
        unit_id=4,
        unit_price=Decimal("28"),
        subtotal=received * Decimal("28"),
        tax_rate=Decimal("13"),
        tax_amount=received * Decimal("28") * Decimal("0.13"),
        total=received * Decimal("28") * Decimal("1.13"),
    )


def _purchase(ids: dict[str, uuid.UUID]) -> Purchase:
    detail = _detail(ids["purchase"])
    return Purchase(
        id=ids["purchase"],
        company_id=ids["company"],
        code="COM-00001",
        purchase_order_id=ids["order"],
        supplier_id=7,
        branch_id=ids["branch"],
        warehouse_id=ids["warehouse"],
        created_by_id=ids["user"],
        purchase_date=datetime.now(UTC),
        currency="USD",
        details=(detail,),
        subtotal=detail.subtotal,
        tax=detail.tax_amount,
        total=detail.total,
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (PurchaseStatus.DRAFT, PurchaseStatus.RECEIVED),
        (PurchaseStatus.DRAFT, PurchaseStatus.CANCELLED),
        (PurchaseStatus.RECEIVED, PurchaseStatus.VERIFIED),
        (PurchaseStatus.VERIFIED, PurchaseStatus.CLOSED),
    ],
)
def test_allowed_purchase_transitions(current: PurchaseStatus, target: PurchaseStatus) -> None:
    ensure_purchase_transition(current, target)


def test_invalid_purchase_transition_raises() -> None:
    with pytest.raises(PurchaseTransitionError):
        ensure_purchase_transition(PurchaseStatus.DRAFT, PurchaseStatus.CLOSED)


@pytest.mark.parametrize("received", [Decimal("0"), Decimal("-1"), Decimal("NaN")])
def test_purchase_detail_requires_positive_received_quantity(received: Decimal) -> None:
    with pytest.raises(ValueError, match="cantidad recibida"):
        _detail(uuid.uuid4(), received=received)


def test_purchase_detail_rejects_quantity_above_ordered() -> None:
    with pytest.raises(ValueError, match="superar"):
        _detail(uuid.uuid4(), received=Decimal("6"))


def test_purchase_detail_rejects_discount_above_subtotal() -> None:
    with pytest.raises(ValueError, match="descuento"):
        PurchaseDetail(
            id=uuid.uuid4(),
            purchase_id=uuid.uuid4(),
            purchase_order_detail_id=uuid.uuid4(),
            product_id=1,
            quantity_ordered=Decimal("5"),
            quantity_received=Decimal("1"),
            unit_id=4,
            unit_price=Decimal("10"),
            subtotal=Decimal("10"),
            discount=Decimal("11"),
        )


def test_purchase_requires_details() -> None:
    ids = _ids()
    with pytest.raises(ValueError, match="al menos un detalle"):
        Purchase(
            id=ids["purchase"],
            company_id=ids["company"],
            code="COM-00001",
            purchase_order_id=ids["order"],
            supplier_id=7,
            branch_id=ids["branch"],
            warehouse_id=ids["warehouse"],
            created_by_id=ids["user"],
            purchase_date=datetime.now(UTC),
            currency="USD",
            details=(),
        )


def test_purchase_rejects_foreign_detail() -> None:
    ids = _ids()
    with pytest.raises(ValueError, match="detalles"):
        Purchase(
            id=ids["purchase"],
            company_id=ids["company"],
            code="COM-00001",
            purchase_order_id=ids["order"],
            supplier_id=7,
            branch_id=ids["branch"],
            warehouse_id=ids["warehouse"],
            created_by_id=ids["user"],
            purchase_date=datetime.now(UTC),
            currency="USD",
            details=(_detail(uuid.uuid4()),),
        )


@pytest.mark.parametrize("currency", ["usd", "US", "US1", "USDD"])
def test_purchase_requires_iso_currency(currency: str) -> None:
    ids = _ids()
    detail = _detail(ids["purchase"])
    with pytest.raises(ValueError, match="moneda"):
        Purchase(
            id=ids["purchase"],
            company_id=ids["company"],
            code="COM-00001",
            purchase_order_id=ids["order"],
            supplier_id=7,
            branch_id=ids["branch"],
            warehouse_id=ids["warehouse"],
            created_by_id=ids["user"],
            purchase_date=datetime.now(UTC),
            currency=currency,
            details=(detail,),
        )


def test_purchase_requires_timezone_aware_date() -> None:
    ids = _ids()
    detail = _detail(ids["purchase"])
    with pytest.raises(ValueError, match="zona horaria"):
        Purchase(
            id=ids["purchase"],
            company_id=ids["company"],
            code="COM-00001",
            purchase_order_id=ids["order"],
            supplier_id=7,
            branch_id=ids["branch"],
            warehouse_id=ids["warehouse"],
            created_by_id=ids["user"],
            purchase_date=datetime.now(UTC).replace(tzinfo=None),
            currency="USD",
            details=(detail,),
        )


def test_purchase_accepts_valid_aggregate() -> None:
    purchase = _purchase(_ids())
    assert purchase.status is PurchaseStatus.DRAFT
    assert purchase.code == "COM-00001"
    assert len(purchase.details) == 1
