"""The transfer vehicle catalogue follows Fleet, the owner of the vehicle records."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.fleet import FleetVehicleModel
from sqlalchemy import select

from tests.e2e.test_inventory_transfers import _committed_transfer_context

pytestmark = pytest.mark.e2e

CATALOG = "/api/v1/inventory/transfers/vehicles"


async def test_catalog_hides_deleted_fleet_vehicles_and_links_pending_ones(
    e2e_client: Any,
) -> None:
    suffix = uuid.uuid4().hex
    values, headers = await _committed_transfer_context(e2e_client, suffix)

    listed = await e2e_client.get(CATALOG, headers=headers)
    assert listed.status_code == 200, listed.text
    assert str(values.vehicle_id) in {item["id"] for item in listed.json()}

    pending_code = f"PD-{suffix[:8].upper()}"
    async with async_session_factory() as session:
        linked = await session.scalar(
            select(FleetVehicleModel).where(
                FleetVehicleModel.company_id == values.company_id,
                FleetVehicleModel.inventory_vehicle_id == values.vehicle_id,
            )
        )
        assert linked is not None
        # A vehicle registered before the company had a transit warehouse (as the
        # seeded ones were) has no transit location yet.
        session.add(
            FleetVehicleModel(
                company_id=values.company_id,
                branch_id=linked.branch_id,
                code=pending_code,
                plate=f"Q{suffix[:7].upper()}",
                kind="cargo_van",
                brand="Toyota",
                model="Hiace",
                year=2024,
                capacity_kg=Decimal("1500"),
                fuel_type="diesel",
                odometer_km=Decimal("1000"),
            )
        )
        linked.deleted_at = datetime.now(UTC)
        await session.commit()

    refreshed = await e2e_client.get(CATALOG, headers=headers)
    assert refreshed.status_code == 200, refreshed.text
    items = refreshed.json()
    assert str(values.vehicle_id) not in {item["id"] for item in items}
    assert pending_code in {item["code"] for item in items}

    async with async_session_factory() as session:
        pending = await session.scalar(
            select(FleetVehicleModel).where(
                FleetVehicleModel.company_id == values.company_id,
                FleetVehicleModel.code == pending_code,
            )
        )
        assert pending is not None
        assert pending.inventory_vehicle_id is not None
