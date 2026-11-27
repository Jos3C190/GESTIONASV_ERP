"""V6b: el motor de inventario vende por pieza solo desde una unidad abierta en la vitrina.

Una salida parcial en su lugar (``shipment`` o ``adjustment_out``) desde una unidad abierta en una
ubicación ``showcase`` descuenta la cantidad de la misma unidad y se valora al costo promedio; la
unidad se cierra al llegar a cero. Fuera de la vitrina las reglas de siempre no cambian.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.application.inventory import InventoryUseCases
from app.domain.entities.inventory import InventoryOperationError
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.inventory import (
    InventoryHandlingUnitModel,
    InventoryMovementLineModel,
)
from app.infrastructure.models.inventory_valuation import InventoryValuationEntryModel
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from httpx import AsyncClient
from sqlalchemy import select, text

from tests.e2e.test_sales_orders import _stock
from tests.e2e.test_sales_quotations import _setup

pytestmark = pytest.mark.e2e


async def _post(
    company_id: uuid.UUID, actor_id: uuid.UUID, movement_type: str, lines: list[dict]
) -> dict:
    async with async_session_factory() as session:
        result = await InventoryUseCases(SqlAlchemyInventoryRepository(session)).post_movement(
            company_id=company_id,
            actor_id=actor_id,
            movement_type=movement_type,
            idempotency_key=f"vitrina-{uuid.uuid4()}",
            source_reference="V6b: prueba del motor",
            lines=lines,
        )
        await session.commit()
        return result


async def _unit(company_id: uuid.UUID, item_id: uuid.UUID) -> InventoryHandlingUnitModel:
    async with async_session_factory() as session:
        unit = await session.scalar(
            select(InventoryHandlingUnitModel)
            .where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.inventory_item_id == item_id,
            )
            .order_by(InventoryHandlingUnitModel.created_at.desc())
            .limit(1)
        )
        assert unit is not None
        return unit


async def test_partial_issue_only_from_an_opened_showcase_unit(e2e_client: AsyncClient) -> None:
    admin, body, _ = await _setup(e2e_client)
    company_id = uuid.UUID(admin["X-Company-ID"])
    item_id = await _stock(admin, body, "10")
    unit = await _unit(company_id, item_id)
    async with async_session_factory() as session:
        actor_id = await session.scalar(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))

    def issue(movement_type: str, quantity: str, location_id: uuid.UUID) -> list[dict]:
        return [
            {
                "inventory_item_id": item_id,
                "handling_unit_id": unit.id,
                "from_location_id": location_id,
                "from_stock_status": "available",
                "to_location_id": None,
                "to_stock_status": None,
                "quantity_base": quantity,
            }
        ]

    # Fuera de la vitrina una venta parcial sigue prohibida.
    with pytest.raises(InventoryOperationError) as outside:
        await _post(company_id, actor_id, "shipment", issue("shipment", "3", unit.location_id))
    assert outside.value.code == "partial_handling_unit_transfer_only"

    # Vitrina en la misma bodega; la unidad completa pasa a ella y se abre.
    async with async_session_factory() as session:
        showcase = await session.scalar(
            text(
                "INSERT INTO locations (id, warehouse_id, code, aisle, rack, level, position, "
                "location_type, created_at, updated_at) VALUES (gen_random_uuid(), :w, 'VIT-E2E', "
                "'V', '1', '1', '1', 'showcase', now(), now()) RETURNING id"
            ),
            {"w": unit.warehouse_id},
        )
        await session.commit()
    await _post(
        company_id,
        actor_id,
        "transfer",
        [
            {
                "inventory_item_id": item_id,
                "handling_unit_id": unit.id,
                "from_location_id": unit.location_id,
                "from_stock_status": "available",
                "to_location_id": showcase,
                "to_stock_status": "available",
                "quantity_base": "10",
            }
        ],
    )
    # En vitrina pero sin abrir: todavía es una caja cerrada.
    with pytest.raises(InventoryOperationError) as closed_box:
        await _post(company_id, actor_id, "shipment", issue("shipment", "3", showcase))
    assert closed_box.value.code == "partial_handling_unit_transfer_only"
    async with async_session_factory() as session:
        await session.execute(
            text(
                "UPDATE inventory_handling_units SET opened_at = :now, opened_by_id = :actor "
                "WHERE id = :unit"
            ),
            {"now": datetime.now(UTC), "actor": actor_id, "unit": unit.id},
        )
        await session.commit()

    # Abierta, ya no vuelve a la bodega ni viaja a otra ubicación.
    with pytest.raises(InventoryOperationError) as moved:
        await _post(
            company_id,
            actor_id,
            "transfer",
            [
                {
                    "inventory_item_id": item_id,
                    "handling_unit_id": unit.id,
                    "from_location_id": showcase,
                    "from_stock_status": "available",
                    "to_location_id": unit.location_id,
                    "to_stock_status": "available",
                    "quantity_base": "10",
                }
            ],
        )
    assert moved.value.code == "handling_unit_opened"

    sold = await _post(company_id, actor_id, "shipment", issue("shipment", "3", showcase))
    after = await _unit(company_id, item_id)
    assert after.id == unit.id
    assert Decimal(after.quantity_base) == Decimal("7")
    assert after.closed_at is None
    async with async_session_factory() as session:
        entry = await session.scalar(
            select(InventoryValuationEntryModel)
            .join(
                InventoryMovementLineModel,
                InventoryMovementLineModel.id == InventoryValuationEntryModel.movement_line_id,
            )
            .where(
                InventoryValuationEntryModel.company_id == company_id,
                InventoryMovementLineModel.movement_id == uuid.UUID(str(sold["id"])),
                InventoryValuationEntryModel.kind == "issue",
            )
        )
    assert entry is not None
    assert -Decimal(entry.inventory_delta) == Decimal("21.00")  # 3 piezas a $7.00

    # La merma también sale por pieza, y la última pieza cierra la unidad.
    await _post(company_id, actor_id, "adjustment_out", issue("adjustment_out", "2", showcase))
    await _post(company_id, actor_id, "shipment", issue("shipment", "5", showcase))
    closed = await _unit(company_id, item_id)
    assert Decimal(closed.quantity_base) == Decimal("5")
    assert closed.closed_at is not None
