"""Pure rules of the guided GPS setup: address, QR, identifiers and signal."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from app.application.tracking.device_setup import (
    PHONE_PREFIX,
    REPORTING_WINDOW,
    TRACKER_MODELS,
    client_config_uri,
    device_readings,
    device_signal,
    enabled_trackers,
    is_phone_identifier,
    is_private_host,
    new_phone_identifier,
    public_server,
)

NOW = datetime(2026, 11, 2, 15, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("host", "private"),
    [
        ("192.168.1.50", True),
        ("10.0.0.7", True),
        ("172.16.4.1", True),
        ("127.0.0.1", True),
        ("localhost", True),
        ("gps.local", True),
        ("8.8.8.8", False),
        ("gps.example.com", False),
    ],
)
def test_private_hosts_are_told_apart(host: str, private: bool) -> None:
    assert is_private_host(host) is private


def test_public_server_keeps_the_port_and_drops_the_rest() -> None:
    server = public_server(" http://192.168.1.50:5055/ ")

    assert server is not None
    assert server.url == "http://192.168.1.50:5055"
    assert server.host == "192.168.1.50"
    assert server.private is True


@pytest.mark.parametrize(
    "value", [None, "", "192.168.1.50:5055", "ftp://gps.example.com", "http://"]
)
def test_a_missing_or_malformed_address_counts_as_not_configured(value: str | None) -> None:
    assert public_server(value) is None


def test_qr_carries_the_server_and_the_keys_the_app_reads() -> None:
    uri = urlsplit(client_config_uri("http://gps.example.com:5055", "GS-ABC123"))
    settings = parse_qs(uri.query)

    assert f"{uri.scheme}://{uri.netloc}{uri.path}" == "http://gps.example.com:5055"
    assert settings["id"] == ["GS-ABC123"]
    assert settings["accuracy"] == ["high"]
    assert settings["heartbeat"] == ["300"]
    assert settings["buffer"] == ["true"]


def test_phone_identifiers_are_recognizable_valid_and_unique() -> None:
    first, second = new_phone_identifier(), new_phone_identifier()

    assert first != second
    assert first.startswith(PHONE_PREFIX)
    assert len(first) <= 64
    assert is_phone_identifier(first)
    assert not is_phone_identifier("358240051111110")
    assert not is_phone_identifier(None)


def test_signal_waits_until_the_first_report() -> None:
    assert device_signal(None, NOW) == "waiting"


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (timedelta(0), "reporting"),
        (REPORTING_WINDOW, "reporting"),
        (REPORTING_WINDOW + timedelta(seconds=1), "silent"),
        (timedelta(days=3), "silent"),
    ],
)
def test_signal_goes_silent_after_the_window(age: timedelta, expected: str) -> None:
    assert device_signal(NOW - age, NOW) == expected


def test_readings_keep_only_what_the_device_sent() -> None:
    assert device_readings({}) == {}
    assert device_readings({"batteryLevel": 80, "motion": True, "rssi": 4}) == {}
    assert device_readings(
        {"ignition": True, "power": 12.6, "sat": 9, "hours": 7_200_000, "temp1": 4.5}
    ) == {"ignition": True, "voltage": 12.6, "satellites": 9, "engine_hours": 2, "temperature": 4.5}


@pytest.mark.parametrize(
    "attributes",
    [
        {"ignition": 1.0},
        {"power": 12600},
        {"power": 0},
        {"power": True},
        {"power": "12.6"},
        {"sat": 500},
        {"hours": -1},
        {"temp1": 4095},
        {"power": float("nan")},
    ],
)
def test_readings_leave_out_what_is_not_believable(attributes: dict[str, object]) -> None:
    assert device_readings(attributes) == {}


def test_only_the_models_with_an_open_port_are_offered() -> None:
    assert enabled_trackers(None) == TRACKER_MODELS
    assert enabled_trackers("") == TRACKER_MODELS
    assert [model.key for model in enabled_trackers("teltonika, gt06")] == ["gt06", "teltonika"]
    assert enabled_trackers("none") == ()


def test_catalogue_has_unique_keys_and_ports() -> None:
    assert len({model.key for model in TRACKER_MODELS}) == len(TRACKER_MODELS)
    assert len({model.port for model in TRACKER_MODELS}) == len(TRACKER_MODELS)
