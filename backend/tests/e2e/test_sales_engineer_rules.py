"""Pedido del ingeniero (24/11/2026): nunca bajo costo, promoción por sucursal y salida al confirmar.

El artículo de ``_setup`` cuesta $7.00 y su lista lo vende a $10.00 sin IVA.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.e2e.test_sales_orders import ORDER_SELLER, _create, _order_act, _order_body, _stock
from tests.e2e.test_sales_quotations import _setup, _with_policy

pytestmark = pytest.mark.e2e

ORDERS = "/api/v1/sales"
PROMOTIONS = "/api/v1/sales/promotions"


async def _preview(client: AsyncClient, headers: dict[str, str], body: dict) -> dict:
    response = await client.post(f"{ORDERS}/preview", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _post_order(client: AsyncClient, headers: dict[str, str], body: dict):
    return await client.post(
        ORDERS, json=body, headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
    )


async def test_never_below_kardex_cost(e2e_client: AsyncClient) -> None:
    admin, body, _unit = await _setup(e2e_client)
    await _stock(admin, body, "5")

    # 40 % deja $6.00 contra un costo de $7.00: se marca en la vista previa y no se guarda.
    below = _order_body(body, "1")
    below["lines"] = [{**body["lines"][0], "quantity": "1", "discount_percent": "40"}]
    preview = await _preview(e2e_client, admin, below)
    reasons = [r["code"] for r in preview["lines"][0]["authorization_reasons"]]
    assert "below_cost" in reasons
    assert "below_cost" not in [r["code"] for r in preview["authorization_reasons"]]
    refused = await _post_order(e2e_client, admin, below)
    assert refused.status_code == 422
    assert refused.json()["code"] == "sales_price_below_cost"

    # El descuento global también cuenta: 35 % deja $6.50.
    global_ = _order_body(body, "1", global_discount_percent="35")
    refused = await _post_order(e2e_client, admin, global_)
    assert refused.json()["code"] == "sales_price_below_cost"

    # Ni el superusuario lo autoriza: ya no existe el permiso de vender bajo costo.
    policy = (await e2e_client.get(f"{ORDERS}/my-discount-policy", headers=admin)).json()
    assert "can_sell_below_cost" not in policy


async def test_branch_promotion_replaces_other_discounts(e2e_client: AsyncClient) -> None:
    admin, body, unit = await _setup(e2e_client)
    await _stock(admin, body, "5")
    branch_id, product_id = body["branch_id"], unit["product_id"]
    seller = await _with_policy(e2e_client, admin, ORDER_SELLER, "5", "2")
    denied = await e2e_client.post(
        PROMOTIONS,
        json={"branch_id": branch_id, "product_id": product_id, "discount_percent": "10"},
        headers=seller,
    )
    assert denied.status_code == 403

    created = await e2e_client.post(
        PROMOTIONS,
        json={"branch_id": branch_id, "product_id": product_id, "discount_percent": "10"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    promotion = created.json()
    try:
        assert promotion["status"] == "current"
        overlap = await e2e_client.post(
            PROMOTIONS,
            json={"branch_id": branch_id, "product_id": product_id, "discount_percent": "5"},
            headers=admin,
        )
        assert overlap.status_code == 409
        assert overlap.json()["code"] == "sales_promotion_overlap"

        # El vendedor escribe 3 %, pero la línea queda con el 10 % de la promoción y sin tope.
        draft = _order_body(body, "1")
        draft["lines"] = [{**body["lines"][0], "quantity": "1", "discount_percent": "3"}]
        line = (await _preview(e2e_client, seller, draft))["lines"][0]
        assert line["suggested_discount_source"] == "promotion"
        assert line["discount_percent"] == "10.00"
        assert line["authorization_reasons"] == []

        # Con promoción el documento no admite descuento global.
        refused = await e2e_client.post(
            f"{ORDERS}/preview",
            json=_order_body(body, "1", global_discount_percent="2"),
            headers=admin,
        )
        assert refused.status_code == 422
        assert refused.json()["code"] == "sales_global_discount_with_promotion"

        listed = (await e2e_client.get(PROMOTIONS, headers=seller)).json()
        assert promotion["id"] in [item["id"] for item in listed]
    finally:
        ended = await e2e_client.post(f"{PROMOTIONS}/{promotion['id']}/end", headers=admin)
        assert ended.status_code == 200, ended.text
        assert ended.json()["status"] == "ended"

    # Una promoción que deja la línea bajo costo no se puede usar para vender.
    deep = await e2e_client.post(
        PROMOTIONS,
        json={"branch_id": branch_id, "product_id": product_id, "discount_percent": "50"},
        headers=admin,
    )
    assert deep.status_code == 201, deep.text
    try:
        refused = await _post_order(e2e_client, admin, _order_body(body, "1"))
        assert refused.status_code == 422
        assert refused.json()["code"] == "sales_price_below_cost"
    finally:
        await e2e_client.post(f"{PROMOTIONS}/{deep.json()['id']}/end", headers=admin)


async def test_confirming_delivers_whole_units_and_reports_the_rest(
    e2e_client: AsyncClient,
) -> None:
    admin, body, _unit = await _setup(e2e_client)
    await _stock(admin, body, "5")
    settings = (await e2e_client.get(f"{ORDERS}/settings/orders", headers=admin)).json()
    assert settings == {"auto_deliver_on_confirm": True}

    # 5 unidades: la unidad logística completa cubre el pedido y sale del kardex al confirmar.
    order = await _create(e2e_client, admin, _order_body(body, "5"))
    confirmed = await _order_act(e2e_client, admin, order, "confirm")
    assert confirmed.status_code == 200, confirmed.text
    auto = confirmed.json()["auto_delivery"]
    assert auto["delivery_code"].startswith("ENT-"), auto
    assert auto["pending_products"] == []
    assert confirmed.json()["delivery_progress"] == "complete"
    deliveries = await e2e_client.get(f"{ORDERS}/{order['id']}/deliveries", headers=admin)
    assert deliveries.status_code == 200, deliveries.text
    assert [d["status"] for d in deliveries.json()] == ["confirmed"]

    # 2.5 unidades no se cubren con unidades completas: queda apartado y se avisa.
    await _stock(admin, body, "5")
    partial = await _create(e2e_client, admin, _order_body(body, "2.5"))
    confirmed = await _order_act(e2e_client, admin, partial, "confirm")
    assert confirmed.status_code == 200, confirmed.text
    auto = confirmed.json()["auto_delivery"]
    assert auto["delivery_code"] is None
    assert len(auto["pending_products"]) == 1
    assert confirmed.json()["delivery_progress"] == "pending"
