"""Unit coverage for draft purchase-demand consolidation rules."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from app.application.purchase_consolidations import (
    CentralDemandDraft,
    PurchaseConsolidationUseCases,
    SourceQuantityChange,
)
from app.core.exceptions import BusinessRuleError, ValidationError
from app.domain.entities.purchase_consolidation import (
    PurchaseConsolidation,
    PurchaseConsolidationAward,
    PurchaseConsolidationStatus,
)
from app.domain.entities.purchase_request import (
    PurchaseRequest,
    PurchaseRequestDetail,
    PurchaseRequestStatus,
)
from app.domain.ports.purchase_request_repository import PurchaseProductReference


class FakeConsolidationRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, PurchaseConsolidation] = {}
        self.warehouse_ids: set[uuid.UUID] = set()
        self.central_warehouse_ids: set[uuid.UUID] = set()
        self.linked_source_ids: set[uuid.UUID] = set()
        self.awards: list[PurchaseConsolidationAward] = []
        self.next_code = 1

    async def list_work_items(self, company_id: uuid.UUID, **kwargs: object):
        return [], 0

    async def list_approved_requests(self, company_id: uuid.UUID, **kwargs: object):
        return [], 0

    async def allocate_next_code(self, company_id: uuid.UUID) -> str:
        code = f"CD-{self.next_code:05}"
        self.next_code += 1
        return code

    async def central_warehouse_available(
        self, company_id: uuid.UUID, warehouse_id: uuid.UUID
    ) -> bool:
        return warehouse_id in self.central_warehouse_ids

    async def has_active_source(self, company_id: uuid.UUID, detail_id: uuid.UUID) -> bool:
        return detail_id in self.linked_source_ids

    async def create(self, consolidation: PurchaseConsolidation) -> PurchaseConsolidation:
        self.items[consolidation.id] = consolidation
        self.linked_source_ids.update(
            source.purchase_request_detail_id
            for line in consolidation.lines
            for source in line.sources
        )
        return consolidation

    async def get(
        self, company_id: uuid.UUID, consolidation_id: uuid.UUID, *, for_update: bool = False
    ) -> PurchaseConsolidation | None:
        item = self.items.get(consolidation_id)
        return item if item is not None and item.company_id == company_id else None

    async def save_draft(
        self,
        consolidation: PurchaseConsolidation,
        *,
        actor_id: uuid.UUID,
        change_reason: str,
    ) -> PurchaseConsolidation | None:
        self.items[consolidation.id] = consolidation
        self.linked_source_ids.update(
            source.purchase_request_detail_id
            for line in consolidation.lines
            for source in line.sources
        )
        return consolidation

    async def cancel(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
    ) -> PurchaseConsolidation | None:
        item = await self.get(company_id, consolidation_id)
        if item is None:
            return None
        cancelled = replace(item, status=PurchaseConsolidationStatus.CANCELLED)
        self.items[item.id] = cancelled
        return cancelled

    async def list_awards(self, company_id: uuid.UUID, consolidation_id: uuid.UUID):
        return tuple(
            award
            for award in self.awards
            if award.company_id == company_id and award.consolidation_id == consolidation_id
        )


class FakePurchaseRequestRepository:
    def __init__(self) -> None:
        self.requests: dict[uuid.UUID, PurchaseRequest] = {}
        self.product_references: dict[int, PurchaseProductReference] = {}

    async def get_request(self, company_id: uuid.UUID, request_id: uuid.UUID):
        request = self.requests.get(request_id)
        return request if request is not None and request.company_id == company_id else None

    async def get_product_reference(self, company_id: uuid.UUID, product_id: int):
        return self.product_references.get(product_id)


def _request(
    *,
    company_id: uuid.UUID,
    branch_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    product_id: int = 14,
    unit_id: int = 2,
    quantity: str = "6",
    status: PurchaseRequestStatus = PurchaseRequestStatus.APPROVED,
    request_day: int = 4,
) -> PurchaseRequest:
    request_id = uuid.uuid4()
    detail = PurchaseRequestDetail(
        id=uuid.uuid4(),
        purchase_request_id=request_id,
        product_id=product_id,
        unit_id=unit_id,
        quantity=Decimal(quantity),
    )
    return PurchaseRequest(
        id=request_id,
        company_id=company_id,
        code=f"SCR-{uuid.uuid4().hex[:6].upper()}",
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        requested_by_id=uuid.uuid4(),
        request_date=datetime(2026, 10, request_day, 12, tzinfo=UTC),
        justification="Abastecimiento de prueba",
        details=(detail,),
        status=status,
        branch_name="Sucursal prueba",
        warehouse_name="Bodega prueba",
    )


@pytest.fixture
def setup_case():
    company_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    consolidation_repository = FakeConsolidationRepository()
    request_repository = FakePurchaseRequestRepository()
    consolidation_repository.warehouse_ids.add(warehouse_id)
    consolidation_repository.central_warehouse_ids.add(warehouse_id)
    use_cases = PurchaseConsolidationUseCases(consolidation_repository, request_repository)
    return {
        "company_id": company_id,
        "actor_id": actor_id,
        "branch_id": branch_id,
        "warehouse_id": warehouse_id,
        "consolidation_repository": consolidation_repository,
        "request_repository": request_repository,
        "use_cases": use_cases,
    }


@pytest.mark.asyncio
async def test_create_rejects_store_warehouse_not_designated_as_central(setup_case):
    case = setup_case
    request = _request(
        company_id=case["company_id"],
        branch_id=case["branch_id"],
        warehouse_id=case["warehouse_id"],
    )
    case["request_repository"].requests[request.id] = request
    case["consolidation_repository"].central_warehouse_ids.clear()

    with pytest.raises(BusinessRuleError, match="marcado como bodega madre"):
        await case["use_cases"].create(
            company_id=case["company_id"],
            actor_id=case["actor_id"],
            request_ids=(request.id,),
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 30),
            central_warehouse_id=case["warehouse_id"],
            notes=None,
        )


@pytest.mark.asyncio
async def test_create_groups_only_identical_product_and_unit_and_preserves_sources(setup_case):
    case = setup_case
    first = _request(
        company_id=case["company_id"],
        branch_id=case["branch_id"],
        warehouse_id=case["warehouse_id"],
        quantity="6",
    )
    second = _request(
        company_id=case["company_id"],
        branch_id=case["branch_id"],
        warehouse_id=case["warehouse_id"],
        quantity="9",
    )
    different_unit = _request(
        company_id=case["company_id"],
        branch_id=case["branch_id"],
        warehouse_id=case["warehouse_id"],
        unit_id=3,
        quantity="2",
    )
    case["request_repository"].requests.update(
        {
            first.id: first,
            second.id: second,
            different_unit.id: different_unit,
        }
    )

    item = await case["use_cases"].create(
        company_id=case["company_id"],
        actor_id=case["actor_id"],
        request_ids=(first.id, second.id, different_unit.id),
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 30),
        central_warehouse_id=None,
        notes=None,
    )

    assert item.status is PurchaseConsolidationStatus.DRAFT
    assert len(item.lines) == 2
    combined = next(line for line in item.lines if line.unit_id == 2)
    assert combined.branch_quantity == Decimal("15")
    assert len(combined.sources) == 2
    assert {source.requested_quantity for source in combined.sources} == {
        Decimal("6"),
        Decimal("9"),
    }


@pytest.mark.asyncio
async def test_create_only_accepts_approved_requests_inside_selected_period(setup_case):
    case = setup_case
    pending = _request(
        company_id=case["company_id"],
        branch_id=case["branch_id"],
        warehouse_id=case["warehouse_id"],
        status=PurchaseRequestStatus.SUBMITTED,
    )
    case["request_repository"].requests[pending.id] = pending

    with pytest.raises(BusinessRuleError, match="aprobada"):
        await case["use_cases"].create(
            company_id=case["company_id"],
            actor_id=case["actor_id"],
            request_ids=(pending.id,),
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 30),
            central_warehouse_id=None,
            notes=None,
        )

    approved_outside = _request(
        company_id=case["company_id"],
        branch_id=case["branch_id"],
        warehouse_id=case["warehouse_id"],
        request_day=31,
    )
    case["request_repository"].requests[approved_outside.id] = approved_outside
    with pytest.raises(BusinessRuleError, match="fuera del período"):
        await case["use_cases"].create(
            company_id=case["company_id"],
            actor_id=case["actor_id"],
            request_ids=(approved_outside.id,),
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 30),
            central_warehouse_id=None,
            notes=None,
        )


@pytest.mark.asyncio
async def test_reducing_or_excluding_source_requires_reason_and_keeps_original_amount(setup_case):
    case = setup_case
    request = _request(
        company_id=case["company_id"],
        branch_id=case["branch_id"],
        warehouse_id=case["warehouse_id"],
    )
    case["request_repository"].requests[request.id] = request
    item = await case["use_cases"].create(
        company_id=case["company_id"],
        actor_id=case["actor_id"],
        request_ids=(request.id,),
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 30),
        central_warehouse_id=None,
        notes=None,
    )
    source = item.lines[0].sources[0]

    with pytest.raises(ValidationError, match="reducción|exclusión"):
        await case["use_cases"].update_draft(
            company_id=case["company_id"],
            consolidation_id=item.id,
            actor_id=case["actor_id"],
            change_reason="Ajuste de demanda",
            source_changes=(SourceQuantityChange(source.id, Decimal("0"), ""),),
            central_demands=(),
            notes=None,
        )

    updated = await case["use_cases"].update_draft(
        company_id=case["company_id"],
        consolidation_id=item.id,
        actor_id=case["actor_id"],
        change_reason="Exclusión explicada",
        source_changes=(SourceQuantityChange(source.id, Decimal("0"), "No se necesita este mes"),),
        central_demands=(),
        notes=None,
    )
    assert updated.lines[0].sources[0].requested_quantity == Decimal("6")
    assert updated.lines[0].sources[0].included_quantity == Decimal("0")
    assert updated.lines[0].sources[0].reason == "No se necesita este mes"


@pytest.mark.asyncio
async def test_source_quantity_cannot_exceed_original_request(setup_case):
    case = setup_case
    request = _request(
        company_id=case["company_id"],
        branch_id=case["branch_id"],
        warehouse_id=case["warehouse_id"],
    )
    case["request_repository"].requests[request.id] = request
    item = await case["use_cases"].create(
        company_id=case["company_id"],
        actor_id=case["actor_id"],
        request_ids=(request.id,),
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 30),
        central_warehouse_id=None,
        notes=None,
    )
    source = item.lines[0].sources[0]

    with pytest.raises(ValidationError, match="superar"):
        await case["use_cases"].update_draft(
            company_id=case["company_id"],
            consolidation_id=item.id,
            actor_id=case["actor_id"],
            change_reason="Aumentar",
            source_changes=(SourceQuantityChange(source.id, Decimal("7"), "Aumentar"),),
            central_demands=(),
            notes=None,
        )


@pytest.mark.asyncio
async def test_new_central_demand_requires_a_reason(setup_case):
    case = setup_case
    request = _request(
        company_id=case["company_id"],
        branch_id=case["branch_id"],
        warehouse_id=case["warehouse_id"],
    )
    case["request_repository"].requests[request.id] = request
    item = await case["use_cases"].create(
        company_id=case["company_id"],
        actor_id=case["actor_id"],
        request_ids=(request.id,),
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 30),
        central_warehouse_id=case["warehouse_id"],
        notes=None,
    )

    with pytest.raises(ValidationError, match="necesidad de bodega central"):
        await case["use_cases"].update_draft(
            company_id=case["company_id"],
            consolidation_id=item.id,
            actor_id=case["actor_id"],
            change_reason="Ajustar plan",
            source_changes=(),
            central_demands=(CentralDemandDraft(14, Decimal("120"), ""),),
            notes=None,
        )


@pytest.mark.asyncio
async def test_central_warehouse_cannot_be_cleared_while_central_demand_remains(setup_case):
    case = setup_case
    request = _request(
        company_id=case["company_id"],
        branch_id=case["branch_id"],
        warehouse_id=case["warehouse_id"],
    )
    case["request_repository"].requests[request.id] = request
    case["request_repository"].product_references[25] = PurchaseProductReference(
        product_id=25,
        purchase_unit_id=2,
        is_active=True,
        lifecycle_status="active",
        can_purchase=True,
        unit_enabled=True,
    )
    item = await case["use_cases"].create(
        company_id=case["company_id"],
        actor_id=case["actor_id"],
        request_ids=(request.id,),
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 30),
        central_warehouse_id=case["warehouse_id"],
        notes=None,
    )
    item = await case["use_cases"].update_draft(
        company_id=case["company_id"],
        consolidation_id=item.id,
        actor_id=case["actor_id"],
        change_reason="Plan central",
        source_changes=(),
        central_demands=(CentralDemandDraft(25, Decimal("2"), "Mínimo central"),),
        notes=None,
    )
    central_line = next(entry for entry in item.lines if entry.product_id == 25)

    with pytest.raises(BusinessRuleError, match="bodega destino"):
        await case["use_cases"].update_draft(
            company_id=case["company_id"],
            consolidation_id=item.id,
            actor_id=case["actor_id"],
            change_reason="Limpiar destino",
            source_changes=(),
            central_demands=(),
            notes=None,
            central_warehouse_id=None,
            update_central_warehouse=True,
        )

    cleared = await case["use_cases"].update_draft(
        company_id=case["company_id"],
        consolidation_id=item.id,
        actor_id=case["actor_id"],
        change_reason="Quitar plan central",
        source_changes=(),
        central_demands=(CentralDemandDraft(25, Decimal("0"), "No se requiere", central_line.id),),
        notes=None,
        central_warehouse_id=None,
        update_central_warehouse=True,
    )
    assert cleared.central_warehouse_id is None
    assert next(
        entry for entry in cleared.lines if entry.product_id == 25
    ).central_quantity == Decimal("0")


@pytest.mark.asyncio
async def test_active_award_blocks_changes_to_demand_until_reversed(setup_case):
    case = setup_case
    request = _request(
        company_id=case["company_id"],
        branch_id=case["branch_id"],
        warehouse_id=case["warehouse_id"],
    )
    case["request_repository"].requests[request.id] = request
    item = await case["use_cases"].create(
        company_id=case["company_id"],
        actor_id=case["actor_id"],
        request_ids=(request.id,),
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 30),
        central_warehouse_id=None,
        notes=None,
    )
    source = item.lines[0].sources[0]
    case["consolidation_repository"].awards.append(
        PurchaseConsolidationAward(
            id=uuid.uuid4(),
            company_id=case["company_id"],
            consolidation_id=item.id,
            consolidation_line_id=item.lines[0].id,
            purchase_quotation_id=uuid.uuid4(),
            purchase_quotation_detail_id=uuid.uuid4(),
            supplier_id=10,
            quantity=Decimal("1"),
            reason="Adjudicada",
            decided_by_id=case["actor_id"],
        )
    )

    with pytest.raises(BusinessRuleError) as error:
        await case["use_cases"].update_draft(
            company_id=case["company_id"],
            consolidation_id=item.id,
            actor_id=case["actor_id"],
            change_reason="Reducir la necesidad",
            source_changes=(SourceQuantityChange(source.id, Decimal("4"), "Cambio solicitado"),),
            central_demands=(),
            notes=None,
        )
    assert error.value.code == "purchase_consolidation_active_awards_block_edit"


@pytest.mark.asyncio
@pytest.mark.parametrize(("hour", "eligible"), [(5, True), (6, False)])
async def test_consolidation_period_uses_el_salvador_day_at_midnight_boundary(
    setup_case, hour, eligible
):
    case = setup_case
    request = _request(
        company_id=case["company_id"],
        branch_id=case["branch_id"],
        warehouse_id=case["warehouse_id"],
    )
    request = replace(request, request_date=datetime(2026, 10, 20, hour, 0, tzinfo=UTC))
    case["request_repository"].requests[request.id] = request
    command = {
        "company_id": case["company_id"],
        "actor_id": case["actor_id"],
        "request_ids": (request.id,),
        "period_start": date(2026, 10, 19),
        "period_end": date(2026, 10, 19),
        "central_warehouse_id": None,
        "notes": None,
    }
    if eligible:
        document = await case["use_cases"].create(**command)
        assert document.lines[0].sources[0].purchase_request_id == request.id
    else:
        with pytest.raises(BusinessRuleError) as error:
            await case["use_cases"].create(**command)
        assert error.value.code == "purchase_consolidation_request_outside_period"
