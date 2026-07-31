"""E2E: RBAC — require_permission enforcement, roles CRUD, assignment, /me/permissions.

Requires the dev stack running. Uses the real DB with per-test cleanup.
"""
from __future__ import annotations

import uuid

import pytest

from tests.e2e.conftest import seed_user

pytestmark = pytest.mark.e2e


async def _login_as(e2e_client, username: str, password: str) -> dict:
    r = await e2e_client.post(
        "/api/v1/auth/login", json={"login": username, "password": password}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _login_superadmin(e2e_client) -> dict:
    await seed_user(
        username="superadmin",
        email="superadmin@erp-system.dev",
        password="Cambio!Seguro2026",
        is_superuser=True,
    )
    return await _login_as(e2e_client, "superadmin", "Cambio!Seguro2026")


async def _login_normal(e2e_client, username="normal", email="normal@e.com") -> dict:
    await seed_user(username=username, email=email, password="Strong!Passw0rd2026")
    return await _login_as(e2e_client, username, "Strong!Passw0rd2026")


# ---------------- /me/permissions ----------------


async def test_me_permissions_superuser_returns_full_catalogue(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.get("/api/v1/auth/me/permissions", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["is_superuser"] is True
    assert "users:read" in body["permissions"]
    assert "roles:create" in body["permissions"]
    assert len(body["permissions"]) >= 20


async def test_me_permissions_normal_user_returns_assigned_only(e2e_client) -> None:
    # Seed a normal user, assign ADMINISTRADOR role, check perms.
    headers = await _login_superadmin(e2e_client)
    uid = await seed_user(username="staff", email="staff@e.com")
    # Get ADMINISTRADOR role id
    r = await e2e_client.get("/api/v1/roles", headers=headers)
    roles = r.json()
    admin_role = next((r for r in roles if r["name"] == "ADMINISTRADOR"), None)
    assert admin_role is not None
    # Assign
    r = await e2e_client.post(
        "/api/v1/roles/assign",
        headers=headers,
        json={"user_id": uid, "role_id": admin_role["id"]},
    )
    assert r.status_code == 200
    # Login as staff and check permissions
    staff_headers = await _login_as(e2e_client, "staff", "Strong!Passw0rd2026")
    r = await e2e_client.get("/api/v1/auth/me/permissions", headers=staff_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["is_superuser"] is False
    assert "users:read" in body["permissions"]
    assert "users:create" in body["permissions"]
    # Should NOT have roles:delete
    assert "roles:delete" not in body["permissions"]


# ---------------- require_permission enforcement ----------------


async def test_users_list_requires_users_read_permission(e2e_client) -> None:
    # Normal user with no roles -> 403
    headers = await _login_normal(e2e_client)
    r = await e2e_client.get("/api/v1/users", headers=headers)
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"


async def test_roles_list_requires_roles_read_permission(e2e_client) -> None:
    headers = await _login_normal(e2e_client)
    r = await e2e_client.get("/api/v1/roles", headers=headers)
    assert r.status_code == 403


async def test_superuser_passes_all_permission_checks(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.get("/api/v1/users", headers=headers)
    assert r.status_code == 200
    r = await e2e_client.get("/api/v1/roles", headers=headers)
    assert r.status_code == 200


async def test_administrator_can_list_users_but_not_delete_roles(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    uid = await seed_user(username="admin_user", email="adminuser@e.com")
    r = await e2e_client.get("/api/v1/roles", headers=headers)
    admin_role = next((r for r in r.json() if r["name"] == "ADMINISTRADOR"), None)
    await e2e_client.post(
        "/api/v1/roles/assign",
        headers=headers,
        json={"user_id": uid, "role_id": admin_role["id"]},
    )
    admin_headers = await _login_as(e2e_client, "admin_user", "Strong!Passw0rd2026")
    # Can list users
    r = await e2e_client.get("/api/v1/users", headers=admin_headers)
    assert r.status_code == 200
    # Cannot delete roles (no roles:delete permission)
    r = await e2e_client.delete(
        f"/api/v1/roles/{admin_role['id']}", headers=admin_headers
    )
    assert r.status_code == 403


# ---------------- Roles CRUD ----------------


async def test_list_roles(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.get("/api/v1/roles", headers=headers)
    assert r.status_code == 200
    names = {r["name"] for r in r.json()}
    assert {"SUPER_ADMIN", "ADMINISTRADOR", "RECURSOS_HUMANOS", "EMPLEADO"}.issubset(names)


async def test_create_role(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    unique = f"CUSTOM_{uuid.uuid4().hex[:8]}"
    r = await e2e_client.post(
        "/api/v1/roles",
        headers=headers,
        json={"name": unique, "description": "Test role"},
    )
    assert r.status_code == 201
    assert r.json()["name"] == unique


async def test_create_role_duplicate(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.post(
        "/api/v1/roles", headers=headers, json={"name": "ADMINISTRADOR"}
    )
    assert r.status_code == 409


async def test_delete_non_system_role(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    unique = f"DEL_{uuid.uuid4().hex[:8]}"
    create = await e2e_client.post(
        "/api/v1/roles", headers=headers, json={"name": unique}
    )
    rid = create.json()["id"]
    r = await e2e_client.delete(f"/api/v1/roles/{rid}", headers=headers)
    assert r.status_code == 200


async def test_delete_system_role_forbidden(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.get("/api/v1/roles", headers=headers)
    super_role = next((r for r in r.json() if r["name"] == "SUPER_ADMIN"), None)
    r = await e2e_client.delete(
        f"/api/v1/roles/{super_role['id']}", headers=headers
    )
    assert r.status_code == 422
    assert r.json()["code"] == "system_role_protected"


async def test_set_role_permissions(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    unique = f"PERM_{uuid.uuid4().hex[:8]}"
    create = await e2e_client.post(
        "/api/v1/roles", headers=headers, json={"name": unique}
    )
    rid = create.json()["id"]
    r = await e2e_client.put(
        f"/api/v1/roles/{rid}/permissions",
        headers=headers,
        json={"permission_codes": ["users:read", "users:create"]},
    )
    assert r.status_code == 200
    codes = {p["code"] for p in r.json()["permissions"]}
    assert codes == {"users:read", "users:create"}


# ---------------- Role assignment ----------------


async def test_assign_and_revoke_role(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    uid = await seed_user(username="target", email="target@e.com")
    r = await e2e_client.get("/api/v1/roles", headers=headers)
    role = next((r for r in r.json() if r["name"] == "EMPLEADO"), None)
    fallback_role = next((r for r in r.json() if r["name"] == "ADMINISTRADOR"), None)
    # Assign
    r = await e2e_client.post(
        "/api/v1/roles/assign",
        headers=headers,
        json={"user_id": uid, "role_id": role["id"]},
    )
    assert r.status_code == 200
    assert r.json()["code"] == "role_assigned"
    await e2e_client.post(
        "/api/v1/roles/assign",
        headers=headers,
        json={"user_id": uid, "role_id": fallback_role["id"]},
    )
    # Verify assignment
    r = await e2e_client.get(
        f"/api/v1/roles/users/{uid}/roles", headers=headers
    )
    assert any(r["name"] == "EMPLEADO" for r in r.json())
    # Revoke
    r = await e2e_client.post(
        "/api/v1/roles/revoke",
        headers=headers,
        json={"user_id": uid, "role_id": role["id"]},
    )
    assert r.status_code == 200
    assert r.json()["code"] == "role_revoked"
    # Verify revoked
    r = await e2e_client.get(
        f"/api/v1/roles/users/{uid}/roles", headers=headers
    )
    assert not any(r["name"] == "EMPLEADO" for r in r.json())


async def test_permissions_catalogue(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.get("/api/v1/roles/permissions", headers=headers)
    assert r.status_code == 200
    codes = {p["code"] for p in r.json()}
    assert "users:read" in codes
    assert "roles:assign" in codes
    assert len(codes) >= 20
