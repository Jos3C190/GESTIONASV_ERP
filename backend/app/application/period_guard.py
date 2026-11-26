"""Guardia del cierre de período (V8b2): un mes cerrado no admite movimientos con su fecha."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.domain.entities.fiscal_period import closed_error
from app.domain.ports.fiscal_period_repository import ClosedPeriods

_TZ = ZoneInfo("America/El_Salvador")


def local_day(moment: datetime | None) -> date | None:
    """Fecha en El Salvador de un instante guardado en UTC."""

    return moment.astimezone(_TZ).date() if moment is not None else None


async def require_open(
    periods: ClosedPeriods | None, company_id: uuid.UUID, *days: date | None
) -> None:
    """Rechaza el movimiento si alguna de sus fechas cae en un mes cerrado."""

    if periods is None:
        return
    for day in sorted({day for day in days if day is not None}):
        closed = await periods.closed_period(company_id, day)
        if closed is not None:
            raise closed_error(closed)
