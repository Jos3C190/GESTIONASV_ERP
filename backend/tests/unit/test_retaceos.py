from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.domain.entities.retaceo import (
    Retaceo,
    RetaceoDetail,
    RetaceoSourceLine,
    RetaceoStatus,
    RetaceoTransitionError,
    calculate_retaceo_allocation,
    ensure_retaceo_transition,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RetaceoStatus.DRAFT, RetaceoStatus.CALCULATED),
        (RetaceoStatus.DRAFT, RetaceoStatus.CANCELLED),
        (RetaceoStatus.CALCULATED, RetaceoStatus.VERIFIED),
        (RetaceoStatus.CALCULATED, RetaceoStatus.CANCELLED),
        (RetaceoStatus.VERIFIED, RetaceoStatus.CLOSED),
    ],
)
def test_allowed_retaceo_transitions(current: RetaceoStatus, target: RetaceoStatus) -> None:
    ensure_retaceo_transition(current, target)


def test_invalid_retaceo_transition_raises() -> None:
    with pytest.raises(RetaceoTransitionError):
        ensure_retaceo_transition(RetaceoStatus.DRAFT, RetaceoStatus.VERIFIED)


def _sources() -> tuple[RetaceoSourceLine, ...]:
    return (
        RetaceoSourceLine(
            purchase_detail_id=uuid.uuid4(),
            product_id=1,
            unit_id=1,
            quantity=Decimal("100"),
            cost_fob=Decimal("20000"),
        ),
        RetaceoSourceLine(
            purchase_detail_id=uuid.uuid4(),
            product_id=2,
            unit_id=1,
            quantity=Decimal("60"),
            cost_fob=Decimal("18000"),
        ),
        RetaceoSourceLine(
            purchase_detail_id=uuid.uuid4(),
            product_id=3,
            unit_id=1,
            quantity=Decimal("70"),
            cost_fob=Decimal("17780"),
        ),
    )


def test_allocation_matches_retaceo_reference_totals() -> None:
    allocation = calculate_retaceo_allocation(
        _sources(),
        total_freight=Decimal("5125"),
        total_expenses=Decimal("1500"),
        total_dai=Decimal("8927"),
    )

    assert allocation.total_fob == Decimal("55780.000000")
    assert allocation.total_freight == Decimal("5125.000000")
    assert allocation.total_expenses == Decimal("1500.000000")
    assert allocation.total_dai == Decimal("8927.000000")
    assert allocation.total_cost == Decimal("71332.000000")
    assert sum((line.freight for line in allocation.lines), Decimal("0")) == Decimal("5125.000000")
    assert sum((line.expenses for line in allocation.lines), Decimal("0")) == Decimal("1500.000000")
    assert sum((line.dai for line in allocation.lines), Decimal("0")) == Decimal("8927.000000")


def test_allocation_reconciles_rounding_residue_exactly() -> None:
    sources = tuple(
        RetaceoSourceLine(
            purchase_detail_id=uuid.uuid4(),
            product_id=index + 1,
            unit_id=1,
            quantity=Decimal("1"),
            cost_fob=Decimal("1"),
        )
        for index in range(3)
    )

    allocation = calculate_retaceo_allocation(
        sources,
        total_freight=Decimal("0.000001"),
        total_expenses=Decimal("0"),
        total_dai=Decimal("0"),
    )

    assert sum((line.freight for line in allocation.lines), Decimal("0")) == Decimal("0.000001")
    assert all(line.freight >= 0 for line in allocation.lines)


def test_allocation_rejects_zero_total_fob() -> None:
    sources = (
        RetaceoSourceLine(
            purchase_detail_id=uuid.uuid4(),
            product_id=1,
            unit_id=1,
            quantity=Decimal("1"),
            cost_fob=Decimal("0"),
        ),
    )

    with pytest.raises(ValueError, match="FOB total"):
        calculate_retaceo_allocation(
            sources,
            total_freight=Decimal("1"),
            total_expenses=Decimal("0"),
            total_dai=Decimal("0"),
        )


def test_allocation_rejects_duplicate_purchase_detail() -> None:
    detail_id = uuid.uuid4()
    sources = (
        RetaceoSourceLine(
            purchase_detail_id=detail_id,
            product_id=1,
            unit_id=1,
            quantity=Decimal("1"),
            cost_fob=Decimal("10"),
        ),
        RetaceoSourceLine(
            purchase_detail_id=detail_id,
            product_id=1,
            unit_id=1,
            quantity=Decimal("1"),
            cost_fob=Decimal("10"),
        ),
    )

    with pytest.raises(ValueError, match="repetirse"):
        calculate_retaceo_allocation(
            sources,
            total_freight=Decimal("1"),
            total_expenses=Decimal("0"),
            total_dai=Decimal("0"),
        )


@pytest.mark.parametrize(
    "value",
    [Decimal("-1"), Decimal("NaN"), Decimal("Infinity")],
)
def test_allocation_rejects_invalid_expense_amounts(value: Decimal) -> None:
    with pytest.raises(ValueError, match="finito|negativo"):
        calculate_retaceo_allocation(
            _sources(),
            total_freight=value,
            total_expenses=Decimal("0"),
            total_dai=Decimal("0"),
        )


def _retaceo_from_reference() -> Retaceo:
    retaceo_id = uuid.uuid4()
    allocation = calculate_retaceo_allocation(
        _sources(),
        total_freight=Decimal("5125"),
        total_expenses=Decimal("1500"),
        total_dai=Decimal("8927"),
    )
    details = tuple(
        RetaceoDetail(
            id=uuid.uuid4(),
            retaceo_id=retaceo_id,
            purchase_detail_id=line.purchase_detail_id,
            product_id=line.product_id,
            unit_id=line.unit_id,
            quantity=line.quantity,
            cost_fob=line.cost_fob,
            freight=line.freight,
            expenses=line.expenses,
            dai=line.dai,
            total_cost=line.total_cost,
            unit_cost=line.unit_cost,
        )
        for line in allocation.lines
    )
    return Retaceo(
        id=retaceo_id,
        company_id=uuid.uuid4(),
        code="RET-00001",
        purchase_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        created_by_id=uuid.uuid4(),
        currency="USD",
        details=details,
        total_fob=allocation.total_fob,
        total_freight=allocation.total_freight,
        total_expenses=allocation.total_expenses,
        total_dai=allocation.total_dai,
        import_vat=Decimal("8367"),
        total_cost=allocation.total_cost,
        status=RetaceoStatus.CALCULATED,
    )


def test_retaceo_keeps_import_vat_outside_landed_cost() -> None:
    item = _retaceo_from_reference()

    assert item.total_cost == Decimal("71332.000000")
    assert item.import_vat == Decimal("8367")
    assert item.freight_percentage == Decimal("9.187881")
    assert item.expense_percentage == Decimal("2.689136")
    assert item.dai_percentage == Decimal("16.003944")


def test_retaceo_rejects_total_that_does_not_match_details() -> None:
    item = _retaceo_from_reference()

    with pytest.raises(ValueError, match="costo total"):
        Retaceo(
            id=item.id,
            company_id=item.company_id,
            code=item.code,
            purchase_id=item.purchase_id,
            branch_id=item.branch_id,
            created_by_id=item.created_by_id,
            currency=item.currency,
            details=item.details,
            total_fob=item.total_fob,
            total_freight=item.total_freight,
            total_expenses=item.total_expenses,
            total_dai=item.total_dai,
            import_vat=item.import_vat,
            total_cost=item.total_cost + Decimal("1"),
            status=item.status,
        )
