"""Unit tests for retaceo application rules."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.application.retaceos import RetaceoUseCases
from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.domain.entities.purchase import Purchase, PurchaseDetail, PurchaseStatus
from app.domain.entities.retaceo import Retaceo, RetaceoStatus


def _ids() -> dict[str, uuid.UUID]:
    return {
        key: uuid.uuid4()
        for key in (
            "company",
            "purchase",
            "order",
            "branch",
            "warehouse",
            "user",
        )
    }


def _purchase(
    ids: dict[str, uuid.UUID],
    *,
    status: PurchaseStatus = PurchaseStatus.RECEIVED,
    zero_fob: bool = False,
) -> Purchase:
    first_subtotal = Decimal("0") if zero_fob else Decimal("30000")
    second_subtotal = Decimal("0") if zero_fob else Decimal("26780")
    first_discount = Decimal("0") if zero_fob else Decimal("1000")
    details = (
        PurchaseDetail(
            id=uuid.uuid4(),
            purchase_id=ids["purchase"],
            purchase_order_detail_id=uuid.uuid4(),
            product_id=11,
            quantity_ordered=Decimal("100"),
            quantity_received=Decimal("100"),
            unit_id=3,
            unit_price=Decimal("300"),
            subtotal=first_subtotal,
            discount=first_discount,
            tax_rate=Decimal("13"),
            tax_amount=Decimal("3770"),
            total=first_subtotal - first_discount + Decimal("3770"),
        ),
        PurchaseDetail(
            id=uuid.uuid4(),
            purchase_id=ids["purchase"],
            purchase_order_detail_id=uuid.uuid4(),
            product_id=12,
            quantity_ordered=Decimal("80"),
            quantity_received=Decimal("80"),
            unit_id=3,
            unit_price=Decimal("334.75"),
            subtotal=second_subtotal,
            tax_rate=Decimal("13"),
            tax_amount=Decimal("3481.4"),
            total=second_subtotal + Decimal("3481.4"),
        ),
    )
    subtotal = sum((detail.subtotal for detail in details), Decimal("0"))
    discount = sum((detail.discount for detail in details), Decimal("0"))
    tax = sum((detail.tax_amount for detail in details), Decimal("0"))
    return Purchase(
        id=ids["purchase"],
        company_id=ids["company"],
        code="COM-00001",
        purchase_order_id=ids["order"],
        supplier_id=7,
        branch_id=ids["branch"],
        warehouse_id=ids["warehouse"],
        created_by_id=ids["user"],
        purchase_date=datetime.now(UTC),
        currency="USD",
        details=details,
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        total=subtotal - discount + tax,
        status=status,
    )


class FakePurchaseRepository:
    def __init__(self, purchase: Purchase | None) -> None:
        self.purchase = purchase

    async def get_purchase_for_update(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> Purchase | None:
        if (
            self.purchase is not None
            and self.purchase.company_id == company_id
            and self.purchase.id == purchase_id
        ):
            return self.purchase
        return None


class FakeRetaceoRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Retaceo] = {}
        self.next_number = 1

    async def list_retaceos(
        self,
        company_id: uuid.UUID,
        *,
        status: RetaceoStatus | None = None,
        purchase_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Retaceo], int]:
        values = [
            item
            for item in self.items.values()
            if item.company_id == company_id
            and (status is None or item.status is status)
            and (purchase_id is None or item.purchase_id == purchase_id)
            and (branch_id is None or item.branch_id == branch_id)
        ]
        return values[skip : skip + limit], len(values)

    async def get_retaceo(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo | None:
        item = self.items.get(retaceo_id)
        return item if item is not None and item.company_id == company_id else None

    async def get_retaceo_for_update(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo | None:
        return await self.get_retaceo(company_id, retaceo_id)

    async def allocate_next_code(self, company_id: uuid.UUID) -> str:
        code = f"RET-{self.next_number:05d}"
        self.next_number += 1
        return code

    async def add_retaceo(self, retaceo: Retaceo) -> Retaceo:
        self.items[retaceo.id] = retaceo
        return retaceo

    async def replace_draft(self, retaceo: Retaceo) -> Retaceo | None:
        if retaceo.id not in self.items:
            return None
        self.items[retaceo.id] = retaceo
        return retaceo

    async def update_status(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        status: RetaceoStatus,
    ) -> Retaceo | None:
        item = await self.get_retaceo(company_id, retaceo_id)
        if item is None:
            return None
        updated = replace(item, status=status)
        self.items[retaceo_id] = updated
        return updated


async def _create(
    repository: FakeRetaceoRepository,
    purchase: Purchase,
) -> Retaceo:
    return await RetaceoUseCases(repository, FakePurchaseRepository(purchase)).create_draft(
        company_id=purchase.company_id,
        created_by_id=uuid.uuid4(),
        purchase_id=purchase.id,
        total_freight=Decimal("5125"),
        total_expenses=Decimal("1500"),
        total_dai=Decimal("8927"),
        import_vat=Decimal("8367"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [PurchaseStatus.RECEIVED, PurchaseStatus.VERIFIED, PurchaseStatus.CLOSED],
)
async def test_create_draft_accepts_immutable_purchase_states(status: PurchaseStatus) -> None:
    ids = _ids()
    purchase = _purchase(ids, status=status)
    repository = FakeRetaceoRepository()

    item = await _create(repository, purchase)

    assert item.status is RetaceoStatus.DRAFT
    assert item.purchase_id == purchase.id
    assert item.branch_id == purchase.branch_id
    assert item.code == "RET-00001"


@pytest.mark.asyncio
async def test_create_draft_uses_exact_purchase_details_and_excludes_tax_from_fob() -> None:
    ids = _ids()
    purchase = _purchase(ids)
    repository = FakeRetaceoRepository()

    item = await _create(repository, purchase)

    assert item.total_fob == Decimal("55780.000000")
    assert item.total_cost == Decimal("71332.000000")
    assert item.import_vat == Decimal("8367.000000")
    assert {detail.purchase_detail_id for detail in item.details} == {
        detail.id for detail in purchase.details
    }
    assert item.details[0].cost_fob == Decimal("29000.000000")
    assert item.details[1].cost_fob == Decimal("26780.000000")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [PurchaseStatus.DRAFT, PurchaseStatus.CANCELLED])
async def test_create_draft_rejects_non_immutable_purchase(status: PurchaseStatus) -> None:
    ids = _ids()
    purchase = _purchase(ids, status=status)

    with pytest.raises(BusinessRuleError) as exc_info:
        await _create(FakeRetaceoRepository(), purchase)

    assert exc_info.value.code == "retaceo_purchase_not_eligible"


@pytest.mark.asyncio
async def test_create_draft_rejects_zero_total_fob() -> None:
    ids = _ids()
    purchase = _purchase(ids, zero_fob=True)

    with pytest.raises(ValidationError) as exc_info:
        await _create(FakeRetaceoRepository(), purchase)

    assert exc_info.value.code == "retaceo_allocation_invalid"


@pytest.mark.asyncio
async def test_create_draft_rejects_invalid_import_vat() -> None:
    ids = _ids()
    purchase = _purchase(ids)
    use_cases = RetaceoUseCases(
        FakeRetaceoRepository(),
        FakePurchaseRepository(purchase),
    )

    with pytest.raises(ValidationError) as exc_info:
        await use_cases.create_draft(
            company_id=ids["company"],
            created_by_id=ids["user"],
            purchase_id=ids["purchase"],
            total_freight=Decimal("0"),
            total_expenses=Decimal("0"),
            total_dai=Decimal("0"),
            import_vat=Decimal("-1"),
        )

    assert exc_info.value.code == "retaceo_import_vat_invalid"


@pytest.mark.asyncio
async def test_update_draft_recalculates_and_preserves_identity() -> None:
    ids = _ids()
    purchase = _purchase(ids)
    repository = FakeRetaceoRepository()
    created = await _create(repository, purchase)
    use_cases = RetaceoUseCases(repository, FakePurchaseRepository(purchase))

    updated = await use_cases.update_draft(
        company_id=ids["company"],
        retaceo_id=created.id,
        total_freight=Decimal("100"),
        total_expenses=Decimal("200"),
        total_dai=Decimal("300"),
        import_vat=Decimal("400"),
        notes="Ajustado",
    )

    assert updated.id == created.id
    assert updated.code == created.code
    assert updated.purchase_id == created.purchase_id
    assert updated.total_cost == Decimal("56380.000000")
    assert updated.import_vat == Decimal("400.000000")
    assert updated.notes == "Ajustado"


@pytest.mark.asyncio
async def test_update_non_draft_is_rejected() -> None:
    ids = _ids()
    purchase = _purchase(ids)
    repository = FakeRetaceoRepository()
    created = await _create(repository, purchase)
    repository.items[created.id] = replace(created, status=RetaceoStatus.CALCULATED)
    use_cases = RetaceoUseCases(repository, FakePurchaseRepository(purchase))

    with pytest.raises(BusinessRuleError) as exc_info:
        await use_cases.update_draft(
            company_id=ids["company"],
            retaceo_id=created.id,
            total_freight=Decimal("1"),
            total_expenses=Decimal("1"),
            total_dai=Decimal("1"),
            import_vat=Decimal("1"),
        )

    assert exc_info.value.code == "retaceo_not_editable"


@pytest.mark.asyncio
async def test_workflow_calculate_verify_close() -> None:
    ids = _ids()
    purchase = _purchase(ids)
    repository = FakeRetaceoRepository()
    created = await _create(repository, purchase)
    use_cases = RetaceoUseCases(repository, FakePurchaseRepository(purchase))

    calculated = await use_cases.calculate_retaceo(ids["company"], created.id)
    verified = await use_cases.verify_retaceo(ids["company"], created.id)
    closed = await use_cases.close_retaceo(ids["company"], created.id)

    assert calculated.status is RetaceoStatus.CALCULATED
    assert verified.status is RetaceoStatus.VERIFIED
    assert closed.status is RetaceoStatus.CLOSED


@pytest.mark.asyncio
async def test_invalid_workflow_transition_is_rejected() -> None:
    ids = _ids()
    purchase = _purchase(ids)
    repository = FakeRetaceoRepository()
    created = await _create(repository, purchase)
    use_cases = RetaceoUseCases(repository, FakePurchaseRepository(purchase))

    with pytest.raises(BusinessRuleError) as exc_info:
        await use_cases.close_retaceo(ids["company"], created.id)

    assert exc_info.value.code == "retaceo_invalid_transition"


@pytest.mark.asyncio
async def test_get_missing_retaceo_returns_not_found() -> None:
    ids = _ids()
    use_cases = RetaceoUseCases(
        FakeRetaceoRepository(),
        FakePurchaseRepository(_purchase(ids)),
    )

    with pytest.raises(NotFoundError) as exc_info:
        await use_cases.get_retaceo(ids["company"], uuid.uuid4())

    assert exc_info.value.code == "retaceo_not_found"
