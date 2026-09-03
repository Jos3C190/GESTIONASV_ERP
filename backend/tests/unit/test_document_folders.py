from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.application.documents import DocumentRecordService
from app.domain.entities.document_folder import DocumentFolder


class RecordingFolders:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def list_folders(self, company_id: uuid.UUID, **kwargs: object):
        self.calls.append({"company_id": company_id, **kwargs})
        return (
            [
                DocumentFolder(
                    id="employees",
                    kind="module",
                    name="Empleados",
                    module="employees",
                    parent_id=None,
                    document_count=4,
                    active_count=3,
                    latest_document_at=datetime(2026, 9, 2, tzinfo=UTC),
                )
            ],
            1,
        )


@pytest.mark.asyncio
async def test_folder_service_forwards_tenant_scope_and_filters() -> None:
    records = RecordingFolders()
    service = DocumentRecordService(
        documents=object(), records=records, employees=object(), audit=object()
    )
    company_id = uuid.uuid4()
    employee_id = uuid.uuid4()
    branch_id = uuid.uuid4()

    folders, total = await service.list_folders(
        company_id,
        parent="employee",
        employee_id=employee_id,
        page=2,
        size=24,
        search="contrato",
        branch_id=branch_id,
        include_restricted=False,
        allowed_modules={"employees"},
        upload_modules={"employees"},
    )

    assert total == 1
    assert folders[0].id == "employees"
    assert records.calls == [
        {
            "company_id": company_id,
            "parent": "employee",
            "employee_id": employee_id,
            "page": 2,
            "size": 24,
            "search": "contrato",
            "branch_id": branch_id,
            "include_restricted": False,
            "allowed_modules": {"employees"},
            "upload_modules": {"employees"},
        }
    ]


@pytest.mark.asyncio
async def test_folder_service_keeps_explicit_empty_module_allowlist_empty() -> None:
    records = RecordingFolders()
    service = DocumentRecordService(
        documents=object(), records=records, employees=object(), audit=object()
    )

    await service.list_folders(
        uuid.uuid4(),
        parent="root",
        page=1,
        size=24,
        allowed_modules=set(),
        upload_modules=set(),
    )

    assert records.calls[0]["allowed_modules"] == set()
    assert records.calls[0]["upload_modules"] == set()
