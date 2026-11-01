from datetime import UTC, datetime, timedelta

from app.application.tracking.alerts import Fix, TripSnapshot, evaluate_trip, stopped_since

NOW = datetime(2026, 10, 30, 15, 0, tzinfo=UTC)
ROAD = (-88.5, 13.6)
SITE = (-88.18, 13.48)


def _fixes(minutes: list[tuple[int, float]], point: tuple[float, float] = ROAD) -> list[Fix]:
    return [Fix(NOW - timedelta(minutes=ago), point, speed) for ago, speed in minutes]


def _trip(**extra: object) -> TripSnapshot:
    values: dict[str, object] = {
        "now": NOW,
        "dispatched_at": NOW - timedelta(hours=1),
        "destination_name": "Bodega Santa Rosa",
        "gps_linked": True,
        "fixes": _fixes([(3, 50.0), (1, 48.0)]),
        "planned_duration_s": 2 * 3600,
        "eta": NOW + timedelta(minutes=60),
        "sites": [(SITE[0], SITE[1], 150.0)],
    }
    values.update(extra)
    return TripSnapshot(**values)  # type: ignore[arg-type]


def _kinds(trip: TripSnapshot) -> set[str]:
    return {condition.kind for condition in evaluate_trip(trip)}


def test_a_trip_on_time_and_on_route_raises_nothing() -> None:
    assert evaluate_trip(_trip()) == []


def test_arrival_replaces_every_other_condition() -> None:
    conditions = evaluate_trip(_trip(arrived=True, off_route=True))
    assert [(c.kind, c.severity) for c in conditions] == [("arrived", "info")]
    assert "Bodega Santa Rosa" in conditions[0].message


def test_gps_silence_and_missing_device_are_critical() -> None:
    assert _kinds(_trip(gps_linked=False)) == {"gps_lost"}
    silent = evaluate_trip(_trip(fixes=_fixes([(25, 40.0)]), off_route=True))
    assert [(c.kind, c.severity) for c in silent] == [("gps_lost", "critical")]
    never_reported = _trip(fixes=[], dispatched_at=NOW - timedelta(minutes=15))
    assert _kinds(never_reported) == {"gps_lost"}
    assert _kinds(_trip(fixes=[], dispatched_at=NOW - timedelta(minutes=5))) == set()


def test_delay_uses_the_larger_of_fifteen_minutes_and_a_quarter_of_the_trip() -> None:
    # Viaje de 2 h: tolerancia 30 min. Llegada prevista 16:00.
    assert _kinds(_trip(eta=NOW + timedelta(minutes=85))) == set()
    delayed = evaluate_trip(_trip(eta=NOW + timedelta(minutes=95)))
    assert [c.kind for c in delayed] == ["delayed"]
    assert delayed[0].details["delay_min"] == 35


def test_long_stops_only_count_outside_known_places() -> None:
    parked = _fixes([(30, 1.0), (10, 0.5), (1, 0.0)])
    assert stopped_since(parked) == NOW - timedelta(minutes=30)
    assert _kinds(_trip(fixes=parked)) == {"long_stop"}
    at_branch = _fixes([(30, 1.0), (1, 0.0)], point=SITE)
    assert _kinds(_trip(fixes=at_branch)) == set()
    short = _fixes([(30, 60.0), (10, 0.0), (1, 0.0)])
    assert _kinds(_trip(fixes=short)) == set()


def test_off_route_is_reported_with_its_distance() -> None:
    condition = evaluate_trip(_trip(off_route=True, off_route_m=640.4))[0]
    assert condition.kind == "off_route"
    assert condition.details["off_route_m"] == 640
