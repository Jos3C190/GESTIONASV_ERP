from datetime import UTC, datetime

from app.application.tracking import build_area, build_events, parse_area, to_geofence


def test_circle_round_trips_with_traccar_lat_lon_order() -> None:
    shape = {"type": "circle", "center": [-88.177, 13.4795], "radius_m": 350}
    area = build_area(shape)
    assert area == "CIRCLE (13.479500 -88.177000, 350.0)"
    assert parse_area(area) == {"type": "circle", "center": [-88.177, 13.4795], "radius_m": 350.0}


def test_polygon_closes_the_ring_for_traccar_and_reopens_it_for_the_erp() -> None:
    coordinates = [[-88.2, 13.5], [-88.1, 13.5], [-88.1, 13.4]]
    area = build_area({"type": "polygon", "coordinates": coordinates})
    assert area.startswith("POLYGON ((13.500000 -88.200000, ")
    assert area.endswith("13.500000 -88.200000))")
    assert parse_area(area) == {"type": "polygon", "coordinates": coordinates}


def test_unsupported_areas_are_skipped() -> None:
    assert parse_area("LINESTRING (1 2, 3 4)") is None
    assert to_geofence({"id": 1, "name": "x", "area": "LINESTRING (1 2, 3 4)"}) is None


def test_geofence_speed_limit_is_reported_in_kmh() -> None:
    geofence = to_geofence(
        {
            "id": 4,
            "name": "Centro",
            "area": "CIRCLE (13.48 -88.18, 300)",
            "attributes": {"speedLimit": 16.2},
        }
    )
    assert geofence is not None
    assert geofence["speed_limit_kmh"] == 30


def test_events_are_filtered_enriched_and_sorted_newest_first() -> None:
    devices = {1: {"id": 1, "name": "FL-001", "uniqueId": "imei-1"}}
    events = [
        {"id": 10, "type": "deviceOnline", "deviceId": 1, "eventTime": "2026-10-28T10:00:00Z"},
        {
            "id": 11,
            "type": "geofenceEnter",
            "deviceId": 1,
            "geofenceId": 4,
            "positionId": 99,
            "eventTime": "2026-10-28T10:05:00Z",
        },
        {"id": 12, "type": "ignitionOff", "deviceId": 1, "eventTime": "2026-10-28T11:00:00Z"},
        {"id": 13, "type": "ignitionOn", "deviceId": 2, "eventTime": "2026-10-28T11:30:00Z"},
    ]
    positions = {99: {"id": 99, "latitude": 13.48, "longitude": -88.18, "speed": 10}}
    result = build_events(events, devices, {4: "Centro de distribución"}, positions)
    assert [item["id"] for item in result] == [12, 11]
    enter = result[1]
    assert enter["geofence_name"] == "Centro de distribución"
    assert enter["speed_kmh"] == 18.5
    assert enter["event_time"] == datetime(2026, 10, 28, 10, 5, tzinfo=UTC)
    assert result[0]["latitude"] is None
