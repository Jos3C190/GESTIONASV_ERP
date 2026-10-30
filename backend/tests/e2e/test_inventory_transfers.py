"""HTTP-level acceptance checks for company and branch-scoped transfers."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.inventory import InventoryBalanceModel, InventoryMovementModel
from app.infrastructure.models.organization import Company, UserCompany
from app.infrastructure.models.user import User
from sqlalchemy import func, select

from tests.e2e.test_inventory_block4_closure import _branch_profile_headers
from tests.e2e.test_purchase_orders import _headers
from tests.integration.test_inventory_transfer_repository import _create_context

pytestmark = pytest.mark.e2e


async def _committed_transfer_context(
    client, suffix: str
) -> tuple[SimpleNamespace, dict[str, str]]:
    async with async_session_factory() as session:
        context = await _create_context(session, suffix)
        actor_username = f"transfer-{suffix[:16]}"
        actor = await session.scalar(select(User).where(User.id == context.actor_id))
        assert actor is not None
        session.add(
            Employee(
                company_id=context.company_id,
                employee_code=f"TR-{suffix[:12].upper()}",
                first_name=actor_username,
                last_name="Prueba",
                user_id=context.actor_id,
                status="activo",
            )
        )
        values = SimpleNamespace(
            company_id=context.company_id,
            actor_id=context.actor_id,
            origin_id=context.origin.id,
            destination_id=context.destination.id,
            destination_branch_id=context.destination.branch_id,
            destination_location_id=context.destination_location.id,
            handling_unit_id=context.handling_unit_id,
            item_id=context.item.id,
            vehicle_id=context.vehicle_id,
        )
        await session.commit()
    headers = await _headers(
        client,
        company_id=values.company_id,
        username=f"transfer-admin-{suffix[:10]}",
        is_superuser=True,
    )
    return values, headers


async def _create_preparation(
    client, values: SimpleNamespace, headers: dict[str, str], suffix: str
):
    response = await client.post(
        "/api/v1/inventory/transfers",
        headers=headers,
        json={
            "idempotency_key": f"transfer-create-{suffix}",
            "origin_warehouse_id": str(values.origin_id),
            "destination_warehouse_id": str(values.destination_id),
            "vehicle_id": str(values.vehicle_id),
            "notes": "Preparación ficticia para comprobar el motor.",
            "lines": [
                {
                    "handling_unit_id": str(values.handling_unit_id),
                    "quantity_base": "10",
                    "demand_allocations": [],
                    "excess_reason": "Traslado manual de demostración",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _dispatch(
    client, transfer: dict, headers: dict[str, str], suffix: str, vehicle_id: uuid.UUID
):
    return await client.post(
        f"/api/v1/inventory/transfers/{transfer['id']}/dispatch",
        headers=headers,
        json={
            "vehicle_id": str(vehicle_id),
            "idempotency_key": f"transfer-dispatch-{suffix}",
        },
    )


async def test_concurrent_dispatches_cannot_consume_the_same_handling_unit(e2e_client) -> None:
    suffix = uuid.uuid4().hex
    values, headers = await _committed_transfer_context(e2e_client, suffix)
    first = await _create_preparation(e2e_client, values, headers, f"first-{suffix[:12]}")
    second = await _create_preparation(e2e_client, values, headers, f"second-{suffix[:12]}")

    async def dispatch(transfer: dict, key: str):
        response = await e2e_client.post(
            f"/api/v1/inventory/transfers/{transfer['id']}/dispatch",
            headers=headers,
            json={"vehicle_id": str(values.vehicle_id), "idempotency_key": key},
        )
        return transfer, response

    results = await asyncio.gather(
        dispatch(first, f"dispatch-first-{suffix}"),
        dispatch(second, f"dispatch-second-{suffix}"),
    )
    successes = [
        (transfer, response) for transfer, response in results if response.status_code == 200
    ]
    conflicts = [
        (transfer, response) for transfer, response in results if response.status_code == 409
    ]
    assert len(successes) == 1, [(response.status_code, response.text) for _, response in results]
    assert len(conflicts) == 1, [(response.status_code, response.text) for _, response in results]

    successful_transfer, successful_response = successes[0]
    assert successful_response.json()["status"] == "in_transit"
    async with async_session_factory() as session:
        total = await session.scalar(
            select(func.sum(InventoryBalanceModel.quantity_base)).where(
                InventoryBalanceModel.company_id == values.company_id,
                InventoryBalanceModel.inventory_item_id == values.item_id,
            )
        )
        assert total == Decimal("10")
        movements = await session.scalar(
            select(func.count(InventoryMovementModel.id)).where(
                InventoryMovementModel.company_id == values.company_id,
                InventoryMovementModel.source_reference
                == f"inventory_transfer:{successful_transfer['code']}:dispatch",
            )
        )
        assert movements == 1
        vehicle_balance = await session.scalar(
            select(InventoryBalanceModel.quantity_base).where(
                InventoryBalanceModel.company_id == values.company_id,
                InventoryBalanceModel.inventory_item_id == values.item_id,
                InventoryBalanceModel.stock_status == "in_transit",
            )
        )
        assert vehicle_balance == Decimal("10")
        competitor = conflicts[0][0]
        loser = await session.scalar(
            select(InventoryMovementModel.id).where(
                InventoryMovementModel.company_id == values.company_id,
                InventoryMovementModel.source_reference
                == f"inventory_transfer:{competitor['code']}:dispatch",
            )
        )
        assert loser is None


async def test_destination_branch_receiver_can_receive_without_global_access(e2e_client) -> None:
    suffix = uuid.uuid4().hex
    values, headers = await _committed_transfer_context(e2e_client, suffix)
    transfer = await _create_preparation(e2e_client, values, headers, suffix)
    dispatched = await _dispatch(
        e2e_client, transfer, headers, f"dispatch-{suffix}", values.vehicle_id
    )
    assert dispatched.status_code == 200, dispatched.text

    receiver_username = f"transfer-receiver-{suffix[:10]}"
    receiver_headers = await _branch_profile_headers(
        e2e_client,
        company_id=values.company_id,
        branch_id=values.destination_branch_id,
        username=receiver_username,
        permissions=("inventory:read", "inventory:receive"),
    )
    async with async_session_factory() as session:
        receiver = await session.scalar(
            select(UserCompany).where(
                UserCompany.company_id == values.company_id,
                UserCompany.user_id
                == select(User.id).where(User.username == receiver_username).scalar_subquery(),
            )
        )
        assert receiver is not None
        assert receiver.access_all_branches is False

    transfer_detail_id = dispatched.json()["lines"][0]["id"]

    async def receive(key: str):
        return await e2e_client.post(
            f"/api/v1/inventory/transfers/{transfer['id']}/receive",
            headers=receiver_headers,
            json={
                "idempotency_key": key,
                "lines": [
                    {
                        "transfer_detail_id": transfer_detail_id,
                        "destination_location_id": str(values.destination_location_id),
                        "quantity_base": "6",
                    }
                ],
            },
        )

    receipt_results = await asyncio.gather(
        receive(f"receive-first-{suffix}"),
        receive(f"receive-second-{suffix}"),
    )
    successful_receipts = [result for result in receipt_results if result.status_code == 200]
    conflicts = [result for result in receipt_results if result.status_code == 409]
    assert len(successful_receipts) == 1, [result.text for result in receipt_results]
    assert len(conflicts) == 1, [result.text for result in receipt_results]
    assert successful_receipts[0].json()["status"] == "in_transit"
    assert successful_receipts[0].json()["lines"][0]["quantity_received"] == "6.000000"
    assert successful_receipts[0].json()["lines"][0]["quantity_in_transit"] == "4.000000"
    async with async_session_factory() as session:
        balance = await session.scalar(
            select(InventoryBalanceModel.quantity_base).where(
                InventoryBalanceModel.company_id == values.company_id,
                InventoryBalanceModel.inventory_item_id == values.item_id,
                InventoryBalanceModel.location_id == values.destination_location_id,
                InventoryBalanceModel.stock_status == "quarantine",
            )
        )
        assert balance == Decimal("6")
        transit_balance = await session.scalar(
            select(func.sum(InventoryBalanceModel.quantity_base)).where(
                InventoryBalanceModel.company_id == values.company_id,
                InventoryBalanceModel.inventory_item_id == values.item_id,
                InventoryBalanceModel.stock_status == "in_transit",
            )
        )
        assert transit_balance == Decimal("4")


async def test_transfer_from_another_company_is_not_visible(e2e_client) -> None:
    suffix = uuid.uuid4().hex
    values, headers = await _committed_transfer_context(e2e_client, suffix)
    transfer = await _create_preparation(e2e_client, values, headers, suffix)

    async with async_session_factory() as session:
        source_company = await session.get(Company, values.company_id)
        assert source_company is not None
        foreign_company = Company(
            name=f"Empresa ajena B03 {suffix[:8]}",
            commercial_name=f"Empresa ajena B03 {suffix[:8]}",
            nit=f"TEST-B03-{suffix[:20]}",
            nrc=f"REG-B03-{suffix[:20]}",
            address=source_company.address,
            department_id=source_company.department_id,
            municipality_id=source_company.municipality_id,
            district_id=source_company.district_id,
        )
        session.add(foreign_company)
        await session.flush()
        foreign_company_id = foreign_company.id
        await session.commit()

    foreign_company_headers = {**headers, "X-Company-ID": str(foreign_company_id)}
    response = await e2e_client.get(
        f"/api/v1/inventory/transfers/{transfer['id']}", headers=foreign_company_headers
    )
    assert response.status_code == 404, response.text
