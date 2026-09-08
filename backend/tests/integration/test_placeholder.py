"""Placeholder integration test (skipped until Phase 1).

Demonstrates the opt-in marker pattern. The conftest `db_session` fixture will
be added in Phase 1 once we have real repositories.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_integration_harness_is_wired() -> None:
    """If this collects without error, the integration folder is recognised."""
    assert True
