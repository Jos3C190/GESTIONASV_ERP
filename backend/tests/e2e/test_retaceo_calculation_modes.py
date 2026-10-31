from decimal import ROUND_HALF_UP, Decimal

import pytest

from tests.e2e.test_purchase_orders import _headers, _reference_ids, _sent_order

pytestmark = pytest.mark.e2e


async def test_automatic_taxes_persist_and_manual_mode_accepts_operator_amounts(e2e_client):
    company, branch, warehouse, product, supplier, currency = await _reference_ids()
    headers = await _headers(
        e2e_client, company_id=company, username="automatic-retaceo", is_superuser=True
    )
    order = await _sent_order(
        e2e_client,
        headers=headers,
        branch_id=branch,
        warehouse_id=warehouse,
        product_id=product,
        supplier_id=supplier,
        currency=currency,
        quantity="2.000000",
    )
    response = await e2e_client.post(
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
    response = await e2e_client.post(f"/api/v1/purchases/{purchase['id']}/receive", headers=headers)
    assert response.status_code == 200, response.text
    fob = sum(
        (Decimal(row["subtotal"]) - Decimal(row["discount"]) for row in purchase["details"]),
        Decimal("0"),
    )
    response = await e2e_client.post(
        "/api/v1/retaceos",
        headers=headers,
        json={
            "purchase_id": purchase["id"],
            "calculation_mode": "automatic",
            "dai_rate": "10",
            "vat_rate": "13",
            "total_freight": "10",
            "total_expenses": "0",
        },
    )
    assert response.status_code == 201, response.text
    item = response.json()
    quantum = Decimal("0.000001")
    dai = ((fob + 10) * Decimal("0.10")).quantize(quantum, rounding=ROUND_HALF_UP)
    vat = ((fob + 10 + dai) * Decimal("0.13")).quantize(quantum, rounding=ROUND_HALF_UP)
    assert Decimal(item["total_fob"]) == fob
    assert Decimal(item["total_dai"]) == dai
    assert Decimal(item["import_vat"]) == vat
    assert Decimal(item["total_cost"]) == fob + 10 + dai
    saved = await e2e_client.get(f"/api/v1/retaceos/{item['id']}", headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["calculation_mode"] == "automatic"
    assert Decimal(saved.json()["dai_rate"]) == Decimal("10")
    assert Decimal(saved.json()["vat_rate"]) == Decimal("13")

    # Removing taxes keeps the original fixed-cost rows as inactive history.
    response = await e2e_client.put(
        f"/api/v1/retaceos/{item['id']}",
        headers=headers,
        json={
            "calculation_mode": "automatic",
            "dai_rate": "0",
            "vat_rate": "0",
            "total_freight": "5",
            "total_expenses": "0",
        },
    )
    assert response.status_code == 200, response.text
    zeroed = response.json()
    assert Decimal(zeroed["total_dai"]) == 0
    assert Decimal(zeroed["import_vat"]) == 0
    freight = next(
        row for row in zeroed["costs"] if row["classification"] == "freight" and row["is_active"]
    )
    detail_id = purchase["details"][0]["id"]
    costs = [
        {
            "id": freight["id"],
            "classification": "freight",
            "title": "Flete y seguro",
            "amount": "5",
            "allocations": [{"purchase_detail_id": detail_id, "amount": "5"}],
        },
        {
            "classification": "dai",
            "title": "DAI manual",
            "amount": "3",
            "allocations": [{"purchase_detail_id": detail_id, "amount": "3"}],
        },
        {"classification": "import_vat", "title": "IVA manual", "amount": "7", "allocations": []},
    ]
    response = await e2e_client.put(
        f"/api/v1/retaceos/{item['id']}",
        headers=headers,
        json={
            "calculation_mode": "manual",
            "fob_lines": [
                {
                    "purchase_detail_id": row["id"],
                    "amount": str(Decimal(row["subtotal"]) - Decimal(row["discount"])),
                }
                for row in purchase["details"]
            ],
            "total_freight": "5",
            "total_expenses": "0",
            "total_dai": "3",
            "import_vat": "7",
            "costs": costs,
        },
    )
    assert response.status_code == 200, response.text
    manual = response.json()
    assert manual["calculation_mode"] == "manual"
    assert manual["dai_rate"] is None
    assert manual["vat_rate"] is None
    assert Decimal(manual["total_dai"]) == 3
    assert Decimal(manual["import_vat"]) == 7
    assert Decimal(manual["total_cost"]) == fob + 8
