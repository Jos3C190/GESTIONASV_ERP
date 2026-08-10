"""Unit tests for the enterprise record-lifecycle application service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.application.lifecycle import LifecycleService
from app.core.exceptions import ValidationError
from app.domain.ports.lifecycle_repository import DeletedRecord

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ACTOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
DELETED_AT = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


def deleted_record(*, reason: str = "Registro duplicado") -> DeletedRecord:
    return DeletedRecord(
        resource="products",
        record_id="42",
        label="Cafetera industrial",
        company_id=COMPANY_ID,
        deleted_at=DELETED_AT,
        deleted_by=ACTOR_ID,
        deletion_reason=reason,
    )


class LifecycleRepositoryFake:
    def __init__(self) -> None:
        self.items = [deleted_record()]
        self.total = 1
        self.list_call: dict[str, object] | None = None
        self.delete_call: dict[str, object] | None = None
        self.restore_call: dict[str, object] | None = None

    async def list_deleted(
        self,
        company_id: uuid.UUID,
        *,
        page: int,
        size: int,
        resource: str | None = None,
        search: str | None = None,
        include_global: bool = False,
        include_all_companies: bool = False,
    ) -> tuple[list[DeletedRecord], int]:
        self.list_call = {
            "company_id": company_id,
            "page": page,
            "size": size,
            "resource": resource,
            "search": search,
            "include_global": include_global,
            "include_all_companies": include_all_companies,
        }
        return self.items, self.total

    async def soft_delete(
        self,
        resource: str,
        record_id: str,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
        allow_global: bool = False,
    ) -> DeletedRecord:
        self.delete_call = {
            "resource": resource,
            "record_id": record_id,
            "company_id": company_id,
            "actor_id": actor_id,
            "reason": reason,
            "allow_global": allow_global,
        }
        return deleted_record(reason=reason)

    async def restore(
        self,
        resource: str,
        record_id: str,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        allow_global: bool = False,
    ) -> DeletedRecord:
        self.restore_call = {
            "resource": resource,
            "record_id": record_id,
            "company_id": company_id,
            "actor_id": actor_id,
            "allow_global": allow_global,
        }
        return deleted_record()


async def test_list_deleted_forwards_tenant_filters_and_pagination() -> None:
    repository = LifecycleRepositoryFake()
    service = LifecycleService(repository)

    items, total = await service.list_deleted(
        COMPANY_ID,
        page=3,
        size=25,
        resource="products",
        search="cafetera",
        include_global=True,
    )

    assert items == repository.items
    assert total == 1
    assert repository.list_call == {
        "company_id": COMPANY_ID,
        "page": 3,
        "size": 25,
        "resource": "products",
        "search": "cafetera",
        "include_global": True,
        "include_all_companies": False,
    }


@pytest.mark.parametrize("reason", ["", " ", "ab", "  a  ", "\t\n"])
async def test_delete_rejects_missing_or_too_short_reason(reason: str) -> None:
    repository = LifecycleRepositoryFake()
    service = LifecycleService(repository)

    with pytest.raises(ValidationError) as exc:
        await service.delete(
            "products",
            "42",
            company_id=COMPANY_ID,
            actor_id=ACTOR_ID,
            reason=reason,
        )

    assert exc.value.code == "deletion_reason_required"
    assert repository.delete_call is None


async def test_delete_normalizes_reason_and_preserves_scope() -> None:
    repository = LifecycleRepositoryFake()
    service = LifecycleService(repository)

    result = await service.delete(
        "products",
        "42",
        company_id=COMPANY_ID,
        actor_id=ACTOR_ID,
        reason="  Registro duplicado  ",
        allow_global=True,
    )

    assert result.deletion_reason == "Registro duplicado"
    assert repository.delete_call == {
        "resource": "products",
        "record_id": "42",
        "company_id": COMPANY_ID,
        "actor_id": ACTOR_ID,
        "reason": "Registro duplicado",
        "allow_global": True,
    }


async def test_restore_forwards_actor_tenant_and_global_scope() -> None:
    repository = LifecycleRepositoryFake()
    service = LifecycleService(repository)

    result = await service.restore(
        "products",
        "42",
        company_id=COMPANY_ID,
        actor_id=ACTOR_ID,
        allow_global=True,
    )

    assert result.record_id == "42"
    assert repository.restore_call == {
        "resource": "products",
        "record_id": "42",
        "company_id": COMPANY_ID,
        "actor_id": ACTOR_ID,
        "allow_global": True,
    }
