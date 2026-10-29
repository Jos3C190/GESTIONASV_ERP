"""Safety checks for the purchase-to-inventory boundary."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from app.domain.entities.inventory import (
    InventoryItem,
    InventoryOperationError,
    PackagingDefinition,
    PackagingType,
    PhysicalMeasures,
)
from app.domain.entities.purchase import (
    Purchase,
    PurchaseDetail,
    PurchaseStatus,
    PurchaseVerificationLine,
)
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.repositories.purchase_inventory_gateway import (
    SqlAlchemyPurchaseInventoryGateway,
)

pytestmark = pytest.mark.unit


class _FakeReceiptSession:
    def __init__(
        self,
        location_result: uuid.UUID | None,
        *,
        existing_lot: InventoryLotModel | None = None,
        lot_details: list[InventoryLotDetailModel] | None = None,
        valuation_currency: str | None = None,
    ) -> None:
        self.location_result = location_result
        self.valuation_currency = valuation_currency
        self.existing_lot = existing_lot
        self.lot_details = lot_details or []
        self.statements: list[Any] = []
        self.added: list[object] = []

    async def scalar(self, statement: Any) -> Any:
        self.statements.append(statement)
        sql = str(statement).lower()
        if "from inventory_valuation_settings" in sql:
            return self.valuation_currency
        if "from locations" in sql:
            return self.location_result
        if "from inventory_lots" in sql:
            return self.existing_lot
        if "from products" in sql:
            return "PRD-HAR-003 — Harina Integral de Trigo 25kg"
        return None

    async def scalars(self, statement: Any) -> Any:
        del statement
        new_lot_details = [row for row in self.added if isinstance(row, InventoryLotDetailModel)]
        return _FakeScalars([*self.lot_details, *new_lot_details])

    def begin_nested(self) -> _FakeSavepoint:
        return _FakeSavepoint(self)

    def add(self, row: object) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        for row in self.added:
            if getattr(row, "id", None) is None:
                row.id = uuid.uuid4()


class _FakeScalars:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values

    def __iter__(self):
        return iter(self.values)


class _FakeSavepoint:
    def __init__(self, session: _FakeReceiptSession) -> None:
        self.session = session
        self.initial_added_count = len(session.added)

    async def __aenter__(self) -> _FakeSavepoint:
        return self

    async def __aexit__(self, exception_type: Any, *_args: object) -> bool:
        if exception_type is not None:
            del self.session.added[self.initial_added_count :]
        return False


class _FakeInventoryRepository:
    def __init__(self, item: InventoryItem | None) -> None:
        self.item = item
        self.item_lookups = 0
        self.packaging_lookups = 0
        self.packaging: list[PackagingDefinition] = []
        self.movements: list[dict[str, object]] = []

    async def get_item_by_target(self, **_kwargs: object) -> InventoryItem | None:
        self.item_lookups += 1
        return self.item

    async def list_packaging(
        self, _company_id: uuid.UUID, _item_id: uuid.UUID
    ) -> list[PackagingDefinition]:
        self.packaging_lookups += 1
        return self.packaging

    async def post_movement(self, **movement: object) -> dict[str, object]:
        self.movements.append(movement)
        return {"id": uuid.uuid4()}


class _FailingInventoryRepository(_FakeInventoryRepository):
    async def post_movement(self, **_movement: object) -> dict[str, object]:
        raise InventoryOperationError("La recepción fue rechazada.", code="capacity_exceeded")


def _purchase() -> Purchase:
    purchase_id = uuid.uuid4()
    detail = PurchaseDetail(
        id=uuid.uuid4(),
        purchase_id=purchase_id,
        purchase_order_detail_id=uuid.uuid4(),
        product_id=5,
        quantity_ordered=Decimal("2"),
        quantity_received=Decimal("1"),
        unit_id=2,
        unit_price=Decimal("10"),
    )
    return Purchase(
        id=purchase_id,
        company_id=uuid.uuid4(),
        code="COM-TEST-0001",
        purchase_order_id=uuid.uuid4(),
        supplier_id=4,
        branch_id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        created_by_id=uuid.uuid4(),
        purchase_date=datetime.now(UTC),
        currency="USD",
        details=(detail,),
        status=PurchaseStatus.RECEIVED,
    )


@pytest.mark.asyncio
async def test_receipt_from_location_outside_purchase_warehouse_is_rejected_without_writes() -> (
    None
):
    purchase = _purchase()
    location_id = uuid.uuid4()
    session = _FakeReceiptSession(location_result=None)
    inventory = _FakeInventoryRepository(item=None)
    gateway = SqlAlchemyPurchaseInventoryGateway(session)  # type: ignore[arg-type]
    gateway._inventory = inventory  # type: ignore[assignment]

    with pytest.raises(InventoryOperationError) as error:
        await gateway.post_verified_receipt(
            purchase=purchase,
            lines=(
                PurchaseVerificationLine(
                    purchase_detail_id=purchase.details[0].id,
                    quantity_accepted=Decimal("1"),
                    inventory_location_id=location_id,
                ),
            ),
            actor_id=uuid.uuid4(),
        )

    assert error.value.code == "purchase_receipt_location_invalid"
    # The query is scoped to the purchase warehouse, company and active location.
    location_query = next(
        query for query in session.statements if "from locations" in str(query).lower()
    )
    compiled_params = location_query.compile().params.values()
    assert purchase.warehouse_id in compiled_params
    assert inventory.item_lookups == 0
    assert inventory.movements == []
    assert session.added == []


@pytest.mark.asyncio
async def test_receipt_without_required_unit_conversion_is_rejected_without_movement() -> None:
    purchase = _purchase()
    item = InventoryItem(
        id=uuid.uuid4(),
        company_id=purchase.company_id,
        product_id=purchase.details[0].product_id,
        variant_id=None,
        base_unit_id=1,
        is_active=True,
    )
    session = _FakeReceiptSession(location_result=uuid.uuid4())
    inventory = _FakeInventoryRepository(item=item)
    gateway = SqlAlchemyPurchaseInventoryGateway(session)  # type: ignore[arg-type]
    gateway._inventory = inventory  # type: ignore[assignment]

    with pytest.raises(InventoryOperationError) as error:
        await gateway.post_verified_receipt(
            purchase=purchase,
            lines=(
                PurchaseVerificationLine(
                    purchase_detail_id=purchase.details[0].id,
                    quantity_accepted=Decimal("1"),
                    inventory_location_id=uuid.uuid4(),
                ),
            ),
            actor_id=uuid.uuid4(),
        )

    assert error.value.code == "purchase_receipt_unit_conversion_missing"
    assert "PRD-HAR-003 — Harina Integral de Trigo 25kg" in str(error.value)
    assert "Productos → Empaques y presentaciones" in str(error.value)
    label_query = next(
        query for query in session.statements if "from products" in str(query).lower()
    )
    assert purchase.company_id in label_query.compile().params.values()
    assert purchase.details[0].product_id in label_query.compile().params.values()
    assert inventory.item_lookups == 1
    assert inventory.packaging_lookups == 1
    assert inventory.movements == []
    assert session.added == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("factor", "accepted", "expected"),
    [("0.040000", "100", "4.000000"), ("0.044092", "100", "4.409200")],
)
async def test_kilogram_presentations_convert_without_changing_receipt_quantity(
    factor: str, accepted: str, expected: str
) -> None:
    purchase = _purchase()
    item = InventoryItem(
        id=uuid.uuid4(),
        company_id=purchase.company_id,
        product_id=purchase.details[0].product_id,
        variant_id=None,
        base_unit_id=1,
        is_active=True,
    )
    session = _FakeReceiptSession(location_result=uuid.uuid4())
    inventory = _FakeInventoryRepository(item=item)
    definition = PackagingDefinition(
        id=uuid.uuid4(),
        company_id=purchase.company_id,
        inventory_item_id=item.id,
        code="KG-DEMO",
        name="Compra por kilogramo",
        packaging_type=PackagingType.LOOSE_OTHER,
        packaging_unit_id=purchase.details[0].unit_id,
        version=1,
        base_quantity=Decimal(factor),
        measures=PhysicalMeasures(
            gross_weight_kg=Decimal("1"),
            length_m=None,
            width_m=None,
            height_m=None,
            volume_m3=Decimal("0.002"),
        ),
        stackable=False,
        max_stack=None,
        is_current=True,
        is_active=True,
    )
    inventory.packaging = [definition]
    gateway = SqlAlchemyPurchaseInventoryGateway(session)  # type: ignore[arg-type]
    gateway._inventory = inventory  # type: ignore[assignment]

    result, packaging_id = await gateway._quantity_in_base_unit(
        company_id=purchase.company_id,
        product_id=purchase.details[0].product_id,
        received_unit_id=purchase.details[0].unit_id,
        item=item,
        accepted_quantity=Decimal(accepted),
    )

    assert result == Decimal(expected)
    assert packaging_id == definition.id
    assert purchase.details[0].quantity_received == Decimal("1")
    assert session.added == []
    assert inventory.movements == []


@pytest.mark.asyncio
async def test_receipt_split_posts_each_part_as_its_own_inventory_movement_line() -> None:
    purchase = _purchase()
    location_id = uuid.uuid4()
    item = InventoryItem(
        id=uuid.uuid4(),
        company_id=purchase.company_id,
        product_id=purchase.details[0].product_id,
        variant_id=None,
        base_unit_id=purchase.details[0].unit_id,
        is_active=True,
    )
    session = _FakeReceiptSession(location_result=location_id)
    inventory = _FakeInventoryRepository(item=item)
    gateway = SqlAlchemyPurchaseInventoryGateway(session)  # type: ignore[arg-type]
    gateway._inventory = inventory  # type: ignore[assignment]

    movement_id = await gateway.post_verified_receipt(
        purchase=purchase,
        lines=(
            PurchaseVerificationLine(purchase.details[0].id, Decimal("0.6"), location_id),
            PurchaseVerificationLine(purchase.details[0].id, Decimal("0.4"), location_id),
        ),
        actor_id=uuid.uuid4(),
    )

    assert movement_id is not None
    movement_lines = inventory.movements[0]["lines"]
    assert isinstance(movement_lines, list)
    assert [line["quantity_base"] for line in movement_lines] == [
        Decimal("0.6"),
        Decimal("0.4"),
    ]
    assert len(movement_lines) == 2
    assert all(line["purchase_detail_id"] == purchase.details[0].id for line in movement_lines)
    lot = next(row for row in session.added if isinstance(row, InventoryLotModel))
    lot_details = [row for row in session.added if isinstance(row, InventoryLotDetailModel)]
    assert lot.code == f"LOT-{purchase.code}"
    assert lot.purchase_id == purchase.id
    assert len(lot_details) == 1
    assert lot_details[0].accepted_quantity_base == Decimal("1.0")
    assert all(line["inventory_lot_id"] == lot.id for line in movement_lines)
    assert all(line["valuation_currency"] == purchase.currency for line in movement_lines)
    assert (
        sum(line["valuation_value"] for line in movement_lines)
        == purchase.details[0].subtotal - purchase.details[0].discount
    )


@pytest.mark.asyncio
async def test_receipt_retry_reuses_existing_lot_without_duplicating_details() -> None:
    purchase = _purchase()
    item = InventoryItem(
        id=uuid.uuid4(),
        company_id=purchase.company_id,
        product_id=purchase.details[0].product_id,
        variant_id=None,
        base_unit_id=purchase.details[0].unit_id,
        is_active=True,
    )
    lot = InventoryLotModel(
        company_id=purchase.company_id,
        purchase_id=purchase.id,
        code=f"LOT-{purchase.code}",
        received_at=datetime.now(UTC),
        created_by_id=uuid.uuid4(),
    )
    lot.id = uuid.uuid4()
    detail = InventoryLotDetailModel(
        company_id=purchase.company_id,
        inventory_lot_id=lot.id,
        purchase_detail_id=purchase.details[0].id,
        inventory_item_id=item.id,
        product_id=purchase.details[0].product_id,
        base_unit_id=item.base_unit_id,
        quantity_received=purchase.details[0].quantity_received,
        quantity_accepted=Decimal("1"),
        accepted_quantity_base=Decimal("1"),
    )
    detail.id = uuid.uuid4()
    session = _FakeReceiptSession(
        location_result=uuid.uuid4(), existing_lot=lot, lot_details=[detail]
    )
    inventory = _FakeInventoryRepository(item=item)
    gateway = SqlAlchemyPurchaseInventoryGateway(session)  # type: ignore[arg-type]
    gateway._inventory = inventory  # type: ignore[assignment]

    movement_id = await gateway.post_verified_receipt(
        purchase=purchase,
        lines=(PurchaseVerificationLine(purchase.details[0].id, Decimal("1"), uuid.uuid4()),),
        actor_id=uuid.uuid4(),
    )

    assert movement_id is not None
    assert session.added == []
    assert inventory.movements[0]["lines"][0]["inventory_lot_id"] == lot.id
    assert inventory.movements[0]["lines"][0]["inventory_lot_detail_id"] == detail.id


@pytest.mark.asyncio
async def test_failed_inventory_movement_rolls_back_new_receipt_lot() -> None:
    purchase = _purchase()
    item = InventoryItem(
        id=uuid.uuid4(),
        company_id=purchase.company_id,
        product_id=purchase.details[0].product_id,
        variant_id=None,
        base_unit_id=purchase.details[0].unit_id,
        is_active=True,
    )
    session = _FakeReceiptSession(location_result=uuid.uuid4())
    inventory = _FailingInventoryRepository(item=item)
    gateway = SqlAlchemyPurchaseInventoryGateway(session)  # type: ignore[arg-type]
    gateway._inventory = inventory  # type: ignore[assignment]

    with pytest.raises(InventoryOperationError) as error:
        await gateway.post_verified_receipt(
            purchase=purchase,
            lines=(PurchaseVerificationLine(purchase.details[0].id, Decimal("1"), uuid.uuid4()),),
            actor_id=uuid.uuid4(),
        )

    assert error.value.code == "capacity_exceeded"
    assert session.added == []
