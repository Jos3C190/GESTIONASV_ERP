"""Listas de precios en PostgreSQL (bloque V2b)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.price_list import (
    PriceEntry,
    PriceKey,
    PriceList,
    PriceListDraft,
    SellableUnit,
)
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel, UnitModel
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.inventory import InventoryItemModel, InventoryPackagingModel
from app.infrastructure.models.organization import Branch
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.models.sales import SalesCustomerModel
from app.infrastructure.models.sales_pricing import SalesPriceListItemModel, SalesPriceListModel
from app.infrastructure.models.user import User


def unit_label(name: str, symbol: str) -> str:
    clean_name, clean_symbol = name.strip(), symbol.strip()
    if not clean_name:
        return clean_symbol
    if not clean_symbol or clean_name == clean_symbol or clean_name.endswith(f"({clean_symbol})"):
        return clean_name
    return f"{clean_name} ({clean_symbol})"


class SqlAlchemyPriceListRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- listas ---
    async def _to_lists(
        self, company_id: uuid.UUID, rows: list[SalesPriceListModel]
    ) -> list[PriceList]:
        if not rows:
            return []
        ids = [r.id for r in rows]
        prices = dict(
            (
                await self._session.execute(
                    select(SalesPriceListItemModel.price_list_id, func.count())
                    .where(
                        SalesPriceListItemModel.company_id == company_id,
                        SalesPriceListItemModel.price_list_id.in_(ids),
                    )
                    .group_by(SalesPriceListItemModel.price_list_id)
                )
            )
            .tuples()
            .all()
        )
        customers = dict(
            (
                await self._session.execute(
                    select(SalesCustomerModel.price_list_id, func.count())
                    .where(
                        SalesCustomerModel.company_id == company_id,
                        SalesCustomerModel.price_list_id.in_(ids),
                    )
                    .group_by(SalesCustomerModel.price_list_id)
                )
            )
            .tuples()
            .all()
        )
        return [
            PriceList(
                id=r.id,
                company_id=r.company_id,
                code=r.code,
                name=r.name,
                description=r.description,
                prices_include_vat=r.prices_include_vat,
                is_default=r.is_default,
                is_active=r.is_active,
                price_count=int(prices.get(r.id, 0)),
                customer_count=int(customers.get(r.id, 0)),
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    async def list_lists(self, company_id: uuid.UUID) -> list[PriceList]:
        rows = (
            await self._session.scalars(
                select(SalesPriceListModel)
                .where(SalesPriceListModel.company_id == company_id)
                .order_by(SalesPriceListModel.is_default.desc(), SalesPriceListModel.name)
            )
        ).all()
        return await self._to_lists(company_id, list(rows))

    async def get_list(self, company_id: uuid.UUID, list_id: uuid.UUID) -> PriceList | None:
        row = await self._session.scalar(
            select(SalesPriceListModel).where(
                SalesPriceListModel.company_id == company_id, SalesPriceListModel.id == list_id
            )
        )
        lists = await self._to_lists(company_id, [row] if row else [])
        return lists[0] if lists else None

    async def default_list(self, company_id: uuid.UUID) -> PriceList | None:
        row = await self._session.scalar(
            select(SalesPriceListModel).where(
                SalesPriceListModel.company_id == company_id,
                SalesPriceListModel.is_default.is_(True),
            )
        )
        lists = await self._to_lists(company_id, [row] if row else [])
        return lists[0] if lists else None

    async def code_taken(
        self, company_id: uuid.UUID, code: str, exclude_id: uuid.UUID | None
    ) -> bool:
        query = select(SalesPriceListModel.id).where(
            SalesPriceListModel.company_id == company_id, SalesPriceListModel.code == code
        )
        if exclude_id is not None:
            query = query.where(SalesPriceListModel.id != exclude_id)
        return await self._session.scalar(query) is not None

    async def create_list(
        self, company_id: uuid.UUID, draft: PriceListDraft, actor_id: uuid.UUID
    ) -> uuid.UUID:
        row = SalesPriceListModel(
            company_id=company_id,
            code=draft.code,
            name=draft.name,
            description=draft.description,
            prices_include_vat=draft.prices_include_vat,
            is_default=draft.is_default,
            is_active=draft.is_active,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row.id

    async def update_list(
        self, company_id: uuid.UUID, list_id: uuid.UUID, draft: PriceListDraft, actor_id: uuid.UUID
    ) -> None:
        await self._session.execute(
            update(SalesPriceListModel)
            .where(SalesPriceListModel.company_id == company_id, SalesPriceListModel.id == list_id)
            .values(
                code=draft.code,
                name=draft.name,
                description=draft.description,
                prices_include_vat=draft.prices_include_vat,
                is_default=draft.is_default,
                is_active=draft.is_active,
                updated_by=actor_id,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.flush()

    async def clear_default(self, company_id: uuid.UUID, except_id: uuid.UUID | None) -> None:
        query = update(SalesPriceListModel).where(
            SalesPriceListModel.company_id == company_id,
            SalesPriceListModel.is_default.is_(True),
        )
        if except_id is not None:
            query = query.where(SalesPriceListModel.id != except_id)
        await self._session.execute(query.values(is_default=False, updated_at=datetime.now(UTC)))
        await self._session.flush()

    async def lock_list(self, company_id: uuid.UUID, list_id: uuid.UUID) -> None:
        await self._session.execute(
            select(SalesPriceListModel.id)
            .where(SalesPriceListModel.company_id == company_id, SalesPriceListModel.id == list_id)
            .with_for_update()
        )

    # --- unidades vendibles ---
    async def _units(self, company_id: uuid.UUID, unit_ids: set[int]) -> dict[int, tuple[str, str]]:
        if not unit_ids:
            return {}
        rows = await self._session.execute(
            select(UnitModel.id_unit, UnitModel.name, UnitModel.symbol)
            .join(
                CompanyUnitModel,
                and_(
                    CompanyUnitModel.unit_id == UnitModel.id_unit,
                    CompanyUnitModel.company_id == company_id,
                ),
            )
            .where(
                UnitModel.id_unit.in_(unit_ids),
                CompanyUnitModel.is_enabled.is_(True),
                UnitModel.is_active.is_(True),
            )
        )
        return {uid: (name, symbol) for uid, name, symbol in rows.tuples().all()}

    async def sellable_units(
        self,
        company_id: uuid.UUID,
        *,
        search: str | None = None,
        product_id: int | None = None,
        limit: int = 200,
    ) -> list[SellableUnit]:
        query = select(ProductModel).where(
            ProductModel.company_id == company_id,
            ProductModel.is_active.is_(True),
            ProductModel.can_sell.is_(True),
            ProductModel.lifecycle_status == "active",
            ProductModel.deleted_at.is_(None),
        )
        if product_id is not None:
            query = query.where(ProductModel.id_product == product_id)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    ProductModel.name.ilike(pattern),
                    ProductModel.sku.ilike(pattern),
                    ProductModel.sales_name.ilike(pattern),
                )
            )
        products = (
            await self._session.scalars(query.order_by(ProductModel.name).limit(limit))
        ).all()
        if not products:
            return []
        ids = [p.id_product for p in products]
        variants = (
            await self._session.scalars(
                select(ProductVariantModel)
                .where(
                    ProductVariantModel.company_id == company_id,
                    ProductVariantModel.product_id.in_(ids),
                    ProductVariantModel.is_active.is_(True),
                    ProductVariantModel.lifecycle_status == "active",
                )
                .order_by(ProductVariantModel.sku)
            )
        ).all()
        items = (
            await self._session.scalars(
                select(InventoryItemModel).where(
                    InventoryItemModel.company_id == company_id,
                    InventoryItemModel.product_id.in_(ids),
                    InventoryItemModel.is_active.is_(True),
                )
            )
        ).all()
        packages = (
            await self._session.scalars(
                select(InventoryPackagingModel)
                .where(
                    InventoryPackagingModel.company_id == company_id,
                    InventoryPackagingModel.inventory_item_id.in_([i.id for i in items]),
                    InventoryPackagingModel.is_current.is_(True),
                    InventoryPackagingModel.is_active.is_(True),
                    InventoryPackagingModel.packaging_unit_id.is_not(None),
                )
                .order_by(InventoryPackagingModel.base_quantity)
            )
        ).all()
        unit_ids = {i.base_unit_id for i in items} | {
            int(p.packaging_unit_id) for p in packages if p.packaging_unit_id is not None
        }
        unit_ids |= {p.sale_unit for p in products}
        units = await self._units(company_id, unit_ids)

        result: list[SellableUnit] = []
        for product in products:
            product_name = product.sales_name or product.name
            if product.variant_mode == "standalone":
                owners: list[tuple[uuid.UUID | None, str, str]] = [
                    (None, product.sku, product_name)
                ]
            else:
                owners = [
                    (v.id, v.sku, v.name_override or product_name)
                    for v in variants
                    if v.product_id == product.id_product
                ]
            for variant_id, sku, name in owners:
                item = next(
                    (
                        i
                        for i in items
                        if i.product_id == product.id_product and i.variant_id == variant_id
                    ),
                    None,
                )
                owner = SellableUnit(
                    product.id_product, variant_id, sku, name, 0, "", Decimal("1"), True
                )
                result.extend(_owner_units(owner, product, item, packages, units))
        return result

    # --- precios ---
    async def _user_names(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not ids:
            return {}
        rows = await self._session.execute(
            select(User.id, User.username, Employee.first_name, Employee.last_name)
            .outerjoin(Employee, (Employee.user_id == User.id) & Employee.deleted_at.is_(None))
            .where(User.id.in_(ids))
        )
        names: dict[uuid.UUID, str] = {}
        for user_id, username, first, last in rows.tuples().all():
            full = f"{first or ''} {last or ''}".strip()
            names.setdefault(user_id, full or username)
        return names

    async def _to_entries(
        self, company_id: uuid.UUID, rows: list[SalesPriceListItemModel]
    ) -> list[PriceEntry]:
        users = await self._user_names({r.created_by for r in rows if r.created_by})
        branch_ids = {r.branch_id for r in rows if r.branch_id}
        branches: dict[uuid.UUID, str] = {}
        if branch_ids:
            branches = dict(
                (
                    await self._session.execute(
                        select(Branch.id, Branch.name).where(
                            Branch.company_id == company_id, Branch.id.in_(branch_ids)
                        )
                    )
                )
                .tuples()
                .all()
            )
        return [
            PriceEntry(
                id=r.id,
                price_list_id=r.price_list_id,
                key=PriceKey(r.product_id, r.variant_id, r.unit_id, r.branch_id),
                price=r.price,
                valid_from=r.valid_from,
                valid_to=r.valid_to,
                created_by_name=users.get(r.created_by) if r.created_by else None,
                created_at=r.created_at,
                branch_name=branches.get(r.branch_id) if r.branch_id else None,
            )
            for r in rows
        ]

    async def entries(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        *,
        product_ids: set[int] | None = None,
        key: PriceKey | None = None,
        any_branch: bool = False,
    ) -> list[PriceEntry]:
        query = select(SalesPriceListItemModel).where(
            SalesPriceListItemModel.company_id == company_id,
            SalesPriceListItemModel.price_list_id == list_id,
        )
        if product_ids is not None:
            query = query.where(SalesPriceListItemModel.product_id.in_(product_ids))
        if key is not None:
            variant = SalesPriceListItemModel.variant_id
            query = query.where(
                SalesPriceListItemModel.product_id == key.product_id,
                SalesPriceListItemModel.unit_id == key.unit_id,
                variant.is_(None) if key.variant_id is None else variant == key.variant_id,
            )
            if not any_branch:
                branch = SalesPriceListItemModel.branch_id
                query = query.where(
                    branch.is_(None) if key.branch_id is None else branch == key.branch_id
                )
        rows = (
            await self._session.scalars(
                query.order_by(
                    SalesPriceListItemModel.product_id,
                    SalesPriceListItemModel.valid_from.desc(),
                )
            )
        ).all()
        return await self._to_entries(company_id, list(rows))

    async def get_entry(self, company_id: uuid.UUID, entry_id: uuid.UUID) -> PriceEntry | None:
        row = await self._session.scalar(
            select(SalesPriceListItemModel).where(
                SalesPriceListItemModel.company_id == company_id,
                SalesPriceListItemModel.id == entry_id,
            )
        )
        entries = await self._to_entries(company_id, [row] if row else [])
        return entries[0] if entries else None

    async def insert_entry(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        key: PriceKey,
        price: Decimal,
        valid_from: date,
        actor_id: uuid.UUID,
    ) -> uuid.UUID:
        row = SalesPriceListItemModel(
            company_id=company_id,
            price_list_id=list_id,
            product_id=key.product_id,
            variant_id=key.variant_id,
            unit_id=key.unit_id,
            branch_id=key.branch_id,
            price=price,
            valid_from=valid_from,
            created_by=actor_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row.id

    async def set_valid_to(self, entry_id: uuid.UUID, valid_to: date | None) -> None:
        await self._session.execute(
            update(SalesPriceListItemModel)
            .where(SalesPriceListItemModel.id == entry_id)
            .values(valid_to=valid_to)
        )
        await self._session.flush()

    async def delete_entry(self, entry_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(SalesPriceListItemModel).where(SalesPriceListItemModel.id == entry_id)
        )
        await self._session.flush()

    async def branch_exists(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> bool:
        found = await self._session.scalar(
            select(Branch.id).where(
                Branch.company_id == company_id,
                Branch.id == branch_id,
                Branch.deleted_at.is_(None),
            )
        )
        return found is not None

    async def customer_list_id(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> tuple[bool, uuid.UUID | None]:
        row = (
            await self._session.execute(
                select(SalesCustomerModel.id, SalesCustomerModel.price_list_id).where(
                    SalesCustomerModel.company_id == company_id,
                    SalesCustomerModel.id == customer_id,
                )
            )
        ).first()
        if row is None:
            return False, None
        return True, row[1]


def _owner_units(
    owner: SellableUnit,
    product: ProductModel,
    item: InventoryItemModel | None,
    packages: Sequence[InventoryPackagingModel],
    units: dict[int, tuple[str, str]],
) -> list[SellableUnit]:
    """Unidades vendibles de un producto o variante: base y empaques vigentes."""

    def unit(unit_id: int, label: str, factor: Decimal, is_base: bool) -> SellableUnit:
        return replace(owner, unit_id=unit_id, unit_name=label, factor=factor, is_base=is_base)

    if item is None:
        if product.product_kind == "goods" or product.sale_unit not in units:
            return []
        return [unit(product.sale_unit, unit_label(*units[product.sale_unit]), Decimal("1"), True)]
    found: list[SellableUnit] = []
    if item.base_unit_id in units:
        found.append(
            unit(item.base_unit_id, unit_label(*units[item.base_unit_id]), Decimal("1"), True)
        )
    seen = {item.base_unit_id}
    for package in packages:
        unit_id = package.packaging_unit_id
        if package.inventory_item_id != item.id or unit_id is None:
            continue
        if unit_id in seen or unit_id not in units:
            continue
        seen.add(unit_id)
        label = unit_label(package.name, units[unit_id][1])
        found.append(unit(int(unit_id), label, Decimal(package.base_quantity), False))
    return found
