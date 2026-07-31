"""E2E: full auth flow — login -> me -> refresh -> logout.

Requires the dev stack to be running (`make up`). Uses the real DB with
per-test cleanup (see e2e/conftest.py).
"""
from __future__ import annotations

import pytest

from tests.e2e.conftest import seed_user

pytestmark = pytest.mark.e2e


async def test_login_me_refresh_logout_flow(e2e_client) -> None:
    await seed_user(username="alice", email="alice@example.com", password="Strong!Passw0rd2026")

    # 1) Login
    r = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": "alice@example.com", "password": "Strong!Passw0rd2026"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    access = body["access_token"]
    refresh = body["refresh_token"]
    assert access
    assert refresh

    # 2) /me with the access token
    r = await e2e_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert r.status_code == 200
    me = r.json()
    assert me["username"] == "alice"
    assert me["email"] == "alice@example.com"

    # 3) Refresh -> new access + rotated refresh
    r = await e2e_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh}
    )
    assert r.status_code == 200, r.text
    new_body = r.json()
    new_access = new_body["access_token"]
    new_refresh = new_body["refresh_token"]
    assert new_access != access
    assert new_refresh != refresh

    # 4) Reusing the OLD refresh token triggers reuse protection (401)
    r = await e2e_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh}
    )
    assert r.status_code == 401
    assert r.json()["code"] == "session_revoked"

    # 5) The new refresh token was revoked by the reuse protection cascade
    r = await e2e_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_refresh}
    )
    assert r.status_code == 401

    # 6) Logout with a fresh login
    r = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": "alice", "password": "Strong!Passw0rd2026"},
    )
    refresh2 = r.json()["refresh_token"]
    r = await e2e_client.post(
        "/api/v1/auth/logout", json={"refresh_token": refresh2}
    )
    assert r.status_code == 200
    assert r.json()["code"] == "logout_ok"


async def test_login_wrong_password_returns_generic_401(e2e_client) -> None:
    await seed_user(username="bob", email="bob@example.com", password="Strong!Passw0rd2026")
    r = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": "bob@example.com", "password": "wrong"},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == "invalid_credentials"
    # Generic message, no hint about which field was wrong
    assert "Credenciales inválidas" in body["message"]


async def test_me_without_token_returns_401(e2e_client) -> None:
    r = await e2e_client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_with_invalid_token_returns_401(e2e_client) -> None:
    r = await e2e_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert r.status_code == 401


async def test_progressive_lockout_after_five_failures(e2e_client) -> None:
    await seed_user(username="locked", email="locked@example.com", password="Strong!Passw0rd2026")

    for _ in range(5):
        r = await e2e_client.post(
            "/api/v1/auth/login",
            json={"login": "locked@example.com", "password": "wrong"},
        )
        assert r.status_code == 401

    # 6th attempt: account is locked, specific code returned
    r = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": "locked@example.com", "password": "Strong!Passw0rd2026"},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "account_locked"


async def test_login_nonexistent_user_returns_generic_401(e2e_client) -> None:
    r = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": "ghost@example.com", "password": "whatever"},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"


async def test_refresh_with_missing_token_returns_401(e2e_client) -> None:
    r = await e2e_client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


async def test_authenticated_user_can_change_password_and_sessions_are_revoked(
    e2e_client,
) -> None:
    old_password = "Strong!Passw0rd2026"
    new_password = "Nueva!ClaveSegura2026"
    await seed_user(
        username="password-user",
        email="password@example.com",
        password=old_password,
    )
    login = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": "password-user", "password": old_password},
    )
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]

    changed = await e2e_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {access}"},
        json={"current_password": old_password, "new_password": new_password},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["code"] == "password_changed"

    revoked = await e2e_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert revoked.status_code == 401
    old_login = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": "password-user", "password": old_password},
    )
    assert old_login.status_code == 401
    new_login = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": "password-user", "password": new_password},
    )
    assert new_login.status_code == 200
