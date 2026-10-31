"""Inventory cost application boundary for purchasing workflows."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.domain.entities.retaceo import Retaceo


@dataclass(frozen=True, slots=True)
class RetaceoAverageLine:
    product_id: int
    inventory_item_id: uuid.UUID
    base_unit_id: int
    previous_quantity: Decimal
    previous_value: Decimal
    previous_average: Decimal
    incoming_quantity: Decimal
    incoming_value: Decimal
    resulting_quantity: Decimal
    resulting_value: Decimal
    resulting_average: Decimal


@dataclass(frozen=True, slots=True)
class RetaceoAverageComparison:
    currency: str
    mode: str
    lines: tuple[RetaceoAverageLine, ...]
    value_only: bool = False


class RetaceoValuationGateway(Protocol):
    async def lock(self, company_id: uuid.UUID) -> None: ...

    async def enabled(self, company_id: uuid.UUID) -> bool: ...

    async def receipt_is_valued(self, company_id: uuid.UUID, purchase_id: uuid.UUID) -> bool: ...

    async def apply_retaceo(self, retaceo: Retaceo, actor_id: uuid.UUID) -> None: ...

    async def average_comparison(self, retaceo: Retaceo) -> RetaceoAverageComparison: ...
