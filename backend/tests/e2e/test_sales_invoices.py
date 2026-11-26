"""V3b: facturar el pedido contra el servicio DTE real en modo simulado.

La emisión la hace el trabajador; aquí se llama a ``process_fiscal_document`` directamente para
no depender de que ``dte-worker`` mire la base de pruebas.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from app.core.config import settings
from app.infrastructure.db.session import async_session_factory, session_scope
from app.infrastructure.dte_email import email_sender, process_fiscal_email
from app.infrastructure.dte_worker import dte_client, object_storage, process_fiscal_document
from app.infrastructure.models.fiscal import (
    CompanyDteDocumentTypeModel,
    CompanyEconomicActivityModel,
    CompanyFiscalProfileModel,
    FiscalEstablishmentModel,
    FiscalPointOfSaleModel,
)
from app.infrastructure.models.organization import Company
from app.infrastructure.models.sales import SalesCustomerModel
from httpx import AsyncClient
from sqlalchemy import select, update

from tests.e2e.test_fiscal_settings import _second_company
from tests.e2e.test_sales_orders import ORDER_SELLER, _create, _order_act, _order_body, _stock
from tests.e2e.test_sales_quotations import _setup, _with_policy

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

ORDERS = "/api/v1/sales"
DOCUMENTS = "/api/v1/sales/fiscal-documents"


async def _issuer(company_id: uuid.UUID, branch_id: uuid.UUID) -> uuid.UUID:
    """Deja a la empresa lista para emitir desde la sucursal; devuelve un punto de venta."""

    async with async_session_factory() as session:
        company = await session.get(Company, company_id)
        assert company is not None
        company.nrc = "1234567"
        if not company.nit or len("".join(ch for ch in company.nit if ch.isdigit())) != 14:  # noqa: PLR2004
            company.nit = f"0614{uuid.uuid4().int % 10**10:010d}"
        profile = await session.get(CompanyFiscalProfileModel, company_id)
        if profile is None:
            profile = CompanyFiscalProfileModel(company_id=company_id)
            session.add(profile)
        profile.operating_mode = "simulated"
        profile.dte_email = "facturacion@example.com"
        profile.dte_phone = "2222-0000"
        activity = await session.scalar(
            select(CompanyEconomicActivityModel).where(
                CompanyEconomicActivityModel.company_id == company_id
            )
        )
        if activity is None:
            activity = CompanyEconomicActivityModel(
                company_id=company_id, activity_code="10712", is_primary=True
            )
            session.add(activity)
            await session.flush()
        # Clasificación de renta sugerida (V4b2): sin ella, facturar pide elegirla.
        await session.execute(
            update(CompanyEconomicActivityModel)
            .where(
                CompanyEconomicActivityModel.company_id == company_id,
                CompanyEconomicActivityModel.renta_operation_type.is_(None),
            )
            .values(renta_operation_type=1, renta_income_type=3)
        )
        establishment = await session.scalar(
            select(FiscalEstablishmentModel).where(
                FiscalEstablishmentModel.company_id == company_id,
                FiscalEstablishmentModel.branch_id == branch_id,
            )
        )
        if establishment is None:
            establishment = FiscalEstablishmentModel(
                company_id=company_id,
                branch_id=branch_id,
                establishment_type="02",
                code=f"M{uuid.uuid4().int % 899 + 100:03d}",
                activity_id=activity.id,
            )
            session.add(establishment)
            await session.flush()
        establishment.is_active = True
        point = FiscalPointOfSaleModel(
            company_id=company_id,
            establishment_id=establishment.id,
            code=f"P{uuid.uuid4().int % 899 + 100:03d}",
            name="Caja de facturación",
        )
        session.add(point)
        for document in ("01", "03"):
            setting = await session.get(CompanyDteDocumentTypeModel, (company_id, document))
            if setting is None:
                session.add(
                    CompanyDteDocumentTypeModel(
                        company_id=company_id, document_type=document, is_enabled=True
                    )
                )
            else:
                setting.is_enabled = True
        await session.commit()
        return point.id


async def _set_enabled(company_id: uuid.UUID, document: str, enabled: bool) -> None:
    async with async_session_factory() as session:
        setting = await session.get(CompanyDteDocumentTypeModel, (company_id, document))
        assert setting is not None
        setting.is_enabled = enabled
        await session.commit()


async def _process(document_id: str) -> None:
    client = dte_client()
    assert client is not None
    await process_fiscal_document(uuid.UUID(document_id), client=client, storage=object_storage())


async def _confirmed_order(
    client: AsyncClient, stock: str = "5"
) -> tuple[dict[str, str], dict, uuid.UUID]:
    admin, body, _unit = await _setup(client)
    await _stock(admin, body, stock)
    company_id = uuid.UUID(admin["X-Company-ID"])
    point = await _issuer(company_id, uuid.UUID(str(body["branch_id"])))
    order = await _create(client, admin, _order_body(body, "2"))
    confirmed = await _order_act(client, admin, order, "confirm")
    assert confirmed.status_code == 200, confirmed.text
    return admin, confirmed.json(), point


async def test_invoice_flow_is_idempotent_and_blocks_cancelling(e2e_client: AsyncClient) -> None:
    admin, order, point = await _confirmed_order(e2e_client)

    options = await e2e_client.get(f"{ORDERS}/{order['id']}/invoice-options", headers=admin)
    assert options.status_code == 200, options.text
    assert options.json()["blockers"] == []
    assert str(point) in {p["id"] for p in options.json()["points_of_sale"]}

    invoiced = await e2e_client.post(
        f"{ORDERS}/{order['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
    )
    assert invoiced.status_code == 202, invoiced.text
    document = invoiced.json()
    assert document["status"] == "pending"
    assert document["total"] == order["total"]
    again = await e2e_client.post(
        f"{ORDERS}/{order['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
    )
    assert again.status_code == 200
    assert again.json()["id"] == document["id"]

    await _process(document["id"])
    issued = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}", headers=admin)).json()
    assert issued["status"] == "simulated", issued
    assert issued["error_code"] is None, issued
    assert issued["control_number"].startswith(f"DTE-01-{issued['establishment_code']}P")
    assert issued["has_json"] is True
    assert issued["has_pdf"] is True

    dte = await e2e_client.get(f"{DOCUMENTS}/{document['id']}/json", headers=admin)
    assert dte.status_code == 200
    assert dte.json()["identificacion"]["numeroControl"] == issued["control_number"]
    assert f"{dte.json()['resumen']['totalPagar']:.2f}" == order["total"]
    assert dte.json()["emisor"]["codPuntoVenta"] == issued["point_of_sale_code"]
    pdf = await e2e_client.get(f"{DOCUMENTS}/{document['id']}/pdf", headers=admin)
    assert pdf.status_code == 200, pdf.text
    assert pdf.json()["url"].startswith("http")

    # Procesar otra vez no emite un segundo DTE.
    await _process(document["id"])
    inbox = await e2e_client.get(DOCUMENTS, params={"sale_id": order["id"]}, headers=admin)
    assert inbox.json()["total"] == 1

    current = (await e2e_client.get(f"{ORDERS}/{order['id']}", headers=admin)).json()
    blocked = await _order_act(e2e_client, admin, current, "cancel", reason="Cliente desistió")
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "sales_order_invoiced"


async def test_permanent_failure_then_retry_with_the_same_key(e2e_client: AsyncClient) -> None:
    admin, order, point = await _confirmed_order(e2e_client)
    company_id = uuid.UUID(admin["X-Company-ID"])
    document = (
        await e2e_client.post(
            f"{ORDERS}/{order['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
        )
    ).json()

    # Con la factura deshabilitada el servicio rechaza el tipo: falla sin reintentar.
    await _set_enabled(company_id, "01", False)
    await _process(document["id"])
    failed = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}", headers=admin)).json()
    assert failed["status"] == "failed", failed
    assert failed["error_code"] == "DTE_DOCUMENT_TYPE_NOT_ALLOWED"

    await _set_enabled(company_id, "01", True)
    retried = await e2e_client.post(f"{DOCUMENTS}/{document['id']}/retry", headers=admin)
    assert retried.status_code == 202, retried.text
    assert retried.json()["status"] == "pending"
    await _process(document["id"])
    issued = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}", headers=admin)).json()
    assert issued["status"] == "simulated", issued
    not_again = await e2e_client.post(f"{DOCUMENTS}/{document['id']}/retry", headers=admin)
    assert not_again.status_code == 422
    assert not_again.json()["code"] == "sales_invoice_not_retryable"


async def test_rules_permissions_and_company_isolation(e2e_client: AsyncClient) -> None:
    admin, body, _unit = await _setup(e2e_client)
    await _stock(admin, body, "5")
    company_id = uuid.UUID(admin["X-Company-ID"])
    point = await _issuer(company_id, uuid.UUID(str(body["branch_id"])))

    draft = await _create(e2e_client, admin, _order_body(body, "1"))
    not_confirmed = await e2e_client.post(
        f"{ORDERS}/{draft['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
    )
    assert not_confirmed.status_code == 422
    assert not_confirmed.json()["code"] == "sales_invoice_order_not_confirmed"
    options = (
        await e2e_client.get(f"{ORDERS}/{draft['id']}/invoice-options", headers=admin)
    ).json()
    assert options["blockers"] == ["Solo se factura un pedido confirmado."]

    order = (await _order_act(e2e_client, admin, draft, "confirm")).json()
    seller = await _with_policy(e2e_client, admin, ORDER_SELLER, "5", "2")
    denied = await e2e_client.post(
        f"{ORDERS}/{order['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=seller
    )
    assert denied.status_code == 403
    assert (await e2e_client.get(DOCUMENTS, headers=seller)).status_code == 403

    document = (
        await e2e_client.post(
            f"{ORDERS}/{order['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
        )
    ).json()
    me = (await e2e_client.get("/api/v1/auth/me", headers=admin)).json()
    other_company, _branch = await _second_company(str(me["id"]))
    other = {**admin, "X-Company-ID": str(other_company)}
    foreign = await e2e_client.get(f"{DOCUMENTS}/{document['id']}", headers=other)
    assert foreign.status_code == 404
    assert (await e2e_client.get(DOCUMENTS, headers=other)).json()["total"] == 0


# --- V3c: envío por correo -------------------------------------------------------------------


MAILPIT = "http://mailpit:8025/api/v1"


async def _set_customer_email(order: dict, email: str | None) -> None:
    async with async_session_factory() as session:
        customer = await session.get(SalesCustomerModel, uuid.UUID(order["customer_id"]))
        assert customer is not None
        customer.email = email
        await session.commit()


async def _deliver(email_id: str) -> None:
    sender = email_sender()
    assert sender is not None
    await process_fiscal_email(
        uuid.UUID(email_id),
        sender=sender,
        storage=object_storage(),
        client=dte_client(),
        scope=session_scope,
    )


async def _mailbox(address: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        found = await client.get(f"{MAILPIT}/search", params={"query": f"to:{address}"})
    found.raise_for_status()
    return list(found.json()["messages"])


async def _issued(client: AsyncClient) -> tuple[dict[str, str], dict, dict]:
    admin, order, point = await _confirmed_order(client)
    document = (
        await client.post(
            f"{ORDERS}/{order['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
        )
    ).json()
    return admin, order, document


@pytest.mark.skipif(not settings.SMTP_HOST, reason="Sin servidor de correo configurado")
async def test_issued_document_is_emailed_to_the_customer(e2e_client: AsyncClient) -> None:
    admin, order, document = await _issued(e2e_client)
    customer = f"cliente-{uuid.uuid4().hex[:8]}@example.com"
    await _set_customer_email(order, customer)
    await _process(document["id"])

    history = await e2e_client.get(f"{DOCUMENTS}/{document['id']}/emails", headers=admin)
    assert history.status_code == 200, history.text
    assert history.json()["enabled"] is True
    assert history.json()["customer_email"] == customer
    [auto] = history.json()["items"]
    assert auto["origin"] == "auto"
    assert auto["status"] == "pending"
    assert auto["recipients"] == [customer]

    await _deliver(auto["id"])
    [sent] = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}/emails", headers=admin)).json()[
        "items"
    ]
    assert sent["status"] == "sent", sent
    [message] = await _mailbox(customer)
    issued = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}", headers=admin)).json()
    assert issued["control_number"] in message["Subject"]
    assert message["Subject"].startswith("[SIMULADO")
    assert message["Attachments"] == 2
    assert message["ReplyTo"][0]["Address"] == "facturacion@example.com"

    # Procesar de nuevo no reenvía; reemitir el aviso automático tampoco.
    await _deliver(auto["id"])
    await _process(document["id"])
    assert len(await _mailbox(customer)) == 1


@pytest.mark.skipif(not settings.SMTP_HOST, reason="Sin servidor de correo configurado")
async def test_manual_email_rules_and_permissions(e2e_client: AsyncClient) -> None:
    admin, order, document = await _issued(e2e_client)
    await _set_customer_email(order, None)

    not_issued = await e2e_client.post(
        f"{DOCUMENTS}/{document['id']}/emails", json={}, headers=admin
    )
    assert not_issued.status_code == 422
    assert not_issued.json()["code"] == "sales_invoice_email_not_issued"

    await _process(document["id"])
    history = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}/emails", headers=admin)).json()
    assert history["items"] == []  # Sin correo en la ficha no hay envío automático.
    missing = await e2e_client.post(f"{DOCUMENTS}/{document['id']}/emails", json={}, headers=admin)
    assert missing.status_code == 422
    assert missing.json()["code"] == "sales_invoice_email_required"
    invalid = await e2e_client.post(
        f"{DOCUMENTS}/{document['id']}/emails", json={"recipients": ["no-es-correo"]}, headers=admin
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "sales_invoice_email_invalid"

    target = f"contabilidad-{uuid.uuid4().hex[:8]}@example.com"
    manual = await e2e_client.post(
        f"{DOCUMENTS}/{document['id']}/emails",
        json={"recipients": [target.upper(), target]},
        headers=admin,
    )
    assert manual.status_code == 202, manual.text
    assert manual.json()["origin"] == "manual"
    assert manual.json()["recipients"] == [target]
    assert manual.json()["requested_by_name"]
    await _deliver(manual.json()["id"])
    [message] = await _mailbox(target)
    assert message["Attachments"] == 2

    seller = await _with_policy(e2e_client, admin, ORDER_SELLER, "5", "2")
    denied = await e2e_client.post(
        f"{DOCUMENTS}/{document['id']}/emails", json={"recipients": [target]}, headers=seller
    )
    assert denied.status_code == 403
