"""Unit tests for supplier purchase-receipt application rules."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.application.purchases import PurchaseLineDraft, PurchaseUseCases
from app.core.exceptions import BusinessRuleError
from app.domain.entities.purchase import Purchase, PurchaseDetail, PurchaseStatus
from app.domain.entities.purchase_order import (
    PurchaseOrder,
    PurchaseOrderDetail,
    PurchaseOrderStatus,
)


def _ids() -> dict[str, uuid.UUID]:
    return {
        key: uuid.uuid4()
        for key in (
            "company",
            "order",
            "order_detail",
            "quotation_detail",
            "branch",
            "warehouse",
            "user",
        )
    }


def _order(
    ids: dict[str, uuid.UUID],
    *,
    status: PurchaseOrderStatus = PurchaseOrderStatus.SENT,
) -> PurchaseOrder:
    detail = PurchaseOrderDetail(
        id=ids["order_detail"],
        purchase_order_id=ids["order"],
        purchase_quotation_detail_id=ids["quotation_detail"],
        product_id=10,
        quantity=Decimal("5"),
        unit_id=2,
        unit_price=Decimal("28"),
        subtotal=Decimal("140"),
        tax_rate=Decimal("13"),
        tax_amount=Decimal("18.2"),
        total=Decimal("158.2"),
    )
    return PurchaseOrder(
        id=ids["order"],
        company_id=ids["company"],
        code="OC-00001",
        supplier_id=7,
        branch_id=ids["branch"],
        warehouse_id=ids["warehouse"],
        purchase_quotation_id=uuid.uuid4(),
        created_by_id=ids["user"],
        order_date=datetime.now(UTC),
        currency="USD",
        details=(detail,),
        subtotal=detail.subtotal,
        tax=detail.tax_amount,
        total=detail.total,
        status=status,
    )


class FakePurchaseRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Purchase] = {}
        self.received: dict[uuid.UUID, Decimal] = {}
        self.next_code = 1

    async def list_purchases(
        self, company_id: uuid.UUID, **kwargs: object
    ) -> tuple[list[Purchase], int]:
        items = [item for item in self.items.values() if item.company_id == company_id]
        return items, len(items)

    async def get_purchase(self, company_id: uuid.UUID, purchase_id: uuid.UUID) -> Purchase | None:
        item = self.items.get(purchase_id)
        return item if item is not None and item.company_id == company_id else None

    async def get_purchase_for_update(
        self, company_id: uuid.UUID, purchase_id: uuid.UUID
    ) -> Purchase | None:
        return await self.get_purchase(company_id, purchase_id)

    async def allocate_next_code(self, company_id: uuid.UUID) -> str:
        code = f"COM-{self.next_code:05d}"
        self.next_code += 1
        return code

    async def get_received_quantities(
        self,
        company_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        *,
        exclude_purchase_id: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, Decimal]:
        return dict(self.received)

    async def add_purchase(self, purchase: Purchase) -> Purchase:
        self.items[purchase.id] = purchase
        return purchase

    async def replace_draft(self, purchase: Purchase) -> Purchase | None:
        if purchase.id not in self.items:
            return None
        self.items[purchase.id] = purchase
        return purchase

    async def update_status(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
        status: PurchaseStatus,
    ) -> Purchase | None:
        item = await self.get_purchase(company_id, purchase_id)
        if item is None:
            return None
        updated = replace(item, status=status)
        self.items[purchase_id] = updated
        return updated


class FakeOrderRepository:
    def __init__(self, order: PurchaseOrder) -> None:
        self.order = order

    async def get_order(self, company_id: uuid.UUID, order_id: uuid.UUID) -> PurchaseOrder | None:
        if self.order.company_id == company_id and self.order.id == order_id:
            return self.order
        return None

    async def get_order_for_update(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> PurchaseOrder | None:
        return await self.get_order(company_id, order_id)

    async def update_status(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        status: PurchaseOrderStatus,
    ) -> PurchaseOrder | None:
        item = await self.get_order(company_id, order_id)
        if item is None:
            return None
        self.order = replace(item, status=status)
        return self.order


def _purchase(
    ids: dict[str, uuid.UUID],
    *,
    received: Decimal,
    status: PurchaseStatus = PurchaseStatus.DRAFT,
) -> Purchase:
    order = _order(ids)
    detail = PurchaseDetail(
        id=uuid.uuid4(),
        purchase_id=uuid.uuid4(),
        purchase_order_detail_id=ids["order_detail"],
        product_id=10,
        quantity_ordered=Decimal("5"),
        quantity_received=received,
        unit_id=2,
        unit_price=Decimal("28"),
        subtotal=received * Decimal("28"),
        tax_rate=Decimal("13"),
        tax_amount=received * Decimal("28") * Decimal("0.13"),
        total=received * Decimal("28") * Decimal("1.13"),
    )
    detail = replace(detail, purchase_id=detail.purchase_id)
    return Purchase(
        id=detail.purchase_id,
        company_id=ids["company"],
        code="COM-00001",
        purchase_order_id=ids["order"],
        supplier_id=order.supplier_id,
        branch_id=ids["branch"],
        warehouse_id=ids["warehouse"],
        created_by_id=ids["user"],
        purchase_date=datetime.now(UTC),
        currency="USD",
        details=(detail,),
        subtotal=detail.subtotal,
        tax=detail.tax_amount,
        total=detail.total,
        status=status,
    )


@pytest.mark.asyncio
async def test_create_draft_copies_order_traceability_and_calculates_totals() -> None:
    ids = _ids()
    purchases = FakePurchaseRepository()
    orders = FakeOrderRepository(_order(ids))
    use_cases = PurchaseUseCases(purchases, orders)

    created = await use_cases.create_draft(
        company_id=ids["company"],
        created_by_id=ids["user"],
        purchase_order_id=ids["order"],
        lines=(PurchaseLineDraft(ids["order_detail"], Decimal("2")),),
    )

    assert created.code == "COM-00001"
    assert created.details[0].purchase_order_detail_id == ids["order_detail"]
    assert created.details[0].quantity_received == Decimal("2")
    assert created.subtotal == Decimal("56.000000")
    assert created.tax == Decimal("7.280000")
    assert created.total == Decimal("63.280000")


@pytest.mark.asyncio
async def test_create_draft_rejects_quantity_above_pending() -> None:
    ids = _ids()
    purchases = FakePurchaseRepository()
    purchases.received[ids["order_detail"]] = Decimal("4")
    use_cases = PurchaseUseCases(purchases, FakeOrderRepository(_order(ids)))

    with pytest.raises(BusinessRuleError, match="pendiente"):
        await use_cases.create_draft(
            company_id=ids["company"],
            created_by_id=ids["user"],
            purchase_order_id=ids["order"],
            lines=(PurchaseLineDraft(ids["order_detail"], Decimal("2")),),
        )


@pytest.mark.asyncio
async def test_receivable_lines_expose_ordered_received_and_pending() -> None:
    ids = _ids()
    purchases = FakePurchaseRepository()
    purchases.received[ids["order_detail"]] = Decimal("3")
    use_cases = PurchaseUseCases(purchases, FakeOrderRepository(_order(ids)))

    lines = await use_cases.get_receivable_lines(ids["company"], ids["order"])

    assert lines[0].quantity_ordered == Decimal("5")
    assert lines[0].quantity_received == Decimal("3")
    assert lines[0].quantity_pending == Decimal("2")


@pytest.mark.asyncio
async def test_receive_purchase_marks_order_partially_received() -> None:
    ids = _ids()
    purchases = FakePurchaseRepository()
    purchase = _purchase(ids, received=Decimal("2"))
    purchases.items[purchase.id] = purchase
    orders = FakeOrderRepository(_order(ids))
    use_cases = PurchaseUseCases(purchases, orders)

    received = await use_cases.receive_purchase(ids["company"], purchase.id)

    assert received.status is PurchaseStatus.RECEIVED
    assert orders.order.status is PurchaseOrderStatus.PARTIALLY_RECEIVED


@pytest.mark.asyncio
async def test_receive_purchase_marks_order_received_when_completed() -> None:
    ids = _ids()
    purchases = FakePurchaseRepository()
    purchases.received[ids["order_detail"]] = Decimal("3")
    purchase = _purchase(ids, received=Decimal("2"))
    purchases.items[purchase.id] = purchase
    orders = FakeOrderRepository(_order(ids, status=PurchaseOrderStatus.PARTIALLY_RECEIVED))
    use_cases = PurchaseUseCases(purchases, orders)

    await use_cases.receive_purchase(ids["company"], purchase.id)

    assert orders.order.status is PurchaseOrderStatus.RECEIVED


@pytest.mark.asyncio
async def test_receive_purchase_rechecks_pending_before_mutating_status() -> None:
    ids = _ids()
    purchases = FakePurchaseRepository()
    purchases.received[ids["order_detail"]] = Decimal("4")
    purchase = _purchase(ids, received=Decimal("2"))
    purchases.items[purchase.id] = purchase
    orders = FakeOrderRepository(_order(ids))
    use_cases = PurchaseUseCases(purchases, orders)

    with pytest.raises(BusinessRuleError, match="pendiente"):
        await use_cases.receive_purchase(ids["company"], purchase.id)

    assert purchases.items[purchase.id].status is PurchaseStatus.DRAFT
    assert orders.order.status is PurchaseOrderStatus.SENT


class MissingOnUpdateOrderRepository(FakeOrderRepository):
    async def update_status(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        status: PurchaseOrderStatus,
    ) -> PurchaseOrder | None:
        return None


@pytest.mark.asyncio
async def test_receive_purchase_raises_unexpected_error_if_locked_order_update_disappears() -> None:
    ids = _ids()
    purchases = FakePurchaseRepository()
    purchase = _purchase(ids, received=Decimal("2"))
    purchases.items[purchase.id] = purchase
    orders = MissingOnUpdateOrderRepository(_order(ids))
    use_cases = PurchaseUseCases(purchases, orders)

    with pytest.raises(RuntimeError, match="bloqueada desapareció"):
        await use_cases.receive_purchase(ids["company"], purchase.id)
