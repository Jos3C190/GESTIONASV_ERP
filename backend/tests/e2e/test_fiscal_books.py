"""Libros de IVA y F-07: un mes con una factura simulada y una compra con su documento."""

from __future__ import annotations

import uuid
import zipfile
from datetime import date, datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import pytest
from app.core.config import settings
from app.infrastructure.db.session import async_session_factory
from httpx import AsyncClient
from sqlalchemy import text

from tests.e2e.conftest import get_test_company_id
from tests.e2e.test_sales_invalidations import _issued

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

BOOKS = "/api/v1/fiscal-books"


async def _received_purchase(company_id: uuid.UUID, day: date) -> uuid.UUID:
    """Una compra verificada de $100 gravados con $13 de IVA, sin documento del proveedor."""

    purchase_id = uuid.uuid4()
    async with async_session_factory() as session:
        await session.execute(text("SET LOCAL session_replication_role = replica"))
        supplier = await session.scalar(
            text(
                "INSERT INTO suppliers (code, name, legal_name, country_id, company_id) "
                "VALUES (:code, 'Molinos', 'Molinos de El Salvador, S.A. de C.V.', 1, :company) "
                "RETURNING id_supplier"
            ),
            {"code": f"PRV-{purchase_id.hex[:8]}", "company": company_id},
        )
        await session.execute(
            text(
                "INSERT INTO purchases (id, company_id, code, purchase_order_id, supplier_id, "
                "warehouse_id, created_by_id, currency, status, supplier_invoice_date, "
                "subtotal, tax, total) VALUES (:id, :company, :code, gen_random_uuid(), "
                ":supplier, gen_random_uuid(), gen_random_uuid(), 'USD', 'verified', :day, "
                "100, 13, 113)"
            ),
            {
                "id": purchase_id,
                "company": company_id,
                "code": f"CMP-{purchase_id.hex[:8]}",
                "supplier": supplier,
                "day": day,
            },
        )
        await session.execute(
            text(
                "INSERT INTO purchase_details (company_id, purchase_id, purchase_order_detail_id, "
                "product_id, quantity_ordered, quantity_received, unit_id, unit_price, subtotal, "
                "discount, tax_rate, tax_amount, total) VALUES (:company, :id, gen_random_uuid(), "
                "1, 1, 1, 1, 100, 100, 0, 13, 13, 113)"
            ),
            {"company": company_id, "id": purchase_id},
        )
        await session.commit()
    return purchase_id


async def test_month_books_annexes_and_purchase_document(e2e_client: AsyncClient) -> None:
    admin, _order, _point, invoice = await _issued(e2e_client)
    issued_at = datetime.fromisoformat(invoice["issued_at"].replace("Z", "+00:00"))
    day = issued_at.astimezone(ZoneInfo("America/El_Salvador")).date()
    period = f"{day:%Y-%m}"
    company_id = await get_test_company_id()
    purchase_id = await _received_purchase(company_id, day)

    month = (await e2e_client.get(f"{BOOKS}/{period}", headers=admin)).json()
    assert month["mode"] == "simulated", month
    assert month["issuer"]["name"]
    annexes = {annex["key"]: annex for annex in month["annexes"]}
    assert annexes["anexo2"]["file_name"] == f"F07_anexo2_{period}_SIMULADO.csv"
    codes = [row[7] for row in annexes["anexo2"]["rows"]]
    assert invoice["generation_code"].replace("-", "").upper() in codes
    assert any(
        line["first_control"] == invoice["control_number"]
        or line["last_control"] == invoice["control_number"]
        for line in month["consumer_book"]
    )
    assert [p["id"] for p in month["pending_purchases"]] == [str(purchase_id)]
    assert month["purchase_book"] == []

    detail = (await e2e_client.get(f"{BOOKS}/purchases/{purchase_id}", headers=admin)).json()
    assert detail["recorded"] is None
    assert detail["taxed"] in ("100.00", "100", 100)
    payload = {
        "issued_on": day.isoformat(),
        "document_class": 1,
        "document_type": "03",
        "number": "145501",
        "supplier_name": "Molinos de El Salvador, S.A. de C.V.",
        "supplier_id_type": "nit",
        "supplier_id": "0614-241090-102-2",
        "renta": detail["renta_defaults"],
    }
    wrong = await e2e_client.put(
        f"{BOOKS}/purchases/{purchase_id}",
        json={**payload, "document_class": 3},
        headers=admin,
    )
    assert wrong.status_code == 422
    assert wrong.json()["code"] == "fiscal_purchase_document_invalid"
    saved = await e2e_client.put(f"{BOOKS}/purchases/{purchase_id}", json=payload, headers=admin)
    assert saved.status_code == 200, saved.text
    assert saved.json()["recorded"]["supplier_id"] == "06142410901022"

    month = (await e2e_client.get(f"{BOOKS}/{period}", headers=admin)).json()
    assert month["pending_purchases"] == []
    [line] = month["purchase_book"]
    assert line["document_number"] == "145501"
    annexes = {annex["key"]: annex for annex in month["annexes"]}
    [row] = annexes["anexo3"]["rows"]
    assert row[3:5] == ["145501", "06142410901022"]
    assert row[9] == "100.00"
    assert row[13:15] == ["13.00", "100.00"]
    assert float(month["summary"]["credit"]) == pytest.approx(13)

    defaults = {"operation": 1, "classification": 2, "sector": 4, "cost_type": 2}
    changed = await e2e_client.put(f"{BOOKS}/settings", json=defaults, headers=admin)
    assert changed.status_code == 200, changed.text
    assert (await e2e_client.get(f"{BOOKS}/settings", headers=admin)).json() == defaults
    bad = await e2e_client.put(f"{BOOKS}/settings", json={**defaults, "sector": 7}, headers=admin)
    assert bad.status_code == 422
    assert bad.json()["code"] == "fiscal_purchase_renta_invalid"

    assert (await e2e_client.get(f"{BOOKS}/2026-13", headers=admin)).status_code == 422

    workbook = await e2e_client.get(f"{BOOKS}/{period}/xlsx", headers=admin)
    assert workbook.status_code == 200
    assert workbook.content[:2] == b"PK"
    assert f"F07_libros_{period}_SIMULADO.xlsx" in workbook.headers["content-disposition"]
    pdf = await e2e_client.get(
        f"{BOOKS}/{period}/pdf", params={"book": "purchases", "first_folio": 7}, headers=admin
    )
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"
    archive = await e2e_client.get(f"{BOOKS}/{period}/f07.zip", headers=admin)
    assert archive.status_code == 200
    names = zipfile.ZipFile(BytesIO(archive.content)).namelist()
    assert f"F07_anexo3_{period}_SIMULADO.csv" in names
    assert "LEEME.txt" in names
