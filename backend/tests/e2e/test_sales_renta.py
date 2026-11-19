"""V4b2: clasificación de renta sugerida por la actividad y elegida en cada documento."""

from __future__ import annotations

import uuid

import pytest
from app.core.config import settings
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.fiscal import CompanyEconomicActivityModel
from httpx import AsyncClient
from sqlalchemy import select, update

from tests.e2e.test_sales_invoices import DOCUMENTS, ORDERS, _confirmed_order

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

ACTIVITIES = "/api/v1/fiscal/activities"


async def _set_all(company_id: uuid.UUID, operation: int | None, income: int | None) -> None:
    async with async_session_factory() as session:
        await session.execute(
            update(CompanyEconomicActivityModel)
            .where(CompanyEconomicActivityModel.company_id == company_id)
            .values(renta_operation_type=operation, renta_income_type=income)
        )
        await session.commit()


async def test_activity_suggests_and_the_invoice_can_change_it(e2e_client: AsyncClient) -> None:
    admin, order, point = await _confirmed_order(e2e_client)
    company_id = uuid.UUID(admin["X-Company-ID"])
    async with async_session_factory() as session:
        activity_id = await session.scalar(
            select(CompanyEconomicActivityModel.id).where(
                CompanyEconomicActivityModel.company_id == company_id,
                CompanyEconomicActivityModel.is_primary.is_(True),
            )
        )
    assert activity_id is not None

    bad = await e2e_client.put(
        f"{ACTIVITIES}/{activity_id}/renta",
        json={"operation_type": 12, "income_type": 3},
        headers=admin,
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "sales_renta_invalid"
    saved = await e2e_client.put(
        f"{ACTIVITIES}/{activity_id}/renta",
        json={"operation_type": 1, "income_type": 2},
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    assert (saved.json()["renta_operation_type"], saved.json()["renta_income_type"]) == (1, 2)

    options = (
        await e2e_client.get(f"{ORDERS}/{order['id']}/invoice-options", headers=admin)
    ).json()
    assert (options["renta_operation_type"], options["renta_income_type"]) in ((1, 2), (1, 3))

    invoiced = await e2e_client.post(
        f"{ORDERS}/{order['id']}/invoice",
        json={"point_of_sale_id": str(point), "renta_operation_type": 4, "renta_income_type": 3},
        headers=admin,
    )
    assert invoiced.status_code == 202, invoiced.text
    document = invoiced.json()
    assert (document["renta_operation_type"], document["renta_income_type"]) == (4, 3)
    shown = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}", headers=admin)).json()
    assert (shown["renta_operation_type"], shown["renta_income_type"]) == (4, 3)


async def test_without_suggestion_the_invoice_must_choose(e2e_client: AsyncClient) -> None:
    admin, order, point = await _confirmed_order(e2e_client)
    company_id = uuid.UUID(admin["X-Company-ID"])
    await _set_all(company_id, None, None)
    try:
        options = (
            await e2e_client.get(f"{ORDERS}/{order['id']}/invoice-options", headers=admin)
        ).json()
        assert options["renta_operation_type"] is None
        missing = await e2e_client.post(
            f"{ORDERS}/{order['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
        )
        assert missing.status_code == 422
        assert missing.json()["code"] == "sales_invoice_renta_required"
        half = await e2e_client.post(
            f"{ORDERS}/{order['id']}/invoice",
            json={"point_of_sale_id": str(point), "renta_operation_type": 1},
            headers=admin,
        )
        assert half.status_code == 422
        assert half.json()["code"] == "sales_renta_invalid"
        chosen = await e2e_client.post(
            f"{ORDERS}/{order['id']}/invoice",
            json={
                "point_of_sale_id": str(point),
                "renta_operation_type": 1,
                "renta_income_type": 3,
            },
            headers=admin,
        )
        assert chosen.status_code == 202, chosen.text
    finally:
        await _set_all(company_id, 1, 3)
