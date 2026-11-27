"""V6b: crear la vitrina, pasar unidades a vitrina, existencias y conteo de cierre con merma."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.application.rbac.catalogue import POS_CASHIER_PERMISSIONS, POS_SUPERVISOR_PERMISSIONS
from httpx import AsyncClient

from tests.e2e.test_sales_discounts import _login
from tests.e2e.test_sales_orders import _stock
from tests.e2e.test_sales_quotations import _setup

pytestmark = pytest.mark.e2e

SHOWCASES = "/api/v1/pos/showcases"
D = Decimal


def _key() -> str:
    return f"vitrina-{uuid.uuid4()}"


async def test_showcase_open_units_and_waste_count(e2e_client: AsyncClient) -> None:  # noqa: PLR0915
    admin, body, _ = await _setup(e2e_client)
    item_id = str(await _stock(admin, body, "10"))
    branch_id = str(body["branch_id"])
    _, supervisor = await _login(
        e2e_client, superuser=False, permissions=POS_SUPERVISOR_PERMISSIONS
    )
    _, cashier = await _login(e2e_client, superuser=False, permissions=POS_CASHIER_PERMISSIONS)

    # Sin vitrina, la existencia de vitrina avisa.
    missing = await e2e_client.get(f"{SHOWCASES}/{branch_id}/stock", headers=supervisor)
    assert missing.status_code == 404
    assert missing.json()["code"] == "pos_showcase_not_found"

    # Crear la vitrina pide configurar cajas; una por sucursal.
    [warehouse] = (
        await e2e_client.get(
            f"{SHOWCASES}/warehouse-options", params={"branch_id": branch_id}, headers=admin
        )
    ).json()[:1]
    denied = await e2e_client.post(
        SHOWCASES,
        json={"branch_id": branch_id, "warehouse_id": warehouse["id"]},
        headers=supervisor,
    )
    assert denied.status_code == 403
    created = await e2e_client.post(
        SHOWCASES, json={"branch_id": branch_id, "warehouse_id": warehouse["id"]}, headers=admin
    )
    assert created.status_code == 201, created.text
    assert created.json()["location_code"].startswith("VITRINA")
    again = await e2e_client.post(
        SHOWCASES, json={"branch_id": branch_id, "warehouse_id": warehouse["id"]}, headers=admin
    )
    assert again.status_code == 409

    # Pasar a vitrina: unidades completas y disponibles de la bodega.
    candidates = (
        await e2e_client.get(f"{SHOWCASES}/{branch_id}/candidates", headers=supervisor)
    ).json()
    unit = next(item for item in candidates if item["inventory_item_id"] == item_id)
    assert D(unit["quantity"]) == D("10")
    assert (
        await e2e_client.get(f"{SHOWCASES}/{branch_id}/candidates", headers=cashier)
    ).status_code == 403
    key = _key()
    opened = await e2e_client.post(
        f"{SHOWCASES}/{branch_id}/open",
        json={"handling_unit_ids": [unit["handling_unit_id"]], "idempotency_key": key},
        headers=supervisor,
    )
    assert opened.status_code == 201, opened.text
    [stock] = [item for item in opened.json()["stock"] if item["inventory_item_id"] == item_id]
    assert D(stock["quantity"]) == D("10")
    assert D(stock["sellable"]) == D("10")
    replay = await e2e_client.post(
        f"{SHOWCASES}/{branch_id}/open",
        json={"handling_unit_ids": [unit["handling_unit_id"]], "idempotency_key": key},
        headers=supervisor,
    )
    assert replay.status_code == 200
    again_open = await e2e_client.post(
        f"{SHOWCASES}/{branch_id}/open",
        json={"handling_unit_ids": [unit["handling_unit_id"]], "idempotency_key": _key()},
        headers=supervisor,
    )
    assert again_open.status_code == 409
    assert again_open.json()["code"] == "pos_showcase_unit_unavailable"
    after = (await e2e_client.get(f"{SHOWCASES}/{branch_id}/candidates", headers=supervisor)).json()
    assert unit["handling_unit_id"] not in {item["handling_unit_id"] for item in after}

    # El cajero ve la existencia de vitrina, pero no cuenta.
    seen = await e2e_client.get(f"{SHOWCASES}/{branch_id}/stock", headers=cashier)
    assert seen.status_code == 200
    count_url = f"{SHOWCASES}/{branch_id}/counts"
    assert (
        await e2e_client.post(
            count_url,
            json={
                "lines": [{"inventory_item_id": item_id, "counted_quantity": "10"}],
                "idempotency_key": _key(),
            },
            headers=cashier,
        )
    ).status_code == 403

    # Conteo: contar de más no crea existencia y la merma pide motivo.
    over = await e2e_client.post(
        count_url,
        json={
            "lines": [{"inventory_item_id": item_id, "counted_quantity": "12"}],
            "idempotency_key": _key(),
        },
        headers=supervisor,
    )
    assert over.status_code == 422
    assert over.json()["code"] == "pos_showcase_count_over"
    no_reason = await e2e_client.post(
        count_url,
        json={
            "lines": [{"inventory_item_id": item_id, "counted_quantity": "8"}],
            "idempotency_key": _key(),
        },
        headers=supervisor,
    )
    assert no_reason.json()["code"] == "pos_showcase_waste_reason_required"
    key = _key()
    counted = await e2e_client.post(
        count_url,
        json={
            "lines": [
                {"inventory_item_id": item_id, "counted_quantity": "8", "reason": "Pan aplastado"}
            ],
            "notes": "Cierre del día",
            "idempotency_key": key,
        },
        headers=supervisor,
    )
    assert counted.status_code == 201, counted.text
    result = counted.json()
    assert result["code"].startswith("CV-")
    [line] = result["lines"]
    assert (D(line["system_quantity"]), D(line["counted_quantity"]), D(line["waste_quantity"])) == (
        D("10"),
        D("8"),
        D("2"),
    )
    assert D(result["waste_cost"]) == D("14.00")  # 2 piezas a $7.00
    assert result["movement_id"] is not None
    replayed = await e2e_client.post(
        count_url,
        json={
            "lines": [
                {"inventory_item_id": item_id, "counted_quantity": "8", "reason": "Pan aplastado"}
            ],
            "idempotency_key": key,
        },
        headers=supervisor,
    )
    assert replayed.status_code == 200
    assert replayed.json()["id"] == result["id"]
    [left] = [
        item
        for item in (
            await e2e_client.get(f"{SHOWCASES}/{branch_id}/stock", headers=supervisor)
        ).json()
        if item["inventory_item_id"] == item_id
    ]
    assert D(left["quantity"]) == D("8")
    history = (await e2e_client.get(count_url, headers=supervisor)).json()
    assert [item["id"] for item in history] == [result["id"]]

    # Un conteo exacto no mueve inventario.
    exact = await e2e_client.post(
        count_url,
        json={
            "lines": [{"inventory_item_id": item_id, "counted_quantity": "8"}],
            "idempotency_key": _key(),
        },
        headers=supervisor,
    )
    assert exact.status_code == 201
    assert exact.json()["movement_id"] is None
    assert D(exact.json()["waste_cost"]) == D("0.00")
