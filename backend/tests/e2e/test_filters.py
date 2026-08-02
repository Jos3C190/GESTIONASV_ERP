"""E2E: filtros de busqueda en listados (employees por dept/status, audit-log por action/status)."""
from __future__ import annotations

import uuid

import pytest

from tests.e2e.conftest import get_test_company_id, seed_user

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
    company_id = await get_test_company_id()
    return {
        "Authorization": f"Bearer {r.json()['access_token']}",
        "X-Company-ID": str(company_id),
    }


async def test_employees_filter_by_department(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    # Crear dos departamentos
    d1 = await e2e_client.post(
        "/api/v1/departments", headers=headers, json={"company_id": headers["X-Company-ID"], "name": f"Eng_{uuid.uuid4().hex[:6]}"}
    )
    d2 = await e2e_client.post(
        "/api/v1/departments", headers=headers, json={"company_id": headers["X-Company-ID"], "name": f"Sales_{uuid.uuid4().hex[:6]}"}
    )
    did1 = d1.json()["id"]
    did2 = d2.json()["id"]
    # Crear empleados en cada dept
    await e2e_client.post(
        "/api/v1/employees", headers=headers,
        json={"company_id": headers["X-Company-ID"], "employee_code": f"E1_{uuid.uuid4().hex[:6]}", "first_name": "Eng", "last_name": "One", "department_id": did1},
    )
    await e2e_client.post(
        "/api/v1/employees", headers=headers,
        json={"company_id": headers["X-Company-ID"], "employee_code": f"E2_{uuid.uuid4().hex[:6]}", "first_name": "Sales", "last_name": "Two", "department_id": did2},
    )
    # Filtrar por dept1
    r = await e2e_client.get(f"/api/v1/employees?company_id={headers['X-Company-ID']}&department_id={did1}", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(e["department_id"] == did1 for e in items)
    assert any(e["first_name"] == "Eng" for e in items)


async def test_employees_filter_by_status(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    # Crear empleado activo
    await e2e_client.post(
        "/api/v1/employees", headers=headers,
        json={"company_id": headers["X-Company-ID"], "employee_code": f"ACT_{uuid.uuid4().hex[:6]}", "first_name": "Active", "last_name": "Emp", "status": "activo"},
    )
    # Crear empleado de baja
    await e2e_client.post(
        "/api/v1/employees", headers=headers,
        json={"company_id": headers["X-Company-ID"], "employee_code": f"BAJ_{uuid.uuid4().hex[:6]}", "first_name": "Baja", "last_name": "Emp", "status": "baja"},
    )
    # Filtrar por status=activo
    r = await e2e_client.get(f"/api/v1/employees?company_id={headers['X-Company-ID']}&status=activo", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(e["status"] == "activo" for e in items)
    # Filtrar por status=baja
    r = await e2e_client.get(f"/api/v1/employees?company_id={headers['X-Company-ID']}&status=baja", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(e["status"] == "baja" for e in items)


async def test_audit_logs_filter_by_action(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    # Generar un LOGIN_SUCCESS
    await e2e_client.post(
        "/api/v1/auth/login", json={"login": "superadmin", "password": "Cambio!Seguro2026"}
    )
    r = await e2e_client.get("/api/v1/audit-logs?action=LOGIN_SUCCESS&size=5", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["action"] == "LOGIN_SUCCESS" for i in items)


async def test_audit_logs_filter_by_status(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    # Generar un LOGIN_FAILED
    await seed_user(username="failuser", email="fail@e.com")
    await e2e_client.post(
        "/api/v1/auth/login", json={"login": "failuser", "password": "wrong"}
    )
    r = await e2e_client.get("/api/v1/audit-logs?status=failure&size=5", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["status"] == "failure" for i in items)


async def test_users_search(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    await seed_user(username="searchtarget", email="searchtarget@e.com")
    r = await e2e_client.get("/api/v1/users?search=searchtarget", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all("searchtarget" in (u["username"] + u["email"]).lower() for u in items)


async def test_employees_search(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    await e2e_client.post(
        "/api/v1/employees", headers=headers,
        json={"company_id": headers["X-Company-ID"], "employee_code": f"SRC_{uuid.uuid4().hex[:6]}", "first_name": "SearchableName", "last_name": "Test"},
    )
    r = await e2e_client.get(f"/api/v1/employees?company_id={headers['X-Company-ID']}&search=SearchableName", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any("SearchableName" in e["first_name"] for e in items)
