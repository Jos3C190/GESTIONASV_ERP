"""Financial invariants of company/product weighted moving averages."""

from decimal import Decimal
from uuid import uuid4

import pytest
from app.api.v1.schemas.inventory_valuation import ValuationOpeningIn
from app.domain.entities.inventory import InventoryOperationError
from app.domain.entities.inventory_valuation import ValuationEvent, adjustment_breakdown, project
from pydantic import ValidationError

pytestmark = pytest.mark.unit


def event(kind, quantity="0", value="0", original=None):
    return ValuationEvent(uuid4(), kind, Decimal(quantity), Decimal(value), original)


def test_supplier_return_consumes_average_and_separates_credit():
    first, second = event("receipt", "10", "100"), event("receipt", "10", "200")
    sale, returned = event("issue", "15"), event("supplier_return", "5")
    credit = event("supplier_credit", value="100", original=returned.id)
    result = project([first, second, sale, returned, credit])
    assert result.costs[sale.id] == Decimal("225")
    assert result.costs[returned.id] == Decimal("75")
    assert result.supplier_credits[returned.id] - result.costs[returned.id] == Decimal("25")
    assert result.quantity == result.value == result.average == 0


def test_late_retaceo_adjusts_remaining_stock_and_original_issues():
    receipt = event("receipt", "10", "100")
    issue = event("issue", "6")
    before = project([receipt, issue])
    adjustment = event("cost_adjustment", value="20", original=receipt.id)
    after = project([receipt, issue, adjustment])
    assert after.quantity == before.quantity == 4
    assert after.value - before.value == 8
    assert after.costs[issue.id] - before.costs[issue.id] == 12
    assert adjustment_breakdown([receipt, issue], before, after) == [
        {"event_id": str(issue.id), "kind": "issue", "cost_delta": "12.000000"}
    ]


def test_late_retaceo_follows_average_instead_of_physical_lot():
    first, second = event("receipt", "10", "100"), event("receipt", "10", "200")
    issue = event("issue", "10")
    result = project(
        [first, second, issue, event("cost_adjustment", value="40", original=first.id)]
    )
    assert result.value == result.costs[issue.id] == 170
    assert result.average == 17


def test_revaluation_after_stock_exhaustion_does_not_change_later_unrelated_stock():
    first, issue, second = (
        event("receipt", "10", "100"),
        event("issue", "10"),
        event("receipt", "2", "50"),
    )
    result = project(
        [first, issue, second, event("cost_adjustment", value="30", original=first.id)]
    )
    assert result.value == 50
    assert result.costs[issue.id] == 130


def test_customer_return_uses_original_issue_including_retaceo():
    receipt = event("receipt", "10", "100")
    sale = event("issue", "6")
    returned = event("customer_return", "2", original=sale.id)
    events = [receipt, sale, event("receipt", "10", "200"), returned]
    before = project(events)
    after = project([*events, event("cost_adjustment", value="20", original=receipt.id)])
    assert before.costs[returned.id] == 20
    assert after.costs[returned.id] == 24
    deltas = adjustment_breakdown(events, before, after)
    assert sum(Decimal(row["cost_delta"]) for row in deltas) == 8
    assert after.value - before.value == 12


def test_repeated_partial_returns_conserve_micro_cost():
    receipt, sale = event("receipt", "5", "0.000003"), event("issue", "5")
    returns = [event("customer_return", "1", original=sale.id) for _ in range(5)]
    result = project([receipt, sale, *returns])
    assert result.quantity == 5
    assert result.value == Decimal("0.000003")
    assert all(result.costs[row.id] >= 0 for row in returns)


def test_partial_issue_and_final_issue_conserve_cost():
    receipt = event("opening", "3", "10")
    issues = [event("issue", "1") for _ in range(3)]
    result = project([receipt, *issues])
    assert sum(result.costs[row.id] for row in issues) == 10
    assert result.quantity == result.value == 0


@pytest.mark.parametrize(
    ("quantity", "value"),
    [("NaN", "1"), ("1", "Infinity"), ("0.0000001", "1"), ("1", "-1"), ("0", "1")],
)
def test_invalid_receipt_cannot_enter_ledger(quantity, value):
    with pytest.raises(InventoryOperationError):
        project([event("receipt", quantity, value)])


def test_overselling_rejected():
    with pytest.raises(InventoryOperationError):
        project([event("opening", "1", "4"), event("issue", "2")])


def test_return_requires_actual_prior_sale_and_cannot_exceed_quantity():
    receipt, sale = event("receipt", "4", "8"), event("issue", "4")
    for source, quantity in [(receipt.id, "1"), (sale.id, "5"), (uuid4(), "1")]:
        with pytest.raises(InventoryOperationError):
            project([receipt, sale, event("customer_return", quantity, original=source)])


def test_duplicate_events_rejected():
    receipt = event("receipt", "1", "5")
    with pytest.raises(InventoryOperationError):
        project([receipt, receipt])


def test_cost_adjustment_cannot_modify_quantity_or_create_negative_cost():
    receipt = event("receipt", "1", "5")
    for quantity, value in [("1", "2"), ("0", "-6")]:
        with pytest.raises(InventoryOperationError):
            project([receipt, event("cost_adjustment", quantity, value, receipt.id)])


def test_credit_cannot_be_settled_twice():
    receipt, returned = event("receipt", "1", "5"), event("supplier_return", "1")
    settlements = [event("supplier_credit", value="5", original=returned.id) for _ in range(2)]
    with pytest.raises(InventoryOperationError):
        project([receipt, returned, *settlements])


def test_supplier_return_cost_reconciles_after_late_retaceo():
    receipt, returned = event("receipt", "1", "5"), event("supplier_return", "1")
    credit = event("supplier_credit", value="6", original=returned.id)
    result = project(
        [receipt, returned, credit, event("cost_adjustment", value="2", original=receipt.id)]
    )
    assert result.value == result.quantity == 0
    assert result.supplier_credits[returned.id] == 6
    assert result.costs[returned.id] == 7


def test_initial_opening_requires_explicit_approval_and_snapshot():
    with pytest.raises(ValidationError):
        ValuationOpeningIn(
            currency="USD",
            reference="Acta 1",
            approved=False,
            snapshot_fingerprint="a" * 64,
            lines=[],
        )
    with pytest.raises(ValidationError):
        ValuationOpeningIn(
            currency="USD", reference="Acta 1", approved=True, snapshot_fingerprint="", lines=[]
        )
