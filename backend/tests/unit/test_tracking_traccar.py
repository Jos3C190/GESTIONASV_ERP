from datetime import UTC, datetime

from app.application.tracking import build_tracked_devices

COMPANY = "8f6c1a52-3d0b-4c39-9a51-1e2f5f7a9b10"


def _device(device_id: int, name: str, company: str | None = COMPANY) -> dict[str, object]:
    attributes = {"erpCompanyId": company} if company else {}
    return {
        "id": device_id,
        "uniqueId": f"imei-{device_id}",
        "name": name,
        "status": "online",
        "lastUpdate": "2026-10-28T15:30:00.000+00:00",
        "attributes": attributes,
    }


def test_keeps_only_devices_of_the_requested_company() -> None:
    devices = [
        _device(1, "FL-001"),
        _device(2, "Otra empresa", "other"),
        _device(3, "Sin dueño", None),
    ]
    tracked = build_tracked_devices(devices, [], COMPANY.upper())
    assert [item["name"] for item in tracked] == ["FL-001"]
    assert tracked[0]["position"] is None
    assert tracked[0]["last_update"] == datetime(2026, 10, 28, 15, 30, tzinfo=UTC)


def test_joins_latest_position_and_converts_speed_to_kmh() -> None:
    positions = [
        {
            "deviceId": 1,
            "latitude": 13.48,
            "longitude": -88.18,
            "speed": 27.0,
            "course": 90,
            "fixTime": "2026-10-28T15:29:58Z",
            "address": None,
            "attributes": {"ignition": True, "batteryLevel": 81},
        }
    ]
    position = build_tracked_devices([_device(1, "FL-001")], positions, COMPANY)[0]["position"]
    assert position["speed_kmh"] == 50.0
    assert position["course"] == 90.0
    assert position["ignition"] is True
    assert position["battery_level"] == 81
    assert position["fix_time"] == datetime(2026, 10, 28, 15, 29, 58, tzinfo=UTC)
