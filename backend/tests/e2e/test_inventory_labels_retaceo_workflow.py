"""Label printing after manual retaceo: real persistence, replay and stock invariance."""

import uuid
from datetime import UTC, datetime

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.inventory import InventoryHandlingUnitModel, InventoryMovementModel
from app.infrastructure.models.inventory_lot import InventoryLotModel
from app.infrastructure.models.retaceo import RetaceoModel
from sqlalchemy import func, select

from tests.e2e.test_purchase_orders import (
    _headers,
    _receiving_location_id,
    _reference_ids,
    _sent_order,
)

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("archived_product", [False, True], ids=["catalogue", "archived-product"])
async def test_labels_preserve_receipt_identity_and_stock_after_manual_retaceo(
    e2e_client, archived_product
):
    client = e2e_client
    company, branch, warehouse, product, supplier, currency = await _reference_ids()
    headers = await _headers(client, company_id=company, username="labels-b02", is_superuser=True)
    overview = await client.get("/api/v1/inventory/valuation", headers=headers)
    assert overview.status_code == 200, overview.text
    opening = await client.post(
        "/api/v1/inventory/valuation/opening",
        headers=headers,
        json={
            "currency": currency,
            "reference": "B02 apertura de prueba sin existencias",
            "snapshot_fingerprint": overview.json()["snapshot_fingerprint"],
            "approved": True,
            "lines": [],
        },
    )
    assert opening.status_code == 200, opening.text
    order = await _sent_order(
        client,
        headers=headers,
        branch_id=branch,
        warehouse_id=warehouse,
        product_id=product,
        supplier_id=supplier,
        currency=currency,
    )
    response = await client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "purchase_order_id": order["id"],
            "supplier_invoice_number": "FAC-B02-01",
            "supplier_invoice_date": "2026-10-28",
            "lines": [
                {"purchase_order_detail_id": order["details"][0]["id"], "quantity_received": "4"}
            ],
        },
    )
    assert response.status_code == 201, response.text
    purchase = response.json()
    response = await client.post(f"/api/v1/purchases/{purchase['id']}/receive", headers=headers)
    assert response.status_code == 200, response.text
    response = await client.post(
        "/api/v1/retaceos",
        headers=headers,
        json={
            "purchase_id": purchase["id"],
            "total_freight": "5",
            "total_dai": "3",
            "total_expenses": "0",
            "import_vat": "0",
            "fob_lines": [{"purchase_detail_id": purchase["details"][0]["id"], "amount": "100"}],
        },
    )
    assert response.status_code == 201, response.text
    retaceo_id = response.json()["id"]
    for action in ("calculate", "verify", "close"):
        response = await client.post(f"/api/v1/retaceos/{retaceo_id}/{action}", headers=headers)
        assert response.status_code == 200, response.text
    response = await client.post(
        f"/api/v1/purchases/{purchase['id']}/verify",
        headers=headers,
        json={
            "lines": [
                {
                    "purchase_detail_id": purchase["details"][0]["id"],
                    "quantity_accepted": "4",
                    "inventory_location_id": str(await _receiving_location_id(warehouse)),
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    async with async_session_factory() as session:
        lot = await session.scalar(
            select(InventoryLotModel).where(
                InventoryLotModel.purchase_id == uuid.UUID(purchase["id"])
            )
        )
        unit = await session.scalar(
            select(InventoryHandlingUnitModel).where(
                InventoryHandlingUnitModel.inventory_lot_id == lot.id
            )
        )
        unit_id, unit_quantity, lot_id = unit.id, unit.quantity_base, lot.id
        detail_id = unit.inventory_lot_detail_id
        catalogue_product = await session.get(ProductModel, product)
        product_name = catalogue_product.name
        product_code = catalogue_product.internal_code or catalogue_product.sku
        if archived_product:
            catalogue_product.deleted_at = datetime.now(UTC)
            await session.commit()
        movement_count = await session.scalar(
            select(func.count()).select_from(InventoryMovementModel)
        )
    preview_path = f"/api/v1/inventory/labels/preview?handling_unit_id={unit_id}"
    response = await client.get(preview_path, headers=headers)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["product_name"] == product_name
    assert preview["product_internal_code"] == product_code
    detail_preview = await client.get(
        f"/api/v1/inventory/labels/preview?inventory_lot_detail_id={detail_id}", headers=headers
    )
    assert detail_preview.status_code == 200, detail_preview.text
    assert detail_preview.json()["product_name"] == product_name
    assert detail_preview.json()["receipt_lot_code"] == preview["receipt_lot_code"]
    payload = {
        "idempotency_key": "label-b02-0001",
        "handling_unit_id": str(unit_id),
        "quantity_printed": 2,
        "print_date": datetime.now(UTC).date().isoformat(),
        "reason": "initial",
        "layout": {"content": "barcode", "width_mm": 80, "height_mm": 80},
        "notes": "Mantener seco",
    }
    response = await client.post("/api/v1/inventory/labels/prints", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    printed = response.json()
    assert printed["label_snapshot"]["receipt_lot_code"] == preview["receipt_lot_code"]
    assert printed["label_snapshot"]["received_on"] == preview["received_on"]
    assert printed["label_snapshot"]["notes"] == "Mantener seco"
    replay = await client.post("/api/v1/inventory/labels/prints", headers=headers, json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == printed["id"]
    reprint = await client.post(
        "/api/v1/inventory/labels/prints",
        headers=headers,
        json={
            **payload,
            "idempotency_key": "label-b02-0002",
            "reason": "reprint",
            "notes": None,
        },
    )
    assert reprint.status_code == 200, reprint.text
    assert reprint.json()["inventory_lot_id"] == str(lot_id)
    assert reprint.json()["label_snapshot"]["received_on"] == preview["received_on"]
    foreign = await client.get(preview_path, headers={**headers, "X-Company-ID": str(uuid.uuid4())})
    assert foreign.status_code in {403, 404}, foreign.text
    reader = await _headers(
        client, company_id=company, username="labels-without-receive", is_superuser=False
    )
    forbidden = await client.post(
        "/api/v1/inventory/labels/prints",
        headers=reader,
        json={
            **payload,
            "idempotency_key": "label-without-permission",
        },
    )
    assert forbidden.status_code == 403, forbidden.text
    async with async_session_factory() as session:
        visible_product = await session.scalar(
            select(ProductModel).where(ProductModel.id_product == product)
        )
        assert (visible_product is None) == archived_product
        stored_product = await session.scalar(
            select(ProductModel)
            .where(ProductModel.id_product == product)
            .execution_options(include_deleted=True)
        )
        assert (stored_product.deleted_at is not None) == archived_product
        unit = await session.get(InventoryHandlingUnitModel, unit_id)
        assert unit.quantity_base == unit_quantity
        assert unit.inventory_lot_id == lot_id
        assert movement_count == await session.scalar(
            select(func.count()).select_from(InventoryMovementModel)
        )
        # A persisted, verified but unclosed calculation must not enable printing.
        retaceo = await session.get(RetaceoModel, uuid.UUID(retaceo_id))
        retaceo.status = "verified"
        await session.commit()
    blocked = await client.get(preview_path, headers=headers)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "inventory_label_retaceo_not_final"
