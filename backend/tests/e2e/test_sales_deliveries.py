"""B07 real-PostgreSQL/API verification for physical sales deliveries."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"


async def _seed_receipt(company_id, actor_id, payload):
    """Build pre-existing stock for sales tests, outside the public receipt API.

    Purchase receipts now require their purchase/retaceo/placement documents.
    The complete public path is covered by test_inventory_final_acceptance;
    this fixture only establishes the independent delivery/return scenarios.
    """
    from app.api.v1.schemas.inventory import MovementConfirmIn, MovementOut
    from app.application.inventory import InventoryUseCases
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository

    command = MovementConfirmIn.model_validate(payload)
    async with async_session_factory() as session:
        result = await InventoryUseCases(SqlAlchemyInventoryRepository(session)).post_movement(
            company_id=company_id,
            actor_id=actor_id,
            movement_type=command.movement_type,
            idempotency_key=command.idempotency_key,
            source_reference=command.source_reference,
            lines=[line.model_dump() for line in command.lines],
        )
        await session.commit()
        return MovementOut.model_validate(result).model_dump(mode="json")


async def _login(client, username: str, company_id: uuid.UUID) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"login": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {
        "Authorization": f"Bearer {response.json()['access_token']}",
        "X-Company-ID": str(company_id),
    }


async def _physical_value(company_id: uuid.UUID, inventory_item_id: uuid.UUID):
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.inventory import InventoryBalanceModel
    from app.infrastructure.models.inventory_valuation import InventoryCostAverageModel

    async with async_session_factory() as session:
        quantity = Decimal(
            await session.scalar(
                select(func.coalesce(func.sum(InventoryBalanceModel.quantity_base), 0)).where(
                    InventoryBalanceModel.company_id == company_id,
                    InventoryBalanceModel.inventory_item_id == inventory_item_id,
                )
            )
        )
        average = await session.get(InventoryCostAverageModel, (company_id, inventory_item_id))
        value = Decimal(average.inventory_value) if average else None
        return quantity, value


async def _shipment_artifacts(company_id: uuid.UUID, delivery_id: uuid.UUID) -> tuple[int, int]:
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.inventory import InventoryMovementModel
    from app.infrastructure.models.sales_delivery import (
        SalesDeliveryAllocationModel,
        SalesDeliveryLineModel,
    )

    async with async_session_factory() as session:
        movement_count = int(
            await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == company_id,
                    InventoryMovementModel.idempotency_key
                    == f"sales-delivery-confirm:{delivery_id}",
                )
            )
            or 0
        )
        issue_links = int(
            await session.scalar(
                select(func.count(SalesDeliveryAllocationModel.id))
                .select_from(SalesDeliveryAllocationModel)
                .join(
                    SalesDeliveryLineModel,
                    (SalesDeliveryLineModel.company_id == SalesDeliveryAllocationModel.company_id)
                    & (SalesDeliveryLineModel.id == SalesDeliveryAllocationModel.delivery_line_id),
                )
                .where(
                    SalesDeliveryLineModel.delivery_id == delivery_id,
                    SalesDeliveryAllocationModel.movement_line_id.is_not(None),
                )
            )
            or 0
        )
        return movement_count, issue_links


@pytest.mark.asyncio
async def test_sales_delivery_partial_cost_idempotency_concurrency_and_rollback(
    e2e_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.application.sales.deliveries import SalesDeliveryService
    from app.domain.entities.inventory import InventoryOperationError
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
    from app.infrastructure.models.inventory import (
        InventoryHandlingUnitModel,
        InventoryItemModel,
        InventoryPackagingModel,
    )
    from app.infrastructure.models.inventory_valuation import (
        InventoryCostAverageModel,
        InventoryValuationEntryModel,
    )
    from app.infrastructure.models.organization import Branch, Location, Warehouse
    from app.infrastructure.models.sales_delivery import (
        SalesDeliveryAllocationModel,
        SalesDeliveryLineModel,
        SalesDeliveryModel,
    )
    from app.infrastructure.repositories.inventory_valuation_repository import (
        SqlAlchemyInventoryValuationRepository,
    )

    company_id = await get_test_company_id()
    username = f"b07-admin-{uuid.uuid4().hex[:8]}"
    actor_id = uuid.UUID(
        await seed_user(username=username, email=f"{username}@example.test", is_superuser=True)
    )
    headers = await _login(e2e_client, username, company_id)

    async with async_session_factory() as session:
        product = await session.scalar(
            select(ProductModel)
            .join(
                CompanyUnitModel,
                (CompanyUnitModel.company_id == ProductModel.company_id)
                & (CompanyUnitModel.unit_id == ProductModel.sale_unit),
            )
            .where(
                ProductModel.company_id == company_id,
                ProductModel.is_active.is_(True),
                ProductModel.can_sell.is_(True),
                ProductModel.product_kind == "goods",
                ProductModel.lifecycle_status == "active",
                ProductModel.variant_mode == "standalone",
                ProductModel.deleted_at.is_(None),
                CompanyUnitModel.is_enabled.is_(True),
            )
            .order_by(ProductModel.id_product)
            .limit(1)
        )
        assert product is not None
        item = await session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.product_id == product.id_product,
                InventoryItemModel.is_active.is_(True),
            )
        )
        if item is None:
            item = InventoryItemModel(
                company_id=company_id,
                product_id=product.id_product,
                base_unit_id=product.sale_unit,
                is_active=True,
            )
            session.add(item)
            await session.flush()
        inventory_item_id = item.id
        product_id = product.id_product
        base_unit_id = product.sale_unit
        package_unit = await session.scalar(
            select(CompanyUnitModel)
            .where(
                CompanyUnitModel.company_id == company_id,
                CompanyUnitModel.unit_id != base_unit_id,
                CompanyUnitModel.is_enabled.is_(True),
            )
            .order_by(CompanyUnitModel.unit_id)
            .limit(1)
        )
        assert package_unit is not None, "La semilla B07 requiere una unidad de empaque adicional."
        package = InventoryPackagingModel(
            company_id=company_id,
            inventory_item_id=item.id,
            packaging_unit_id=package_unit.unit_id,
            code=f"B07-PACK-{uuid.uuid4().hex[:8]}",
            name="Empaque controlado B07",
            packaging_type="box",
            version=1,
            base_quantity=Decimal("2"),
            is_current=True,
            is_active=True,
        )
        session.add(package)
        await session.flush()
        packaging_id = package.id
        packaging_code = package.code
        package_unit_id = package_unit.unit_id

        branch_locations: dict[uuid.UUID, tuple[Branch, Warehouse, Location]] = {}
        stock_rows = (
            await session.execute(
                select(Branch, Warehouse, Location)
                .join(
                    Warehouse,
                    (Warehouse.branch_id == Branch.id)
                    & (Warehouse.company_id == Branch.company_id),
                )
                .join(
                    Location,
                    (Location.warehouse_id == Warehouse.id) & (Location.deleted_at.is_(None)),
                )
                .where(
                    Branch.company_id == company_id,
                    Branch.is_active.is_(True),
                    Branch.operational_status == "active",
                    Branch.deleted_at.is_(None),
                    Warehouse.is_active.is_(True),
                    Warehouse.is_transit.is_(False),
                    Warehouse.operational_status == "active",
                    Warehouse.deleted_at.is_(None),
                    Location.is_active.is_(True),
                    Location.lifecycle_status == "active",
                    Location.storage_eligible.is_(True),
                    Location.location_type != "virtual",
                )
                .order_by(Branch.code, Warehouse.id, Location.id)
            )
        ).all()
        for branch, warehouse, location in stock_rows:
            branch_locations.setdefault(branch.id, (branch, warehouse, location))
        locations = list(branch_locations.values())
        assert len(locations) >= 2, (
            "La semilla B07 requiere dos sucursales con ubicaciones activas."
        )
        branch_a, _, location_a = locations[0]
        branch_b, _, location_b = locations[1]
        await session.commit()

    catalog_response = await e2e_client.get("/api/v1/sales/catalog", headers=headers)
    assert catalog_response.status_code == 200, catalog_response.text
    assert any(
        row["inventory_item_id"] == str(inventory_item_id) for row in catalog_response.json()
    )

    receipt_lines = [
        (location_a.id, "available", "3", "B07-HU-A-3"),
        (location_a.id, "available", "2", "B07-HU-A-2"),
        (location_a.id, "quarantine", "1", "B07-HU-A-Q"),
        (location_b.id, "available", "7", "B07-HU-B-7"),
    ]
    receipt = await _seed_receipt(
        company_id,
        actor_id,
        {
            "idempotency_key": f"b07-receipt-{uuid.uuid4()}",
            "movement_type": "receipt",
            "source_reference": "B07 automation: opening test stock",
            "lines": [
                {
                    "inventory_item_id": str(inventory_item_id),
                    "to_location_id": str(location_id),
                    "to_stock_status": stock_status,
                    "quantity_base": quantity,
                    "handling_unit_code": code,
                    "actual_measures": {"gross_weight_kg": "1", "volume_m3": "0.1"},
                }
                for location_id, stock_status, quantity, code in receipt_lines
            ],
        },
    )
    receipt_units = [line["handling_unit_id"] for line in receipt["lines"]]
    assert len(receipt_units) == len(receipt_lines)
    hu_a3, hu_a2, hu_quarantine, hu_branch_b = receipt_units

    overview = await e2e_client.get("/api/v1/inventory/valuation", headers=headers)
    assert overview.status_code == 200, overview.text
    opening = await e2e_client.post(
        "/api/v1/inventory/valuation/opening",
        headers=headers,
        json={
            "currency": "USD",
            "reference": "B07 test cut and approval",
            "snapshot_fingerprint": overview.json()["snapshot_fingerprint"],
            "approved": True,
            "lines": [
                {
                    "inventory_item_id": str(inventory_item_id),
                    "quantity_base": "13",
                    "total_cost": "130",
                    "cost_reference": "B07 controlled test average: USD 10 per base unit",
                }
            ],
        },
    )
    assert opening.status_code == 200, opening.text
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("13.000000"),
        Decimal("130.000000"),
    )

    customer = await e2e_client.post(
        "/api/v1/sales/customers",
        headers=headers,
        json={"code": f"B07-{uuid.uuid4().hex[:8]}", "name": "Cliente de prueba B07"},
    )
    assert customer.status_code == 201, customer.text
    valid_until = (
        datetime.now(ZoneInfo("America/El_Salvador")).date() + timedelta(days=2)
    ).isoformat()
    quotation = await e2e_client.post(
        "/api/v1/sales/quotations",
        headers={**headers, "Idempotency-Key": f"b07-quote-{uuid.uuid4()}"},
        json={
            "branch_id": str(branch_a.id),
            "customer_id": customer.json()["id"],
            "valid_until": valid_until,
            "currency": "USD",
            "lines": [
                {
                    "product_id": product_id,
                    "variant_id": None,
                    "unit_id": package_unit_id,
                    "quantity": "1",
                    "unit_price": "40",
                },
                {
                    "product_id": product_id,
                    "variant_id": None,
                    "unit_id": base_unit_id,
                    "quantity": "3",
                    "unit_price": "20",
                },
            ],
        },
    )
    assert quotation.status_code == 201, quotation.text
    quote = await e2e_client.post(
        f"/api/v1/sales/quotations/{quotation.json()['id']}/confirm",
        headers=headers,
        json={"expected_version": quotation.json()["version"]},
    )
    assert quote.status_code == 200, quote.text
    sale_response = await e2e_client.post(
        f"/api/v1/sales/quotations/{quote.json()['id']}/convert",
        headers={**headers, "Idempotency-Key": f"b07-convert-{uuid.uuid4()}"},
        json={"expected_version": quote.json()["version"]},
    )
    assert sale_response.status_code == 200, sale_response.text
    sale = await e2e_client.post(
        f"/api/v1/sales/{sale_response.json()['id']}/confirm",
        headers=headers,
        json={"expected_version": sale_response.json()["version"]},
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["id"]
    assert len(sale.json()["lines"]) == 2
    package_sale_line_id = sale.json()["lines"][0]["id"]
    base_sale_line_id = sale.json()["lines"][1]["id"]
    assert sale.json()["lines"][0]["unit_factor"] == "2.000000"
    assert sale.json()["lines"][0]["quantity_base"] == "2.000000"
    assert sale.json()["lines"][1]["unit_factor"] == "1.000000"
    assert sale.json()["delivery_progress"] == "pending"
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("13.000000"),
        Decimal("130.000000"),
    )

    async with async_session_factory() as session:
        original_package = await session.get(InventoryPackagingModel, packaging_id)
        assert original_package is not None
        original_package.is_current = False
        session.add(
            InventoryPackagingModel(
                company_id=company_id,
                inventory_item_id=inventory_item_id,
                packaging_unit_id=package_unit_id,
                code=packaging_code,
                name="Empaque B07 actualizado después de vender",
                packaging_type="box",
                version=2,
                base_quantity=Decimal("4"),
                supersedes_id=packaging_id,
                is_current=True,
                is_active=True,
            )
        )
        await session.commit()
    frozen_sale = await e2e_client.get(f"/api/v1/sales/{sale_id}", headers=headers)
    assert frozen_sale.status_code == 200, frozen_sale.text
    assert frozen_sale.json()["lines"][0]["unit_factor"] == "2.000000"
    assert frozen_sale.json()["lines"][0]["quantity_base"] == "2.000000"

    stock = await e2e_client.get(f"/api/v1/sales/{sale_id}/delivery-stock", headers=headers)
    assert stock.status_code == 200, stock.text
    assert {row["sale_line_id"] for row in stock.json()} == {
        package_sale_line_id,
        base_sale_line_id,
    }
    for stock_line in stock.json():
        candidate_ids = {row["handling_unit_id"] for row in stock_line["units"]}
        assert candidate_ids == {hu_a3, hu_a2}
        assert hu_quarantine not in candidate_ids
        assert hu_branch_b not in candidate_ids

    full_assignment = [
        {"sale_line_id": package_sale_line_id, "handling_unit_id": hu_a2},
        {"sale_line_id": base_sale_line_id, "handling_unit_id": hu_a3},
    ]
    create_key = f"b07-create-{uuid.uuid4()}"
    first_draft = await e2e_client.post(
        f"/api/v1/sales/{sale_id}/deliveries",
        headers={**headers, "Idempotency-Key": create_key},
        json={"notes": "Primera preparación B07", "assignments": full_assignment},
    )
    assert first_draft.status_code == 201, first_draft.text
    delivery_id = first_draft.json()["id"]
    assert sum(
        (Decimal(line["quantity_base"]) for line in first_draft.json()["lines"]), Decimal("0")
    ) == Decimal("5.000000")
    assert {line["sale_line_id"]: line["unit_factor"] for line in first_draft.json()["lines"]} == {
        package_sale_line_id: "2.000000",
        base_sale_line_id: "1.000000",
    }
    assert "applied_total_cost" not in first_draft.text
    replay_draft = await e2e_client.post(
        f"/api/v1/sales/{sale_id}/deliveries",
        headers={**headers, "Idempotency-Key": create_key},
        json={"notes": "Primera preparación B07", "assignments": full_assignment},
    )
    assert replay_draft.status_code == 201, replay_draft.text
    assert replay_draft.json()["id"] == delivery_id
    conflict_draft = await e2e_client.post(
        f"/api/v1/sales/{sale_id}/deliveries",
        headers={**headers, "Idempotency-Key": create_key},
        json={
            "notes": "Contenido cambiado",
            "assignments": [{"sale_line_id": base_sale_line_id, "handling_unit_id": hu_a3}],
        },
    )
    assert conflict_draft.status_code == 409
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("13.000000"),
        Decimal("130.000000"),
    )

    original_post = SqlAlchemyInventoryValuationRepository.post_physical_line

    async def fail_on_second_line(self, row, data, *, movement_type, reference, actor_id):
        if row.line_number == 2:
            raise InventoryOperationError(
                "Falla inyectada de aplicación en la segunda línea B07.",
                code="b07_second_line_failure",
                status_code=409,
            )
        return await original_post(
            self,
            row,
            data,
            movement_type=movement_type,
            reference=reference,
            actor_id=actor_id,
        )

    with monkeypatch.context() as patcher:
        patcher.setattr(
            SqlAlchemyInventoryValuationRepository, "post_physical_line", fail_on_second_line
        )
        failed_second_line = await e2e_client.post(
            f"/api/v1/sales/deliveries/{delivery_id}/confirm",
            headers={**headers, "Idempotency-Key": f"b07-second-line-app-{uuid.uuid4()}"},
            json={"expected_version": first_draft.json()["version"]},
        )
    assert failed_second_line.status_code == 409, failed_second_line.text
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("13.000000"),
        Decimal("130.000000"),
    )
    assert await _shipment_artifacts(company_id, uuid.UUID(delivery_id)) == (0, 0)
    async with async_session_factory() as session:
        assert (
            await session.scalar(
                select(func.count(InventoryValuationEntryModel.id)).where(
                    InventoryValuationEntryModel.company_id == company_id,
                    InventoryValuationEntryModel.inventory_item_id == inventory_item_id,
                    InventoryValuationEntryModel.kind == "issue",
                )
            )
            == 0
        )

    async def fail_unexpected_second_line(self, row, data, *, movement_type, reference, actor_id):
        if row.line_number == 2:
            raise RuntimeError("B07 injected unexpected second-line failure")
        return await original_post(
            self,
            row,
            data,
            movement_type=movement_type,
            reference=reference,
            actor_id=actor_id,
        )

    with monkeypatch.context() as patcher:
        patcher.setattr(
            SqlAlchemyInventoryValuationRepository,
            "post_physical_line",
            fail_unexpected_second_line,
        )
        with pytest.raises(RuntimeError, match="B07 injected unexpected second-line failure"):
            await e2e_client.post(
                f"/api/v1/sales/deliveries/{delivery_id}/confirm",
                headers={**headers, "Idempotency-Key": f"b07-second-line-runtime-{uuid.uuid4()}"},
                json={"expected_version": first_draft.json()["version"]},
            )
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("13.000000"),
        Decimal("130.000000"),
    )
    assert await _shipment_artifacts(company_id, uuid.UUID(delivery_id)) == (0, 0)

    edited_draft = await e2e_client.put(
        f"/api/v1/sales/deliveries/{delivery_id}",
        headers=headers,
        json={
            "expected_version": first_draft.json()["version"],
            "notes": "Entrega parcial de 3 unidades base",
            "assignments": [{"sale_line_id": base_sale_line_id, "handling_unit_id": hu_a3}],
        },
    )
    assert edited_draft.status_code == 200, edited_draft.text
    competing_draft = await e2e_client.post(
        f"/api/v1/sales/{sale_id}/deliveries",
        headers={**headers, "Idempotency-Key": f"b07-competing-{uuid.uuid4()}"},
        json={
            "notes": "Preparación concurrente",
            "assignments": [{"sale_line_id": base_sale_line_id, "handling_unit_id": hu_a3}],
        },
    )
    assert competing_draft.status_code == 201, competing_draft.text
    first_command = f"b07-confirm-partial-{uuid.uuid4()}"
    second_command = f"b07-confirm-competing-{uuid.uuid4()}"

    async def confirm(delivery_id: str, version: int, key: str):
        return await e2e_client.post(
            f"/api/v1/sales/deliveries/{delivery_id}/confirm",
            headers={**headers, "Idempotency-Key": key},
            json={"expected_version": version},
        )

    concurrent_confirms = await asyncio.gather(
        confirm(delivery_id, edited_draft.json()["version"], first_command),
        confirm(competing_draft.json()["id"], competing_draft.json()["version"], second_command),
    )
    assert sorted(response.status_code for response in concurrent_confirms) == [200, 409], [
        response.text for response in concurrent_confirms
    ]
    winning_delivery = next(
        response.json() for response in concurrent_confirms if response.status_code == 200
    )
    assert winning_delivery["status"] == "confirmed"
    losing_delivery_id, losing_delivery_version = (
        (competing_draft.json()["id"], competing_draft.json()["version"])
        if concurrent_confirms[0].status_code == 200
        else (delivery_id, edited_draft.json()["version"])
    )
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("10.000000"),
        Decimal("100.000000"),
    )
    sale_partial = await e2e_client.get(f"/api/v1/sales/{sale_id}", headers=headers)
    assert sale_partial.status_code == 200, sale_partial.text
    assert sale_partial.json()["delivery_progress"] == "partial"
    partial_lines = {line["id"]: line for line in sale_partial.json()["lines"]}
    assert partial_lines[base_sale_line_id]["quantity_delivered_base"] == "3.000000"
    assert partial_lines[base_sale_line_id]["quantity_pending_base"] == "0.000000"
    assert partial_lines[package_sale_line_id]["quantity_delivered_base"] == "0.000000"
    assert partial_lines[package_sale_line_id]["quantity_pending_base"] == "2.000000"

    cancelled_loser = await e2e_client.post(
        f"/api/v1/sales/deliveries/{losing_delivery_id}/cancel",
        headers=headers,
        json={"expected_version": losing_delivery_version, "reason": "Conflicto de stock"},
    )
    assert cancelled_loser.status_code == 200, cancelled_loser.text

    second_draft = await e2e_client.post(
        f"/api/v1/sales/{sale_id}/deliveries",
        headers={**headers, "Idempotency-Key": f"b07-final-create-{uuid.uuid4()}"},
        json={
            "notes": "Entrega del saldo pendiente",
            "assignments": [{"sale_line_id": package_sale_line_id, "handling_unit_id": hu_a2}],
        },
    )
    assert second_draft.status_code == 201, second_draft.text
    second_delivery_id = second_draft.json()["id"]

    original_audit = SalesDeliveryService._audit

    async def fail_confirmation_audit(self, *, action, **kwargs):
        if action == "SALES_DELIVERY_CONFIRMED":
            raise RuntimeError("B07 injected confirmation audit failure")
        await original_audit(self, action=action, **kwargs)

    second_confirm_key = f"b07-confirm-final-{uuid.uuid4()}"
    with monkeypatch.context() as patcher:
        patcher.setattr(SalesDeliveryService, "_audit", fail_confirmation_audit)
        with pytest.raises(RuntimeError, match="B07 injected confirmation audit failure"):
            await confirm(second_delivery_id, second_draft.json()["version"], second_confirm_key)
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("10.000000"),
        Decimal("100.000000"),
    )
    assert await _shipment_artifacts(company_id, uuid.UUID(second_delivery_id)) == (0, 0)

    cancellation_and_delivery = await asyncio.gather(
        confirm(second_delivery_id, second_draft.json()["version"], second_confirm_key),
        e2e_client.post(
            f"/api/v1/sales/{sale_id}/cancel",
            headers=headers,
            json={
                "expected_version": sale_partial.json()["version"],
                "reason": "Prueba de carrera con entrega",
            },
        ),
    )
    final_delivery, sale_cancellation = cancellation_and_delivery
    assert final_delivery.status_code == 200, final_delivery.text
    assert sale_cancellation.status_code in {409, 422}, sale_cancellation.text
    replay_confirmation = await confirm(
        second_delivery_id, second_draft.json()["version"], second_confirm_key
    )
    assert replay_confirmation.status_code == 200, replay_confirmation.text
    assert replay_confirmation.json()["id"] == final_delivery.json()["id"]

    final_sale = await e2e_client.get(f"/api/v1/sales/{sale_id}", headers=headers)
    assert final_sale.status_code == 200, final_sale.text
    assert final_sale.json()["delivery_progress"] == "complete"
    final_lines = {line["id"]: line for line in final_sale.json()["lines"]}
    assert final_lines[base_sale_line_id]["quantity_delivered_base"] == "3.000000"
    assert Decimal(final_lines[base_sale_line_id]["quantity_pending_base"]) == Decimal("0")
    assert final_lines[package_sale_line_id]["quantity_delivered_base"] == "2.000000"
    assert Decimal(final_lines[package_sale_line_id]["quantity_pending_base"]) == Decimal("0")
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("8.000000"),
        Decimal("80.000000"),
    )
    async with async_session_factory() as session:
        average = await session.get(InventoryCostAverageModel, (company_id, inventory_item_id))
        assert average is not None
        assert average.average_unit_cost == Decimal("10.000000")
        allocations = list(
            (
                await session.scalars(
                    select(SalesDeliveryAllocationModel)
                    .join(
                        SalesDeliveryLineModel,
                        (
                            SalesDeliveryLineModel.company_id
                            == SalesDeliveryAllocationModel.company_id
                        )
                        & (
                            SalesDeliveryLineModel.id
                            == SalesDeliveryAllocationModel.delivery_line_id
                        ),
                    )
                    .join(
                        SalesDeliveryModel,
                        (SalesDeliveryModel.company_id == SalesDeliveryLineModel.company_id)
                        & (SalesDeliveryModel.id == SalesDeliveryLineModel.delivery_id),
                    )
                    .where(
                        SalesDeliveryAllocationModel.company_id == company_id,
                        SalesDeliveryModel.sale_id == uuid.UUID(sale_id),
                        SalesDeliveryModel.status == "confirmed",
                    )
                )
            ).all()
        )
        assert len(allocations) == 2
        assert all(row.movement_line_id and row.valuation_entry_id for row in allocations)
        assert sum(
            (Decimal(row.applied_total_cost) for row in allocations), Decimal("0")
        ) == Decimal("50.000000")
        assert all(Decimal(row.applied_unit_cost) == Decimal("10.000000") for row in allocations)
        issue_count = int(
            await session.scalar(
                select(func.count(InventoryValuationEntryModel.id)).where(
                    InventoryValuationEntryModel.company_id == company_id,
                    InventoryValuationEntryModel.inventory_item_id == inventory_item_id,
                    InventoryValuationEntryModel.kind == "issue",
                )
            )
            or 0
        )
        assert issue_count == 2
        available_count = int(
            await session.scalar(
                select(func.count(InventoryHandlingUnitModel.id)).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.inventory_item_id == inventory_item_id,
                    InventoryHandlingUnitModel.stock_status == "available",
                    InventoryHandlingUnitModel.closed_at.is_(None),
                )
            )
            or 0
        )
        assert available_count == 1
        remaining_available = await session.scalar(
            select(InventoryHandlingUnitModel).where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.id == uuid.UUID(hu_branch_b),
            )
        )
        assert remaining_available is not None
        assert remaining_available.closed_at is None
        assert hu_quarantine != hu_branch_b

    deliveries_response = await e2e_client.get(
        f"/api/v1/sales/{sale_id}/deliveries", headers=headers
    )
    assert deliveries_response.status_code == 200, deliveries_response.text
    assert "applied_total_cost" not in deliveries_response.text

    async def create_confirmed_sale_on_branch_b(label: str) -> tuple[str, str]:
        quote_response = await e2e_client.post(
            "/api/v1/sales/quotations",
            headers={**headers, "Idempotency-Key": f"b07-{label}-quote-{uuid.uuid4()}"},
            json={
                "branch_id": str(branch_b.id),
                "customer_id": customer.json()["id"],
                "valid_until": valid_until,
                "currency": "USD",
                "lines": [
                    {
                        "product_id": product_id,
                        "variant_id": None,
                        "unit_id": base_unit_id,
                        "quantity": "7",
                        "unit_price": "20",
                    }
                ],
            },
        )
        assert quote_response.status_code == 201, quote_response.text
        quote_confirmation = await e2e_client.post(
            f"/api/v1/sales/quotations/{quote_response.json()['id']}/confirm",
            headers=headers,
            json={"expected_version": quote_response.json()["version"]},
        )
        assert quote_confirmation.status_code == 200, quote_confirmation.text
        converted = await e2e_client.post(
            f"/api/v1/sales/quotations/{quote_response.json()['id']}/convert",
            headers={**headers, "Idempotency-Key": f"b07-{label}-convert-{uuid.uuid4()}"},
            json={"expected_version": quote_confirmation.json()["version"]},
        )
        assert converted.status_code == 200, converted.text
        sale_confirmation = await e2e_client.post(
            f"/api/v1/sales/{converted.json()['id']}/confirm",
            headers=headers,
            json={"expected_version": converted.json()["version"]},
        )
        assert sale_confirmation.status_code == 200, sale_confirmation.text
        return converted.json()["id"], sale_confirmation.json()["lines"][0]["id"]

    competitor_sales = [
        await create_confirmed_sale_on_branch_b("branch-b-sale-a"),
        await create_confirmed_sale_on_branch_b("branch-b-sale-b"),
    ]
    competitor_deliveries: list[tuple[str, dict[str, object]]] = []
    for competitor_sale_id, competitor_line_id in competitor_sales:
        candidate_response = await e2e_client.get(
            f"/api/v1/sales/{competitor_sale_id}/delivery-stock", headers=headers
        )
        assert candidate_response.status_code == 200, candidate_response.text
        assert {
            unit["handling_unit_id"] for line in candidate_response.json() for unit in line["units"]
        } == {hu_branch_b}
        prepared = await e2e_client.post(
            f"/api/v1/sales/{competitor_sale_id}/deliveries",
            headers={**headers, "Idempotency-Key": f"b07-last-stock-{uuid.uuid4()}"},
            json={
                "notes": "Competencia entre ventas por el último stock de la sucursal",
                "assignments": [
                    {"sale_line_id": competitor_line_id, "handling_unit_id": hu_branch_b}
                ],
            },
        )
        assert prepared.status_code == 201, prepared.text
        competitor_deliveries.append((competitor_sale_id, prepared.json()))

    last_stock_confirms = await asyncio.gather(
        *(
            confirm(delivery["id"], delivery["version"], f"b07-last-stock-confirm-{uuid.uuid4()}")
            for _, delivery in competitor_deliveries
        )
    )
    assert sorted(response.status_code for response in last_stock_confirms) == [200, 409], [
        (response.status_code, response.text) for response in last_stock_confirms
    ]
    winner_index = next(
        index for index, response in enumerate(last_stock_confirms) if response.status_code == 200
    )
    loser_index = 1 - winner_index
    winning_sale_id, _ = competitor_sales[winner_index]
    losing_sale_id, _ = competitor_sales[loser_index]
    winning_delivery = last_stock_confirms[winner_index].json()
    losing_delivery = competitor_deliveries[loser_index][1]
    assert winning_delivery["status"] == "confirmed"
    assert (await _physical_value(company_id, inventory_item_id)) == (
        Decimal("1.000000"),
        Decimal("10.000000"),
    )
    winner_state = await e2e_client.get(f"/api/v1/sales/{winning_sale_id}", headers=headers)
    loser_state = await e2e_client.get(f"/api/v1/sales/{losing_sale_id}", headers=headers)
    assert winner_state.status_code == loser_state.status_code == 200
    assert winner_state.json()["delivery_progress"] == "complete"
    assert loser_state.json()["delivery_progress"] == "pending"
    cancelled_competitor = await e2e_client.post(
        f"/api/v1/sales/deliveries/{losing_delivery['id']}/cancel",
        headers=headers,
        json={
            "expected_version": losing_delivery["version"],
            "reason": "Otra venta consumió el último stock disponible",
        },
    )
    assert cancelled_competitor.status_code == 200, cancelled_competitor.text
    async with async_session_factory() as session:
        competitor_allocations = list(
            (
                await session.scalars(
                    select(SalesDeliveryAllocationModel)
                    .join(
                        SalesDeliveryLineModel,
                        (
                            SalesDeliveryLineModel.company_id
                            == SalesDeliveryAllocationModel.company_id
                        )
                        & (
                            SalesDeliveryLineModel.id
                            == SalesDeliveryAllocationModel.delivery_line_id
                        ),
                    )
                    .join(
                        SalesDeliveryModel,
                        (SalesDeliveryModel.company_id == SalesDeliveryLineModel.company_id)
                        & (SalesDeliveryModel.id == SalesDeliveryLineModel.delivery_id),
                    )
                    .where(
                        SalesDeliveryModel.sale_id == uuid.UUID(winning_sale_id),
                        SalesDeliveryModel.status == "confirmed",
                    )
                )
            ).all()
        )
        assert len(competitor_allocations) == 1
        assert competitor_allocations[0].movement_line_id is not None
        assert competitor_allocations[0].valuation_entry_id is not None
        assert competitor_allocations[0].applied_total_cost == Decimal("70.000000")
        assert competitor_allocations[0].applied_unit_cost == Decimal("10.000000")

    # B08: raise the current average after the original delivery. A customer
    # return must still use the exact cost of its delivery allocation.
    await _seed_receipt(
        company_id,
        actor_id,
        {
            "idempotency_key": f"b08-newer-average-{uuid.uuid4()}",
            "movement_type": "receipt",
            "source_reference": "B08 fictitious demonstration: later receipt at USD 25",
            "lines": [
                {
                    "inventory_item_id": str(inventory_item_id),
                    "to_location_id": str(location_b.id),
                    "to_stock_status": "available",
                    "quantity_base": "2",
                    "handling_unit_code": f"B08-HU-{uuid.uuid4().hex[:12].upper()}",
                    "actual_measures": {"gross_weight_kg": "1", "volume_m3": "0.1"},
                    "valuation_kind": "receipt",
                    "valuation_value": "50",
                    "valuation_currency": "USD",
                }
            ],
        },
    )
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("3.000000"),
        Decimal("60.000000"),
    )

    returnable = await e2e_client.get(
        f"/api/v1/sales/{sale_id}/returnable-allocations", headers=headers
    )
    assert returnable.status_code == 200, returnable.text
    assert len(returnable.json()) == 2
    first_source, second_source = returnable.json()
    assert all(Decimal(row["quantity_returnable_base"]) > 0 for row in returnable.json())

    from app.application.inventory.use_cases import InventoryApplicationError, InventoryUseCases
    from app.infrastructure.models.document import DocumentAssetModel
    from app.infrastructure.models.document_record import DocumentCategoryModel, DocumentRecordModel
    from app.infrastructure.models.inventory import InventoryMovementModel
    from app.infrastructure.models.sales_return import (
        SalesReturnEventModel,
        SalesReturnModel,
    )

    async with async_session_factory() as session:
        first_source_allocation = await session.get(
            SalesDeliveryAllocationModel,
            uuid.UUID(first_source["delivery_allocation_id"]),
        )
        assert first_source_allocation is not None
        first_source_valuation_entry_id = first_source_allocation.valuation_entry_id

    evidence_id = uuid.uuid4()
    evidence_category_id = uuid.uuid4()
    now = datetime.now(ZoneInfo("UTC"))
    async with async_session_factory() as session:
        session.add(
            DocumentCategoryModel(
                id=evidence_category_id,
                company_id=company_id,
                module="general",
                code=f"B08-EVIDENCE-{uuid.uuid4().hex[:8]}",
                name=f"Evidencia ficticia B08 {uuid.uuid4().hex[:6]}",
                group_name="General",
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        session.add(
            DocumentAssetModel(
                id=evidence_id,
                company_id=company_id,
                original_filename="evidencia-devolucion-b08.pdf",
                extension="pdf",
                declared_content_type="application/pdf",
                detected_content_type="application/pdf",
                size_bytes=32,
                checksum_sha256="a" * 64,
                bucket="test-evidence",
                object_key=f"b08/{evidence_id}.pdf",
                status="active",
                upload_expires_at=now,
                scanned_at=now,
                uploaded_by=actor_id,
            )
        )
        session.add(
            DocumentRecordModel(
                id=evidence_id,
                company_id=company_id,
                module="general",
                owner_type=None,
                owner_id=None,
                category_id=evidence_category_id,
                title="Evidencia ficticia de devolución B08",
                description="Documento sintético de aceptación automatizada.",
                confidentiality="internal",
                tags=["B08", "demostracion"],
                version_group_id=uuid.uuid4(),
                version_number=1,
                is_current=True,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        await session.commit()

    return_payload = {
        "notes": "Caso ficticio B08; no representa un reembolso fiscal.",
        "document_ids": [str(evidence_id)],
        "lines": [
            {
                "delivery_allocation_id": first_source["delivery_allocation_id"],
                "quantity_base": "0.5",
                "reason": "Devolución parcial de demostración",
                "declared_condition": "resalable",
            }
        ],
    }
    create_return_key = f"b08-create-return-{uuid.uuid4()}"
    created_return = await e2e_client.post(
        f"/api/v1/sales/{sale_id}/returns",
        headers={**headers, "Idempotency-Key": create_return_key},
        json=return_payload,
    )
    assert created_return.status_code == 201, created_return.text
    return_doc = created_return.json()
    assert return_doc["status"] == "draft"
    assert return_doc["evidence"] == [
        {
            "document_id": str(evidence_id),
            "title": "Evidencia ficticia de devolución B08",
            "file_name": "evidencia-devolucion-b08.pdf",
        }
    ]
    assert return_doc["lines"][0]["delivery_id"] == first_source["delivery_id"]
    assert return_doc["lines"][0]["source_handling_unit_id"]
    assert return_doc["lines"][0]["quantity_returnable_base"] == (
        f"{Decimal(first_source['quantity_returnable_base']) - Decimal('0.5'):.6f}"
    )
    assert "applied_total_cost" not in created_return.text
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("3.000000"),
        Decimal("60.000000"),
    )
    replay_create = await e2e_client.post(
        f"/api/v1/sales/{sale_id}/returns",
        headers={**headers, "Idempotency-Key": create_return_key},
        json=return_payload,
    )
    assert replay_create.status_code == 201, replay_create.text
    assert replay_create.json()["id"] == return_doc["id"]
    conflicting_create = await e2e_client.post(
        f"/api/v1/sales/{sale_id}/returns",
        headers={**headers, "Idempotency-Key": create_return_key},
        json={**return_payload, "lines": [{**return_payload["lines"][0], "quantity_base": "0.4"}]},
    )
    assert conflicting_create.status_code == 409, conflicting_create.text

    receive_key = f"b08-receive-return-{uuid.uuid4()}"
    received_return = await e2e_client.post(
        f"/api/v1/sales/returns/{return_doc['id']}/receive",
        headers={**headers, "Idempotency-Key": receive_key},
    )
    assert received_return.status_code == 200, received_return.text
    assert received_return.json()["status"] == "received"
    replay_receive = await e2e_client.post(
        f"/api/v1/sales/returns/{return_doc['id']}/receive",
        headers={**headers, "Idempotency-Key": receive_key},
    )
    assert replay_receive.status_code == 200, replay_receive.text
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("3.000000"),
        Decimal("60.000000"),
    )

    return_line_id = received_return.json()["lines"][0]["id"]
    reject_payload = {
        "lines": [
            {
                "return_line_id": return_line_id,
                "decision": "rejected",
                "quantity_base": "0.125",
                "condition": "damaged",
                "reason": "Empaque dañado en la prueba ficticia",
            }
        ]
    }
    reject_key = f"b08-reject-partial-{uuid.uuid4()}"
    rejected_partial = await e2e_client.post(
        f"/api/v1/sales/returns/{return_doc['id']}/resolve",
        headers={**headers, "Idempotency-Key": reject_key},
        json=reject_payload,
    )
    assert rejected_partial.status_code == 200, rejected_partial.text
    assert rejected_partial.json()["status"] == "under_review"
    rejected_line = rejected_partial.json()["lines"][0]
    assert rejected_line["quantity_rejected_base"] == "0.125000"
    assert rejected_line["quantity_pending_base"] == "0.375000"
    replay_reject = await e2e_client.post(
        f"/api/v1/sales/returns/{return_doc['id']}/resolve",
        headers={**headers, "Idempotency-Key": reject_key},
        json=reject_payload,
    )
    assert replay_reject.status_code == 200, replay_reject.text
    assert len(replay_reject.json()["lines"][0]["events"]) == 1
    conflicting_reject = await e2e_client.post(
        f"/api/v1/sales/returns/{return_doc['id']}/resolve",
        headers={**headers, "Idempotency-Key": reject_key},
        json={"lines": [{**reject_payload["lines"][0], "quantity_base": "0.1"}]},
    )
    assert conflicting_reject.status_code == 409, conflicting_reject.text
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("3.000000"),
        Decimal("60.000000"),
    )

    accept_payload = {
        "lines": [
            {
                "return_line_id": return_line_id,
                "decision": "accepted",
                "quantity_base": "0.25",
                "condition": "resalable",
                "reason": "Empaque apto para reventa en la prueba ficticia",
            }
        ]
    }
    accept_key = f"b08-accept-partial-{uuid.uuid4()}"
    accepted_partial = await e2e_client.post(
        f"/api/v1/sales/returns/{return_doc['id']}/resolve",
        headers={**headers, "Idempotency-Key": accept_key},
        json=accept_payload,
    )
    assert accepted_partial.status_code == 200, accepted_partial.text
    accepted_line = accepted_partial.json()["lines"][0]
    assert accepted_partial.json()["status"] == "under_review"
    assert accepted_line["quantity_accepted_base"] == "0.250000"
    assert accepted_line["quantity_rejected_base"] == "0.125000"
    assert accepted_line["quantity_pending_base"] == "0.125000"
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("3.250000"),
        Decimal("62.500000"),
    )
    accepted_event = next(
        event for event in accepted_line["events"] if event["decision"] == "accepted"
    )
    async with async_session_factory() as session:
        returned_entry = await session.get(
            InventoryValuationEntryModel, uuid.UUID(accepted_event["valuation_entry_id"])
        )
        assert returned_entry is not None
        assert returned_entry.kind == "customer_return"
        assert returned_entry.original_entry_id == first_source_valuation_entry_id
        assert returned_entry.inventory_delta == Decimal("2.500000")
        returned_hu = await session.scalar(
            select(InventoryHandlingUnitModel).where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.inventory_item_id == inventory_item_id,
                InventoryHandlingUnitModel.stock_status == "quarantine",
                InventoryHandlingUnitModel.closed_at.is_(None),
                InventoryHandlingUnitModel.code.like("HU-RET-%"),
            )
        )
        assert returned_hu is not None
        assert returned_hu.quantity_base == Decimal("0.250000")
        assert returned_hu.location_id == uuid.UUID(accepted_event["destination_location_id"])
    replay_accept = await e2e_client.post(
        f"/api/v1/sales/returns/{return_doc['id']}/resolve",
        headers={**headers, "Idempotency-Key": accept_key},
        json=accept_payload,
    )
    assert replay_accept.status_code == 200, replay_accept.text
    assert len(replay_accept.json()["lines"][0]["events"]) == 2

    # A failure while accepting a second line must roll back the first inbound
    # movement, event, valuation and success-audit record.
    multi_line_payload = {
        "notes": "Caso de rollback atómico B08 ficticio.",
        "document_ids": [],
        "lines": [
            {
                "delivery_allocation_id": row["delivery_allocation_id"],
                "quantity_base": "0.1",
                "reason": "Ensayo de rollback multi-línea",
                "declared_condition": "resalable",
            }
            for row in (first_source, second_source)
        ],
    }
    multi_line_return = await e2e_client.post(
        f"/api/v1/sales/{sale_id}/returns",
        headers={**headers, "Idempotency-Key": f"b08-create-multi-{uuid.uuid4()}"},
        json=multi_line_payload,
    )
    assert multi_line_return.status_code == 201, multi_line_return.text
    multi_return_id = multi_line_return.json()["id"]
    multi_received = await e2e_client.post(
        f"/api/v1/sales/returns/{multi_return_id}/receive",
        headers={**headers, "Idempotency-Key": f"b08-receive-multi-{uuid.uuid4()}"},
    )
    assert multi_received.status_code == 200, multi_received.text
    multi_resolve_payload = {
        "lines": [
            {
                "return_line_id": line["id"],
                "decision": "accepted",
                "quantity_base": "0.1",
                "condition": "resalable",
                "reason": "Revisada apta en rollback B08",
            }
            for line in multi_received.json()["lines"]
        ]
    }
    multi_resolve_key = f"b08-resolve-multi-{uuid.uuid4()}"
    before_failed_resolution = await _physical_value(company_id, inventory_item_id)
    original_post_movement = InventoryUseCases.post_movement
    post_movement_calls = 0

    async def fail_second_return_movement(self, **kwargs):
        nonlocal post_movement_calls
        post_movement_calls += 1
        if post_movement_calls == 2:
            raise InventoryApplicationError(
                "Fallo inyectado en la segunda línea de devolución B08.",
                code="b08_second_return_line_failure",
                status_code=409,
            )
        return await original_post_movement(self, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(InventoryUseCases, "post_movement", fail_second_return_movement)
        failed_multi_resolve = await e2e_client.post(
            f"/api/v1/sales/returns/{multi_return_id}/resolve",
            headers={**headers, "Idempotency-Key": multi_resolve_key},
            json=multi_resolve_payload,
        )
    assert failed_multi_resolve.status_code == 409, failed_multi_resolve.text
    assert await _physical_value(company_id, inventory_item_id) == before_failed_resolution
    async with async_session_factory() as session:
        persisted_failed_return = await session.get(SalesReturnModel, uuid.UUID(multi_return_id))
        assert persisted_failed_return is not None
        assert persisted_failed_return.status == "received"
        assert (
            await session.scalar(
                select(func.count(SalesReturnEventModel.id)).where(
                    SalesReturnEventModel.company_id == company_id,
                    SalesReturnEventModel.return_id == uuid.UUID(multi_return_id),
                )
            )
            == 0
        )
        assert (
            await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == company_id,
                    InventoryMovementModel.idempotency_key.like("return:%"),
                    InventoryMovementModel.source_reference
                    == f"customer-return:{multi_received.json()['code']}",
                )
            )
            == 0
        )

    successful_multi_resolve = await e2e_client.post(
        f"/api/v1/sales/returns/{multi_return_id}/resolve",
        headers={**headers, "Idempotency-Key": multi_resolve_key},
        json=multi_resolve_payload,
    )
    assert successful_multi_resolve.status_code == 200, successful_multi_resolve.text
    assert successful_multi_resolve.json()["status"] == "accepted"
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("3.450000"),
        Decimal("64.500000"),
    )
    replay_multi_resolve = await e2e_client.post(
        f"/api/v1/sales/returns/{multi_return_id}/resolve",
        headers={**headers, "Idempotency-Key": multi_resolve_key},
        json=multi_resolve_payload,
    )
    assert replay_multi_resolve.status_code == 200, replay_multi_resolve.text
    assert replay_multi_resolve.json()["id"] == multi_return_id

    blocked_generic_return = await e2e_client.post(
        "/api/v1/inventory/movements/confirm",
        headers=headers,
        json={
            "idempotency_key": f"b08-generic-return-block-{uuid.uuid4()}",
            "movement_type": "receipt",
            "source_reference": "B08 direct customer-return bypass attempt",
            "lines": [
                {
                    "inventory_item_id": str(inventory_item_id),
                    "to_location_id": str(location_b.id),
                    "to_stock_status": "quarantine",
                    "quantity_base": "0.1",
                    "handling_unit_code": f"B08-BYPASS-{uuid.uuid4().hex[:10].upper()}",
                    "actual_measures": {"gross_weight_kg": "1", "volume_m3": "0.1"},
                    "valuation_kind": "customer_return",
                    "valuation_original_entry_id": str(first_source_valuation_entry_id),
                }
            ],
        },
    )
    assert blocked_generic_return.status_code == 409, blocked_generic_return.text
    assert blocked_generic_return.json()["detail"]["code"] == "sales_return_document_required"
    assert await _physical_value(company_id, inventory_item_id) == (
        Decimal("3.450000"),
        Decimal("64.500000"),
    )

    no_permission_username = f"b08-no-permission-{uuid.uuid4().hex[:8]}"
    await seed_user(
        username=no_permission_username,
        email=f"{no_permission_username}@example.test",
        is_superuser=False,
    )
    no_permission_headers = await _login(e2e_client, no_permission_username, company_id)
    denied_returns = await e2e_client.get(
        f"/api/v1/sales/returns/{return_doc['id']}", headers=no_permission_headers
    )
    assert denied_returns.status_code == 403, denied_returns.text

    # Two distinct acceptance commands for the same pending quantity must
    # serialize and recognize only one inbound movement.
    race_created = await e2e_client.post(
        f"/api/v1/sales/{sale_id}/returns",
        headers={**headers, "Idempotency-Key": f"b08-race-create-{uuid.uuid4()}"},
        json={
            "lines": [
                {
                    "delivery_allocation_id": first_source["delivery_allocation_id"],
                    "quantity_base": "0.1",
                    "reason": "Aceptación concurrente B08",
                    "declared_condition": "resalable",
                }
            ]
        },
    )
    assert race_created.status_code == 201, race_created.text
    race_id = race_created.json()["id"]
    race_received = await e2e_client.post(
        f"/api/v1/sales/returns/{race_id}/receive",
        headers={**headers, "Idempotency-Key": f"b08-race-receive-{uuid.uuid4()}"},
    )
    assert race_received.status_code == 200, race_received.text
    race_payload = {
        "lines": [
            {
                "return_line_id": race_received.json()["lines"][0]["id"],
                "decision": "accepted",
                "quantity_base": "0.1",
                "condition": "resalable",
                "reason": "Revisión concurrente B08",
            }
        ]
    }
    before_race = await _physical_value(company_id, inventory_item_id)
    race_results = await asyncio.gather(
        *[
            e2e_client.post(
                f"/api/v1/sales/returns/{race_id}/resolve",
                headers={**headers, "Idempotency-Key": f"b08-race-resolve-{uuid.uuid4()}"},
                json=race_payload,
            )
            for _ in range(2)
        ]
    )
    assert sorted(result.status_code for result in race_results) == [200, 422]
    after_race = await _physical_value(company_id, inventory_item_id)
    assert after_race == (before_race[0] + Decimal("0.1"), before_race[1] + Decimal("1"))
    race_read = await e2e_client.get(f"/api/v1/sales/returns/{race_id}", headers=headers)
    assert len(race_read.json()["lines"][0]["events"]) == 1

    from tests.e2e.test_inventory_block4_closure import _branch_profile_headers

    branch_permissions = (
        "sales:read",
        "sales_returns:read",
        "sales_returns:manage",
        "sales_returns:receive",
        "sales_returns:resolve",
    )
    branch_reader = await _branch_profile_headers(
        e2e_client,
        company_id=company_id,
        branch_id=branch_a.id,
        username=f"b08-own-branch-{uuid.uuid4().hex[:8]}",
        permissions=branch_permissions,
    )
    other_branch_reader = await _branch_profile_headers(
        e2e_client,
        company_id=company_id,
        branch_id=branch_b.id,
        username=f"b08-other-branch-{uuid.uuid4().hex[:8]}",
        permissions=branch_permissions,
    )
    own_read = await e2e_client.get(f"/api/v1/sales/returns/{race_id}", headers=branch_reader)
    assert own_read.status_code == 200, own_read.text
    for private_field in (
        "inventory_value",
        "average_unit_cost",
        "applied_total_cost",
        "applied_unit_cost",
    ):
        assert private_field not in own_read.text
    foreign_read = await e2e_client.get(
        f"/api/v1/sales/returns/{race_id}", headers=other_branch_reader
    )
    assert foreign_read.status_code == 403, foreign_read.text
    foreign_replay = await e2e_client.post(
        f"/api/v1/sales/returns/{race_id}/resolve",
        headers={**other_branch_reader, "Idempotency-Key": "b08-forbidden-branch-replay"},
        json=race_payload,
    )
    assert foreign_replay.status_code == 403, foreign_replay.text
    foreign_list = await e2e_client.get("/api/v1/sales/returns", headers=other_branch_reader)
    assert foreign_list.status_code == 200, foreign_list.text
    assert all(row["id"] != race_id for row in foreign_list.json())

    from app.infrastructure.models.organization import Company

    async with async_session_factory() as session:
        original_company = await session.get(Company, company_id)
        other_company = Company(
            name=f"B08 otra empresa {uuid.uuid4().hex[:8]}",
            commercial_name="Otra empresa B08",
            nit=uuid.uuid4().hex,
            nrc=uuid.uuid4().hex,
            address="Demostración aislada B08",
            department_id=original_company.department_id,
            municipality_id=original_company.municipality_id,
            district_id=original_company.district_id,
        )
        session.add(other_company)
        await session.commit()
        other_company_id = other_company.id
    foreign_company = await e2e_client.get(
        f"/api/v1/sales/returns/{race_id}",
        headers={**headers, "X-Company-ID": str(other_company_id)},
    )
    assert foreign_company.status_code == 404, foreign_company.text
    assert await _physical_value(company_id, inventory_item_id) == after_race
