"""Unit tests for supplier purchase-receipt application rules."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.application.purchases import PurchaseLineDraft, PurchaseUseCases
from app.core.exceptions import BusinessRuleError, ConflictError, ValidationError
from app.domain.entities.inventory import InventoryOperationError
from app.domain.entities.purchase import (
    Purchase,
    PurchaseDetail,
    PurchaseStatus,
    PurchaseVerificationLine,
)
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
        quantities = dict(self.received)
        for purchase in self.items.values():
            if (
                purchase.company_id != company_id
                or purchase.purchase_order_id != purchase_order_id
                or purchase.id == exclude_purchase_id
            ):
                continue
            for detail in purchase.details:
                if purchase.status is PurchaseStatus.RECEIVED:
                    quantity = detail.quantity_received
                elif purchase.status in {PurchaseStatus.VERIFIED, PurchaseStatus.CLOSED}:
                    quantity = (
                        detail.quantity_accepted
                        if detail.quantity_accepted is not None
                        else detail.quantity_received
                    )
                else:
                    continue
                quantities[detail.purchase_order_detail_id] = (
                    quantities.get(detail.purchase_order_detail_id, Decimal("0")) + quantity
                )
        return quantities

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

    async def complete_verification(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
        *,
        accepted_quantities: dict[uuid.UUID, tuple[Decimal, uuid.UUID | None]],
        inventory_movement_id: uuid.UUID | None,
        valuation_conversion=None,
    ) -> Purchase | None:
        item = await self.get_purchase(company_id, purchase_id)
        if item is None or {detail.id for detail in item.details} != set(accepted_quantities):
            return None
        details = tuple(
            replace(
                detail,
                quantity_accepted=accepted_quantities[detail.id][0],
                inventory_location_id=accepted_quantities[detail.id][1],
            )
            for detail in item.details
        )
        updated = replace(
            item,
            details=details,
            inventory_movement_id=inventory_movement_id,
            valuation_conversion=valuation_conversion,
            status=PurchaseStatus.VERIFIED,
        )
        self.items[purchase_id] = updated
        return updated


class FakePurchaseInventoryGateway:
    def __init__(self, movement_id: uuid.UUID | None) -> None:
        self.movement_id = movement_id
        self.calls: list[dict[str, object]] = []

    async def valuation_currency(self, company_id: uuid.UUID) -> str | None:
        return "USD"

    async def post_verified_receipt(
        self,
        *,
        purchase: Purchase,
        lines: tuple[PurchaseVerificationLine, ...],
        actor_id: uuid.UUID,
    ) -> uuid.UUID | None:
        self.calls.append({"purchase": purchase, "lines": lines, "actor_id": actor_id})
        if not any(line.quantity_accepted > 0 for line in lines):
            return None
        return self.movement_id


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


@pytest.mark.asyncio
async def test_full_receipt_prevents_confirming_other_drafts_or_creating_another_receipt() -> None:
    ids = _ids()
    purchases = FakePurchaseRepository()
    original = _purchase(ids, received=Decimal("5"))
    other_draft = replace(_purchase(ids, received=Decimal("5")), code="COM-00002")
    purchases.items[original.id] = original
    purchases.items[other_draft.id] = other_draft
    orders = FakeOrderRepository(_order(ids))
    use_cases = PurchaseUseCases(purchases, orders)

    await use_cases.receive_purchase(ids["company"], original.id)
    assert orders.order.status is PurchaseOrderStatus.RECEIVED

    with pytest.raises(BusinessRuleError) as duplicate:
        await use_cases.receive_purchase(ids["company"], original.id)
    assert duplicate.value.code == "purchase_not_receivable"

    with pytest.raises(BusinessRuleError) as other:
        await use_cases.receive_purchase(ids["company"], other_draft.id)
    assert other.value.code == "purchase_order_not_receivable"

    with pytest.raises(BusinessRuleError) as new_receipt:
        await use_cases.create_draft(
            company_id=ids["company"],
            created_by_id=ids["user"],
            purchase_order_id=ids["order"],
            lines=(PurchaseLineDraft(ids["order_detail"], Decimal("5")),),
        )
    assert new_receipt.value.code == "purchase_order_not_receivable"
    assert len(purchases.items) == 2
    assert purchases.items[other_draft.id].status is PurchaseStatus.DRAFT
    assert await purchases.get_received_quantities(ids["company"], ids["order"]) == {
        ids["order_detail"]: Decimal("5")
    }


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


@pytest.mark.asyncio
async def test_verify_purchase_posts_only_accepted_quantities_and_tracks_movement() -> None:
    ids = _ids()
    purchase = _purchase(ids, received=Decimal("2"), status=PurchaseStatus.RECEIVED)
    purchases = FakePurchaseRepository()
    purchases.items[purchase.id] = purchase
    orders = FakeOrderRepository(_order(ids))
    location_id = uuid.uuid4()
    movement_id = uuid.uuid4()
    inventory = FakePurchaseInventoryGateway(movement_id)
    use_cases = PurchaseUseCases(purchases, orders, inventory)

    verified = await use_cases.verify_purchase(
        ids["company"],
        purchase.id,
        lines=(
            PurchaseVerificationLine(
                purchase_detail_id=purchase.details[0].id,
                quantity_accepted=Decimal("1.25"),
                inventory_location_id=location_id,
            ),
        ),
        actor_id=ids["user"],
    )

    assert verified.status is PurchaseStatus.VERIFIED
    assert verified.details[0].quantity_accepted == Decimal("1.25")
    assert verified.details[0].quantity_rejected == Decimal("0.75")
    assert verified.details[0].inventory_location_id == location_id
    assert verified.inventory_movement_id == movement_id
    posted_lines = inventory.calls[0]["lines"]
    assert posted_lines == (
        PurchaseVerificationLine(
            purchase_detail_id=purchase.details[0].id,
            quantity_accepted=Decimal("1.25"),
            inventory_location_id=location_id,
        ),
    )
    assert orders.order.status is PurchaseOrderStatus.PARTIALLY_RECEIVED


@pytest.mark.asyncio
async def test_verify_purchase_keeps_receipt_splits_as_separate_inventory_units() -> None:
    ids = _ids()
    purchase = _purchase(ids, received=Decimal("2"), status=PurchaseStatus.RECEIVED)
    purchases = FakePurchaseRepository()
    purchases.items[purchase.id] = purchase
    orders = FakeOrderRepository(_order(ids))
    location_id = uuid.uuid4()
    inventory = FakePurchaseInventoryGateway(uuid.uuid4())
    use_cases = PurchaseUseCases(purchases, orders, inventory)
    split_lines = (
        PurchaseVerificationLine(purchase.details[0].id, Decimal("1.25"), location_id),
        PurchaseVerificationLine(purchase.details[0].id, Decimal("0.5"), location_id),
    )

    verified = await use_cases.verify_purchase(
        ids["company"],
        purchase.id,
        lines=split_lines,
        actor_id=ids["user"],
    )

    assert inventory.calls[0]["lines"] == split_lines
    assert verified.details[0].quantity_accepted == Decimal("1.75")
    assert verified.details[0].quantity_rejected == Decimal("0.25")
    assert verified.details[0].inventory_location_id == location_id


@pytest.mark.asyncio
async def test_verify_purchase_requires_receipt_splits_to_share_a_location() -> None:
    ids = _ids()
    purchase = _purchase(ids, received=Decimal("2"), status=PurchaseStatus.RECEIVED)
    purchases = FakePurchaseRepository()
    purchases.items[purchase.id] = purchase
    inventory = FakePurchaseInventoryGateway(uuid.uuid4())
    use_cases = PurchaseUseCases(
        purchases,
        FakeOrderRepository(_order(ids)),
        inventory,
    )

    with pytest.raises(ValidationError) as error:
        await use_cases.verify_purchase(
            ids["company"],
            purchase.id,
            lines=(
                PurchaseVerificationLine(purchase.details[0].id, Decimal("1"), uuid.uuid4()),
                PurchaseVerificationLine(purchase.details[0].id, Decimal("1"), uuid.uuid4()),
            ),
            actor_id=ids["user"],
        )

    assert error.value.code == "purchase_receipt_split_location_mismatch"
    assert inventory.calls == []


@pytest.mark.asyncio
async def test_verify_purchase_with_zero_accepted_quantity_creates_no_movement() -> None:
    ids = _ids()
    purchase = _purchase(ids, received=Decimal("2"), status=PurchaseStatus.RECEIVED)
    purchases = FakePurchaseRepository()
    purchases.items[purchase.id] = purchase
    orders = FakeOrderRepository(_order(ids))
    inventory = FakePurchaseInventoryGateway(None)
    use_cases = PurchaseUseCases(purchases, orders, inventory)

    verified = await use_cases.verify_purchase(
        ids["company"],
        purchase.id,
        lines=(
            PurchaseVerificationLine(
                purchase_detail_id=purchase.details[0].id,
                quantity_accepted=Decimal("0"),
                inventory_location_id=None,
            ),
        ),
        actor_id=ids["user"],
    )

    assert verified.status is PurchaseStatus.VERIFIED
    assert verified.details[0].quantity_accepted == Decimal("0")
    assert verified.details[0].inventory_location_id is None
    assert verified.inventory_movement_id is None
    assert orders.order.status is PurchaseOrderStatus.SENT

    # Rejected units are not counted against the order; the full amount remains receivable.
    next_draft = await use_cases.create_draft(
        company_id=ids["company"],
        created_by_id=ids["user"],
        purchase_order_id=ids["order"],
        lines=(PurchaseLineDraft(ids["order_detail"], Decimal("5")),),
    )
    assert next_draft.details[0].quantity_received == Decimal("5")


@pytest.mark.asyncio
async def test_verify_purchase_requires_location_for_accepted_quantity() -> None:
    ids = _ids()
    purchase = _purchase(ids, received=Decimal("2"), status=PurchaseStatus.RECEIVED)
    purchases = FakePurchaseRepository()
    purchases.items[purchase.id] = purchase
    inventory = FakePurchaseInventoryGateway(uuid.uuid4())
    use_cases = PurchaseUseCases(purchases, FakeOrderRepository(_order(ids)), inventory)

    with pytest.raises(ValidationError) as exc_info:
        await use_cases.verify_purchase(
            ids["company"],
            purchase.id,
            lines=(
                PurchaseVerificationLine(
                    purchase_detail_id=purchase.details[0].id,
                    quantity_accepted=Decimal("1"),
                    inventory_location_id=None,
                ),
            ),
            actor_id=ids["user"],
        )

    assert exc_info.value.code == "purchase_receipt_location_required"
    assert inventory.calls == []


@pytest.mark.asyncio
async def test_inventory_rejection_leaves_purchase_unverified_and_order_unchanged() -> None:
    ids = _ids()
    purchase = _purchase(ids, received=Decimal("2"), status=PurchaseStatus.RECEIVED)
    purchases = FakePurchaseRepository()
    purchases.items[purchase.id] = purchase
    orders = FakeOrderRepository(_order(ids))

    class RejectingInventoryGateway(FakePurchaseInventoryGateway):
        async def post_verified_receipt(
            self,
            *,
            purchase: Purchase,
            lines: tuple[PurchaseVerificationLine, ...],
            actor_id: uuid.UUID,
        ) -> uuid.UUID | None:
            self.calls.append({"purchase": purchase, "lines": lines, "actor_id": actor_id})
            raise InventoryOperationError(
                "La ubicación debe estar activa y pertenecer al almacén de esta compra.",
                code="purchase_receipt_location_invalid",
                status_code=409,
            )

    inventory = RejectingInventoryGateway(None)
    use_cases = PurchaseUseCases(purchases, orders, inventory)

    with pytest.raises(ConflictError) as error:
        await use_cases.verify_purchase(
            ids["company"],
            purchase.id,
            lines=(
                PurchaseVerificationLine(
                    purchase_detail_id=purchase.details[0].id,
                    quantity_accepted=Decimal("1"),
                    inventory_location_id=uuid.uuid4(),
                ),
            ),
            actor_id=ids["user"],
        )

    assert error.value.code == "purchase_receipt_location_invalid"
    assert inventory.calls
    assert purchases.items[purchase.id].status is PurchaseStatus.RECEIVED
    assert purchases.items[purchase.id].details[0].quantity_accepted is None
    assert orders.order.status is PurchaseOrderStatus.SENT
