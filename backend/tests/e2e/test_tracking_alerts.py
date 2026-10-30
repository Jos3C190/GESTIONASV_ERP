"""Transfer trips: monitor alerts, branch scope, archived trail cut at reception."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.api.v1.transfer_tracking import archive_trip
from app.core.config import settings
from app.infrastructure import tracking_monitor
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.fleet import FleetVehicleModel
from app.infrastructure.models.inventory_transfer import InventoryTransferModel
from app.infrastructure.models.tracking import TrackingAlertModel, TransferTrackModel
from sqlalchemy import select

from tests.e2e import test_fleet_tracking
from tests.e2e.test_fleet_tracking import FakeTraccar
from tests.e2e.test_inventory_transfers import (
    DISPATCH_OVERRIDE,
    _committed_transfer_context,
    _create_preparation,
)

pytestmark = pytest.mark.e2e

traccar = test_fleet_tracking.traccar

#: A point on the road between origin and destination, away from any branch.
ROAD = (-88.6, 13.62)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _position(
    at: datetime, speed_knots: float, point: tuple[float, float] = ROAD
) -> dict[str, Any]:
    return {
        "longitude": point[0],
        "latitude": point[1],
        "speed": speed_knots,
        "course": 90,
        "fixTime": _iso(at),
    }


async def test_monitor_alerts_and_archives_the_trip(
    e2e_client: Any, traccar: FakeTraccar, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "OSRM_URL", None)
    suffix = uuid.uuid4().hex
    values, headers = await _committed_transfer_context(e2e_client, suffix)
    transfer = await _create_preparation(e2e_client, values, headers, f"alert-{suffix[:12]}")
    dispatched = await e2e_client.post(
        f"/api/v1/inventory/transfers/{transfer['id']}/dispatch",
        headers=headers,
        json={
            "vehicle_id": str(values.vehicle_id),
            "idempotency_key": f"alert-dispatch-{suffix}",
            "override_reason": DISPATCH_OVERRIDE,
        },
    )
    assert dispatched.status_code == 200, dispatched.text

    now = datetime.now(UTC)
    device_id = traccar.add_device(f"IMEI{suffix[:10]}")
    async with async_session_factory() as session:
        fleet = await session.scalar(
            select(FleetVehicleModel).where(
                FleetVehicleModel.inventory_vehicle_id == values.vehicle_id
            )
        )
        assert fleet is not None
        fleet.gps_device_unique_id = f"IMEI{suffix[:10]}"
        fleet.traccar_device_id = device_id
        record = await session.get(InventoryTransferModel, uuid.UUID(transfer["id"]))
        assert record is not None
        record.dispatched_at = now - timedelta(minutes=50)
        await session.commit()
    # Avanza 10 minutos y lleva 35 detenido en carretera, lejos de toda sucursal.
    traccar.positions[device_id] = [
        _position(now - timedelta(minutes=48), 25.0, (-88.75, 13.60)),
        _position(now - timedelta(minutes=40), 20.0, (-88.68, 13.61)),
        _position(now - timedelta(minutes=35), 0.5),
        _position(now - timedelta(minutes=20), 0.0),
        _position(now - timedelta(minutes=1), 0.0),
    ]

    await tracking_monitor.run_once()
    alerts = await e2e_client.get("/api/v1/tracking/alerts", headers=headers)
    assert alerts.status_code == 200, alerts.text
    body = alerts.json()
    stop = next(item for item in body["items"] if item["kind"] == "long_stop")
    assert stop["transfer_code"] == transfer["code"]
    assert body["unacknowledged"] >= 1

    # Un segundo ciclo no duplica la alerta abierta.
    await tracking_monitor.run_once()
    async with async_session_factory() as session:
        open_stops = (
            await session.scalars(
                select(TrackingAlertModel).where(
                    TrackingAlertModel.transfer_id == uuid.UUID(transfer["id"]),
                    TrackingAlertModel.kind == "long_stop",
                    TrackingAlertModel.resolved_at.is_(None),
                )
            )
        ).all()
    assert len(open_stops) == 1

    acked = await e2e_client.post(
        f"/api/v1/tracking/alerts/{stop['id']}/acknowledge", headers=headers
    )
    assert acked.status_code == 200, acked.text
    assert acked.json()["acknowledged_at"] is not None

    # Recepción: el recorrido se corta en received_at y queda guardado en el ERP.
    received_at = now - timedelta(minutes=10)
    traccar.positions[device_id].append(_position(now - timedelta(minutes=2), 30.0))
    async with async_session_factory() as session:
        record = await session.get(InventoryTransferModel, uuid.UUID(transfer["id"]))
        assert record is not None
        record.status = "received"
        record.received_at = received_at
        await session.commit()
    await archive_trip(values.company_id, uuid.UUID(transfer["id"]))
    async with async_session_factory() as session:
        track = await session.get(TransferTrackModel, uuid.UUID(transfer["id"]))
        assert track is not None
        assert track.point_count == 4
        assert all(point[2] <= _iso(received_at) for point in track.points)
        still_open = await session.scalar(
            select(TrackingAlertModel.id).where(
                TrackingAlertModel.transfer_id == uuid.UUID(transfer["id"]),
                TrackingAlertModel.resolved_at.is_(None),
            )
        )
        assert still_open is None

    traccar.positions[device_id] = []  # Traccar ya no tiene el historial.
    trip = await e2e_client.get(f"/api/v1/tracking/transfers/{transfer['id']}", headers=headers)
    assert trip.status_code == 200, trip.text
    assert trip.json()["track_stored"] is True
    assert trip.json()["arrived"] is True
    assert len(trip.json()["trail"]) >= 2
