"""E2E: rate limiting on login (10 attempts/min per IP)."""

from __future__ import annotations

import pytest

from tests.e2e.conftest import seed_user

pytestmark = pytest.mark.e2e


async def test_login_rate_limit_kicks_in(e2e_client) -> None:
    """After 10 failed logins in a minute, the 11th gets 429."""
    await seed_user(username="ratelimit", email="rl@e.com")
    for _i in range(10):
        r = await e2e_client.post(
            "/api/v1/auth/login",
            json={"login": "ratelimit", "password": "wrong"},
        )
        assert r.status_code == 401  # first 10 are credential errors
    # 11th should be rate-limited
    r = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": "ratelimit", "password": "wrong"},
    )
    assert r.status_code == 429
    assert r.json()["code"] == "rate_limited"
