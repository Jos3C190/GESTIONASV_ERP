"""DTOs del cálculo fiscal de documentos de venta (bloque V2a)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_IN = ConfigDict(extra="forbid", str_strip_whitespace=True)
_MONEY = Field(default=Decimal("0"), ge=0, max_digits=19, decimal_places=8)


class TaxCalculationLineIn(BaseModel):
    model_config = _IN

    product_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=19, decimal_places=8)
    unit_price: Decimal = Field(ge=0, max_digits=19, decimal_places=8)
    price_includes_vat: bool
    discount: Decimal = _MONEY


class GlobalDiscountsIn(BaseModel):
    model_config = _IN

    taxed: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    exempt: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    not_subject: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)


class TaxCalculationIn(BaseModel):
    model_config = _IN

    document_type: Literal["01", "03"]
    customer_id: uuid.UUID | None = None
    lines: list[TaxCalculationLineIn] = Field(min_length=1, max_length=500)
    global_discounts: GlobalDiscountsIn = Field(default_factory=GlobalDiscountsIn)


class TaxCalculationLineOut(BaseModel):
    product_id: int
    sku: str
    name: str
    hacienda_unit_code: str | None
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    not_subject: Decimal
    exempt: Decimal
    taxed: Decimal
    vat_item: Decimal | None


class TaxSummaryOut(BaseModel):
    total_not_subject: Decimal
    total_exempt: Decimal
    total_taxed: Decimal
    subtotal_sales: Decimal
    discount_not_subject: Decimal
    discount_exempt: Decimal
    discount_taxed: Decimal
    total_discount: Decimal
    subtotal: Decimal
    vat: Decimal
    vat_perceived: Decimal
    vat_withheld: Decimal
    total_operation: Decimal
    total_to_pay: Decimal
    total_in_words: str


class TaxCalculationOut(BaseModel):
    document_type: str
    customer_id: uuid.UUID | None
    customer_name: str | None
    prices_include_vat: bool
    lines: list[TaxCalculationLineOut]
    summary: TaxSummaryOut
