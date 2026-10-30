"""Regression coverage for the final integrated inventory acceptance findings."""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from app.application.inventory import InventoryUseCases
from app.domain.entities.inventory import InventoryOperationError
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryMovementLineModel,
    InventoryMovementModel,
)
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.models.organization import Location, UserBranch, UserCompany
from app.infrastructure.models.purchase_order import PurchaseOrderDetailModel
from app.infrastructure.models.rbac import Permission, Role, RolePermission, UserRole
from app.infrastructure.models.user import User
from sqlalchemy import func, or_, select

from tests.e2e.test_purchase_orders import (
    _headers,
    _legacy_receipt,
    _receiving_location_id,
    _reference_ids,
    _sent_order,
)

pytestmark = pytest.mark.e2e

_VALUATION_PRIVATE_FIELDS = {
    "average_unit_cost",
    "closing_value",
    "cost_breakdown",
    "cost_delta",
    "cost_difference",
    "credit_net",
    "inventory_cost",
    "inventory_value",
    "opening_value",
    "source_value",
    "valued_quantity",
}


def _assert_no_valuation_fields(payload) -> None:
    if isinstance(payload, dict):
        assert not (_VALUATION_PRIVATE_FIELDS & payload.keys())
        for value in payload.values():
            _assert_no_valuation_fields(value)
    elif isinstance(payload, list):
        for value in payload:
            _assert_no_valuation_fields(value)


async def _measured_receipt(
    client,
    *,
    create_draft_retaceo: bool = False,
    quantity: str = "4.000000",
    username: str = "block4-closure",
):
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(client, company_id=company_id, username=username, is_superuser=True)
    order = await _sent_order(
        client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        supplier_id=supplier_id,
        currency=currency,
        quantity=quantity,
    )
    created = await client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "purchase_order_id": order["id"],
            "lines": [
                {
                    "purchase_order_detail_id": order["details"][0]["id"],
                    "quantity_received": quantity,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    purchase = created.json()
    await _legacy_receipt(purchase["id"])
    received = await client.post(f"/api/v1/purchases/{purchase['id']}/receive", headers=headers)
    assert received.status_code == 200, received.text
    verified = await client.post(
        f"/api/v1/purchases/{purchase['id']}/verify",
        headers=headers,
        json={
            "lines": [
                {
                    "purchase_detail_id": purchase["details"][0]["id"],
                    "quantity_accepted": quantity,
                    "inventory_location_id": str(await _receiving_location_id(warehouse_id)),
                }
            ]
        },
    )
    assert verified.status_code == 200, verified.text
    if create_draft_retaceo:
        retaceo = await client.post(
            "/api/v1/retaceos",
            headers=headers,
            json={
                "purchase_id": purchase["id"],
                "total_freight": "5.000000",
                "total_expenses": "2.000000",
                "total_dai": "3.000000",
                "import_vat": "13.000000",
                "notes": "Retaceo pendiente para regresión B4-02",
            },
        )
        assert retaceo.status_code == 201, retaceo.text
        assert retaceo.json()["status"] == "draft"

    async with async_session_factory() as session:
        lot = await session.scalar(
            select(InventoryLotModel).where(
                InventoryLotModel.company_id == company_id,
                InventoryLotModel.purchase_id == uuid.UUID(purchase["id"]),
            )
        )
        assert lot is not None
        unit = await session.scalar(
            select(InventoryHandlingUnitModel).where(
                InventoryHandlingUnitModel.inventory_lot_id == lot.id,
            )
        )
        assert unit is not None
        unit_id, item_id, lot_id = unit.id, unit.inventory_item_id, lot.id
    measured = await client.patch(
        f"/api/v1/inventory/handling-units/{unit_id}/measurements",
        headers=headers,
        json={
            "source": "manual",
            "measures": {
                "gross_weight_kg": "1",
                "length_m": "0.1",
                "width_m": "0.1",
                "height_m": "0.1",
            },
        },
    )
    assert measured.status_code == 200, measured.text
    return headers, warehouse_id, unit_id, item_id, lot_id, measured.json()


async def _receipt_lot_detail_id(lot_id: uuid.UUID) -> uuid.UUID:
    async with async_session_factory() as session:
        detail_id = await session.scalar(
            select(InventoryLotDetailModel.id)
            .where(InventoryLotDetailModel.inventory_lot_id == lot_id)
            .order_by(InventoryLotDetailModel.id)
            .limit(1)
        )
    assert detail_id is not None
    return detail_id


async def _branch_profile_headers(
    client,
    *,
    company_id: uuid.UUID,
    branch_id: uuid.UUID,
    username: str,
    permissions: tuple[str, ...],
) -> dict[str, str]:
    headers = await _headers(client, company_id=company_id, username=username, is_superuser=False)
    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.username == username))
        assert user is not None
        membership = await session.get(UserCompany, (user.id, company_id))
        assert membership is not None
        membership.access_all_branches = False
        membership.last_branch_id = branch_id
        permission_rows = list(
            await session.scalars(
                select(Permission).where(
                    Permission.code.in_(permissions), Permission.deleted_at.is_(None)
                )
            )
        )
        assert {row.code for row in permission_rows} == set(permissions)
        role = Role(
            company_id=company_id,
            name=f"B4 branch {uuid.uuid4().hex[:10]}",
            description="Perfil de aceptación aislado y limitado a una sucursal.",
        )
        session.add(role)
        await session.flush()
        session.add_all(
            [
                *[
                    RolePermission(role_id=role.id, permission_id=permission.id)
                    for permission in permission_rows
                ],
                UserRole(
                    user_id=user.id,
                    company_id=company_id,
                    role_id=role.id,
                    assigned_by=user.id,
                ),
                UserBranch(
                    user_id=user.id,
                    company_id=company_id,
                    branch_id=branch_id,
                    is_active=True,
                    is_default=True,
                ),
            ]
        )
        await session.commit()
    return headers


async def test_measurement_response_matches_list_with_label_and_retaceo_blockers(e2e_client):
    headers, warehouse_id, unit_id, _, _, measured = await _measured_receipt(
        e2e_client, create_draft_retaceo=True
    )
    listed = await e2e_client.get(
        f"/api/v1/inventory/warehouses/{warehouse_id}/handling-units", headers=headers
    )
    assert listed.status_code == 200, listed.text
    current = next(row for row in listed.json() if row["id"] == str(unit_id))
    requirements = set(current["release_requirements"])
    assert "label_confirmation_required" in requirements
    assert requirements & {"retaceo_not_final", "retaceo_cost_unapplied"}
    assert measured["release_requirements"] == current["release_requirements"]
    assert measured["purchase_code"] == current["purchase_code"]
    assert measured["receipt_lot_code"] == current["receipt_lot_code"]


async def test_pending_label_and_retaceo_can_only_be_put_away_in_quarantine(e2e_client):
    headers, warehouse_id, unit_id, item_id, lot_id, _ = await _measured_receipt(
        e2e_client, create_draft_retaceo=True
    )
    async with async_session_factory() as session:
        unit = await session.get(InventoryHandlingUnitModel, unit_id)
        assert unit is not None
        destinations = [
            Location(
                warehouse_id=warehouse_id,
                code=f"B4-RELEASE-BLOCK-{number}",
                aisle="B4",
                rack="03",
                level="01",
                position=str(number),
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            for number in (1, 2)
        ]
        session.add_all(destinations)
        await session.flush()
        quarantine_location_id, available_location_id = (row.id for row in destinations)
        await session.commit()

    putaway = await e2e_client.post(
        "/api/v1/inventory/putaway-groups/confirm",
        headers=headers,
        json={
            "idempotency_key": "block4-release-pending-requirements-putaway",
            "receipt_lot_id": str(lot_id),
            "inventory_lot_detail_id": str(await _receipt_lot_detail_id(lot_id)),
            "inventory_item_id": str(item_id),
            "allocations": [
                {
                    "handling_unit_id": str(unit_id),
                    "quantity_base": "4",
                    "destination_location_id": str(quarantine_location_id),
                }
            ],
        },
    )
    assert putaway.status_code == 201, putaway.text
    assert putaway.json()["allocations"][0]["stock_status"] == "quarantine"

    listed = await e2e_client.get(
        f"/api/v1/inventory/warehouses/{warehouse_id}/handling-units", headers=headers
    )
    assert listed.status_code == 200, listed.text
    current = next(row for row in listed.json() if row["id"] == str(unit_id))
    assert {
        "label_confirmation_required",
        "retaceo_not_final",
    }.issubset(set(current["release_requirements"]))

    release = await e2e_client.post(
        "/api/v1/inventory/movements/confirm",
        headers=headers,
        json={
            "idempotency_key": "block4-release-pending-requirements-attempt",
            "movement_type": "putaway",
            "source_reference": "block4-release-pending-requirements",
            "lines": [
                {
                    "inventory_item_id": str(item_id),
                    "handling_unit_id": str(unit_id),
                    "from_location_id": str(quarantine_location_id),
                    "to_location_id": str(available_location_id),
                    "from_stock_status": "quarantine",
                    "to_stock_status": "available",
                    "quantity_base": "4",
                }
            ],
        },
    )
    assert release.status_code == 409, release.text

    async with async_session_factory() as session:
        balances = list(
            await session.scalars(
                select(InventoryBalanceModel).where(
                    InventoryBalanceModel.company_id == uuid.UUID(headers["X-Company-ID"]),
                    InventoryBalanceModel.inventory_item_id == item_id,
                    InventoryBalanceModel.location_id == quarantine_location_id,
                )
            )
        )
        active_unit = await session.get(InventoryHandlingUnitModel, unit_id)
    assert sum(
        (row.quantity_base for row in balances if row.stock_status == "quarantine"),
        Decimal("0"),
    ) == Decimal("4")
    assert active_unit is not None
    assert active_unit.stock_status == "quarantine"
    assert active_unit.location_id == quarantine_location_id


async def test_branch_kardex_profile_cannot_fetch_company_valuation_json(e2e_client):
    headers, warehouse_id, unit_id, item_id, _, _ = await _measured_receipt(e2e_client)
    company_id, branch_id, _, _, _, _ = await _reference_ids()
    branch_headers = await _branch_profile_headers(
        e2e_client,
        company_id=company_id,
        branch_id=branch_id,
        username="block4-branch-kardex-read-only",
        permissions=("inventory:read",),
    )

    today = datetime.now(ZoneInfo("America/El_Salvador")).date().isoformat()
    physical = await e2e_client.get(
        "/api/v1/inventory/kardex/physical",
        headers=branch_headers,
        params={
            "warehouse_id": str(warehouse_id),
            "inventory_item_id": str(item_id),
            "period_from": today,
            "period_to": today,
        },
    )
    assert physical.status_code == 200, physical.text
    _assert_no_valuation_fields(physical.json())

    handling_units = await e2e_client.get(
        f"/api/v1/inventory/warehouses/{warehouse_id}/handling-units", headers=branch_headers
    )
    assert handling_units.status_code == 200, handling_units.text
    _assert_no_valuation_fields(handling_units.json())
    assert any(row["id"] == str(unit_id) for row in handling_units.json())

    for path, params in (
        ("/api/v1/inventory/kardex/reconciliation", {}),
        (
            "/api/v1/inventory/kardex/valuation",
            {
                "inventory_item_id": str(item_id),
                "period_from": today,
                "period_to": today,
            },
        ),
    ):
        denied = await e2e_client.get(path, headers=branch_headers, params=params)
        assert denied.status_code == 403, denied.text
        body = denied.text
        assert "inventory_value" not in body
        assert "average_unit_cost" not in body
        assert "opening_value" not in body
        assert "closing_value" not in body

    other_company = {**branch_headers, "X-Company-ID": str(uuid.uuid4())}
    wrong_scope = await e2e_client.get(
        "/api/v1/inventory/kardex/physical",
        headers=other_company,
        params={
            "warehouse_id": str(warehouse_id),
            "inventory_item_id": str(item_id),
            "period_from": today,
            "period_to": today,
        },
    )
    assert wrong_scope.status_code in {403, 404}, wrong_scope.text
    assert "inventory_value" not in wrong_scope.text
    assert "average_unit_cost" not in wrong_scope.text


async def test_group_putaway_uses_split_requirements_for_each_result(e2e_client):
    headers, warehouse_id, unit_id, item_id, lot_id, measured = await _measured_receipt(
        e2e_client, quantity="50.000000"
    )
    async with async_session_factory() as session:
        lot = await session.get(InventoryLotModel, lot_id)
        assert lot is not None
        # Exercise the documented historical label exception with no other blocker.
        lot.label_confirmation_required = False
        destinations = [
            Location(
                warehouse_id=warehouse_id,
                code=f"B4-CLOSURE-{number}",
                aisle="B4",
                rack="01",
                level="01",
                position=str(number),
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            for number in (1, 2)
        ]
        session.add_all(destinations)
        await session.flush()
        destination_ids = [destination.id for destination in destinations]
        original_quantity = (await session.get(InventoryHandlingUnitModel, unit_id)).quantity_base
        await session.commit()
    assert original_quantity == Decimal("50")

    current = await e2e_client.get(
        f"/api/v1/inventory/warehouses/{warehouse_id}/handling-units", headers=headers
    )
    assert current.status_code == 200, current.text
    source = next(row for row in current.json() if row["id"] == str(unit_id))
    assert source["release_requirements"] == []
    oversized = await e2e_client.post(
        "/api/v1/inventory/putaway-groups/confirm",
        headers=headers,
        json={
            "idempotency_key": "block4-closure-over-allocation",
            "receipt_lot_id": str(lot_id),
            "inventory_lot_detail_id": str(await _receipt_lot_detail_id(lot_id)),
            "inventory_item_id": str(item_id),
            "allocations": [
                {
                    "handling_unit_id": str(unit_id),
                    "quantity_base": "51",
                    "destination_location_id": str(destination_ids[0]),
                }
            ],
        },
    )
    assert oversized.status_code == 409, oversized.text

    response = await e2e_client.post(
        "/api/v1/inventory/putaway-groups/confirm",
        headers=headers,
        json={
            "idempotency_key": "block4-closure-two-destinations",
            "receipt_lot_id": str(lot_id),
            "inventory_lot_detail_id": str(await _receipt_lot_detail_id(lot_id)),
            "inventory_item_id": str(item_id),
            "allocations": [
                {
                    "handling_unit_id": str(unit_id),
                    "quantity_base": quantity,
                    "destination_location_id": str(destination_id),
                }
                for quantity, destination_id in zip(("20", "30"), destination_ids, strict=True)
            ],
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert [row["stock_status"] for row in payload["allocations"]] == [
        "quarantine",
        "quarantine",
    ]
    assert sum(
        (Decimal(row["quantity_base"]) for row in payload["allocations"]), Decimal(0)
    ) == Decimal("50")
    assert [Decimal(row["quantity_base"]) for row in payload["allocations"]] == [
        Decimal("20"),
        Decimal("30"),
    ]
    assert len({row["destination_location_id"] for row in payload["allocations"]}) == 2

    async with async_session_factory() as session:
        units = list(
            await session.scalars(
                select(InventoryHandlingUnitModel)
                .where(
                    InventoryHandlingUnitModel.inventory_lot_id == lot_id,
                    InventoryHandlingUnitModel.closed_at.is_(None),
                )
                .order_by(InventoryHandlingUnitModel.quantity_base)
            )
        )
    assert len(units) == 2
    assert sum((unit.quantity_base for unit in units), Decimal(0)) == original_quantity
    assert {unit.stock_status for unit in units} == {"quarantine"}
    assert {unit.measurement_source for unit in units} == {"split_estimate"}
    assert {unit.location_id for unit in units} == set(destination_ids)
    children = [unit for unit in units if unit.origin_handling_unit_id is not None]
    assert len(children) == 1
    assert children[0].origin_handling_unit_id == unit_id

    replay = await e2e_client.post(
        "/api/v1/inventory/putaway-groups/confirm",
        headers=headers,
        json={
            "idempotency_key": "block4-closure-two-destinations",
            "receipt_lot_id": str(lot_id),
            "inventory_lot_detail_id": str(await _receipt_lot_detail_id(lot_id)),
            "inventory_item_id": str(item_id),
            "allocations": [
                {
                    "handling_unit_id": str(unit_id),
                    "quantity_base": quantity,
                    "destination_location_id": str(destination_id),
                }
                for quantity, destination_id in zip(("20", "30"), destination_ids, strict=True)
            ],
        },
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["replayed"] is True
    async with async_session_factory() as session:
        after_replay = list(
            await session.scalars(
                select(InventoryHandlingUnitModel).where(
                    InventoryHandlingUnitModel.inventory_lot_id == lot_id,
                    InventoryHandlingUnitModel.closed_at.is_(None),
                )
            )
        )
    assert len(after_replay) == 2


async def test_group_putaway_preserves_two_purchase_detail_origins(e2e_client):
    """A grouped receipt must keep each same-product purchase line traceable."""
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        e2e_client,
        company_id=company_id,
        username="block4-two-purchase-details",
        is_superuser=True,
    )
    order = await _sent_order(
        e2e_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        supplier_id=supplier_id,
        currency=currency,
        quantity="50.000000",
    )
    first_order_detail_id = uuid.UUID(order["details"][0]["id"])
    async with async_session_factory() as session:
        first_detail = await session.get(PurchaseOrderDetailModel, first_order_detail_id)
        assert first_detail is not None
        assert first_detail.quantity == Decimal("50")
        # Split the awarded 50-unit line into two real order lines for the same SKU.
        # They retain the same quotation origin but receive distinct purchase/lot details.
        original = {
            "company_id": first_detail.company_id,
            "purchase_order_id": first_detail.purchase_order_id,
            "purchase_quotation_detail_id": first_detail.purchase_quotation_detail_id,
            "purchase_consolidation_award_id": first_detail.purchase_consolidation_award_id,
            "product_id": first_detail.product_id,
            "unit_id": first_detail.unit_id,
            "unit_price": first_detail.unit_price,
            "tax_rate": first_detail.tax_rate,
            "notes": first_detail.notes,
        }
        price = Decimal(first_detail.unit_price)
        tax_rate = Decimal(first_detail.tax_rate)
        full_discount = Decimal(first_detail.discount)
        full_subtotal = Decimal(first_detail.subtotal)

        def set_line_amounts(row, quantity: Decimal, discount: Decimal) -> None:
            subtotal = (price * quantity).quantize(Decimal("0.000001"))
            tax = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.000001"))
            row.quantity = quantity
            row.discount = discount
            row.subtotal = subtotal
            row.tax_amount = tax
            row.total = subtotal - discount + tax

        first_discount = (full_discount * Decimal("0.4")).quantize(Decimal("0.000001"))
        second_discount = full_discount - first_discount
        # Preserve the original subtotal if the order used a negotiated unit price.
        first_unit_price = (full_subtotal * Decimal("0.4") / Decimal("20")).quantize(
            Decimal("0.000001")
        )
        second_unit_price = (full_subtotal * Decimal("0.6") / Decimal("30")).quantize(
            Decimal("0.000001")
        )
        first_detail.unit_price = first_unit_price
        original["unit_price"] = second_unit_price
        set_line_amounts(first_detail, Decimal("20"), first_discount)
        second_detail = PurchaseOrderDetailModel(**original)
        set_line_amounts(second_detail, Decimal("30"), second_discount)
        session.add(second_detail)
        await session.flush()
        second_order_detail_id = second_detail.id
        await session.commit()

    created = await e2e_client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "purchase_order_id": order["id"],
            "lines": [
                {
                    "purchase_order_detail_id": str(first_order_detail_id),
                    "quantity_received": "20.000000",
                },
                {
                    "purchase_order_detail_id": str(second_order_detail_id),
                    "quantity_received": "30.000000",
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    purchase = created.json()
    assert len(purchase["details"]) == 2
    assert {row["product_id"] for row in purchase["details"]} == {product_id}

    received = await e2e_client.post(f"/api/v1/purchases/{purchase['id']}/receive", headers=headers)
    assert received.status_code == 200, received.text
    receiving_location_id = str(await _receiving_location_id(warehouse_id))
    verification_lines = [
        {
            "purchase_detail_id": row["id"],
            "quantity_accepted": row["quantity_received"],
            "inventory_location_id": receiving_location_id,
        }
        for row in purchase["details"]
    ]
    verified = await e2e_client.post(
        f"/api/v1/purchases/{purchase['id']}/verify",
        headers=headers,
        json={"lines": verification_lines},
    )
    assert verified.status_code == 200, verified.text

    async with async_session_factory() as session:
        lot = await session.scalar(
            select(InventoryLotModel).where(
                InventoryLotModel.company_id == company_id,
                InventoryLotModel.purchase_id == uuid.UUID(purchase["id"]),
            )
        )
        assert lot is not None
        lot.label_confirmation_required = False
        lot_details = list(
            await session.scalars(
                select(InventoryLotDetailModel).where(
                    InventoryLotDetailModel.inventory_lot_id == lot.id
                )
            )
        )
        assert len(lot_details) == 2
        assert len({detail.purchase_detail_id for detail in lot_details}) == 2
        assert len({detail.code for detail in lot_details}) == 2
        assert all(detail.code == f"{lot.code}-D{detail.id.hex.upper()}" for detail in lot_details)
        detail_codes = {detail.id: detail.code for detail in lot_details}
        receipt_header_code = lot.code
        units = list(
            await session.scalars(
                select(InventoryHandlingUnitModel).where(
                    InventoryHandlingUnitModel.inventory_lot_id == lot.id,
                    InventoryHandlingUnitModel.closed_at.is_(None),
                )
            )
        )
        assert len(units) == 2
        assert {unit.inventory_lot_detail_id for unit in units} == {
            detail.id for detail in lot_details
        }
        receipt_lines = list(
            await session.scalars(
                select(InventoryMovementLineModel).where(
                    InventoryMovementLineModel.company_id == company_id,
                    InventoryMovementLineModel.inventory_lot_detail_id.in_(detail_codes),
                )
            )
        )
        assert len(receipt_lines) == 2
        assert {line.inventory_lot_detail_id for line in receipt_lines} == set(detail_codes)
        unit_by_detail = {unit.inventory_lot_detail_id: unit for unit in units}
        destinations = [
            Location(
                warehouse_id=warehouse_id,
                code=f"B4-TWO-DETAIL-{number}",
                aisle="B4",
                rack="02",
                level="01",
                position=str(number),
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            for number in (1, 2)
        ]
        session.add_all(destinations)
        await session.flush()
        destination_ids = [destination.id for destination in destinations]
        lot_id = lot.id
        item_id = units[0].inventory_item_id
        unit_detail_pairs = [
            (unit_by_detail[detail.id].id, detail.id, Decimal(detail.accepted_quantity_base))
            for detail in sorted(lot_details, key=lambda row: row.quantity_accepted)
        ]
        await session.commit()

    assert [quantity for _, _, quantity in unit_detail_pairs] == [Decimal("20"), Decimal("30")]

    today = datetime.now(ZoneInfo("America/El_Salvador")).date().isoformat()
    for handling_unit_id, detail_id, _quantity in unit_detail_pairs:
        label = await e2e_client.get(
            f"/api/v1/inventory/labels/preview?handling_unit_id={handling_unit_id}",
            headers=headers,
        )
        assert label.status_code == 200, label.text
        assert label.json()["product_name"]
        assert label.json()["receipt_lot_code"] == detail_codes[detail_id]
        assert label.json()["receipt_lot_header_code"] == receipt_header_code

        detail_kardex = await e2e_client.get(
            "/api/v1/inventory/kardex/physical",
            headers=headers,
            params={
                "warehouse_id": str(warehouse_id),
                "inventory_item_id": str(item_id),
                "period_from": today,
                "period_to": today,
                "lot_code": detail_codes[detail_id],
            },
        )
        assert detail_kardex.status_code == 200, detail_kardex.text
        assert detail_kardex.json()["total"] == 1
        assert detail_kardex.json()["items"][0]["receipt_lot_code"] == detail_codes[detail_id]

    header_kardex = await e2e_client.get(
        "/api/v1/inventory/kardex/physical",
        headers=headers,
        params={
            "warehouse_id": str(warehouse_id),
            "inventory_item_id": str(item_id),
            "period_from": today,
            "period_to": today,
            "lot_code": receipt_header_code,
        },
    )
    assert header_kardex.status_code == 200, header_kardex.text
    assert header_kardex.json()["total"] == 2
    assert {row["receipt_lot_code"] for row in header_kardex.json()["items"]} == set(
        detail_codes.values()
    )

    for handling_unit_id, _, _ in unit_detail_pairs:
        measured = await e2e_client.patch(
            f"/api/v1/inventory/handling-units/{handling_unit_id}/measurements",
            headers=headers,
            json={
                "source": "manual",
                "measures": {
                    "gross_weight_kg": "1",
                    "length_m": "0.1",
                    "width_m": "0.1",
                    "height_m": "0.1",
                },
            },
        )
        assert measured.status_code == 200, measured.text

    invalid = await e2e_client.post(
        "/api/v1/inventory/putaway-groups/confirm",
        headers=headers,
        json={
            "idempotency_key": "block4-two-details-over-allocation",
            "receipt_lot_id": str(lot_id),
            "inventory_lot_detail_id": str(unit_detail_pairs[0][1]),
            "inventory_item_id": str(item_id),
            "allocations": [
                {
                    "handling_unit_id": str(unit_detail_pairs[0][0]),
                    "quantity_base": "21",
                    "destination_location_id": str(destination_ids[0]),
                },
            ],
        },
    )
    assert invalid.status_code == 409, invalid.text

    group_bodies = []
    group_results = []
    for index, (handling_unit_id, detail_id, quantity) in enumerate(unit_detail_pairs):
        body = {
            "idempotency_key": f"block4-two-details-preserve-origins-{index}",
            "receipt_lot_id": str(lot_id),
            "inventory_lot_detail_id": str(detail_id),
            "inventory_item_id": str(item_id),
            "allocations": [
                {
                    "handling_unit_id": str(handling_unit_id),
                    "quantity_base": str(quantity),
                    "destination_location_id": str(destination_ids[index]),
                }
            ],
        }
        response = await e2e_client.post(
            "/api/v1/inventory/putaway-groups/confirm", headers=headers, json=body
        )
        assert response.status_code == 201, response.text
        group_bodies.append(body)
        group_results.append(response.json())
    flattened_allocations = [
        allocation for result in group_results for allocation in result["allocations"]
    ]
    assert [row["stock_status"] for row in flattened_allocations] == ["available", "available"]

    async with async_session_factory() as session:
        destination_units = list(
            await session.scalars(
                select(InventoryHandlingUnitModel).where(
                    InventoryHandlingUnitModel.inventory_lot_id == lot_id,
                    InventoryHandlingUnitModel.closed_at.is_(None),
                )
            )
        )
        by_location = {unit.location_id: unit for unit in destination_units}
        assert len(by_location) == 2
        for index, (source_unit_id, lot_detail_id, quantity) in enumerate(unit_detail_pairs):
            destination_unit = by_location[destination_ids[index]]
            assert destination_unit.id == source_unit_id
            assert destination_unit.inventory_lot_detail_id == lot_detail_id
            assert destination_unit.quantity_base == quantity
            source_unit = await session.get(InventoryHandlingUnitModel, source_unit_id)
            assert source_unit is not None
            assert source_unit.closed_at is None
            assert source_unit.location_id == destination_ids[index]
        movement_lines = list(
            await session.scalars(
                select(InventoryMovementLineModel).where(
                    InventoryMovementLineModel.movement_id.in_(
                        [uuid.UUID(row["movement_id"]) for row in flattened_allocations]
                    )
                )
            )
        )
        assert len(movement_lines) == 2
        assert {
            (row.handling_unit_id, row.to_location_id, row.quantity_base) for row in movement_lines
        } == {
            (unit_id, destination_ids[index], quantity)
            for index, (unit_id, _, quantity) in enumerate(unit_detail_pairs)
        }
        destination_balances = list(
            await session.scalars(
                select(InventoryBalanceModel).where(
                    InventoryBalanceModel.company_id == company_id,
                    InventoryBalanceModel.inventory_item_id == item_id,
                    InventoryBalanceModel.location_id.in_(destination_ids),
                    InventoryBalanceModel.stock_status == "available",
                )
            )
        )
        assert {row.location_id: row.quantity_base for row in destination_balances} == {
            destination_ids[index]: quantity
            for index, (_, _, quantity) in enumerate(unit_detail_pairs)
        }

    for body in group_bodies:
        replay = await e2e_client.post(
            "/api/v1/inventory/putaway-groups/confirm", headers=headers, json=body
        )
        assert replay.status_code == 201, replay.text
        assert replay.json()["replayed"] is True

    conflicting_body = {
        **group_bodies[0],
        "allocations": [{**group_bodies[0]["allocations"][0], "quantity_base": "19"}],
    }
    conflict = await e2e_client.post(
        "/api/v1/inventory/putaway-groups/confirm",
        headers=headers,
        json=conflicting_body,
    )
    assert conflict.status_code == 409, conflict.text

    unauthorized_headers = await _headers(
        e2e_client,
        company_id=company_id,
        username="block4-two-detail-no-move-permission",
        is_superuser=False,
    )
    denied_replay = await e2e_client.post(
        "/api/v1/inventory/putaway-groups/confirm",
        headers=unauthorized_headers,
        json=group_bodies[0],
    )
    assert denied_replay.status_code == 403, denied_replay.text

    scoped_headers = await _branch_profile_headers(
        e2e_client,
        company_id=company_id,
        branch_id=branch_id,
        username="block4-two-detail-scoped-replay",
        permissions=("inventory:read", "inventory:move"),
    )
    scoped_replay = await e2e_client.post(
        "/api/v1/inventory/putaway-groups/confirm",
        headers=scoped_headers,
        json=group_bodies[0],
    )
    assert scoped_replay.status_code == 201, scoped_replay.text
    assert scoped_replay.json()["replayed"] is True
    _assert_no_valuation_fields(scoped_replay.json())

    async with async_session_factory() as session:
        scoped_user = await session.scalar(
            select(User).where(User.username == "block4-two-detail-scoped-replay")
        )
        assert scoped_user is not None
        branch_access = await session.get(UserBranch, (scoped_user.id, branch_id))
        assert branch_access is not None
        branch_access.is_active = False
        branch_access.revoked_at = datetime.now(UTC)
        await session.commit()

    revoked_replay = await e2e_client.post(
        "/api/v1/inventory/putaway-groups/confirm",
        headers=scoped_headers,
        json=group_bodies[0],
    )
    assert revoked_replay.status_code == 403, revoked_replay.text


async def test_group_putaway_rolls_back_first_allocation_when_second_fails(e2e_client, monkeypatch):
    headers, warehouse_id, unit_id, item_id, lot_id, _ = await _measured_receipt(
        e2e_client, quantity="5.000000"
    )
    async with async_session_factory() as session:
        lot = await session.get(InventoryLotModel, lot_id)
        assert lot is not None
        lot.label_confirmation_required = False
        destinations = [
            Location(
                warehouse_id=warehouse_id,
                code=f"B4-ROLLBACK-{number}",
                aisle="B4",
                rack="03",
                level="01",
                position=str(number),
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            for number in (1, 2)
        ]
        session.add_all(destinations)
        await session.flush()
        destination_ids = [destination.id for destination in destinations]
        source = await session.get(InventoryHandlingUnitModel, unit_id)
        assert source is not None
        origin_location_id = source.location_id
        before_balance = await session.scalar(
            select(InventoryBalanceModel.quantity_base).where(
                InventoryBalanceModel.company_id == source.company_id,
                InventoryBalanceModel.inventory_item_id == item_id,
                InventoryBalanceModel.location_id == origin_location_id,
                InventoryBalanceModel.stock_status == "quarantine",
            )
        )
        await session.commit()

    original_post_movement = InventoryUseCases.post_movement
    calls = 0

    async def fail_second_movement(self, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise InventoryOperationError(
                "Synthetic second allocation failure.",
                code="synthetic_putaway_failure",
                status_code=409,
            )
        return await original_post_movement(self, **kwargs)

    monkeypatch.setattr(InventoryUseCases, "post_movement", fail_second_movement)
    idempotency_key = "block4-closure-second-allocation-rollback"
    failed = await e2e_client.post(
        "/api/v1/inventory/putaway-groups/confirm",
        headers=headers,
        json={
            "idempotency_key": idempotency_key,
            "receipt_lot_id": str(lot_id),
            "inventory_lot_detail_id": str(await _receipt_lot_detail_id(lot_id)),
            "inventory_item_id": str(item_id),
            "allocations": [
                {
                    "handling_unit_id": str(unit_id),
                    "quantity_base": quantity,
                    "destination_location_id": str(destination_id),
                }
                for quantity, destination_id in zip(("2", "3"), destination_ids, strict=True)
            ],
        },
    )
    assert failed.status_code == 409, failed.text
    assert calls == 2

    key_digest = hashlib.sha256(f"{headers['X-Company-ID']}:{idempotency_key}".encode()).hexdigest()
    async with async_session_factory() as session:
        source = await session.get(InventoryHandlingUnitModel, unit_id)
        assert source is not None
        assert source.quantity_base == Decimal("5")
        assert source.closed_at is None
        assert source.location_id == origin_location_id
        active_units = list(
            await session.scalars(
                select(InventoryHandlingUnitModel).where(
                    InventoryHandlingUnitModel.inventory_lot_id == lot_id,
                    InventoryHandlingUnitModel.closed_at.is_(None),
                )
            )
        )
        assert len(active_units) == 1
        after_balance = await session.scalar(
            select(InventoryBalanceModel.quantity_base).where(
                InventoryBalanceModel.company_id == source.company_id,
                InventoryBalanceModel.inventory_item_id == item_id,
                InventoryBalanceModel.location_id == origin_location_id,
                InventoryBalanceModel.stock_status == "quarantine",
            )
        )
        putaway_count = await session.scalar(
            select(func.count(InventoryMovementModel.id)).where(
                InventoryMovementModel.company_id == source.company_id,
                InventoryMovementModel.source_reference.like(f"putaway-group:{key_digest}:%"),
            )
        )
        successful_audit_count = await session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.company_id == source.company_id,
                AuditLog.resource_type == "inventory_putaway_groups",
                AuditLog.resource_id == key_digest,
                AuditLog.action == "CONFIRM",
            )
        )
    assert after_balance == before_balance
    assert putaway_count == 0
    assert successful_audit_count == 0


async def test_concurrent_group_movement_and_measurement_are_serialized(e2e_client):
    headers, warehouse_id, unit_id, item_id, lot_id, measured = await _measured_receipt(
        e2e_client, quantity="5.000000", username="block4-concurrent-writers"
    )
    company_id = uuid.UUID(headers["X-Company-ID"])
    assert measured["measurement_status"] == "verified"
    async with async_session_factory() as session:
        lot = await session.get(InventoryLotModel, lot_id)
        unit = await session.get(InventoryHandlingUnitModel, unit_id)
        assert lot is not None
        assert unit is not None
        lot.label_confirmation_required = False
        source_location_id = unit.location_id
        destinations = [
            Location(
                warehouse_id=warehouse_id,
                code=f"B4-CONCURRENT-WRITER-{number}",
                aisle="B4",
                rack="05",
                level="01",
                position=str(number),
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            for number in (1, 2)
        ]
        session.add_all(destinations)
        await session.flush()
        destination_ids = [row.id for row in destinations]
        await session.commit()

    group_request = {
        "idempotency_key": "block4-concurrent-group-writer",
        "receipt_lot_id": str(lot_id),
        "inventory_lot_detail_id": str(await _receipt_lot_detail_id(lot_id)),
        "inventory_item_id": str(item_id),
        "allocations": [
            {
                "handling_unit_id": str(unit_id),
                "quantity_base": "5",
                "destination_location_id": str(destination_ids[0]),
            }
        ],
    }
    movement_request = {
        "idempotency_key": "block4-concurrent-movement-writer",
        "movement_type": "putaway",
        "source_reference": "block4-concurrent-direct-putaway",
        "lines": [
            {
                "inventory_item_id": str(item_id),
                "handling_unit_id": str(unit_id),
                "from_location_id": str(source_location_id),
                "to_location_id": str(destination_ids[1]),
                "from_stock_status": "quarantine",
                "to_stock_status": "available",
                "quantity_base": "5",
            }
        ],
    }
    measurement_request = {
        "source": "manual",
        "measures": {
            "gross_weight_kg": "2",
            "length_m": "0.2",
            "width_m": "0.2",
            "height_m": "0.2",
        },
    }
    barrier = asyncio.Barrier(3)

    async def race_group():
        await barrier.wait()
        return await e2e_client.post(
            "/api/v1/inventory/putaway-groups/confirm",
            headers=headers,
            json=group_request,
        )

    async def race_movement():
        await barrier.wait()
        return await e2e_client.post(
            "/api/v1/inventory/movements/confirm",
            headers=headers,
            json=movement_request,
        )

    async def race_measurement():
        await barrier.wait()
        return await e2e_client.patch(
            f"/api/v1/inventory/handling-units/{unit_id}/measurements",
            headers=headers,
            json=measurement_request,
        )

    group_response, movement_response, measurement_response = await asyncio.wait_for(
        asyncio.gather(race_group(), race_movement(), race_measurement()), timeout=8
    )
    assert sorted((group_response.status_code, movement_response.status_code)) == [201, 409]
    assert measurement_response.status_code in {200, 409}, measurement_response.text

    async with async_session_factory() as session:
        current = await session.get(InventoryHandlingUnitModel, unit_id)
        assert current is not None
        assert current.closed_at is None
        assert current.stock_status == "available"
        assert current.quantity_base == Decimal("5")
        assert current.location_id in set(destination_ids)
        group_key_digest = hashlib.sha256(
            f"{company_id}:{group_request['idempotency_key']}".encode()
        ).hexdigest()
        winning_movements = list(
            await session.scalars(
                select(InventoryMovementModel).where(
                    InventoryMovementModel.company_id == current.company_id,
                    or_(
                        InventoryMovementModel.source_reference
                        == "block4-concurrent-direct-putaway",
                        InventoryMovementModel.source_reference.like(
                            f"putaway-group:{group_key_digest}:%"
                        ),
                    ),
                )
            )
        )
        assert len(winning_movements) == 1
        balances = list(
            await session.scalars(
                select(InventoryBalanceModel).where(
                    InventoryBalanceModel.company_id == current.company_id,
                    InventoryBalanceModel.inventory_item_id == item_id,
                    InventoryBalanceModel.location_id.in_(destination_ids),
                )
            )
        )
        assert sum((row.quantity_base for row in balances), Decimal("0")) == Decimal("5")


async def test_concurrent_group_retry_applies_once_and_replays(e2e_client, monkeypatch):
    headers, warehouse_id, unit_id, item_id, lot_id, _ = await _measured_receipt(
        e2e_client, username="block4-concurrent-group"
    )
    async with async_session_factory() as session:
        lot = await session.get(InventoryLotModel, lot_id)
        assert lot is not None
        lot.label_confirmation_required = False
        destination = Location(
            warehouse_id=warehouse_id,
            code="B4-CONCURRENT-GROUP",
            aisle="B4",
            rack="04",
            level="01",
            position="01",
            storage_eligible=True,
            capacity_enforcement_mode="disabled",
        )
        session.add(destination)
        await session.flush()
        destination_id = destination.id
        await session.commit()

    from app.infrastructure.repositories.inventory_valuation_repository import (
        SqlAlchemyInventoryValuationRepository,
    )

    original_lock = SqlAlchemyInventoryValuationRepository.lock
    barrier = asyncio.Barrier(2)
    gated_calls = 0
    gated_calls_lock = asyncio.Lock()

    async def synchronized_first_locks(self, company_id):
        nonlocal gated_calls
        async with gated_calls_lock:
            synchronize = gated_calls < 2
            if synchronize:
                gated_calls += 1
        if synchronize:
            await asyncio.wait_for(barrier.wait(), timeout=5)
        await original_lock(self, company_id)

    monkeypatch.setattr(SqlAlchemyInventoryValuationRepository, "lock", synchronized_first_locks)
    idempotency_key = "block4-closure-concurrent-retry"
    body = {
        "idempotency_key": idempotency_key,
        "receipt_lot_id": str(lot_id),
        "inventory_lot_detail_id": str(await _receipt_lot_detail_id(lot_id)),
        "inventory_item_id": str(item_id),
        "allocations": [
            {
                "handling_unit_id": str(unit_id),
                "quantity_base": "4",
                "destination_location_id": str(destination_id),
            }
        ],
    }
    first, second = await asyncio.wait_for(
        asyncio.gather(
            e2e_client.post("/api/v1/inventory/putaway-groups/confirm", headers=headers, json=body),
            e2e_client.post("/api/v1/inventory/putaway-groups/confirm", headers=headers, json=body),
        ),
        timeout=15,
    )
    assert first.status_code == second.status_code == 201, (first.text, second.text)
    assert {first.json()["replayed"], second.json()["replayed"]} == {False, True}

    key_digest = hashlib.sha256(f"{headers['X-Company-ID']}:{idempotency_key}".encode()).hexdigest()
    async with async_session_factory() as session:
        movements = list(
            await session.scalars(
                select(InventoryMovementModel).where(
                    InventoryMovementModel.source_reference.like(f"putaway-group:{key_digest}:%")
                )
            )
        )
        audits = list(
            await session.scalars(
                select(AuditLog).where(
                    AuditLog.resource_type == "inventory_putaway_groups",
                    AuditLog.resource_id == key_digest,
                    AuditLog.action == "CONFIRM",
                )
            )
        )
        active_units = list(
            await session.scalars(
                select(InventoryHandlingUnitModel).where(
                    InventoryHandlingUnitModel.inventory_lot_id == lot_id,
                    InventoryHandlingUnitModel.closed_at.is_(None),
                )
            )
        )
    assert len(movements) == 1
    assert len(audits) == 1
    assert len(active_units) == 1
    assert active_units[0].quantity_base == Decimal("4")
    assert active_units[0].location_id == destination_id


async def test_new_receipt_split_invalidates_label_on_both_grouped_results(e2e_client):
    headers, warehouse_id, unit_id, item_id, lot_id, _ = await _measured_receipt(
        e2e_client, quantity="10.000000"
    )
    preview = await e2e_client.get(
        f"/api/v1/inventory/labels/preview?handling_unit_id={unit_id}", headers=headers
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["label_confirmation_required"] is True
    printed = await e2e_client.post(
        "/api/v1/inventory/labels/prints",
        headers=headers,
        json={
            "idempotency_key": "b4-closure-initial-label-print",
            "handling_unit_id": str(unit_id),
            "quantity_printed": 1,
            "print_date": datetime.now(UTC)
            .astimezone(ZoneInfo("America/El_Salvador"))
            .date()
            .isoformat(),
            "reason": "initial",
        },
    )
    assert printed.status_code == 200, printed.text
    confirmed = await e2e_client.post(
        "/api/v1/inventory/labels/confirmations",
        headers=headers,
        json={
            "idempotency_key": "b4-closure-label-placement",
            "handling_unit_id": str(unit_id),
            "handling_unit_code": preview.json()["handling_unit_code"],
            "label_print_id": printed.json()["id"],
        },
    )
    assert confirmed.status_code == 200, confirmed.text

    async with async_session_factory() as session:
        destinations = [
            Location(
                warehouse_id=warehouse_id,
                code=f"B4-LABEL-{number}",
                aisle="B4",
                rack="02",
                level="01",
                position=str(number),
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            for number in (1, 2)
        ]
        session.add_all(destinations)
        await session.flush()
        destination_ids = [destination.id for destination in destinations]
        await session.commit()

    group = await e2e_client.post(
        "/api/v1/inventory/putaway-groups/confirm",
        headers=headers,
        json={
            "idempotency_key": "b4-closure-new-label-two-destinations",
            "receipt_lot_id": str(lot_id),
            "inventory_lot_detail_id": str(await _receipt_lot_detail_id(lot_id)),
            "inventory_item_id": str(item_id),
            "allocations": [
                {
                    "handling_unit_id": str(unit_id),
                    "quantity_base": quantity,
                    "destination_location_id": str(destination_id),
                }
                for quantity, destination_id in zip(("4", "6"), destination_ids, strict=True)
            ],
        },
    )
    assert group.status_code == 201, group.text
    assert {row["stock_status"] for row in group.json()["allocations"]} == {"quarantine"}

    listed = await e2e_client.get(
        f"/api/v1/inventory/warehouses/{warehouse_id}/handling-units", headers=headers
    )
    assert listed.status_code == 200, listed.text
    result_ids = {row["handling_unit_id"] for row in group.json()["allocations"]}
    resulting = [row for row in listed.json() if row["id"] in result_ids]
    assert len(resulting) == 2
    for unit in resulting:
        assert "measurement_required" in unit["release_requirements"]
        assert "label_confirmation_required" in unit["release_requirements"]

    async with async_session_factory() as session:
        rows = list(
            await session.scalars(
                select(InventoryHandlingUnitModel).where(
                    InventoryHandlingUnitModel.inventory_lot_id == lot_id,
                    InventoryHandlingUnitModel.closed_at.is_(None),
                )
            )
        )
    original = next(row for row in rows if row.id == unit_id)
    child = next(row for row in rows if row.id != unit_id)
    assert original.label_revision == confirmed.json()["label_revision"] + 1
    assert child.label_revision == 1
    assert child.origin_handling_unit_id == original.id


async def test_0082_to_0083_preserves_legacy_receipt_rows(e2e_client):
    headers, _, unit_id, _, lot_id, _ = await _measured_receipt(e2e_client)
    async with async_session_factory() as session:
        legacy_unit = await session.get(InventoryHandlingUnitModel, unit_id)
        legacy_lot = await session.get(InventoryLotModel, lot_id)
        assert legacy_unit is not None
        assert legacy_lot is not None
        legacy_code = legacy_unit.code
        legacy_quantity = legacy_unit.quantity_base
        legacy_lot_code = legacy_lot.code

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    backend_root = Path(__file__).resolve().parents[2]
    database_url = os.environ["DATABASE_URL_SYNC"]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_section_option("alembic", "sqlalchemy.url", database_url.replace("%", "%%"))
    from app.infrastructure.db.session import dispose_engine

    await dispose_engine()
    try:
        command.downgrade(config, "0082")
        engine = create_engine(database_url)
        try:
            with engine.connect() as connection:
                preserved = connection.execute(
                    text(
                        "SELECT l.code AS lot_code, h.code AS unit_code, h.quantity_base "
                        "FROM inventory_lots l JOIN inventory_handling_units h "
                        "ON h.inventory_lot_id = l.id WHERE l.id = :lot_id AND h.id = :unit_id"
                    ),
                    {"lot_id": lot_id, "unit_id": unit_id},
                ).one()
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
        finally:
            engine.dispose()
        assert revision == "0082"
        assert preserved.lot_code == legacy_lot_code
        assert preserved.unit_code == legacy_code
        assert Decimal(preserved.quantity_base) == legacy_quantity
    finally:
        # Restore the disposable test schema even if an assertion above fails.
        command.upgrade(config, "head")
        await dispose_engine()

    async with async_session_factory() as session:
        migrated_unit = await session.get(InventoryHandlingUnitModel, unit_id)
        migrated_lot = await session.get(InventoryLotModel, lot_id)
        assert migrated_unit is not None
        assert migrated_lot is not None
        assert migrated_unit.code == legacy_code
        assert migrated_unit.quantity_base == legacy_quantity
        assert migrated_unit.inventory_lot_detail_id is None
        assert migrated_unit.label_revision == 1
        assert migrated_lot.code == legacy_lot_code
        assert migrated_lot.label_confirmation_required is False

    _, _, _, _, new_lot_id, _ = await _measured_receipt(e2e_client, username="block4-closure-new")
    async with async_session_factory() as session:
        new_lot = await session.get(InventoryLotModel, new_lot_id)
        assert new_lot is not None
        assert new_lot.label_confirmation_required is True
