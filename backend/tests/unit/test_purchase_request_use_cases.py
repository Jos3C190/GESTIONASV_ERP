from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal

import pytest
from app.application.purchase_requests.use_cases import (
    PurchaseRequestLineDraft,
    PurchaseRequestUseCases,
)
from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.purchase_request import PurchaseRequest, PurchaseRequestStatus
from app.domain.ports.purchase_request_repository import PurchaseProductReference


class FakePurchaseRequestRepository:
    def __init__(self) -> None:
        self.company_id = uuid.uuid4()
        self.branch_id = uuid.uuid4()
        self.warehouse_id = uuid.uuid4()
        self.requests: dict[tuple[uuid.UUID, uuid.UUID], PurchaseRequest] = {}
        self.products: dict[int, PurchaseProductReference] = {
            10: PurchaseProductReference(
                product_id=10,
                purchase_unit_id=7,
                is_active=True,
                lifecycle_status="active",
                can_purchase=True,
                unit_enabled=True,
            )
        }
        self._sequence = 0

    async def list_requests(self, company_id, **kwargs):
        items = [
            request
            for (tenant, _request_id), request in self.requests.items()
            if tenant == company_id
        ]
        return items, len(items)

    async def get_request(self, company_id, request_id):
        return self.requests.get((company_id, request_id))

    async def get_request_for_update(self, company_id, request_id):
        return await self.get_request(company_id, request_id)

    async def allocate_next_code(self, company_id):
        self._sequence += 1
        return f"SCR-{self._sequence:05d}"

    async def is_branch_available(self, company_id, branch_id):
        return company_id == self.company_id and branch_id == self.branch_id

    async def is_warehouse_available(self, company_id, branch_id, warehouse_id):
        return (
            company_id == self.company_id
            and branch_id == self.branch_id
            and warehouse_id == self.warehouse_id
        )

    async def get_product_reference(self, company_id, product_id):
        if company_id != self.company_id:
            return None
        return self.products.get(product_id)

    async def add_request(self, request):
        self.requests[(request.company_id, request.id)] = request
        return request

    async def replace_draft(self, request):
        key = (request.company_id, request.id)
        if key not in self.requests:
            return None
        self.requests[key] = request
        return request

    async def update_status(self, company_id, request_id, status):
        current = self.requests.get((company_id, request_id))
        if current is None:
            return None
        updated = replace(current, status=status)
        self.requests[(company_id, request_id)] = updated
        return updated


def _line(product_id: int = 10, quantity: str = "2") -> PurchaseRequestLineDraft:
    return PurchaseRequestLineDraft(product_id=product_id, quantity=Decimal(quantity))


async def _create(
    repository: FakePurchaseRequestRepository,
) -> tuple[PurchaseRequestUseCases, PurchaseRequest]:
    use_cases = PurchaseRequestUseCases(repository)
    request = await use_cases.create_request(
        company_id=repository.company_id,
        requested_by_id=uuid.uuid4(),
        branch_id=repository.branch_id,
        warehouse_id=repository.warehouse_id,
        justification="Reposición semanal",
        lines=(_line(),),
    )
    return use_cases, request


@pytest.mark.asyncio
async def test_create_assigns_server_code_and_product_purchase_unit() -> None:
    repository = FakePurchaseRequestRepository()
    _use_cases, request = await _create(repository)

    assert request.code == "SCR-00001"
    assert request.status is PurchaseRequestStatus.DRAFT
    assert request.details[0].unit_id == 7
    assert request.details[0].product_id == 10


@pytest.mark.asyncio
async def test_create_rejects_branch_outside_company() -> None:
    repository = FakePurchaseRequestRepository()
    use_cases = PurchaseRequestUseCases(repository)

    with pytest.raises(NotFoundError) as rejected:
        await use_cases.create_request(
            company_id=repository.company_id,
            requested_by_id=uuid.uuid4(),
            branch_id=uuid.uuid4(),
            warehouse_id=repository.warehouse_id,
            justification="Reposición",
            lines=(_line(),),
        )

    assert rejected.value.code == "purchase_request_branch_not_found"


@pytest.mark.asyncio
async def test_create_rejects_warehouse_from_other_branch() -> None:
    repository = FakePurchaseRequestRepository()
    use_cases = PurchaseRequestUseCases(repository)

    with pytest.raises(NotFoundError) as rejected:
        await use_cases.create_request(
            company_id=repository.company_id,
            requested_by_id=uuid.uuid4(),
            branch_id=repository.branch_id,
            warehouse_id=uuid.uuid4(),
            justification="Reposición",
            lines=(_line(),),
        )

    assert rejected.value.code == "purchase_request_warehouse_not_found"


@pytest.mark.asyncio
async def test_create_rejects_unknown_product() -> None:
    repository = FakePurchaseRequestRepository()
    use_cases = PurchaseRequestUseCases(repository)

    with pytest.raises(NotFoundError) as rejected:
        await use_cases.create_request(
            company_id=repository.company_id,
            requested_by_id=uuid.uuid4(),
            branch_id=repository.branch_id,
            warehouse_id=repository.warehouse_id,
            justification="Reposición",
            lines=(_line(product_id=999),),
        )

    assert rejected.value.code == "purchase_request_product_not_found"


@pytest.mark.asyncio
async def test_create_rejects_product_not_enabled_for_purchase() -> None:
    repository = FakePurchaseRequestRepository()
    repository.products[10] = replace(repository.products[10], can_purchase=False)
    use_cases = PurchaseRequestUseCases(repository)

    with pytest.raises(BusinessRuleError) as rejected:
        await use_cases.create_request(
            company_id=repository.company_id,
            requested_by_id=uuid.uuid4(),
            branch_id=repository.branch_id,
            warehouse_id=repository.warehouse_id,
            justification="Reposición",
            lines=(_line(),),
        )

    assert rejected.value.code == "purchase_request_product_not_purchasable"


@pytest.mark.asyncio
async def test_create_rejects_disabled_purchase_unit() -> None:
    repository = FakePurchaseRequestRepository()
    repository.products[10] = replace(repository.products[10], unit_enabled=False)
    use_cases = PurchaseRequestUseCases(repository)

    with pytest.raises(BusinessRuleError) as rejected:
        await use_cases.create_request(
            company_id=repository.company_id,
            requested_by_id=uuid.uuid4(),
            branch_id=repository.branch_id,
            warehouse_id=repository.warehouse_id,
            justification="Reposición",
            lines=(_line(),),
        )

    assert rejected.value.code == "purchase_request_purchase_unit_unavailable"


@pytest.mark.asyncio
async def test_create_rejects_duplicate_products() -> None:
    repository = FakePurchaseRequestRepository()
    use_cases = PurchaseRequestUseCases(repository)

    with pytest.raises(ValidationError) as rejected:
        await use_cases.create_request(
            company_id=repository.company_id,
            requested_by_id=uuid.uuid4(),
            branch_id=repository.branch_id,
            warehouse_id=repository.warehouse_id,
            justification="Reposición",
            lines=(_line(), _line(quantity="3")),
        )

    assert rejected.value.code == "purchase_request_duplicate_product"


@pytest.mark.asyncio
async def test_create_maps_invalid_quantity_to_application_error() -> None:
    repository = FakePurchaseRequestRepository()
    use_cases = PurchaseRequestUseCases(repository)

    with pytest.raises(ValidationError) as rejected:
        await use_cases.create_request(
            company_id=repository.company_id,
            requested_by_id=uuid.uuid4(),
            branch_id=repository.branch_id,
            warehouse_id=repository.warehouse_id,
            justification="Reposición",
            lines=(_line(quantity="0"),),
        )

    assert rejected.value.code == "purchase_request_quantity_invalid"


@pytest.mark.asyncio
async def test_replace_draft_preserves_server_owned_fields() -> None:
    repository = FakePurchaseRequestRepository()
    use_cases, request = await _create(repository)
    original_requested_by = request.requested_by_id
    original_request_date = request.request_date

    updated = await use_cases.replace_draft(
        company_id=repository.company_id,
        request_id=request.id,
        branch_id=repository.branch_id,
        warehouse_id=repository.warehouse_id,
        justification="Reposición corregida",
        lines=(_line(quantity="5"),),
        notes="Urgente",
    )

    assert updated.id == request.id
    assert updated.code == request.code
    assert updated.requested_by_id == original_requested_by
    assert updated.request_date == original_request_date
    assert updated.justification == "Reposición corregida"
    assert updated.details[0].quantity == Decimal("5")


@pytest.mark.asyncio
async def test_replace_rejects_non_draft_request() -> None:
    repository = FakePurchaseRequestRepository()
    use_cases, request = await _create(repository)
    await use_cases.submit_request(repository.company_id, request.id)

    with pytest.raises(BusinessRuleError) as rejected:
        await use_cases.replace_draft(
            company_id=repository.company_id,
            request_id=request.id,
            branch_id=repository.branch_id,
            warehouse_id=repository.warehouse_id,
            justification="No debería guardarse",
            lines=(_line(),),
        )

    assert rejected.value.code == "purchase_request_not_editable"


@pytest.mark.asyncio
async def test_submit_then_approve_follows_workflow() -> None:
    repository = FakePurchaseRequestRepository()
    use_cases, request = await _create(repository)

    submitted = await use_cases.submit_request(repository.company_id, request.id)
    approved = await use_cases.approve_request(repository.company_id, request.id)

    assert submitted.status is PurchaseRequestStatus.SUBMITTED
    assert approved.status is PurchaseRequestStatus.APPROVED


@pytest.mark.asyncio
async def test_submit_then_reject_and_draft_cancel_follow_workflow() -> None:
    repository = FakePurchaseRequestRepository()
    use_cases, request = await _create(repository)

    submitted = await use_cases.submit_request(repository.company_id, request.id)
    rejected = await use_cases.reject_request(repository.company_id, request.id)

    assert submitted.status is PurchaseRequestStatus.SUBMITTED
    assert rejected.status is PurchaseRequestStatus.REJECTED

    _other_use_cases, cancellable = await _create(repository)
    cancelled = await use_cases.cancel_request(repository.company_id, cancellable.id)
    assert cancelled.status is PurchaseRequestStatus.CANCELLED


@pytest.mark.asyncio
async def test_illegal_transition_is_business_rule_error() -> None:
    repository = FakePurchaseRequestRepository()
    use_cases, request = await _create(repository)

    with pytest.raises(BusinessRuleError) as rejected:
        await use_cases.approve_request(repository.company_id, request.id)

    assert rejected.value.code == "purchase_request_invalid_transition"


@pytest.mark.asyncio
async def test_get_request_is_tenant_scoped() -> None:
    repository = FakePurchaseRequestRepository()
    use_cases, request = await _create(repository)

    with pytest.raises(NotFoundError) as rejected:
        await use_cases.get_request(uuid.uuid4(), request.id)

    assert rejected.value.code == "purchase_request_not_found"
