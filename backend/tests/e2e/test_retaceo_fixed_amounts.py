"""Retaceo costs: FOB from the invoice, typed freight and DAI, all split by FOB, no VAT."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
from sqlalchemy import and_, select

from tests.e2e.test_purchase_orders import _headers, _reference_ids, _sent_order

pytestmark = pytest.mark.e2e

RETIRED_FIELDS = {
    "calculation_mode": "manual",
    "dai_rate": "10",
    "vat_rate": "13",
    "import_vat": "0",
    "fob_lines": [],
}


async def _received_purchase(client, username):
    company, branch, warehouse, product, supplier, currency = await _reference_ids()
    headers = await _headers(client, company_id=company, username=username, is_superuser=True)
    order = await _sent_order(
        client,
        headers=headers,
        branch_id=branch,
        warehouse_id=warehouse,
        product_id=product,
        supplier_id=supplier,
        currency=currency,
        quantity="2.000000",
    )
    response = await client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "purchase_order_id": order["id"],
            "lines": [
                {
                    "purchase_order_detail_id": order["details"][0]["id"],
                    "quantity_received": "2.000000",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    purchase = response.json()
    response = await client.post(f"/api/v1/purchases/{purchase['id']}/receive", headers=headers)
    assert response.status_code == 200, response.text
    fob = sum(
        (Decimal(row["subtotal"]) - Decimal(row["discount"]) for row in purchase["details"]),
        Decimal("0"),
    )
    return headers, purchase, fob


async def test_retired_fields_and_invalid_amounts_are_rejected(e2e_client):
    headers, purchase, _ = await _received_purchase(e2e_client, "fixed-amounts-422")
    base = {
        "purchase_id": purchase["id"],
        "total_freight": "10",
        "total_dai": "5",
        "total_expenses": "0",
    }
    for field, value in RETIRED_FIELDS.items():
        response = await e2e_client.post(
            "/api/v1/retaceos", headers=headers, json={**base, field: value}
        )
        assert response.status_code == 422, (field, response.text)
    for payload in (
        {k: v for k, v in base.items() if k != "total_dai"},
        {k: v for k, v in base.items() if k != "total_freight"},
        {**base, "total_dai": "-1"},
        {**base, "total_freight": "-0.01"},
    ):
        response = await e2e_client.post("/api/v1/retaceos", headers=headers, json=payload)
        assert response.status_code == 422, response.text


async def test_fob_comes_from_the_invoice_and_costs_split_by_fob(e2e_client):
    headers, purchase, fob = await _received_purchase(e2e_client, "fixed-amounts-ok")
    response = await e2e_client.post(
        "/api/v1/retaceos",
        headers=headers,
        json={
            "purchase_id": purchase["id"],
            "total_freight": "10",
            "total_dai": "5",
            "total_expenses": "0",
        },
    )
    assert response.status_code == 201, response.text
    item = response.json()
    for retired in RETIRED_FIELDS:
        assert retired not in item
    assert Decimal(item["total_fob"]) == fob
    assert Decimal(item["total_freight"]) == 10
    assert Decimal(item["total_dai"]) == 5
    assert Decimal(item["total_cost"]) == fob + 15
    detail = item["details"][0]
    assert Decimal(detail["cost_fob"]) == fob
    assert Decimal(detail["freight"]) == 10
    assert Decimal(detail["dai"]) == 5
    assert Decimal(detail["unit_cost"]) == (
        Decimal(detail["total_cost"]) / Decimal(detail["quantity"])
    ).quantize(Decimal("0.000001"))
    # The server stored the by-FOB distribution of each typed amount.
    for cost in item["costs"]:
        assert sum(Decimal(row["amount"]) for row in cost["allocations"]) == Decimal(cost["amount"])

    # Changing an amount requires sending its component too; allocations are never accepted.
    costs = [
        {
            "id": cost["id"],
            "classification": cost["classification"],
            "title": cost["title"],
            "amount": "20" if cost["classification"] == "freight" else cost["amount"],
        }
        for cost in item["costs"]
    ]
    updated = await e2e_client.put(
        f"/api/v1/retaceos/{item['id']}",
        headers=headers,
        json={"total_freight": "20", "total_dai": "5", "total_expenses": "0", "costs": costs},
    )
    assert updated.status_code == 200, updated.text
    assert Decimal(updated.json()["total_cost"]) == fob + 25
    assert Decimal(updated.json()["details"][0]["freight"]) == 20
    with_allocations = [{**costs[0], "allocations": []}]
    rejected = await e2e_client.put(
        f"/api/v1/retaceos/{item['id']}",
        headers=headers,
        json={
            "total_freight": "20",
            "total_dai": "5",
            "total_expenses": "0",
            "costs": with_allocations,
        },
    )
    assert rejected.status_code == 422
    vat = [{"classification": "import_vat", "title": "IVA", "amount": "7"}]
    rejected = await e2e_client.put(
        f"/api/v1/retaceos/{item['id']}",
        headers=headers,
        json={"total_freight": "20", "total_dai": "5", "total_expenses": "0", "costs": vat},
    )
    assert rejected.status_code == 422


async def test_zero_freight_and_dai_are_valid_without_cost_rows(e2e_client):
    headers, purchase, fob = await _received_purchase(e2e_client, "fixed-amounts-zero")
    response = await e2e_client.post(
        "/api/v1/retaceos",
        headers=headers,
        json={
            "purchase_id": purchase["id"],
            "total_freight": "0",
            "total_dai": "0",
            "total_expenses": "0",
        },
    )
    assert response.status_code == 201, response.text
    item = response.json()
    assert Decimal(item["total_cost"]) == fob
    assert [cost for cost in item["costs"] if cost["is_active"]] == []
    assert Decimal(item["details"][0]["unit_cost"]) == (fob / Decimal("2")).quantize(
        Decimal("0.000001")
    )


async def _second_product(first_product_id, company_id):
    async with async_session_factory() as session:
        return await session.scalar(
            select(ProductModel.id_product)
            .join(
                CompanyUnitModel,
                and_(
                    CompanyUnitModel.company_id == ProductModel.company_id,
                    CompanyUnitModel.unit_id == ProductModel.purchase_unit,
                ),
            )
            .where(
                ProductModel.company_id == company_id,
                ProductModel.id_product != first_product_id,
                ProductModel.deleted_at.is_(None),
                ProductModel.is_active.is_(True),
                ProductModel.lifecycle_status == "active",
                ProductModel.can_purchase.is_(True),
                CompanyUnitModel.is_enabled.is_(True),
            )
            .order_by(ProductModel.id_product)
            .limit(1)
        )


async def _two_line_received_purchase(client, username):
    """Two lines whose net values (37.50 and 7.50) leave a rounding residue when split."""
    company, branch, warehouse, product, supplier, currency = await _reference_ids()
    second = await _second_product(product, company)
    assert second is not None, "El seed E2E necesita un segundo producto comprable."
    headers = await _headers(client, company_id=company, username=username, is_superuser=True)
    created = await client.post(
        "/api/v1/purchase-requests",
        headers=headers,
        json={
            "branch_id": str(branch),
            "warehouse_id": str(warehouse),
            "justification": "Retaceo con dos líneas",
            "details": [
                {"product_id": product, "quantity": "3"},
                {"product_id": second, "quantity": "1"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    for action in ("submit", "approve"):
        step = await client.post(
            f"/api/v1/purchase-requests/{request_id}/{action}", headers=headers
        )
        assert step.status_code == 200, step.text
    request_details = step.json()["details"]
    prices = {"3": "12.500000", "1": "7.500000"}
    quotation = await client.post(
        "/api/v1/purchase-quotations",
        headers=headers,
        json={
            "supplier_id": supplier,
            "currency": currency,
            "requests": [
                {
                    "purchase_request_id": request_id,
                    "lines": [
                        {"purchase_request_detail_id": row["id"], "quantity": row["quantity"]}
                        for row in request_details
                    ],
                }
            ],
        },
    )
    assert quotation.status_code == 201, quotation.text
    quotation_id = quotation.json()["id"]
    sent = await client.post(f"/api/v1/purchase-quotations/{quotation_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text
    responded = await client.put(
        f"/api/v1/purchase-quotations/{quotation_id}/response",
        headers=headers,
        json={
            "quotation_date": datetime.now(UTC).isoformat(),
            "payment_terms": "30 días crédito",
            "delivery_days": 3,
            "lines": [
                {
                    "product_id": row["product_id"],
                    "unit_id": row["unit_id"],
                    "quantity": row["quantity"],
                    "available_quantity": row["quantity"],
                    "unit_price": prices[str(int(Decimal(row["quantity"])))],
                    "tax_rate": "13",
                }
                for row in request_details
            ],
        },
    )
    assert responded.status_code == 200, responded.text
    selected = await client.post(
        f"/api/v1/purchase-quotations/{quotation_id}/select", headers=headers
    )
    assert selected.status_code == 200, selected.text
    order = await client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={
            "purchase_quotation_id": quotation_id,
            "branch_id": str(branch),
            "warehouse_id": str(warehouse),
            "expected_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            "lines": [
                {"purchase_quotation_detail_id": row["id"], "quantity": row["quantity"]}
                for row in selected.json()["details"]
            ],
            "notes": "Orden con dos líneas",
        },
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]
    for action in ("submit", "approve", "send"):
        step = await client.post(f"/api/v1/purchase-orders/{order_id}/{action}", headers=headers)
        assert step.status_code == 200, step.text
    purchase = await client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "purchase_order_id": order_id,
            "lines": [
                {"purchase_order_detail_id": row["id"], "quantity_received": row["quantity"]}
                for row in step.json()["details"]
            ],
        },
    )
    assert purchase.status_code == 201, purchase.text
    received = await client.post(
        f"/api/v1/purchases/{purchase.json()['id']}/receive", headers=headers
    )
    assert received.status_code == 200, received.text
    return headers, purchase.json()


async def test_rounding_residue_is_assigned_by_largest_remainder_and_sums_exactly(e2e_client):
    headers, purchase = await _two_line_received_purchase(e2e_client, "fixed-amounts-residue")
    nets = [Decimal(row["subtotal"]) - Decimal(row["discount"]) for row in purchase["details"]]
    assert sorted(nets) == [Decimal("7.5"), Decimal("37.5")]
    response = await e2e_client.post(
        "/api/v1/retaceos",
        headers=headers,
        json={
            "purchase_id": purchase["id"],
            "total_freight": "10",
            "total_dai": "0.000001",
            "total_expenses": "0",
        },
    )
    assert response.status_code == 201, response.text
    item = response.json()
    assert Decimal(item["total_fob"]) == Decimal("45")
    small, large = sorted(item["details"], key=lambda row: Decimal(row["cost_fob"]))
    # 10 x 37.5/45 = 8.333333.. and 10 x 7.5/45 = 1.666666..: the residue goes to the larger
    # fraction, so both lines add back to exactly 10.
    assert Decimal(large["freight"]) == Decimal("8.333333")
    assert Decimal(small["freight"]) == Decimal("1.666667")
    assert Decimal(large["freight"]) + Decimal(small["freight"]) == Decimal("10")
    # One micro-unit of DAI cannot be split: it goes to the line with the larger FOB.
    assert Decimal(large["dai"]) == Decimal("0.000001")
    assert Decimal(small["dai"]) == 0
    assert Decimal(item["total_cost"]) == Decimal("45") + Decimal("10.000001")
    for row in item["details"]:
        assert Decimal(row["unit_cost"]) == (
            Decimal(row["total_cost"]) / Decimal(row["quantity"])
        ).quantize(Decimal("0.000001"))
