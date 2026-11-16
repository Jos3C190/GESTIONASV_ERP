"""Listas de precios de venta (bloque V2b).

Un precio nunca se edita: cambiarlo cierra la vigencia anterior y abre otra. Así el historial
responde qué precio regía cualquier día, y un cambio no altera documentos ya confirmados.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from app.core.exceptions import BusinessRuleError, ConflictError
from app.domain.entities.sales_margin import require_target_margin

_CODE = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,19}$")


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


@dataclass(frozen=True, slots=True)
class PriceListDraft:
    code: str
    name: str
    prices_include_vat: bool
    description: str | None = None
    is_default: bool = False
    is_active: bool = True
    target_margin_percent: Decimal | None = None


def validate_list_draft(draft: PriceListDraft) -> PriceListDraft:
    code = draft.code.strip().upper()
    if not _CODE.match(code):
        raise _rule(
            "El código lleva de 1 a 20 letras, números o guiones, sin espacios.",
            "price_list_code_invalid",
        )
    name = " ".join(draft.name.split())
    if len(name) < 2:  # noqa: PLR2004
        raise _rule("Escribe el nombre de la lista.", "price_list_name_required")
    if draft.is_default and not draft.is_active:
        raise _rule(
            "La lista predeterminada no puede estar inactiva.", "price_list_default_inactive"
        )
    description = (draft.description or "").strip() or None
    require_target_margin(draft.target_margin_percent)
    return PriceListDraft(
        code=code,
        name=name,
        prices_include_vat=draft.prices_include_vat,
        description=description,
        is_default=draft.is_default,
        is_active=draft.is_active,
        target_margin_percent=draft.target_margin_percent,
    )


@dataclass(frozen=True, slots=True)
class PriceList:
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    name: str
    description: str | None
    prices_include_vat: bool
    is_default: bool
    is_active: bool
    price_count: int
    customer_count: int
    updated_at: datetime
    target_margin_percent: Decimal | None = None


class PriceStatus(StrEnum):
    SCHEDULED = "scheduled"
    CURRENT = "current"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class PriceKey:
    """Lo que identifica un precio dentro de una lista."""

    product_id: int
    variant_id: uuid.UUID | None
    unit_id: int
    branch_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class PriceEntry:
    id: uuid.UUID
    price_list_id: uuid.UUID
    key: PriceKey
    price: Decimal
    valid_from: date
    valid_to: date | None
    created_by_name: str | None
    created_at: datetime
    branch_name: str | None = None

    def covers(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)

    def status(self, today: date) -> PriceStatus:
        if self.valid_from > today:
            return PriceStatus.SCHEDULED
        if self.valid_to is not None and self.valid_to < today:
            return PriceStatus.EXPIRED
        return PriceStatus.CURRENT


@dataclass(frozen=True, slots=True)
class PriceChange:
    """Lo que hay que escribir para fijar un precio nuevo."""

    close_entry_id: uuid.UUID | None
    close_on: date | None
    valid_from: date


def plan_price_change(
    entries: list[PriceEntry], price: Decimal, valid_from: date, today: date
) -> PriceChange:
    """Decide cómo fijar ``price`` desde ``valid_from`` sobre las vigencias de una clave."""

    if price < 0:
        raise _rule("El precio no puede ser negativo.", "price_list_price_invalid")
    if valid_from < today:
        raise _rule(
            "Un precio rige desde hoy o desde una fecha futura; el historial no se reescribe.",
            "price_list_backdated",
        )
    later = [e for e in entries if e.valid_from >= valid_from]
    if later:
        first = min(later, key=lambda e: e.valid_from)
        raise ConflictError(
            f"Ya hay un precio que rige desde el {first.valid_from:%d/%m/%Y}. "
            "Anúlalo antes de fijar otro en esa fecha o antes.",
            code="price_list_future_exists",
        )
    covering = next((e for e in entries if e.covers(valid_from)), None)
    if covering is None:
        return PriceChange(close_entry_id=None, close_on=None, valid_from=valid_from)
    return PriceChange(
        close_entry_id=covering.id,
        close_on=valid_from - timedelta(days=1),
        valid_from=valid_from,
    )


def require_cancellable(entry: PriceEntry, today: date) -> None:
    """Solo se anula un precio que aún no empieza a regir."""

    if entry.status(today) is not PriceStatus.SCHEDULED:
        raise _rule(
            "Solo se anula un precio programado. Para cambiar uno vigente, fija el precio nuevo.",
            "price_list_not_scheduled",
        )


def require_endable(entry: PriceEntry, ends_on: date, today: date) -> None:
    if entry.status(today) is PriceStatus.EXPIRED:
        raise _rule("Ese precio ya no está vigente.", "price_list_already_ended")
    if ends_on < today or ends_on < entry.valid_from:
        raise _rule(
            "La fecha final debe ser hoy o posterior, y no antes de que el precio empiece.",
            "price_list_end_invalid",
        )
    if entry.valid_to is not None and ends_on > entry.valid_to:
        raise _rule("Ese precio ya termina antes de la fecha indicada.", "price_list_end_invalid")


def pick_price(
    entries: list[PriceEntry], branch_id: uuid.UUID | None, day: date
) -> PriceEntry | None:
    """El precio de la sucursal gana al general; ambos deben regir ese día."""

    valid = [e for e in entries if e.covers(day)]
    if branch_id is not None:
        own = next((e for e in valid if e.key.branch_id == branch_id), None)
        if own is not None:
            return own
    return next((e for e in valid if e.key.branch_id is None), None)


class PriceSource(StrEnum):
    CUSTOMER = "customer"
    DEFAULT = "default"


@dataclass(frozen=True, slots=True)
class SellableUnit:
    """Una unidad en que se vende un producto (o variante) y su factor a la unidad base."""

    product_id: int
    variant_id: uuid.UUID | None
    sku: str
    name: str
    unit_id: int
    unit_name: str
    factor: Decimal
    is_base: bool
    category_id: int | None = None
    inventory_item_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ListedPrice:
    """Una unidad vendible con su precio en una lista para un día y sucursal."""

    unit: SellableUnit
    current: PriceEntry | None
    next: PriceEntry | None
    branch_overrides: int
    cost: Decimal | None = None
    """Costo actual de la unidad (costo promedio x factor); solo si se pidió."""
    target_margin_percent: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ResolvedPrice:
    price_list: PriceList | None
    source: PriceSource | None
    entry: PriceEntry | None

    @property
    def found(self) -> bool:
        return self.entry is not None
