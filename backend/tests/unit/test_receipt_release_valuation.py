"""Release requires an applied landed cost only when a retaceo exists."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.domain.entities.inventory import InventoryOperationError
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("has_retaceo", "applied", "allowed"),
    [(False, False, True), (True, False, False), (True, True, True)],
)
async def test_release_of_valued_purchase_respects_applicable_retaceo(
    has_retaceo, applied, allowed
):
    source = SimpleNamespace(id=uuid.uuid4(), purchase_detail_id=uuid.uuid4())
    session = AsyncMock()
    session.scalar.side_effect = [
        source,
        uuid.uuid4() if has_retaceo else None,
        uuid.uuid4() if applied else None,
    ]
    row = SimpleNamespace(company_id=uuid.uuid4(), handling_unit_id=uuid.uuid4())
    repository = SqlAlchemyInventoryValuationRepository(session)
    if allowed:
        await repository._ensure_retaceo_applied(row)
    else:
        with pytest.raises(InventoryOperationError) as error:
            await repository._ensure_retaceo_applied(row)
        assert error.value.code == "inventory_retaceo_application_required"
