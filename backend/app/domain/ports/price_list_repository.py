"""Puerto de persistencia de las listas de precios (bloque V2b)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.domain.entities.price_list import (
    PriceEntry,
    PriceKey,
    PriceList,
    PriceListDraft,
    SellableUnit,
)


class PriceListRepository(Protocol):
    async def list_lists(self, company_id: uuid.UUID) -> list[PriceList]: ...

    async def get_list(self, company_id: uuid.UUID, list_id: uuid.UUID) -> PriceList | None: ...

    async def default_list(self, company_id: uuid.UUID) -> PriceList | None: ...

    async def code_taken(
        self, company_id: uuid.UUID, code: str, exclude_id: uuid.UUID | None
    ) -> bool: ...

    async def create_list(
        self, company_id: uuid.UUID, draft: PriceListDraft, actor_id: uuid.UUID
    ) -> uuid.UUID: ...

    async def update_list(
        self, company_id: uuid.UUID, list_id: uuid.UUID, draft: PriceListDraft, actor_id: uuid.UUID
    ) -> None: ...

    async def clear_default(self, company_id: uuid.UUID, except_id: uuid.UUID | None) -> None: ...

    async def lock_list(self, company_id: uuid.UUID, list_id: uuid.UUID) -> None: ...

    async def sellable_units(
        self,
        company_id: uuid.UUID,
        *,
        search: str | None = None,
        product_id: int | None = None,
        limit: int = 200,
    ) -> list[SellableUnit]: ...

    async def entries(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        *,
        product_ids: set[int] | None = None,
        key: PriceKey | None = None,
        any_branch: bool = False,
    ) -> list[PriceEntry]:
        """Precios de la lista. Con ``key`` y ``any_branch`` trae todas las sucursales."""
        ...

    async def get_entry(self, company_id: uuid.UUID, entry_id: uuid.UUID) -> PriceEntry | None: ...

    async def insert_entry(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        key: PriceKey,
        price: Decimal,
        valid_from: date,
        actor_id: uuid.UUID,
    ) -> uuid.UUID: ...

    async def set_valid_to(self, entry_id: uuid.UUID, valid_to: date | None) -> None: ...

    async def delete_entry(self, entry_id: uuid.UUID) -> None: ...

    async def branch_exists(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> bool: ...

    async def unit_costs(
        self, company_id: uuid.UUID, item_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, Decimal]:
        """Costo promedio por unidad base de cada artículo de inventario."""
        ...

    async def category_margins(
        self, company_id: uuid.UUID, list_id: uuid.UUID
    ) -> dict[int, Decimal]: ...

    async def replace_category_margins(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        margins: dict[int, Decimal],
        actor_id: uuid.UUID,
    ) -> None: ...

    async def categories(self, company_id: uuid.UUID) -> list[tuple[int, str]]: ...

    async def customer_list_id(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> tuple[bool, uuid.UUID | None]:
        """(existe el cliente, lista asignada)."""
        ...
