"""Pure rules of the tracking simulator: motion, holds, reports, expiry, OsmAnd."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.application.tracking.simulation import (
    IDLE_TIMEOUT,
    MAX_SESSION,
    PARKED_REPORT_S,
    SimSnapshot,
    bearing,
    detour_waypoint,
    expiry_reason,
    is_simulator_unique_id,
    osmand_params,
    osmand_url,
    path_length,
    plausible_drive,
    point_at,
    step,
    turns_between,
    unique_id_for,
)
from app.application.tracking.transfers import distance_m, locate_on_route

NOW = datetime(2026, 10, 30, 15, 0, tzinfo=UTC)
#: About 1.1 km heading east, then 1.1 km heading north.
ROUTE = [(-88.20, 13.48), (-88.19, 13.48), (-88.19, 13.49)]


def _snapshot(**overrides: object) -> SimSnapshot:
    base = SimSnapshot(
        mode="route",
        state="running",
        route=ROUTE,
        route_length_m=path_length(ROUTE),
        progress_m=0.0,
        speed_kmh=60.0,
        current_speed_kmh=0.0,
        position=ROUTE[0],
        course=0.0,
        stop_until=None,
        signal_lost_until=None,
        last_report_at=None,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def _run(snapshot: SimSnapshot, seconds: int, dt: float = 1.0) -> SimSnapshot:
    moment = NOW
    for _ in range(int(seconds / dt)):
        moment += timedelta(seconds=dt)
        result = step(snapshot, moment, dt)
        snapshot = replace(
            snapshot,
            state=result.state,
            progress_m=result.progress_m,
            position=result.position,
            course=result.course,
            current_speed_kmh=result.current_speed_kmh,
            stop_until=result.stop_until,
            signal_lost_until=result.signal_lost_until,
            last_report_at=moment if result.report else snapshot.last_report_at,
        )
    return snapshot


def test_point_at_walks_the_route_with_its_heading() -> None:
    point, course = point_at(ROUTE, 0)
    assert point == ROUTE[0]
    assert course == pytest.approx(90, abs=1)
    corner = distance_m(ROUTE[0], ROUTE[1])
    point, course = point_at(ROUTE, corner + 100)
    assert course == pytest.approx(0, abs=1)
    assert point[0] == pytest.approx(-88.19)
    end, _ = point_at(ROUTE, path_length(ROUTE) + 500)
    assert end == ROUTE[-1]


def test_unit_accelerates_like_a_vehicle_and_keeps_the_target_speed() -> None:
    moved = _run(_snapshot(), 2)
    assert 0 < moved.current_speed_kmh <= 24.1
    cruising = _run(_snapshot(), 8)
    assert cruising.current_speed_kmh == pytest.approx(60, abs=0.1)
    # Avanza sobre la ruta, nunca fuera de ella.
    _, offset = locate_on_route(cruising.position, ROUTE)
    assert offset < 1


def test_unit_brakes_into_the_destination_and_arrives() -> None:
    arrived = _run(_snapshot(), 400)
    assert arrived.state == "arrived"
    assert arrived.progress_m == pytest.approx(path_length(ROUTE))
    assert arrived.current_speed_kmh == 0
    assert arrived.position == ROUTE[-1]


def test_pause_and_timed_stop_hold_the_unit_until_they_end() -> None:
    cruising = _run(_snapshot(), 10)
    paused = _run(replace(cruising, state="paused"), 10)
    assert paused.current_speed_kmh == 0
    assert paused.state == "paused"
    held = paused.progress_m
    assert _run(paused, 20).progress_m == pytest.approx(held)

    stopped = replace(cruising, stop_until=NOW + timedelta(seconds=5))
    after = _run(stopped, 30)
    assert after.stop_until is None
    assert after.current_speed_kmh > 0
    assert after.progress_m > stopped.progress_m


def test_signal_loss_suppresses_reports_and_restoring_reports_at_once() -> None:
    lost = _snapshot(signal_lost_until=NOW + timedelta(seconds=30), last_report_at=NOW)
    for second in range(1, 30):
        assert not step(lost, NOW + timedelta(seconds=second), 1.0).report
    back = step(lost, NOW + timedelta(seconds=31), 1.0)
    assert back.report
    assert back.signal_lost_until is None


def test_parked_units_send_a_heartbeat_and_moving_ones_report_often() -> None:
    parked = _snapshot(state="arrived", last_report_at=NOW)
    assert not step(parked, NOW + timedelta(seconds=10), 1.0).report
    assert step(parked, NOW + timedelta(seconds=PARKED_REPORT_S), 1.0).report
    moving = _snapshot(current_speed_kmh=60, last_report_at=NOW)
    assert step(moving, NOW + timedelta(seconds=3), 1.0).report


def test_joystick_sessions_are_kept_alive_without_moving() -> None:
    joystick = _snapshot(
        mode="joystick", route=[], route_length_m=0, current_speed_kmh=30, last_report_at=NOW
    )
    result = step(joystick, NOW + timedelta(seconds=PARKED_REPORT_S + 1), 2.0)
    assert result.position == joystick.position
    assert result.current_speed_kmh == 0  # Sin órdenes del joystick, la unidad está detenida.
    assert result.report


def test_corners_crossed_on_a_tick_are_reported_in_order() -> None:
    corner = distance_m(ROUTE[0], ROUTE[1])
    assert [vertex for _, vertex, _ in turns_between(ROUTE, 0, corner + 50)] == [ROUTE[1]]
    assert turns_between(ROUTE, 0, corner - 50) == []
    before = _snapshot(progress_m=corner - 20, current_speed_kmh=60, last_report_at=NOW)
    result = step(before, NOW + timedelta(seconds=2), 2.0)
    assert result.report  # Aunque no tocaba reportar, cruzar la esquina lo exige.
    [(vertex, course, fraction)] = result.corners
    assert vertex == ROUTE[1]
    assert course == pytest.approx(0, abs=1)
    assert 0 < fraction < 1
    lost = replace(before, signal_lost_until=NOW + timedelta(minutes=1))
    assert step(lost, NOW + timedelta(seconds=2), 2.0).corners == ()


def test_detour_point_is_beside_the_road_ahead() -> None:
    waypoint = detour_waypoint(ROUTE, 0)
    assert waypoint is not None
    _, offset = locate_on_route(waypoint, ROUTE)
    assert offset > 500
    assert detour_waypoint(ROUTE, path_length(ROUTE) - 50) is None


def test_sessions_expire_when_idle_or_too_long() -> None:
    assert expiry_reason(NOW, NOW, NOW + timedelta(minutes=10)) is None
    assert expiry_reason(NOW, NOW, NOW + IDLE_TIMEOUT) is not None
    busy = NOW + MAX_SESSION
    assert expiry_reason(NOW, busy, busy) is not None


def test_joystick_reports_cannot_teleport() -> None:
    start = (-88.2, 13.48)
    near = (-88.199, 13.48)
    assert plausible_drive(start, NOW, near, NOW + timedelta(seconds=1))
    far = (-88.1, 13.48)
    assert not plausible_drive(start, NOW, far, NOW + timedelta(seconds=1))
    assert not plausible_drive(start, None, (-87.5, 13.48), NOW)


def test_osmand_report_and_receiver_url() -> None:
    params = osmand_params("erp-sim-x", (-88.2, 13.48), NOW, 92.6, 370)
    assert params["id"] == "erp-sim-x"
    assert params["lat"] == "13.480000"
    assert params["speed"] == "50.00"  # nudos
    assert params["bearing"] == "10.0"
    assert params["timestamp"] == str(int(NOW.timestamp() * 1000))
    assert osmand_url(None, "http://traccar:8082") == "http://traccar:5055"
    assert osmand_url("http://gps.test:9000/", "http://traccar:8082") == "http://gps.test:9000"
    assert osmand_url(None, None) is None


def test_virtual_device_ids_are_stable_and_reserved() -> None:
    vehicle = uuid.uuid4()
    assert unique_id_for(vehicle) == unique_id_for(vehicle)
    assert is_simulator_unique_id(unique_id_for(vehicle))
    assert not is_simulator_unique_id("356938035643809")
    assert bearing((0, 0), (0, 1)) == pytest.approx(0)
