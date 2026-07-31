"""E2E: employees + departments CRUD, hierarchy, cycle detection, link/unlink."""
from __future__ import annotations

import uuid

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


# ---------------- Departments ----------------


async def test_create_department(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.post(
        "/api/v1/departments",
        headers=headers,
        json={"name": f"IT_{uuid.uuid4().hex[:6]}", "description": "Tech"},
    )
    assert r.status_code == 201
    assert r.json()["name"].startswith("IT_")


async def test_list_departments(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    await e2e_client.post(
        "/api/v1/departments", headers=headers, json={"name": f"HR_{uuid.uuid4().hex[:6]}"}
    )
    r = await e2e_client.get("/api/v1/departments", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


async def test_create_department_hierarchy(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    parent = await e2e_client.post(
        "/api/v1/departments", headers=headers, json={"name": f"P_{uuid.uuid4().hex[:6]}"}
    )
    pid = parent.json()["id"]
    child = await e2e_client.post(
        "/api/v1/departments",
        headers=headers,
        json={"name": f"C_{uuid.uuid4().hex[:6]}", "parent_department_id": pid},
    )
    assert child.status_code == 201
    assert child.json()["parent_department_id"] == pid


async def test_update_department_cycle_detection(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    a = await e2e_client.post(
        "/api/v1/departments", headers=headers, json={"name": f"A_{uuid.uuid4().hex[:6]}"}
    )
    b = await e2e_client.post(
        "/api/v1/departments",
        headers=headers,
        json={"name": f"B_{uuid.uuid4().hex[:6]}", "parent_department_id": a.json()["id"]},
    )
    # Try to set A's parent to B -> would create cycle A->B->A
    r = await e2e_client.patch(
        f"/api/v1/departments/{a.json()['id']}",
        headers=headers,
        json={"parent_department_id": b.json()["id"]},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "dept_cycle_detected"


async def test_update_department_self_parent(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    d = await e2e_client.post(
        "/api/v1/departments", headers=headers, json={"name": f"S_{uuid.uuid4().hex[:6]}"}
    )
    r = await e2e_client.patch(
        f"/api/v1/departments/{d.json()['id']}",
        headers=headers,
        json={"parent_department_id": d.json()["id"]},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "dept_self_parent"


async def test_delete_department_with_employees_blocked(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    d = await e2e_client.post(
        "/api/v1/departments", headers=headers, json={"name": f"DEL_{uuid.uuid4().hex[:6]}"}
    )
    did = d.json()["id"]
    await e2e_client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "employee_code": f"EMP_{uuid.uuid4().hex[:6]}",
            "first_name": "Test",
            "last_name": "User",
            "department_id": did,
        },
    )
    r = await e2e_client.delete(f"/api/v1/departments/{did}", headers=headers)
    assert r.status_code == 422
    assert r.json()["code"] == "dept_has_employees"


async def test_delete_empty_department(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    d = await e2e_client.post(
        "/api/v1/departments", headers=headers, json={"name": f"EMPTY_{uuid.uuid4().hex[:6]}"}
    )
    r = await e2e_client.delete(f"/api/v1/departments/{d.json()['id']}", headers=headers)
    assert r.status_code == 200


# ---------------- Employees ----------------


async def test_create_employee(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "employee_code": f"EMP_{uuid.uuid4().hex[:6]}",
            "first_name": "Juan",
            "last_name": "Perez",
            "position": "Developer",
        },
    )
    assert r.status_code == 201
    assert r.json()["first_name"] == "Juan"
    assert r.json()["status"] == "activo"


async def test_create_employee_duplicate_code(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    code = f"DUP_{uuid.uuid4().hex[:6]}"
    await e2e_client.post(
        "/api/v1/employees",
        headers=headers,
        json={"employee_code": code, "first_name": "Alpha", "last_name": "Beta"},
    )
    r = await e2e_client.post(
        "/api/v1/employees",
        headers=headers,
        json={"employee_code": code, "first_name": "Gamma", "last_name": "Delta"},
    )
    assert r.status_code == 409
    assert r.json()["code"] == "employee_code_taken"


async def test_list_employees_paginated(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    for i in range(3):
        await e2e_client.post(
            "/api/v1/employees",
            headers=headers,
            json={
                "employee_code": f"L_{uuid.uuid4().hex[:6]}_{i}",
                "first_name": f"Name{i}",
                "last_name": "Test",
            },
        )
    r = await e2e_client.get("/api/v1/employees?page=1&size=2", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 2
    assert body["meta"]["pages"] >= 1


async def test_list_employees_search(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    await e2e_client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "employee_code": f"SRCH_{uuid.uuid4().hex[:6]}",
            "first_name": "UniqueName",
            "last_name": "Searchable",
        },
    )
    r = await e2e_client.get("/api/v1/employees?search=UniqueName", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any("UniqueName" in e["first_name"] for e in items)


async def test_update_employee(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    emp = await e2e_client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "employee_code": f"UPD_{uuid.uuid4().hex[:6]}",
            "first_name": "Old",
            "last_name": "Name",
        },
    )
    r = await e2e_client.patch(
        f"/api/v1/employees/{emp.json()['id']}",
        headers=headers,
        json={"first_name": "New", "status": "vacaciones"},
    )
    assert r.status_code == 200
    assert r.json()["first_name"] == "New"
    assert r.json()["status"] == "vacaciones"


async def test_create_employee_with_photo(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    r = await e2e_client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "employee_code": f"PH_{uuid.uuid4().hex[:6]}",
            "first_name": "Photo",
            "last_name": "Graphy",
            "photo_url": "https://i.pravatar.cc/300?u=test-photo",
        },
    )
    assert r.status_code == 201
    assert r.json()["photo_url"] == "https://i.pravatar.cc/300?u=test-photo"


async def test_update_employee_photo(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    emp = await e2e_client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "employee_code": f"UPH_{uuid.uuid4().hex[:6]}",
            "first_name": "Snap",
            "last_name": "Shot",
        },
    )
    assert emp.json()["photo_url"] is None
    r = await e2e_client.patch(
        f"/api/v1/employees/{emp.json()['id']}",
        headers=headers,
        json={"photo_url": "https://i.pravatar.cc/300?u=updated"},
    )
    assert r.status_code == 200
    assert r.json()["photo_url"] == "https://i.pravatar.cc/300?u=updated"


async def test_delete_employee(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    emp = await e2e_client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "employee_code": f"DEL_{uuid.uuid4().hex[:6]}",
            "first_name": "Delete",
            "last_name": "Me",
        },
    )
    r = await e2e_client.delete(f"/api/v1/employees/{emp.json()['id']}", headers=headers)
    assert r.status_code == 200
    # Verify it no longer appears in list
    r = await e2e_client.get("/api/v1/employees", headers=headers)
    assert all(e["id"] != emp.json()["id"] for e in r.json()["items"])


async def test_link_unlink_user(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    uid = await seed_user(username="linkuser", email="linkuser@e.com")
    emp = await e2e_client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "employee_code": f"LNK_{uuid.uuid4().hex[:6]}",
            "first_name": "Link",
            "last_name": "Test",
        },
    )
    eid = emp.json()["id"]
    r = await e2e_client.post(
        f"/api/v1/employees/{eid}/link-user", headers=headers, json={"user_id": uid}
    )
    assert r.status_code == 200
    # Verify link
    r = await e2e_client.get(f"/api/v1/employees/{eid}", headers=headers)
    assert r.json()["user_id"] == uid
    # Unlink
    r = await e2e_client.post(f"/api/v1/employees/{eid}/unlink-user", headers=headers)
    assert r.status_code == 200
    r = await e2e_client.get(f"/api/v1/employees/{eid}", headers=headers)
    assert r.json()["user_id"] is None


async def test_employees_require_permission(e2e_client) -> None:
    await seed_user(username="noaccess", email="noaccess@e.com")
    r = await e2e_client.post(
        "/api/v1/auth/login", json={"login": "noaccess", "password": "Strong!Passw0rd2026"}
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await e2e_client.get("/api/v1/employees", headers=headers)
    assert r.status_code == 403


async def test_department_mutations_are_audited(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    created = await e2e_client.post(
        "/api/v1/departments",
        headers=headers,
        json={"name": f"AUD_DEPT_{uuid.uuid4().hex[:6]}"},
    )
    dept_id = created.json()["id"]
    await e2e_client.patch(
        f"/api/v1/departments/{dept_id}",
        headers=headers,
        json={"description": "Actualizado para auditoría"},
    )
    await e2e_client.delete(f"/api/v1/departments/{dept_id}", headers=headers)

    logs = await e2e_client.get(
        f"/api/v1/audit-logs?resource_type=departments&resource_id={dept_id}&size=20",
        headers=headers,
    )
    assert logs.status_code == 200
    actions = {item["action"] for item in logs.json()["items"]}
    assert actions == {"CREATE", "UPDATE", "DELETE"}
    update_log = next(item for item in logs.json()["items"] if item["action"] == "UPDATE")
    assert update_log["before_state"]["description"] is None
    assert update_log["after_state"]["description"] == "Actualizado para auditoría"


async def test_employee_mutations_and_user_links_are_audited(e2e_client) -> None:
    headers = await _login_superadmin(e2e_client)
    user_id = await seed_user(
        username=f"audit-link-{uuid.uuid4().hex[:6]}",
        email=f"audit-{uuid.uuid4().hex[:6]}@example.com",
    )
    created = await e2e_client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "employee_code": f"AUD_EMP_{uuid.uuid4().hex[:6]}",
            "first_name": "Audit",
            "last_name": "Employee",
        },
    )
    emp_id = created.json()["id"]
    await e2e_client.patch(
        f"/api/v1/employees/{emp_id}",
        headers=headers,
        json={"position": "Auditor"},
    )
    await e2e_client.post(
        f"/api/v1/employees/{emp_id}/link-user",
        headers=headers,
        json={"user_id": user_id},
    )
    await e2e_client.post(
        f"/api/v1/employees/{emp_id}/unlink-user",
        headers=headers,
    )
    await e2e_client.delete(f"/api/v1/employees/{emp_id}", headers=headers)

    logs = await e2e_client.get(
        f"/api/v1/audit-logs?resource_type=employees&resource_id={emp_id}&size=20",
        headers=headers,
    )
    assert logs.status_code == 200
    actions = {item["action"] for item in logs.json()["items"]}
    assert actions == {
        "CREATE",
        "UPDATE",
        "LINK_USER",
        "UNLINK_USER",
        "LOGICAL_DELETE",
    }
    link_log = next(item for item in logs.json()["items"] if item["action"] == "LINK_USER")
    assert link_log["before_state"]["user_id"] is None
    assert link_log["after_state"]["user_id"] == user_id
