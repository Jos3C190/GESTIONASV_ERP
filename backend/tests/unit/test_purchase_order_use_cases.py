from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.application.purchase_orders import (
    PurchaseOrderExpenseDraft,
    PurchaseOrderLineDraft,
    PurchaseOrderUseCases,
)
from app.core.exceptions import BusinessRuleError, ValidationError
from app.domain.entities.purchase_order import PurchaseOrder, PurchaseOrderStatus
from app.domain.entities.purchase_quotation import PurchaseQuotationStatus
from app.domain.ports.purchase_order_repository import (
    PurchaseOrderDestinationReference,
    PurchaseOrderQuotationDetailReference,
    PurchaseOrderQuotationReference,
)


class FakePurchaseOrderRepository:
    def __init__(self) -> None:
        self.orders: dict[tuple[uuid.UUID, uuid.UUID], PurchaseOrder] = {}
        self.quotations: dict[tuple[uuid.UUID, uuid.UUID], PurchaseOrderQuotationReference] = {}
        self.destinations: dict[
            tuple[uuid.UUID, uuid.UUID, uuid.UUID], PurchaseOrderDestinationReference
        ] = {}
        self.expense_types: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.ordered: dict[tuple[uuid.UUID, uuid.UUID], dict[uuid.UUID, Decimal]] = {}
        self.advanced: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.next_number = 1

    async def list_orders(self, company_id, *, status=None, supplier_id=None, skip=0, limit=50):
        values = [
            order
            for (tenant, _), order in self.orders.items()
            if tenant == company_id
            and (status is None or order.status is status)
            and (supplier_id is None or order.supplier_id == supplier_id)
        ]
        return values[skip : skip + limit], len(values)

    async def get_order(self, company_id, order_id):
        return self.orders.get((company_id, order_id))

    async def get_order_for_update(self, company_id, order_id):
        return self.orders.get((company_id, order_id))

    async def allocate_next_code(self, company_id):
        code = f"OC-{self.next_number:05d}"
        self.next_number += 1
        return code

    async def get_quotation_reference_for_update(self, company_id, quotation_id):
        return self.quotations.get((company_id, quotation_id))

    async def get_destination_reference(self, company_id, branch_id, warehouse_id):
        return self.destinations.get((company_id, branch_id, warehouse_id))

    async def is_expense_type_active(self, company_id, expense_type_id):
        return (company_id, expense_type_id) in self.expense_types

    async def get_ordered_quantities(
        self,
        company_id,
        quotation_id,
        *,
        exclude_order_id=None,
    ):
        return dict(self.ordered.get((company_id, quotation_id), {}))

    async def add_order(self, order):
        self.orders[(order.company_id, order.id)] = order
        return order

    async def replace_draft(self, order):
        key = (order.company_id, order.id)
        if key not in self.orders:
            return None
        self.orders[key] = order
        return order

    async def update_status(self, company_id, order_id, status):
        current = self.orders.get((company_id, order_id))
        if current is None:
            return None
        updated = replace(current, status=status)
        self.orders[(company_id, order_id)] = updated
        return updated

    async def advance_purchase_request_order_statuses(self, company_id, quotation_id):
        self.advanced.append((company_id, quotation_id))


def _setup() -> tuple[
    FakePurchaseOrderRepository,
    uuid.UUID,
    uuid.UUID,
    uuid.UUID,
    uuid.UUID,
    uuid.UUID,
]:
    repository = FakePurchaseOrderRepository()
    company_id = uuid.uuid4()
    quotation_id = uuid.uuid4()
    quotation_detail_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    repository.quotations[(company_id, quotation_id)] = PurchaseOrderQuotationReference(
        id=quotation_id,
        supplier_id=7,
        currency="USD",
        payment_terms="30 días",
        status=PurchaseQuotationStatus.SELECTED,
        details=(
            PurchaseOrderQuotationDetailReference(
                id=quotation_detail_id,
                product_id=11,
                unit_id=3,
                quantity=Decimal("5"),
                available_quantity=Decimal("4"),
                unit_price=Decimal("10"),
                discount=Decimal("5"),
                subtotal=Decimal("50"),
                tax_rate=Decimal("13"),
                notes="Línea seleccionada",
            ),
        ),
    )
    repository.destinations[(company_id, branch_id, warehouse_id)] = (
        PurchaseOrderDestinationReference(
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            branch_is_active=True,
            branch_operational_status="active",
            warehouse_is_active=True,
            warehouse_operational_status="active",
            warehouse_storage_eligible=True,
        )
    )
    return (
        repository,
        company_id,
        quotation_id,
        quotation_detail_id,
        branch_id,
        warehouse_id,
    )


@pytest.mark.asyncio
async def test_create_draft_uses_selected_quotation_and_calculates_totals() -> None:
    repository, company_id, quotation_id, detail_id, branch_id, warehouse_id = _setup()
    expense_type_id = uuid.uuid4()
    repository.expense_types.add((company_id, expense_type_id))

    order = await PurchaseOrderUseCases(repository).create_draft(
        company_id=company_id,
        created_by_id=uuid.uuid4(),
        purchase_quotation_id=quotation_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        lines=(
            PurchaseOrderLineDraft(
                purchase_quotation_detail_id=detail_id,
                quantity=Decimal("2"),
            ),
        ),
        expenses=(
            PurchaseOrderExpenseDraft(
                expense_type_id=expense_type_id,
                amount=Decimal("3.25"),
                description="Flete",
            ),
        ),
    )

    assert order.code == "OC-00001"
    assert order.supplier_id == 7
    assert order.currency == "USD"
    assert order.payment_terms == "30 días"
    assert order.details[0].subtotal == Decimal("20.000000")
    assert order.details[0].discount == Decimal("2.000000")
    assert order.details[0].tax_amount == Decimal("2.340000")
    assert order.details[0].total == Decimal("20.340000")
    assert order.additional_expenses == Decimal("3.250000")
    assert order.total == Decimal("23.590000")


@pytest.mark.asyncio
async def test_create_draft_requires_selected_quotation() -> None:
    repository, company_id, quotation_id, detail_id, branch_id, warehouse_id = _setup()
    repository.quotations[(company_id, quotation_id)] = replace(
        repository.quotations[(company_id, quotation_id)],
        status=PurchaseQuotationStatus.RECEIVED,
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        await PurchaseOrderUseCases(repository).create_draft(
            company_id=company_id,
            created_by_id=uuid.uuid4(),
            purchase_quotation_id=quotation_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            lines=(
                PurchaseOrderLineDraft(
                    purchase_quotation_detail_id=detail_id,
                    quantity=Decimal("1"),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_order_quotation_not_selected"


@pytest.mark.asyncio
async def test_create_draft_rejects_invalid_destination() -> None:
    repository, company_id, quotation_id, detail_id, branch_id, warehouse_id = _setup()
    repository.destinations.clear()

    with pytest.raises(ValidationError) as exc_info:
        await PurchaseOrderUseCases(repository).create_draft(
            company_id=company_id,
            created_by_id=uuid.uuid4(),
            purchase_quotation_id=quotation_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            lines=(
                PurchaseOrderLineDraft(
                    purchase_quotation_detail_id=detail_id,
                    quantity=Decimal("1"),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_order_destination_invalid"


@pytest.mark.asyncio
async def test_create_draft_rejects_unavailable_warehouse() -> None:
    repository, company_id, quotation_id, detail_id, branch_id, warehouse_id = _setup()
    repository.destinations[(company_id, branch_id, warehouse_id)] = replace(
        repository.destinations[(company_id, branch_id, warehouse_id)],
        warehouse_storage_eligible=False,
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        await PurchaseOrderUseCases(repository).create_draft(
            company_id=company_id,
            created_by_id=uuid.uuid4(),
            purchase_quotation_id=quotation_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            lines=(
                PurchaseOrderLineDraft(
                    purchase_quotation_detail_id=detail_id,
                    quantity=Decimal("1"),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_order_warehouse_unavailable"


@pytest.mark.asyncio
async def test_create_draft_rejects_quantity_above_remaining_availability() -> None:
    repository, company_id, quotation_id, detail_id, branch_id, warehouse_id = _setup()
    repository.ordered[(company_id, quotation_id)] = {detail_id: Decimal("3")}

    with pytest.raises(BusinessRuleError) as exc_info:
        await PurchaseOrderUseCases(repository).create_draft(
            company_id=company_id,
            created_by_id=uuid.uuid4(),
            purchase_quotation_id=quotation_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            lines=(
                PurchaseOrderLineDraft(
                    purchase_quotation_detail_id=detail_id,
                    quantity=Decimal("2"),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_order_quantity_exceeded"


@pytest.mark.asyncio
async def test_create_draft_rejects_inactive_expense_type() -> None:
    repository, company_id, quotation_id, detail_id, branch_id, warehouse_id = _setup()

    with pytest.raises(ValidationError) as exc_info:
        await PurchaseOrderUseCases(repository).create_draft(
            company_id=company_id,
            created_by_id=uuid.uuid4(),
            purchase_quotation_id=quotation_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            lines=(
                PurchaseOrderLineDraft(
                    purchase_quotation_detail_id=detail_id,
                    quantity=Decimal("1"),
                ),
            ),
            expenses=(
                PurchaseOrderExpenseDraft(
                    expense_type_id=uuid.uuid4(),
                    amount=Decimal("1"),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_order_expense_type_invalid"


@pytest.mark.asyncio
async def test_update_draft_recalculates_commercial_values() -> None:
    repository, company_id, quotation_id, detail_id, branch_id, warehouse_id = _setup()
    use_cases = PurchaseOrderUseCases(repository)
    created = await use_cases.create_draft(
        company_id=company_id,
        created_by_id=uuid.uuid4(),
        purchase_quotation_id=quotation_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        lines=(
            PurchaseOrderLineDraft(
                purchase_quotation_detail_id=detail_id,
                quantity=Decimal("1"),
            ),
        ),
    )

    updated = await use_cases.update_draft(
        company_id=company_id,
        order_id=created.id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        lines=(
            PurchaseOrderLineDraft(
                purchase_quotation_detail_id=detail_id,
                quantity=Decimal("2"),
            ),
        ),
        notes="Actualizada",
    )

    assert updated.code == created.code
    assert updated.details[0].quantity == Decimal("2")
    assert updated.total == Decimal("20.340000")
    assert updated.notes == "Actualizada"


@pytest.mark.asyncio
async def test_update_non_draft_is_rejected() -> None:
    repository, company_id, quotation_id, detail_id, branch_id, warehouse_id = _setup()
    use_cases = PurchaseOrderUseCases(repository)
    created = await use_cases.create_draft(
        company_id=company_id,
        created_by_id=uuid.uuid4(),
        purchase_quotation_id=quotation_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        lines=(
            PurchaseOrderLineDraft(
                purchase_quotation_detail_id=detail_id,
                quantity=Decimal("1"),
            ),
        ),
    )
    repository.orders[(company_id, created.id)] = replace(
        created,
        status=PurchaseOrderStatus.PENDING_APPROVAL,
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        await use_cases.update_draft(
            company_id=company_id,
            order_id=created.id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            lines=(
                PurchaseOrderLineDraft(
                    purchase_quotation_detail_id=detail_id,
                    quantity=Decimal("1"),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_order_not_editable"


@pytest.mark.asyncio
async def test_workflow_submit_approve_send_advances_purchase_requests() -> None:
    repository, company_id, quotation_id, detail_id, branch_id, warehouse_id = _setup()
    use_cases = PurchaseOrderUseCases(repository)
    order = await use_cases.create_draft(
        company_id=company_id,
        created_by_id=uuid.uuid4(),
        purchase_quotation_id=quotation_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        lines=(
            PurchaseOrderLineDraft(
                purchase_quotation_detail_id=detail_id,
                quantity=Decimal("1"),
            ),
        ),
    )
    submitted = await use_cases.submit_order(company_id, order.id)
    approved = await use_cases.approve_order(company_id, order.id)
    sent = await use_cases.send_order(company_id, order.id)

    assert submitted.status is PurchaseOrderStatus.PENDING_APPROVAL
    assert approved.status is PurchaseOrderStatus.APPROVED
    assert sent.status is PurchaseOrderStatus.SENT
    assert repository.advanced == [(company_id, quotation_id)]


@pytest.mark.asyncio
async def test_cancel_after_send_is_rejected() -> None:
    repository, company_id, quotation_id, detail_id, branch_id, warehouse_id = _setup()
    use_cases = PurchaseOrderUseCases(repository)
    order = await use_cases.create_draft(
        company_id=company_id,
        created_by_id=uuid.uuid4(),
        purchase_quotation_id=quotation_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        lines=(
            PurchaseOrderLineDraft(
                purchase_quotation_detail_id=detail_id,
                quantity=Decimal("1"),
            ),
        ),
    )
    await use_cases.submit_order(company_id, order.id)
    await use_cases.approve_order(company_id, order.id)
    await use_cases.send_order(company_id, order.id)

    with pytest.raises(BusinessRuleError) as exc_info:
        await use_cases.cancel_order(company_id, order.id)
    assert exc_info.value.code == "purchase_order_invalid_transition"


@pytest.mark.asyncio
async def test_expected_date_before_order_date_is_rejected() -> None:
    repository, company_id, quotation_id, detail_id, branch_id, warehouse_id = _setup()

    with pytest.raises(ValidationError) as exc_info:
        await PurchaseOrderUseCases(repository).create_draft(
            company_id=company_id,
            created_by_id=uuid.uuid4(),
            purchase_quotation_id=quotation_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            expected_date=datetime.now(UTC) - timedelta(days=1),
            lines=(
                PurchaseOrderLineDraft(
                    purchase_quotation_detail_id=detail_id,
                    quantity=Decimal("1"),
                ),
            ),
        )
    assert exc_info.value.code == "purchase_order_invalid"
