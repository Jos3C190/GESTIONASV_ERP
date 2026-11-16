"""DTOs de la clasificación fiscal de productos y unidades."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.product_fiscal import DteItemType, TaxTreatment

_IN = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CatalogEntryOut(BaseModel):
    code: str
    name: str


class FiscalOptionsOut(BaseModel):
    taxes: list[CatalogEntryOut]
    units: list[CatalogEntryOut]


class UnitFiscalOut(BaseModel):
    unit_id: int
    code: str
    name: str
    symbol: str
    is_enabled: bool
    hacienda_unit_code: str | None
    suggested_code: str
    effective_code: str
    hacienda_unit_name: str | None


class UnitFiscalIn(BaseModel):
    model_config = _IN

    hacienda_unit_code: str | None = Field(default=None, max_length=2)


class ProductFiscalOut(BaseModel):
    product_id: int
    product_uuid: uuid.UUID
    sku: str
    name: str
    product_kind: str
    can_sell: bool
    tax_treatment: TaxTreatment
    dte_item_type: DteItemType | None
    effective_item_type: DteItemType
    additional_taxes: list[CatalogEntryOut]
    sale_unit: UnitFiscalOut | None
    billing_issues: list[str]


class ProductFiscalIn(BaseModel):
    model_config = _IN

    tax_treatment: TaxTreatment
    dte_item_type: DteItemType | None = None
    additional_tax_codes: list[str] = Field(default_factory=list, max_length=10)
