"""Settings tests (pure unit — no I/O)."""

from __future__ import annotations

import pytest
from app.core.config import Settings


def test_settings_defaults_to_dev() -> None:
    s = Settings(_env_file=None, ENVIRONMENT="development")
    assert s.ENVIRONMENT == "development"
    assert s.is_production is False
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 15


def test_settings_cors_parses_list() -> None:
    s = Settings(_env_file=None, CORS_ORIGINS="http://a.com, http://b.com ,  ")
    assert s.cors_origin_list == ["http://a.com", "http://b.com"]


def test_settings_log_level_uppercased() -> None:
    s = Settings(_env_file=None, LOG_LEVEL="debug")
    assert s.LOG_LEVEL == "DEBUG"


def test_settings_test_env_flag() -> None:
    s = Settings(_env_file=None, ENVIRONMENT="test")
    assert s.is_test is True


@pytest.mark.parametrize("environment", ["development", "test", "staging", "production"])
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("allow_production", [False, True])
def test_simulator_requires_explicit_production_opt_in(
    environment: str, enabled: bool, allow_production: bool
) -> None:
    configured = Settings(
        _env_file=None,
        ENVIRONMENT=environment,
        TRACKING_SIMULATOR_ENABLED=enabled,
        TRACKING_SIMULATOR_ALLOW_PRODUCTION=allow_production,
    )
    expected = enabled and (environment != "production" or allow_production)
    assert configured.simulator_enabled is expected
    assert configured.is_production is (environment == "production")


def test_environment_variable_taken_from_os(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "x")
    s = Settings()
    assert s.ENVIRONMENT == "production"
    assert s.is_production is True


def test_observability_requires_endpoint() -> None:
    with pytest.raises(ValueError, match="OTEL_EXPORTER_OTLP_ENDPOINT"):
        Settings(
            _env_file=None,
            OBSERVABILITY_ENABLED=True,
            OTEL_EXPORTER_OTLP_ENDPOINT="",
        )


def test_production_otlp_requires_https_or_explicit_insecure() -> None:
    with pytest.raises(ValueError, match="OTEL_EXPORTER_OTLP_INSECURE"):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            OBSERVABILITY_ENABLED=True,
            OTEL_EXPORTER_OTLP_ENDPOINT="http://collector:4318",
            OTEL_EXPORTER_OTLP_INSECURE=False,
        )
    configured = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        OBSERVABILITY_ENABLED=True,
        OTEL_EXPORTER_OTLP_ENDPOINT="https://collector.example.com",
        OTEL_TRACE_SAMPLE_RATIO=None,
    )
    assert configured.otel_trace_sample_ratio == 0.1


def test_development_trace_sampling_defaults_to_full() -> None:
    configured = Settings(_env_file=None, ENVIRONMENT="development")
    assert configured.otel_trace_sample_ratio == 1.0
