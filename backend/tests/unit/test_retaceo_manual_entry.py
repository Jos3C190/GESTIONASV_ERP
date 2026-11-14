"""Manual amounts, separate budgets, source identity and partial expense reservations."""

import uuid
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from app.api.v1.schemas.retaceo import RetaceoCostInput, RetaceoCreate, RetaceoUpdate
from app.application.purchase_orders.actual_expenses import ActualExpenseUseCases
from app.application.retaceos.use_cases import RetaceoCostDraft, RetaceoUseCases
from app.core.exceptions import BusinessRuleError, ValidationError
from app.domain.entities.actual_expense import ActualExpenseClosure, ActualPurchaseExpense
from app.domain.entities.purchase import PurchaseInventoryWorkflow, PurchaseStatus
from app.domain.entities.purchase_order import PurchaseOrderStatus
from app.domain.entities.retaceo import (
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


def with_fob(purchase, values):
    """Give each receipt line a simple net value (subtotal minus discount)."""
    return replace(
        purchase,
        details=tuple(
            replace(line, subtotal=value, discount=D("0"))
            for line, value in zip(purchase.details, values, strict=True)
        ),
    )


def setup():
    purchase = replace(
        with_fob(_purchase(_ids(), status=PurchaseStatus.RECEIVED), (D("10"), D("30"))),
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
    }


@pytest.mark.asyncio
async def test_amounts_are_typed_and_distribution_by_fob_reconciles_without_budget_copy():
    purchase, _, _, cases = setup()
    item = await cases.create_draft(**inputs(purchase))
    assert item.manual_entry
    assert item.total_fob == D("40")  # Net value of the receipt lines (10 and 30).
    assert item.total_freight == D("20")
    assert item.total_dai == D("8")
    assert item.total_cost == D("68")
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
async def test_fob_is_rebuilt_from_the_purchase_receipt_on_every_save():
    purchase, _, _, cases = setup()
    item = await cases.create_draft(**inputs(purchase))
    assert [row.cost_fob for row in item.details] == [D("10"), D("30")]
    # The receipt changes (for example a corrected accepted value): the next save follows it.
    cases._purchases.purchase = with_fob(purchase, (D("20"), D("20")))
    saved = await cases.update_draft(
        company_id=purchase.company_id,
        retaceo_id=item.id,
        total_freight=D("20"),
        total_expenses=D("0"),
        total_dai=D("8"),
    )
    assert [row.cost_fob for row in saved.details] == [D("20"), D("20")]
    assert saved.total_fob == D("40")
    assert [row.freight for row in saved.details] == [D("10"), D("10")]
    assert [row.dai for row in saved.details] == [D("4"), D("4")]


@pytest.mark.asyncio
async def test_notes_never_change_the_fob_of_a_historical_receipt():
    purchase = with_fob(_purchase(_ids(), status=PurchaseStatus.CLOSED), (D("10"), D("30")))
    cases = RetaceoUseCases(FakeRetaceoRepository(), FakePurchaseRepository(purchase))
    item = await cases.create_draft(
        **inputs(purchase),
        notes="Nota larga con más de veinte caracteres para comprobar que no regulariza el FOB.",
    )
    assert item.total_fob == D("40")
    assert [row.cost_fob for row in item.details] == [D("10"), D("30")]
    assert purchase.details[0].subtotal == D("10")


@pytest.mark.asyncio
async def test_lumped_other_expense_is_rejected_on_creation():
    purchase, _, _, cases = setup()
    with pytest.raises(ValidationError, match="Desglosa"):
        await cases.create_draft(**(inputs(purchase) | {"total_expenses": D("50")}))


@pytest.mark.parametrize("field", ["total_freight", "total_dai"])
def test_fixed_components_cannot_be_omitted_from_api(field):
    values = {
        "purchase_id": uuid.uuid4(),
        "total_freight": "0",
        "total_expenses": "0",
        "total_dai": "0",
    }
    del values[field]
    with pytest.raises(SchemaError):
        RetaceoCreate(**values)


@pytest.mark.parametrize("field", ["total_freight", "total_dai"])
@pytest.mark.parametrize("value", ["-1", "-0.000001"])
def test_negative_fixed_components_are_rejected_by_the_api(field, value):
    values = {"total_freight": "0", "total_expenses": "0", "total_dai": "0", field: value}
    with pytest.raises(SchemaError):
        RetaceoCreate(purchase_id=uuid.uuid4(), **values)
    with pytest.raises(SchemaError):
        RetaceoUpdate(**values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("import_vat", "0"),
        ("calculation_mode", "manual"),
        ("dai_rate", "10"),
        ("vat_rate", "13"),
        ("fob_lines", []),
    ],
)
def test_retired_fields_are_rejected_by_create_and_update(field, value):
    base = {"total_freight": "0", "total_expenses": "0", "total_dai": "0"}
    with pytest.raises(SchemaError):
        RetaceoCreate(purchase_id=uuid.uuid4(), **base, **{field: value})
    with pytest.raises(SchemaError):
        RetaceoUpdate(**base, **{field: value})


def test_cost_input_rejects_allocations_and_import_vat_classification():
    row = {"title": "Gasolina", "amount": "5", "classification": "expense"}
    assert RetaceoCostInput(**row).classification is RetaceoCostClass.EXPENSE
    with pytest.raises(SchemaError):
        RetaceoCostInput(**row, allocations=[])
    with pytest.raises(SchemaError):
        RetaceoCostInput(**(row | {"classification": "import_vat"}))


@pytest.mark.asyncio
async def test_explicit_zero_fixed_components_are_valid_without_fake_cost_rows():
    purchase, _, _, cases = setup()
    item = await cases.create_draft(
        **(inputs(purchase) | {"total_freight": D("0"), "total_dai": D("0")})
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
        RetaceoCostDraft(row.id, row.classification, row.title, row.amount) for row in current.costs
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
            costs=(*drafts, expense),
        )


@pytest.mark.asyncio
async def test_partial_actual_expense_survives_edit_and_is_split_by_fob():
    purchase, _, orders, cases, source, current, drafts = await draft_with_actual()
    orders.used = {source.id: D("60")}
    expense = RetaceoCostDraft(
        None,
        RetaceoCostClass.EXPENSE,
        "Gasolina",
        D("40"),
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
        costs=(*drafts, expense),
    )
    assert saved.total_fob == D("40")
    assert saved.total_expenses == D("40")
    assert saved.total_cost == D("108")
    # The server splits every cost by FOB (10 and 30); nothing is typed per line.
    split = {
        cost.classification: [row.amount for row in cost.allocations]
        for cost in saved.costs
        if cost.is_active
    }
    assert split[RetaceoCostClass.EXPENSE] == [D("10"), D("30")]
    assert split[RetaceoCostClass.FREIGHT] == [D("5"), D("15")]
    assert split[RetaceoCostClass.DAI] == [D("2"), D("6")]


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
async def test_calculate_rejects_a_draft_with_hand_made_allocations_until_it_is_saved_again():
    purchase, repository, _, cases = setup()
    current = await cases.create_draft(**inputs(purchase))
    freight = next(
        cost for cost in current.costs if cost.classification is RetaceoCostClass.FREIGHT
    )
    hand_made = tuple(
        replace(row, amount=D("10")) for row in freight.allocations
    )  # Typed 10/10 instead of the 5/15 that FOB 10/30 produces.
    repository.items[current.id] = replace(
        current,
        costs=tuple(
            replace(cost, allocations=hand_made) if cost.id == freight.id else cost
            for cost in current.costs
        ),
    )
    with pytest.raises(BusinessRuleError) as failure:
        await cases.calculate_retaceo(purchase.company_id, current.id)
    assert failure.value.code == "retaceo_cost_allocation_incomplete"
    assert "Guarda el borrador de nuevo" in str(failure.value)
    await cases.update_draft(
        company_id=purchase.company_id,
        retaceo_id=current.id,
        total_freight=D("20"),
        total_expenses=D("0"),
        total_dai=D("8"),
    )
    calculated = await cases.calculate_retaceo(purchase.company_id, current.id)
    assert calculated.status is RetaceoStatus.CALCULATED


@pytest.mark.asyncio
async def test_calculate_rejects_a_draft_whose_stored_fob_no_longer_matches_the_receipt():
    purchase, _, _, cases = setup()
    current = await cases.create_draft(**inputs(purchase))
    cases._purchases.purchase = with_fob(purchase, (D("20"), D("20")))
    with pytest.raises(BusinessRuleError) as failure:
        await cases.calculate_retaceo(purchase.company_id, current.id)
    assert failure.value.code == "retaceo_cost_allocation_incomplete"
    saved = await cases.update_draft(
        company_id=purchase.company_id,
        retaceo_id=current.id,
        total_freight=D("20"),
        total_expenses=D("0"),
        total_dai=D("8"),
    )
    assert [row.cost_fob for row in saved.details] == [D("20"), D("20")]
    calculated = await cases.calculate_retaceo(purchase.company_id, current.id)
    assert calculated.status is RetaceoStatus.CALCULATED


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


@pytest.mark.asyncio
async def test_insurance_is_not_an_additional_expense_of_a_retaceo_but_stays_in_the_order_log():
    from app.domain.entities.actual_expense import (
        is_excluded_retaceo_expense_category,
        is_fixed_retaceo_category,
    )

    for name in ("Seguro", "seguro de carga", "Flete", "DAI"):
        assert is_excluded_retaceo_expense_category(name)
    assert not is_excluded_retaceo_expense_category("Agente aduanal")
    assert not is_fixed_retaceo_category("Seguro")  # The order log keeps its own predicate.

    purchase, _, orders, cases, _, current, drafts = await draft_with_actual()
    orders.category.name = "Seguro"
    insurance = RetaceoCostDraft(
        None,
        RetaceoCostClass.EXPENSE,
        "Seguro de carga",
        D("5"),
        description="Póliza del viaje",
        expense_type_id=orders.category.id,
        incurred_on=date(2026, 10, 27),
    )
    with pytest.raises(
        ValidationError, match="flete y seguro y DAI tienen campos propios"
    ) as raised:
        await cases.update_draft(
            company_id=purchase.company_id,
            retaceo_id=current.id,
            total_freight=D("20"),
            total_expenses=D("5"),
            total_dai=D("8"),
            costs=(*drafts, insurance),
        )
    assert raised.value.code == "retaceo_expense_category_invalid"
    # The same category can still be recorded as an actual expense of the order.
    expense = await ActualExpenseUseCases(orders).create(
        company_id=purchase.company_id,
        order_id=orders.order_id,
        expense_type_id=orders.category.id,
        amount=D("12"),
        incurred_on=date(2026, 10, 20),
        reference="SEG-12",
        description="Seguro de la carga",
    )
    assert expense.amount == D("12")
