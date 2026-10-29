"""HTTP acceptance checks for adjustment financial evidence permissions."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.application.documents import DocumentService
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.inventory_adjustment import (
    InventoryAdjustmentDocumentModel,
)
from app.infrastructure.models.organization import Company, UserBranch
from app.infrastructure.models.user import User
from app.infrastructure.repositories.inventory_adjustment_repository import (
    SqlAlchemyInventoryAdjustmentRepository,
)
from sqlalchemy import select

from tests.e2e.test_inventory_block4_closure import _branch_profile_headers
from tests.e2e.test_purchase_orders import _headers
from tests.integration.test_inventory_transfer_repository import _create_context

pytestmark = pytest.mark.e2e


async def test_adjustment_evidence_download_requires_valuation_permission(
    e2e_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    suffix = uuid.uuid4().hex
    async with async_session_factory() as session:
        context = await _create_context(session, suffix)
        session.add(
            Employee(
                company_id=context.company_id,
                employee_code=f"ADJ-{suffix[:12].upper()}",
                first_name=f"Ajuste {suffix[:8]}",
                last_name="Prueba",
                user_id=context.actor_id,
                status="activo",
            )
        )
        company_id = context.company_id
        warehouse_id = context.origin.id
        location_id = context.source_location.id
        branch_id = context.origin.branch_id
        item_id = context.item.id
        await session.commit()

    admin_username = f"adjustment-evidence-admin-{suffix[:10]}"
    admin_headers = await _headers(
        e2e_client,
        company_id=company_id,
        username=admin_username,
        is_superuser=True,
    )
    async with async_session_factory() as session:
        admin_id = await session.scalar(select(User.id).where(User.username == admin_username))
        assert admin_id is not None
        adjustment = await SqlAlchemyInventoryAdjustmentRepository(session).create_adjustment(
            company_id=company_id,
            actor_id=admin_id,
            warehouse_id=warehouse_id,
            operational_date=date(2026, 10, 20),
            accounting_date=date(2026, 10, 20),
            reason="Ajuste ficticio para revisar el permiso del comprobante.",
            document_reference=f"ACTA-ERS-P01-{suffix[:10].upper()}",
            notes="Caso aislado; no toca el inventario de demostración.",
            idempotency_key=f"ers-p01-adjustment-{suffix}",
            lines=[
                {
                    "inventory_item_id": item_id,
                    "location_id": location_id,
                    "direction": "increase",
                    "quantity_base": Decimal("1"),
                    "stock_status": "quarantine",
                    "documented_unit_cost": Decimal("9.25"),
                    "documented_total_cost": Decimal("9.25"),
                    "actual_gross_weight_kg": None,
                    "actual_volume_m3": None,
                }
            ],
        )

        now = datetime.now(UTC)
        checksum = f"{suffix[:1]}" * 64
        document = DocumentAssetModel(
            company_id=company_id,
            original_filename=f"support-{suffix[:12]}.pdf",
            extension="pdf",
            declared_content_type="application/pdf",
            detected_content_type="application/pdf",
            size_bytes=512,
            checksum_sha256=checksum,
            bucket="adjustment-test",
            object_key=f"adjustments/{suffix}.pdf",
            status="active",
            upload_expires_at=now + timedelta(hours=1),
            scanned_at=now,
            uploaded_by=admin_id,
        )
        session.add(document)
        await session.flush()
        link = InventoryAdjustmentDocumentModel(
            company_id=company_id,
            adjustment_id=adjustment["id"],
            document_id=document.id,
            checksum_sha256=checksum,
            original_filename=document.original_filename,
            linked_by_id=admin_id,
            linked_at=now,
            upload_completed_at=now,
        )
        session.add(link)
        await session.commit()
        adjustment_id = adjustment["id"]
        document_id = document.id

    async def signed_url_stub(
        self: DocumentService,
        requested_company_id: uuid.UUID,
        requested_document_id: uuid.UUID,
        actor_id: uuid.UUID,
        *,
        variant: str = "original",
    ) -> tuple[str, datetime]:
        assert requested_company_id == company_id
        assert requested_document_id == document_id
        return "https://files.example.test/ers-p01-placeholder", datetime.now(UTC) + timedelta(
            minutes=1
        )

    monkeypatch.setattr(DocumentService, "download_url", signed_url_stub)

    reader_headers = await _branch_profile_headers(
        e2e_client,
        company_id=company_id,
        branch_id=branch_id,
        username=f"adjustment-reader-{suffix[:10]}",
        permissions=("inventory:read",),
    )
    detail = await e2e_client.get(
        f"/api/v1/inventory/adjustments/{adjustment_id}", headers=reader_headers
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["lines"][0]["documented_unit_cost"] is None
    assert detail.json()["lines"][0]["documented_total_cost"] is None

    download_path = (
        f"/api/v1/inventory/adjustments/{adjustment_id}/documents/{document_id}/download"
    )
    denied_download = await e2e_client.get(download_path, headers=reader_headers)
    assert denied_download.status_code == 403, denied_download.text
    assert denied_download.json()["code"] == "forbidden"

    document_payload = {
        "file_name": "soporte-ajuste.pdf",
        "content_type": "application/pdf",
        "size_bytes": 512,
        "checksum_sha256": "a" * 64,
    }
    denied_initiate = await e2e_client.post(
        f"/api/v1/inventory/adjustments/{adjustment_id}/documents",
        headers=reader_headers,
        json=document_payload,
    )
    assert denied_initiate.status_code == 403, denied_initiate.text
    denied_complete = await e2e_client.post(
        f"/api/v1/inventory/adjustments/{adjustment_id}/documents/{document_id}/complete",
        headers=reader_headers,
    )
    assert denied_complete.status_code == 403, denied_complete.text
    denied_detach = await e2e_client.delete(
        f"/api/v1/inventory/adjustments/{adjustment_id}/documents/{document_id}",
        headers=reader_headers,
    )
    assert denied_detach.status_code == 403, denied_detach.text

    no_read_headers = await _branch_profile_headers(
        e2e_client,
        company_id=company_id,
        branch_id=branch_id,
        username=f"adjustment-no-read-{suffix[:10]}",
        permissions=(),
    )
    no_read_download = await e2e_client.get(download_path, headers=no_read_headers)
    assert no_read_download.status_code == 403, no_read_download.text

    valuation_username = f"adjustment-valuation-reader-{suffix[:10]}"
    valuation_headers = await _branch_profile_headers(
        e2e_client,
        company_id=company_id,
        branch_id=branch_id,
        username=valuation_username,
        permissions=("inventory:read", "inventory:valuation"),
    )
    allowed_download = await e2e_client.get(download_path, headers=valuation_headers)
    assert allowed_download.status_code == 200, allowed_download.text
    assert allowed_download.json()["url"] == "https://files.example.test/ers-p01-placeholder"

    # A different document ID under the same adjustment is not authorized just
    # because the caller can read valuation for this branch.
    unrelated_document_download = await e2e_client.get(
        f"/api/v1/inventory/adjustments/{adjustment_id}/documents/{uuid.uuid4()}/download",
        headers=valuation_headers,
    )
    assert unrelated_document_download.status_code == 404, unrelated_document_download.text

    # Company-wide permission is not enough to cross the adjustment's branch.
    destination_reader_headers = await _branch_profile_headers(
        e2e_client,
        company_id=company_id,
        branch_id=context.destination.branch_id,
        username=f"adjustment-other-branch-{suffix[:10]}",
        permissions=("inventory:read", "inventory:valuation"),
    )
    other_branch_download = await e2e_client.get(
        download_path, headers=destination_reader_headers
    )
    assert other_branch_download.status_code == 403, other_branch_download.text

    async with async_session_factory() as session:
        source_company = await session.get(Company, company_id)
        assert source_company is not None
        foreign_company = Company(
            name=f"Empresa ajena P01 {suffix[:8]}",
            commercial_name=f"Empresa ajena P01 {suffix[:8]}",
            nit=f"TEST-P01-{suffix[:20]}",
            nrc=f"REG-P01-{suffix[:20]}",
            address=source_company.address,
            department_id=source_company.department_id,
            municipality_id=source_company.municipality_id,
            district_id=source_company.district_id,
        )
        session.add(foreign_company)
        await session.flush()
        foreign_company_id = foreign_company.id
        await session.commit()
    cross_company_download = await e2e_client.get(
        download_path,
        headers={**admin_headers, "X-Company-ID": str(foreign_company_id)},
    )
    assert cross_company_download.status_code == 404, cross_company_download.text

    detached = await e2e_client.delete(
        f"/api/v1/inventory/adjustments/{adjustment_id}/documents/{document_id}",
        headers=admin_headers,
    )
    assert detached.status_code == 200, detached.text
    async with async_session_factory() as session:
        persisted_link = await session.scalar(
            select(InventoryAdjustmentDocumentModel).where(
                InventoryAdjustmentDocumentModel.company_id == company_id,
                InventoryAdjustmentDocumentModel.adjustment_id == adjustment_id,
                InventoryAdjustmentDocumentModel.document_id == document_id,
            )
        )
        assert persisted_link is not None
        assert persisted_link.detached_at is not None
    after_detach_download = await e2e_client.get(download_path, headers=valuation_headers)
    assert after_detach_download.status_code == 404, after_detach_download.text

    async with async_session_factory() as session:
        valuation_reader = await session.scalar(
            select(User).where(User.username == valuation_username)
        )
        assert valuation_reader is not None
        branch_grant = await session.scalar(
            select(UserBranch).where(
                UserBranch.user_id == valuation_reader.id,
                UserBranch.company_id == company_id,
                UserBranch.branch_id == branch_id,
            )
        )
        assert branch_grant is not None
        branch_grant.is_active = False
        branch_grant.revoked_at = datetime.now(UTC)
        await session.commit()
    after_access_revoked = await e2e_client.get(download_path, headers=valuation_headers)
    assert after_access_revoked.status_code == 403, after_access_revoked.text
