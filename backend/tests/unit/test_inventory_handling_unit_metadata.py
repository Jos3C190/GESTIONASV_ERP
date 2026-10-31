from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from app.infrastructure.models.inventory_lot import InventoryLotModel
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository

pytestmark = pytest.mark.unit


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _AvailableHandlingUnitSession:
    def __init__(self, lot: InventoryLotModel, purchase_code: str) -> None:
        self.lot = lot
        self.purchase_code = purchase_code

    async def scalars(self, _statement):
        return _Rows([self.lot])

    async def execute(self, _statement):
        return _Rows([(self.lot.purchase_id, self.purchase_code)])


@pytest.mark.asyncio
async def test_available_handling_unit_includes_its_receipt_lot_metadata() -> None:
    company_id = uuid.uuid4()
    purchase_id = uuid.uuid4()
    handling_unit_id = uuid.uuid4()
    lot = InventoryLotModel(
        company_id=company_id,
        purchase_id=purchase_id,
        code="LOT-COM-00017",
        received_at=datetime.now(UTC),
        created_by_id=uuid.uuid4(),
    )
    lot.id = uuid.uuid4()
    unit = SimpleNamespace(
        id=handling_unit_id,
        inventory_lot_id=lot.id,
        inventory_lot_detail_id=None,
        stock_status="available",
        closed_at=None,
    )
    repository = SqlAlchemyInventoryRepository(
        _AvailableHandlingUnitSession(lot, "COM-00017")  # type: ignore[arg-type]
    )

    (
        release_requirements,
        lots_by_id,
        purchase_codes,
        detail_codes,
    ) = await repository._handling_unit_release_metadata(company_id=company_id, rows=[unit])

    assert release_requirements == {}
    assert lots_by_id[lot.id].code == "LOT-COM-00017"
    assert purchase_codes[purchase_id] == "COM-00017"
    assert detail_codes == {}
