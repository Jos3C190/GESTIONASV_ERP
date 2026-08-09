"""E2E: users CRUD — list, get, create, update, force-reset, unlock, deactivate.

Requires the dev stack running. Uses the real DB with per-test cleanup.
"""

from __future__ import annotations

import pytest

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e


async def _login_as(e2e_client, username: str, password: str) -> dict:
    """Login and return the Authorization headers."""
    r = await e2e_client.post("/api/v1/auth/login", json={"login": username, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    company_id = await get_test_company_id()
    return {
        "Authorization": f"Bearer {token}",
        "X-Company-ID": str(company_id),
    }


async def _login_superadmin(e2e_client) -> dict:
    await seed_user(
        username="superadmin",
        email="superadmin@erp-system.dev",
        password="Cambio!Seguro2026",
        is_superuser=True,
    )
    return await _login_as(e2e_client, "superadmin", "Cambio!Seguro2026")


async def test_list_users_requires_superuser(e2e_client) -> None:
    await seed_user(username="normal", email="normal@e.com", password="Strong!Passw0rd2026")
    headers = await _login_as(e2e_client, "normal", "Strong!Passw0rd2026")
    r = await e2e_client.get("/api/v1/users", headers=headers)
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"


async def test_list_users_requires_auth(e2e_client) -> None:
    r = await e2e_client.get("/api/v1/users")
    assert r.status_code == 401


async def test_list_users_paginated(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    for i in range(5):
        await seed_user(username=f"user{i}", email=f"user{i}@e.com")
    r = await e2e_client.get("/api/v1/users?page=1&size=3", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 3
    assert body["meta"]["total"] >= 6  # 5 + superadmin
    assert body["meta"]["pages"] >= 2


async def test_batch_user_roles_returns_one_scoped_payload(e2e_client) -> None:
    from uuid import UUID

    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.rbac import Role, UserRole
    from sqlalchemy import select

    headers = await _login_superadmin(e2e_client)
    user_id = await seed_user(username="batch-role", email="batch-role@example.com")
    async with async_session_factory() as session:
        role_id = (
            await session.execute(select(Role.id).where(Role.name == "EMPLEADO"))
        ).scalar_one()
        session.add(
            UserRole(
                user_id=UUID(user_id),
                company_id=UUID(headers["X-Company-ID"]),
                role_id=role_id,
            )
        )
        await session.commit()

    response = await e2e_client.get(
        "/api/v1/users/batch/roles",
        headers=headers,
        params={"user_ids": user_id, "company_id": headers["X-Company-ID"]},
    )
    assert response.status_code == 200, response.text
    assert [role["name"] for role in response.json()[user_id]] == ["EMPLEADO"]


async def test_list_users_search(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    await seed_user(username="alice", email="alice@example.com")
    r = await e2e_client.get("/api/v1/users?search=alice", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all("alice" in (u["username"] + u["email"]).lower() for u in items)


async def test_list_users_status_filter_is_server_paginated(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    for i in range(5):
        await seed_user(username=f"disabled{i}", email=f"disabled{i}@e.com", is_active=False)
    first = await e2e_client.get("/api/v1/users?status=inactive&page=1&size=2", headers=headers)
    second = await e2e_client.get("/api/v1/users?status=inactive&page=2&size=2", headers=headers)
    assert first.status_code == 200
    assert first.json()["meta"] == {"page": 1, "size": 2, "total": 5, "pages": 3}
    assert second.status_code == 200
    assert all(not user["is_active"] for user in first.json()["items"] + second.json()["items"])
    assert {user["id"] for user in first.json()["items"]}.isdisjoint(
        {user["id"] for user in second.json()["items"]}
    )


async def test_get_user_by_id(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    uid = await seed_user(username="bob", email="bob@example.com")
    r = await e2e_client.get(f"/api/v1/users/{uid}", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "bob"


async def test_get_user_not_found(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.get("/api/v1/users/00000000-0000-0000-0000-000000000000", headers=headers)
    assert r.status_code == 404
    assert r.json()["code"] == "user_not_found"


async def test_create_user_success(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "company_id": headers["X-Company-ID"],
            "username": "newuser",
            "email": "new@example.com",
            "password": "Strong!Passw0rd2026",
            "is_superuser": False,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == "newuser"
    assert body["email"] == "new@example.com"
    assert body["is_active"] is True
    assert "password" not in body  # never expose
    employees = await e2e_client.get(
        f"/api/v1/employees?company_id={headers['X-Company-ID']}&search=newuser",
        headers=headers,
    )
    assert employees.status_code == 200
    linked_employee = next(
        employee for employee in employees.json()["items"] if employee["user_id"] == body["id"]
    )
    delete_linked = await e2e_client.delete(
        f"/api/v1/employees/{linked_employee['id']}", headers=headers
    )
    assert delete_linked.status_code == 409
    assert delete_linked.json()["code"] == "employee_has_user"


async def test_database_rejects_active_user_without_employee(e2e_client) -> None:
    from app.core.security import hash_password
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.user import User as ORMUser
    from sqlalchemy.exc import IntegrityError

    async with async_session_factory() as session:
        session.add(
            ORMUser(
                username="orphan-user",
                email="orphan-user@example.com",
                password_hash=hash_password("Orphan!User2026"),
                is_active=True,
                is_superuser=False,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


async def test_create_user_rejects_weak_password(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "company_id": headers["X-Company-ID"],
            "username": "weak",
            "email": "weak@example.com",
            "password": "short",
            "is_superuser": False,
        },
    )
    assert r.status_code == 422


async def test_create_user_rejects_duplicate_username(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    await seed_user(username="dup", email="first@example.com")
    r = await e2e_client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "company_id": headers["X-Company-ID"],
            "username": "dup",
            "email": "second@example.com",
            "password": "Strong!Passw0rd2026",
        },
    )
    assert r.status_code == 409
    assert r.json()["code"] == "username_taken"


async def test_update_user_cannot_self_deactivate(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    # superadmin's own id — get it from /me
    me = (await e2e_client.get("/api/v1/auth/me", headers=headers)).json()
    r = await e2e_client.patch(
        f"/api/v1/users/{me['id']}", headers=headers, json={"is_active": False}
    )
    assert r.status_code == 403
    assert r.json()["code"] == "self_deactivate_forbidden"


async def test_update_user_cannot_self_demote(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    me = (await e2e_client.get("/api/v1/auth/me", headers=headers)).json()
    r = await e2e_client.patch(
        f"/api/v1/users/{me['id']}", headers=headers, json={"is_superuser": False}
    )
    assert r.status_code == 403
    assert r.json()["code"] == "self_demote_forbidden"


async def test_update_user_activate_deactivate(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    uid = await seed_user(username="target", email="target@e.com")
    r = await e2e_client.patch(f"/api/v1/users/{uid}", headers=headers, json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


async def test_force_password_reset_success(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    uid = await seed_user(username="resetme", email="resetme@e.com")
    r = await e2e_client.post(
        f"/api/v1/users/{uid}/force-password-reset",
        headers=headers,
        json={"new_password": "New!Strong2026"},
    )
    assert r.status_code == 200
    # Verify new password works for login
    r = await e2e_client.post(
        "/api/v1/auth/login", json={"login": "resetme", "password": "New!Strong2026"}
    )
    assert r.status_code == 200


async def test_unlock_account_success(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    uid = await seed_user(username="locked", email="locked@e.com")
    # Lock the account via 5 failed attempts
    for _ in range(5):
        await e2e_client.post("/api/v1/auth/login", json={"login": "locked", "password": "wrong"})
    # Now unlock via admin
    r = await e2e_client.post(f"/api/v1/users/{uid}/unlock", headers=headers)
    assert r.status_code == 200
    # Login with correct password should now work
    r = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": "locked", "password": "Strong!Passw0rd2026"},
    )
    assert r.status_code == 200


async def test_deactivate_user_success(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    uid = await seed_user(username="deleteme", email="delete@e.com")
    r = await e2e_client.delete(f"/api/v1/users/{uid}", headers=headers)
    assert r.status_code == 200
    # User no longer appears in list
    r = await e2e_client.get("/api/v1/users", headers=headers)
    assert all(u["id"] != uid for u in r.json()["items"])


async def test_deactivate_user_cannot_self(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    me = (await e2e_client.get("/api/v1/auth/me", headers=headers)).json()
    r = await e2e_client.delete(f"/api/v1/users/{me['id']}", headers=headers)
    assert r.status_code == 403
    assert r.json()["code"] == "self_deactivate_forbidden"
