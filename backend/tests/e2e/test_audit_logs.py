"""E2E: audit log — entries created on login, read-only, cursor pagination."""

from __future__ import annotations

import pytest

from tests.e2e.conftest import seed_user

pytestmark = pytest.mark.e2e


async def _login_superadmin(e2e_client) -> dict:
    await seed_user(
        username="superadmin",
        email="superadmin@erp-system.dev",
        password="Cambio!Seguro2026",
        is_superuser=True,
    )
    r = await e2e_client.post(
        "/api/v1/auth/login", json={"login": "superadmin", "password": "Cambio!Seguro2026"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_login_creates_audit_entry(e2e_client) -> None:
    await _login_superadmin(e2e_client)
    # Login again to get a fresh token (the first was consumed by _login_superadmin)
    r = await e2e_client.post(
        "/api/v1/auth/login", json={"login": "superadmin", "password": "Cambio!Seguro2026"}
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await e2e_client.get("/api/v1/audit-logs?limit=10", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) >= 1
    actions = {item["action"] for item in body["items"]}
    assert "LOGIN_SUCCESS" in actions


async def test_failed_login_creates_audit_entry(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    await seed_user(username="audituser", email="audituser@e.com")
    # Failed login
    await e2e_client.post("/api/v1/auth/login", json={"login": "audituser", "password": "wrong"})
    r = await e2e_client.get("/api/v1/audit-logs?limit=10&action=LOGIN_FAILED", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all(i["action"] == "LOGIN_FAILED" for i in items)
    assert all(i["status"] == "failure" for i in items)


async def test_audit_logs_require_permission(e2e_client) -> None:
    await seed_user(username="noaccess", email="noaccess@e.com")
    r = await e2e_client.post(
        "/api/v1/auth/login", json={"login": "noaccess", "password": "Strong!Passw0rd2026"}
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await e2e_client.get("/api/v1/audit-logs", headers=headers)
    assert r.status_code == 403


async def test_audit_logs_require_auth(e2e_client) -> None:
    r = await e2e_client.get("/api/v1/audit-logs")
    assert r.status_code == 401


async def test_audit_logs_pagination(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    for _ in range(3):
        await e2e_client.post(
            "/api/v1/auth/login",
            json={"login": "superadmin", "password": "Cambio!Seguro2026"},
        )
    r = await e2e_client.get("/api/v1/audit-logs?page=1&size=2", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 2
    assert body["meta"]["pages"] >= 2
    assert body["meta"]["total"] >= 2

    r2 = await e2e_client.get("/api/v1/audit-logs?page=2&size=2", headers=headers)
    assert r2.status_code == 200
    ids_page1 = {i["id"] for i in body["items"]}
    ids_page2 = {i["id"] for i in r2.json()["items"]}
    assert not ids_page1.intersection(ids_page2)


async def test_audit_logs_filter_by_user(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    uid = await seed_user(username="filtered", email="filtered@e.com")
    # Login as that user to generate an entry
    await e2e_client.post(
        "/api/v1/auth/login", json={"login": "filtered", "password": "Strong!Passw0rd2026"}
    )
    r = await e2e_client.get(f"/api/v1/audit-logs?limit=10&user_id={uid}", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["user_id"] == uid for i in items)


async def test_audit_logs_no_write_endpoints(e2e_client) -> None:
    """Verify there are no POST/PUT/DELETE endpoints on /audit-logs."""
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.post("/api/v1/audit-logs", headers=headers, json={})
    assert r.status_code == 405  # Method Not Allowed
    r = await e2e_client.delete("/api/v1/audit-logs", headers=headers)
    assert r.status_code == 405
