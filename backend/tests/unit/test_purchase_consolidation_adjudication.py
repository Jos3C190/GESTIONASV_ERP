"""Rules for comparing supplier responses and manually allocating demand."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from app.application.purchase_consolidations import PurchaseConsolidationAdjudicationUseCases
from app.core.exceptions import BusinessRuleError
from app.domain.entities.purchase_consolidation import (
    ConsolidationLine,
    PurchaseConsolidation,
    PurchaseConsolidationAward,
    PurchaseConsolidationStatus,
)
from app.domain.entities.purchase_quotation import (
    PurchaseQuotation,
    PurchaseQuotationDetail,
    PurchaseQuotationLineSnapshot,
    PurchaseQuotationStatus,
)


class FakeConsolidationRepository:
    def __init__(self, consolidation: PurchaseConsolidation) -> None:
        self.consolidation = consolidation
        self.awards: list[PurchaseConsolidationAward] = []

    async def get(self, company_id, consolidation_id, *, for_update=False):
        if self.consolidation.company_id != company_id or self.consolidation.id != consolidation_id:
            return None
        return self.consolidation

    async def list_awards(self, company_id, consolidation_id):
        return tuple(
            award
            for award in self.awards
            if award.company_id == company_id and award.consolidation_id == consolidation_id
        )

    async def create_award(self, award):
        saved = replace(award, created_at=datetime.now(UTC))
        self.awards.append(saved)
        return saved

    async def revoke_award(self, company_id, consolidation_id, award_id, *, actor_id, reason):
        for index, award in enumerate(self.awards):
            if (
                award.company_id == company_id
                and award.consolidation_id == consolidation_id
                and award.id == award_id
                and award.is_active
            ):
                saved = replace(
                    award,
                    revoked_at=datetime.now(UTC),
                    revoked_by_id=actor_id,
                    revocation_reason=reason,
                )
                self.awards[index] = saved
                return saved
        return None


class FakeQuotationRepository:
    def __init__(self, quotations: tuple[PurchaseQuotation, ...]) -> None:
        self.quotations = quotations

    async def list_consolidation_quotations(self, company_id, consolidation_id):
        return tuple(
            quotation
            for quotation in self.quotations
            if quotation.company_id == company_id
            and quotation.consolidation_id == consolidation_id
        )


class FakePurchaseOrderRepository:
    def __init__(self, ordered_quantities: dict[uuid.UUID, Decimal]) -> None:
        self.ordered_quantities = ordered_quantities

    async def get_ordered_award_quantities(
        self, company_id, award_ids, *, exclude_order_id=None
    ):
        return {
            award_id: self.ordered_quantities[award_id]
            for award_id in award_ids
            if award_id in self.ordered_quantities
        }


def _fixture(
    *,
    offered: str = "5",
    available: str | None = "5",
    status: PurchaseQuotationStatus = PurchaseQuotationStatus.UNDER_EVALUATION,
    supplier_id: int = 7,
    version: int = 1,
    currency: str = "USD",
):
    company_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    consolidation_id = uuid.uuid4()
    line_id = uuid.uuid4()
    consolidation = PurchaseConsolidation(
        id=consolidation_id,
        company_id=company_id,
        code="CD-00001",
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        status=PurchaseConsolidationStatus.DRAFT,
        created_by_id=actor_id,
        created_at=None,
        updated_at=None,
        central_warehouse_id=None,
        central_warehouse_name=None,
        notes=None,
        lines=(
            ConsolidationLine(
                id=line_id,
                product_id=10,
                product_sku="SKU-10",
                product_name="Harina",
                unit_id=1,
                unit_name="kg",
                central_quantity=Decimal("10"),
                central_reason="Reposición",
                sources=(),
            ),
        ),
    )
    quotation_id = uuid.uuid4()
    detail_id = uuid.uuid4()
    offered_quantity = Decimal(offered)
    detail = PurchaseQuotationDetail(
        id=detail_id,
        purchase_quotation_id=quotation_id,
        product_id=10,
        unit_id=1,
        quantity=Decimal("10"),
        unit_price=Decimal("4"),
        subtotal=Decimal("40"),
        tax_rate=Decimal("13"),
        tax_amount=Decimal("5.20"),
        total=Decimal("45.20"),
        offered_quantity=offered_quantity,
        available_quantity=Decimal(available) if available is not None else None,
    )
    quotation = PurchaseQuotation(
        id=quotation_id,
        company_id=company_id,
        code=f"COT-{supplier_id:05}",
        supplier_id=supplier_id,
        quotation_date=datetime(2026, 10, 1, tzinfo=UTC),
        currency=currency,
        created_by_id=actor_id,
        request_links=(),
        details=(detail,),
        status=status,
        consolidation_id=consolidation_id,
        consolidation_code=consolidation.code,
        version_number=version,
        snapshots=(
            PurchaseQuotationLineSnapshot(
                purchase_quotation_detail_id=detail_id,
                consolidation_line_id=line_id,
                product_sku="SKU-10",
                product_name="Harina",
                unit_name="kg",
                branch_quantity=Decimal("0"),
                central_quantity=Decimal("10"),
                sources=(),
            ),
        ),
    )
    consolidation_repository = FakeConsolidationRepository(consolidation)
    quotation_repository = FakeQuotationRepository((quotation,))
    use_cases = PurchaseConsolidationAdjudicationUseCases(
        consolidation_repository, quotation_repository
    )
    return {
        "company_id": company_id,
        "actor_id": actor_id,
        "consolidation": consolidation,
        "line_id": line_id,
        "quotation": quotation,
        "detail_id": detail_id,
        "consolidation_repository": consolidation_repository,
        "quotation_repository": quotation_repository,
        "use_cases": use_cases,
    }


def _additional_quote(case, *, supplier_id: int, version: int, offered: str, currency: str):
    original = case["quotation"]
    new_quotation_id = uuid.uuid4()
    new_detail_id = uuid.uuid4()
    detail = replace(
        original.details[0],
        id=new_detail_id,
        purchase_quotation_id=new_quotation_id,
        offered_quantity=Decimal(offered),
        available_quantity=Decimal(offered),
    )
    snapshot = replace(
        original.snapshots[0],
        purchase_quotation_detail_id=new_detail_id,
        consolidation_line_id=case["line_id"],
    )
    return replace(
        original,
        id=new_quotation_id,
        code=f"COT-{supplier_id:05d}-V{version}",
        supplier_id=supplier_id,
        currency=currency,
        details=(detail,),
        version_number=version,
        snapshots=(snapshot,),
    )


@pytest.mark.asyncio
async def test_board_preserves_original_currencies_and_allows_split_allocations():
    case = _fixture(offered="5", available="4")
    second = _additional_quote(case, supplier_id=8, version=1, offered="8", currency="EUR")
    case["quotation_repository"].quotations += (second,)

    saved_first = await case["use_cases"].award(
        company_id=case["company_id"],
        consolidation_id=case["consolidation"].id,
        consolidation_line_id=case["line_id"],
        quotation_id=case["quotation"].id,
        quotation_detail_id=case["detail_id"],
        quantity=Decimal("4"),
        reason="Entrega disponible esta semana",
        actor_id=case["actor_id"],
    )
    saved_second = await case["use_cases"].award(
        company_id=case["company_id"],
        consolidation_id=case["consolidation"].id,
        consolidation_line_id=case["line_id"],
        quotation_id=second.id,
        quotation_detail_id=second.details[0].id,
        quantity=Decimal("6"),
        reason="Completa el faltante",
        actor_id=case["actor_id"],
    )

    board = await case["use_cases"].get_board(case["company_id"], case["consolidation"].id)
    line = board.lines[0]
    assert (saved_first.quantity, saved_second.quantity) == (Decimal("4"), Decimal("6"))
    assert line.awarded_quantity == Decimal("10")
    assert line.remaining_quantity == Decimal("0")
    assert board.currencies == ("EUR", "USD")


@pytest.mark.asyncio
async def test_award_cannot_exceed_remaining_demand_or_supplier_offer():
    case = _fixture(offered="5", available="4")
    common = {
        "company_id": case["company_id"],
        "consolidation_id": case["consolidation"].id,
        "consolidation_line_id": case["line_id"],
        "quotation_id": case["quotation"].id,
        "quotation_detail_id": case["detail_id"],
        "reason": "Decisión de prueba",
        "actor_id": case["actor_id"],
    }
    with pytest.raises(BusinessRuleError) as demand_error:
        await case["use_cases"].award(**common, quantity=Decimal("11"))
    assert demand_error.value.code == "purchase_award_demand_exceeded"

    with pytest.raises(BusinessRuleError) as offer_error:
        await case["use_cases"].award(**common, quantity=Decimal("5"))
    assert offer_error.value.code == "purchase_award_offer_quantity_exceeded"


@pytest.mark.asyncio
async def test_received_offer_must_be_moved_to_evaluation_before_award():
    case = _fixture(status=PurchaseQuotationStatus.RECEIVED)
    board = await case["use_cases"].get_board(case["company_id"], case["consolidation"].id)
    assert board.lines[0].offers[0].can_award is False
    assert "evaluación" in (board.lines[0].offers[0].blocked_reason or "")
    with pytest.raises(BusinessRuleError) as error:
        await case["use_cases"].award(
            company_id=case["company_id"],
            consolidation_id=case["consolidation"].id,
            consolidation_line_id=case["line_id"],
            quotation_id=case["quotation"].id,
            quotation_detail_id=case["detail_id"],
            quantity=Decimal("1"),
            reason="Probar bloqueo de estado",
            actor_id=case["actor_id"],
        )
    assert error.value.code == "purchase_award_offer_unavailable"


@pytest.mark.asyncio
async def test_revoking_award_restores_demand_and_preserves_decision_history():
    case = _fixture(offered="5", available="5")
    award = await case["use_cases"].award(
        company_id=case["company_id"],
        consolidation_id=case["consolidation"].id,
        consolidation_line_id=case["line_id"],
        quotation_id=case["quotation"].id,
        quotation_detail_id=case["detail_id"],
        quantity=Decimal("3"),
        reason="Primera decisión",
        actor_id=case["actor_id"],
    )
    revoked = await case["use_cases"].revoke_award(
        company_id=case["company_id"],
        consolidation_id=case["consolidation"].id,
        award_id=award.id,
        actor_id=uuid.uuid4(),
        reason="El proveedor cambió la fecha de entrega",
    )
    board = await case["use_cases"].get_board(case["company_id"], case["consolidation"].id)
    assert revoked.revoked_at is not None
    assert revoked.revocation_reason == "El proveedor cambió la fecha de entrega"
    assert board.lines[0].awarded_quantity == Decimal("0")
    assert board.lines[0].remaining_quantity == Decimal("10")
    assert board.lines[0].decisions[0].is_active is False


@pytest.mark.asyncio
async def test_award_cannot_be_revoked_while_a_non_cancelled_order_uses_it():
    case = _fixture(offered="5", available="5")
    award = await case["use_cases"].award(
        company_id=case["company_id"],
        consolidation_id=case["consolidation"].id,
        consolidation_line_id=case["line_id"],
        quotation_id=case["quotation"].id,
        quotation_detail_id=case["detail_id"],
        quantity=Decimal("3"),
        reason="Proveedor confirmado",
        actor_id=case["actor_id"],
    )
    case["use_cases"] = PurchaseConsolidationAdjudicationUseCases(
        case["consolidation_repository"],
        case["quotation_repository"],
        FakePurchaseOrderRepository({award.id: Decimal("3")}),
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        await case["use_cases"].revoke_award(
            company_id=case["company_id"],
            consolidation_id=case["consolidation"].id,
            award_id=award.id,
            actor_id=uuid.uuid4(),
            reason="Intento de reversión",
        )

    assert exc_info.value.code == "purchase_award_has_purchase_order"
    assert case["consolidation_repository"].awards[0].is_active is True


@pytest.mark.asyncio
async def test_only_one_active_version_per_supplier_and_product_can_be_used():
    case = _fixture(offered="5", available="5", supplier_id=7, version=1)
    second = _additional_quote(case, supplier_id=7, version=2, offered="5", currency="USD")
    case["quotation_repository"].quotations += (second,)
    await case["use_cases"].award(
        company_id=case["company_id"],
        consolidation_id=case["consolidation"].id,
        consolidation_line_id=case["line_id"],
        quotation_id=case["quotation"].id,
        quotation_detail_id=case["detail_id"],
        quantity=Decimal("2"),
        reason="Usar versión uno",
        actor_id=case["actor_id"],
    )
    board = await case["use_cases"].get_board(case["company_id"], case["consolidation"].id)
    second_offer = next(
        offer for offer in board.lines[0].offers if offer.quotation_id == second.id
    )
    assert second_offer.can_award is False
    assert "otra versión" in (second_offer.blocked_reason or "")
