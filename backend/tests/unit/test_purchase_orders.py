from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.domain.entities.purchase_order import (
    PurchaseOrder,
    PurchaseOrderDetail,
    PurchaseOrderExpense,
    PurchaseOrderStatus,
    PurchaseOrderTransitionError,
    ensure_purchase_order_transition,
)


def _ids() -> dict[str, uuid.UUID]:
    return {
        name: uuid.uuid4()
        for name in (
            "company",
            "order",
            "branch",
            "warehouse",
            "quotation",
            "user",
            "expense_type",
        )
    }


def _detail(order_id: uuid.UUID) -> PurchaseOrderDetail:
    return PurchaseOrderDetail(
        id=uuid.uuid4(),
        purchase_order_id=order_id,
        product_id=10,
        quantity=Decimal("5"),
        unit_id=2,
        unit_price=Decimal("10"),
        subtotal=Decimal("50"),
        tax_rate=Decimal("13"),
        tax_amount=Decimal("6.50"),
        total=Decimal("56.50"),
    )


def _order(
    ids: dict[str, uuid.UUID],
    *,
    details: tuple[PurchaseOrderDetail, ...] | None = None,
    expenses: tuple[PurchaseOrderExpense, ...] = (),
    expected_date: datetime | None = None,
) -> PurchaseOrder:
    order_date = datetime.now(UTC)
    return PurchaseOrder(
        id=ids["order"],
        company_id=ids["company"],
        code="OC-00001",
        supplier_id=7,
        branch_id=ids["branch"],
        warehouse_id=ids["warehouse"],
        purchase_quotation_id=ids["quotation"],
        created_by_id=ids["user"],
        order_date=order_date,
        expected_date=expected_date,
        currency="USD",
        details=details if details is not None else (_detail(ids["order"]),),
        expenses=expenses,
        subtotal=Decimal("50"),
        tax=Decimal("6.50"),
        total=Decimal("56.50"),
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.PENDING_APPROVAL),
        (PurchaseOrderStatus.PENDING_APPROVAL, PurchaseOrderStatus.APPROVED),
        (PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.SENT),
        (PurchaseOrderStatus.SENT, PurchaseOrderStatus.PARTIALLY_RECEIVED),
        (PurchaseOrderStatus.SENT, PurchaseOrderStatus.RECEIVED),
        (PurchaseOrderStatus.PARTIALLY_RECEIVED, PurchaseOrderStatus.RECEIVED),
        (PurchaseOrderStatus.RECEIVED, PurchaseOrderStatus.CLOSED),
    ],
)
def test_allowed_purchase_order_transitions(
    current: PurchaseOrderStatus,
    target: PurchaseOrderStatus,
) -> None:
    ensure_purchase_order_transition(current, target)


def test_invalid_purchase_order_transition_raises() -> None:
    with pytest.raises(PurchaseOrderTransitionError):
        ensure_purchase_order_transition(
            PurchaseOrderStatus.DRAFT,
            PurchaseOrderStatus.APPROVED,
        )


def test_purchase_order_detail_validates_commercial_values() -> None:
    order_id = uuid.uuid4()
    with pytest.raises(ValueError, match="cantidad ordenada"):
        PurchaseOrderDetail(
            id=uuid.uuid4(),
            purchase_order_id=order_id,
            product_id=1,
            quantity=Decimal("0"),
            unit_id=1,
            unit_price=Decimal("1"),
        )
    with pytest.raises(ValueError, match="precio unitario"):
        PurchaseOrderDetail(
            id=uuid.uuid4(),
            purchase_order_id=order_id,
            product_id=1,
            quantity=Decimal("1"),
            unit_id=1,
            unit_price=Decimal("-0.01"),
        )
    with pytest.raises(ValueError, match="superar 100"):
        PurchaseOrderDetail(
            id=uuid.uuid4(),
            purchase_order_id=order_id,
            product_id=1,
            quantity=Decimal("1"),
            unit_id=1,
            unit_price=Decimal("1"),
            tax_rate=Decimal("100.01"),
        )


def test_purchase_order_detail_rejects_discount_above_subtotal() -> None:
    with pytest.raises(ValueError, match="descuento"):
        PurchaseOrderDetail(
            id=uuid.uuid4(),
            purchase_order_id=uuid.uuid4(),
            product_id=1,
            quantity=Decimal("1"),
            unit_id=1,
            unit_price=Decimal("10"),
            subtotal=Decimal("10"),
            discount=Decimal("11"),
        )


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1"), Decimal("NaN")])
def test_purchase_order_expense_requires_positive_amount(amount: Decimal) -> None:
    with pytest.raises(ValueError, match="monto del gasto"):
        PurchaseOrderExpense(
            id=uuid.uuid4(),
            purchase_order_id=uuid.uuid4(),
            expense_type_id=uuid.uuid4(),
            amount=amount,
        )


def test_purchase_order_requires_details() -> None:
    ids = _ids()
    with pytest.raises(ValueError, match="al menos un detalle"):
        _order(ids, details=())


def test_purchase_order_rejects_foreign_detail() -> None:
    ids = _ids()
    with pytest.raises(ValueError, match="detalles"):
        _order(ids, details=(_detail(uuid.uuid4()),))


def test_purchase_order_rejects_foreign_expense() -> None:
    ids = _ids()
    expense = PurchaseOrderExpense(
        id=uuid.uuid4(),
        purchase_order_id=uuid.uuid4(),
        expense_type_id=ids["expense_type"],
        amount=Decimal("5"),
    )
    with pytest.raises(ValueError, match="gastos"):
        _order(ids, expenses=(expense,))


@pytest.mark.parametrize("currency", ["usd", "US", "US1", "USDD"])
def test_purchase_order_requires_iso_currency(currency: str) -> None:
    ids = _ids()
    with pytest.raises(ValueError, match="moneda"):
        PurchaseOrder(
            id=ids["order"],
            company_id=ids["company"],
            code="OC-00001",
            supplier_id=7,
            branch_id=ids["branch"],
            warehouse_id=ids["warehouse"],
            purchase_quotation_id=ids["quotation"],
            created_by_id=ids["user"],
            order_date=datetime.now(UTC),
            currency=currency,
            details=(_detail(ids["order"]),),
        )


def test_purchase_order_rejects_expected_date_before_order_date() -> None:
    ids = _ids()
    order_date = datetime.now(UTC)
    with pytest.raises(ValueError, match="fecha esperada"):
        PurchaseOrder(
            id=ids["order"],
            company_id=ids["company"],
            code="OC-00001",
            supplier_id=7,
            branch_id=ids["branch"],
            warehouse_id=ids["warehouse"],
            purchase_quotation_id=ids["quotation"],
            created_by_id=ids["user"],
            order_date=order_date,
            expected_date=order_date - timedelta(days=1),
            currency="USD",
            details=(_detail(ids["order"]),),
        )


def test_purchase_order_rejects_discount_above_subtotal() -> None:
    ids = _ids()
    with pytest.raises(ValueError, match="descuento"):
        PurchaseOrder(
            id=ids["order"],
            company_id=ids["company"],
            code="OC-00001",
            supplier_id=7,
            branch_id=ids["branch"],
            warehouse_id=ids["warehouse"],
            purchase_quotation_id=ids["quotation"],
            created_by_id=ids["user"],
            order_date=datetime.now(UTC),
            currency="USD",
            details=(_detail(ids["order"]),),
            subtotal=Decimal("10"),
            discount=Decimal("11"),
        )


def test_purchase_order_accepts_valid_aggregate() -> None:
    ids = _ids()
    order = _order(ids)
    assert order.status is PurchaseOrderStatus.DRAFT
    assert order.code == "OC-00001"
    assert len(order.details) == 1


def test_purchase_order_requires_timezone_aware_dates() -> None:
    ids = _ids()
    with pytest.raises(ValueError, match="zona horaria"):
        PurchaseOrder(
            id=ids["order"],
            company_id=ids["company"],
            code="OC-00001",
            supplier_id=7,
            branch_id=ids["branch"],
            warehouse_id=ids["warehouse"],
            purchase_quotation_id=ids["quotation"],
            created_by_id=ids["user"],
            order_date=datetime(2026, 9, 12, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            currency="USD",
            details=(_detail(ids["order"]),),
        )

    order_date = datetime.now(UTC)
    with pytest.raises(ValueError, match="zona horaria"):
        PurchaseOrder(
            id=ids["order"],
            company_id=ids["company"],
            code="OC-00001",
            supplier_id=7,
            branch_id=ids["branch"],
            warehouse_id=ids["warehouse"],
            purchase_quotation_id=ids["quotation"],
            created_by_id=ids["user"],
            order_date=order_date,
            expected_date=datetime(2026, 9, 20, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            currency="USD",
            details=(_detail(ids["order"]),),
        )
