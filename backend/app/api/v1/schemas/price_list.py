"""DTOs de listas de precios de venta (bloque V2b)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

_IN = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PriceListIn(BaseModel):
    model_config = _IN

    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    prices_include_vat: bool
    is_default: bool = False
    is_active: bool = True


class PriceListOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    prices_include_vat: bool
    is_default: bool
    is_active: bool
    price_count: int
    customer_count: int
    updated_at: datetime


class SellableUnitOut(BaseModel):
    product_id: int
    variant_id: uuid.UUID | None
    sku: str
    name: str
    unit_id: int
    unit_name: str
    factor: Decimal
    is_base: bool


class PriceEntryOut(BaseModel):
    id: uuid.UUID
    price_list_id: uuid.UUID
    product_id: int
    variant_id: uuid.UUID | None
    unit_id: int
    branch_id: uuid.UUID | None
    branch_name: str | None
    price: Decimal
    valid_from: date
    valid_to: date | None
    status: str
    created_by_name: str | None
    created_at: datetime


class ListedPriceOut(BaseModel):
    unit: SellableUnitOut
    current: PriceEntryOut | None
    next: PriceEntryOut | None
    branch_overrides: int


class PriceIn(BaseModel):
    model_config = _IN

    product_id: int = Field(gt=0)
    variant_id: uuid.UUID | None = None
    unit_id: int = Field(gt=0)
    branch_id: uuid.UUID | None = None
    price: Decimal = Field(ge=0, max_digits=19, decimal_places=8)
    valid_from: date | None = None


class EndPriceIn(BaseModel):
    model_config = _IN

    ends_on: date


class ResolvedPriceOut(BaseModel):
    found: bool
    price: Decimal | None
    prices_include_vat: bool | None
    price_list_id: uuid.UUID | None
    price_list_name: str | None
    source: str | None
    branch_specific: bool
    entry_id: uuid.UUID | None
    valid_to: date | None
    message: str | None
