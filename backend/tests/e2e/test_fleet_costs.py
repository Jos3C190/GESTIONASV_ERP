"""Who owns a vehicle, what it costs, and where each figure of the report comes from."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from app.application.fleet.costs import business_today
from app.domain.ports.malware_scanner import ScanResult
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.fleet import OdometerReadingModel
from app.infrastructure.models.organization import Company
from app.infrastructure.models.supplier import SupplierModel
from sqlalchemy import select, update

from tests.e2e.test_documents import E2EScanner, _enable_fake_services
from tests.e2e.test_fleet_operations import _new_vehicle
from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches

pytestmark = pytest.mark.e2e

FLEET = "/api/v1/fleet"


async def _supplier(company_id: str, name: str | None = None, *, active: bool = True) -> int:
    from app.infrastructure.models.catalog import CountryModel

    suffix = uuid.uuid4().hex[:8]
    async with async_session_factory() as session:
        country_id = await session.scalar(select(CountryModel.id_country).limit(1))
        supplier = SupplierModel(
            company_id=uuid.UUID(company_id),
            code=f"P-{suffix}",
            name=name or f"Proveedor {suffix}",
            country_id=country_id,
            is_active=active,
        )
        session.add(supplier)
        await session.commit()
        return supplier.id_supplier


async def _setup(client: Any) -> tuple[dict[str, str], str, str]:
    admin = await _admin(client)
    branch = (await _branches(client, admin))[0]["id"]
    vehicle = await _new_vehicle(client, admin, branch)
    return admin, branch, f"{FLEET}/vehicles/{vehicle['id']}"


def _cost(**overrides: Any) -> dict[str, Any]:
    return {
        "category": "insurance",
        "incurred_on": str(business_today()),
        "amount": "120.50",
        **overrides,
    }


async def _report(client: Any, headers: dict[str, str], **params: Any) -> dict[str, Any]:
    today = business_today()
    response = await client.get(
        f"{FLEET}/cost-report",
        headers=headers,
        params={"date_from": str(today), "date_to": str(today), **params},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_rented_vehicle_keeps_its_contract(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    owner = await _supplier(admin["X-Company-ID"], "Arrendadora Central")
    ends_on = str(business_today() + timedelta(days=200))
    saved = await e2e_client.patch(
        base,
        headers=admin,
        json={
            "ownership": "rented",
            "owner_supplier_id": owner,
            "contract_reference": " CT-88 ",
            "contract_ends_on": ends_on,
            "monthly_fee": "450.00",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["ownership"] == "rented"
    assert body["owner_supplier_name"] == "Arrendadora Central"
    assert body["contract_reference"] == "CT-88"
    assert body["contract_ends_on"] == ends_on
    assert body["monthly_fee"] == "450.00"

    # Volver a propio borra el contrato, aunque el formulario enviara datos viejos.
    owned = await e2e_client.patch(
        base, headers=admin, json={"ownership": "owned", "contract_reference": "CT-88"}
    )
    assert owned.status_code == 200, owned.text
    assert owned.json()["contract_reference"] is None
    assert owned.json()["owner_supplier_id"] is None
    assert owned.json()["monthly_fee"] is None


async def test_owner_must_be_an_active_supplier_of_the_company(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    inactive = await _supplier(admin["X-Company-ID"], active=False)
    async with async_session_factory() as session:
        template = await session.get(Company, uuid.UUID(admin["X-Company-ID"]))
        assert template is not None
        suffix = uuid.uuid4().hex[:6].upper()
        other = Company(
            name=f"Ajena {suffix}",
            commercial_name=f"Ajena {suffix}",
            nit=f"0614-{suffix}",
            nrc=f"N{suffix}",
            address=template.address,
            department_id=template.department_id,
            municipality_id=template.municipality_id,
            district_id=template.district_id,
        )
        session.add(other)
        await session.commit()
        other_id = str(other.id)
    foreign = await _supplier(other_id)
    for supplier in (inactive, foreign):
        response = await e2e_client.patch(
            base, headers=admin, json={"ownership": "rented", "owner_supplier_id": supplier}
        )
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "supplier_not_available"
    listed = await e2e_client.get(f"{FLEET}/suppliers", headers=admin)
    assert listed.status_code == 200
    assert {inactive, foreign}.isdisjoint({item["id"] for item in listed.json()})


async def test_an_expired_contract_blocks_and_a_near_one_warns(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    today = business_today()

    async def _codes(ends_on: date) -> tuple[str, set[str]]:
        response = await e2e_client.patch(
            base, headers=admin, json={"ownership": "leased", "contract_ends_on": str(ends_on)}
        )
        assert response.status_code == 200, response.text
        compliance = response.json()["compliance"]
        return compliance["state"], {issue["code"] for issue in compliance["issues"]}

    assert "contract_expiring" in (await _codes(today + timedelta(days=10)))[1]
    state, codes = await _codes(today - timedelta(days=2))
    assert state == "blocked"
    assert "contract_expired" in codes
    alerts = (await e2e_client.get(f"{FLEET}/alerts", headers=admin)).json()
    assert any(alert["code"] == "contract_expired" for alert in alerts)


async def test_costs_are_recorded_voided_and_audited(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    supplier = await _supplier(admin["X-Company-ID"], "Aseguradora Sur")
    created = await e2e_client.post(
        f"{base}/costs",
        headers=admin,
        json=_cost(description=" Póliza anual ", supplier_id=supplier),
    )
    assert created.status_code == 201, created.text
    cost = created.json()
    assert cost["description"] == "Póliza anual"
    assert cost["supplier_name"] == "Aseguradora Sur"
    assert cost["recorded_by_name"]

    voided = await e2e_client.post(
        f"{base}/costs/{cost['id']}/void", headers=admin, json={"reason": "Monto equivocado"}
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["void_reason"] == "Monto equivocado"
    assert voided.json()["voided_by_name"]

    again = await e2e_client.post(
        f"{base}/costs/{cost['id']}/void", headers=admin, json={"reason": "Otra vez"}
    )
    assert again.status_code == 409
    listed = (await e2e_client.get(f"{base}/costs", headers=admin)).json()
    assert [item["id"] for item in listed] == [cost["id"]]
    async with async_session_factory() as session:
        actions = set((await session.scalars(select(AuditLog.action))).all())
    assert {"FLEET_COST", "VOID_FLEET_COST"} <= actions


async def test_cost_cannot_be_dated_in_the_future(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    response = await e2e_client.post(
        f"{base}/costs",
        headers=admin,
        json=_cost(incurred_on=str(business_today() + timedelta(days=1))),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "cost_future_date"


async def test_a_retired_vehicle_can_still_receive_a_late_cost(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    retired = await e2e_client.post(
        f"{base}/status", headers=admin, json={"status": "retired", "reason": "Vendido"}
    )
    assert retired.status_code == 200, retired.text
    late = await e2e_client.post(f"{base}/costs", headers=admin, json=_cost(category="tax"))
    assert late.status_code == 201, late.text


async def test_report_adds_fuel_service_and_costs_and_skips_what_was_voided(
    e2e_client: Any,
) -> None:
    admin, _, base = await _setup(e2e_client)
    vehicle_id = base.rsplit("/", 1)[-1]
    # La lectura inicial es de ayer: solo cuenta lo recorrido dentro del periodo.
    async with async_session_factory() as session:
        await session.execute(
            update(OdometerReadingModel)
            .where(OdometerReadingModel.vehicle_id == uuid.UUID(vehicle_id))
            .values(read_at=datetime.now(UTC) - timedelta(days=2))
        )
        await session.commit()
    for odometer, amount in (("2000.0", "100.00"), ("2500.0", "80.00")):
        added = await e2e_client.post(
            f"{base}/fuel-logs",
            headers=admin,
            json={
                "filled_at": datetime.now(UTC).isoformat(),
                "liters": "30.000",
                "total_amount": amount,
                "odometer_km": odometer,
            },
        )
        assert added.status_code == 201, added.text
    logs = (await e2e_client.get(f"{base}/fuel-logs", headers=admin)).json()["items"]
    voided_fuel = await e2e_client.post(
        f"{base}/fuel-logs/{logs[0]['id']}/void", headers=admin, json={"reason": "Duplicada"}
    )
    assert voided_fuel.status_code == 200, voided_fuel.text

    order = await e2e_client.post(
        f"{base}/maintenance-orders",
        headers=admin,
        json={"kind": "corrective", "title": "Frenos"},
    )
    assert order.status_code == 201, order.text
    order_url = f"{base}/maintenance-orders/{order.json()['id']}"
    assert (await e2e_client.post(f"{order_url}/start", headers=admin)).status_code == 200
    completed = await e2e_client.post(
        f"{order_url}/complete", headers=admin, json={"odometer_km": "2100.0", "cost": "300.00"}
    )
    assert completed.status_code == 200, completed.text

    open_order = await e2e_client.post(
        f"{base}/maintenance-orders",
        headers=admin,
        json={"kind": "corrective", "title": "Sin cerrar"},
    )
    assert open_order.status_code == 201

    await e2e_client.post(f"{base}/costs", headers=admin, json=_cost(amount="50.00"))
    to_void = await e2e_client.post(
        f"{base}/costs", headers=admin, json=_cost(amount="999.00", category="toll")
    )
    await e2e_client.post(
        f"{base}/costs/{to_void.json()['id']}/void", headers=admin, json={"reason": "Error"}
    )

    report = await _report(e2e_client, admin, vehicle_id=vehicle_id)
    row = report["rows"][0]
    assert row["fuel"] == "100.00"
    assert row["maintenance"] == "300.00"
    assert row["other"] == "50.00"
    assert row["total"] == "450.00"
    # 1250.5 antes del periodo, 2000 con la carga vigente y 2100 al cerrar la orden.
    assert row["distance"] == "849.5"
    assert row["cost_per_unit"] == "0.5297"
    assert report["totals"]["total"] == "450.00"
    assert report["other_by_category"] == {"insurance": "50.00"}

    tomorrow = str(business_today() + timedelta(days=1))
    empty = await _report(e2e_client, admin, date_from=tomorrow, date_to=tomorrow)
    assert empty["totals"]["total"] == "0"
    backwards = await e2e_client.get(
        f"{FLEET}/cost-report",
        headers=admin,
        params={"date_from": tomorrow, "date_to": str(business_today())},
    )
    assert backwards.status_code == 422


async def test_branch_users_only_reach_their_branch(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branches = await _branches(e2e_client, admin)
    own = await _new_vehicle(e2e_client, admin, branches[0]["id"])
    other = await _new_vehicle(e2e_client, admin, branches[1]["id"])
    for vehicle in (own, other):
        created = await e2e_client.post(
            f"{FLEET}/vehicles/{vehicle['id']}/costs", headers=admin, json=_cost()
        )
        assert created.status_code == 201, created.text

    manager = await _branch_manager(e2e_client, admin, branches[0]["id"])
    report = await _report(e2e_client, manager)
    assert [row["vehicle_id"] for row in report["rows"]] == [own["id"]]
    hidden = await _report_status(e2e_client, manager, vehicle_id=other["id"])
    assert hidden == 404
    assert (
        await e2e_client.get(f"{FLEET}/vehicles/{other['id']}/costs", headers=manager)
    ).status_code == 404


async def _report_status(client: Any, headers: dict[str, str], **params: Any) -> int:
    today = str(business_today())
    response = await client.get(
        f"{FLEET}/cost-report",
        headers=headers,
        params={"date_from": today, "date_to": today, **params},
    )
    return int(response.status_code)


async def test_recording_costs_needs_its_own_permission(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    vehicle = await _new_vehicle(e2e_client, admin, branch)
    manager = await _branch_manager(e2e_client, admin, branch)
    denied = await e2e_client.post(
        f"{FLEET}/vehicles/{vehicle['id']}/costs", headers=manager, json=_cost()
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "forbidden"


async def test_supplier_fills_the_workshop_and_station_names(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    shop = await _supplier(admin["X-Company-ID"], "Taller El Rápido")
    fuel = await e2e_client.post(
        f"{base}/fuel-logs",
        headers=admin,
        json={
            "filled_at": datetime.now(UTC).isoformat(),
            "liters": "30.000",
            "total_amount": "90.00",
            "odometer_km": "2000.0",
            "supplier_id": shop,
        },
    )
    assert fuel.status_code == 201, fuel.text
    assert fuel.json()["station"] == "Taller El Rápido"
    assert fuel.json()["supplier_id"] == shop

    # Lo escrito a mano sigue valiendo para un taller ocasional.
    typed = await e2e_client.post(
        f"{base}/maintenance-orders",
        headers=admin,
        json={"kind": "corrective", "title": "Llanta", "workshop": "Don Chepe"},
    )
    assert typed.json()["workshop"] == "Don Chepe"
    assert typed.json()["supplier_id"] is None

    order = await e2e_client.post(
        f"{base}/maintenance-orders",
        headers=admin,
        json={"kind": "corrective", "title": "Frenos", "supplier_id": shop},
    )
    assert order.status_code == 201, order.text
    assert order.json()["workshop"] == "Taller El Rápido"


async def test_invoice_must_belong_to_the_vehicle(
    e2e_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_fake_services(e2e_client, monkeypatch, E2EScanner(ScanResult(clean=True)))
    admin, branch, base = await _setup(e2e_client)
    categories = await e2e_client.get(f"{base}/documents/categories", headers=admin)
    invoice = next(item for item in categories.json() if item["code"] == "purchase_invoice")
    payload = b"%PDF-1.7\nfactura"
    initiated = await e2e_client.post(
        f"{base}/documents/uploads",
        headers=admin,
        json={
            "file_name": "factura.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(payload),
            "checksum_sha256": hashlib.sha256(payload).hexdigest(),
            "category_id": invoice["id"],
        },
    )
    assert initiated.status_code == 201, initiated.text
    document = initiated.json()["document_id"]

    linked = await e2e_client.post(f"{base}/costs", headers=admin, json=_cost(document_id=document))
    assert linked.status_code == 201, linked.text
    assert linked.json()["document_id"] == document

    other = await _new_vehicle(e2e_client, admin, branch)
    foreign = await e2e_client.post(
        f"{FLEET}/vehicles/{other['id']}/costs", headers=admin, json=_cost(document_id=document)
    )
    assert foreign.status_code == 422
    assert foreign.json()["code"] == "receipt_document_invalid"
    fuel = await e2e_client.post(
        f"{FLEET}/vehicles/{other['id']}/fuel-logs",
        headers=admin,
        json={
            "filled_at": datetime.now(UTC).isoformat(),
            "liters": "30.000",
            "total_amount": "90.00",
            "odometer_km": "2000.0",
            "receipt_document_id": document,
        },
    )
    assert fuel.status_code == 422
    assert fuel.json()["code"] == "receipt_document_invalid"
