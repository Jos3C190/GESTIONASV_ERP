"""Listas de precios de venta (bloque V2b)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domain.entities.price_list import (
    ListedPrice,
    PriceEntry,
    PriceKey,
    PriceList,
    PriceListDraft,
    PriceSource,
    PriceStatus,
    ResolvedPrice,
    SellableUnit,
    pick_price,
    plan_price_change,
    require_cancellable,
    require_endable,
    validate_list_draft,
)
from app.domain.ports.price_list_repository import PriceListRepository

_TZ = ZoneInfo("America/El_Salvador")


def today_in_el_salvador() -> date:
    return datetime.now(_TZ).date()


class PriceListUseCases:
    def __init__(self, repository: PriceListRepository) -> None:
        self._repo = repository

    # --- listas ---
    async def list_lists(self, company_id: uuid.UUID) -> list[PriceList]:
        return await self._repo.list_lists(company_id)

    async def get_list(self, company_id: uuid.UUID, list_id: uuid.UUID) -> PriceList:
        found = await self._repo.get_list(company_id, list_id)
        if found is None:
            raise NotFoundError("Lista de precios no encontrada.", code="price_list_not_found")
        return found

    async def create_list(
        self, company_id: uuid.UUID, draft: PriceListDraft, actor_id: uuid.UUID
    ) -> PriceList:
        clean = validate_list_draft(draft)
        if await self._repo.code_taken(company_id, clean.code, None):
            raise ConflictError(
                f"Ya existe una lista con el código {clean.code}.", code="price_list_code_taken"
            )
        if await self._repo.default_list(company_id) is None:
            if not clean.is_active:
                raise BusinessRuleError(
                    "La primera lista es la predeterminada y debe estar activa.",
                    code="price_list_default_inactive",
                )
            clean = replace(clean, is_default=True)
        if clean.is_default:
            await self._repo.clear_default(company_id, None)
        list_id = await self._repo.create_list(company_id, clean, actor_id)
        return await self.get_list(company_id, list_id)

    async def update_list(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        draft: PriceListDraft,
        actor_id: uuid.UUID,
    ) -> tuple[PriceList, PriceList]:
        before = await self.get_list(company_id, list_id)
        clean = validate_list_draft(draft)
        if before.is_default and not clean.is_default:
            raise BusinessRuleError(
                "Siempre hay una lista predeterminada. Marca otra como predeterminada y esta "
                "dejará de serlo.",
                code="price_list_default_required",
            )
        if await self._repo.code_taken(company_id, clean.code, list_id):
            raise ConflictError(
                f"Ya existe una lista con el código {clean.code}.", code="price_list_code_taken"
            )
        if clean.is_default:
            await self._repo.clear_default(company_id, list_id)
        await self._repo.update_list(company_id, list_id, clean, actor_id)
        return before, await self.get_list(company_id, list_id)

    # --- precios ---
    async def sellable_units(self, company_id: uuid.UUID, search: str | None) -> list[SellableUnit]:
        return await self._repo.sellable_units(company_id, search=search)

    async def listed_prices(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        *,
        search: str | None,
        branch_id: uuid.UUID | None,
        on: date | None,
    ) -> list[ListedPrice]:
        await self.get_list(company_id, list_id)
        day = on or today_in_el_salvador()
        units = await self._repo.sellable_units(company_id, search=search)
        entries = await self._repo.entries(
            company_id, list_id, product_ids={u.product_id for u in units}
        )
        result: list[ListedPrice] = []
        for unit in units:
            mine = [
                e
                for e in entries
                if e.key.product_id == unit.product_id
                and e.key.variant_id == unit.variant_id
                and e.key.unit_id == unit.unit_id
            ]
            current = pick_price(mine, branch_id, day)
            scope = current.key.branch_id if current else branch_id
            upcoming = sorted(
                (e for e in mine if e.key.branch_id == scope and e.valid_from > day),
                key=lambda e: e.valid_from,
            )
            overrides = {
                e.key.branch_id
                for e in mine
                if e.key.branch_id is not None and e.status(day) is not PriceStatus.EXPIRED
            }
            result.append(
                ListedPrice(
                    unit=unit,
                    current=current,
                    next=upcoming[0] if upcoming else None,
                    branch_overrides=len(overrides),
                )
            )
        return result

    async def history(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        product_id: int,
        variant_id: uuid.UUID | None,
        unit_id: int,
    ) -> list[PriceEntry]:
        await self.get_list(company_id, list_id)
        return await self._repo.entries(
            company_id,
            list_id,
            key=PriceKey(product_id, variant_id, unit_id, None),
            any_branch=True,
        )

    async def _require_sellable(self, company_id: uuid.UUID, key: PriceKey) -> None:
        units = await self._repo.sellable_units(company_id, product_id=key.product_id)
        if not units:
            raise NotFoundError(
                "El producto no existe o no está activo y marcado como vendible.",
                code="price_list_product_not_sellable",
            )
        if not any(u.variant_id == key.variant_id and u.unit_id == key.unit_id for u in units):
            raise BusinessRuleError(
                "Esa unidad no es una forma de venta del producto: usa su unidad base o la de "
                "uno de sus empaques vigentes.",
                code="price_list_unit_invalid",
            )
        if key.branch_id is not None and not await self._repo.branch_exists(
            company_id, key.branch_id
        ):
            raise NotFoundError("Sucursal no encontrada.", code="branch_not_found")

    async def set_price(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        key: PriceKey,
        price: Decimal,
        valid_from: date | None,
        actor_id: uuid.UUID,
    ) -> PriceEntry:
        await self.get_list(company_id, list_id)
        await self._require_sellable(company_id, key)
        await self._repo.lock_list(company_id, list_id)
        today = today_in_el_salvador()
        start = valid_from or today
        entries = await self._repo.entries(company_id, list_id, key=key)
        change = plan_price_change(entries, price, start, today)
        if change.close_entry_id is not None:
            await self._repo.set_valid_to(change.close_entry_id, change.close_on)
        entry_id = await self._repo.insert_entry(
            company_id, list_id, key, price, change.valid_from, actor_id
        )
        created = await self._repo.get_entry(company_id, entry_id)
        assert created is not None
        return created

    async def _entry(self, company_id: uuid.UUID, entry_id: uuid.UUID) -> PriceEntry:
        entry = await self._repo.get_entry(company_id, entry_id)
        if entry is None:
            raise NotFoundError("Precio no encontrado.", code="price_list_entry_not_found")
        return entry

    async def cancel_price(self, company_id: uuid.UUID, entry_id: uuid.UUID) -> PriceEntry:
        entry = await self._entry(company_id, entry_id)
        require_cancellable(entry, today_in_el_salvador())
        await self._repo.lock_list(company_id, entry.price_list_id)
        siblings = await self._repo.entries(company_id, entry.price_list_id, key=entry.key)
        previous = next(
            (
                e
                for e in siblings
                if e.valid_to is not None and (entry.valid_from - e.valid_to).days == 1
            ),
            None,
        )
        await self._repo.delete_entry(entry.id)
        if previous is not None:
            await self._repo.set_valid_to(previous.id, entry.valid_to)
        return entry

    async def end_price(
        self, company_id: uuid.UUID, entry_id: uuid.UUID, ends_on: date
    ) -> tuple[PriceEntry, PriceEntry]:
        entry = await self._entry(company_id, entry_id)
        require_endable(entry, ends_on, today_in_el_salvador())
        await self._repo.lock_list(company_id, entry.price_list_id)
        await self._repo.set_valid_to(entry.id, ends_on)
        return entry, await self._entry(company_id, entry_id)

    # --- resolución ---
    async def resolve(
        self,
        company_id: uuid.UUID,
        *,
        customer_id: uuid.UUID | None,
        branch_id: uuid.UUID | None,
        product_id: int,
        variant_id: uuid.UUID | None,
        unit_id: int,
        on: date | None,
    ) -> ResolvedPrice:
        chosen: PriceList | None = None
        source: PriceSource | None = None
        if customer_id is not None:
            exists, list_id = await self._repo.customer_list_id(company_id, customer_id)
            if not exists:
                raise NotFoundError("Cliente no encontrado.", code="sales_customer_not_found")
            if list_id is not None:
                assigned = await self._repo.get_list(company_id, list_id)
                if assigned is not None and assigned.is_active:
                    chosen, source = assigned, PriceSource.CUSTOMER
        if chosen is None:
            chosen = await self._repo.default_list(company_id)
            source = PriceSource.DEFAULT if chosen else None
        if chosen is None:
            return ResolvedPrice(price_list=None, source=None, entry=None)
        entries = await self._repo.entries(
            company_id,
            chosen.id,
            key=PriceKey(product_id, variant_id, unit_id, None),
            any_branch=True,
        )
        entry = pick_price(entries, branch_id, on or today_in_el_salvador())
        return ResolvedPrice(price_list=chosen, source=source, entry=entry)
