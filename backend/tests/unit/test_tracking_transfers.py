from datetime import UTC, datetime

import pytest
from app.application.tracking.transfers import (
    ARRIVAL_RADIUS_M,
    build_transfer_progress,
    distance_m,
    downsample,
    locate_on_route,
    plan_route,
    straight_route,
)

ROOSEVELT = (-88.185666, 13.483663)
SANTA_ROSA = (-87.89288, 13.62781)
NOW = datetime(2026, 10, 28, 15, 0, tzinfo=UTC)


def _position(lng: float, lat: float, speed_knots: float = 27.0) -> dict[str, object]:
    return {
        "longitude": lng,
        "latitude": lat,
        "speed": speed_knots,
        "course": 60,
        "fixTime": "2026-10-28T14:59:50Z",
    }


def test_halfway_position_reports_progress_and_eta() -> None:
    route = straight_route(ROOSEVELT, SANTA_ROSA)
    mid = ((ROOSEVELT[0] + SANTA_ROSA[0]) / 2, (ROOSEVELT[1] + SANTA_ROSA[1]) / 2)
    result = build_transfer_progress(
        route=route,
        destination=SANTA_ROSA,
        positions=[_position(*ROOSEVELT), _position(*mid)],
        now=NOW,
    )
    assert result["progress"] == pytest.approx(0.5, abs=0.01)
    assert result["remaining_m"] == pytest.approx(route["distance_m"] / 2, rel=0.02)
    assert result["eta"] > NOW
    assert result["position"]["speed_kmh"] == 50.0
    assert len(result["trail"]) == 2
    assert result["arrived"] is False
    assert result["off_route"] is False


def test_position_near_destination_counts_as_arrived() -> None:
    route = straight_route(ROOSEVELT, SANTA_ROSA)
    near = (SANTA_ROSA[0] + 0.001, SANTA_ROSA[1])
    assert distance_m(near, SANTA_ROSA) < ARRIVAL_RADIUS_M
    result = build_transfer_progress(
        route=route, destination=SANTA_ROSA, positions=[_position(*near, 0)], now=NOW
    )
    assert result["arrived"] is True
    assert result["progress"] == 1.0
    assert result["eta"] is None


def test_detects_deviation_from_the_planned_route() -> None:
    route = straight_route(ROOSEVELT, SANTA_ROSA)
    away = (-88.05, 13.45)  # unos 10 km al sur de la línea
    result = build_transfer_progress(
        route=route, destination=SANTA_ROSA, positions=[_position(*away)], now=NOW
    )
    assert result["off_route"] is True
    assert result["off_route_m"] > 1000


def test_without_positions_only_the_route_is_known() -> None:
    route = straight_route(ROOSEVELT, SANTA_ROSA)
    result = build_transfer_progress(route=route, destination=SANTA_ROSA, positions=[], now=NOW)
    assert result["position"] is None
    assert result["progress"] == 0.0
    assert result["remaining_m"] == route["distance_m"]


def test_locate_on_route_follows_polyline_segments() -> None:
    route = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
    along, lateral = locate_on_route((0.5, 1.0), route)
    assert along == pytest.approx(
        distance_m((0, 0), (0, 1)) + distance_m((0, 1), (0.5, 1)), rel=0.01
    )
    assert lateral == pytest.approx(0, abs=1)


def test_downsample_keeps_ends() -> None:
    points = [(float(i), 0.0) for i in range(1000)]
    sampled = downsample(points, 100)
    assert len(sampled) == 100
    assert sampled[0] == points[0]
    assert sampled[-1] == points[-1]


async def test_plan_route_without_service_is_a_straight_line() -> None:
    route = await plan_route(None, ROOSEVELT, SANTA_ROSA)
    assert route["source"] == "straight"
    assert route["coordinates"] == [list(ROOSEVELT), list(SANTA_ROSA)]
