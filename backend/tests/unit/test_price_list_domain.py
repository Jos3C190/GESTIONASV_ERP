"""Listas de precios: vigencias, anulación, fin y elección del precio."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError, ConflictError
from app.domain.entities.price_list import (
    PriceEntry,
    PriceKey,
    PriceListDraft,
    PriceStatus,
    pick_price,
    plan_price_change,
    require_cancellable,
    require_endable,
    validate_list_draft,
)

TODAY = date(2026, 11, 16)
BRANCH = uuid.uuid4()
LIST = uuid.uuid4()


def entry(
    start: str, end: str | None = None, *, branch: uuid.UUID | None = None, price: str = "1"
) -> PriceEntry:
    return PriceEntry(
        id=uuid.uuid4(),
        price_list_id=LIST,
        key=PriceKey(1, None, 1, branch),
        price=Decimal(price),
        valid_from=date.fromisoformat(start),
        valid_to=date.fromisoformat(end) if end else None,
        created_by_name=None,
        created_at=datetime.now(UTC),
    )


def test_list_draft_is_normalized_and_validated() -> None:
    clean = validate_list_draft(
        PriceListDraft(code=" mayoreo-1 ", name="  Mayoreo   San Miguel ", prices_include_vat=False)
    )
    assert clean.code == "MAYOREO-1"
    assert clean.name == "Mayoreo San Miguel"
    for draft, code in (
        (
            PriceListDraft(code="con espacio", name="Lista", prices_include_vat=True),
            "price_list_code_invalid",
        ),
        (PriceListDraft(code="L1", name=" ", prices_include_vat=True), "price_list_name_required"),
        (
            PriceListDraft(
                code="L1", name="Lista", prices_include_vat=True, is_default=True, is_active=False
            ),
            "price_list_default_inactive",
        ),
    ):
        with pytest.raises(BusinessRuleError) as exc:
            validate_list_draft(draft)
        assert exc.value.code == code


def test_new_price_closes_the_one_in_force() -> None:
    current = entry("2026-01-01")
    change = plan_price_change([current], Decimal("1.25"), date(2026, 12, 1), TODAY)
    assert change.close_entry_id == current.id
    assert change.close_on == date(2026, 11, 30)
    first = plan_price_change([], Decimal("1"), TODAY, TODAY)
    assert first.close_entry_id is None


def test_price_cannot_be_backdated_or_jump_a_scheduled_one() -> None:
    with pytest.raises(BusinessRuleError) as exc:
        plan_price_change([], Decimal("1"), date(2026, 11, 15), TODAY)
    assert exc.value.code == "price_list_backdated"
    with pytest.raises(BusinessRuleError) as exc:
        plan_price_change([], Decimal("-1"), TODAY, TODAY)
    assert exc.value.code == "price_list_price_invalid"
    scheduled = [entry("2026-01-01", "2026-11-30"), entry("2026-12-01")]
    with pytest.raises(ConflictError) as conflict:
        plan_price_change(scheduled, Decimal("2"), date(2026, 11, 20), TODAY)
    assert conflict.value.code == "price_list_future_exists"


def test_status_cancel_and_end_rules() -> None:
    assert entry("2026-12-01").status(TODAY) is PriceStatus.SCHEDULED
    assert entry("2026-01-01").status(TODAY) is PriceStatus.CURRENT
    assert entry("2026-01-01", "2026-11-15").status(TODAY) is PriceStatus.EXPIRED
    require_cancellable(entry("2026-12-01"), TODAY)
    with pytest.raises(BusinessRuleError) as exc:
        require_cancellable(entry("2026-01-01"), TODAY)
    assert exc.value.code == "price_list_not_scheduled"
    require_endable(entry("2026-01-01"), TODAY, TODAY)
    for ends_on, item in (
        (date(2026, 11, 15), entry("2026-01-01")),
        (date(2026, 12, 31), entry("2026-01-01", "2026-12-15")),
        (TODAY, entry("2026-01-01", "2026-11-10")),
    ):
        with pytest.raises(BusinessRuleError):
            require_endable(item, ends_on, TODAY)


def test_branch_price_wins_over_general_only_while_in_force() -> None:
    general = entry("2026-01-01", price="1.13")
    own = entry("2026-11-01", "2026-11-30", branch=BRANCH, price="1.25")
    assert pick_price([general, own], BRANCH, TODAY) is own
    assert pick_price([general, own], uuid.uuid4(), TODAY) is general
    assert pick_price([general, own], None, TODAY) is general
    assert pick_price([general, own], BRANCH, date(2026, 12, 1)) is general
    assert pick_price([entry("2026-12-01")], None, TODAY) is None
