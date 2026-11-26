"""Cierre de período fiscal (V8b2): un mes declarado ya no admite movimientos con fecha de ese mes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal_books import Period

MIN_REOPEN_REASON = 10
MAX_REOPEN_REASON = 500


@dataclass(frozen=True, slots=True)
class PeriodClose:
    id: uuid.UUID
    period: Period
    status: str
    summary: dict[str, Any]
    closed_by: str | None
    closed_at: datetime
    reopen_reason: str | None = None
    reopened_by: str | None = None
    reopened_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PeriodStatus:
    period: Period
    closed: PeriodClose | None
    history: list[PeriodClose] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


def period_of(day: date) -> Period:
    return Period(day.year, day.month)


def require_closable(period: Period, today: date) -> None:
    """Solo se cierra un mes ya terminado: el actual sigue recibiendo documentos."""

    if period.last >= date(today.year, today.month, 1):
        raise BusinessRuleError(
            f"{period.label} todavía no termina: solo se cierra un mes ya terminado.",
            code="fiscal_period_not_ended",
        )


def require_reopen_reason(reason: str) -> str:
    text = " ".join(reason.split())
    if not MIN_REOPEN_REASON <= len(text) <= MAX_REOPEN_REASON:
        raise BusinessRuleError(
            f"Indica por qué se reabre el período (mínimo {MIN_REOPEN_REASON} caracteres).",
            code="fiscal_period_reopen_reason_required",
        )
    return text


def closed_error(period: Period) -> BusinessRuleError:
    return BusinessRuleError(
        f"El período {period.label} está cerrado: reábrelo en Libros de IVA para registrar o cambiar "
        "movimientos con fecha de ese mes.",
        code="fiscal_period_closed",
    )
