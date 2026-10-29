"""Real receipt → labels → split → two placements with exact valued stock."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryMovementModel,
)
from app.infrastructure.models.inventory_valuation import InventoryValuationEntryModel
from app.infrastructure.models.organization import (
    Location,
    UserBranch,
    UserCompany,
    UserWarehouseAccess,
    Warehouse,
)
from app.infrastructure.models.rbac import UserRole
from app.infrastructure.models.user import User
from scripts.provision_warehouse_operator import _operator_role
from sqlalchemy import func, select

from tests.e2e.test_purchase_orders import (
    _headers,
    _receiving_location_id,
    _reference_ids,
    _sent_order,
)

pytestmark = pytest.mark.e2e


async def _staged_receipt(client):
    company, branch, warehouse, product, supplier, currency = await _reference_ids()
    headers = await _headers(
        client, company_id=company, username="placement-admin", is_superuser=True
    )
    overview = await client.get("/api/v1/inventory/valuation", headers=headers)
    opened = await client.post(
        "/api/v1/inventory/valuation/opening",
        headers=headers,
        json={
            "currency": currency,
            "reference": "B03 apertura vacía",
            "approved": True,
            "snapshot_fingerprint": overview.json()["snapshot_fingerprint"],
            "lines": [],
        },
    )
    assert opened.status_code == 200, opened.text
    order = await _sent_order(
        client,
        headers=headers,
        branch_id=branch,
        warehouse_id=warehouse,
        product_id=product,
        supplier_id=supplier,
        currency=currency,
        quantity="50",
    )
    response = await client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "purchase_order_id": order["id"],
            "supplier_invoice_number": "FAC-B03",
            "supplier_invoice_date": "2026-10-28",
            "lines": [
                {"purchase_order_detail_id": order["details"][0]["id"], "quantity_received": "50"}
            ],
        },
    )
    assert response.status_code == 201, response.text
    purchase = response.json()
    assert purchase["inventory_workflow"] == "placement_before_inventory"
    response = await client.post(f"/api/v1/purchases/{purchase['id']}/receive", headers=headers)
    assert response.status_code == 200, response.text
    response = await client.post(
        "/api/v1/retaceos",
        headers=headers,
        json={
            "purchase_id": purchase["id"],
            "total_freight": "5.123457",
            "total_dai": "3",
            "total_expenses": "0",
            "import_vat": "0",
            "fob_lines": [{"purchase_detail_id": purchase["details"][0]["id"], "amount": "100"}],
        },
    )
    assert response.status_code == 201, response.text
    for action in ("calculate", "verify", "close"):
        next_response = await client.post(
            f"/api/v1/retaceos/{response.json()['id']}/{action}", headers=headers
        )
        assert next_response.status_code == 200, next_response.text
    response = await client.post(
        f"/api/v1/purchases/{purchase['id']}/verify",
        headers=headers,
        json={
            "lines": [
                {
                    "purchase_detail_id": purchase["details"][0]["id"],
                    "quantity_accepted": "50",
                    "inventory_location_id": str(await _receiving_location_id(warehouse)),
                }
            ]
        },
    )
    assert response.status_code == 200, response.text
    return company, warehouse, headers


async def _review_unit(client, headers, unit):
    response = await client.patch(
        f"/api/v1/inventory/handling-units/{unit['id']}/measurements",
        headers=headers,
        json={"measures": {"gross_weight_kg": "0.5", "volume_m3": "0.01"}, "source": "manual"},
    )
    assert response.status_code == 200, response.text
    response = await client.post(
        "/api/v1/inventory/labels/prints",
        headers=headers,
        json={
            "idempotency_key": f"print-{unit['id']}",
            "handling_unit_id": unit["id"],
            "quantity_printed": 1,
            "print_date": datetime.now(UTC).date().isoformat(),
            "reason": "initial",
        },
    )
    assert response.status_code == 200, response.text
    confirmed = await client.post(
        "/api/v1/inventory/labels/confirmations",
        headers=headers,
        json={
            "idempotency_key": f"label-{unit['id']}",
            "handling_unit_id": unit["id"],
            "handling_unit_code": unit["code"],
            "label_print_id": response.json()["id"],
        },
    )
    assert confirmed.status_code == 200, confirmed.text


async def _operator_headers(client, company, warehouse):
    headers = await _headers(
        client, company_id=company, username="placement-operator", is_superuser=False
    )
    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.username == "placement-operator"))
        branch_id = await session.scalar(
            select(Warehouse.branch_id).where(Warehouse.id == warehouse)
        )
        member = await session.get(UserCompany, (user.id, company))
        member.access_all_branches = False
        member.warehouse_restricted = True
        member.last_branch_id = branch_id
        role = await _operator_role(session, company)
        session.add_all(
            [
                UserRole(user_id=user.id, company_id=company, role_id=role.id),
                UserBranch(
                    user_id=user.id,
                    company_id=company,
                    branch_id=branch_id,
                    is_default=True,
                    is_active=True,
                ),
                UserWarehouseAccess(user_id=user.id, company_id=company, warehouse_id=warehouse),
            ]
        )
        await session.commit()
    return {**headers, "X-Branch-ID": str(branch_id)}


async def test_pending_receipt_posts_only_when_each_prepared_unit_is_placed(e2e_client):
    client = e2e_client
    company, warehouse, headers = await _staged_receipt(client)
    operator = await _operator_headers(client, company, warehouse)
    headers = operator
    query = f"/api/v1/inventory/preparation?warehouse_id={warehouse}"
    queue = await client.get(query, headers=operator)
    assert queue.status_code == 200, queue.text
    source = queue.json()["items"][0]
    assert source["phase"] == "measure"
    assert not any(
        word in queue.text
        for word in ("entry_value", "unit_cost", "inventory_value", "entry_currency")
    )
    assert (await client.get("/api/v1/inventory/valuation", headers=operator)).status_code == 403
    assert (
        await client.get(
            "/api/v1/inventory/preparation?warehouse_id=" + str(uuid.uuid4()), headers=operator
        )
    ).status_code in (403, 404)
    visible = await client.get(
        f"/api/v1/inventory/warehouses/{warehouse}/handling-units", headers=headers
    )
    assert visible.status_code == 200, visible.text
    assert source["id"] not in visible.text
    stock_lots = await client.get(
        f"/api/v1/inventory/lots?warehouse_id={warehouse}&status=all", headers=headers
    )
    assert stock_lots.status_code == 200, stock_lots.text
    assert stock_lots.json()["items"] == []
    async with async_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(InventoryMovementModel)) == 0
        assert await session.scalar(select(func.count()).select_from(InventoryBalanceModel)) == 0
        destinations = list(
            await session.scalars(
                select(Location)
                .where(
                    Location.warehouse_id == warehouse,
                    Location.storage_eligible.is_(True),
                    Location.is_active.is_(True),
                    Location.lifecycle_status == "active",
                    Location.location_type != "receiving",
                )
                .limit(2)
            )
        )
        assert destinations
        second = Location(
            warehouse_id=warehouse,
            code="B03-R02-N01-P01",
            aisle="B03",
            rack="02",
            level="01",
            position="01",
            is_active=True,
            lifecycle_status="active",
            location_type="standard",
            storage_eligible=True,
            capacity_enforcement_mode="disabled",
        )
        session.add(second)
        session.add(
            Location(
                warehouse_id=warehouse,
                code="B03-LIMITADA",
                aisle="B03",
                rack="03",
                level="01",
                position="01",
                is_active=True,
                lifecycle_status="active",
                location_type="standard",
                storage_eligible=True,
                capacity_enforcement_mode="enforce",
                certified_max_weight_kg=Decimal("0.1"),
                operational_max_weight_kg=Decimal("0.1"),
                certified_usable_volume_m3=Decimal("0.001"),
                operational_usable_volume_m3=Decimal("0.001"),
            )
        )
        await session.commit()
        destinations = [destinations[0], second]
        codes = [row.code for row in destinations]
    body = {"idempotency_key": "b03-split-30", "quantity_base": "30", "unit_scan": source["code"]}
    split = await client.post(
        f"/api/v1/inventory/preparation/{source['id']}/split", headers=headers, json=body
    )
    assert split.status_code == 200, split.text
    replay = await client.post(
        f"/api/v1/inventory/preparation/{source['id']}/split", headers=headers, json=body
    )
    assert replay.json() == split.json()
    changed = await client.post(
        f"/api/v1/inventory/preparation/{source['id']}/split",
        headers=headers,
        json={**body, "quantity_base": "25"},
    )
    assert changed.status_code == 409, changed.text
    queue = (await client.get(query, headers=headers)).json()
    assert sorted(Decimal(row["quantity_base"]) for row in queue["items"]) == [
        Decimal("20"),
        Decimal("30"),
    ]
    for index, unit in enumerate(queue["items"]):
        place_body = {
            "idempotency_key": f"b03-place-{unit['id']}",
            "quantity_base": unit["quantity_base"],
            "unit_scan": unit["code"],
            "location_scan": codes[index],
        }
        rejected = await client.post(
            f"/api/v1/inventory/preparation/{unit['id']}/place", headers=headers, json=place_body
        )
        assert rejected.status_code == 409, rejected.text
        await _review_unit(client, headers, unit)
        wrong_scan = await client.post(
            f"/api/v1/inventory/preparation/{unit['id']}/place",
            headers=headers,
            json={**place_body, "unit_scan": "HU-OTRA-UNIDAD"},
        )
        assert wrong_scan.status_code == 409, wrong_scan.text
        capacity = await client.post(
            f"/api/v1/inventory/preparation/{unit['id']}/place",
            headers=headers,
            json={**place_body, "location_scan": "B03-LIMITADA"},
        )
        assert capacity.status_code == 409, capacity.text
        async with async_session_factory() as session:
            assert (
                await session.scalar(select(func.count()).select_from(InventoryMovementModel))
                == index
            )
        wrong = await client.post(
            f"/api/v1/inventory/preparation/{unit['id']}/place",
            headers=headers,
            json={**place_body, "location_scan": "OTRA-BODEGA-NO-EXISTE"},
        )
        assert wrong.status_code == 409, wrong.text
        placed = await client.post(
            f"/api/v1/inventory/preparation/{unit['id']}/place", headers=headers, json=place_body
        )
        assert placed.status_code == 200, placed.text
        replay = await client.post(
            f"/api/v1/inventory/preparation/{unit['id']}/place", headers=headers, json=place_body
        )
        assert replay.json() == placed.json()
        again = await client.post(
            f"/api/v1/inventory/preparation/{unit['id']}/place",
            headers=headers,
            json={**place_body, "idempotency_key": f"again-{unit['id']}"},
        )
        assert again.status_code == 409, again.text
    assert (await client.get(query, headers=headers)).json()["meta"]["total"] == 0
    foreign = await client.get(query, headers={**headers, "X-Company-ID": str(uuid.uuid4())})
    assert foreign.status_code in (403, 404), foreign.text
    async with async_session_factory() as session:
        assert await session.scalar(
            select(func.sum(InventoryBalanceModel.quantity_base))
        ) == Decimal("50")
        quantity, value = (
            await session.execute(
                select(
                    func.sum(InventoryValuationEntryModel.quantity_base),
                    func.sum(InventoryValuationEntryModel.inventory_delta),
                ).where(InventoryValuationEntryModel.kind == "receipt")
            )
        ).one()
        assert quantity == Decimal("50")
        assert value == Decimal("108.123457")
        assert await session.scalar(select(func.count()).select_from(InventoryMovementModel)) == 2
        stored = list(await session.scalars(select(InventoryHandlingUnitModel)))
        assert all(row.inventory_posted_at is not None for row in stored)
