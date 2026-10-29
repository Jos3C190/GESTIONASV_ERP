"""Manual amounts, separate budgets, source identity and partial expense reservations."""

import uuid
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from app.api.v1.schemas.retaceo import RetaceoCreate
from app.application.purchase_orders.actual_expenses import ActualExpenseUseCases
from app.application.retaceos.use_cases import RetaceoCostDraft, RetaceoFobDraft, RetaceoUseCases
from app.core.exceptions import BusinessRuleError, ValidationError
from app.domain.entities.actual_expense import ActualExpenseClosure, ActualPurchaseExpense
from app.domain.entities.purchase import PurchaseInventoryWorkflow, PurchaseStatus
from app.domain.entities.purchase_order import PurchaseOrderStatus
from app.domain.entities.retaceo import (
    RetaceoCostAllocation,
    RetaceoCostClass,
    RetaceoCostDocument,
    RetaceoImportData,
    RetaceoStatus,
)
from pydantic import ValidationError as SchemaError

from tests.unit.test_retaceo_use_cases import (
    FakePurchaseRepository,
    FakeRetaceoRepository,
    _ids,
    _purchase,
)

D = Decimal


class Orders:
    def __init__(self, order_id):
        self.order_id = order_id
        self.category = SimpleNamespace(id=uuid.uuid4(), name="Gasolina", is_active=True)
        self.status = PurchaseOrderStatus.SENT
        self.actuals = ()
        self.used = {}
        self.closure = None
        self.locked = False

    async def get_order_for_update(self, *_):
        self.locked = True
        return SimpleNamespace(id=self.order_id, status=self.status, currency="USD")

    async def get_actual_expense_closure(self, *_):
        return self.closure

    async def get_order(self, *_):
        raise AssertionError("The manual entry path must never copy budget amounts")

    async def get_expense_type(self, company_id, category_id):
        return self.category if category_id == self.category.id else None

    async def list_actual_expenses(self, *_):
        return self.actuals

    async def actual_expense_usage(self, *_, **__):
        return self.used

    async def add_actual_expense(self, expense):
        self.actuals = (*self.actuals, expense)
        return expense


def setup():
    purchase = replace(
        _purchase(_ids(), status=PurchaseStatus.RECEIVED),
        inventory_workflow=PurchaseInventoryWorkflow.AFTER_RETACEO,
    )
    repository = FakeRetaceoRepository()
    orders = Orders(purchase.purchase_order_id)
    cases = RetaceoUseCases(repository, FakePurchaseRepository(purchase), orders)
    return purchase, repository, orders, cases


def inputs(purchase):
    return {
        "company_id": purchase.company_id,
        "created_by_id": purchase.created_by_id,
        "purchase_id": purchase.id,
        "total_freight": D("20"),
        "total_expenses": D("0"),
        "total_dai": D("8"),
        "import_vat": D("13"),
        "fob_lines": tuple(
            RetaceoFobDraft(line.id, value)
            for line, value in zip(purchase.details, (D("10"), D("30")), strict=True)
        ),
    }


@pytest.mark.asyncio
async def test_amounts_are_manual_and_fixed_distribution_reconciles_without_budget_copy():
    purchase, _, _, cases = setup()
    item = await cases.create_draft(**inputs(purchase))
    assert item.manual_entry
    assert item.total_fob == D("40")  # Purchase itself holds 55,780 net.
    assert item.total_freight == D("20")
    assert item.total_dai == D("8")
    assert item.total_cost == D("68")
    assert item.import_vat == D("13")
    assert [row.freight for row in item.details] == [D("5"), D("15")]
    assert [row.dai for row in item.details] == [D("2"), D("6")]
    assert all(row.source_purchase_order_expense_id is None for row in item.costs)


@pytest.mark.asyncio
async def test_retaceo_can_close_with_no_other_expenses_in_the_order_log():
    purchase, _, orders, cases = setup()
    current = await cases.create_draft(**inputs(purchase))
    assert orders.actuals == ()

    await cases.calculate_retaceo(purchase.company_id, current.id)
    await cases.verify_retaceo(purchase.company_id, current.id)
    closed = await cases.close_retaceo(purchase.company_id, current.id)

    assert closed.status is RetaceoStatus.CLOSED
    assert closed.total_expenses == D("0")
    assert closed.total_cost == D("68")
    assert orders.actuals == ()


@pytest.mark.asyncio
async def test_missing_fob_does_not_fall_back_to_purchase_amount():
    purchase, _, _, cases = setup()
    values = inputs(purchase)
    del values["fob_lines"]
    with pytest.raises(ValidationError, match="manualmente"):
        await cases.create_draft(**values)


@pytest.mark.asyncio
async def test_legacy_fob_correction_requires_a_reason_and_preserves_original_purchase():
    purchase = _purchase(_ids(), status=PurchaseStatus.CLOSED)
    purchase = replace(
        purchase,
        details=tuple(
            replace(line, discount=line.subtotal, total=line.tax_amount)
            for line in purchase.details
        ),
    )
    repository = FakeRetaceoRepository()
    cases = RetaceoUseCases(repository, FakePurchaseRepository(purchase))
    values = inputs(purchase)
    with pytest.raises(BusinessRuleError, match="20 caracteres"):
        await cases.create_draft(**values)
    item = await cases.create_draft(
        **values, notes="Descuento capturado por error; se regulariza con la factura confirmada."
    )
    assert item.documents_historical_fob_correction
    assert item.total_fob == D("40")
    assert all(line.discount == line.subtotal for line in purchase.details)


@pytest.mark.asyncio
async def test_lumped_other_expense_is_rejected_on_creation():
    purchase, _, _, cases = setup()
    with pytest.raises(ValidationError, match="Desglose"):
        await cases.create_draft(**(inputs(purchase) | {"total_expenses": D("50")}))


@pytest.mark.parametrize("field", ["total_freight", "total_dai"])
def test_fixed_components_cannot_be_omitted_from_api(field):
    values = {
        "purchase_id": uuid.uuid4(),
        "total_freight": "0",
        "total_expenses": "0",
        "total_dai": "0",
        "import_vat": "0",
    }
    del values[field]
    with pytest.raises(SchemaError):
        RetaceoCreate(**values)


@pytest.mark.asyncio
async def test_explicit_zero_fixed_components_are_valid_without_fake_cost_rows():
    purchase, _, _, cases = setup()
    item = await cases.create_draft(
        **(inputs(purchase) | {"total_freight": D("0"), "total_dai": D("0"), "import_vat": D("0")})
    )
    assert item.total_cost == D("40")
    assert item.costs == ()


@pytest.mark.asyncio
async def test_receipt_invoice_cannot_be_replaced_from_retaceo():
    purchase, _, _, cases = setup()
    with pytest.raises(BusinessRuleError, match="factura"):
        await cases.create_draft(
            **(
                inputs(purchase)
                | {"import_data": RetaceoImportData(import_invoice_number="DIFFERENT")}
            )
        )


async def draft_with_actual():
    purchase, repository, orders, cases = setup()
    source = ActualPurchaseExpense(
        uuid.uuid4(),
        purchase.company_id,
        purchase.purchase_order_id,
        orders.category.id,
        D("100"),
        date(2026, 10, 20),
        "REC-100",
        "Gasolina del viaje",
    )
    orders.actuals = (source,)
    current = await cases.create_draft(**inputs(purchase))
    drafts = tuple(
        RetaceoCostDraft(row.id, row.classification, row.title, row.amount, row.allocations)
        for row in current.costs
    )
    return purchase, repository, orders, cases, source, current, drafts


@pytest.mark.asyncio
async def test_other_expense_cannot_exceed_actual_balance_reserved_by_another_receipt():
    purchase, _, orders, cases, source, current, drafts = await draft_with_actual()
    orders.used = {source.id: D("60")}
    expense = RetaceoCostDraft(
        None,
        RetaceoCostClass.EXPENSE,
        "Gasolina",
        D("41"),
        (RetaceoCostAllocation(purchase.details[0].id, D("41")),),
        description="Recibo del viaje",
        expense_type_id=source.expense_type_id,
        incurred_on=source.incurred_on,
        source_purchase_order_expense_id=source.id,
    )
    with pytest.raises(BusinessRuleError, match="saldo"):
        await cases.update_draft(
            company_id=purchase.company_id,
            retaceo_id=current.id,
            total_freight=D("20"),
            total_expenses=D("41"),
            total_dai=D("8"),
            import_vat=D("13"),
            costs=(*drafts, expense),
        )


@pytest.mark.asyncio
async def test_partial_actual_expense_and_manual_fob_survive_edit():
    purchase, _, orders, cases, source, current, drafts = await draft_with_actual()
    orders.used = {source.id: D("60")}
    expense = RetaceoCostDraft(
        None,
        RetaceoCostClass.EXPENSE,
        "Gasolina",
        D("40"),
        (RetaceoCostAllocation(purchase.details[0].id, D("40")),),
        description="Recibo del viaje",
        expense_type_id=source.expense_type_id,
        incurred_on=source.incurred_on,
        source_purchase_order_expense_id=source.id,
    )
    saved = await cases.update_draft(
        company_id=purchase.company_id,
        retaceo_id=current.id,
        total_freight=D("20"),
        total_expenses=D("40"),
        total_dai=D("8"),
        import_vat=D("13"),
        costs=(*drafts, expense),
    )
    assert saved.total_fob == D("40")
    assert saved.total_expenses == D("40")
    assert saved.total_cost == D("108")


@pytest.mark.asyncio
async def test_positive_fixed_amount_requires_its_component_but_no_attachment():
    purchase, _, _, cases = setup()
    current = await cases.create_draft(**inputs(purchase))
    with pytest.raises(ValidationError, match="único componente"):
        await cases.update_draft(
            company_id=purchase.company_id,
            retaceo_id=current.id,
            total_freight=D("50"),
            total_expenses=D("0"),
            total_dai=D("8"),
            import_vat=D("13"),
        )
    calculated = await cases.calculate_retaceo(purchase.company_id, current.id)
    assert calculated.status is RetaceoStatus.CALCULATED
    assert calculated.total_cost == D("68")
    assert all(not cost.documents for cost in calculated.costs)


@pytest.mark.asyncio
async def test_other_expenses_can_calculate_without_attachments():
    purchase, _, orders, cases, _, current, drafts = await draft_with_actual()
    expense = RetaceoCostDraft(
        None,
        RetaceoCostClass.EXPENSE,
        "Gasolina",
        D("5"),
        (RetaceoCostAllocation(purchase.details[0].id, D("5")),),
        description="Gasolina del viaje",
        expense_type_id=orders.category.id,
        incurred_on=date(2026, 10, 27),
    )
    await cases.update_draft(
        company_id=purchase.company_id,
        retaceo_id=current.id,
        total_freight=D("20"),
        total_expenses=D("5"),
        total_dai=D("8"),
        import_vat=D("13"),
        costs=(*drafts, expense),
    )
    calculated = await cases.calculate_retaceo(purchase.company_id, current.id)
    assert calculated.total_cost == D("73")
    assert all(not cost.documents for cost in calculated.costs)


@pytest.mark.asyncio
async def test_optional_attachments_do_not_bypass_allocation_validation():
    purchase, repository, _, cases = setup()
    current = await cases.create_draft(**inputs(purchase))
    repository.items[current.id] = replace(
        current, costs=(replace(current.costs[0], allocations=()), *current.costs[1:])
    )
    with pytest.raises(BusinessRuleError) as failure:
        await cases.calculate_retaceo(purchase.company_id, current.id)
    assert failure.value.code == "retaceo_cost_allocation_incomplete"


@pytest.mark.asyncio
async def test_an_optional_file_started_by_user_must_finish_or_be_removed():
    purchase, repository, _, cases = setup()
    current = await cases.create_draft(**inputs(purchase))
    cost = current.costs[0]
    attachment = RetaceoCostDocument(
        uuid.uuid4(), cost.id, uuid.uuid4(), "Flete.pdf", "application/pdf"
    )
    repository.items[current.id] = replace(
        current, costs=(replace(cost, documents=(attachment,)), *current.costs[1:])
    )
    with pytest.raises(BusinessRuleError) as failure:
        await cases.calculate_retaceo(purchase.company_id, current.id)
    assert failure.value.code == "retaceo_cost_document_incomplete"


@pytest.mark.asyncio
async def test_actual_expense_available_during_wait_and_cannot_use_fixed_category():
    purchase, _, orders, _ = setup()
    cases = ActualExpenseUseCases(orders)
    values = {
        "company_id": purchase.company_id,
        "order_id": orders.order_id,
        "expense_type_id": orders.category.id,
        "amount": D("12"),
        "incurred_on": date(2026, 10, 20),
        "reference": "REC-12",
        "description": "Gasolina",
    }
    expense = await cases.create(**values)
    assert expense.amount == D("12")
    assert orders.status is PurchaseOrderStatus.SENT
    orders.category.name = "Flete"
    with pytest.raises(ValidationError, match="campos propios"):
        await cases.create(**values)
    orders.status = PurchaseOrderStatus.DRAFT
    with pytest.raises(BusinessRuleError, match="aprobación"):
        await cases.create(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.RECEIVED])
async def test_closed_retaceo_blocks_new_actual_expenses_even_if_order_allows_them(status):
    purchase, _, orders, _ = setup()
    orders.status = status
    orders.closure = ActualExpenseClosure(uuid.uuid4(), "RET-00021")
    cases = ActualExpenseUseCases(orders)
    availability = await cases.availability(
        purchase.company_id, await orders.get_order_for_update()
    )
    assert not availability.can_record
    assert availability.closed_retaceo_id == orders.closure.retaceo_id
    assert availability.closed_retaceo_code == "RET-00021"
    with pytest.raises(BusinessRuleError) as failure:
        await cases.create(
            company_id=purchase.company_id,
            order_id=orders.order_id,
            expense_type_id=orders.category.id,
            amount=D("33"),
            incurred_on=date(2026, 10, 27),
            reference="333",
            description="Gasto después del cierre",
        )
    assert failure.value.code == "actual_expense_retaceo_closed"
    assert orders.actuals == ()
    assert orders.locked


@pytest.mark.asyncio
async def test_retaceo_closure_locks_order_before_changing_status():
    purchase, repository, orders, cases = setup()
    current = await cases.create_draft(**inputs(purchase))
    repository.items[current.id] = replace(current, status=RetaceoStatus.VERIFIED)
    orders.locked = False
    original_update = repository.update_status

    async def update_after_order_lock(*args):
        assert orders.locked
        return await original_update(*args)

    repository.update_status = update_after_order_lock
    closed = await cases.close_retaceo(purchase.company_id, current.id)
    assert closed.status is RetaceoStatus.CLOSED


@pytest.mark.parametrize(("allocated", "remaining"), [("0", "33"), ("12", "21"), ("33", "0")])
def test_actual_expense_exposes_unassigned_amount_without_changing_original(allocated, remaining):
    expense = ActualPurchaseExpense(
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        D("33"),
        date(2026, 10, 27),
        "333",
        "Gasto real",
        allocated_amount=D(allocated),
    )
    assert expense.unallocated_amount == D(remaining)
    assert expense.amount == D("33")
