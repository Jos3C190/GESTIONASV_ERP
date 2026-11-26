"""V6a: cajas, turnos, efectivo, cierre ciego con aprobación, PIN de supervisor y depósitos."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from app.application.rbac.catalogue import POS_CASHIER_PERMISSIONS, POS_SUPERVISOR_PERMISSIONS
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.organization import Branch
from httpx import AsyncClient
from sqlalchemy import select

from tests.e2e.conftest import get_test_company_id
from tests.e2e.test_sales_discounts import PASSWORD, _login
from tests.e2e.test_sales_invoices import _issuer

pytestmark = pytest.mark.e2e

POS = "/api/v1/pos"
D = Decimal


def _bills(*pairs: tuple[str, int], form: str = "bill") -> list[dict[str, object]]:
    return [
        {"form": form, "denomination": value, "quantity": quantity} for value, quantity in pairs
    ]


FIFTY = _bills(("20", 2), ("10", 1))


def _key() -> str:
    return f"pos-{uuid.uuid4()}"


async def _branch() -> uuid.UUID:
    company_id = await get_test_company_id()
    async with async_session_factory() as session:
        branch = await session.scalar(
            select(Branch.id)
            .where(Branch.company_id == company_id, Branch.is_active.is_(True))
            .order_by(Branch.created_at, Branch.id)
            .limit(1)
        )
    assert branch is not None
    return branch


async def _register(client: AsyncClient, manager: dict[str, str], code: str = "CAJA-01") -> dict:
    company_id = uuid.UUID(manager["X-Company-ID"])
    point = await _issuer(company_id, await _branch())
    created = await client.post(
        f"{POS}/registers",
        json={
            "point_of_sale_id": str(point),
            "code": code,
            "name": "Caja principal",
            "opening_float": "50.00",
            "cash_out_approval_threshold": "20.00",
            "cash_drawer_limit": "300.00",
        },
        headers=manager,
    )
    assert created.status_code == 201, created.text
    return created.json()


async def _actions(resource_id: str) -> list[str]:
    async with async_session_factory() as session:
        rows = await session.scalars(
            select(AuditLog.action)
            .where(AuditLog.resource_id == resource_id)
            .order_by(AuditLog.created_at)
        )
        return list(rows)


async def test_register_configuration(e2e_client: AsyncClient) -> None:
    _, manager = await _login(e2e_client, superuser=False, permissions=("pos:registers_manage",))
    _, cashier = await _login(e2e_client, superuser=False, permissions=POS_CASHIER_PERMISSIONS)
    register = await _register(e2e_client, manager)
    assert register["code"] == "CAJA-01"
    assert register["has_shifts"] is False

    options = (await e2e_client.get(f"{POS}/point-of-sale-options", headers=manager)).json()
    taken = next(item for item in options if item["id"] == register["point_of_sale_id"])
    assert taken["available"] is False

    again = await e2e_client.post(
        f"{POS}/registers",
        json={
            "point_of_sale_id": register["point_of_sale_id"],
            "code": "CAJA-02",
            "name": "Otra",
            "opening_float": "0",
            "cash_out_approval_threshold": "0",
        },
        headers=manager,
    )
    assert again.status_code == 409
    assert again.json()["code"] == "pos_point_of_sale_taken"

    # El cajero ve las cajas para abrir su turno, pero no las configura.
    listed = await e2e_client.get(f"{POS}/registers", headers=cashier)
    assert listed.status_code == 200
    assert register["id"] in {item["id"] for item in listed.json()}
    forbidden = await e2e_client.put(
        f"{POS}/registers/{register['id']}",
        json={**register, "expected_version": register["version"], "name": "Cambiada"},
        headers=cashier,
    )
    assert forbidden.status_code == 403

    updated = await e2e_client.put(
        f"{POS}/registers/{register['id']}",
        json={
            "code": "caja-01",
            "name": "  Caja   de entrada ",
            "opening_float": "50.00",
            "cash_out_approval_threshold": "25.00",
            "expected_version": register["version"],
        },
        headers=manager,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Caja de entrada"
    assert updated.json()["code"] == "CAJA-01"
    stale = await e2e_client.put(
        f"{POS}/registers/{register['id']}",
        json={
            "code": "CAJA-01",
            "name": "Caja",
            "opening_float": "50.00",
            "cash_out_approval_threshold": "25.00",
            "expected_version": register["version"],
        },
        headers=manager,
    )
    assert stale.status_code == 409
    assert await _actions(register["id"]) == ["CREATE_POS_REGISTER", "UPDATE_POS_REGISTER"]


async def test_blind_close_recount_approval_and_deposit(e2e_client: AsyncClient) -> None:  # noqa: PLR0915
    _, manager = await _login(e2e_client, superuser=False, permissions=("pos:registers_manage",))
    cashier_id, cashier = await _login(
        e2e_client, superuser=False, permissions=POS_CASHIER_PERMISSIONS
    )
    _, other_cashier = await _login(
        e2e_client, superuser=False, permissions=POS_CASHIER_PERMISSIONS
    )
    supervisor_id, supervisor = await _login(
        e2e_client, superuser=False, permissions=POS_SUPERVISOR_PERMISSIONS
    )
    register = await _register(e2e_client, manager)

    # Apertura: el fondo es el conteo; si no coincide con el de la caja, pide explicación.
    short = await e2e_client.post(
        f"{POS}/shifts",
        json={
            "register_id": register["id"],
            "denominations": _bills(("20", 2)),
            "idempotency_key": _key(),
        },
        headers=cashier,
    )
    assert short.status_code == 422
    assert short.json()["code"] == "pos_opening_float_differs"
    key = _key()
    opened = await e2e_client.post(
        f"{POS}/shifts",
        json={"register_id": register["id"], "denominations": FIFTY, "idempotency_key": key},
        headers=cashier,
    )
    assert opened.status_code == 201, opened.text
    shift = opened.json()
    assert shift["status"] == "open"
    assert D(shift["opening_float"]) == D("50.00")
    assert shift["code"].startswith("TUR-")
    replay = await e2e_client.post(
        f"{POS}/shifts",
        json={"register_id": register["id"], "denominations": FIFTY, "idempotency_key": key},
        headers=cashier,
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == shift["id"]
    busy = await e2e_client.post(
        f"{POS}/shifts",
        json={"register_id": register["id"], "denominations": FIFTY, "idempotency_key": _key()},
        headers=other_cashier,
    )
    assert busy.status_code == 409
    assert busy.json()["code"] == "pos_register_busy"
    me = (await e2e_client.get(f"{POS}/me", headers=cashier)).json()
    assert me["shift"]["id"] == shift["id"]
    assert me["can_supervise"] is False

    movements = f"{POS}/shifts/{shift['id']}/movements"

    async def move(kind: str, amount: str, **extra: object) -> object:
        return await e2e_client.post(
            movements,
            json={
                "kind": kind,
                "amount": amount,
                "reason": "Movimiento de prueba",
                "idempotency_key": _key(),
                **extra,
            },
            headers=cashier,
        )

    assert (await move("cash_in", "10.00")).status_code == 201
    needs = await move("cash_out", "25.00")
    assert needs.status_code == 422
    assert needs.json()["code"] == "pos_movement_requires_supervisor"

    # El supervisor define su PIN con su contraseña y autoriza la salida.
    bad_password = await e2e_client.put(
        f"{POS}/me/pin", json={"password": "incorrecta", "pin": "482915"}, headers=supervisor
    )
    assert bad_password.status_code == 403
    weak = await e2e_client.put(
        f"{POS}/me/pin", json={"password": PASSWORD, "pin": "123456"}, headers=supervisor
    )
    assert weak.status_code == 422
    assert (
        await e2e_client.put(
            f"{POS}/me/pin", json={"password": PASSWORD, "pin": "482915"}, headers=supervisor
        )
    ).status_code == 204
    choices = (
        await e2e_client.get(f"{POS}/branches/{register['branch_id']}/supervisors", headers=cashier)
    ).json()
    assert supervisor_id in {item["id"] for item in choices}
    assert cashier_id not in {item["id"] for item in choices}
    wrong = await move(
        "cash_out", "25.00", approval={"supervisor_id": supervisor_id, "pin": "000000"}
    )
    assert wrong.status_code == 403
    assert wrong.json()["code"] == "pos_pin_incorrect"
    approved_out = await move(
        "cash_out", "25.00", approval={"supervisor_id": supervisor_id, "pin": "482915"}
    )
    assert approved_out.status_code == 201, approved_out.text
    assert approved_out.json()["authorized_by"]["id"] == supervisor_id
    too_much = await move("safe_drop", "100.00")
    assert too_much.status_code == 422
    assert too_much.json()["code"] == "pos_movement_exceeds_cash"
    assert (await move("safe_drop", "20.00")).status_code == 201
    # Esperado: 50 + 10 - 25 - 20 = 15.

    # Cierre ciego: el cajero nunca ve el esperado mientras el turno no se cierra.
    own = (await e2e_client.get(f"{POS}/shifts/{shift['id']}", headers=cashier)).json()
    assert own["totals"] is None
    assert own["shift"]["expected_cash"] is None
    assert len(own["movements"]) == 3
    peek = await e2e_client.get(f"{POS}/shifts/{shift['id']}", headers=other_cashier)
    assert peek.status_code == 403

    counted = await e2e_client.post(
        f"{POS}/shifts/{shift['id']}/count",
        json={
            "expected_version": shift["version"],
            "denominations": _bills(("10", 1), ("1", 4)),
            "declared_card": "0",
            "declared_transfer": "0",
        },
        headers=cashier,
    )
    assert counted.status_code == 200, counted.text
    counted_shift = counted.json()
    assert counted_shift["status"] == "counted"
    assert counted_shift["expected_cash"] is None
    assert D(counted_shift["counted_cash"]) == D("14.00")
    after_count = await move("cash_in", "1.00")
    assert after_count.status_code == 409
    assert after_count.json()["code"] == "pos_shift_not_open"

    review = (await e2e_client.get(f"{POS}/shifts/{shift['id']}", headers=supervisor)).json()
    assert D(review["totals"]["expected_cash"]) == D("15.00")
    assert D(review["shift"]["expected_cash"]) == D("15.00")
    listed = (
        await e2e_client.get(f"{POS}/shifts", params={"status": "counted"}, headers=supervisor)
    ).json()
    assert shift["id"] in {item["id"] for item in listed["items"]}
    no_notes = await e2e_client.post(
        f"{POS}/shifts/{shift['id']}/approve",
        json={"expected_version": counted_shift["version"], "retained_float": "10.00"},
        headers=supervisor,
    )
    assert no_notes.status_code == 422
    assert no_notes.json()["code"] == "pos_difference_requires_notes"
    recount = await e2e_client.post(
        f"{POS}/shifts/{shift['id']}/recount",
        json={
            "expected_version": counted_shift["version"],
            "reason": "Falta un dólar, vuelve a contar",
        },
        headers=supervisor,
    )
    assert recount.status_code == 200, recount.text
    assert recount.json()["status"] == "recount"
    recounted = await e2e_client.post(
        f"{POS}/shifts/{shift['id']}/count",
        json={
            "expected_version": recount.json()["version"],
            "denominations": _bills(("10", 1), ("1", 5)),
            "declared_card": "0",
            "declared_transfer": "0",
        },
        headers=cashier,
    )
    assert recounted.status_code == 200, recounted.text
    approved = await e2e_client.post(
        f"{POS}/shifts/{shift['id']}/approve",
        json={"expected_version": recounted.json()["version"], "retained_float": "10.00"},
        headers=supervisor,
    )
    assert approved.status_code == 200, approved.text
    closed = approved.json()
    assert closed["status"] == "closed"
    assert D(closed["cash_difference"]) == D("0.00")
    assert D(closed["cash_to_deposit"]) == D("5.00")
    assert closed["approved_by"]["id"] == supervisor_id

    # Cerrado, el cajero ve el resultado; el turno ya no cambia.
    final = (await e2e_client.get(f"{POS}/shifts/{shift['id']}", headers=cashier)).json()
    assert D(final["shift"]["expected_cash"]) == D("15.00")
    assert [count["kind"] for count in final["counts"]] == ["opening", "closing", "closing"]
    again = await e2e_client.post(
        f"{POS}/shifts/{shift['id']}/approve",
        json={"expected_version": closed["version"], "retained_float": "10.00"},
        headers=supervisor,
    )
    assert again.status_code == 409
    assert await _actions(shift["id"]) == [
        "OPEN_POS_SHIFT",
        "POS_CASH_MOVEMENT",
        "POS_CASH_MOVEMENT",
        "POS_CASH_MOVEMENT",
        "COUNT_POS_SHIFT",
        "REQUEST_POS_SHIFT_RECOUNT",
        "COUNT_POS_SHIFT",
        "APPROVE_POS_SHIFT",
    ]

    # Depósito: lo contado que no queda de fondo (5) más el retiro a caja fuerte (20).
    candidates = (
        await e2e_client.get(
            f"{POS}/deposits/candidates",
            params={"branch_id": register["branch_id"]},
            headers=supervisor,
        )
    ).json()
    [candidate] = [item for item in candidates if item["shift_id"] == shift["id"]]
    assert D(candidate["amount"]) == D("25.00")
    deposit_body = {
        "branch_id": register["branch_id"],
        "shift_ids": [shift["id"]],
        "deposited_on": datetime.now(ZoneInfo("America/El_Salvador")).date().isoformat(),
        "bank_name": "Banco Agrícola",
        "account_reference": "Cuenta corriente 0001",
        "slip_number": "BOL-12345",
        "deposited_amount": "24.00",
        "idempotency_key": _key(),
    }
    tomorrow = datetime.now(ZoneInfo("America/El_Salvador")).date() + timedelta(days=1)
    future = await e2e_client.post(
        f"{POS}/deposits",
        json={**deposit_body, "deposited_on": tomorrow.isoformat()},
        headers=supervisor,
    )
    assert future.json()["code"] == "pos_deposit_date_future"
    before_close = await e2e_client.post(
        f"{POS}/deposits",
        json={**deposit_body, "deposited_on": (tomorrow - timedelta(days=5)).isoformat()},
        headers=supervisor,
    )
    assert before_close.json()["code"] == "pos_deposit_date_before_close"
    unexplained = await e2e_client.post(f"{POS}/deposits", json=deposit_body, headers=supervisor)
    assert unexplained.status_code == 422
    assert unexplained.json()["code"] == "pos_deposit_difference_requires_notes"
    deposit_body["deposited_amount"] = "25.00"
    deposit = await e2e_client.post(f"{POS}/deposits", json=deposit_body, headers=supervisor)
    assert deposit.status_code == 201, deposit.text
    assert deposit.json()["code"].startswith("DEP-")
    assert D(deposit.json()["difference"]) == D("0.00")
    replayed = await e2e_client.post(f"{POS}/deposits", json=deposit_body, headers=supervisor)
    assert replayed.status_code == 200
    reused = await e2e_client.post(
        f"{POS}/deposits", json={**deposit_body, "idempotency_key": _key()}, headers=supervisor
    )
    assert reused.status_code == 409
    remaining = (
        await e2e_client.get(
            f"{POS}/deposits/candidates",
            params={"branch_id": register["branch_id"]},
            headers=supervisor,
        )
    ).json()
    assert shift["id"] not in {item["shift_id"] for item in remaining}
    assert (await e2e_client.get(f"{POS}/deposits", headers=cashier)).status_code == 403


async def test_supervisor_never_approves_own_shift(e2e_client: AsyncClient) -> None:
    _, manager = await _login(e2e_client, superuser=False, permissions=("pos:registers_manage",))
    _, supervisor = await _login(
        e2e_client, superuser=False, permissions=POS_SUPERVISOR_PERMISSIONS
    )
    register = await _register(e2e_client, manager)
    shift = (
        await e2e_client.post(
            f"{POS}/shifts",
            json={"register_id": register["id"], "denominations": FIFTY, "idempotency_key": _key()},
            headers=supervisor,
        )
    ).json()
    counted = (
        await e2e_client.post(
            f"{POS}/shifts/{shift['id']}/count",
            json={
                "expected_version": shift["version"],
                "denominations": FIFTY,
                "declared_card": "0",
                "declared_transfer": "0",
            },
            headers=supervisor,
        )
    ).json()
    # Contando su propio turno tampoco ve el esperado, aunque sea supervisor.
    assert counted["expected_cash"] is None
    own = await e2e_client.post(
        f"{POS}/shifts/{shift['id']}/approve",
        json={"expected_version": counted["version"], "retained_float": "50.00"},
        headers=supervisor,
    )
    assert own.status_code == 422
    assert own.json()["code"] == "pos_self_authorization"


async def test_pos_permissions(e2e_client: AsyncClient) -> None:
    _, seller = await _login(e2e_client, superuser=False, permissions=("pos:sell",))
    _, outsider = await _login(e2e_client, superuser=False, permissions=("sales:read",))
    assert (await e2e_client.get(f"{POS}/me", headers=seller)).status_code == 200
    assert (await e2e_client.get(f"{POS}/me", headers=outsider)).status_code == 403
    assert (await e2e_client.get(f"{POS}/shifts", headers=seller)).status_code == 403
    assert (await e2e_client.get(f"{POS}/point-of-sale-options", headers=seller)).status_code == 403
    missing = await e2e_client.get(f"{POS}/shifts/{uuid.uuid4()}", headers=seller)
    assert missing.status_code == 404


async def test_other_branch_supervisor_is_blocked(e2e_client: AsyncClient) -> None:
    from app.infrastructure.models.organization import UserCompany

    _, manager = await _login(e2e_client, superuser=False, permissions=("pos:registers_manage",))
    _, cashier = await _login(e2e_client, superuser=False, permissions=POS_CASHIER_PERMISSIONS)
    outsider_id, outsider = await _login(
        e2e_client, superuser=False, permissions=POS_SUPERVISOR_PERMISSIONS
    )
    company_id = uuid.UUID(manager["X-Company-ID"])
    async with async_session_factory() as session:
        membership = await session.get(UserCompany, (uuid.UUID(outsider_id), company_id))
        assert membership is not None
        membership.access_all_branches = False  # sin sucursales asignadas
        await session.commit()
    register = await _register(e2e_client, manager)
    shift = (
        await e2e_client.post(
            f"{POS}/shifts",
            json={"register_id": register["id"], "denominations": FIFTY, "idempotency_key": _key()},
            headers=cashier,
        )
    ).json()
    assert (
        await e2e_client.get(f"{POS}/shifts/{shift['id']}", headers=outsider)
    ).status_code == 403
    denied = await e2e_client.post(
        f"{POS}/shifts/{shift['id']}/recount",
        json={"expected_version": shift["version"], "reason": "No es de mi sucursal"},
        headers=outsider,
    )
    assert denied.status_code == 403
    choices = (
        await e2e_client.get(f"{POS}/branches/{register['branch_id']}/supervisors", headers=cashier)
    ).json()
    assert outsider_id not in {item["id"] for item in choices}
