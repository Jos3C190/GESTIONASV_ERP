"""B06 real API flow: quotes convert to sales without touching inventory."""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"


async def _login(client, username: str, password: str, company_id: uuid.UUID) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"login": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {
        "Authorization": f"Bearer {response.json()['access_token']}",
        "X-Company-ID": str(company_id),
    }


async def _inventory_fingerprint() -> dict[str, tuple[int, str]]:
    from app.infrastructure.db.session import async_session_factory

    tables = (
        "inventory_items",
        "inventory_handling_units",
        "inventory_balances",
        "inventory_capacity_reservations",
        "inventory_movements",
        "inventory_movement_lines",
        "inventory_cost_averages",
        "inventory_valuation_entries",
    )
    result: dict[str, tuple[int, str]] = {}
    async with async_session_factory() as session:
        for table in tables:
            count = int((await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one())
            digest = str(
                (
                    await session.execute(
                        text(
                            f"SELECT md5(COALESCE(string_agg(to_jsonb(row_data)::text, E'\\n' "
                            f"ORDER BY to_jsonb(row_data)::text), '')) FROM {table} AS row_data"
                        )
                    )
                ).scalar_one()
            )
            result[table] = (count, digest)
    return result


async def _conversion_artifact_counts(
    company_id: uuid.UUID, quotation_id: uuid.UUID, idempotency_key: str
) -> tuple[int, int, int]:
    """Count sale, idempotency, and conversion audit writes for a quote/key."""
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.audit import AuditLog
    from app.infrastructure.models.sales import SaleModel, SalesIdempotencyModel

    async with async_session_factory() as session:
        sale_count = int(
            await session.scalar(
                select(func.count(SaleModel.id)).where(
                    SaleModel.company_id == company_id,
                    SaleModel.quotation_id == quotation_id,
                )
            )
            or 0
        )
        idempotency_count = int(
            await session.scalar(
                select(func.count(SalesIdempotencyModel.id)).where(
                    SalesIdempotencyModel.company_id == company_id,
                    SalesIdempotencyModel.action == "convert_quote",
                    SalesIdempotencyModel.idempotency_key == idempotency_key,
                )
            )
            or 0
        )
        audit_count = int(
            await session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.company_id == company_id,
                    AuditLog.resource_id == str(quotation_id),
                    AuditLog.action == "SALES_QUOTATION_CONVERTED",
                )
            )
            or 0
        )
        return sale_count, idempotency_count, audit_count


async def _make_branch_scoped_reader(
    company_id: uuid.UUID, branch_id: uuid.UUID
) -> tuple[str, str]:
    """Create a real non-superuser with sales read access to one branch only."""
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.organization import UserBranch, UserCompany
    from app.infrastructure.models.rbac import Permission, Role, RolePermission, UserRole

    username = f"sales-reader-{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.test"
    user_id = uuid.UUID(
        await seed_user(username=username, email=email, password=PASSWORD, is_superuser=False)
    )
    async with async_session_factory() as session:
        membership = await session.get(UserCompany, (user_id, company_id))
        assert membership is not None
        membership.access_all_branches = False
        session.add(
            UserBranch(
                user_id=user_id,
                company_id=company_id,
                branch_id=branch_id,
                assigned_by=user_id,
                is_default=True,
                is_active=True,
            )
        )
        role = Role(company_id=company_id, name=f"B06_READ_{uuid.uuid4().hex[:8]}")
        session.add(role)
        await session.flush()
        permissions = list(
            (
                await session.scalars(
                    select(Permission).where(
                        Permission.code.in_(["sales_quotations:read", "sales_customers:read"]),
                        Permission.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        assert len(permissions) == 2
        for permission in permissions:
            session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        session.add(UserRole(user_id=user_id, company_id=company_id, role_id=role.id))
        await session.commit()
    return username, email


async def test_sales_quote_conversion_is_idempotent_scoped_and_inventory_neutral(
    e2e_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import datetime

    from app.application.sales.service import SalesService
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
    from app.infrastructure.models.inventory import InventoryItemModel
    from app.infrastructure.models.organization import Branch
    from app.infrastructure.models.sales import SalesQuotationModel

    company_id = await get_test_company_id()
    admin_username = f"sales-admin-{uuid.uuid4().hex[:8]}"
    admin_email = f"{admin_username}@example.test"
    await seed_user(
        username=admin_username, email=admin_email, password=PASSWORD, is_superuser=True
    )
    admin_headers = await _login(e2e_client, admin_username, PASSWORD, company_id)

    async with async_session_factory() as session:
        branches = list(
            (
                await session.scalars(
                    select(Branch)
                    .where(
                        Branch.company_id == company_id,
                        Branch.is_active.is_(True),
                        Branch.deleted_at.is_(None),
                        Branch.operational_status == "active",
                    )
                    .order_by(Branch.code)
                    .limit(2)
                )
            ).all()
        )
    assert len(branches) == 2, "La semilla de integración debe contener varias sucursales activas."
    branch_a, branch_b = branches

    # The canonical API seed has commercial products but intentionally no
    # stock identities. Prepare one catalog identity in this isolated test DB.
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
        assert product is not None, "La semilla debe tener un producto independiente y vendible."
        inventory_item = await session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.product_id == product.id_product,
                InventoryItemModel.is_active.is_(True),
            )
        )
        if inventory_item is None:
            session.add(
                InventoryItemModel(
                    company_id=company_id,
                    product_id=product.id_product,
                    base_unit_id=product.sale_unit,
                    is_active=True,
                )
            )
            await session.commit()

    catalog_response = await e2e_client.get("/api/v1/sales/catalog", headers=admin_headers)
    assert catalog_response.status_code == 200, catalog_response.text
    catalog = catalog_response.json()
    assert catalog, "La semilla debe incluir al menos un artículo vendible e inventariable."
    item = catalog[0]
    unit_id = item["units"][0]["unit_id"]

    created_customer = await e2e_client.post(
        "/api/v1/sales/customers",
        headers=admin_headers,
        json={"code": f"CLI-{uuid.uuid4().hex[:8].upper()}", "name": "Cliente B06 de prueba"},
    )
    assert created_customer.status_code == 201, created_customer.text
    customer_id = created_customer.json()["id"]

    local_today = datetime.now(ZoneInfo("America/El_Salvador")).date()
    valid_until = (local_today + timedelta(days=2)).isoformat()
    body = {
        "branch_id": str(branch_a.id),
        "customer_id": customer_id,
        "valid_until": valid_until,
        "currency": "USD",
        "notes": "Validación automatizada B06",
        "subtotal": 0,
        "total": 0,
        "lines": [
            {
                "product_id": item["product_id"],
                "variant_id": item["variant_id"],
                "unit_id": unit_id,
                "quantity": "3",
                "unit_price": "1.255",
            }
        ],
    }

    unsupported_currency = await e2e_client.post(
        "/api/v1/sales/quotations",
        headers={**admin_headers, "Idempotency-Key": f"b06-currency-{uuid.uuid4()}"},
        json={**body, "currency": "EUR"},
    )
    assert unsupported_currency.status_code == 422
    unsupported_unit = await e2e_client.post(
        "/api/v1/sales/quotations",
        headers={**admin_headers, "Idempotency-Key": f"b06-unit-{uuid.uuid4()}"},
        json={**body, "lines": [{**body["lines"][0], "unit_id": 99999999}]},
    )
    assert unsupported_unit.status_code == 422

    before = await _inventory_fingerprint()
    create_key = f"b06-quote-{uuid.uuid4()}"
    created = await e2e_client.post(
        "/api/v1/sales/quotations",
        headers={**admin_headers, "Idempotency-Key": create_key},
        json=body,
    )
    assert created.status_code == 201, created.text
    quote = created.json()
    assert quote["subtotal"] == "3.77"
    assert quote["total"] == "3.77"
    assert quote["lines"][0]["quantity_delivered_base"] == "0.000000"
    assert quote["lines"][0]["quantity_pending_base"] == quote["lines"][0]["quantity_base"]
    assert not ({"unit_cost", "average_unit_cost", "inventory_value", "margin"} & quote.keys())

    replay_quote = await e2e_client.post(
        "/api/v1/sales/quotations",
        headers={**admin_headers, "Idempotency-Key": create_key},
        json=body,
    )
    assert replay_quote.status_code == 201, replay_quote.text
    assert replay_quote.json()["id"] == quote["id"]
    conflicting_replay = await e2e_client.post(
        "/api/v1/sales/quotations",
        headers={**admin_headers, "Idempotency-Key": create_key},
        json={**body, "notes": "Mismo token con otro contenido"},
    )
    assert conflicting_replay.status_code == 409

    confirmed_quote = await e2e_client.post(
        f"/api/v1/sales/quotations/{quote['id']}/confirm",
        headers=admin_headers,
        json={"expected_version": quote["version"]},
    )
    assert confirmed_quote.status_code == 200, confirmed_quote.text
    quote = confirmed_quote.json()
    assert quote["status"] == "confirmed"
    confirmed_quote_edit = await e2e_client.put(
        f"/api/v1/sales/quotations/{quote['id']}",
        headers=admin_headers,
        json={
            "expected_version": quote["version"],
            "valid_until": valid_until,
            "currency": "USD",
            "notes": quote["notes"],
            "lines": body["lines"],
        },
    )
    assert confirmed_quote_edit.status_code == 422

    # Product and packaging names are copied into quote lines. Renaming the
    # catalogue after confirmation must not rewrite the commercial snapshot.
    original_product_name = quote["lines"][0]["product_name"]
    async with async_session_factory() as session:
        stored_product = await session.scalar(
            select(ProductModel).where(
                ProductModel.company_id == company_id,
                ProductModel.id_product == item["product_id"],
            )
        )
        assert stored_product is not None
        stored_product.sales_name = f"B06 nombre cambiado {uuid.uuid4().hex[:8]}"
        await session.commit()
    quote_after_catalog_change = await e2e_client.get(
        f"/api/v1/sales/quotations/{quote['id']}", headers=admin_headers
    )
    assert quote_after_catalog_change.status_code == 200, quote_after_catalog_change.text
    assert quote_after_catalog_change.json()["lines"][0]["product_name"] == original_product_name

    # Confirmation and draft editing use the same expected version. Exactly
    # one transition may win; the losing request must reload instead of
    # silently overwriting the confirmed revision.
    race_edit_quote_response = await e2e_client.post(
        "/api/v1/sales/quotations",
        headers={**admin_headers, "Idempotency-Key": f"b06-confirm-edit-{uuid.uuid4()}"},
        json=body,
    )
    assert race_edit_quote_response.status_code == 201, race_edit_quote_response.text
    race_edit_quote = race_edit_quote_response.json()
    race_edit_confirmation, race_edit_update = await asyncio.gather(
        e2e_client.post(
            f"/api/v1/sales/quotations/{race_edit_quote['id']}/confirm",
            headers=admin_headers,
            json={"expected_version": race_edit_quote["version"]},
        ),
        e2e_client.put(
            f"/api/v1/sales/quotations/{race_edit_quote['id']}",
            headers=admin_headers,
            json={
                "expected_version": race_edit_quote["version"],
                "valid_until": valid_until,
                "currency": "USD",
                "notes": "Edición concurrente B06",
                "lines": body["lines"],
            },
        ),
    )
    assert (race_edit_confirmation.status_code, race_edit_update.status_code) in {
        (200, 422),
        (409, 200),
    }, (race_edit_confirmation.text, race_edit_update.text)
    final_race_quote = await e2e_client.get(
        f"/api/v1/sales/quotations/{race_edit_quote['id']}", headers=admin_headers
    )
    assert final_race_quote.status_code == 200, final_race_quote.text
    if final_race_quote.json()["status"] == "draft":
        final_race_confirmation = await e2e_client.post(
            f"/api/v1/sales/quotations/{race_edit_quote['id']}/confirm",
            headers=admin_headers,
            json={"expected_version": final_race_quote.json()["version"]},
        )
        assert final_race_confirmation.status_code == 200, final_race_confirmation.text

    # Inject a failure after the sale, lines, idempotency record, and first
    # conversion audit event have been flushed. The savepoint must remove all
    # of them so the same request can safely be retried.
    from app.application.sales import service as sales_service_module

    original_audit = SalesService._audit

    async def fail_late_audit(self, **kwargs):
        if kwargs.get("action") == "SALES_DRAFT_CREATED_FROM_QUOTATION":
            raise RuntimeError("B06 injected late audit failure")
        await original_audit(self, **kwargs)

    late_audit_key = f"b06-late-audit-{uuid.uuid4()}"
    with monkeypatch.context() as patcher:
        patcher.setattr(SalesService, "_audit", fail_late_audit)
        with pytest.raises(RuntimeError, match="B06 injected late audit failure"):
            await e2e_client.post(
                f"/api/v1/sales/quotations/{quote['id']}/convert",
                headers={**admin_headers, "Idempotency-Key": late_audit_key},
                json={"expected_version": quote["version"]},
            )
    assert await _conversion_artifact_counts(
        company_id, uuid.UUID(quote["id"]), late_audit_key
    ) == (0, 0, 0)

    # Exercise a database failure on the second copied line after the first
    # line and sale header have been sent to PostgreSQL.
    two_line_body = {
        **body,
        "notes": "Prueba de rollback en segunda línea B06",
        "lines": [body["lines"][0], {**body["lines"][0], "quantity": "2"}],
    }
    two_line_quote_response = await e2e_client.post(
        "/api/v1/sales/quotations",
        headers={**admin_headers, "Idempotency-Key": f"b06-two-line-{uuid.uuid4()}"},
        json=two_line_body,
    )
    assert two_line_quote_response.status_code == 201, two_line_quote_response.text
    two_line_quote = two_line_quote_response.json()
    two_line_confirmation = await e2e_client.post(
        f"/api/v1/sales/quotations/{two_line_quote['id']}/confirm",
        headers=admin_headers,
        json={"expected_version": two_line_quote["version"]},
    )
    assert two_line_confirmation.status_code == 200, two_line_confirmation.text
    two_line_quote = two_line_confirmation.json()
    real_sale_line_model = sales_service_module.SaleLineModel

    def invalid_second_line(**kwargs):
        line = real_sale_line_model(**kwargs)
        if line.line_number == 2:
            line.quantity_base = Decimal("0")
        return line

    second_line_failure_key = f"b06-second-line-{uuid.uuid4()}"
    with monkeypatch.context() as patcher:
        patcher.setattr(sales_service_module, "SaleLineModel", invalid_second_line)
        with pytest.raises(IntegrityError):
            await e2e_client.post(
                f"/api/v1/sales/quotations/{two_line_quote['id']}/convert",
                headers={**admin_headers, "Idempotency-Key": second_line_failure_key},
                json={"expected_version": two_line_quote["version"]},
            )
    assert await _conversion_artifact_counts(
        company_id, uuid.UUID(two_line_quote["id"]), second_line_failure_key
    ) == (0, 0, 0)
    second_line_retry = await e2e_client.post(
        f"/api/v1/sales/quotations/{two_line_quote['id']}/convert",
        headers={**admin_headers, "Idempotency-Key": second_line_failure_key},
        json={"expected_version": two_line_quote["version"]},
    )
    assert second_line_retry.status_code == 200, second_line_retry.text
    assert len(second_line_retry.json()["lines"]) == 2

    convert_key = f"b06-convert-{uuid.uuid4()}"
    concurrent_results = await asyncio.gather(
        *(
            e2e_client.post(
                f"/api/v1/sales/quotations/{quote['id']}/convert",
                headers={**admin_headers, "Idempotency-Key": key},
                json={"expected_version": quote["version"]},
            )
            for key in (convert_key, f"b06-convert-race-{uuid.uuid4()}")
        )
    )
    assert all(response.status_code == 200 for response in concurrent_results), [
        response.text for response in concurrent_results
    ]
    sale = concurrent_results[0].json()
    assert concurrent_results[1].json()["id"] == sale["id"]
    assert sale["quotation_id"] == quote["id"]
    assert sale["lines"][0]["product_name"] == original_product_name
    assert sale["delivery_progress"] == "pending"
    assert sale["lines"][0]["quantity_delivered_base"] == "0.000000"
    assert sale["lines"][0]["quantity_pending_base"] == sale["lines"][0]["quantity_base"]

    edited_sale = await e2e_client.put(
        f"/api/v1/sales/{sale['id']}",
        headers=admin_headers,
        json={
            "expected_version": sale["version"],
            "notes": "Precio comercial revisado en borrador",
            "lines": [
                {
                    "source_quotation_line_id": sale["lines"][0]["source_quotation_line_id"],
                    "quantity": "3",
                    "unit_price": "2.00",
                }
            ],
        },
    )
    assert edited_sale.status_code == 200, edited_sale.text
    sale = edited_sale.json()
    assert sale["total"] == "6.00"
    assert sale["delivery_progress"] == "pending"

    replay_sale = await e2e_client.post(
        f"/api/v1/sales/quotations/{quote['id']}/convert",
        headers={**admin_headers, "Idempotency-Key": convert_key},
        json={"expected_version": quote["version"]},
    )
    assert replay_sale.status_code == 200, replay_sale.text
    assert replay_sale.json()["id"] == sale["id"]
    new_key_sale = await e2e_client.post(
        f"/api/v1/sales/quotations/{quote['id']}/convert",
        headers={**admin_headers, "Idempotency-Key": f"b06-convert-retry-{uuid.uuid4()}"},
        json={"expected_version": quote["version"]},
    )
    assert new_key_sale.status_code == 200, new_key_sale.text
    assert new_key_sale.json()["id"] == sale["id"]

    confirmed_sale = await e2e_client.post(
        f"/api/v1/sales/{sale['id']}/confirm",
        headers=admin_headers,
        json={"expected_version": sale["version"]},
    )
    assert confirmed_sale.status_code == 200, confirmed_sale.text
    sale = confirmed_sale.json()
    assert sale["status"] == "confirmed"
    assert sale["delivery_progress"] == "pending"
    confirmed_sale_edit = await e2e_client.put(
        f"/api/v1/sales/{sale['id']}",
        headers=admin_headers,
        json={
            "expected_version": sale["version"],
            "notes": sale["notes"],
            "lines": [
                {
                    "source_quotation_line_id": sale["lines"][0]["source_quotation_line_id"],
                    "quantity": sale["lines"][0]["quantity"],
                    "unit_price": sale["lines"][0]["unit_price"],
                }
            ],
        },
    )
    assert confirmed_sale_edit.status_code == 422

    cancelled_sale = await e2e_client.post(
        f"/api/v1/sales/{sale['id']}/cancel",
        headers=admin_headers,
        json={"expected_version": sale["version"], "reason": "Prueba B06 sin entrega"},
    )
    assert cancelled_sale.status_code == 200, cancelled_sale.text
    assert cancelled_sale.json()["status"] == "cancelled"

    # A second company context cannot use the existing document identifier.
    unknown_company = uuid.uuid4()
    cross_company = await e2e_client.get(
        f"/api/v1/sales/quotations/{quote['id']}",
        headers={**admin_headers, "X-Company-ID": str(unknown_company)},
    )
    assert cross_company.status_code in {403, 404}

    # A user with read permission for one branch cannot query another branch or its document.
    _, reader_email = await _make_branch_scoped_reader(company_id, branch_a.id)
    reader_headers = await _login(e2e_client, reader_email, PASSWORD, company_id)
    permitted_list = await e2e_client.get(
        f"/api/v1/sales/quotations?branch_id={branch_a.id}", headers=reader_headers
    )
    assert permitted_list.status_code == 200, permitted_list.text
    denied_list = await e2e_client.get(
        f"/api/v1/sales/quotations?branch_id={branch_b.id}", headers=reader_headers
    )
    assert denied_list.status_code == 403
    allowed_detail = await e2e_client.get(
        f"/api/v1/sales/quotations/{quote['id']}", headers=reader_headers
    )
    assert allowed_detail.status_code == 200, allowed_detail.text
    denied_conversion_replay = await e2e_client.post(
        f"/api/v1/sales/quotations/{quote['id']}/convert",
        headers={**reader_headers, "Idempotency-Key": convert_key},
        json={"expected_version": quote["version"]},
    )
    assert denied_conversion_replay.status_code == 403

    branch_b_quote = await e2e_client.post(
        "/api/v1/sales/quotations",
        headers={**admin_headers, "Idempotency-Key": f"b06-branch-b-{uuid.uuid4()}"},
        json={**body, "branch_id": str(branch_b.id)},
    )
    assert branch_b_quote.status_code == 201, branch_b_quote.text
    async with async_session_factory() as session:
        expired_row = await session.get(SalesQuotationModel, uuid.UUID(branch_b_quote.json()["id"]))
        assert expired_row is not None
        expired_row.quotation_date = local_today - timedelta(days=2)
        expired_row.valid_until = local_today - timedelta(days=1)
        await session.commit()
    expired_quote = await e2e_client.get(
        f"/api/v1/sales/quotations/{branch_b_quote.json()['id']}", headers=admin_headers
    )
    assert expired_quote.status_code == 200, expired_quote.text
    assert expired_quote.json()["status"] == "expired"
    expired_confirmation = await e2e_client.post(
        f"/api/v1/sales/quotations/{branch_b_quote.json()['id']}/confirm",
        headers=admin_headers,
        json={"expected_version": expired_quote.json()["version"]},
    )
    assert expired_confirmation.status_code == 422
    denied_detail = await e2e_client.get(
        f"/api/v1/sales/quotations/{branch_b_quote.json()['id']}", headers=reader_headers
    )
    assert denied_detail.status_code == 403

    cancelled_quote = await e2e_client.post(
        "/api/v1/sales/quotations",
        headers={**admin_headers, "Idempotency-Key": f"b06-cancel-quote-{uuid.uuid4()}"},
        json=body,
    )
    assert cancelled_quote.status_code == 201, cancelled_quote.text
    quote_cancellation = await e2e_client.post(
        f"/api/v1/sales/quotations/{cancelled_quote.json()['id']}/cancel",
        headers=admin_headers,
        json={"expected_version": cancelled_quote.json()["version"], "reason": "Prueba comercial"},
    )
    assert quote_cancellation.status_code == 200, quote_cancellation.text
    assert quote_cancellation.json()["status"] == "cancelled"

    race_quote = await e2e_client.post(
        "/api/v1/sales/quotations",
        headers={**admin_headers, "Idempotency-Key": f"b06-race-quote-{uuid.uuid4()}"},
        json=body,
    )
    assert race_quote.status_code == 201, race_quote.text
    race_confirm = await e2e_client.post(
        f"/api/v1/sales/quotations/{race_quote.json()['id']}/confirm",
        headers=admin_headers,
        json={"expected_version": race_quote.json()["version"]},
    )
    assert race_confirm.status_code == 200, race_confirm.text
    race_version = race_confirm.json()["version"]
    race_results = await asyncio.gather(
        e2e_client.post(
            f"/api/v1/sales/quotations/{race_quote.json()['id']}/cancel",
            headers=admin_headers,
            json={"expected_version": race_version, "reason": "Carrera B06"},
        ),
        e2e_client.post(
            f"/api/v1/sales/quotations/{race_quote.json()['id']}/convert",
            headers={**admin_headers, "Idempotency-Key": f"b06-race-convert-{uuid.uuid4()}"},
            json={"expected_version": race_version},
        ),
    )
    assert sum(response.status_code == 200 for response in race_results) == 1
    loser = next(response for response in race_results if response.status_code != 200)
    # Cancellation can win before conversion acquires the lock, in which case
    # conversion must see the new version. If conversion wins, cancellation
    # rejects the already converted quotation.
    assert (loser.status_code, loser.json()["code"]) in {
        (409, "sales_quote_version_conflict"),
        (422, "sales_quote_converted"),
    }

    deactivated_customer = await e2e_client.patch(
        f"/api/v1/sales/customers/{customer_id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert deactivated_customer.status_code == 200, deactivated_customer.text
    assert deactivated_customer.json()["is_active"] is False
    historical_quote = await e2e_client.get(
        f"/api/v1/sales/quotations/{quote['id']}", headers=admin_headers
    )
    assert historical_quote.status_code == 200, historical_quote.text
    inactive_customer_quote = await e2e_client.post(
        "/api/v1/sales/quotations",
        headers={**admin_headers, "Idempotency-Key": f"b06-inactive-customer-{uuid.uuid4()}"},
        json={**body, "branch_id": str(branch_a.id)},
    )
    assert inactive_customer_quote.status_code == 422
    after = await _inventory_fingerprint()
    assert after == before, (
        "Las operaciones comerciales no deben alterar ningún registro físico o de valoración."
    )

    no_permission_username = f"no-sales-{uuid.uuid4().hex[:8]}"
    no_permission_email = f"{no_permission_username}@example.test"
    await seed_user(username=no_permission_username, email=no_permission_email, password=PASSWORD)
    no_permission_headers = await _login(e2e_client, no_permission_email, PASSWORD, company_id)
    denied = await e2e_client.get("/api/v1/sales/customers", headers=no_permission_headers)
    assert denied.status_code == 403
