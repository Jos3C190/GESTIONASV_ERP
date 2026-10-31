"""Retaceo application is verified, once-only and required before closing."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.application.retaceos import RetaceoUseCases
from app.core.exceptions import BusinessRuleError
from app.domain.entities.retaceo import RetaceoStatus

from tests.unit.test_retaceo_use_cases import (
    FakePurchaseRepository,
    FakeRetaceoRepository,
    _create,
    _ids,
    _purchase,
)

pytestmark = pytest.mark.unit


class ValuationGateway:
    def __init__(self, repository):
        self.repository = repository
        self.applications = 0
        self.locked = False

    async def lock(self, company_id):
        self.locked = True

    async def enabled(self, company_id):
        return True

    async def receipt_is_valued(self, company_id, purchase_id):
        return True

    async def apply_retaceo(self, retaceo, actor_id):
        assert self.locked
        self.applications += 1
        self.repository.items[retaceo.id] = replace(
            retaceo, applied_at=datetime.now(UTC), applied_by=actor_id
        )


async def setup():
    purchase = _purchase(_ids())
    repository = FakeRetaceoRepository()
    retaceo = await _create(repository, purchase)
    gateway = ValuationGateway(repository)
    use_cases = RetaceoUseCases(repository, FakePurchaseRepository(purchase), valuation=gateway)
    return repository, gateway, use_cases, retaceo


async def test_apply_rejects_unverified_draft():
    _, gateway, use_cases, retaceo = await setup()
    with pytest.raises(BusinessRuleError, match="Verifique"):
        await use_cases.apply_retaceo(retaceo.company_id, retaceo.id, uuid4())
    assert gateway.applications == 0


async def test_verified_retaceo_applies_once_and_can_close():
    repository, gateway, use_cases, retaceo = await setup()
    repository.items[retaceo.id] = replace(retaceo, status=RetaceoStatus.VERIFIED)
    actor = uuid4()
    applied = await use_cases.apply_retaceo(retaceo.company_id, retaceo.id, actor)
    await use_cases.apply_retaceo(retaceo.company_id, retaceo.id, actor)
    assert gateway.applications == 1
    assert applied.applied_by == actor
    assert applied.applied_at is not None
    closed = await use_cases.close_retaceo(retaceo.company_id, retaceo.id)
    assert closed.status is RetaceoStatus.CLOSED
    assert closed.applied_at == applied.applied_at


async def test_active_valuation_prevents_closing_without_application():
    repository, _, use_cases, retaceo = await setup()
    repository.items[retaceo.id] = replace(retaceo, status=RetaceoStatus.VERIFIED)
    with pytest.raises(BusinessRuleError) as failure:
        await use_cases.close_retaceo(retaceo.company_id, retaceo.id)
    assert failure.value.code == "retaceo_application_required"
    assert repository.items[retaceo.id].status is RetaceoStatus.VERIFIED
