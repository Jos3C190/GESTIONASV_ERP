"""Casos de uso de la clasificación fiscal de productos y de las unidades por empresa."""

from __future__ import annotations

import uuid

from app.core.exceptions import NotFoundError
from app.domain.entities.product_fiscal import (
    IVA_TAX_CODES,
    CatalogEntry,
    DteItemType,
    ProductFiscal,
    TaxTreatment,
    UnitFiscal,
    validate_tax_codes,
    validate_unit_code,
)
from app.domain.ports.product_fiscal_repository import ProductFiscalRepository

UNIT_CATALOG = "CAT-014"
TAX_CATALOG = "CAT-015"


class ProductFiscalUseCases:
    def __init__(self, repository: ProductFiscalRepository) -> None:
        self._repo = repository

    async def tax_options(self) -> list[CatalogEntry]:
        """Tributos que un producto puede llevar: CAT-015 sin el IVA."""
        return [e for e in await self._repo.catalog(TAX_CATALOG) if e.code not in IVA_TAX_CODES]

    async def unit_options(self) -> list[CatalogEntry]:
        return await self._repo.catalog(UNIT_CATALOG)

    async def get_product(self, company_id: uuid.UUID, product_id: int) -> ProductFiscal:
        product = await self._repo.get_product(company_id, product_id)
        if product is None:
            raise NotFoundError("Producto no encontrado.", code="product_not_found")
        return product

    async def update_product(
        self,
        company_id: uuid.UUID,
        product_id: int,
        *,
        tax_treatment: TaxTreatment,
        dte_item_type: DteItemType | None,
        additional_tax_codes: list[str],
    ) -> ProductFiscal:
        await self.get_product(company_id, product_id)
        known = frozenset(e.code for e in await self._repo.catalog(TAX_CATALOG))
        codes = validate_tax_codes(tax_treatment, additional_tax_codes, known)
        return await self._repo.save_product(
            company_id,
            product_id,
            tax_treatment=tax_treatment,
            dte_item_type=dte_item_type,
            additional_tax_codes=codes,
        )

    async def list_units(self, company_id: uuid.UUID) -> list[UnitFiscal]:
        return await self._repo.list_units(company_id)

    async def get_unit(self, company_id: uuid.UUID, unit_id: int) -> UnitFiscal:
        unit = await self._repo.get_unit(company_id, unit_id)
        if unit is None:
            raise NotFoundError(
                "Esa unidad no está registrada en la empresa.", code="fiscal_unit_not_found"
            )
        return unit

    async def update_unit(
        self, company_id: uuid.UUID, unit_id: int, hacienda_unit_code: str | None
    ) -> UnitFiscal:
        await self.get_unit(company_id, unit_id)
        code = None
        if hacienda_unit_code is not None and hacienda_unit_code.strip():
            known = frozenset(e.code for e in await self._repo.catalog(UNIT_CATALOG))
            code = validate_unit_code(hacienda_unit_code, known)
        return await self._repo.save_unit_code(company_id, unit_id, code)
