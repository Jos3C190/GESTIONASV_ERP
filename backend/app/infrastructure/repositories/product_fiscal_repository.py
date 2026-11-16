"""SQLAlchemy implementation of the product and unit fiscal classification repository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.product_fiscal import (
    CatalogEntry,
    DteItemType,
    ProductFiscal,
    TaxTreatment,
    UnitFiscal,
    suggested_unit_code,
)
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel, UnitModel
from app.infrastructure.models.fiscal import HaciendaCatalogItemModel

UNIT_CATALOG = "CAT-014"
TAX_CATALOG = "CAT-015"


class SqlAlchemyProductFiscalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def catalog(self, catalog_code: str) -> list[CatalogEntry]:
        rows = await self._session.execute(
            select(HaciendaCatalogItemModel.code, HaciendaCatalogItemModel.name)
            .where(
                HaciendaCatalogItemModel.catalog_code == catalog_code,
                HaciendaCatalogItemModel.is_active.is_(True),
            )
            .order_by(HaciendaCatalogItemModel.group_code, HaciendaCatalogItemModel.sort_order)
        )
        seen: dict[str, CatalogEntry] = {}
        for code, name in rows.tuples().all():
            seen.setdefault(code, CatalogEntry(code, name))
        return list(seen.values())

    async def _names(self, catalog_code: str) -> dict[str, str]:
        return {entry.code: entry.name for entry in await self.catalog(catalog_code)}

    def _unit(
        self, unit: UnitModel, link: CompanyUnitModel | None, names: dict[str, str]
    ) -> UnitFiscal:
        stored = link.hacienda_unit_code if link is not None else None
        effective = stored or suggested_unit_code(unit.code)
        return UnitFiscal(
            unit_id=unit.id_unit,
            code=unit.code,
            name=(link.alias if link is not None and link.alias else unit.name),
            symbol=unit.symbol,
            is_enabled=bool(link is not None and link.is_enabled),
            hacienda_unit_code=stored,
            hacienda_unit_name=names.get(effective),
        )

    async def get_product(self, company_id: uuid.UUID, product_id: int) -> ProductFiscal | None:
        product = await self._session.scalar(
            select(ProductModel).where(
                ProductModel.company_id == company_id,
                ProductModel.id_product == product_id,
                ProductModel.deleted_at.is_(None),
            )
        )
        if product is None:
            return None
        unit_row = (
            await self._session.execute(
                select(UnitModel, CompanyUnitModel)
                .outerjoin(
                    CompanyUnitModel,
                    (CompanyUnitModel.unit_id == UnitModel.id_unit)
                    & (CompanyUnitModel.company_id == company_id),
                )
                .where(UnitModel.id_unit == product.sale_unit)
            )
        ).first()
        units = await self._names(UNIT_CATALOG)
        taxes = await self._names(TAX_CATALOG)
        return ProductFiscal(
            product_id=product.id_product,
            product_uuid=product.uuid,
            sku=product.sku,
            name=product.name,
            product_kind=product.product_kind,
            can_sell=product.can_sell,
            tax_treatment=TaxTreatment(product.tax_treatment),
            dte_item_type=DteItemType(product.dte_item_type) if product.dte_item_type else None,
            additional_taxes=tuple(
                CatalogEntry(code, taxes.get(code, code)) for code in product.additional_tax_codes
            ),
            sale_unit=self._unit(unit_row[0], unit_row[1], units) if unit_row else None,
        )

    async def save_product(
        self,
        company_id: uuid.UUID,
        product_id: int,
        *,
        tax_treatment: TaxTreatment,
        dte_item_type: DteItemType | None,
        additional_tax_codes: tuple[str, ...],
    ) -> ProductFiscal:
        await self._session.execute(
            update(ProductModel)
            .where(ProductModel.company_id == company_id, ProductModel.id_product == product_id)
            .values(
                tax_treatment=tax_treatment.value,
                dte_item_type=dte_item_type.value if dte_item_type else None,
                additional_tax_codes=list(additional_tax_codes),
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.flush()
        saved = await self.get_product(company_id, product_id)
        assert saved is not None
        return saved

    async def list_units(self, company_id: uuid.UUID) -> list[UnitFiscal]:
        rows = (
            await self._session.execute(
                select(UnitModel, CompanyUnitModel)
                .join(CompanyUnitModel, CompanyUnitModel.unit_id == UnitModel.id_unit)
                .where(
                    CompanyUnitModel.company_id == company_id,
                    UnitModel.deleted_at.is_(None),
                )
                .order_by(UnitModel.type, UnitModel.name)
            )
        ).all()
        names = await self._names(UNIT_CATALOG)
        return [self._unit(unit, link, names) for unit, link in rows]

    async def get_unit(self, company_id: uuid.UUID, unit_id: int) -> UnitFiscal | None:
        return next((u for u in await self.list_units(company_id) if u.unit_id == unit_id), None)

    async def save_unit_code(
        self, company_id: uuid.UUID, unit_id: int, hacienda_unit_code: str | None
    ) -> UnitFiscal:
        await self._session.execute(
            update(CompanyUnitModel)
            .where(CompanyUnitModel.company_id == company_id, CompanyUnitModel.unit_id == unit_id)
            .values(hacienda_unit_code=hacienda_unit_code, updated_at=datetime.now(UTC))
        )
        await self._session.flush()
        saved = await self.get_unit(company_id, unit_id)
        assert saved is not None
        return saved
