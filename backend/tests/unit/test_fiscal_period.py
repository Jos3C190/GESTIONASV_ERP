"""Reglas puras del cierre de período (V8b2)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from app.application.period_guard import require_open
from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal_books import Period
from app.domain.entities.fiscal_period import (
    closed_error,
    period_of,
    require_closable,
    require_reopen_reason,
)


def test_only_ended_months_close() -> None:
    today = date(2026, 11, 25)
    require_closable(Period(2026, 10), today)
    for period in (Period(2026, 11), Period(2026, 12)):
        with pytest.raises(BusinessRuleError) as error:
            require_closable(period, today)
        assert error.value.code == "fiscal_period_not_ended"


def test_reopen_reason_is_normalized_and_required() -> None:
    assert require_reopen_reason("  Cobro   registrado tarde ") == "Cobro registrado tarde"
    with pytest.raises(BusinessRuleError) as error:
        require_reopen_reason("corto")
    assert error.value.code == "fiscal_period_reopen_reason_required"


def test_closed_error_names_the_month() -> None:
    error = closed_error(Period(2026, 10))
    assert error.code == "fiscal_period_closed"
    assert "octubre de 2026" in error.message.lower()
    assert period_of(date(2026, 10, 31)) == Period(2026, 10)


class _Closed:
    def __init__(self, *periods: Period) -> None:
        self.periods = set(periods)
        self.asked: list[date] = []

    async def closed_period(self, company_id: uuid.UUID, day: date) -> Period | None:
        self.asked.append(day)
        period = Period(day.year, day.month)
        return period if period in self.periods else None


async def test_require_open_checks_each_date_once() -> None:
    company = uuid.uuid4()
    await require_open(None, company, date(2026, 10, 1))
    periods = _Closed(Period(2026, 10))
    await require_open(periods, company, date(2026, 11, 2), None, date(2026, 11, 2))
    assert periods.asked == [date(2026, 11, 2)]
    with pytest.raises(BusinessRuleError) as error:
        await require_open(periods, company, date(2026, 11, 2), date(2026, 10, 9))
    assert error.value.code == "fiscal_period_closed"
