"""Puerto de la clasificación fiscal de productos y unidades. Toda operación recibe la empresa."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.domain.entities.product_fiscal import (
    CatalogEntry,
    DteItemType,
    ProductFiscal,
    TaxTreatment,
    UnitFiscal,
)


class ProductFiscalRepository(Protocol):
    async def catalog(self, catalog_code: str) -> list[CatalogEntry]: ...

    async def get_product(self, company_id: uuid.UUID, product_id: int) -> ProductFiscal | None: ...

    async def save_product(
        self,
        company_id: uuid.UUID,
        product_id: int,
        *,
        tax_treatment: TaxTreatment,
        dte_item_type: DteItemType | None,
        additional_tax_codes: tuple[str, ...],
    ) -> ProductFiscal: ...

    async def list_units(self, company_id: uuid.UUID) -> list[UnitFiscal]: ...

    async def get_unit(self, company_id: uuid.UUID, unit_id: int) -> UnitFiscal | None: ...

    async def save_unit_code(
        self, company_id: uuid.UUID, unit_id: int, hacienda_unit_code: str | None
    ) -> UnitFiscal: ...
