from __future__ import annotations

from typing import Any

import pytest
from app.api.v1.routers import health as health_module


class _Response:
    status = 200

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None


@pytest.mark.parametrize(
    ("actual", "expected", "status", "detail"),
    [
        (frozenset({"0083"}), frozenset({"0083"}), "ok", None),
        (
            frozenset({"0078"}),
            frozenset({"0083"}),
            "outdated",
            "Expected 0083; found 0078",
        ),
        (None, frozenset({"0083"}), "unknown", "Schema version could not be verified"),
    ],
)
def test_schema_revision_status(
    actual: frozenset[str] | None,
    expected: frozenset[str],
    status: str,
    detail: str | None,
) -> None:
    assert health_module._schema_revision_status(actual, expected) == (status, detail)


@pytest.mark.asyncio
async def test_collector_health_states(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module.settings, "OBSERVABILITY_ENABLED", False)
    assert await health_module._observability_health() == ("disabled", None)

    monkeypatch.setattr(health_module.settings, "OBSERVABILITY_ENABLED", True)
    monkeypatch.setattr(health_module.settings, "OBSERVABILITY_HEALTH_URL", None)
    status, detail = await health_module._observability_health()
    assert status == "configured"
    assert detail is not None

    monkeypatch.setattr(
        health_module.settings,
        "OBSERVABILITY_HEALTH_URL",
        "http://collector.internal:13133/",
    )
    monkeypatch.setattr(health_module, "urlopen", lambda *_args, **_kwargs: _Response())
    assert await health_module._observability_health() == ("ok", None)


@pytest.mark.asyncio
async def test_collector_failure_is_degraded_not_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health_module.settings, "OBSERVABILITY_ENABLED", True)
    monkeypatch.setattr(
        health_module.settings,
        "OBSERVABILITY_HEALTH_URL",
        "http://collector.internal:13133/",
    )

    def _unavailable(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("collector unavailable")

    monkeypatch.setattr(health_module, "urlopen", _unavailable)
    status, detail = await health_module._observability_health()
    assert status == "down"
    assert detail is not None
