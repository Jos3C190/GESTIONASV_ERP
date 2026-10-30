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
    assert result["remaining_m"] == round(route["distance_m"])


def test_locate_on_route_follows_polyline_segments() -> None:
    route = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
    along, lateral = locate_on_route((0.5, 1.0), route)
    assert along == pytest.approx(
        distance_m((0, 0), (0, 1)) + distance_m((0, 1), (0.5, 1)), rel=0.01
    )
    assert lateral == pytest.approx(0, abs=1)


def test_downsample_keeps_ends() -> None:
    # Una calle en zigzag: reducirla respeta el límite y conserva los extremos.
    points = [(i * 0.0001, (i % 2) * 0.0001) for i in range(1000)]
    sampled = downsample(points, 100)
    assert len(sampled) <= 100
    assert sampled[0] == points[0]
    assert sampled[-1] == points[-1]


async def test_plan_route_without_service_is_a_straight_line() -> None:
    route = await plan_route(None, ROOSEVELT, SANTA_ROSA)
    assert route["source"] == "straight"
    assert route["coordinates"] == [list(ROOSEVELT), list(SANTA_ROSA)]


# ---------------------------------------------------------------- matching and rerouting

from app.application.tracking import transfers as tr  # noqa: E402


def test_split_route_returns_remaining_geometry_from_projection() -> None:
    route = [(0.0, 0.0), (0.0, 0.01), (0.01, 0.01)]
    along, lateral, remaining = tr.split_route((0.0001, 0.005), route)
    assert along == pytest.approx(distance_m((0, 0), (0, 0.005)), rel=0.01)
    assert lateral == pytest.approx(distance_m((0.0001, 0.005), (0, 0.005)), rel=0.05)
    assert remaining[0] == pytest.approx((0.0, 0.005), abs=1e-6)
    assert remaining[1:] == route[1:]


def test_dedupe_drops_parked_jitter() -> None:
    points = [(0.0, 0.0), (0.00001, 0.0), (0.001, 0.0), (0.00101, 0.0)]
    assert tr.dedupe(points) == [(0.0, 0.0), (0.001, 0.0)]


async def test_match_trail_is_incremental(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def fake_window(
        _base: str, points: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        calls.append(len(points))
        return [(lng, lat + 0.00001) for lng, lat in points]  # "snapped"

    monkeypatch.setattr(tr, "_match_window", fake_window)
    monkeypatch.setattr(tr, "_match_window_size", 100)
    points = [(0.001 * i, 0.0) for i in range(150)]
    geometry, matched = await tr.match_trail("http://osrm", "transfer-a", points[:120])
    assert matched is True
    assert calls == [100, 21]  # dos ventanas que comparten un punto
    geometry, _ = await tr.match_trail("http://osrm", "transfer-a", points)
    assert calls == [100, 21, 31]  # solo los puntos nuevos (+1 de enlace)
    assert len(geometry) == 150


async def test_match_trail_keeps_raw_points_when_matching_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_match(_base: str, _points: list[tuple[float, float]]) -> None:
        return None

    monkeypatch.setattr(tr, "_match_window", no_match)
    points = [(0.001 * i, 0.0) for i in range(5)]
    geometry, matched = await tr.match_trail("http://osrm", "transfer-b", points)
    assert matched is False
    assert geometry == points


async def test_reroutes_once_and_keeps_detour_until_back_on_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planned = straight_route(ROOSEVELT, SANTA_ROSA)
    planned_calls: list[tuple[float, float]] = []

    async def fake_plan(
        _base: str | None, origin: tuple[float, float], destination: tuple[float, float]
    ) -> dict:
        planned_calls.append(origin)
        return straight_route(origin, destination)

    monkeypatch.setattr(tr, "plan_route", fake_plan)
    key = "transfer-c"
    on_route = ((ROOSEVELT[0] + SANTA_ROSA[0]) / 2, (ROOSEVELT[1] + SANTA_ROSA[1]) / 2)
    route, rerouted, _ = await tr.resolve_active_route(
        "http://osrm", key, planned, SANTA_ROSA, on_route
    )
    assert (route, rerouted) == (planned, False)

    away = (-88.05, 13.45)
    route, rerouted, deviation = await tr.resolve_active_route(
        "http://osrm", key, planned, SANTA_ROSA, away
    )
    assert rerouted is True
    assert deviation > tr.OFF_ROUTE_M
    assert route["coordinates"][0] == list(away)

    # Sigue sobre el desvío: no se vuelve a calcular.
    a_bit_further = (
        away[0] + (SANTA_ROSA[0] - away[0]) * 0.05,
        away[1] + (SANTA_ROSA[1] - away[1]) * 0.05,
    )
    route_again, rerouted, _ = await tr.resolve_active_route(
        "http://osrm", key, planned, SANTA_ROSA, a_bit_further
    )
    assert rerouted is True
    assert route_again is route
    assert planned_calls == [away]

    # Regresa a la ruta planeada: se descarta el desvío.
    route, rerouted, _ = await tr.resolve_active_route(
        "http://osrm", key, planned, SANTA_ROSA, on_route
    )
    assert (route, rerouted) == (planned, False)


def test_progress_on_a_detour_uses_the_driven_distance() -> None:
    planned = straight_route(ROOSEVELT, SANTA_ROSA)
    away = (-88.05, 13.45)
    detour = straight_route(away, SANTA_ROSA)
    driven = [ROOSEVELT, away]
    result = build_transfer_progress(
        route=planned,
        destination=SANTA_ROSA,
        positions=[_position(*ROOSEVELT), _position(*away)],
        now=NOW,
        trail=driven,
        active_route=detour,
        rerouted=True,
        deviation_m=10_000,
    )
    travelled = distance_m(ROOSEVELT, away)
    remaining = distance_m(away, SANTA_ROSA)
    assert result["rerouted"] is True
    assert result["off_route"] is False
    assert result["progress"] == pytest.approx(travelled / (travelled + remaining), abs=0.01)
    assert result["remaining_m"] == pytest.approx(remaining, rel=0.01)
    assert result["remaining_route"][0] == pytest.approx(list(away), abs=1e-6)


async def test_match_window_shrinks_when_server_says_too_big(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sizes: list[int] = []

    async def limited(_base: str, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        sizes.append(len(points))
        if len(points) > 10:  # noqa: PLR2004
            raise tr._TooBigError
        return points

    monkeypatch.setattr(tr, "_match_window", limited)
    monkeypatch.setattr(tr, "_match_window_size", 100)
    points = [(0.001 * i, 0.0) for i in range(30)]
    geometry, matched = await tr.match_trail("http://osrm", "transfer-d", points)
    assert matched is True
    assert geometry == points
    assert sizes[:4] == [30, 30, 25, 12]  # 100 → 50 → 25 → 12 → 6
    assert all(size <= 6 for size in sizes[4:])
    assert tr._match_window_size == 6
