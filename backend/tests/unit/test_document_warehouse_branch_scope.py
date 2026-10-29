"""A purchase's warehouse remains the source of branch scope for legacy rows."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from app.api.v1 import company_access
from fastapi import HTTPException


class _Result:
    def __init__(self, row: object | None) -> None:
        self._row = row

    def one_or_none(self) -> object | None:
        return self._row


class _Session:
    def __init__(self, row: object | None) -> None:
        self.row = row

    async def execute(self, _statement: object) -> _Result:
        return _Result(self.row)


def _warehouse_row(
    branch_id: uuid.UUID,
    *,
    is_central: bool = True,
    is_headquarters: bool = True,
    is_active: bool = True,
    operational_status: str = "active",
    deleted_at: object | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        branch_id=branch_id,
        is_central=is_central,
        is_headquarters=is_headquarters,
        is_active=is_active,
        operational_status=operational_status,
        deleted_at=deleted_at,
    )


@pytest.mark.asyncio
async def test_legacy_null_branch_uses_the_central_warehouse_headquarters(monkeypatch) -> None:
    company_id = uuid.uuid4()
    headquarters_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    authorizations: list[uuid.UUID | None] = []

    async def authorize(_session, _user, _company_id, branch_id):
        authorizations.append(branch_id)

    monkeypatch.setattr(company_access, "resolve_branch_scope", authorize)

    actual_branch = await company_access.resolve_document_warehouse_scope(
        _Session(_warehouse_row(headquarters_id)),
        current=object(),
        company_id=company_id,
        document_branch_id=None,
        warehouse_id=warehouse_id,
    )

    assert actual_branch == headquarters_id
    assert authorizations == [headquarters_id]


@pytest.mark.asyncio
async def test_document_and_warehouse_branch_mismatch_fails_closed(monkeypatch) -> None:
    company_id = uuid.uuid4()
    warehouse_branch_id = uuid.uuid4()
    other_document_branch_id = uuid.uuid4()

    async def authorize(*_args):
        pytest.fail("No debe autorizar un documento con asignación inconsistente")

    monkeypatch.setattr(company_access, "resolve_branch_scope", authorize)

    with pytest.raises(HTTPException) as error:
        await company_access.resolve_document_warehouse_scope(
            _Session(_warehouse_row(warehouse_branch_id, is_central=False)),
            current=object(),
            company_id=company_id,
            document_branch_id=other_document_branch_id,
            warehouse_id=uuid.uuid4(),
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_central_warehouse_requires_an_active_headquarters(monkeypatch) -> None:
    async def authorize(*_args):
        pytest.fail("La matriz inválida no debe llegar a autorización")

    monkeypatch.setattr(company_access, "resolve_branch_scope", authorize)

    with pytest.raises(HTTPException) as error:
        await company_access.resolve_document_warehouse_scope(
            _Session(_warehouse_row(uuid.uuid4(), is_headquarters=False)),
            current=object(),
            company_id=uuid.uuid4(),
            document_branch_id=None,
            warehouse_id=uuid.uuid4(),
        )

    assert error.value.status_code == 409
